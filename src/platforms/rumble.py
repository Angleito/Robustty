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
    from_http_status,
)
from ..extractors.rumble_extractor import RumbleExtractor
from ..services.metrics_collector import get_metrics_collector
from ..utils.network_resilience import (
    with_retry,
    with_circuit_breaker,
    PLATFORM_RETRY_CONFIG,
    PLATFORM_CIRCUIT_BREAKER_CONFIG,
    NetworkResilienceError,
    CircuitBreakerOpenError,
    NetworkTimeoutError,
    MaxRetriesExceededError,
)

logger = logging.getLogger(__name__)


class RumblePlatform(VideoPlatform):
    """Rumble platform implementation"""

    def __init__(self, name: str, config: Dict[str, Any], cache_manager=None):
        super().__init__(name, config, cache_manager)
        self.api_token: Optional[str] = config.get("api_token")

        # URL patterns for Rumble
        self.url_patterns = [
            re.compile(r"rumble\.com/(v[A-Za-z0-9]+)(?:-[^/?]*)?"),
            re.compile(r"rumble\.com/embed/(v[A-Za-z0-9]+)(?:[/?].*)?$"),
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

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="rumble_search",
        exceptions=(PlatformAPIError, ConnectionError, TimeoutError),
        exclude_exceptions=(
            PlatformAuthenticationError,
            PlatformRateLimitError,
            CircuitBreakerOpenError,
        ),
    )
    async def search_videos(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search Rumble videos using Apify API with enhanced error handling"""
        # Check cache first
        cached_results = await self.get_cached_search_results(query)
        if cached_results:
            logger.info(f"Using cached Rumble search results for: {query}")
            return cached_results

        if not self.api_token or not self.extractor:
            logger.error("Rumble API token not configured")
            raise PlatformAuthenticationError(
                "API token is required for Rumble searches. Please configure 'api_token' in config.",
                platform="Rumble",
            )

        try:
            logger.debug(f"Searching Rumble for: {query} (max_results: {max_results})")

            # Use metrics timer context manager
            with self.metrics.api_call_timer("search"):
                # Call the extractor's search method with timeout
                import asyncio

                search_results = await asyncio.wait_for(
                    self.extractor.search_videos(query, max_results),
                    timeout=20.0,  # 20 second timeout for Rumble searches
                )

            if not search_results:
                logger.info(f"No results returned from Rumble for query: {query}")
                return []

            # Convert the results to our expected format
            results: List[Dict[str, Any]] = []
            for video in search_results:
                try:
                    # Validate required fields
                    video_id = video.get("id", "")
                    title = video.get("title", "")
                    url = video.get("url", "")

                    if not video_id or not title:
                        logger.warning(f"Skipping invalid Rumble video result: {video}")
                        continue

                    results.append(
                        {
                            "id": video_id,
                            "title": title,
                            "channel": video.get("uploader", "Unknown"),
                            "thumbnail": video.get("thumbnail_url", ""),
                            "url": url or f"https://rumble.com/{video_id}",
                            "platform": "rumble",
                            "description": video.get("description", ""),
                            "duration": video.get("duration", 0),
                            "views": video.get("view_count", 0),
                        }
                    )
                except Exception as result_error:
                    logger.warning(f"Error processing Rumble result: {result_error}")
                    continue

            logger.info(
                f"Rumble search returned {len(results)} valid results for: {query}"
            )
            # Cache the results
            await self.cache_search_results(query, results)
            return results

        except asyncio.TimeoutError:
            logger.warning(f"Rumble search timed out for query: {query}")
            raise PlatformNotAvailableError(
                "Rumble search timed out. The service might be slow or unavailable.",
                platform="Rumble",
            )
        except NetworkResilienceError:
            # Re-raise network resilience errors as-is
            raise
        except PlatformError:
            # Re-raise platform errors as-is
            raise
        except PlatformRateLimitError as e:
            self.metrics.record_rate_limit()
            logger.warning(f"Rumble rate limit exceeded: {e}")
            raise
        except Exception as e:
            logger.error(f"Rumble search error: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")

            # Categorize error based on content
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                raise PlatformNotAvailableError(
                    "Rumble service is responding slowly or is unavailable",
                    platform="Rumble",
                    original_error=e,
                )
            elif "rate limit" in error_str or "too many requests" in error_str:
                self.metrics.record_rate_limit()
                raise PlatformRateLimitError(
                    "Rumble API rate limit exceeded",
                    platform="Rumble",
                    original_error=e,
                )
            elif "unauthorized" in error_str or "forbidden" in error_str:
                raise PlatformAuthenticationError(
                    "Rumble API access denied - check API token",
                    platform="Rumble",
                    original_error=e,
                )
            else:
                # Generic API error
                raise PlatformAPIError(
                    f"Rumble search failed: {str(e)[:100]}...",
                    platform="Rumble",
                    original_error=e,
                )

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="rumble_metadata",
        exceptions=(PlatformAPIError, ConnectionError, TimeoutError),
        exclude_exceptions=(
            PlatformAuthenticationError,
            PlatformRateLimitError,
            CircuitBreakerOpenError,
        ),
    )
    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a Rumble video with enhanced error handling"""
        # Check cache first
        cached_metadata = await self.get_cached_video_metadata(video_id)
        if cached_metadata:
            logger.info(f"Using cached video metadata for Rumble video: {video_id}")
            return cached_metadata

        if not self.api_token or not self.extractor:
            logger.warning("Rumble API token not configured for video details")
            # Return basic info instead of failing completely
            basic_info = {
                "id": video_id,
                "title": f"Rumble Video {video_id}",
                "channel": "Unknown",
                "thumbnail": "",
                "url": f"https://rumble.com/{video_id}",
                "platform": "rumble",
                "description": "Video details unavailable - API token required",
                "duration": 0,
                "views": 0,
            }
            # Cache basic info too (short TTL)
            await self.cache_video_metadata(video_id, basic_info, ttl=300)  # 5 minutes
            return basic_info

        try:
            logger.debug(f"Getting details for Rumble video: {video_id}")

            # Validate video ID format
            if not video_id or not video_id.startswith("v"):
                logger.warning(f"Invalid Rumble video ID format: {video_id}")
                return None

            # Construct the video URL from the ID
            video_url = f"https://rumble.com/{video_id}"

            # Use metrics timer context manager
            with self.metrics.api_call_timer("metadata"):
                # Call the extractor's metadata method with timeout
                import asyncio

                metadata = await asyncio.wait_for(
                    self.extractor.get_video_metadata(video_url),
                    timeout=15.0,  # 15 second timeout for metadata
                )

            if not metadata:
                logger.warning(f"No metadata returned for Rumble video: {video_id}")
                return None

            # Convert the metadata to our expected format with validation
            video_metadata = {
                "id": video_id,
                "title": metadata.get("title", f"Rumble Video {video_id}"),
                "channel": metadata.get("uploader", "Unknown"),
                "thumbnail": metadata.get("thumbnail_url", ""),
                "url": video_url,
                "platform": "rumble",
                "description": metadata.get("description", ""),
                "duration": metadata.get("duration", 0),
                "views": metadata.get("view_count", 0),
                "likes": metadata.get("like_count", 0),
                "uploaded_date": metadata.get("publish_date", ""),
            }
            # Cache the metadata
            await self.cache_video_metadata(video_id, video_metadata)
            return video_metadata

        except asyncio.TimeoutError:
            logger.warning(f"Rumble metadata request timed out for video: {video_id}")
            # Return basic info as fallback
            return {
                "id": video_id,
                "title": f"Rumble Video {video_id}",
                "channel": "Unknown",
                "thumbnail": "",
                "url": f"https://rumble.com/{video_id}",
                "platform": "rumble",
                "description": "Video details unavailable - request timed out",
            }
        except NetworkResilienceError:
            # Re-raise network resilience errors
            raise
        except PlatformError:
            # Re-raise platform errors as-is
            raise
        except PlatformRateLimitError as e:
            self.metrics.record_rate_limit()
            logger.warning(f"Rumble rate limit hit getting video details: {e}")
            raise
        except Exception as e:
            logger.error(f"Rumble video details error for {video_id}: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")

            # Provide graceful degradation - return basic info
            return {
                "id": video_id,
                "title": f"Rumble Video {video_id}",
                "channel": "Unknown",
                "thumbnail": "",
                "url": f"https://rumble.com/{video_id}",
                "platform": "rumble",
                "description": f"Video details unavailable: {str(e)[:50]}...",
            }

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

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="rumble_stream_url",
        exceptions=(Exception,),
        exclude_exceptions=(
            PlatformAPIError,
            CircuitBreakerOpenError,
            NetworkResilienceError,
        ),
    )
    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL for a Rumble video using direct yt-dlp extraction with enhanced error handling"""
        import yt_dlp
        import asyncio

        logger.info(f"Getting stream URL for Rumble video: {video_id}")

        # Check cache first
        cached_stream_url = await self.get_cached_stream_url(video_id)
        if cached_stream_url:
            logger.info(f"Using cached stream URL for Rumble video: {video_id}")
            return cached_stream_url

        # Validate video ID format
        if not video_id or not video_id.startswith("v"):
            logger.error(f"Invalid Rumble video ID format: {video_id}")
            raise PlatformAPIError(
                f"Invalid Rumble video ID: {video_id}", platform="Rumble"
            )

        try:
            # Construct the video URL from the ID
            video_url = f"https://rumble.com/{video_id}"

            # Configure yt-dlp options for Rumble with enhanced settings
            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best[height<=720]",
                "quiet": True,
                "no_warnings": False,
                "noplaylist": True,
                "extract_flat": False,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "prefer_insecure": False,
                "verbose": False,
                "socket_timeout": 30,
                "retries": 2,
            }

            def extract_info():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(video_url, download=False)

                        if not info:
                            logger.error(
                                "yt-dlp returned no information for Rumble video"
                            )
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
                                # Sort by audio quality
                                audio_formats.sort(
                                    key=lambda f: f.get("abr", 0) or f.get("tbr", 0),
                                    reverse=True,
                                )
                                stream_url = audio_formats[0]["url"]
                                logger.debug(
                                    f"Selected Rumble audio format: {audio_formats[0].get('format_id')} (bitrate: {audio_formats[0].get('abr', 'unknown')})"
                                )
                            else:
                                # Fallback to best available format
                                valid_formats = [f for f in formats if f.get("url")]
                                if valid_formats:
                                    # Sort by quality
                                    valid_formats.sort(
                                        key=lambda f: f.get("tbr", 0)
                                        or f.get("abr", 0),
                                        reverse=True,
                                    )
                                    stream_url = valid_formats[0]["url"]
                                    logger.debug(
                                        f"Selected Rumble fallback format: {valid_formats[0].get('format_id')}"
                                    )

                        if not stream_url:
                            logger.error(
                                "No valid stream URL found in Rumble extraction result"
                            )
                            return None, "No stream URL found"

                        logger.debug(
                            f"Extracted Rumble stream URL: {stream_url[:100]}..."
                        )
                        return stream_url, None

                except yt_dlp.DownloadError as e:
                    error_msg = str(e)
                    logger.error(f"yt-dlp download error for Rumble: {error_msg}")

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
                    logger.error(f"yt-dlp extraction error for Rumble: {e}")
                    return None, f"Extraction error: {str(e)}"

            # Run yt-dlp in thread to avoid blocking with timeout
            loop = asyncio.get_event_loop()
            try:
                stream_url, error = await asyncio.wait_for(
                    loop.run_in_executor(None, extract_info),
                    timeout=45.0,  # 45 second timeout for Rumble extraction
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Rumble stream extraction timed out for video: {video_id}"
                )
                raise PlatformNotAvailableError(
                    "Rumble stream extraction timed out", platform="Rumble"
                )

            # Handle errors
            if error:
                logger.error(
                    f"Rumble stream extraction failed for video {video_id}: {error}"
                )
                raise PlatformAPIError(
                    f"Failed to extract stream: {error}", platform="Rumble"
                )

            if stream_url:
                logger.info(
                    f"Successfully extracted Rumble stream URL for {video_id}: {stream_url[:100]}..."
                )
                # Cache the stream URL
                await self.cache_stream_url(video_id, stream_url)
                return stream_url
            else:
                logger.error(f"No stream URL extracted for Rumble video {video_id}")
                raise PlatformAPIError(
                    "No stream URL could be extracted", platform="Rumble"
                )

        except PlatformAPIError:
            # Re-raise platform errors
            raise
        except Exception as e:
            logger.error(f"Failed to get stream URL for Rumble video {video_id}: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")
            raise PlatformAPIError(
                f"Stream extraction failed: {str(e)}",
                platform="Rumble",
                original_error=e,
            )
