import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import aiohttp

from src.platforms.base import VideoPlatform
from src.platforms.errors import (
    PlatformNotAvailableError,
    PlatformAPIError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
    from_http_status,
)
from src.utils.network_resilience import (
    with_retry,
    with_circuit_breaker,
    PLATFORM_RETRY_CONFIG,
    PLATFORM_CIRCUIT_BREAKER_CONFIG,
    NetworkResilienceError,
    CircuitBreakerOpenError,
    NetworkTimeoutError,
    safe_aiohttp_request,
)

logger = logging.getLogger(__name__)


class OdyseePlatform(VideoPlatform):
    """Odysee/LBRY platform implementation"""

    def __init__(self, name: str, config: Dict[str, Any], cache_manager=None) -> None:
        super().__init__(name, config, cache_manager)
        self.api_url = config.get("api_url", "https://api.lbry.tv/api/v1")
        self.stream_url = config.get("stream_url", "https://api.lbry.tv")

        # URL patterns for Odysee videos
        self.url_patterns = [
            re.compile(r"https?://odysee\.com/@[^/]+:[a-f0-9]+/[^/]+:[a-f0-9]+"),
            re.compile(r"https?://lbry\.tv/@[^/]+:[a-f0-9]+/[^/]+:[a-f0-9]+"),
            re.compile(r"lbry://(@[^/]+/[^/]+)"),
        ]

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="odysee_search",
        exceptions=(PlatformAPIError, aiohttp.ClientError, asyncio.TimeoutError),
        exclude_exceptions=(PlatformRateLimitError, CircuitBreakerOpenError),
    )
    async def search_videos(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for videos on Odysee with enhanced error handling"""
        # Check cache first
        cached_results = await self.get_cached_search_results(query)
        if cached_results:
            logger.info(f"Using cached Odysee search results for: {query}")
            return cached_results

        if not self.session:
            logger.error("Session not initialized for Odysee search")
            raise PlatformNotAvailableError(
                "Odysee service not initialized", platform="Odysee"
            )

        try:
            logger.debug(f"Searching Odysee for: {query} (max_results: {max_results})")

            # Use claim_search endpoint
            url = f"{self.api_url}/claim_search"
            params = {
                "text": query,
                "page": 1,
                "page_size": min(max_results, 50),  # Limit to reasonable size
                "claim_type": ["stream"],
                "stream_types": ["video"],
                "order_by": ["trending_group", "trending_mixed"],
                "no_totals": True,
            }

            try:
                response = await safe_aiohttp_request(
                    self.session, "POST", url, json=params, timeout=15
                )

                if response.status == 429:
                    raise PlatformRateLimitError(
                        "Odysee API rate limit exceeded", platform="Odysee"
                    )
                elif response.status >= 500:
                    raise PlatformNotAvailableError(
                        f"Odysee server error ({response.status})", platform="Odysee"
                    )
                elif response.status != 200:
                    error_text = await response.text()
                    raise PlatformAPIError(
                        f"Odysee search failed: {response.status} - {error_text[:100]}...",
                        platform="Odysee",
                        status_code=response.status,
                    )

                data = await response.json()

            except NetworkTimeoutError:
                logger.warning(f"Odysee search timed out for query: {query}")
                raise PlatformNotAvailableError(
                    "Odysee search timed out - service may be slow", platform="Odysee"
                )
            except aiohttp.ClientError as e:
                logger.error(f"Odysee network error: {e}")
                raise PlatformNotAvailableError(
                    "Network error connecting to Odysee",
                    platform="Odysee",
                    original_error=e,
                )

            if not data or "items" not in data:
                logger.warning(f"Odysee returned no data for query: {query}")
                return []

            results = []
            items = data.get("items", [])

            for item in items:
                try:
                    if item.get("value_type") != "stream":
                        continue

                    value = item.get("value", {})
                    if value.get("stream_type") != "video":
                        continue

                    # Validate required fields
                    claim_id = item.get("claim_id")
                    title = value.get("title", item.get("name", ""))

                    if not claim_id or not title:
                        logger.debug(f"Skipping invalid Odysee result: {item}")
                        continue

                    # Extract video information
                    video_data = {
                        "id": claim_id,
                        "title": title,
                        "channel": item.get("signing_channel", {}).get(
                            "name", "Unknown Channel"
                        ),
                        "thumbnail": value.get("thumbnail", {}).get("url", ""),
                        "url": f"https://odysee.com/{item.get('canonical_url', '')}",
                        "platform": "odysee",
                        "description": value.get("description", ""),
                        "duration": value.get("video", {}).get("duration"),
                        "views": item.get("meta", {}).get("effective_amount", 0),
                    }
                    results.append(video_data)

                except Exception as item_error:
                    logger.warning(f"Error processing Odysee result: {item_error}")
                    continue

            logger.info(
                f"Odysee search returned {len(results)} valid results for: {query}"
            )
            # Cache the results
            await self.cache_search_results(query, results)
            return results

        except NetworkResilienceError:
            # Re-raise network resilience errors as-is
            raise
        except PlatformRateLimitError:
            # Re-raise rate limit errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching Odysee: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")

            # Categorize error
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                raise PlatformNotAvailableError(
                    "Odysee service is responding slowly or is unavailable",
                    platform="Odysee",
                    original_error=e,
                )
            else:
                raise PlatformAPIError(
                    f"Odysee search failed: {str(e)[:100]}...",
                    platform="Odysee",
                    original_error=e,
                )

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="odysee_metadata",
        exceptions=(PlatformAPIError, aiohttp.ClientError, asyncio.TimeoutError),
        exclude_exceptions=(PlatformRateLimitError, CircuitBreakerOpenError),
    )
    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific video with enhanced error handling"""
        # Check cache first
        cached_metadata = await self.get_cached_video_metadata(video_id)
        if cached_metadata:
            logger.info(f"Using cached video metadata for Odysee video: {video_id}")
            return cached_metadata

        if not self.session:
            logger.warning("Session not initialized for Odysee video details")
            # Return basic info as fallback
            basic_info = {
                "id": video_id,
                "title": f"Odysee Video {video_id}",
                "channel": "Unknown",
                "thumbnail": "",
                "url": f"https://odysee.com/$/download/{video_id}",
                "platform": "odysee",
                "description": "Video details unavailable - session not initialized",
            }
            # Cache basic info (short TTL)
            await self.cache_video_metadata(video_id, basic_info, ttl=300)  # 5 minutes
            return basic_info

        try:
            logger.debug(f"Getting details for Odysee video: {video_id}")

            # Validate video ID (should be a hex string)
            if not video_id or not re.match(r"^[a-f0-9]+$", video_id, re.IGNORECASE):
                logger.warning(f"Invalid Odysee claim ID format: {video_id}")
                return None

            url = f"{self.api_url}/claim_search"
            params = {
                "claim_id": video_id,
                "page": 1,
                "page_size": 1,
            }

            try:
                response = await safe_aiohttp_request(
                    self.session, "POST", url, json=params, timeout=10
                )

                if response.status == 429:
                    raise PlatformRateLimitError(
                        "Odysee API rate limit exceeded", platform="Odysee"
                    )
                elif response.status >= 500:
                    raise PlatformNotAvailableError(
                        f"Odysee server error ({response.status})", platform="Odysee"
                    )
                elif response.status != 200:
                    error_text = await response.text()
                    logger.warning(
                        f"Odysee video details failed: {response.status} - {error_text[:100]}..."
                    )
                    # Return basic info as fallback instead of failing
                    return {
                        "id": video_id,
                        "title": f"Odysee Video {video_id}",
                        "channel": "Unknown",
                        "thumbnail": "",
                        "url": f"https://odysee.com/$/download/{video_id}",
                        "platform": "odysee",
                        "description": f"Video details unavailable: HTTP {response.status}",
                    }

                data = await response.json()

            except NetworkTimeoutError:
                logger.warning(f"Odysee video details timed out for: {video_id}")
                # Return basic info as fallback
                return {
                    "id": video_id,
                    "title": f"Odysee Video {video_id}",
                    "channel": "Unknown",
                    "thumbnail": "",
                    "url": f"https://odysee.com/$/download/{video_id}",
                    "platform": "odysee",
                    "description": "Video details unavailable - request timed out",
                }
            except aiohttp.ClientError as e:
                logger.error(f"Odysee network error getting video details: {e}")
                # Return basic info as fallback
                return {
                    "id": video_id,
                    "title": f"Odysee Video {video_id}",
                    "channel": "Unknown",
                    "thumbnail": "",
                    "url": f"https://odysee.com/$/download/{video_id}",
                    "platform": "odysee",
                    "description": f"Video details unavailable: {str(e)[:50]}...",
                }

            if not data or "items" not in data:
                logger.warning(f"No data returned for Odysee video: {video_id}")
                return None

            items = data.get("items", [])
            if not items:
                logger.info(f"No video found for Odysee claim ID: {video_id}")
                return None

            item = items[0]
            value = item.get("value", {})

            return {
                "id": item.get("claim_id"),
                "title": value.get(
                    "title", item.get("name", f"Odysee Video {video_id}")
                ),
                "channel": item.get("signing_channel", {}).get(
                    "name", "Unknown Channel"
                ),
                "thumbnail": value.get("thumbnail", {}).get("url", ""),
                "url": f"https://odysee.com/{item.get('canonical_url', '')}",
                "platform": "odysee",
                "description": value.get("description", ""),
                "duration": value.get("video", {}).get("duration"),
                "views": item.get("meta", {}).get("effective_amount", 0),
            }

        except NetworkResilienceError:
            # Re-raise network resilience errors
            raise
        except PlatformRateLimitError:
            # Re-raise rate limit errors
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting Odysee video details for {video_id}: {e}"
            )
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")

            # Return basic info as graceful degradation
            return {
                "id": video_id,
                "title": f"Odysee Video {video_id}",
                "channel": "Unknown",
                "thumbnail": "",
                "url": f"https://odysee.com/$/download/{video_id}",
                "platform": "odysee",
                "description": f"Video details unavailable: {str(e)[:50]}...",
            }

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
        return any(pattern.match(url) for pattern in self.url_patterns) or any(
            domain in url for domain in ["odysee.com", "lbry.tv"]
        )

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="odysee_stream_url",
        exceptions=(Exception,),
        exclude_exceptions=(
            PlatformAPIError,
            CircuitBreakerOpenError,
            NetworkResilienceError,
        ),
    )
    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get the stream URL for a video with enhanced error handling"""
        if not self.session:
            logger.error("Session not initialized for Odysee stream URL")
            raise PlatformNotAvailableError(
                "Odysee service not initialized", platform="Odysee"
            )

        # Validate video ID format
        if not video_id or not re.match(r"^[a-f0-9]+$", video_id, re.IGNORECASE):
            logger.error(f"Invalid Odysee claim ID format: {video_id}")
            raise PlatformAPIError(
                f"Invalid Odysee claim ID: {video_id}", platform="Odysee"
            )

        try:
            logger.info(f"Getting stream URL for Odysee video: {video_id}")

            # First, get the claim details to verify video exists
            video_details = await self.get_video_details(video_id)
            if not video_details:
                logger.warning(f"Video details not found for Odysee claim: {video_id}")
                raise PlatformAPIError(
                    "Video not found or unavailable", platform="Odysee"
                )

            # Try multiple stream URL formats for Odysee
            stream_urls = [
                f"{self.stream_url}/content/claims/{video_id}/stream",
                f"{self.stream_url}/api/v1/proxy?m=get&uri=lbry://{video_id}",
                f"https://api.lbry.tv/content/claims/{video_id}/stream",
            ]

            for stream_url in stream_urls:
                try:
                    # Verify the stream URL is accessible with timeout
                    response = await safe_aiohttp_request(
                        self.session, "HEAD", stream_url, timeout=10
                    )

                    if response.status == 200:
                        logger.info(
                            f"Successfully found Odysee stream URL: {stream_url[:100]}..."
                        )
                        return stream_url
                    elif response.status == 404:
                        logger.debug(f"Stream URL not found: {stream_url}")
                        continue
                    else:
                        logger.warning(
                            f"Stream URL returned status {response.status}: {stream_url}"
                        )
                        continue

                except NetworkTimeoutError:
                    logger.warning(f"Timeout checking stream URL: {stream_url}")
                    continue
                except aiohttp.ClientError as e:
                    logger.warning(
                        f"Network error checking stream URL {stream_url}: {e}"
                    )
                    continue
                except Exception as e:
                    logger.warning(f"Error checking stream URL {stream_url}: {e}")
                    continue

            # If no stream URLs work, try yt-dlp as fallback
            logger.info(
                f"Direct stream URLs failed, trying yt-dlp for Odysee video: {video_id}"
            )
            return await self._get_stream_url_with_ytdlp(video_id, video_details)

        except PlatformAPIError:
            # Re-raise platform errors
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting Odysee stream URL for {video_id}: {e}"
            )
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")
            raise PlatformAPIError(
                f"Stream extraction failed: {str(e)}",
                platform="Odysee",
                original_error=e,
            )

    async def _get_stream_url_with_ytdlp(
        self, video_id: str, video_details: Dict[str, Any]
    ) -> Optional[str]:
        """Fallback method using yt-dlp for stream extraction"""
        try:
            import yt_dlp
            import asyncio

            video_url = video_details.get(
                "url", f"https://odysee.com/$/download/{video_id}"
            )
            logger.debug(f"Trying yt-dlp for Odysee URL: {video_url}")

            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best[height<=720]",
                "quiet": True,
                "no_warnings": False,
                "noplaylist": True,
                "extract_flat": False,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "socket_timeout": 30,
                "retries": 2,
            }

            def extract_info():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(video_url, download=False)

                        if not info:
                            return None, "No video information found"

                        # Extract stream URL
                        stream_url = None
                        if "url" in info:
                            stream_url = info["url"]
                        elif "formats" in info and info["formats"]:
                            formats = info["formats"]
                            # Prefer audio-only formats
                            audio_formats = [
                                f
                                for f in formats
                                if f.get("vcodec") == "none" and f.get("url")
                            ]
                            if audio_formats:
                                audio_formats.sort(
                                    key=lambda f: f.get("abr", 0) or f.get("tbr", 0),
                                    reverse=True,
                                )
                                stream_url = audio_formats[0]["url"]
                            else:
                                valid_formats = [f for f in formats if f.get("url")]
                                if valid_formats:
                                    stream_url = valid_formats[0]["url"]

                        return stream_url, None

                except yt_dlp.DownloadError as e:
                    error_msg = str(e)
                    if "private" in error_msg.lower():
                        return None, "Video is private"
                    elif "unavailable" in error_msg.lower():
                        return None, "Video is unavailable"
                    else:
                        return None, f"Download error: {error_msg}"
                except Exception as e:
                    return None, f"Extraction error: {str(e)}"

            # Run yt-dlp in thread with timeout
            loop = asyncio.get_event_loop()
            try:
                stream_url, error = await asyncio.wait_for(
                    loop.run_in_executor(None, extract_info), timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"yt-dlp extraction timed out for Odysee video: {video_id}"
                )
                return None

            if error:
                logger.warning(
                    f"yt-dlp extraction failed for Odysee video {video_id}: {error}"
                )
                return None

            if stream_url:
                logger.info(
                    f"Successfully extracted Odysee stream URL via yt-dlp: {stream_url[:100]}..."
                )
                return stream_url

            return None

        except ImportError:
            logger.warning("yt-dlp not available for Odysee stream extraction")
            return None
        except Exception as e:
            logger.error(f"yt-dlp fallback failed for Odysee video {video_id}: {e}")
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
