import logging
import re
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

from .base import VideoPlatform
from .errors import (
    PlatformNotAvailableError,
    PlatformAPIError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
    from_http_status
)

logger = logging.getLogger(__name__)


class YouTubePlatform(VideoPlatform):
    """YouTube platform implementation"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.api_key: Optional[str] = config.get("api_key")
        self.youtube: Optional[Any] = None

        # URL patterns for YouTube
        self.url_patterns = [
            re.compile(
                r"(?:https?:\/\/)?(?:www\.)?" r"youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)"
            ),
            re.compile(r"(?:https?:\/\/)?(?:www\.)?" r"youtu\.be\/([a-zA-Z0-9_-]+)"),
            re.compile(
                r"(?:https?:\/\/)?(?:www\.)?" r"youtube\.com\/embed\/([a-zA-Z0-9_-]+)"
            ),
        ]

    async def initialize(self):
        """Initialize YouTube API client"""
        await super().initialize()
        if self.api_key:
            self.youtube = build("youtube", "v3", developerKey=self.api_key)
        else:
            logger.warning("YouTube API key not provided")

    async def search_videos(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search YouTube videos"""
        if not self.youtube:
            raise PlatformAuthenticationError(
                "YouTube API key is required for search. Please configure 'api_key' in config.",
                platform="YouTube"
            )

        try:
            request = self.youtube.search().list(
                part="snippet", q=query, type="video", maxResults=max_results
            )
            response = request.execute()

            results: List[Dict[str, Any]] = []
            for item in response.get("items", []):
                # Handle different response structures
                if "id" in item and isinstance(item["id"], dict):
                    video_id = item["id"].get("videoId")
                elif "id" in item and isinstance(item["id"], str):
                    video_id = item["id"]
                else:
                    continue
                    
                if not video_id:
                    continue
                    
                snippet = item.get("snippet", {})

                logger.info(f"YouTube search result: video_id={video_id}, title={snippet.get('title', 'Unknown')}")
                results.append(
                    {
                        "id": video_id,
                        "title": snippet.get("title", "Unknown"),
                        "channel": snippet.get("channelTitle", "Unknown"),
                        "thumbnail": (
                            snippet.get("thumbnails", {})
                            .get("high", {})
                            .get("url", snippet.get("thumbnails", {}).get("default", {}).get("url", ""))
                        ),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "platform": "youtube",
                        "description": snippet.get("description", ""),
                    }
                )

            return results
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            
            # Check for quota exceeded
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                raise PlatformRateLimitError(
                    "YouTube API quota exceeded",
                    platform="YouTube",
                    original_error=e
                )
            
            # Use from_http_status for other HTTP errors
            raise from_http_status(
                e.resp.status,
                "YouTube",
                str(e)
            )
        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            raise PlatformAPIError(
                f"Search failed: {str(e)}",
                platform="YouTube",
                original_error=e
            )

    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a video"""
        if not self.youtube:
            return None

        try:
            request = self.youtube.videos().list(
                part="snippet,contentDetails,statistics", id=video_id
            )
            response = request.execute()

            if not response.get("items"):
                return None

            item = response["items"][0]
            snippet = item["snippet"]

            return {
                "id": video_id,
                "title": snippet["title"],
                "channel": snippet["channelTitle"],
                "thumbnail": snippet["thumbnails"]["high"]["url"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "platform": "youtube",
                "description": snippet.get("description", ""),
                "duration": item["contentDetails"]["duration"],
                "views": item["statistics"].get("viewCount", 0),
            }
        except Exception as e:
            logger.error(f"YouTube video details error: {e}")
            return None

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        for pattern in self.url_patterns:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    def is_platform_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL"""
        return any(pattern.search(url) for pattern in self.url_patterns)

    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL (delegated to stream service)"""
        # This will be handled by the yt-dlp stream service
        return f"http://robustty-stream:5000/stream/youtube/{video_id}"
