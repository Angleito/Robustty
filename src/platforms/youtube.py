import logging
import re
from pathlib import Path
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

    def _convert_cookies_to_netscape(self, json_cookie_file: str, netscape_cookie_file: str) -> bool:
        """Convert JSON cookies to Netscape format for yt-dlp with enhanced error handling"""
        try:
            import json
            
            if not Path(json_cookie_file).exists():
                logger.warning(f"JSON cookie file not found: {json_cookie_file}")
                return False
            
            # Validate file is readable and not empty
            try:
                file_size = Path(json_cookie_file).stat().st_size
                if file_size == 0:
                    logger.warning(f"Cookie file is empty: {json_cookie_file}")
                    return False
            except Exception as e:
                logger.error(f"Cannot access cookie file {json_cookie_file}: {e}")
                return False
            
            # Read and parse JSON cookies
            try:
                with open(json_cookie_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        logger.warning(f"Cookie file content is empty: {json_cookie_file}")
                        return False
                    cookies = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in cookie file {json_cookie_file}: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to read cookie file {json_cookie_file}: {e}")
                return False
            
            if not cookies or not isinstance(cookies, list):
                logger.warning(f"No valid cookies found in {json_cookie_file} (found: {type(cookies)})")
                return False
            
            # Ensure output directory exists
            try:
                Path(netscape_cookie_file).parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Cannot create cookie output directory: {e}")
                return False
            
            # Convert to Netscape format
            try:
                with open(netscape_cookie_file, 'w', encoding='utf-8') as f:
                    # Write Netscape cookie file header
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# This is a generated file! Do not edit.\n\n")
                    
                    valid_cookies = 0
                    for cookie in cookies:
                        # Skip invalid cookie entries
                        if not isinstance(cookie, dict):
                            continue
                        
                        name = cookie.get('name', '').strip()
                        value = cookie.get('value', '')
                        
                        # Skip cookies without name (value can be empty)
                        if not name:
                            continue
                        
                        # Skip cookies with problematic characters
                        if '\t' in name or '\t' in value or '\n' in name or '\n' in value:
                            logger.debug(f"Skipping cookie with invalid characters: {name}")
                            continue
                        
                        # Netscape format: domain, domain_specified, path, secure, expires, name, value
                        domain = cookie.get('domain', '.youtube.com')
                        if not domain:
                            domain = '.youtube.com'
                        
                        domain_specified = 'TRUE' if domain.startswith('.') else 'FALSE'
                        path = cookie.get('path', '/')
                        secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                        
                        # Handle expires field - convert to Unix timestamp if needed
                        expires = cookie.get('expires', 0)
                        if expires is None:
                            expires = 0
                        elif isinstance(expires, (int, float)):
                            expires = int(expires)
                        else:
                            expires = 0
                        
                        # Write cookie line in Netscape format
                        cookie_line = f"{domain}\t{domain_specified}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"
                        f.write(cookie_line)
                        valid_cookies += 1
                
                if valid_cookies > 0:
                    logger.info(f"Successfully converted {valid_cookies} cookies to Netscape format")
                    return True
                else:
                    logger.warning("No valid cookies were converted")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to write Netscape cookie file {netscape_cookie_file}: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Unexpected error during cookie conversion: {e}")
            import traceback
            logger.debug(f"Cookie conversion traceback: {traceback.format_exc()}")
            return False

    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL using yt-dlp with cookies"""
        import yt_dlp
        import asyncio
        
        logger.info(f"Getting stream URL for YouTube video: {video_id}")
        
        try:
            # Use yt-dlp to get stream URL
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Configure yt-dlp options optimized for Discord audio
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio',
                'quiet': True,
                'no_warnings': False,  # Enable warnings for debugging
                'noplaylist': True,
                'extract_flat': False,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'http_chunk_size': 10485760,  # 10MB chunks
                'prefer_insecure': False,
                'verbose': False
            }
            
            # Standardized cookie path
            cookie_paths = [
                '/app/cookies/youtube_cookies.json'
            ]
            
            cookies_loaded = False
            for json_cookie_file in cookie_paths:
                if Path(json_cookie_file).exists():
                    netscape_cookie_file = str(Path(json_cookie_file).parent / 'youtube_cookies.txt')
                    
                    try:
                        if self._convert_cookies_to_netscape(json_cookie_file, netscape_cookie_file):
                            ydl_opts['cookiefile'] = netscape_cookie_file
                            logger.info(f"Using converted YouTube cookies from {json_cookie_file}")
                            cookies_loaded = True
                            break
                        else:
                            logger.warning(f"Failed to convert cookies from {json_cookie_file}")
                    except Exception as cookie_error:
                        logger.error(f"Cookie conversion error for {json_cookie_file}: {cookie_error}")
                        continue
            
            if not cookies_loaded:
                logger.info("No valid YouTube cookies found, proceeding without authentication")
            
            def extract_info():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        
                        if not info:
                            logger.error("yt-dlp returned no information")
                            return None
                        
                        # Extract URL from different possible structures
                        stream_url = None
                        
                        if 'url' in info:
                            stream_url = info['url']
                        elif 'formats' in info and info['formats']:
                            # Find best audio format
                            formats = info['formats']
                            
                            # Prefer audio-only formats
                            audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('url')]
                            if audio_formats:
                                # Sort by audio quality
                                audio_formats.sort(key=lambda f: f.get('abr', 0) or f.get('tbr', 0), reverse=True)
                                stream_url = audio_formats[0]['url']
                            else:
                                # Fallback to best available format
                                valid_formats = [f for f in formats if f.get('url')]
                                if valid_formats:
                                    stream_url = valid_formats[-1]['url']
                        elif 'entries' in info and info['entries']:
                            # Handle playlist case (should not happen with noplaylist=True)
                            first_entry = info['entries'][0]
                            if first_entry and 'url' in first_entry:
                                stream_url = first_entry['url']
                        
                        if not stream_url:
                            logger.error("No valid stream URL found in extraction result")
                            return None
                        
                        logger.debug(f"Extracted stream URL: {stream_url[:100]}...")
                        return stream_url
                        
                except yt_dlp.DownloadError as e:
                    logger.error(f"yt-dlp download error: {e}")
                    return None
                except Exception as e:
                    logger.error(f"yt-dlp extraction error: {e}")
                    return None
            
            # Run yt-dlp in thread to avoid blocking
            loop = asyncio.get_event_loop()
            stream_url = await loop.run_in_executor(None, extract_info)
            
            # Return stream URL if extracted (validation was too strict)
            if stream_url:
                logger.info(f"Successfully extracted stream URL: {stream_url[:100]}...")
                return stream_url
            else:
                logger.error(f"No stream URL extracted for video {video_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get stream URL for {video_id}: {e}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return None
    
    def _validate_stream_url(self, url: str) -> bool:
        """Validate that the stream URL is accessible (sync version)"""
        try:
            import requests
            
            # Quick HEAD request to check if URL is accessible
            response = requests.head(url, timeout=5, allow_redirects=True)
            is_valid = response.status_code < 400
            
            if not is_valid:
                logger.warning(f"Stream URL validation failed with status {response.status_code}")
            
            return is_valid
            
        except Exception as e:
            logger.warning(f"Stream URL validation error: {e}")
            # Return True on validation error to avoid blocking valid URLs
            return True
    
    async def _validate_stream_url_async(self, url: str) -> bool:
        """Validate that the stream URL is accessible (async version)"""
        try:
            import aiohttp
            import asyncio
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.head(url, allow_redirects=True) as response:
                        is_valid = response.status < 400
                        
                        if not is_valid:
                            logger.warning(f"Stream URL validation failed with status {response.status}")
                        
                        return is_valid
                except asyncio.TimeoutError:
                    logger.warning("Stream URL validation timed out")
                    return True  # Assume valid on timeout
                    
        except ImportError:
            # Fallback to sync validation if aiohttp not available
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._validate_stream_url, url)
        except Exception as e:
            logger.warning(f"Stream URL validation error: {e}")
            # Return True on validation error to avoid blocking valid URLs
            return True
