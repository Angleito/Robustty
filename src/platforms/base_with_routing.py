"""
Enhanced base platform class with network routing support.

This demonstrates how to integrate the network routing module with
the existing platform system.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import aiohttp

from ..utils.network_routing import get_http_client, ServiceType

if TYPE_CHECKING:
    from ..services.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class VideoPlatformWithRouting(ABC):
    """Abstract base class for video platforms with network routing support"""

    def __init__(self, name: str, config: Dict[str, Any], cache_manager: Optional['CacheManager'] = None):
        self.name = name
        self.config = config
        self.cache_manager = cache_manager
        self.enabled = config.get("enabled", True)
        self._network_client = None
        self._service_type = self._determine_service_type()

    def _determine_service_type(self) -> ServiceType:
        """Determine the service type based on platform name"""
        platform_mapping = {
            'youtube': ServiceType.YOUTUBE,
            'rumble': ServiceType.RUMBLE,
            'odysee': ServiceType.ODYSEE,
            'peertube': ServiceType.PEERTUBE,
        }
        return platform_mapping.get(self.name.lower(), ServiceType.GENERIC)

    @abstractmethod
    async def search_videos(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for videos on the platform"""
        pass

    @abstractmethod
    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific video"""
        pass

    @abstractmethod
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from platform URL"""
        pass

    @abstractmethod
    def is_platform_url(self, url: str) -> bool:
        """Check if URL belongs to this platform"""
        pass

    @abstractmethod
    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get the stream URL for a video"""
        pass

    async def initialize(self):
        """Initialize platform resources with network routing"""
        try:
            # Initialize network-aware HTTP client
            self._network_client = get_http_client()
            await self._network_client.initialize()
            
            logger.info(f"Initialized {self.name} platform with network routing")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self.name} platform: {e}")
            raise

    async def cleanup(self):
        """Cleanup platform resources"""
        # The global HTTP client will be cleaned up by the bot
        logger.info(f"Cleaned up {self.name} platform")

    async def _make_http_request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make HTTP request using network routing"""
        if not self._network_client:
            raise RuntimeError(f"Platform {self.name} not initialized")
        
        async with self._network_client.get_session(self._service_type) as session:
            async with session.request(method, url, **kwargs) as response:
                return response

    async def _get_json(self, url: str, **kwargs) -> Dict[str, Any]:
        """Get JSON response from URL using network routing"""
        response = await self._make_http_request('GET', url, **kwargs)
        response.raise_for_status()
        return await response.json()

    async def _get_text(self, url: str, **kwargs) -> str:
        """Get text response from URL using network routing"""
        response = await self._make_http_request('GET', url, **kwargs)
        response.raise_for_status()
        return await response.text()

    # Cache-aware helper methods (unchanged from original)
    async def get_cached_search_results(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results if available"""
        if self.cache_manager:
            try:
                return await self.cache_manager.get_search_results(self.name, query)
            except Exception as e:
                logger.debug(f"Error getting cached search results for {self.name}: {e}")
        return None

    async def cache_search_results(self, query: str, results: List[Dict[str, Any]], ttl: Optional[int] = None):
        """Cache search results"""
        if self.cache_manager and results:
            try:
                await self.cache_manager.set_search_results(self.name, query, results, ttl)
                logger.debug(f"Cached {len(results)} search results for {self.name}")
            except Exception as e:
                logger.debug(f"Error caching search results for {self.name}: {e}")

    async def get_cached_video_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get cached video metadata if available"""
        if self.cache_manager:
            try:
                return await self.cache_manager.get_video_metadata(self.name, video_id)
            except Exception as e:
                logger.debug(f"Error getting cached video metadata for {self.name}: {e}")
        return None

    async def cache_video_metadata(self, video_id: str, metadata: Dict[str, Any], ttl: Optional[int] = None):
        """Cache video metadata"""
        if self.cache_manager and metadata:
            try:
                await self.cache_manager.set_video_metadata(self.name, video_id, metadata, ttl)
                logger.debug(f"Cached video metadata for {self.name}: {video_id}")
            except Exception as e:
                logger.debug(f"Error caching video metadata for {self.name}: {e}")


class YouTubePlatformWithRouting(VideoPlatformWithRouting):
    """Example YouTube platform implementation with network routing"""

    async def search_videos(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for videos using YouTube API with network routing"""
        # Check cache first
        cached_results = await self.get_cached_search_results(query)
        if cached_results:
            logger.debug(f"Using cached search results for: {query}")
            return cached_results

        try:
            # Make API request using network routing
            api_key = self.config.get('api_key')
            if not api_key:
                raise ValueError("YouTube API key not configured")

            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': max_results,
                'key': api_key
            }

            data = await self._get_json(url, params=params)
            
            # Process results
            results = []
            for item in data.get('items', []):
                video_data = {
                    'id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'thumbnail': item['snippet']['thumbnails']['default']['url'],
                    'channel': item['snippet']['channelTitle'],
                    'published': item['snippet']['publishedAt']
                }
                results.append(video_data)

            # Cache results
            await self.cache_search_results(query, results)
            
            logger.info(f"Found {len(results)} videos for query: {query}")
            return results

        except Exception as e:
            logger.error(f"YouTube search failed for query '{query}': {e}")
            return []

    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video details using YouTube API with network routing"""
        # Check cache first
        cached_details = await self.get_cached_video_metadata(video_id)
        if cached_details:
            logger.debug(f"Using cached video details for: {video_id}")
            return cached_details

        try:
            api_key = self.config.get('api_key')
            if not api_key:
                raise ValueError("YouTube API key not configured")

            url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                'part': 'snippet,contentDetails,statistics',
                'id': video_id,
                'key': api_key
            }

            data = await self._get_json(url, params=params)
            
            if not data.get('items'):
                return None

            item = data['items'][0]
            details = {
                'id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'duration': item['contentDetails']['duration'],
                'views': item['statistics'].get('viewCount', 0),
                'likes': item['statistics'].get('likeCount', 0),
                'channel': item['snippet']['channelTitle'],
                'published': item['snippet']['publishedAt']
            }

            # Cache details
            await self.cache_video_metadata(video_id, details)
            
            return details

        except Exception as e:
            logger.error(f"Failed to get video details for {video_id}: {e}")
            return None

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        import re
        
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None

    def is_platform_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL"""
        return any(domain in url.lower() for domain in ['youtube.com', 'youtu.be'])

    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL for video (would use yt-dlp in real implementation)"""
        # This would typically use yt-dlp with network routing
        logger.info(f"Getting stream URL for video: {video_id}")
        # Implementation would go here
        return f"https://youtube.com/watch?v={video_id}"