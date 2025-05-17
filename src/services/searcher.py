import asyncio
import logging
from typing import Any, Coroutine, Dict, List, Optional, Tuple

from src.platforms.base import VideoPlatform
from src.platforms.registry import PlatformRegistry

logger = logging.getLogger(__name__)


class MultiPlatformSearcher:
    """Searches across multiple video platforms"""

    def __init__(self, platform_registry: PlatformRegistry):
        self.platform_registry = platform_registry

    async def search_all_platforms(
        self, query: str, max_results: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all enabled platforms"""
        results: Dict[str, List[Dict[str, Any]]] = {}
        platforms = self.platform_registry.get_enabled_platforms()

        # Check if query is a URL
        video_info = self._extract_video_info(query)

        if video_info:
            # URL-based search
            results = await self._search_for_mirrors(video_info, max_results)
        else:
            # Text-based search
            tasks: List[Tuple[str, Coroutine[Any, Any, List[Dict[str, Any]]]]] = []
            for name, platform in platforms.items():
                task = self._search_single_platform(platform, query, max_results)
                tasks.append((name, task))

            # Execute all searches concurrently
            search_results = await asyncio.gather(
                *[task for _, task in tasks], return_exceptions=True
            )

            for (name, _), result in zip(tasks, search_results):
                if isinstance(result, Exception):
                    logger.error(f"Search error on {name}: {result}")
                    results[name] = []
                elif isinstance(result, list):
                    results[name] = result
                else:
                    results[name] = []

        return results

    async def _search_single_platform(
        self, platform: VideoPlatform, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """Search on a specific platform"""
        try:
            return await platform.search_videos(query, max_results)
        except Exception as e:
            logger.error(f"Error searching {platform.name}: {e}")
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

    async def _search_for_mirrors(
        self, video_info: Dict[str, Any], max_results: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search for mirrors of a video on other platforms"""
        results: Dict[str, List[Dict[str, Any]]] = {}
        source_platform = self.platform_registry.get_platform(video_info["platform"])

        if source_platform is None:
            logger.error(f"Platform {video_info['platform']} not found")
            return results

        # Get video details from source platform
        video_details = await source_platform.get_video_details(video_info["id"])

        if video_details and "title" in video_details:
            # Search other platforms for this video
            search_query = video_details["title"]
            platforms = self.platform_registry.get_enabled_platforms()

            tasks: List[Tuple[str, Coroutine[Any, Any, List[Dict[str, Any]]]]] = []
            for name, platform in platforms.items():
                # Skip source platform
                if name != video_info["platform"]:
                    task = self._search_single_platform(
                        platform, search_query, max_results
                    )
                    tasks.append((name, task))

            # Include the original video
            results[video_info["platform"]] = [video_details]

            # Execute searches
            search_results = await asyncio.gather(
                *[task for _, task in tasks], return_exceptions=True
            )

            for (name, _), result in zip(tasks, search_results):
                if isinstance(result, Exception):
                    logger.error(f"Mirror search error on {name}: {result}")
                    results[name] = []
                elif isinstance(result, list):
                    results[name] = result
                else:
                    results[name] = []

        return results
