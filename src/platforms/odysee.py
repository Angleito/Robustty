import asyncio
import logging
import os
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
    CircuitBreakerConfig,
    RetryConfig,
)

logger = logging.getLogger(__name__)

def _detect_vps_environment() -> bool:
    """Detect if running in VPS environment based on various indicators"""
    vps_indicators = [
        os.getenv('VPS_MODE', '').lower() == 'true',
        os.getenv('DOCKER_CONTAINER', '').lower() == 'true', 
        os.path.exists('/.dockerenv'),
        os.getenv('CI', '').lower() == 'true',
        'vps' in os.getenv('HOSTNAME', '').lower(),
        'docker' in os.getenv('HOSTNAME', '').lower(),
    ]
    return any(vps_indicators)

# Environment detection
IS_VPS_ENVIRONMENT = _detect_vps_environment()

# VPS-optimized configurations for better resilience in variable network conditions
if IS_VPS_ENVIRONMENT:
    # More lenient configuration for VPS environments
    ODYSEE_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
        failure_threshold=8,  # Higher threshold for VPS network variability
        recovery_timeout=180,  # Longer recovery time for VPS (3 minutes)
        success_threshold=3,  # Require more successes to confirm recovery
        timeout=60,  # Longer timeout for VPS network latency
    )
    
    ODYSEE_RETRY_CONFIG = RetryConfig(
        max_attempts=5,  # More retry attempts for VPS
        base_delay=3.0,  # Longer base delay for VPS
        max_delay=45.0,  # Longer max delay for VPS
        exponential_base=1.8,  # Gentler exponential backoff
        jitter=True,
    )
else:
    # Standard configuration for local/development environments
    ODYSEE_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
        failure_threshold=5,  # Standard threshold for stable networks
        recovery_timeout=90,  # Standard recovery time
        success_threshold=2,  # Faster recovery for stable networks
        timeout=45,  # Standard timeout
    )
    
    ODYSEE_RETRY_CONFIG = RetryConfig(
        max_attempts=4,  # Standard retry attempts
        base_delay=2.0,  # Standard base delay
        max_delay=30.0,  # Standard max delay
        exponential_base=2.0,
        jitter=True,
    )

# Enhanced error classification for better handling
ODYSEE_RETRYABLE_ERRORS = (
    aiohttp.ClientConnectionError,
    aiohttp.ClientConnectorError,
    aiohttp.ServerConnectionError,
    aiohttp.ClientOSError,
    asyncio.TimeoutError,
    ConnectionResetError,
    OSError,
)

ODYSEE_NON_RETRYABLE_ERRORS = (
    PlatformRateLimitError,
    PlatformAuthenticationError,
    CircuitBreakerOpenError,
    aiohttp.ClientResponseError,  # Don't retry 4xx errors
)


class OdyseePlatform(VideoPlatform):
    """Odysee/LBRY platform implementation"""

    def __init__(self, name: str, config: Dict[str, Any], cache_manager=None) -> None:
        super().__init__(name, config, cache_manager)
        self.api_url = config.get("api_url", "https://api.lbry.tv/api/v1")
        self.stream_url = config.get("stream_url", "https://api.lbry.tv")
        
        # Environment-specific timeout configuration
        if IS_VPS_ENVIRONMENT:
            # VPS-optimized timeouts for variable network conditions
            base_api_timeout = config.get("api_timeout", 45)  # Longer for VPS
            base_stream_timeout = config.get("stream_timeout", 30)  # Longer for VPS
            base_search_timeout = config.get("search_timeout", 35)  # Longer for VPS
            
            # More generous connection pool for VPS
            self.max_connections = config.get("max_connections", 15)
            self.max_connections_per_host = config.get("max_connections_per_host", 8)
            
            logger.info(f"Odysee configured for VPS environment with extended timeouts")
        else:
            # Standard timeouts for local/development
            base_api_timeout = config.get("api_timeout", 30)
            base_stream_timeout = config.get("stream_timeout", 20) 
            base_search_timeout = config.get("search_timeout", 25)
            
            # Standard connection pool
            self.max_connections = config.get("max_connections", 10)
            self.max_connections_per_host = config.get("max_connections_per_host", 5)
            
            logger.info(f"Odysee configured for local environment with standard timeouts")
        
        self.api_timeout = base_api_timeout
        self.stream_timeout = base_stream_timeout
        self.search_timeout = base_search_timeout

        # Failure tracking for adaptive behavior
        self.consecutive_failures = 0
        self.last_success_time = None
        # Start with lower multiplier for VPS to be more conservative
        self.adaptive_timeout_multiplier = 1.2 if IS_VPS_ENVIRONMENT else 1.0

        # URL patterns for Odysee videos
        self.url_patterns = [
            re.compile(r"https?://odysee\.com/@[^/]+:[a-f0-9]+/[^/]+:[a-f0-9]+"),
            re.compile(r"https?://lbry\.tv/@[^/]+:[a-f0-9]+/[^/]+:[a-f0-9]+"),
            re.compile(r"lbry://(@[^/]+/[^/]+)"),
        ]

    @with_retry(
        retry_config=ODYSEE_RETRY_CONFIG,
        circuit_breaker_config=ODYSEE_CIRCUIT_BREAKER_CONFIG,
        service_name="odysee_search",
        exceptions=ODYSEE_RETRYABLE_ERRORS,
        exclude_exceptions=ODYSEE_NON_RETRYABLE_ERRORS,
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
                # Calculate adaptive timeout based on recent failures
                adaptive_timeout = int(
                    self.search_timeout * self.adaptive_timeout_multiplier
                )
                logger.debug(
                    f"Odysee search timeout: {adaptive_timeout}s (multiplier: {self.adaptive_timeout_multiplier:.2f})"
                )

                response = await safe_aiohttp_request(
                    self.session, "POST", url, json=params, timeout=adaptive_timeout
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

            except NetworkTimeoutError as e:
                await self._handle_network_failure("search timeout")
                logger.warning(
                    f"Odysee search timed out for query: {query} (timeout: {adaptive_timeout}s)"
                )
                raise PlatformNotAvailableError(
                    f"Odysee search timed out after {adaptive_timeout}s - service may be slow",
                    platform="Odysee",
                    original_error=e,
                )
            except aiohttp.ClientConnectionError as e:
                await self._handle_network_failure("connection error")
                logger.error(f"Odysee connection error: {e}")
                raise PlatformNotAvailableError(
                    "Connection failed to Odysee - service may be unreachable",
                    platform="Odysee",
                    original_error=e,
                )
            except aiohttp.ServerConnectionError as e:
                await self._handle_network_failure("server connection error")
                logger.error(f"Odysee server connection error: {e}")
                raise PlatformNotAvailableError(
                    "Odysee server connection failed - service may be down",
                    platform="Odysee",
                    original_error=e,
                )
            except aiohttp.ClientError as e:
                await self._handle_network_failure(f"client error: {type(e).__name__}")
                logger.error(f"Odysee network error: {e}")
                # More specific error categorization
                if "Connection closed" in str(e):
                    raise PlatformNotAvailableError(
                        "Odysee connection was closed unexpectedly - network instability",
                        platform="Odysee",
                        original_error=e,
                    )
                elif "Connection refused" in str(e):
                    raise PlatformNotAvailableError(
                        "Odysee refused connection - service may be overloaded",
                        platform="Odysee",
                        original_error=e,
                    )
                else:
                    raise PlatformNotAvailableError(
                        f"Network error connecting to Odysee: {type(e).__name__}",
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
            # Record successful operation
            await self._handle_network_success()

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
        retry_config=ODYSEE_RETRY_CONFIG,
        circuit_breaker_config=ODYSEE_CIRCUIT_BREAKER_CONFIG,
        service_name="odysee_metadata",
        exceptions=ODYSEE_RETRYABLE_ERRORS,
        exclude_exceptions=ODYSEE_NON_RETRYABLE_ERRORS,
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
                # Use adaptive timeout for metadata requests
                adaptive_timeout = int(
                    self.api_timeout * self.adaptive_timeout_multiplier
                )
                logger.debug(f"Odysee metadata timeout: {adaptive_timeout}s")

                response = await safe_aiohttp_request(
                    self.session, "POST", url, json=params, timeout=adaptive_timeout
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

            except NetworkTimeoutError as e:
                await self._handle_network_failure("metadata timeout")
                logger.warning(
                    f"Odysee video details timed out for: {video_id} (timeout: {adaptive_timeout}s)"
                )
                # Return basic info as fallback
                return {
                    "id": video_id,
                    "title": f"Odysee Video {video_id}",
                    "channel": "Unknown",
                    "thumbnail": "",
                    "url": f"https://odysee.com/$/download/{video_id}",
                    "platform": "odysee",
                    "description": f"Video details unavailable - request timed out after {adaptive_timeout}s",
                }
            except (aiohttp.ClientConnectionError, aiohttp.ServerConnectionError) as e:
                await self._handle_network_failure(
                    f"connection error: {type(e).__name__}"
                )
                logger.error(f"Odysee connection error getting video details: {e}")
                # Return basic info as fallback
                return {
                    "id": video_id,
                    "title": f"Odysee Video {video_id}",
                    "channel": "Unknown",
                    "thumbnail": "",
                    "url": f"https://odysee.com/$/download/{video_id}",
                    "platform": "odysee",
                    "description": f"Video details unavailable - connection failed: {type(e).__name__}",
                }
            except aiohttp.ClientError as e:
                await self._handle_network_failure(f"client error: {type(e).__name__}")
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
        retry_config=ODYSEE_RETRY_CONFIG,
        circuit_breaker_config=ODYSEE_CIRCUIT_BREAKER_CONFIG,
        service_name="odysee_stream_url",
        exceptions=ODYSEE_RETRYABLE_ERRORS
        + (PlatformAPIError,),  # Include PlatformAPIError for stream URL retries
        exclude_exceptions=ODYSEE_NON_RETRYABLE_ERRORS,
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
                    # Verify the stream URL is accessible with adaptive timeout
                    stream_check_timeout = int(
                        self.stream_timeout * self.adaptive_timeout_multiplier
                    )
                    logger.debug(
                        f"Checking Odysee stream URL with timeout: {stream_check_timeout}s"
                    )

                    response = await safe_aiohttp_request(
                        self.session, "HEAD", stream_url, timeout=stream_check_timeout
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

                except NetworkTimeoutError as e:
                    logger.warning(
                        f"Timeout checking stream URL: {stream_url} (timeout: {stream_check_timeout}s)"
                    )
                    continue
                except (
                    aiohttp.ClientConnectionError,
                    aiohttp.ServerConnectionError,
                ) as e:
                    logger.warning(
                        f"Connection error checking stream URL {stream_url}: {e}"
                    )
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
                # Record success for adaptive timeout adjustment
                await self._handle_network_success()
                return stream_url

            return None

        except ImportError:
            logger.warning("yt-dlp not available for Odysee stream extraction")
            return None
        except Exception as e:
            logger.error(f"yt-dlp fallback failed for Odysee video {video_id}: {e}")
            return None

    async def _handle_network_success(self):
        """Handle successful network operation for adaptive behavior"""
        import time

        self.consecutive_failures = 0
        self.last_success_time = time.time()

        # Environment-specific timeout multiplier reduction
        if IS_VPS_ENVIRONMENT:
            # More conservative reduction for VPS to maintain stability
            baseline_multiplier = 1.2  # VPS baseline is higher
            if self.adaptive_timeout_multiplier > baseline_multiplier:
                self.adaptive_timeout_multiplier = max(
                    baseline_multiplier, self.adaptive_timeout_multiplier * 0.95  # Gentler reduction
                )
                logger.debug(
                    f"[VPS] Reduced Odysee timeout multiplier to {self.adaptive_timeout_multiplier:.2f} "
                    f"(baseline: {baseline_multiplier})"
                )
        else:
            # Faster reduction for local environments
            if self.adaptive_timeout_multiplier > 1.0:
                self.adaptive_timeout_multiplier = max(
                    1.0, self.adaptive_timeout_multiplier * 0.9
                )
                logger.debug(
                    f"Reduced Odysee timeout multiplier to {self.adaptive_timeout_multiplier:.2f}"
                )

    async def _handle_network_failure(self, failure_type: str):
        """Handle network failure for adaptive behavior"""
        self.consecutive_failures += 1

        # Environment-specific adaptive timeout adjustment
        if IS_VPS_ENVIRONMENT:
            # More aggressive timeout increases for VPS due to variable network conditions
            if self.consecutive_failures >= 2:
                old_multiplier = self.adaptive_timeout_multiplier
                # Increase more gradually for VPS to avoid overly long timeouts
                self.adaptive_timeout_multiplier = min(
                    4.0, self.adaptive_timeout_multiplier * 1.15  # Gentler increase
                )
                if old_multiplier != self.adaptive_timeout_multiplier:
                    logger.info(
                        f"[VPS] Increased Odysee timeout multiplier to {self.adaptive_timeout_multiplier:.2f} "
                        f"after {self.consecutive_failures} consecutive failures ({failure_type})"
                    )
        else:
            # Standard timeout adjustment for local environments
            if self.consecutive_failures >= 2:
                old_multiplier = self.adaptive_timeout_multiplier
                self.adaptive_timeout_multiplier = min(
                    3.0, self.adaptive_timeout_multiplier * 1.2
                )
                if old_multiplier != self.adaptive_timeout_multiplier:
                    logger.info(
                        f"Increased Odysee timeout multiplier to {self.adaptive_timeout_multiplier:.2f} "
                        f"after {self.consecutive_failures} consecutive failures ({failure_type})"
                    )

    async def _configure_optimized_session(self):
        """Configure aiohttp session with Odysee-specific optimizations"""
        if self.session and not self.session.closed:
            return

        # Environment-specific connector configuration
        if IS_VPS_ENVIRONMENT:
            # VPS-optimized connector settings
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections_per_host,
                ttl_dns_cache=600,  # Cache DNS longer for VPS (10 minutes)
                use_dns_cache=True,
                keepalive_timeout=60,  # Keep connections alive longer for VPS
                enable_cleanup_closed=True,
                force_close=False,  # Reuse connections aggressively
                resolver=aiohttp.AsyncResolver(nameservers=['8.8.8.8', '1.1.1.1']),  # Use reliable DNS
            )
            
            # More generous timeouts for VPS
            timeout = aiohttp.ClientTimeout(
                total=None,  # No total timeout (handled per request)
                connect=20,  # Longer connection timeout for VPS
                sock_read=45,  # Longer socket read timeout for VPS
            )
            
            logger.debug("Configured VPS-optimized aiohttp session for Odysee")
        else:
            # Standard connector for local development
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections_per_host,
                ttl_dns_cache=300,  # Cache DNS for 5 minutes
                use_dns_cache=True,
                keepalive_timeout=30,  # Standard keepalive
                enable_cleanup_closed=True,
                force_close=False,  # Reuse connections
            )
            
            # Standard timeout configuration
            timeout = aiohttp.ClientTimeout(
                total=None,  # No total timeout (handled per request)
                connect=10,  # Standard connection timeout
                sock_read=30,  # Standard socket read timeout
            )
            
            logger.debug("Configured standard aiohttp session for Odysee")

        # Enhanced headers for better compatibility
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; RobusttyBot/1.0; +https://github.com/robustty)",
            "Accept": "application/json, */*",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",  # Avoid stale responses
        }

        # Note: Session will be created by parent class using session manager
        self._odysee_headers = headers
        self._odysee_connector_config = {
            'limit': 20,
            'limit_per_host': 5,
            'ttl_dns_cache': 600,
            'use_dns_cache': True,
            'enable_cleanup_closed': True,
            'force_close': True,
        }

        logger.debug(
            f"Configured optimized aiohttp session for Odysee with {len(headers)} custom headers"
        )

    async def initialize(self):
        """Initialize platform resources with enhanced configuration"""
        # Store original config
        original_config = self.config.copy()
        
        # Update config with Odysee-specific settings
        self.config['http_timeout'] = self.api_timeout
        self.config['http_connect_timeout'] = 10
        self.config['connections_per_host'] = 5
        self.config['dns_cache_ttl'] = 600
        
        # Initialize parent (which will create session via manager)
        await super().initialize()
        
        # Apply custom headers to the session
        if self.session and hasattr(self, '_odysee_headers'):
            self.session.headers.update(self._odysee_headers)
        
        # Restore original config
        self.config = original_config
        
        logger.info(
            f"Initialized Odysee platform with API URL: {self.api_url}, "
            f"timeouts: search={self.search_timeout}s, api={self.api_timeout}s, stream={self.stream_timeout}s"
        )

    async def cleanup(self):
        """Cleanup platform resources with proper session handling"""
        # Use parent class cleanup which handles session manager
        await super().cleanup()
        logger.info("Cleaned up Odysee platform")

    def get_platform_status(self) -> Dict[str, Any]:
        """Get current platform status and health metrics"""
        import time

        current_time = time.time()

        return {
            "platform": "odysee",
            "environment": "vps" if IS_VPS_ENVIRONMENT else "local",
            "api_url": self.api_url,
            "consecutive_failures": self.consecutive_failures,
            "adaptive_timeout_multiplier": self.adaptive_timeout_multiplier,
            "last_success_age_seconds": (
                current_time - self.last_success_time
                if self.last_success_time
                else None
            ),
            "configured_timeouts": {
                "search": self.search_timeout,
                "api": self.api_timeout,
                "stream": self.stream_timeout,
            },
            "current_adaptive_timeouts": {
                "search": int(self.search_timeout * self.adaptive_timeout_multiplier),
                "api": int(self.api_timeout * self.adaptive_timeout_multiplier),
                "stream": int(self.stream_timeout * self.adaptive_timeout_multiplier),
            },
            "circuit_breaker_config": {
                "failure_threshold": ODYSEE_CIRCUIT_BREAKER_CONFIG.failure_threshold,
                "recovery_timeout": ODYSEE_CIRCUIT_BREAKER_CONFIG.recovery_timeout,
                "success_threshold": ODYSEE_CIRCUIT_BREAKER_CONFIG.success_threshold,
                "timeout": ODYSEE_CIRCUIT_BREAKER_CONFIG.timeout,
            },
            "retry_config": {
                "max_attempts": ODYSEE_RETRY_CONFIG.max_attempts,
                "base_delay": ODYSEE_RETRY_CONFIG.base_delay,
                "max_delay": ODYSEE_RETRY_CONFIG.max_delay,
            },
            "connection_pool": {
                "max_connections": self.max_connections,
                "max_connections_per_host": self.max_connections_per_host,
            },
            "session_status": (
                "active" if self.session and not self.session.closed else "inactive"
            ),
        }
