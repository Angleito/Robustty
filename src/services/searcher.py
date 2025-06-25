import asyncio
import logging
import time
from typing import Any, Coroutine, Dict, List, Optional, Tuple

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
)
from src.services.platform_prioritization import get_prioritization_manager

try:
    from src.services.deduplication import CrossPlatformDeduplicator
    DEDUPLICATION_AVAILABLE = True
except ImportError:
    DEDUPLICATION_AVAILABLE = False
    logger.warning("Deduplication module not available")

logger = logging.getLogger(__name__)


class MultiPlatformSearcher:
    """Searches across multiple video platforms"""

    def __init__(self, platform_registry: PlatformRegistry, config: Optional[Dict[str, Any]] = None):
        self.platform_registry = platform_registry
        self.status_reporter = get_status_reporter()
        self._last_search_status: Optional[MultiPlatformStatus] = None
        # Cache manager will be accessible through the platform registry
        
        # Initialize deduplication if available
        self.deduplicator = None
        if DEDUPLICATION_AVAILABLE and config:
            dedup_config = config.get('deduplication', {})
            if dedup_config.get('enabled', False):
                self.deduplicator = CrossPlatformDeduplicator(dedup_config)
                logger.info("Cross-platform deduplication enabled")

    async def search_all_platforms(
        self, query: str, max_results: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all enabled platforms with enhanced error handling and fallback"""
        results: Dict[str, List[Dict[str, Any]]] = {}
        platforms = self.platform_registry.get_enabled_platforms()
        platform_reports: Dict[str, StatusReport] = {}

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
                    if platform_name == video_info['platform']:
                        # Original platform - direct URL processing
                        platform_reports[platform_name] = StatusReport.create_direct_url_success(
                            platform_name,
                            f"Direct URL processing successful",
                            details={'results_count': len(platform_results)}
                        )
                    else:
                        # Mirror search on other platforms
                        platform_reports[platform_name] = StatusReport.create_search_success(
                            platform_name,
                            SearchMethod.MIRROR_SEARCH,
                            len(platform_results),
                            f"Mirror search successful"
                        )
                else:
                    platform_reports[platform_name] = StatusReport.create_platform_error(
                        platform_name,
                        SearchMethod.MIRROR_SEARCH if platform_name != video_info['platform'] else SearchMethod.DIRECT_URL,
                        "No results found",
                        f"No results found for {platform_name}"
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
                    platform = video.get('platform', 'unknown')
                    if platform not in deduplicated_by_platform:
                        deduplicated_by_platform[platform] = []
                    
                    # Remove platform tag and quality metadata before returning
                    clean_video = {k: v for k, v in video.items() 
                                 if not k.startswith('_') and k != 'platform'}
                    deduplicated_by_platform[platform].append(clean_video)
                
                # Log deduplication summary
                dedup_summary = self.deduplicator.get_deduplication_summary(dedup_result)
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
                    'summary': self.deduplicator.get_deduplication_summary(dedup_result),
                    'stats': dedup_result.deduplication_stats,
                    'duplicate_groups_count': len(dedup_result.duplicate_groups),
                    'removed_count': len(dedup_result.removed_duplicates)
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
        elif DEDUPLICATION_AVAILABLE and config.get('enabled', False):
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
        self, platform: VideoPlatform, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """Search on a specific platform with enhanced error handling"""
        start_time = time.time()
        prioritization_manager = get_prioritization_manager()
        
        try:
            logger.debug(f"Searching {platform.name} for: {query}")
            results = await platform.search_videos(query, max_results)
            response_time = time.time() - start_time
            
            logger.debug(f"{platform.name} returned {len(results)} results in {response_time:.2f}s")
            
            # Record successful operation for prioritization
            if prioritization_manager:
                prioritization_manager.record_platform_operation(
                    platform.name, success=True, response_time=response_time
                )
            
            return results

        except PlatformRateLimitError as e:
            response_time = time.time() - start_time
            logger.warning(f"Rate limit hit on {platform.name}: {e.user_message}")
            
            # Record failure for prioritization
            if prioritization_manager:
                prioritization_manager.record_platform_operation(
                    platform.name, success=False, response_time=response_time, error_type="rate_limit"
                )
            
            # Don't retry rate limits, return empty results
            return []

        except CircuitBreakerOpenError as e:
            response_time = time.time() - start_time
            logger.warning(f"Circuit breaker open for {platform.name}: {e}")
            
            # Record failure for prioritization
            if prioritization_manager:
                prioritization_manager.record_platform_operation(
                    platform.name, success=False, response_time=response_time, error_type="circuit_breaker"
                )
            
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
                    platform.name, success=False, response_time=response_time, error_type="unavailable"
                )
            
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
                    platform.name, success=False, response_time=response_time, error_type="platform_error"
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
                    platform.name, success=False, response_time=response_time, error_type="unexpected_error"
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
        self, platforms: Dict[str, VideoPlatform], query: str, max_results: int
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, StatusReport]]:
        """Search all platforms with fallback and prioritization"""
        results: Dict[str, List[Dict[str, Any]]] = {}
        platform_reports: Dict[str, StatusReport] = {}

        # Use dynamic prioritization if available, otherwise fall back to static
        prioritization_manager = get_prioritization_manager()
        if prioritization_manager and prioritization_manager.enabled:
            # Get dynamically prioritized platform order
            priority_order = prioritization_manager.get_platform_priority_order(platforms)
            logger.debug(f"Using dynamic platform prioritization: {priority_order}")
            sorted_platforms = [(name, platforms[name]) for name in priority_order if name in platforms]
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
            logger.debug(f"Using static platform prioritization: {[name for name, _ in sorted_platforms]}")

        # Execute searches with controlled concurrency
        semaphore = asyncio.Semaphore(3)  # Limit concurrent platform searches

        async def search_with_semaphore(name: str, platform: VideoPlatform):
            async with semaphore:
                return name, await self._search_single_platform(
                    platform, query, max_results
                )

        tasks = [
            search_with_semaphore(name, platform) for name, platform in sorted_platforms
        ]

        # Execute all searches with timeout
        try:
            search_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0,  # 30 second total timeout for all searches
            )

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
                        f"{name} search failed: {str(platform_results)[:100]}"
                    )
                else:
                    results[name] = platform_results
                    if platform_results:
                        platform_reports[name] = StatusReport.create_search_success(
                            name,
                            SearchMethod.API_SEARCH,
                            len(platform_results),
                            f"Search successful - found {len(platform_results)} results"
                        )
                    else:
                        platform_reports[name] = StatusReport.create_platform_error(
                            name,
                            SearchMethod.API_SEARCH,
                            "No results found",
                            f"Search completed but no results found"
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
                        f"{name} search timed out"
                    )

        return results, platform_reports

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
