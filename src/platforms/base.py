import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from ..services.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class VideoPlatform(ABC):
    """Abstract base class for all video platforms"""

    def __init__(self, name: str, config: Dict[str, Any], cache_manager: Optional['CacheManager'] = None):
        self.name = name
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.enabled = config.get("enabled", True)
        self.cache_manager = cache_manager

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
        """Initialize platform resources"""
        self.session = aiohttp.ClientSession()
        logger.info(f"Initialized {self.name} platform")

    async def cleanup(self):
        """Cleanup platform resources"""
        if self.session:
            await self.session.close()
        logger.info(f"Cleaned up {self.name} platform")

    # Cache-aware helper methods
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
                logger.debug(f"Cached video metadata for {self.name}:{video_id}")
            except Exception as e:
                logger.debug(f"Error caching video metadata for {self.name}: {e}")

    async def get_cached_stream_url(self, video_id: str, quality: Optional[str] = None) -> Optional[str]:
        """Get cached stream URL if available"""
        if self.cache_manager:
            try:
                return await self.cache_manager.get_stream_url(self.name, video_id, quality)
            except Exception as e:
                logger.debug(f"Error getting cached stream URL for {self.name}: {e}")
        return None

    async def cache_stream_url(self, video_id: str, stream_url: str, quality: Optional[str] = None, ttl: Optional[int] = None):
        """Cache stream URL"""
        if self.cache_manager and stream_url:
            try:
                await self.cache_manager.set_stream_url(self.name, video_id, stream_url, quality, ttl)
                logger.debug(f"Cached stream URL for {self.name}:{video_id}")
            except Exception as e:
                logger.debug(f"Error caching stream URL for {self.name}: {e}")

    def __str__(self):
        return f"{self.name} ({'enabled' if self.enabled else 'disabled'})"
