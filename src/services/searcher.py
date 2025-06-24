import asyncio
import logging
from typing import Any, Coroutine, Dict, List, Optional, Tuple

from src.platforms.base import VideoPlatform
from src.platforms.registry import PlatformRegistry
from src.platforms.errors import PlatformError, PlatformNotAvailableError, PlatformRateLimitError
from src.utils.network_resilience import (
    with_retry,
    PLATFORM_RETRY_CONFIG,
    PLATFORM_CIRCUIT_BREAKER_CONFIG,
    NetworkResilienceError,
    CircuitBreakerOpenError,
    MaxRetriesExceededError,
    get_resilience_manager
)

logger = logging.getLogger(__name__)


class MultiPlatformSearcher:
    """Searches across multiple video platforms"""

    def __init__(self, platform_registry: PlatformRegistry):
        self.platform_registry = platform_registry

    async def search_all_platforms(
        self, query: str, max_results: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all enabled platforms with enhanced error handling and fallback"""
        results: Dict[str, List[Dict[str, Any]]] = {}
        platforms = self.platform_registry.get_enabled_platforms()
        
        # Check service health before attempting searches
        resilience_manager = get_resilience_manager()
        service_status = resilience_manager.get_all_status()
        
        logger.info(f"Starting multi-platform search for: {query} (max_results: {max_results})")
        logger.debug(f"Available platforms: {list(platforms.keys())}")

        # Check if query is a URL
        video_info = self._extract_video_info(query)

        if video_info:
            # URL-based search with enhanced error handling
            logger.info(f"Detected URL for platform {video_info['platform']}: {video_info['id']}")
            results = await self._search_for_mirrors_with_fallback(video_info, max_results)
        else:
            # Text-based search with parallel execution and fallback
            results = await self._search_all_platforms_with_fallback(platforms, query, max_results)
        
        # Log search summary
        total_results = sum(len(platform_results) for platform_results in results.values())
        successful_platforms = [name for name, res in results.items() if res]
        failed_platforms = [name for name, res in results.items() if not res]
        
        logger.info(f"Search completed: {total_results} total results from {len(successful_platforms)} platforms")
        if successful_platforms:
            logger.debug(f"Successful platforms: {successful_platforms}")
        if failed_platforms:
            logger.warning(f"Failed platforms: {failed_platforms}")

        return results

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="platform_search",
        exceptions=(PlatformError, ConnectionError, TimeoutError),
        exclude_exceptions=(PlatformRateLimitError, CircuitBreakerOpenError)
    )
    async def _search_single_platform(
        self, platform: VideoPlatform, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """Search on a specific platform with enhanced error handling"""
        try:
            logger.debug(f"Searching {platform.name} for: {query}")
            results = await platform.search_videos(query, max_results)
            logger.debug(f"{platform.name} returned {len(results)} results")
            return results
            
        except PlatformRateLimitError as e:
            logger.warning(f"Rate limit hit on {platform.name}: {e.user_message}")
            # Don't retry rate limits, return empty results
            return []
            
        except CircuitBreakerOpenError as e:
            logger.warning(f"Circuit breaker open for {platform.name}: {e}")
            # Service temporarily unavailable
            return []
            
        except PlatformNotAvailableError as e:
            logger.warning(f"Platform {platform.name} temporarily unavailable: {e.user_message}")
            # Platform is down, log but don't fail entire search
            return []
            
        except PlatformError as e:
            logger.error(f"Platform error on {platform.name}: {e.user_message}")
            # Platform-specific error, log details for debugging
            if hasattr(e, 'original_error') and e.original_error:
                logger.debug(f"Original error: {e.original_error}")
            return []
            
        except Exception as e:
            logger.error(f"Unexpected error searching {platform.name}: {e}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
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
            'enabled_platforms': list(platforms.keys()),
            'total_platforms': len(platforms),
            'resilience_status': resilience_manager.get_all_status(),
            'registry_status': 'healthy' if platforms else 'no_platforms_enabled'
        }

    async def _search_all_platforms_with_fallback(
        self, platforms: Dict[str, VideoPlatform], query: str, max_results: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search all platforms with fallback and prioritization"""
        results: Dict[str, List[Dict[str, Any]]] = {}
        
        # Prioritize platforms by reliability (you can adjust this based on your experience)
        platform_priority = ['youtube', 'odysee', 'peertube', 'rumble']
        sorted_platforms = sorted(
            platforms.items(),
            key=lambda x: platform_priority.index(x[0]) if x[0] in platform_priority else len(platform_priority)
        )
        
        # Execute searches with controlled concurrency
        semaphore = asyncio.Semaphore(3)  # Limit concurrent platform searches
        
        async def search_with_semaphore(name: str, platform: VideoPlatform):
            async with semaphore:
                return name, await self._search_single_platform(platform, query, max_results)
        
        tasks = [search_with_semaphore(name, platform) for name, platform in sorted_platforms]
        
        # Execute all searches with timeout
        try:
            search_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0  # 30 second total timeout for all searches
            )
            
            for result in search_results:
                if isinstance(result, Exception):
                    logger.error(f"Search task failed: {result}")
                    continue
                    
                name, platform_results = result
                if isinstance(platform_results, Exception):
                    logger.error(f"Platform {name} search failed: {platform_results}")
                    results[name] = []
                else:
                    results[name] = platform_results
                    
        except asyncio.TimeoutError:
            logger.warning(f"Multi-platform search timed out after 30 seconds for query: {query}")
            # Return partial results
            for name, _ in sorted_platforms:
                if name not in results:
                    results[name] = []
        
        return results
    
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
                source_platform.get_video_details(video_info["id"]),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting video details from {video_info['platform']}")
            # Fallback: create basic video info from URL
            video_details = {
                'id': video_info['id'],
                'title': f"Video {video_info['id']}",
                'url': video_info['url'],
                'platform': video_info['platform']
            }
        except Exception as e:
            logger.error(f"Failed to get video details from {video_info['platform']}: {e}")
            # Still try to create basic info
            video_details = {
                'id': video_info['id'],
                'title': f"Video {video_info['id']}",
                'url': video_info['url'],
                'platform': video_info['platform']
            }

        if video_details and "title" in video_details:
            # Include the original video first
            results[video_info["platform"]] = [video_details]
            
            # Search other platforms for mirrors
            search_query = video_details["title"]
            platforms = self.platform_registry.get_enabled_platforms()
            
            # Filter out source platform
            other_platforms = {
                name: platform for name, platform in platforms.items() 
                if name != video_info["platform"]
            }
            
            if other_platforms:
                logger.info(f"Searching {len(other_platforms)} platforms for mirrors of: {search_query}")
                mirror_results = await self._search_all_platforms_with_fallback(
                    other_platforms, search_query, max_results
                )
                results.update(mirror_results)
        else:
            logger.warning(f"Could not extract video details for mirror search: {video_info}")
            # Return just the original platform with basic info
            results[video_info["platform"]] = [video_details] if video_details else []

        return results
