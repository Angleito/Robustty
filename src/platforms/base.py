from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import aiohttp
import logging

logger = logging.getLogger(__name__)

class VideoPlatform(ABC):
    """Abstract base class for all video platforms"""
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.enabled = config.get('enabled', True)
    
    @abstractmethod
    async def search_videos(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search for videos on the platform"""
        pass
    
    @abstractmethod
    async def get_video_details(self, video_id: str) -> Optional[Dict]:
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
    
    def __str__(self):
        return f"{self.name} ({'enabled' if self.enabled else 'disabled'})"