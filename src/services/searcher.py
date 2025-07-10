import asyncio
import logging
import time
from typing import Any, Coroutine, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from src.platforms.base import VideoPlatform
    from src.platforms.registry import PlatformRegistry
from src.platforms.errors import (
    PlatformError,
    PlatformNotAvailableError,
    PlatformRateLimitError,
)
from src.utils.network_resilience import (
    with_retry,
    PLATFORM_RETRY_CONFIG,
    PLATFORM_CIRCUIT_BREAKER_CONFIG,
    NetworkResilienceError,
    CircuitBreakerOpenError,
    MaxRetriesExceededError,
    get_resilience_manager,
)
from src.services.status_reporting import (
    SearchMethod,
    PlatformStatus,
    StatusReport,
    MultiPlatformStatus,
    get_status_reporter,
    report_search_success,
    report_platform_error,
    report_direct_url_success,
    report_fallback_success,
    report_api_quota_exceeded,
)
from src.services.platform_prioritization import get_prioritization_manager

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.services.cache_manager import CacheManager
    from src.services.stability_monitor import StabilityMonitor

try:
    from src.services.deduplication import CrossPlatformDeduplicator

    DEDUPLICATION_AVAILABLE = True
except ImportError:
    DEDUPLICATION_AVAILABLE = False
    logger.warning("Deduplication module not available")


class MultiPlatformSearcher:
    """Searches across multiple video platforms with enhanced caching and fallback strategies"""

    def __init__(
        self,
        platform_registry: 'PlatformRegistry',
        config: Optional[Dict[str, Any]] = None,
        stability_monitor: Optional['StabilityMonitor'] = None,
    ):
        self.platform_registry = platform_registry
        self.status_reporter = get_status_reporter()
        self._last_search_status: Optional[MultiPlatformStatus] = None
        self.config = config or {}
        self.stability_monitor = stability_monitor
        
        # Task management for proper cleanup
        self._background_tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

        # Enhanced cache configuration
        cache_config = self.config.get("cache", {})
        self.cache_first_enabled = cache_config.get("cache_first_search", True)
        self.stale_cache_threshold_minutes = cache_config.get(
            "stale_cache_threshold_minutes", 60
        )
        self.serve_stale_on_failure = cache_config.get("serve_stale_on_failure", True)
        self.cache_enrichment_enabled = cache_config.get("enrich_cached_results", True)

        # YouTube-specific fallback configuration
        youtube_config = self.config.get("platforms", {}).get("youtube", {})
        self.youtube_fallback_timeout = youtube_config.get(
            "fallback_timeout_seconds", 15
        )
        self.youtube_concurrent_fallbacks = youtube_config.get(
            "concurrent_fallbacks", False
        )
        self.youtube_max_fallback_strategies = youtube_config.get(
            "max_fallback_strategies", 3
        )

        # Initialize deduplication if available
        self.deduplicator = None
        if DEDUPLICATION_AVAILABLE and config:
            dedup_config = config.get("deduplication", {})
            if dedup_config.get("enabled", False):
                self.deduplicator = CrossPlatformDeduplicator(dedup_config)
                logger.info("Cross-platform deduplication enabled")

    async def search_all_platforms(
        self, query: str, max_results: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all enabled platforms with cache-first approach and enhanced fallback"""
        results: Dict[str, List[Dict[str, Any]]] = {}
        platforms = self.platform_registry.get_enabled_platforms()
        platform_reports: Dict[str, StatusReport] = {}
        cache_manager = self._get_cache_manager()

        # Step 1: Check cache first (before anything else)
        if self.cache_first_enabled and cache_manager:
            cached_results = await self._check_all_platform_caches(query, platforms)
            if cached_results:
                logger.info(f"Found cached results for query: {query}")
                # Enrich cache results with metadata
                if self.cache_enrichment_enabled:
                    cached_results = await self._enrich_cache_results(
                        cached_results, is_stale=False
                    )

                # Create cache hit reports
                for platform_name, platform_results in cached_results.items():
                    if platform_results:
                        platform_reports[platform_name] = (
                            StatusReport.create_search_success(
                                platform_name,
                                SearchMethod.CACHE_HIT,
                                len(platform_results),
                                "Results served from cache (fresh)",
                            )
                        )

                # Still check for new results in background if configured
                if self.config.get("background_refresh_cache", True):
                    task = asyncio.create_task(
                        self._background_refresh_search(query, platforms, max_results)
                    )
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)

                # Store status and return early
                self._last_search_status = (
                    self.status_reporter.create_multi_platform_status(
                        query,
                        platform_reports,
                        sum(len(r) for r in cached_results.values()),
                    )
                )
                return cached_results

        # Check service health before attempting searches
        resilience_manager = get_resilience_manager()
        service_status = resilience_manager.get_all_status()

        logger.info(
            f"Starting multi-platform search for: {query} (max_results: {max_results})"
        )
        logger.debug(f"Available platforms: {list(platforms.keys())}")

        # Check if query is a URL
        video_info = self._extract_video_info(query)

        if video_info:
            # URL-based search with enhanced error handling
            logger.info(
                f"Detected URL for platform {video_info['platform']}: {video_info['id']}"
            )
            results = await self._search_for_mirrors_with_fallback(
                video_info, max_results
            )

            # Create status reports for URL-based search
            for platform_name, platform_results in results.items():
                if platform_results:
                    if platform_name == video_info["platform"]:
                        # Original platform - direct URL processing
                        platform_reports[platform_name] = (
                            StatusReport.create_direct_url_success(
                                platform_name,
                                f"Direct URL processing successful",
                                details={"results_count": len(platform_results)},
                            )
                        )
                    else:
                        # Mirror search on other platforms
                        platform_reports[platform_name] = (
                            StatusReport.create_search_success(
                                platform_name,
                                SearchMethod.MIRROR_SEARCH,
                                len(platform_results),
                                f"Mirror search successful",
                            )
                        )
                else:
                    platform_reports[platform_name] = (
                        StatusReport.create_platform_error(
                            platform_name,
                            (
                                SearchMethod.MIRROR_SEARCH
                                if platform_name != video_info["platform"]
                                else SearchMethod.DIRECT_URL
                            ),
                            "No results found",
                            f"No results found for {platform_name}",
                        )
                    )
        else:
            # Text-based search with parallel execution and fallback
            results, platform_reports = await self._search_all_platforms_with_fallback(
                platforms, query, max_results
            )

        # Log search summary
        total_results = sum(
            len(platform_results) for platform_results in results.values()
        )
        successful_platforms = [name for name, res in results.items() if res]
        failed_platforms = [name for name, res in results.items() if not res]

        logger.info(
            f"Search completed: {total_results} total results from {len(successful_platforms)} platforms"
        )
        if successful_platforms:
            logger.debug(f"Successful platforms: {successful_platforms}")
        if failed_platforms:
            logger.warning(f"Failed platforms: {failed_platforms}")

        # Create and store multi-platform status
        multi_status = self.status_reporter.create_multi_platform_status(
            query, platform_reports, total_results
        )

        # Store the multi-platform status for later retrieval
        self._last_search_status = multi_status

        # Apply deduplication if enabled
        if self.deduplicator and total_results > 1:
            try:
                dedup_result = self.deduplicator.deduplicate_search_results(results)

                # Reorganize deduplicated results back into platform format
                deduplicated_by_platform = {}
                for video in dedup_result.deduplicated_videos:
                    platform = video.get("platform", "unknown")
                    if platform not in deduplicated_by_platform:
                        deduplicated_by_platform[platform] = []

                    # Remove quality metadata before returning (keep platform field)
                    clean_video = {
                        k: v
                        for k, v in video.items()
                        if not k.startswith("_")
                    }
                    deduplicated_by_platform[platform].append(clean_video)

                # Log deduplication summary
                dedup_summary = self.deduplicator.get_deduplication_summary(
                    dedup_result
                )
                logger.info(f"Deduplication applied: {dedup_summary}")

                return deduplicated_by_platform

            except Exception as e:
                logger.warning(f"Deduplication failed, returning original results: {e}")
                return results

        return results

    def get_last_search_status(self) -> Optional[MultiPlatformStatus]:
        """Get the status of the last search operation"""
        return self._last_search_status

    async def search_all_platforms_with_deduplication(
        self, query: str, max_results: int = 10, enable_deduplication: bool = True
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Optional[Dict[str, Any]]]:
        """Search with explicit deduplication control, returning results and deduplication info"""
        # Temporarily override deduplication setting
        original_deduplicator = self.deduplicator
        if not enable_deduplication:
            self.deduplicator = None

        try:
            results = await self.search_all_platforms(query, max_results)

            # If deduplication was applied, get the summary
            dedup_info = None
            if self.deduplicator and enable_deduplication:
                # Run deduplication again to get detailed info
                dedup_result = self.deduplicator.deduplicate_search_results(results)
                dedup_info = {
                    "summary": self.deduplicator.get_deduplication_summary(
                        dedup_result
                    ),
                    "stats": dedup_result.deduplication_stats,
                    "duplicate_groups_count": len(dedup_result.duplicate_groups),
                    "removed_count": len(dedup_result.removed_duplicates),
                }

            return results, dedup_info

        finally:
            # Restore original deduplicator
            self.deduplicator = original_deduplicator

    def configure_deduplication(self, config: Dict[str, Any]):
        """Update deduplication configuration"""
        if self.deduplicator:
            self.deduplicator.update_config(config)
            logger.info("Deduplication configuration updated")
        elif DEDUPLICATION_AVAILABLE and config.get("enabled", False):
            self.deduplicator = CrossPlatformDeduplicator(config)
            logger.info("Deduplication enabled with new configuration")

    def get_deduplication_config(self) -> Optional[Dict[str, Any]]:
        """Get current deduplication configuration"""
        if self.deduplicator:
            return self.deduplicator.get_current_config()
        return None

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="platform_search",
        exceptions=(PlatformError, ConnectionError, TimeoutError),
        exclude_exceptions=(PlatformRateLimitError, CircuitBreakerOpenError),
    )
    async def _search_single_platform(
        self, platform: 'VideoPlatform', query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """Search on a specific platform with enhanced error handling and fallback"""
        start_time = time.time()
        prioritization_manager = get_prioritization_manager()

        # Special handling for YouTube with full fallback chain
        if platform.name.lower() == "youtube":
            return await self._search_youtube_with_fallback(
                platform, query, max_results
            )

        try:
            logger.debug(f"Searching {platform.name} for: {query}")
            results = await platform.search_videos(query, max_results)
            response_time = time.time() - start_time

            logger.debug(
                f"{platform.name} returned {len(results)} results in {response_time:.2f}s"
            )

            # Record successful operation for prioritization
            if prioritization_manager:
                prioritization_manager.record_platform_operation(
                    platform.name, success=True, response_time=response_time
                )
                
            # Record success in stability monitor
            if self.stability_monitor:
                await self.stability_monitor.record_platform_success(platform.name)

            return results

        except PlatformRateLimitError as e:
            response_time = time.time() - start_time
            logger.warning(f"Rate limit hit on {platform.name}: {e.user_message}")

            # Record failure for prioritization
            if prioritization_manager:
                prioritization_manager.record_platform_operation(
                    platform.name,
                    success=False,
                    response_time=response_time,
                    error_type="rate_limit",
                )
                
            # Record failure in stability monitor
            if self.stability_monitor:
                await self.stability_monitor.record_platform_failure(
                    platform.name, "rate_limit"
                )

            # Check if we should serve stale cache
            if await self._should_serve_stale_cache(platform.name, "rate_limit"):
                stale_results = await self._get_stale_cache_results(
                    platform.name, query
                )
                if stale_results:
                    return stale_results

            # Don't retry rate limits, return empty results
            return []

        except CircuitBreakerOpenError as e:
            response_time = time.time() - start_time
            logger.warning(f"Circuit breaker open for {platform.name}: {e}")

            # Record failure for prioritization
            if prioritization_manager:
                prioritization_manager.record_platform_operation(
                    platform.name,
                    success=False,
                    response_time=response_time,
                    error_type="circuit_breaker",
                )
                
            # Record failure in stability monitor
            if self.stability_monitor:
                await self.stability_monitor.record_platform_failure(
                    platform.name, "circuit_breaker"
                )

            # Check if we should serve stale cache
            if await self._should_serve_stale_cache(
                platform.name, "circuit_breaker_open"
            ):
                stale_results = await self._get_stale_cache_results(
                    platform.name, query
                )
                if stale_results:
                    return stale_results

            # Service temporarily unavailable
            return []

        except PlatformNotAvailableError as e:
            response_time = time.time() - start_time
            logger.warning(
                f"Platform {platform.name} temporarily unavailable: {e.user_message}"
            )

            # Record failure for prioritization
            if prioritization_manager:
                prioritization_manager.record_platform_operation(
                    platform.name,
                    success=False,
                    response_time=response_time,
                    error_type="unavailable",
                )
                
            # Record failure in stability monitor
            if self.stability_monitor:
                await self.stability_monitor.record_platform_failure(
                    platform.name, "unavailable"
                )

            # Check if we should serve stale cache
            if await self._should_serve_stale_cache(
                platform.name, "platform_unavailable"
            ):
                stale_results = await self._get_stale_cache_results(
                    platform.name, query
                )
                if stale_results:
                    return stale_results

            # Platform is down, log but don't fail entire search
            return []

        except PlatformError as e:
            response_time = time.time() - start_time
            logger.error(f"Platform error on {platform.name}: {e.user_message}")

            # Platform-specific error, log details for debugging
            if hasattr(e, "original_error") and e.original_error:
                logger.debug(f"Original error: {e.original_error}")

            # Record failure for prioritization
            if prioritization_manager:
                prioritization_manager.record_platform_operation(
                    platform.name,
                    success=False,
                    response_time=response_time,
                    error_type="platform_error",
                )
                
            # Record failure in stability monitor
            if self.stability_monitor:
                await self.stability_monitor.record_platform_failure(
                    platform.name, "platform_error"
                )

            return []

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Unexpected error searching {platform.name}: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")

            # Record failure for prioritization
            if prioritization_manager:
                prioritization_manager.record_platform_operation(
                    platform.name,
                    success=False,
                    response_time=response_time,
                    error_type="unexpected_error",
                )
                
            # Record failure in stability monitor
            if self.stability_monitor:
                await self.stability_monitor.record_platform_failure(
                    platform.name, "unexpected_error"
                )

            return []

    def _extract_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract video info from URL"""
        platforms = self.platform_registry.get_all_platforms()
        for name, platform in platforms.items():
            if platform.is_platform_url(url):
                video_id = platform.extract_video_id(url)
                if video_id:
                    return {"platform": name, "id": video_id, "url": url}
        return None

    def get_search_health_status(self) -> Dict[str, Any]:
        """Get health status of search services for debugging"""
        resilience_manager = get_resilience_manager()
        platforms = self.platform_registry.get_enabled_platforms()

        return {
            "enabled_platforms": list(platforms.keys()),
            "total_platforms": len(platforms),
            "resilience_status": resilience_manager.get_all_status(),
            "registry_status": "healthy" if platforms else "no_platforms_enabled",
        }

    async def _search_all_platforms_with_fallback(
        self, platforms: Dict[str, 'VideoPlatform'], query: str, max_results: int
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, StatusReport]]:
        """Search all platforms with fallback and prioritization"""
        results: Dict[str, List[Dict[str, Any]]] = {}
        platform_reports: Dict[str, StatusReport] = {}

        # Use dynamic prioritization if available, otherwise fall back to static
        prioritization_manager = get_prioritization_manager()
        if prioritization_manager and prioritization_manager.enabled:
            # Get dynamically prioritized platform order
            priority_order = prioritization_manager.get_platform_priority_order(
                platforms
            )
            logger.debug(f"Using dynamic platform prioritization: {priority_order}")
            sorted_platforms = [
                (name, platforms[name]) for name in priority_order if name in platforms
            ]
        else:
            # Fall back to static prioritization
            platform_priority = ["youtube", "odysee", "peertube", "rumble"]
            sorted_platforms = sorted(
                platforms.items(),
                key=lambda x: (
                    platform_priority.index(x[0])
                    if x[0] in platform_priority
                    else len(platform_priority)
                ),
            )
            logger.debug(
                f"Using static platform prioritization: {[name for name, _ in sorted_platforms]}"
            )

        # Execute searches with sequential fallback - try YouTube API first, fallback to others only if needed
        search_results = []
        primary_success = False
        
        # Check stability mode setting for concurrent vs sequential execution
        stability_config = self.config.get("stability_mode", {})
        use_sequential = stability_config.get("disable_concurrent_requests", True)
        
        logger.info(f"Search mode config - stability_config: {stability_config}")
        logger.info(f"Search mode: {'sequential' if use_sequential else 'concurrent'}")
        
        if use_sequential:
            # Sequential execution: try platforms in priority order until we get results
            logger.info("Using sequential platform search (YouTube API first, others as fallback)")
            
            for name, platform in sorted_platforms:
                try:
                    logger.info(f"Trying {name} platform...")
                    platform_results = await asyncio.wait_for(
                        self._search_single_platform(platform, query, max_results),
                        timeout=45.0  # Per-platform timeout
                    )
                    
                    search_results.append((name, platform_results))
                    
                    # If we got results from primary platform (YouTube), we're done
                    if platform_results and name == "youtube":
                        logger.info(f"YouTube API successful with {len(platform_results)} results - skipping other platforms")
                        primary_success = True
                        break
                    elif platform_results:
                        # Got results from a fallback platform
                        logger.info(f"{name} successful with {len(platform_results)} results")
                        break
                        
                except Exception as e:
                    logger.warning(f"{name} platform failed: {e}")
                    search_results.append((name, e))
                    
        else:
            # Concurrent execution (original behavior) with controlled concurrency
            logger.info("Using concurrent platform search")
            semaphore = asyncio.Semaphore(3)  # Limit concurrent platform searches

            async def search_with_semaphore(name: str, platform: 'VideoPlatform'):
                async with semaphore:
                    return name, await self._search_single_platform(
                        platform, query, max_results
                    )

            tasks = [
                search_with_semaphore(name, platform) for name, platform in sorted_platforms
            ]

            # Execute all searches with timeout
            search_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0,  # 30 second total timeout for all searches
            )

        # Process search results (both sequential and concurrent modes)
        try:
            for result in search_results:
                if isinstance(result, Exception):
                    logger.error(f"Search task failed: {result}")
                    continue

                name, platform_results = result
                if isinstance(platform_results, Exception):
                    logger.error(f"Platform {name} search failed: {platform_results}")
                    results[name] = []
                    platform_reports[name] = StatusReport.create_platform_error(
                        name,
                        SearchMethod.API_SEARCH,
                        str(platform_results),
                        f"{name} search failed: {str(platform_results)[:100]}",
                    )
                else:
                    results[name] = platform_results
                    if platform_results:
                        platform_reports[name] = StatusReport.create_search_success(
                            name,
                            SearchMethod.API_SEARCH,
                            len(platform_results),
                            f"Search successful - found {len(platform_results)} results",
                        )
                    else:
                        platform_reports[name] = StatusReport.create_platform_error(
                            name,
                            SearchMethod.API_SEARCH,
                            "No results found",
                            f"Search completed but no results found",
                        )

        except asyncio.TimeoutError:
            logger.warning(
                f"Multi-platform search timed out after 30 seconds for query: {query}"
            )
            # Return partial results and create timeout reports
            for name, _ in sorted_platforms:
                if name not in results:
                    results[name] = []
                    platform_reports[name] = StatusReport.create_platform_error(
                        name,
                        SearchMethod.API_SEARCH,
                        "Search timeout",
                        f"{name} search timed out",
                    )

        return results, platform_reports

    def _get_cache_manager(self) -> Optional["CacheManager"]:
        """Get cache manager from platform registry or configuration"""
        # Try to get from any platform that has it
        platforms = self.platform_registry.get_all_platforms()
        for platform in platforms.values():
            if hasattr(platform, "cache_manager") and platform.cache_manager:
                return platform.cache_manager
        return None

    async def _check_all_platform_caches(
        self, query: str, platforms: Dict[str, 'VideoPlatform']
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Check cache for all platforms in parallel"""
        cache_manager = self._get_cache_manager()
        if not cache_manager:
            return {}

        cached_results = {}
        cache_tasks = []

        for platform_name in platforms:
            task = asyncio.create_task(
                cache_manager.get_search_results(platform_name, query)
            )
            cache_tasks.append((platform_name, task))

        # Check all caches in parallel
        for platform_name, task in cache_tasks:
            try:
                results = await task
                if results:
                    cached_results[platform_name] = results
            except Exception as e:
                logger.debug(f"Cache check failed for {platform_name}: {e}")

        return cached_results

    async def _enrich_cache_results(
        self, results: Dict[str, List[Dict[str, Any]]], is_stale: bool
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Add cache metadata to results"""
        enriched_results = {}

        for platform_name, platform_results in results.items():
            enriched_results[platform_name] = []
            for result in platform_results:
                enriched_result = result.copy()
                enriched_result["_cache_metadata"] = {
                    "from_cache": True,
                    "is_stale": is_stale,
                    "cached_at": result.get("_cached_at", "unknown"),
                }
                enriched_results[platform_name].append(enriched_result)

        return enriched_results

    async def _should_serve_stale_cache(
        self, platform_name: str, error_type: str
    ) -> bool:
        """Determine if stale cache should be served based on error type"""
        # Always serve stale cache for these error types
        critical_errors = {
            "quota_exceeded",
            "rate_limit",
            "authentication_error",
            "circuit_breaker_open",
            "platform_unavailable",
        }

        if error_type in critical_errors:
            return True

        # Check platform-specific configuration
        platform_config = self.config.get("platforms", {}).get(platform_name, {})
        return platform_config.get("serve_stale_on_error", self.serve_stale_on_failure)

    async def _get_stale_cache_results(
        self, platform_name: str, query: str, max_age_minutes: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get potentially stale cache results within acceptable age"""
        cache_manager = self._get_cache_manager()
        if not cache_manager:
            return None

        max_age = max_age_minutes or self.stale_cache_threshold_minutes

        # For now, just try to get from cache (could be enhanced with timestamp checking)
        try:
            results = await cache_manager.get_search_results(platform_name, query)
            if results:
                logger.info(
                    f"Serving stale cache for {platform_name} due to platform errors"
                )
                return results
        except Exception as e:
            logger.debug(f"Failed to get stale cache for {platform_name}: {e}")

        return None

    async def _search_youtube_with_fallback(
        self, platform: 'VideoPlatform', query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """Enhanced YouTube search with full fallback chain"""
        logger.info(f"Starting YouTube search with enhanced fallback for: {query}")

        # Track which strategy succeeded
        successful_strategy = None
        error_details = {}

        # Strategy 1: Check cache first (freshest data)
        cache_manager = self._get_cache_manager()
        if cache_manager:
            try:
                cached_results = await cache_manager.get_search_results(
                    "youtube", query
                )
                if cached_results:
                    logger.info("YouTube search: Using fresh cached results")
                    successful_strategy = "cache"
                    return cached_results
            except Exception as e:
                logger.debug(f"Cache check failed: {e}")
                error_details["cache"] = str(e)

        # Strategy 2: Try normal API search
        try:
            results = await platform.search_videos(query, max_results)
            if results:
                logger.info("YouTube search: API search successful")
                successful_strategy = "api"
                # Cache the results
                if cache_manager:
                    await cache_manager.set_search_results("youtube", query, results)
                return results
        except Exception as e:
            logger.warning(f"YouTube API search failed: {e}")
            error_details["api"] = str(e)

            # Check if it's a quota error
            if "quota" in str(e).lower():
                report_api_quota_exceeded(
                    "YouTube", "API quota exceeded, trying fallback strategies"
                )

        # Strategy 3: Try yt-dlp fallback (if available)
        if hasattr(platform, "_search_with_ytdlp"):
            try:
                logger.info("YouTube search: Attempting yt-dlp fallback")
                ytdlp_results = await platform._search_with_ytdlp(query, max_results)
                if ytdlp_results:
                    logger.info(
                        f"YouTube search: yt-dlp fallback successful, found {len(ytdlp_results)} results"
                    )
                    successful_strategy = "ytdlp"
                    report_fallback_success(
                        "YouTube",
                        SearchMethod.YTDLP_SEARCH,
                        f"yt-dlp fallback successful after API failure",
                        details={
                            "results_count": len(ytdlp_results),
                            "errors": error_details,
                        },
                    )
                    # Cache the results
                    if cache_manager:
                        await cache_manager.set_search_results(
                            "youtube", query, ytdlp_results
                        )
                    return ytdlp_results
            except Exception as e:
                logger.warning(f"yt-dlp fallback failed: {e}")
                error_details["ytdlp"] = str(e)

        # Strategy 4: Try stale cache (older but still useful)
        if cache_manager and self.serve_stale_on_failure:
            try:
                # Try to get any cached results, even if stale
                stale_results = await self._get_stale_cache_results(
                    "youtube", query, max_age_minutes=24 * 60
                )  # Up to 24 hours old
                if stale_results:
                    logger.info(
                        "YouTube search: Using stale cache due to all strategies failing"
                    )
                    successful_strategy = "stale_cache"
                    # Enrich with stale metadata
                    if self.cache_enrichment_enabled:
                        enriched_results = await self._enrich_cache_results(
                            {"youtube": stale_results}, is_stale=True
                        )
                        stale_results = enriched_results.get("youtube", stale_results)

                    report_fallback_success(
                        "YouTube",
                        SearchMethod.CACHE_HIT,
                        "Serving stale cache after all strategies failed",
                        details={"is_stale": True, "errors": error_details},
                    )
                    return stale_results
            except Exception as e:
                logger.debug(f"Stale cache retrieval failed: {e}")
                error_details["stale_cache"] = str(e)

        # All strategies failed
        logger.error(f"All YouTube search strategies failed for query: {query}")
        logger.debug(f"Error details: {error_details}")

        report_platform_error(
            "YouTube",
            SearchMethod.API_SEARCH,
            "All search strategies failed",
            f"Unable to search YouTube. Errors: {', '.join(f'{k}: {v[:50]}' for k, v in error_details.items())}",
        )

        return []

    async def _background_refresh_search(
        self, query: str, platforms: Dict[str, 'VideoPlatform'], max_results: int
    ):
        """Background task to refresh cached search results"""
        try:
            logger.debug(f"Starting background refresh for query: {query}")
            # Perform actual search
            results, _ = await self._search_all_platforms_with_fallback(
                platforms, query, max_results
            )

            # Update cache with fresh results
            cache_manager = self._get_cache_manager()
            if cache_manager:
                for platform_name, platform_results in results.items():
                    if platform_results:
                        await cache_manager.set_search_results(
                            platform_name, query, platform_results
                        )

            logger.debug(f"Background refresh completed for query: {query}")
        except Exception as e:
            logger.debug(f"Background refresh failed for query '{query}': {e}")

    async def _search_for_mirrors_with_fallback(
        self, video_info: Dict[str, Any], max_results: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search for mirrors of a video on other platforms with enhanced error handling"""
        results: Dict[str, List[Dict[str, Any]]] = {}
        source_platform = self.platform_registry.get_platform(video_info["platform"])

        if source_platform is None:
            logger.error(f"Platform {video_info['platform']} not found")
            return results

        try:
            # Get video details from source platform with timeout
            video_details = await asyncio.wait_for(
                source_platform.get_video_details(video_info["id"]), timeout=15.0
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout getting video details from {video_info['platform']}"
            )
            # Fallback: create basic video info from URL
            video_details = {
                "id": video_info["id"],
                "title": f"Video {video_info['id']}",
                "url": video_info["url"],
                "platform": video_info["platform"],
            }
        except Exception as e:
            logger.error(
                f"Failed to get video details from {video_info['platform']}: {e}"
            )
            # Still try to create basic info
            video_details = {
                "id": video_info["id"],
                "title": f"Video {video_info['id']}",
                "url": video_info["url"],
                "platform": video_info["platform"],
            }

        if video_details and "title" in video_details:
            # Include the original video first
            results[video_info["platform"]] = [video_details]

            # Search other platforms for mirrors
            search_query = video_details["title"]
            platforms = self.platform_registry.get_enabled_platforms()

            # Filter out source platform
            other_platforms = {
                name: platform
                for name, platform in platforms.items()
                if name != video_info["platform"]
            }

            if other_platforms:
                logger.info(
                    f"Searching {len(other_platforms)} platforms for mirrors of: {search_query}"
                )
                mirror_results = await self._search_all_platforms_with_fallback(
                    other_platforms, search_query, max_results
                )
                results.update(mirror_results)
        else:
            logger.warning(
                f"Could not extract video details for mirror search: {video_info}"
            )
            # Return just the original platform with basic info
            results[video_info["platform"]] = [video_details] if video_details else []

        return results

    async def cleanup(self):
        """Cleanup searcher resources and cancel background tasks"""
        logger.info("Starting searcher cleanup")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel all background tasks
        if self._background_tasks:
            logger.info(f"Cancelling {len(self._background_tasks)} background tasks")
            for task in self._background_tasks.copy():
                if not task.done():
                    task.cancel()
            
            # Wait for all tasks to complete or be cancelled
            if self._background_tasks:
                try:
                    await asyncio.gather(*self._background_tasks, return_exceptions=True)
                    logger.info("All background tasks completed")
                except Exception as e:
                    logger.error(f"Error waiting for background tasks to complete: {e}")
                
                # Clear the task set
                self._background_tasks.clear()
        
        logger.info("Searcher cleanup completed")
