import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from googleapiclient.discovery import build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

from .base import VideoPlatform
from .errors import (
    PlatformAPIError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
    from_http_status,
)
from ..utils.network_resilience import (
    with_retry,
    PLATFORM_RETRY_CONFIG,
    PLATFORM_CIRCUIT_BREAKER_CONFIG,
    NetworkResilienceError,
    CircuitBreakerOpenError,
)
from ..services.status_reporting import (
    SearchMethod,
    PlatformStatus,
    report_api_quota_exceeded,
    report_fallback_success,
    report_direct_url_success,
    report_search_success,
    report_no_api_key,
    report_platform_error,
)

logger = logging.getLogger(__name__)


class YouTubePlatform(VideoPlatform):
    """YouTube platform implementation"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.api_key: Optional[str] = config.get("api_key")
        self.youtube: Optional[Any] = None

        # Fallback configuration
        self.fallback_manager = None  # Will be set by bot initialization
        self.cookie_health_monitor = None  # Will be set by bot initialization
        self.enable_fallbacks = config.get("enable_fallbacks", True)

        # Language configuration options - defaults to English for search results
        self.default_region: str = config.get("default_region", "US")
        self.default_language: str = config.get("default_language", "en")
        self.interface_language: str = config.get("interface_language", "en")
        self.auto_detect_language: bool = config.get("auto_detect_language", False)  # Changed default to False for English preference
        self.force_english_for_english_queries: bool = config.get("force_english_for_english_queries", True)
        self.prefer_english_results: bool = config.get("prefer_english_results", True)  # New option to prefer English by default

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
        """Initialize YouTube API client with fallback awareness"""
        await super().initialize()
        if self.api_key:
            self.youtube = build("youtube", "v3", developerKey=self.api_key)
            logger.info("YouTube API client initialized successfully")
        else:
            logger.warning("YouTube API key not provided - will rely on fallback modes")
            if self.fallback_manager and self.enable_fallbacks:
                self.fallback_manager.activate_fallback(
                    "youtube", "No API key provided"
                )

    def set_fallback_manager(self, fallback_manager):
        """Set the fallback manager for this platform"""
        self.fallback_manager = fallback_manager

    def set_cookie_health_monitor(self, cookie_health_monitor):
        """Set the cookie health monitor for this platform"""
        self.cookie_health_monitor = cookie_health_monitor

    def _get_search_params(self, query: str) -> Dict[str, str]:
        """Get search parameters including language and region settings with English defaults"""
        detected_language = self._detect_query_language(query)
        
        # Apply language preferences - prefer English by default
        if not self.auto_detect_language or self.prefer_english_results:
            # Use English as default unless auto-detection explicitly overrides
            if detected_language == "auto" and not self.prefer_english_results:
                relevance_language = None  # Let YouTube auto-detect
            else:
                relevance_language = "en" if self.prefer_english_results or detected_language == "en" else self.default_language
        else:
            relevance_language = detected_language if detected_language != "auto" else None
        
        params = {
            "regionCode": self.default_region,
            "hl": self.interface_language,  # Always set interface language for English UI
        }
        
        # Add relevance language if determined
        if relevance_language:
            params["relevanceLanguage"] = relevance_language
        
        logger.debug(f"Search params for query '{query[:50]}...': region={params['regionCode']}, "
                    f"language={params['relevanceLanguage']}, hl={params.get('hl', 'not set')}")
        
        return params

    def _detect_query_language(self, query: str) -> str:
        """Detect if the search query is in English or another language
        
        Returns:
            'en' for English queries, 'auto' for non-English queries
        """
        if not query or not query.strip():
            return 'en' if self.prefer_english_results else 'auto'
        
        # If prefer_english_results is True and auto_detect_language is False, always return English
        if self.prefer_english_results and not self.auto_detect_language:
            logger.debug(f"Using English language preference for query: {query}")
            return 'en'
        
        query_lower = query.lower().strip()
        
        # Check for primarily ASCII characters (strong indicator of English)
        ascii_chars = sum(1 for c in query if ord(c) < 128)
        total_chars = len(query)
        ascii_ratio = ascii_chars / total_chars if total_chars > 0 else 0
        
        # If less than 80% ASCII, likely non-English
        if ascii_ratio < 0.8:
            logger.debug(f"Query '{query}' detected as non-English (ASCII ratio: {ascii_ratio:.2f})")
            return 'auto'
        
        # Common English words and patterns
        english_indicators = {
            # Common English words
            'the', 'and', 'or', 'of', 'to', 'in', 'for', 'with', 'on', 'at', 'by', 'from',
            'how', 'what', 'when', 'where', 'why', 'who', 'which', 'that', 'this', 'these',
            'song', 'music', 'video', 'tutorial', 'review', 'news', 'live', 'official',
            'cover', 'remix', 'acoustic', 'piano', 'guitar', 'drum', 'bass', 'vocal',
            'best', 'top', 'new', 'old', 'latest', 'first', 'last', 'full', 'complete',
            'funny', 'amazing', 'epic', 'awesome', 'cool', 'great', 'good', 'bad',
            # Common music/entertainment terms
            'album', 'single', 'ep', 'mixtape', 'playlist', 'concert', 'performance',
            'interview', 'behind', 'scenes', 'making', 'reaction', 'analysis',
            # Music genres and common terms
            'rock', 'pop', 'jazz', 'blues', 'country', 'rap', 'hip', 'hop', 'metal', 'punk',
            'folk', 'classical', 'electronic', 'dance', 'house', 'techno', 'dubstep',
            'band', 'artist', 'singer', 'musician', 'group', 'duo', 'trio', 'orchestra',
            # Common abbreviations and brand names in English context
            'bts', 'kpop', 'jpop', 'cpop', 'mv', 'ost', 'bgm', 'dj', 'mc', 'ft', 'feat'
        }
        
        # Split query into words and check for English indicators
        words = query_lower.replace('-', ' ').replace('_', ' ').split()
        english_word_count = 0
        
        for word in words:
            # Remove common punctuation
            clean_word = word.strip('.,!?;:"()[]{}')
            if clean_word in english_indicators:
                english_word_count += 1
        
        # If we have English words, check the ratio
        if len(words) > 0:
            english_ratio = english_word_count / len(words)
            
            # If 30% or more words are common English words, consider it English
            if english_ratio >= 0.3:
                logger.debug(f"Query '{query}' detected as English (English word ratio: {english_ratio:.2f})")
                return 'en'
                
            # If prefer_english_results is True, lean towards English even with lower ratio
            if self.prefer_english_results and english_ratio >= 0.1:
                logger.debug(f"Query '{query}' using English preference (English word ratio: {english_ratio:.2f})")
                return 'en'
        
        # Check for English patterns
        english_patterns = [
            r'\bhow\s+to\b',  # "how to"
            r'\bwhat\s+is\b',  # "what is"
            r'\b\w+ing\b',    # words ending in -ing
            r'\b\w+ed\b',     # words ending in -ed
            r'\b\w+ly\b',     # words ending in -ly
            r'\b\w+\'s\b',    # possessives
            r'\b\w+n\'t\b',   # contractions like don't, can't
        ]
        
        import re
        for pattern in english_patterns:
            if re.search(pattern, query_lower):
                logger.debug(f"Query '{query}' detected as English (pattern match: {pattern})")
                return 'en'
        
        # Default based on configuration
        if self.prefer_english_results:
            logger.debug(f"Query '{query}' defaulting to English preference")
            return 'en'
        else:
            logger.debug(f"Query '{query}' language detection inconclusive, using 'auto'")
            return 'auto'

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="youtube_search",
        exceptions=(HttpError, PlatformAPIError, PlatformRateLimitError),
        exclude_exceptions=(PlatformAuthenticationError, CircuitBreakerOpenError),
    )
    async def search_videos(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search YouTube videos with enhanced error handling and detailed metadata"""
        # First try URL parsing if query contains a YouTube URL
        url_results = await self._search_via_url_parsing(query)
        if url_results:
            logger.info("Successfully found YouTube URL in query and extracted metadata")
            report_direct_url_success(
                "YouTube",
                f"Processed direct YouTube URL successfully",
                details={'results_count': len(url_results)}
            )
            return url_results
        
        # If no API key, try yt-dlp fallback search
        if not self.youtube:
            logger.warning("No YouTube API key available, attempting yt-dlp fallback search")
            report_no_api_key(
                "YouTube",
                "No API key configured - attempting yt-dlp fallback search"
            )
            fallback_results = await self._search_with_ytdlp(query, max_results)
            if fallback_results:
                logger.info(f"yt-dlp fallback search successful without API, returning {len(fallback_results)} results")
                report_fallback_success(
                    "YouTube", 
                    SearchMethod.YTDLP_SEARCH,
                    f"yt-dlp fallback search successful",
                    details={'results_count': len(fallback_results)}
                )
                return fallback_results
            else:
                report_platform_error(
                    "YouTube",
                    SearchMethod.YTDLP_SEARCH,
                    "yt-dlp fallback search failed",
                    "No API key and fallback search failed. Please configure API key or use direct URLs."
                )
                raise PlatformAuthenticationError(
                    "YouTube API key is required for reliable text search. yt-dlp fallback also failed. Please configure 'api_key' in config, or provide a direct YouTube URL.",
                    platform="YouTube",
                )

        try:
            # Build search parameters with language configuration
            search_params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results
            }
            
            # Add language and region parameters based on configuration
            language_params = self._get_search_params(query)
            search_params.update(language_params)
            
            # First, get search results
            search_request = self.youtube.search().list(**search_params)
            search_response = search_request.execute()

            # Extract video IDs for detailed lookup
            video_ids = []
            for item in search_response.get("items", []):
                if "id" in item and isinstance(item["id"], dict):
                    video_id = item["id"].get("videoId")
                elif "id" in item and isinstance(item["id"], str):
                    video_id = item["id"]
                else:
                    continue

                if video_id:
                    video_ids.append(video_id)

            if not video_ids:
                return []

            # Get detailed video information including duration, view count, etc.
            videos_request = self.youtube.videos().list(
                part="snippet,contentDetails,statistics", id=",".join(video_ids)
            )
            videos_response = videos_request.execute()

            results: List[Dict[str, Any]] = []
            for item in videos_response.get("items", []):
                video_id = item.get("id")
                if not video_id:
                    continue

                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                statistics = item.get("statistics", {})

                # Parse duration from ISO 8601 format (PT4M13S -> 4:13)
                duration = self._parse_duration(content_details.get("duration", ""))

                # Format view count
                view_count = statistics.get("viewCount", "0")
                view_count_formatted = self._format_view_count(view_count)

                # Get best thumbnail
                thumbnail_url = self._get_best_thumbnail(snippet.get("thumbnails", {}))

                # Format publish date
                published_at = snippet.get("publishedAt", "")
                published_formatted = self._format_publish_date(published_at)

                logger.info(
                    f"YouTube search result: video_id={video_id}, title={snippet.get('title', 'Unknown')}, duration={duration}, views={view_count_formatted}"
                )

                results.append(
                    {
                        "id": video_id,
                        "title": snippet.get("title", "Unknown"),
                        "channel": snippet.get("channelTitle", "Unknown"),
                        "thumbnail": thumbnail_url,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "platform": "youtube",
                        "description": (
                            snippet.get("description", "")[:200] + "..."
                            if len(snippet.get("description", "")) > 200
                            else snippet.get("description", "")
                        ),
                        "duration": duration,
                        "views": view_count_formatted,
                        "published": published_formatted,
                        "view_count_raw": (
                            int(view_count) if view_count.isdigit() else 0
                        ),
                    }
                )

            # Report successful API search
            report_search_success(
                "YouTube",
                SearchMethod.API_SEARCH,
                len(results),
                f"API search successful - found {len(results)} results"
            )
            return results
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")

            # Check for quota exceeded and attempt fallback
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                logger.warning("YouTube API quota exceeded, attempting yt-dlp fallback search")
                report_api_quota_exceeded(
                    "YouTube",
                    "YouTube API quota exceeded - attempting yt-dlp fallback search"
                )
                
                try:
                    fallback_results = await self._search_with_ytdlp(query, max_results)
                    if fallback_results:
                        logger.info(f"yt-dlp fallback search successful, returning {len(fallback_results)} results")
                        report_fallback_success(
                            "YouTube",
                            SearchMethod.YTDLP_SEARCH,
                            f"yt-dlp fallback search successful after quota exceeded",
                            details={'results_count': len(fallback_results)}
                        )
                        return fallback_results
                    else:
                        logger.warning("yt-dlp fallback search returned no results")
                        report_platform_error(
                            "YouTube",
                            SearchMethod.YTDLP_SEARCH,
                            "yt-dlp fallback returned no results",
                            "API quota exceeded and fallback search found no results"
                        )
                except Exception as fallback_error:
                    logger.error(f"yt-dlp fallback search failed with error: {fallback_error}")
                
                # If fallback fails, raise the original error
                raise PlatformRateLimitError(
                    "YouTube API quota exceeded and yt-dlp fallback search failed. Please try again later.",
                    platform="YouTube",
                    original_error=e,
                )

            # Use from_http_status for other HTTP errors
            raise from_http_status(e.resp.status, "YouTube", str(e))
        except NetworkResilienceError:
            # Re-raise network resilience errors as-is
            raise
        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            raise PlatformAPIError(
                f"Search failed: {str(e)}", platform="YouTube", original_error=e
            )

    def _parse_duration(self, duration: str) -> str:
        """Parse ISO 8601 duration (PT4M13S) to readable format (4:13)"""
        if not duration:
            return "Unknown"

        try:
            import re

            # Match PT[hours]H[minutes]M[seconds]S with stricter validation
            # Pattern correctly handles ISO 8601 duration format
            pattern = (
                r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
            )
            match = re.match(pattern, duration.strip())

            if not match:
                logger.debug(f"Duration format not recognized: {duration}")
                return "Unknown"

            # Extract time components with proper defaults
            hours = int(match.group("hours") or 0)
            minutes = int(match.group("minutes") or 0)
            seconds = int(match.group("seconds") or 0)

            # Handle edge case where all components are zero
            if hours == 0 and minutes == 0 and seconds == 0:
                return "0:00"

            # Format duration based on presence of hours
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"

        except Exception as e:
            logger.debug(f"Error parsing duration '{duration}': {e}")
            return "Unknown"

    def _format_view_count(self, view_count: str) -> str:
        """Format view count to readable format (1.2M, 45K, etc.)"""
        try:
            count = int(view_count)
            if count >= 1_000_000:
                return f"{count / 1_000_000:.1f}M views"
            elif count >= 1_000:
                return f"{count / 1_000:.1f}K views"
            else:
                return f"{count} views"
        except (ValueError, TypeError):
            return "Unknown views"

    def _get_best_thumbnail(self, thumbnails: Dict[str, Any]) -> str:
        """Get the best available thumbnail URL"""
        # Priority: maxres > high > medium > default
        for quality in ["maxres", "high", "medium", "default"]:
            if quality in thumbnails and "url" in thumbnails[quality]:
                return thumbnails[quality]["url"]
        return ""

    def _format_publish_date(self, published_at: str) -> str:
        """Format publish date to readable format"""
        if not published_at:
            return "Unknown"

        try:
            from datetime import datetime

            # Parse ISO format: 2023-01-15T10:30:00Z
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            now = datetime.now(dt.tzinfo)

            # Calculate time difference
            diff = now - dt
            days = diff.days

            if days == 0:
                return "Today"
            elif days == 1:
                return "Yesterday"
            elif days < 7:
                return f"{days} days ago"
            elif days < 30:
                weeks = days // 7
                return f"{weeks} week{'s' if weeks != 1 else ''} ago"
            elif days < 365:
                months = days // 30
                return f"{months} month{'s' if months != 1 else ''} ago"
            else:
                years = days // 365
                return f"{years} year{'s' if years != 1 else ''} ago"
        except Exception:
            return "Unknown"

    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a video with fallback to yt-dlp"""
        # Try API first if available
        if self.youtube:
            try:
                request = self.youtube.videos().list(
                    part="snippet,contentDetails,statistics", id=video_id
                )
                response = request.execute()

                if response.get("items"):
                    item = response["items"][0]
                    snippet = item["snippet"]

                    # Format the detailed video information
                    duration = self._parse_duration(item["contentDetails"].get("duration", ""))
                    view_count = item["statistics"].get("viewCount", "0")
                    view_count_formatted = self._format_view_count(view_count)
                    thumbnail_url = self._get_best_thumbnail(snippet.get("thumbnails", {}))
                    published_formatted = self._format_publish_date(
                        snippet.get("publishedAt", "")
                    )

                    return {
                        "id": video_id,
                        "title": snippet["title"],
                        "channel": snippet["channelTitle"],
                        "thumbnail": thumbnail_url,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "platform": "youtube",
                        "description": (
                            snippet.get("description", "")[:200] + "..."
                            if len(snippet.get("description", "")) > 200
                            else snippet.get("description", "")
                        ),
                        "duration": duration,
                        "views": view_count_formatted,
                        "published": published_formatted,
                        "view_count_raw": int(view_count) if view_count.isdigit() else 0,
                    }
            except HttpError as e:
                # Check for quota exceeded
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    logger.warning("YouTube API quota exceeded for video details, falling back to yt-dlp")
                else:
                    logger.error(f"YouTube API error getting video details: {e}")
            except Exception as e:
                logger.error(f"YouTube video details error: {e}")

        # Fallback to yt-dlp if API failed or not available
        logger.info(f"Using yt-dlp fallback for video details: {video_id}")
        return await self._extract_metadata_via_ytdlp(video_id)

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

    def _convert_cookies_to_netscape(
        self, json_cookie_file: str, netscape_cookie_file: str
    ) -> bool:
        """Convert JSON cookies to Netscape format for yt-dlp with enhanced error handling
        
        Supports multiple cookie formats:
        - Standard browser export format
        - Chrome/Brave cookie format
        - Firefox cookie format
        - Custom extraction formats
        """
        try:
            import json
            import time

            if not Path(json_cookie_file).exists():
                logger.warning(f"JSON cookie file not found: {json_cookie_file}")
                return False

            # Validate file is readable and not empty
            try:
                file_size = Path(json_cookie_file).stat().st_size
                if file_size == 0:
                    logger.warning(f"Cookie file is empty: {json_cookie_file}")
                    return False
                
                # Check file age for staleness warning
                file_stat = Path(json_cookie_file).stat()
                file_age_hours = (time.time() - file_stat.st_mtime) / 3600
                if file_age_hours > 24:
                    logger.warning(
                        f"Cookie file is {file_age_hours:.1f} hours old, consider refreshing: {json_cookie_file}"
                    )
            except Exception as e:
                logger.error(f"Cannot access cookie file {json_cookie_file}: {e}")
                return False

            # Read and parse JSON cookies with multiple format support
            try:
                with open(json_cookie_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        logger.warning(
                            f"Cookie file content is empty: {json_cookie_file}"
                        )
                        return False
                    
                    cookies_data = json.loads(content)
                    
                    # Handle different cookie file formats
                    cookies = self._normalize_cookie_format(cookies_data)
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in cookie file {json_cookie_file}: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to read cookie file {json_cookie_file}: {e}")
                return False

            if not cookies:
                logger.warning(
                    f"No valid cookies found in {json_cookie_file}"
                )
                return False

            # Validate and filter cookies
            valid_cookies = self._validate_and_filter_cookies(cookies)
            if not valid_cookies:
                logger.warning("No valid cookies remained after validation")
                return False

            # Ensure output directory exists
            try:
                Path(netscape_cookie_file).parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Cannot create cookie output directory: {e}")
                return False

            # Convert to Netscape format with enhanced validation
            try:
                return self._write_netscape_cookies(valid_cookies, netscape_cookie_file)
            except Exception as e:
                logger.error(
                    f"Failed to write Netscape cookie file {netscape_cookie_file}: {e}"
                )
                return False

        except Exception as e:
            logger.error(f"Unexpected error during cookie conversion: {e}")
            import traceback

            logger.debug(f"Cookie conversion traceback: {traceback.format_exc()}")
            return False

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="youtube_stream_url",
        exceptions=(Exception,),
        exclude_exceptions=(
            PlatformAPIError,
            CircuitBreakerOpenError,
            NetworkResilienceError,
        ),
    )
    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL using yt-dlp with cookies and enhanced error handling"""
        import yt_dlp
        import asyncio

        logger.info(f"Getting stream URL for YouTube video: {video_id}")

        # Validate video ID format
        if not video_id or len(video_id) != 11:
            logger.error(
                f"Invalid YouTube video ID: {video_id} (expected 11 characters)"
            )
            raise PlatformAPIError(
                f"Invalid YouTube video ID: {video_id}", platform="YouTube"
            )

        try:
            # Use yt-dlp to get stream URL
            url = f"https://www.youtube.com/watch?v={video_id}"

            # Configure yt-dlp options optimized for Discord audio with enhanced cookie support
            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best[height<=720]",
                "quiet": True,
                "no_warnings": False,  # Enable warnings for debugging
                "noplaylist": True,
                "extract_flat": False,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "http_chunk_size": 10485760,  # 10MB chunks
                "prefer_insecure": False,
                "verbose": False,
                "socket_timeout": 30,
                "retries": 3,
                # Enhanced cookie and authentication settings
                "extractor_retries": 3,
                "fragment_retries": 5,
                "skip_unavailable_fragments": True,
                "keep_fragments": False,
                "abort_on_unavailable_fragment": False,
                # Better error handling for auth issues
                "ignoreerrors": False,
                "no_color": True,
                # Subtitle settings - disable downloads for audio streaming
                "writesubtitles": False,
                "writeautomaticsub": False,
            }

            # Enhanced cookie loading with comprehensive fallback paths
            cookie_result = self._load_cookies_with_fallback()
            if cookie_result["success"]:
                ydl_opts["cookiefile"] = cookie_result["cookie_file"]
                logger.info(
                    f"Using YouTube cookies: {cookie_result['cookie_file']} "
                    f"({cookie_result['cookie_count']} cookies, {cookie_result['age_info']})"
                )
            else:
                logger.warning(
                    f"Cookie loading failed: {cookie_result['error']}. "
                    "Proceeding without authentication - some videos may be unavailable."
                )

            def extract_info():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)

                        if not info:
                            logger.error("yt-dlp returned no information")
                            return None, "No video information found"

                        # Extract URL from different possible structures
                        stream_url = None

                        if "url" in info:
                            stream_url = info["url"]
                        elif "formats" in info and info["formats"]:
                            # Find best audio format
                            formats = info["formats"]

                            # Prefer audio-only formats
                            audio_formats = [
                                f
                                for f in formats
                                if f.get("vcodec") == "none" and f.get("url")
                            ]
                            if audio_formats:
                                # Sort by audio quality (prefer higher bitrate)
                                audio_formats.sort(
                                    key=lambda f: f.get("abr", 0) or f.get("tbr", 0),
                                    reverse=True,
                                )
                                stream_url = audio_formats[0]["url"]
                                logger.debug(
                                    f"Selected audio format: {audio_formats[0].get('format_id')} (bitrate: {audio_formats[0].get('abr', 'unknown')})"
                                )
                            else:
                                # Fallback to best available format
                                valid_formats = [f for f in formats if f.get("url")]
                                if valid_formats:
                                    # Sort by quality and prefer audio formats
                                    valid_formats.sort(
                                        key=lambda f: (
                                            f.get("acodec", "")
                                            != "none",  # Audio available
                                            f.get("abr", 0)
                                            or f.get("tbr", 0),  # Bitrate
                                        ),
                                        reverse=True,
                                    )
                                    stream_url = valid_formats[0]["url"]
                                    logger.debug(
                                        f"Selected fallback format: {valid_formats[0].get('format_id')}"
                                    )
                        elif "entries" in info and info["entries"]:
                            # Handle playlist case (should not happen with noplaylist=True)
                            first_entry = info["entries"][0]
                            if first_entry and "url" in first_entry:
                                stream_url = first_entry["url"]

                        if not stream_url:
                            logger.error(
                                "No valid stream URL found in extraction result"
                            )
                            return None, "No stream URL found"

                        logger.debug(f"Extracted stream URL: {stream_url[:100]}...")
                        return stream_url, None

                except yt_dlp.DownloadError as e:
                    error_msg = str(e)
                    logger.error(f"yt-dlp download error: {error_msg}")

                    # Handle specific errors
                    if "private" in error_msg.lower():
                        return None, "Video is private"
                    elif "unavailable" in error_msg.lower():
                        return None, "Video is unavailable"
                    elif "copyright" in error_msg.lower():
                        return None, "Video blocked due to copyright"
                    elif "region" in error_msg.lower():
                        return None, "Video not available in your region"
                    else:
                        return None, f"Download error: {error_msg}"

                except Exception as e:
                    logger.error(f"yt-dlp extraction error: {e}")
                    return None, f"Extraction error: {str(e)}"

            # Run yt-dlp in thread to avoid blocking
            loop = asyncio.get_event_loop()
            stream_url, error = await loop.run_in_executor(None, extract_info)

            # Handle errors
            if error:
                logger.error(f"Stream extraction failed for video {video_id}: {error}")
                raise PlatformAPIError(
                    f"Failed to extract stream: {error}", platform="YouTube"
                )

            # Return stream URL if extracted
            if stream_url:
                logger.info(
                    f"Successfully extracted stream URL for {video_id}: {stream_url[:100]}..."
                )
                return stream_url
            else:
                logger.error(f"No stream URL extracted for video {video_id}")
                raise PlatformAPIError(
                    "No stream URL could be extracted", platform="YouTube"
                )

        except PlatformAPIError:
            # Re-raise platform errors
            raise
        except Exception as e:
            logger.error(f"Failed to get stream URL for {video_id}: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")
            raise PlatformAPIError(
                f"Stream extraction failed: {str(e)}",
                platform="YouTube",
                original_error=e,
            )

    def _validate_stream_url(self, url: str) -> bool:
        """Validate that the stream URL is accessible (sync version)"""
        try:
            import requests

            # Quick HEAD request to check if URL is accessible
            response = requests.head(url, timeout=5, allow_redirects=True)
            is_valid = response.status_code < 400

            if not is_valid:
                logger.warning(
                    f"Stream URL validation failed with status {response.status_code}"
                )

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
                            logger.warning(
                                f"Stream URL validation failed with status {response.status}"
                            )

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

    def _get_ytdlp_config(self, query: str = "") -> Dict[str, Any]:
        """Get yt-dlp configuration with cookies, language preferences, and subtitle settings"""
        ydl_opts = {
            "quiet": True,
            "no_warnings": False,
            "noplaylist": True,
            "extract_flat": False,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "prefer_insecure": False,
            "verbose": False,
            "socket_timeout": 30,
            "retries": 2,
            # Enhanced settings for authenticated access
            "extractor_retries": 2,
            "fragment_retries": 3,
            "skip_unavailable_fragments": True,
            "ignoreerrors": False,
            "no_color": True,
            # Better handling of age-restricted content
            "age_limit": None,
            # Subtitle settings - disable downloads
            "writesubtitles": False,
            "writeautomaticsub": False,
            # Language preferences based on query
            "extractor_args": self._get_language_preferences(query),
        }

        # Enhanced cookie loading for metadata extraction
        cookie_result = self._load_cookies_with_fallback()
        if cookie_result["success"]:
            ydl_opts["cookiefile"] = cookie_result["cookie_file"]
            logger.debug(
                f"Using YouTube cookies for metadata: {cookie_result['cookie_file']} "
                f"({cookie_result['cookie_count']} cookies)"
            )

        return ydl_opts

    def _normalize_cookie_format(self, cookies_data) -> List[Dict]:
        """Normalize different cookie formats to a standard format"""
        if isinstance(cookies_data, list):
            # Already in list format (most common)
            return cookies_data
        elif isinstance(cookies_data, dict):
            # Handle different dictionary formats
            if "cookies" in cookies_data:
                # Format: {"cookies": [...]}
                return cookies_data["cookies"]
            elif "data" in cookies_data:
                # Format: {"data": [...]} or {"data": {"cookies": [...]}}
                data = cookies_data["data"]
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "cookies" in data:
                    return data["cookies"]
            else:
                # Treat dictionary as single cookie entry
                if "name" in cookies_data and "value" in cookies_data:
                    return [cookies_data]
                else:
                    # Try to extract cookies from keys
                    potential_cookies = []
                    for key, value in cookies_data.items():
                        if isinstance(value, dict) and "name" in value:
                            potential_cookies.append(value)
                        elif isinstance(value, list):
                            potential_cookies.extend(value)
                    return potential_cookies
        
        logger.warning(f"Unknown cookie format: {type(cookies_data)}")
        return []

    def _validate_and_filter_cookies(self, cookies: List[Dict]) -> List[Dict]:
        """Validate and filter cookies with expiration checking"""
        import time
        
        valid_cookies = []
        current_time = int(time.time())
        expired_count = 0
        invalid_count = 0
        
        for cookie in cookies:
            # Skip invalid cookie entries
            if not isinstance(cookie, dict):
                invalid_count += 1
                continue

            name = cookie.get("name", "").strip()
            value = cookie.get("value", "")

            # Skip cookies without name (value can be empty)
            if not name:
                invalid_count += 1
                continue

            # Skip cookies with problematic characters
            if (
                "\t" in name
                or "\t" in str(value)
                or "\n" in name
                or "\n" in str(value)
                or "\r" in name
                or "\r" in str(value)
            ):
                logger.debug(
                    f"Skipping cookie with invalid characters: {name}"
                )
                invalid_count += 1
                continue

            # Check cookie expiration
            expires = cookie.get("expires")
            if expires is not None:
                # Handle different expiration formats
                if isinstance(expires, str):
                    try:
                        # Try parsing ISO format
                        dt = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                        expires = int(dt.timestamp())
                    except:
                        try:
                            # Try parsing as timestamp string
                            expires = int(float(expires))
                        except:
                            expires = None
                
                if expires and expires > 0 and expires < current_time:
                    logger.debug(f"Skipping expired cookie: {name} (expired {(current_time - expires) // 3600}h ago)")
                    expired_count += 1
                    continue

            # Cookie is valid, add to list
            valid_cookies.append(cookie)
        
        if expired_count > 0:
            logger.info(f"Filtered out {expired_count} expired cookies")
        if invalid_count > 0:
            logger.debug(f"Filtered out {invalid_count} invalid cookies")
            
        return valid_cookies

    def _write_netscape_cookies(self, cookies: List[Dict], netscape_cookie_file: str) -> bool:
        """Write cookies to Netscape format file with enhanced validation"""
        try:
            with open(netscape_cookie_file, "w", encoding="utf-8") as f:
                # Write Netscape cookie file header
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# This is a generated file! Do not edit.\n")
                f.write(f"# Generated at: {datetime.now().isoformat()}\n\n")

                written_cookies = 0
                for cookie in cookies:
                    name = cookie.get("name", "").strip()
                    value = str(cookie.get("value", ""))  # Convert to string

                    # Netscape format: domain, domain_specified, path, secure, expires, name, value
                    domain = cookie.get("domain", ".youtube.com")
                    if not domain:
                        domain = ".youtube.com"
                    
                    # Ensure domain starts with . for wildcard domains
                    if not domain.startswith(".") and not domain.startswith("http"):
                        if "youtube" in domain or "google" in domain:
                            if not domain.startswith("www."):
                                domain = f".{domain}"

                    domain_specified = "TRUE" if domain.startswith(".") else "FALSE"
                    path = cookie.get("path", "/")
                    secure = "TRUE" if cookie.get("secure", False) else "FALSE"

                    # Handle expires field with better validation
                    expires = cookie.get("expires", 0)
                    if expires is None:
                        expires = 0
                    elif isinstance(expires, (int, float)):
                        expires = int(expires)
                        # Validate timestamp is reasonable (not too far in future)
                        import time
                        max_future = int(time.time()) + (10 * 365 * 24 * 3600)  # 10 years
                        if expires > max_future:
                            expires = max_future
                    else:
                        expires = 0

                    # Write cookie line in Netscape format
                    cookie_line = f"{domain}\t{domain_specified}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"
                    f.write(cookie_line)
                    written_cookies += 1

            if written_cookies > 0:
                logger.info(
                    f"Successfully converted {written_cookies} cookies to Netscape format: {netscape_cookie_file}"
                )
                return True
            else:
                logger.warning("No cookies were written to Netscape file")
                return False
                
        except Exception as e:
            logger.error(f"Error writing Netscape cookie file: {e}")
            return False

    async def _extract_metadata_via_ytdlp(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Extract video metadata using yt-dlp as fallback when API quota is exceeded"""
        import yt_dlp
        import asyncio

        logger.info(f"Extracting metadata via yt-dlp for video: {video_id}")

        # Validate video ID format
        if not video_id or len(video_id) != 11:
            logger.error(
                f"Invalid YouTube video ID: {video_id} (expected 11 characters)"
            )
            return None

        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            ydl_opts = self._get_ytdlp_config("")  # Empty query for metadata extraction

            def extract_metadata():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        
                        if not info:
                            logger.error("yt-dlp returned no information")
                            return None

                        # Extract metadata in the same format as API results
                        title = info.get("title", "Unknown")
                        channel = info.get("uploader", info.get("channel", "Unknown"))
                        description = info.get("description", "")
                        duration_seconds = info.get("duration")
                        view_count = info.get("view_count", 0)
                        upload_date = info.get("upload_date")
                        
                        # Get best thumbnail
                        thumbnails = info.get("thumbnails", [])
                        thumbnail_url = ""
                        if thumbnails:
                            # Sort by resolution/quality
                            sorted_thumbnails = sorted(
                                thumbnails, 
                                key=lambda t: (t.get("width", 0) * t.get("height", 0)),
                                reverse=True
                            )
                            thumbnail_url = sorted_thumbnails[0].get("url", "")

                        # Format duration from seconds to readable format
                        duration = "Unknown"
                        if duration_seconds and isinstance(duration_seconds, (int, float)):
                            duration_seconds = int(duration_seconds)
                            if duration_seconds >= 3600:
                                hours = duration_seconds // 3600
                                minutes = (duration_seconds % 3600) // 60
                                seconds = duration_seconds % 60
                                duration = f"{hours}:{minutes:02d}:{seconds:02d}"
                            else:
                                minutes = duration_seconds // 60
                                seconds = duration_seconds % 60
                                duration = f"{minutes}:{seconds:02d}"

                        # Format view count
                        view_count_formatted = self._format_view_count(str(view_count))

                        # Format publish date
                        published_formatted = "Unknown"
                        if upload_date:
                            try:
                                from datetime import datetime
                                # upload_date is in format YYYYMMDD
                                dt = datetime.strptime(upload_date, "%Y%m%d")
                                now = datetime.now()
                                diff = now - dt
                                days = diff.days

                                if days == 0:
                                    published_formatted = "Today"
                                elif days == 1:
                                    published_formatted = "Yesterday"
                                elif days < 7:
                                    published_formatted = f"{days} days ago"
                                elif days < 30:
                                    weeks = days // 7
                                    published_formatted = f"{weeks} week{'s' if weeks != 1 else ''} ago"
                                elif days < 365:
                                    months = days // 30
                                    published_formatted = f"{months} month{'s' if months != 1 else ''} ago"
                                else:
                                    years = days // 365
                                    published_formatted = f"{years} year{'s' if years != 1 else ''} ago"
                            except Exception:
                                published_formatted = "Unknown"

                        logger.info(
                            f"yt-dlp metadata extracted: video_id={video_id}, title={title}, duration={duration}, views={view_count_formatted}"
                        )

                        return {
                            "id": video_id,
                            "title": title,
                            "channel": channel,
                            "thumbnail": thumbnail_url,
                            "url": url,
                            "platform": "youtube",
                            "description": (
                                description[:200] + "..."
                                if len(description) > 200
                                else description
                            ),
                            "duration": duration,
                            "views": view_count_formatted,
                            "published": published_formatted,
                            "view_count_raw": int(view_count) if isinstance(view_count, (int, float)) else 0,
                        }

                except yt_dlp.DownloadError as e:
                    error_msg = str(e)
                    logger.error(f"yt-dlp download error: {error_msg}")
                    
                    # Log specific errors but don't fail completely
                    if "private" in error_msg.lower():
                        logger.warning("Video is private")
                    elif "unavailable" in error_msg.lower():
                        logger.warning("Video is unavailable")
                    elif "copyright" in error_msg.lower():
                        logger.warning("Video blocked due to copyright")
                    elif "region" in error_msg.lower():
                        logger.warning("Video not available in region")
                    
                    return None

                except Exception as e:
                    logger.error(f"yt-dlp metadata extraction error: {e}")
                    return None

            # Run yt-dlp in thread to avoid blocking
            loop = asyncio.get_event_loop()
            metadata = await loop.run_in_executor(None, extract_metadata)
            
            if metadata:
                logger.info(f"Successfully extracted metadata via yt-dlp for {video_id}")
                return metadata
            else:
                logger.warning(f"Failed to extract metadata via yt-dlp for {video_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to extract metadata via yt-dlp for {video_id}: {e}")
            return None

    async def _search_via_url_parsing(self, query: str) -> List[Dict[str, Any]]:
        """Handle direct YouTube URLs in search queries by extracting video metadata"""
        logger.info(f"Attempting URL parsing search for query: {query}")
        
        # Check if query contains a YouTube URL
        video_id = self.extract_video_id(query)
        if not video_id:
            logger.debug("No YouTube URL found in query")
            return []
        
        logger.info(f"Extracted video ID from URL: {video_id}")
        
        # Try to get metadata via yt-dlp
        metadata = await self._extract_metadata_via_ytdlp(video_id)
        if metadata:
            logger.info(f"Successfully extracted metadata for URL: {query}")
            return [metadata]
        else:
            logger.warning(f"Failed to extract metadata for URL: {query}")
            return []

    async def _search_with_ytdlp(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Use yt-dlp's ytsearch: feature to search YouTube without API with language preferences"""
        import yt_dlp
        import asyncio
        
        logger.info(f"Attempting yt-dlp search for query: {query} (max_results: {max_results})")
        
        # First check if it's a URL
        url_results = await self._search_via_url_parsing(query)
        if url_results:
            logger.info("Found URL in query, returning metadata")
            return url_results
        
        try:
            # Get language parameters for consistent behavior
            language_params = self._get_search_params(query)
            detected_language = language_params.get("relevanceLanguage", "auto")
            
            # Use yt-dlp's search functionality
            search_query = f"ytsearch{max_results}:{query}"
            ydl_opts = self._get_ytdlp_config()
            ydl_opts.update({
                "extract_flat": False,  # We need full metadata
                "playlistend": max_results,
                "quiet": True,
                "no_warnings": True,  # Reduce noise in logs
                # Add HTTP headers for English language preference
                "http_headers": {
                    "Accept-Language": f"{self.default_language}-{self.default_region},{self.default_language};q=0.9",
                },
            })
            
            # Add language preference for yt-dlp if query is detected as English
            if detected_language == 'en':
                # yt-dlp doesn't have direct language preference, but we can add geo-bypass
                # and prefer English content through user-agent and headers
                ydl_opts.update({
                    "geo_bypass": True,
                    "geo_bypass_country": "US",  # Prefer US content for English queries
                })
                logger.debug(f"Applied English preferences to yt-dlp search for query: {query}")
            else:
                logger.debug(f"Using default yt-dlp settings for non-English query: {query}")
            
            def search_videos():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        search_results = ydl.extract_info(search_query, download=False)
                        
                        if not search_results or "entries" not in search_results:
                            logger.warning("yt-dlp search returned no results")
                            return []
                        
                        results = []
                        entries = search_results["entries"] or []
                        
                        for entry in entries[:max_results]:
                            if not entry:
                                continue
                                
                            # Extract metadata from yt-dlp result
                            metadata = self._extract_metadata_from_ytdlp_result(entry)
                            if metadata:
                                results.append(metadata)
                                logger.debug(f"Processed yt-dlp search result: {metadata['title']}")
                        
                        logger.info(f"yt-dlp search extracted {len(results)} results")
                        return results
                        
                except yt_dlp.DownloadError as e:
                    logger.error(f"yt-dlp search download error: {e}")
                    return []
                except Exception as e:
                    logger.error(f"yt-dlp search error: {e}")
                    return []
            
            # Run yt-dlp search in thread to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, search_videos)
            
            if results:
                logger.info(f"yt-dlp search successful, found {len(results)} results")
                return results
            else:
                logger.warning("yt-dlp search returned no results")
                return []
                
        except Exception as e:
            logger.error(f"yt-dlp search failed: {e}")
            return []
    
    def _extract_metadata_from_ytdlp_result(self, info_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert yt-dlp metadata to our standard format"""
        try:
            # Extract basic information
            video_id = info_dict.get("id")
            if not video_id:
                logger.debug("No video ID found in yt-dlp result")
                return None
            
            title = info_dict.get("title", "Unknown")
            channel = info_dict.get("uploader", info_dict.get("channel", "Unknown"))
            description = info_dict.get("description", "")
            duration_seconds = info_dict.get("duration")
            view_count = info_dict.get("view_count", 0)
            upload_date = info_dict.get("upload_date")
            
            # Get best thumbnail
            thumbnails = info_dict.get("thumbnails", [])
            thumbnail_url = ""
            if thumbnails:
                # Sort by resolution/quality (prefer higher resolution)
                sorted_thumbnails = sorted(
                    [t for t in thumbnails if t.get("url")],
                    key=lambda t: (t.get("width", 0) * t.get("height", 0)),
                    reverse=True
                )
                if sorted_thumbnails:
                    thumbnail_url = sorted_thumbnails[0].get("url", "")
            
            # Format duration from seconds to readable format
            duration = "Unknown"
            if duration_seconds and isinstance(duration_seconds, (int, float)):
                duration_seconds = int(duration_seconds)
                if duration_seconds >= 3600:
                    hours = duration_seconds // 3600
                    minutes = (duration_seconds % 3600) // 60
                    seconds = duration_seconds % 60
                    duration = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    minutes = duration_seconds // 60
                    seconds = duration_seconds % 60
                    duration = f"{minutes}:{seconds:02d}"
            
            # Format view count
            view_count_formatted = self._format_view_count(str(view_count))
            
            # Format publish date
            published_formatted = "Unknown"
            if upload_date:
                try:
                    from datetime import datetime
                    # upload_date is in format YYYYMMDD
                    dt = datetime.strptime(upload_date, "%Y%m%d")
                    now = datetime.now()
                    diff = now - dt
                    days = diff.days
                    
                    if days == 0:
                        published_formatted = "Today"
                    elif days == 1:
                        published_formatted = "Yesterday"
                    elif days < 7:
                        published_formatted = f"{days} days ago"
                    elif days < 30:
                        weeks = days // 7
                        published_formatted = f"{weeks} week{'s' if weeks != 1 else ''} ago"
                    elif days < 365:
                        months = days // 30
                        published_formatted = f"{months} month{'s' if months != 1 else ''} ago"
                    else:
                        years = days // 365
                        published_formatted = f"{years} year{'s' if years != 1 else ''} ago"
                except Exception as e:
                    logger.debug(f"Error formatting publish date: {e}")
                    published_formatted = "Unknown"
            
            # Create URL
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Truncate description if too long
            if len(description) > 200:
                description = description[:200] + "..."
            
            logger.debug(
                f"Extracted yt-dlp metadata: video_id={video_id}, title={title}, duration={duration}, views={view_count_formatted}"
            )
            
            return {
                "id": video_id,
                "title": title,
                "channel": channel,
                "thumbnail": thumbnail_url,
                "url": url,
                "platform": "youtube",
                "description": description,
                "duration": duration,
                "views": view_count_formatted,
                "published": published_formatted,
                "view_count_raw": int(view_count) if isinstance(view_count, (int, float)) else 0,
            }
            
        except Exception as e:
            logger.error(f"Error extracting metadata from yt-dlp result: {e}")
            return None
    
    async def _fallback_search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Fallback search method when API quota is exceeded - now uses yt-dlp"""
        logger.info(f"Attempting fallback search for query: {query}")
        return await self._search_with_ytdlp(query, max_results)

    def _load_cookies_with_fallback(self) -> Dict[str, Any]:
        """Load cookies with comprehensive fallback and validation
        
        Returns:
            Dict containing success status, cookie file path, error info, and metadata
        """
        import time
        
        # Define cookie search paths in order of preference
        base_paths = [
            Path("/app/cookies"),
            Path("data/cookies"), 
            Path("./cookies"),
            Path("cookies"),  # Simple relative path
            Path.home() / ".config" / "robustty" / "cookies",  # User config
        ]
        
        # Add additional paths from environment or config
        env_cookie_path = os.getenv("ROBUSTTY_COOKIE_PATH")
        if env_cookie_path:
            base_paths.insert(0, Path(env_cookie_path))
        
        result = {
            "success": False,
            "cookie_file": None,
            "error": "No cookie paths found",
            "cookie_count": 0,
            "age_info": "unknown",
            "paths_tried": []
        }
        
        for base_path in base_paths:
            json_cookie_file = base_path / "youtube_cookies.json"
            result["paths_tried"].append(str(json_cookie_file))
            
            if not json_cookie_file.exists():
                continue
                
            try:
                # Check file age and size
                file_stat = json_cookie_file.stat()
                if file_stat.st_size == 0:
                    logger.debug(f"Skipping empty cookie file: {json_cookie_file}")
                    continue
                    
                file_age_hours = (time.time() - file_stat.st_mtime) / 3600
                age_info = f"{file_age_hours:.1f}h old"
                
                # Attempt cookie conversion with validation
                netscape_cookie_file = base_path / "youtube_cookies.txt"
                
                if self._convert_cookies_to_netscape(
                    str(json_cookie_file), str(netscape_cookie_file)
                ):
                    # Count cookies for reporting
                    cookie_count = self._count_netscape_cookies(str(netscape_cookie_file))
                    
                    # Verify cookie file health
                    health_check = self._verify_cookie_health(str(json_cookie_file))
                    
                    result.update({
                        "success": True,
                        "cookie_file": str(netscape_cookie_file),
                        "error": None,
                        "cookie_count": cookie_count,
                        "age_info": age_info,
                        "health_status": health_check,
                        "source_file": str(json_cookie_file)
                    })
                    
                    # Log health warnings if any
                    if health_check.get("warnings"):
                        for warning in health_check["warnings"]:
                            logger.warning(f"Cookie health warning: {warning}")
                    
                    return result
                else:
                    logger.debug(f"Cookie conversion failed for: {json_cookie_file}")
                    
            except Exception as e:
                logger.debug(f"Error processing cookie file {json_cookie_file}: {e}")
                continue
        
        result["error"] = f"No valid cookies found in {len(base_paths)} paths"
        return result

    def _count_netscape_cookies(self, netscape_file: str) -> int:
        """Count cookies in Netscape format file"""
        try:
            with open(netscape_file, 'r') as f:
                return sum(1 for line in f if line.strip() and not line.startswith('#'))
        except Exception:
            return 0
    
    def _verify_cookie_health(self, json_cookie_file: str) -> Dict[str, Any]:
        """Verify cookie health and detect issues
        
        Returns health status with warnings and recommendations
        """
        import json
        import time
        
        health = {
            "healthy": True,
            "warnings": [],
            "recommendations": [],
            "expires_soon": [],
            "total_cookies": 0,
            "expired_cookies": 0
        }
        
        try:
            with open(json_cookie_file, 'r') as f:
                cookies_data = json.load(f)
                cookies = self._normalize_cookie_format(cookies_data)
                
            current_time = int(time.time())
            health["total_cookies"] = len(cookies)
            
            # Check for critical authentication cookies
            auth_cookies = set()
            expires_within_24h = []
            expired_count = 0
            
            for cookie in cookies:
                name = cookie.get("name", "")
                expires = cookie.get("expires")
                
                # Track important authentication cookies
                if name.lower() in ['session_token', 'sapisid', 'hsid', 'ssid', 'apisid', 'login_info']:
                    auth_cookies.add(name)
                
                # Check expiration
                if expires and isinstance(expires, (int, float)) and expires > 0:
                    if expires < current_time:
                        expired_count += 1
                    elif expires < current_time + 24 * 3600:  # Expires within 24 hours
                        hours_until_expiry = (expires - current_time) / 3600
                        expires_within_24h.append((name, hours_until_expiry))
            
            health["expired_cookies"] = expired_count
            health["expires_soon"] = expires_within_24h
            
            # Generate warnings and recommendations
            if expired_count > 0:
                health["warnings"].append(f"{expired_count} cookies have expired")
                health["recommendations"].append("Refresh browser cookies")
                
            if len(expires_within_24h) > 0:
                health["warnings"].append(
                    f"{len(expires_within_24h)} cookies expire within 24 hours"
                )
                health["recommendations"].append("Consider refreshing cookies soon")
            
            # Check for essential authentication cookies
            essential_cookies = {'sapisid', 'hsid', 'ssid'}
            missing_essential = essential_cookies - {c.lower() for c in auth_cookies}
            if missing_essential:
                health["warnings"].append(
                    f"Missing important auth cookies: {', '.join(missing_essential)}"
                )
                health["recommendations"].append(
                    "Re-authenticate in browser to get fresh cookies"
                )
            
            # Check file age
            file_age_hours = (time.time() - Path(json_cookie_file).stat().st_mtime) / 3600
            if file_age_hours > 48:  # Older than 2 days
                health["warnings"].append(f"Cookie file is {file_age_hours:.1f} hours old")
                health["recommendations"].append("Extract fresh cookies from browser")
            
            if health["warnings"]:
                health["healthy"] = False
                
        except Exception as e:
            health["healthy"] = False
            health["warnings"].append(f"Cookie health check failed: {str(e)}")
        
        return health
    
    def _should_refresh_cookies(self) -> bool:
        """Determine if cookies should be refreshed based on health status"""
        if self.cookie_health_monitor:
            return self.cookie_health_monitor.should_use_fallback("youtube")
        
        # Fallback: check cookie file age
        cookie_paths = [
            Path("/app/cookies/youtube_cookies.json"),
            Path("data/cookies/youtube_cookies.json"),
            Path("./cookies/youtube_cookies.json"),
        ]
        
        for cookie_file in cookie_paths:
            if cookie_file.exists():
                try:
                    import time
                    file_age_hours = (time.time() - cookie_file.stat().st_mtime) / 3600
                    return file_age_hours > 12  # Refresh if older than 12 hours
                except Exception:
                    return True  # Refresh on error
        
        return True  # Refresh if no cookies found

    def _detect_query_language(self, query: str) -> str:
        """Detect the primary language of the search query"""
        try:
            import re
            
            # Remove common musical notation and special characters
            cleaned_query = re.sub(r'[^\w\s]', ' ', query.lower())
            
            # Check for English indicators
            english_patterns = [
                r'\b(song|music|video|cover|live|official|acoustic|remix|lyrics|audio)\b',
                r'\b(the|and|or|for|with|by|feat|featuring)\b',
                r'\b[a-z]+ing\b',  # English -ing words
                r'\b[a-z]+ed\b',   # English -ed words
            ]
            
            english_score = 0
            for pattern in english_patterns:
                if re.search(pattern, cleaned_query):
                    english_score += 1
            
            # Check for non-English indicators
            non_english_patterns = [
                r'[àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]',  # Latin accents
                r'[αβγδεζηθικλμνξοπρστυφχψω]',        # Greek
                r'[абвгдеёжзийклмнопрстуфхцчшщъыьэюя]', # Cyrillic
                r'[一-龯]',                              # Chinese/Japanese
                r'[가-힣]',                              # Korean
                r'[ا-ي]',                               # Arabic
            ]
            
            non_english_score = 0
            for pattern in non_english_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    non_english_score += 2  # Weight non-English indicators higher
            
            # Determine language
            if english_score > non_english_score:
                return "en"
            elif non_english_score > 0:
                return "auto"  # Let YouTube decide for non-English content
            else:
                return "en"    # Default to English for ambiguous cases
                
        except Exception as e:
            logger.debug(f"Language detection error: {e}")
            return "en"  # Default to English on error

    def _get_language_preferences(self, query: str) -> Dict[str, Any]:
        """Get language preferences for yt-dlp based on query language with English defaults"""
        detected_lang = self._detect_query_language(query)
        
        # Build YouTube-specific extractor arguments
        youtube_args = {}
        
        if detected_lang == "en" or self.prefer_english_results:
            # Prefer English content for English queries or when English preference is enabled
            youtube_args = {
                "lang": ["en", "en-US", "en-GB"],
                "player_client": ["web"],
                "skip_dash_manifest": False,
                "geo_bypass_country": self.default_region,
                "hl": self.interface_language,
            }
            logger.debug("Using English language preferences for search")
        else:
            # For non-English queries when English preference is disabled
            youtube_args = {
                "player_client": ["web"],
                "skip_dash_manifest": False,
            }
            logger.debug(f"Using auto language preferences for detected language: {detected_lang}")
        
        return {"youtube": youtube_args}

    def _build_search_query(self, query: str, max_results: int) -> str:
        """Build optimized search query with language preferences"""
        detected_lang = self._detect_query_language(query)
        
        # Base search query
        search_query = f"ytsearch{max_results}:{query}"
        
        # For English queries, we can add language hints to improve results
        if detected_lang == "en":
            # Add subtle English preference without being too restrictive
            # This helps prioritize English content without excluding other languages entirely
            logger.debug("Building English-optimized search query")
        else:
            logger.debug(f"Building search query for detected language: {detected_lang}")
        
        return search_query
