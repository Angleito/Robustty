import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import aiohttp

from src.platforms.base import VideoPlatform

logger = logging.getLogger(__name__)


class OdyseePlatform(VideoPlatform):
    """Odysee/LBRY platform implementation"""

    def __init__(self, name: str, config: Dict[str, Any]) -> None:
        super().__init__(name, config)
        self.api_url = config.get("api_url", "https://api.lbry.tv/api/v1")
        self.stream_url = config.get("stream_url", "https://api.lbry.tv")
        
        # URL patterns for Odysee videos
        self.url_patterns = [
            re.compile(r"https?://odysee\.com/@[^/]+:[a-f0-9]+/[^/]+:[a-f0-9]+"),
            re.compile(r"https?://lbry\.tv/@[^/]+:[a-f0-9]+/[^/]+:[a-f0-9]+"),
            re.compile(r"lbry://(@[^/]+/[^/]+)"),
        ]

    async def search_videos(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for videos on Odysee"""
        if not self.session:
            logger.error("Session not initialized")
            return []
        
        try:
            # Use claim_search endpoint
            url = f"{self.api_url}/claim_search"
            params = {
                "text": query,
                "page": 1,
                "page_size": max_results,
                "claim_type": ["stream"],
                "stream_types": ["video"],
                "order_by": ["trending_group", "trending_mixed"],
                "no_totals": True,
            }

            async with self.session.post(url, json=params) as response:
                if response.status != 200:
                    logger.error(f"Odysee search failed: {response.status}")
                    return []

                data = await response.json()
                results = []
                
                for item in data.get("items", []):
                    if item.get("value_type") != "stream":
                        continue
                        
                    value = item.get("value", {})
                    if value.get("stream_type") != "video":
                        continue
                    
                    # Extract video information
                    video_data = {
                        "id": item.get("claim_id"),
                        "title": value.get("title", item.get("name", "Unknown Title")),
                        "channel": item.get("signing_channel", {}).get("name", "Unknown Channel"),
                        "thumbnail": value.get("thumbnail", {}).get("url", ""),
                        "url": f"https://odysee.com/{item.get('canonical_url', '')}",
                        "platform": "odysee",
                        "description": value.get("description", ""),
                        "duration": value.get("video", {}).get("duration"),
                        "views": item.get("meta", {}).get("effective_amount", 0),
                    }
                    results.append(video_data)

                return results

        except Exception as e:
            logger.error(f"Error searching Odysee: {e}")
            return []

    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific video"""
        if not self.session:
            logger.error("Session not initialized")
            return None
            
        try:
            url = f"{self.api_url}/claim_search"
            params = {
                "claim_id": video_id,
                "page": 1,
                "page_size": 1,
            }

            async with self.session.post(url, json=params) as response:
                if response.status != 200:
                    logger.error(f"Odysee get details failed: {response.status}")
                    return None

                data = await response.json()
                items = data.get("items", [])
                
                if not items:
                    return None
                
                item = items[0]
                value = item.get("value", {})
                
                return {
                    "id": item.get("claim_id"),
                    "title": value.get("title", item.get("name", "Unknown Title")),
                    "channel": item.get("signing_channel", {}).get("name", "Unknown Channel"),
                    "thumbnail": value.get("thumbnail", {}).get("url", ""),
                    "url": f"https://odysee.com/{item.get('canonical_url', '')}",
                    "platform": "odysee",
                    "description": value.get("description", ""),
                    "duration": value.get("video", {}).get("duration"),
                    "views": item.get("meta", {}).get("effective_amount", 0),
                }

        except Exception as e:
            logger.error(f"Error getting Odysee video details: {e}")
            return None

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract claim ID from Odysee URL"""
        # Example URL: https://odysee.com/@Channel:6/video-title:2
        # The claim ID is the hex after the last colon
        
        pattern = re.compile(r"[:/]([a-f0-9]+)$")
        match = pattern.search(url)
        
        if match:
            return match.group(1)
            
        # Try to extract from canonical URL format
        pattern = re.compile(r"@[^/]+:([a-f0-9]+)/[^/]+:([a-f0-9]+)")
        match = pattern.search(url)
        
        if match:
            return match.group(2)  # Return the video claim ID, not channel
            
        return None

    def is_platform_url(self, url: str) -> bool:
        """Check if URL belongs to Odysee/LBRY"""
        return any(
            pattern.match(url) for pattern in self.url_patterns
        ) or any(domain in url for domain in ["odysee.com", "lbry.tv"])

    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get the stream URL for a video"""
        if not self.session:
            logger.error("Session not initialized")
            return None
            
        try:
            # First, get the claim details to get the SD hash
            video_details = await self.get_video_details(video_id)
            if not video_details:
                return None
            
            # Construct stream URL
            # Odysee uses a specific format for streaming
            stream_url = f"{self.stream_url}/content/claims/{video_id}/stream"
            
            # Verify the stream URL is accessible
            async with self.session.head(stream_url) as response:
                if response.status == 200:
                    return stream_url
                else:
                    logger.error(f"Stream URL not accessible: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error getting Odysee stream URL: {e}")
            return None

    async def initialize(self):
        """Initialize platform resources"""
        await super().initialize()
        logger.info(f"Initialized Odysee platform with API URL: {self.api_url}")

    async def cleanup(self):
        """Cleanup platform resources"""
        if self.session:
            await self.session.close()
        logger.info("Cleaned up Odysee platform")