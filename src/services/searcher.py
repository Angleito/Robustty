import asyncio
import logging
from typing import Dict, List, Optional
from platforms.registry import PlatformRegistry

logger = logging.getLogger(__name__)

class MultiPlatformSearcher:
    """Searches across multiple video platforms"""
    
    def __init__(self, platform_registry: PlatformRegistry):
        self.platform_registry = platform_registry
    
    async def search_all_platforms(
        self, 
        query: str, 
        max_results: int = 10
    ) -> Dict[str, List[Dict]]:
        """Search across all enabled platforms"""
        results = {}
        platforms = self.platform_registry.get_enabled_platforms()
        
        # Check if query is a URL
        video_info = self._extract_video_info(query)
        
        if video_info:
            # URL-based search
            results = await self._search_for_mirrors(video_info, max_results)
        else:
            # Text-based search
            tasks = []
            for name, platform in platforms.items():
                task = self._search_single_platform(platform, query, max_results)
                tasks.append((name, task))
            
            # Execute all searches concurrently
            search_results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True
            )
            
            for (name, _), result in zip(tasks, search_results):
                if isinstance(result, Exception):
                    logger.error(f"Search error on {name}: {result}")
                    results[name] = []
                else:
                    results[name] = result
        
        return results
    
    async def _search_single_platform(
        self, 
        platform, 
        query: str, 
        max_results: int
    ) -> List[Dict]:
        """Search on a specific platform"""
        try:
            return await platform.search_videos(query, max_results)
        except Exception as e:
            logger.error(f"Error searching {platform.name}: {e}")
            return []
    
    def _extract_video_info(self, url: str) -> Optional[Dict]:
        """Extract video info from URL"""
        for name, platform in self.platform_registry.get_all_platforms().items():
            if platform.is_platform_url(url):
                video_id = platform.extract_video_id(url)
                if video_id:
                    return {
                        'platform': name,
                        'id': video_id,
                        'url': url
                    }
        return None
    
    async def _search_for_mirrors(
        self, 
        video_info: Dict, 
        max_results: int
    ) -> Dict[str, List[Dict]]:
        """Search for mirrors of a video on other platforms"""
        results = {}
        source_platform = self.platform_registry.get_platform(video_info['platform'])
        
        # Get video details from source platform
        video_details = await source_platform.get_video_details(video_info['id'])
        
        if video_details and 'title' in video_details:
            # Search other platforms for this video
            search_query = video_details['title']
            platforms = self.platform_registry.get_enabled_platforms()
            
            tasks = []
            for name, platform in platforms.items():
                if name != video_info['platform']:  # Skip source platform
                    task = self._search_single_platform(platform, search_query, max_results)
                    tasks.append((name, task))
            
            # Include the original video
            results[video_info['platform']] = [video_details]
            
            # Execute searches
            search_results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True
            )
            
            for (name, _), result in zip(tasks, search_results):
                if isinstance(result, Exception):
                    logger.error(f"Mirror search error on {name}: {result}")
                    results[name] = []
                else:
                    results[name] = result
        
        return results