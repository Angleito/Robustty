"""Rumble platform implementation for Robustty.

This module implements Rumble video platform support using the Apify API
for video search and extraction functionality.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .base import VideoPlatform
from .errors import (
    PlatformError,
    PlatformNotAvailableError,
    PlatformAPIError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
    from_http_status
)
from ..extractors.rumble_extractor import RumbleExtractor
from ..services.metrics_collector import get_metrics_collector

logger = logging.getLogger(__name__)


class RumblePlatform(VideoPlatform):
    """Rumble platform implementation"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.api_token: Optional[str] = config.get("api_token")
        
        # URL patterns for Rumble
        self.url_patterns = [
            re.compile(
                r"rumble\.com/(v[A-Za-z0-9]+)(?:-[^/?]*)?"
            ),
            re.compile(
                r"rumble\.com/embed/(v[A-Za-z0-9]+)(?:[/?].*)?$"
            ),
        ]
        
        # Initialize the Rumble extractor
        self.extractor: Optional[RumbleExtractor] = None
        
        # Initialize metrics collector
        self.metrics = get_metrics_collector()

    async def initialize(self):
        """Initialize Rumble API client"""
        await super().initialize()
        
        if self.api_token:
            self.extractor = RumbleExtractor(apify_api_token=self.api_token)
            logger.info("Rumble API token provided, extractor initialized")
        else:
            logger.warning("Rumble API token not provided, searches will fail")

    async def search_videos(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search Rumble videos using Apify API"""
        if not self.api_token or not self.extractor:
            logger.error("Rumble API token not configured")
            raise PlatformAuthenticationError(
                "API token is required for Rumble searches. Please configure 'api_token' in config.",
                platform="Rumble"
            )
        
        try:
            logger.info(f"Searching Rumble for: {query}")
            
            # Use metrics timer context manager
            with self.metrics.api_call_timer("search"):
                # Call the extractor's search method
                search_results = await self.extractor.search_videos(query, max_results)
            
            # Convert the results to our expected format
            results: List[Dict[str, Any]] = []
            for video in search_results:
                results.append({
                    "id": video.get("id", ""),
                    "title": video.get("title", ""),
                    "channel": video.get("uploader", ""),
                    "thumbnail": video.get("thumbnail_url", ""),
                    "url": video.get("url", ""),
                    "platform": "rumble",
                    "description": video.get("description", ""),
                    "duration": video.get("duration", 0),
                    "views": video.get("view_count", 0),
                })
            
            return results
            
        except PlatformError:
            # Re-raise platform errors as-is
            raise
        except PlatformRateLimitError as e:
            self.metrics.record_rate_limit()
            raise
        except Exception as e:
            logger.error(f"Rumble search error: {e}")
            
            # Try to handle specific error types
            if isinstance(e, PlatformAuthenticationError):
                raise e
            else:
                # Wrap non-platform errors
                raise PlatformAPIError(
                    f"Search failed: {str(e)}",
                    platform="Rumble",
                    original_error=e
                )

    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a Rumble video"""
        if not self.api_token or not self.extractor:
            logger.error("Rumble API token not configured")
            raise PlatformAuthenticationError(
                "API token is required for video details. Please configure 'api_token' in config.",
                platform="Rumble"
            )
        
        try:
            logger.info(f"Getting details for Rumble video: {video_id}")
            
            # Construct the video URL from the ID
            video_url = f"https://rumble.com/{video_id}"
            
            # Use metrics timer context manager
            with self.metrics.api_call_timer("metadata"):
                # Call the extractor's metadata method
                metadata = await self.extractor.get_video_metadata(video_url)
            
            # Convert the metadata to our expected format
            return {
                "id": video_id,
                "title": metadata.get("title", ""),
                "channel": metadata.get("uploader", ""),
                "thumbnail": metadata.get("thumbnail_url", ""),
                "url": video_url,
                "platform": "rumble",
                "description": metadata.get("description", ""),
                "duration": metadata.get("duration", 0),
                "views": metadata.get("view_count", 0),
                "likes": metadata.get("like_count", 0),
                "uploaded_date": metadata.get("publish_date", ""),
            }
            
        except PlatformError:
            # Re-raise platform errors as-is
            raise
        except PlatformRateLimitError as e:
            self.metrics.record_rate_limit()
            raise
        except Exception as e:
            logger.error(f"Rumble video details error: {e}")
            
            # Try to handle specific error types
            if isinstance(e, PlatformNotAvailableError):
                raise e
            elif isinstance(e, PlatformAuthenticationError):
                raise e
            else:
                # Wrap non-platform errors
                raise PlatformAPIError(
                    f"Failed to get video details: {str(e)}",
                    platform="Rumble",
                    original_error=e
                )

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from Rumble URL"""
        for pattern in self.url_patterns:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    def is_platform_url(self, url: str) -> bool:
        """Check if URL is a Rumble URL"""
        return any(pattern.search(url) for pattern in self.url_patterns)

    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL for a Rumble video"""
        # This is handled by the stream service which uses the same rumble extractor
        return f"http://robustty-stream:5000/stream/rumble/{video_id}"