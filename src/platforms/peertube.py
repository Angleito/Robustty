import asyncio
import logging
import re
import ssl
from datetime import datetime, timedelta
from typing import Any, Coroutine, Dict, List, Optional, Union, Set

import aiohttp

from src.platforms.base import VideoPlatform
from src.platforms.errors import (
    PlatformNotAvailableError,
    PlatformAPIError,
    PlatformRateLimitError,
    from_http_status,
)
from src.platforms.peertube_types import (
    InstanceURL,
    PeerTubeError,
    SearchData,
    SearchQuery,
    VideoFile,
    VideoID,
    VideoInfo,
)
from src.utils.network_resilience import (
    with_retry,
    with_circuit_breaker,
    PLATFORM_RETRY_CONFIG,
    PLATFORM_CIRCUIT_BREAKER_CONFIG,
    NetworkResilienceError,
    CircuitBreakerOpenError,
    NetworkTimeoutError,
    MaxRetriesExceededError,
    safe_aiohttp_request,
    get_resilience_manager,
    CircuitBreakerConfig,
    RetryConfig,
)
from src.utils.network_routing import get_http_client, ServiceType

logger = logging.getLogger(__name__)


# PeerTube-specific error types
class PeerTubeConnectionError(PlatformNotAvailableError):
    """Raised when connection to PeerTube instance fails"""

    pass


class PeerTubeInstanceUnavailableError(PlatformNotAvailableError):
    """Raised when a specific PeerTube instance is unavailable"""

    def __init__(self, message: str, instance: str, **kwargs):
        super().__init__(message, **kwargs)
        self.instance = instance


class PeerTubeDNSError(PeerTubeConnectionError):
    """Raised when DNS resolution fails for PeerTube instance"""

    pass


class PeerTubeTimeoutError(PeerTubeConnectionError):
    """Raised when connection to PeerTube instance times out"""

    pass


# PeerTube-specific configurations
PEERTUBE_INSTANCE_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,  # Allow 3 failures before opening (was 2)
    recovery_timeout=60,  # Reduced recovery timeout (was 120)
    success_threshold=1,  # Only need 1 success to close
    timeout=15,  # Reasonable timeout for instance calls (was 20)
)

PEERTUBE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,  # Longer base delay for connection issues
    max_delay=15.0,  # Cap at 15 seconds
    exponential_base=2.0,
    jitter=True,
)


class InstanceHealthTracker:
    """Tracks health status of PeerTube instances"""

    def __init__(self):
        self.instance_health: Dict[str, Dict[str, Any]] = {}
        self.unhealthy_instances: Set[str] = set()
        self.last_health_check: Dict[str, datetime] = {}
        self.consecutive_failures: Dict[str, int] = {}

    def record_success(self, instance: str):
        """Record successful operation for instance"""
        self.consecutive_failures[instance] = 0
        self.unhealthy_instances.discard(instance)
        self.last_health_check[instance] = datetime.now()

        if instance not in self.instance_health:
            self.instance_health[instance] = {}

        self.instance_health[instance].update(
            {
                "last_success": datetime.now(),
                "status": "healthy",
                "consecutive_failures": 0,
            }
        )

    def record_failure(self, instance: str, error_type: str):
        """Record failed operation for instance"""
        self.consecutive_failures[instance] = (
            self.consecutive_failures.get(instance, 0) + 1
        )
        self.last_health_check[instance] = datetime.now()

        if instance not in self.instance_health:
            self.instance_health[instance] = {}

        self.instance_health[instance].update(
            {
                "last_failure": datetime.now(),
                "last_error_type": error_type,
                "status": (
                    "unhealthy"
                    if self.consecutive_failures[instance] >= 3
                    else "degraded"
                ),
                "consecutive_failures": self.consecutive_failures[instance],
            }
        )

        # Mark as unhealthy after 3 consecutive failures
        if self.consecutive_failures[instance] >= 3:
            self.unhealthy_instances.add(instance)

    def is_instance_healthy(self, instance: str) -> bool:
        """Check if instance is considered healthy"""
        if instance in self.unhealthy_instances:
            # Check if enough time has passed to retry
            last_check = self.last_health_check.get(instance)
            if last_check and datetime.now() - last_check < timedelta(minutes=5):
                return False
            # Remove from unhealthy set to allow retry
            self.unhealthy_instances.discard(instance)
        return True

    def get_healthy_instances(self, instances: List[str]) -> List[str]:
        """Get list of healthy instances"""
        return [
            instance for instance in instances if self.is_instance_healthy(instance)
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get health status of all instances"""
        return {
            "instance_health": self.instance_health,
            "unhealthy_instances": list(self.unhealthy_instances),
            "total_instances": len(self.instance_health),
            "healthy_instances": len(self.instance_health)
            - len(self.unhealthy_instances),
        }


class PeerTubePlatform(VideoPlatform):
    """PeerTube platform implementation - federated video platform with enhanced resilience"""

    def __init__(self, name: str, config: Dict[str, Any], cache_manager=None) -> None:
        super().__init__(name, config, cache_manager)
        self.instances: List[InstanceURL] = config.get("instances", [])
        self.max_results_per_instance: int = config.get("max_results_per_instance", 5)

        # Instance health tracking
        self.health_tracker = InstanceHealthTracker()

        # Circuit breaker configuration for individual instances
        self.instance_circuit_breaker_config = PEERTUBE_INSTANCE_CIRCUIT_BREAKER_CONFIG
        self.retry_config = PEERTUBE_RETRY_CONFIG

        # URL pattern for PeerTube videos
        self.url_pattern: re.Pattern[str] = re.compile(
            r"https?://([^/]+)/videos/watch/([a-f0-9-]+)"
        )
        
        # Initialize network-aware HTTP client
        self._network_client = None
        self._service_type = ServiceType.PEERTUBE

        logger.info(
            f"PeerTube platform initialized with {len(self.instances)} instances"
        )

    async def initialize(self):
        """Initialize platform resources with custom SSL context and network routing for PeerTube instances"""
        # Create SSL context that accepts self-signed certificates
        # Many PeerTube instances use self-signed certificates which would otherwise cause connection failures
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE  # Disable certificate verification for self-signed certs
        
        # Create timeout config
        timeout = aiohttp.ClientTimeout(
            total=self.config.get('http_timeout', 30),
            connect=self.config.get('http_connect_timeout', 10),
            sock_connect=self.config.get('sock_connect_timeout', 10),
            sock_read=self.config.get('sock_read_timeout', 10)
        )
        
        # Create connector with SSL context
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit_per_host=self.config.get('connections_per_host', 10),
            ttl_dns_cache=self.config.get('dns_cache_ttl', 300),
            enable_cleanup_closed=True,
            force_close=True
        )
        
        # Initialize network-aware HTTP client
        self._network_client = get_http_client()
        await self._network_client.initialize()
        
        # Create session with custom settings
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': 'Robustty-Bot/1.0 (Discord Music Bot)'
            }
        )
        self._session_closed = False
        logger.info(f"Initialized PeerTube platform with custom SSL context, network routing, and {len(self.instances)} instances")

    async def search_videos(
        self, query: SearchQuery, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search across all configured PeerTube instances with enhanced resilience and error handling"""
        # Check cache first
        cached_results = await self.get_cached_search_results(query)
        if cached_results:
            logger.info(f"Using cached PeerTube search results for: {query}")
            return cached_results

        if not self.instances:
            logger.warning("No PeerTube instances configured")
            return []

        if not self._network_client:
            logger.error("Network client not initialized for PeerTube search")
            raise PlatformNotAvailableError(
                "PeerTube service not initialized", platform="PeerTube"
            )

        # Get healthy instances only
        healthy_instances = self.health_tracker.get_healthy_instances(self.instances)

        if not healthy_instances:
            logger.warning("No healthy PeerTube instances available")
            # If all instances are marked unhealthy, try a subset anyway
            healthy_instances = self.instances[: min(2, len(self.instances))]
            logger.info(
                f"Attempting search with {len(healthy_instances)} potentially unhealthy instances"
            )

        all_results: List[Dict[str, Any]] = []
        tasks: List[Coroutine[Any, Any, Union[List[Dict[str, Any]], PeerTubeError]]] = (
            []
        )

        # Calculate results per instance
        results_per_instance: int = min(
            max_results // len(healthy_instances) + 1, self.max_results_per_instance
        )

        logger.info(
            f"Searching {len(healthy_instances)}/{len(self.instances)} PeerTube instances for: {query}"
        )

        try:
            # Search each healthy instance with small stagger to avoid thundering herd
            for i, instance in enumerate(healthy_instances):
                task = self._search_instance_with_resilience(
                    instance, query, results_per_instance
                )
                tasks.append(task)
                # Add small delay between instance requests (50ms)
                if i < len(healthy_instances) - 1:
                    await asyncio.sleep(0.05)

            # Gather results from all instances with timeout
            # Use longer timeout for instances that might be recovering
            search_timeout = min(45.0, len(healthy_instances) * 15.0)
            instance_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=search_timeout
            )

            successful_searches = 0
            failed_instances = []

            for i, results in enumerate(instance_results):
                instance = healthy_instances[i]

                if isinstance(results, Exception):
                    logger.error(
                        f"Error searching PeerTube instance {instance}: {results}"
                    )
                    failed_instances.append(instance)

                    # Classify error for health tracking
                    error_type = self._classify_error(results)
                    self.health_tracker.record_failure(instance, error_type)

                elif isinstance(results, list):
                    all_results.extend(results)
                    successful_searches += 1
                    self.health_tracker.record_success(instance)

            # Log instance health status
            if failed_instances:
                logger.warning(f"Failed instances: {failed_instances}")

            if successful_searches == 0:
                logger.warning("No PeerTube instances responded successfully")

                # Check if this is a widespread network issue
                if len(failed_instances) == len(self.instances):
                    raise PlatformNotAvailableError(
                        f"All {len(self.instances)} PeerTube instances failed to respond. "
                        "This may indicate a network connectivity issue.",
                        platform="PeerTube",
                    )
                else:
                    # Some instances might still be healthy, but search failed
                    raise PlatformNotAvailableError(
                        f"PeerTube search failed: {successful_searches}/{len(healthy_instances)} instances responded",
                        platform="PeerTube",
                    )

            # Sort by relevance/views and limit results
            all_results.sort(key=lambda x: x.get("views", 0), reverse=True)
            final_results = all_results[:max_results]

            logger.info(
                f"PeerTube search returned {len(final_results)} results from {successful_searches}/{len(healthy_instances)} healthy instances "
                f"(out of {len(self.instances)} total configured)"
            )

            # Cache the results
            await self.cache_search_results(query, final_results)
            return final_results

        except asyncio.TimeoutError:
            logger.warning(
                f"PeerTube search timed out for query: {query} (timeout: {search_timeout}s)"
            )
            # Mark all instances as potentially slow
            for instance in healthy_instances:
                self.health_tracker.record_failure(instance, "timeout")

            raise PlatformNotAvailableError(
                f"PeerTube search timed out after {search_timeout}s - instances may be slow or unreachable",
                platform="PeerTube",
            )
        except NetworkResilienceError:
            # Re-raise network resilience errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching PeerTube instances: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")

            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                raise PlatformNotAvailableError(
                    "PeerTube instances are responding slowly or are unavailable",
                    platform="PeerTube",
                    original_error=e,
                )
            else:
                raise PlatformAPIError(
                    f"PeerTube search failed: {str(e)[:100]}...",
                    platform="PeerTube",
                    original_error=e,
                )

    async def _search_instance_with_resilience(
        self, instance_url: InstanceURL, query: SearchQuery, max_results: int
    ) -> List[Dict[str, Any]]:
        """Search a specific PeerTube instance with enhanced resilience and per-instance circuit breaker"""

        # Get per-instance circuit breaker
        resilience_manager = get_resilience_manager()
        instance_cb_name = (
            f"peertube_instance_{instance_url.replace('://', '_').replace('/', '_')}"
        )
        circuit_breaker = resilience_manager.get_circuit_breaker(
            instance_cb_name, self.instance_circuit_breaker_config
        )

        # Check if circuit breaker is open
        if not circuit_breaker.is_available:
            logger.warning(
                f"Circuit breaker for {instance_url} is OPEN, skipping instance"
            )
            return []

        # Use retry logic with circuit breaker
        try:
            return await self._retry_instance_search(
                circuit_breaker, instance_url, query, max_results
            )
        except CircuitBreakerOpenError:
            logger.warning(f"Circuit breaker opened for {instance_url} during search")
            return []
        except MaxRetriesExceededError as e:
            logger.error(f"Max retries exceeded for {instance_url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error searching {instance_url}: {e}")
            return []

    async def _retry_instance_search(
        self,
        circuit_breaker,
        instance_url: InstanceURL,
        query: SearchQuery,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """Retry logic for searching a specific instance"""

        last_exception = None

        for attempt in range(1, self.retry_config.max_attempts + 1):
            try:
                # Use circuit breaker to execute the search
                result = await circuit_breaker.call(
                    self._search_instance_direct, instance_url, query, max_results
                )

                if attempt > 1:
                    logger.info(
                        f"Instance {instance_url} search succeeded on attempt {attempt}"
                    )

                return result

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                NetworkTimeoutError,
            ) as e:
                last_exception = e

                if attempt == self.retry_config.max_attempts:
                    logger.error(
                        f"Instance {instance_url} failed after {self.retry_config.max_attempts} attempts: {e}"
                    )
                    raise MaxRetriesExceededError(
                        f"PeerTube instance {instance_url} failed after {self.retry_config.max_attempts} attempts"
                    ) from e

                # Calculate exponential backoff delay
                delay = min(
                    self.retry_config.base_delay
                    * (self.retry_config.exponential_base ** (attempt - 1)),
                    self.retry_config.max_delay,
                )

                if self.retry_config.jitter:
                    import random

                    jitter_range = delay * 0.25
                    delay += random.uniform(-jitter_range, jitter_range)

                delay = max(0, delay)

                logger.warning(
                    f"Instance {instance_url} attempt {attempt} failed: {e}. Retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)

            except (PlatformRateLimitError, CircuitBreakerOpenError):
                # Don't retry these exceptions
                raise

            except Exception as e:
                logger.error(
                    f"Unexpected error on attempt {attempt} for {instance_url}: {e}"
                )
                if attempt == self.retry_config.max_attempts:
                    raise
                last_exception = e

        # This should never be reached
        if last_exception:
            raise last_exception

        return []

    async def _search_instance_direct(
        self, instance_url: InstanceURL, query: SearchQuery, max_results: int
    ) -> List[Dict[str, Any]]:
        """Direct search of a specific PeerTube instance without retry logic"""
        url: str = f"{instance_url}/api/v1/search/videos"
        params: Dict[str, Union[str, int]] = {
            "search": query,
            "count": max_results,
            "sort": "-views",  # Sort by views descending
        }

        if self._network_client is None:
            logger.error(f"Network client not initialized for {instance_url}")
            raise PlatformNotAvailableError(
                f"Network client not available for {instance_url}", platform="PeerTube"
            )

        try:
            # Use shorter timeout for individual instance calls with network routing
            async with self._network_client.get_session(self._service_type) as session:
                response = await safe_aiohttp_request(
                    session, "GET", url, params=params, timeout=12
                )

            # Read response data while connection is still active
            try:
                if response.status == 403:
                    logger.warning(
                        f"PeerTube instance {instance_url} returned 403 "
                        "Forbidden - may require authentication"
                    )
                    return []
                elif response.status == 429:
                    raise PlatformRateLimitError(
                        f"PeerTube instance {instance_url} rate limit exceeded",
                        platform="PeerTube",
                    )
                elif response.status >= 500:
                    raise PeerTubeInstanceUnavailableError(
                        f"Server error ({response.status})",
                        instance=instance_url,
                        platform="PeerTube",
                    )
                elif response.status != 200:
                    logger.warning(
                        f"PeerTube search failed for {instance_url}: {response.status}"
                    )
                    return []

                data: SearchData = await response.json()
                results: List[Dict[str, Any]] = []
            finally:
                # Ensure response is closed
                response.close()

            for video in data.get("data", []):
                try:
                    channel_name: str = "Unknown"
                    channel = video.get("channel")
                    if channel:
                        channel_name = channel.get("displayName", "Unknown")

                    # Validate required fields
                    if not video.get("uuid") or not video.get("name"):
                        logger.debug(f"Skipping invalid PeerTube result: {video}")
                        continue

                    result = {
                        "id": video["uuid"],
                        "title": video["name"],
                        "channel": channel_name,
                        "thumbnail": f"{instance_url}{video['thumbnailPath']}",
                        "url": f"{instance_url}/videos/watch/{video['uuid']}",
                        "platform": "peertube",
                        "instance": instance_url,
                        "description": video.get("description", ""),
                        "duration": video.get("duration"),
                        "views": video.get("views", 0),
                    }
                    results.append(result)

                except Exception as item_error:
                    logger.warning(
                        f"Error processing PeerTube result from {instance_url}: {item_error}"
                    )
                    continue

            logger.debug(
                f"PeerTube instance {instance_url} returned {len(results)} results"
            )
            return results

        except NetworkTimeoutError:
            logger.warning(f"PeerTube instance {instance_url} search timed out")
            raise PeerTubeTimeoutError(
                f"Instance {instance_url} timed out", platform="PeerTube"
            )
        except aiohttp.ClientConnectorError as e:
            # DNS resolution or connection errors
            error_msg = str(e).lower()
            if (
                "name or service not known" in error_msg
                or "nodename nor servname provided" in error_msg
            ):
                logger.error(f"DNS resolution failed for {instance_url}: {e}")
                raise PeerTubeDNSError(
                    f"DNS resolution failed for {instance_url}",
                    platform="PeerTube",
                    original_error=e,
                )
            elif "ssl" in error_msg or "certificate" in error_msg or "sslcertverificationerror" in error_msg:
                logger.error(f"SSL/TLS error connecting to {instance_url}: {e}")
                raise PeerTubeConnectionError(
                    f"SSL/TLS error connecting to {instance_url}. This may be due to self-signed certificates. "
                    "SSL verification has been disabled to support self-signed certificates.",
                    platform="PeerTube",
                    original_error=e,
                )
            else:
                logger.error(f"Connection error to {instance_url}: {e}")
                raise PeerTubeConnectionError(
                    f"Connection failed to {instance_url}: {str(e)[:100]}",
                    platform="PeerTube",
                    original_error=e,
                )
        except aiohttp.ClientError as e:
            logger.error(f"Network error connecting to {instance_url}: {e}")
            raise PeerTubeConnectionError(
                f"Network error connecting to PeerTube instance {instance_url}",
                platform="PeerTube",
                original_error=e,
            )

        except (NetworkResilienceError, PlatformRateLimitError):
            # Re-raise these specific errors
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error searching PeerTube instance {instance_url}: {e}"
            )

            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                raise PeerTubeTimeoutError(
                    f"Instance {instance_url} is responding slowly",
                    platform="PeerTube",
                    original_error=e,
                )
            else:
                raise PeerTubeInstanceUnavailableError(
                    f"Instance failed: {str(e)[:100]}",
                    instance=instance_url,
                    platform="PeerTube",
                    original_error=e,
                )

    async def get_video_details(self, video_id: VideoID) -> Optional[Dict[str, Any]]:
        """Get details for a PeerTube video"""
        # Check cache first
        cached_metadata = await self.get_cached_video_metadata(video_id)
        if cached_metadata:
            logger.info(f"Using cached video metadata for PeerTube video: {video_id}")
            return cached_metadata

        # Try to find which instance hosts this video
        for instance in self.instances:
            try:
                url: str = f"{instance}/api/v1/videos/{video_id}"
                if self._network_client is None:
                    logger.error("Network client not initialized")
                    continue
                    
                # Use safe_aiohttp_request for consistent SSL handling with network routing
                async with self._network_client.get_session(self._service_type) as session:
                    response = await safe_aiohttp_request(
                        session, "GET", url, timeout=12
                    )
                
                try:
                    if response.status == 200:
                        video: VideoInfo = await response.json()

                        channel_name: str = "Unknown"
                        channel = video.get("channel")
                        if channel:
                            channel_name = channel.get("displayName", "Unknown")

                        details = {
                            "id": video["uuid"],
                            "title": video["name"],
                            "channel": channel_name,
                            "thumbnail": f"{instance}{video['thumbnailPath']}",
                            "url": f"{instance}/videos/watch/{video['uuid']}",
                            "platform": "peertube",
                            "instance": instance,
                            "description": video.get("description", ""),
                            "duration": video.get("duration"),
                            "views": video.get("views", 0),
                            "likes": video.get("likes", 0),
                            "dislikes": video.get("dislikes", 0),
                            "publishedAt": video.get("publishedAt"),
                        }
                        # Cache the details
                        await self.cache_video_metadata(video_id, details)
                        return details
                    elif response.status == 404:
                        # Video not found on this instance, try next
                        continue
                finally:
                    response.close()
                    
            except aiohttp.ClientConnectorError as e:
                error_msg = str(e).lower()
                if "ssl" in error_msg or "certificate" in error_msg:
                    logger.warning(f"SSL/TLS error getting video details from {instance}: {e}")
                else:
                    logger.debug(f"Connection error to {instance}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Video {video_id} not found on {instance}: {e}")
                continue

        return None

    def extract_video_id(self, url: str) -> Optional[VideoID]:
        """Extract video ID from PeerTube URL"""
        match: Optional[re.Match[str]] = self.url_pattern.search(url)
        if match:
            return match.group(2)
        return None

    def is_platform_url(self, url: str) -> bool:
        """Check if URL is a PeerTube URL"""
        return bool(self.url_pattern.search(url))

    async def get_stream_url(self, video_id: VideoID) -> Optional[str]:
        """Get stream URL for a PeerTube video"""
        # Check cache first
        cached_stream_url = await self.get_cached_stream_url(video_id)
        if cached_stream_url:
            logger.info(f"Using cached stream URL for PeerTube video: {video_id}")
            return cached_stream_url

        # Find which instance hosts this video
        video_details = await self.get_video_details(video_id)
        if not video_details:
            return None

        instance: str = video_details["instance"]

        try:
            # Get video files
            url: str = f"{instance}/api/v1/videos/{video_id}"
            if self._network_client is None:
                logger.error("Network client not initialized")
                return None
                
            # Use safe_aiohttp_request for consistent SSL handling with network routing
            async with self._network_client.get_session(self._service_type) as session:
                response = await safe_aiohttp_request(
                    session, "GET", url, timeout=12
                )
            
            try:
                if response.status != 200:
                    logger.warning(f"Failed to get stream URL from {instance}: status {response.status}")
                    return None

                video: VideoInfo = await response.json()

                # Get best quality file
                files: List[VideoFile] = video.get("files", [])
                if not files:
                    logger.warning(f"No video files available for {video_id} on {instance}")
                    return None

                # Sort by resolution, get highest
                files.sort(
                    key=lambda x: x.get("resolution", {}).get("id", 0), reverse=True
                )
                best_file: VideoFile = files[0]
                stream_url = best_file["fileUrl"]

                # Cache the stream URL
                await self.cache_stream_url(video_id, stream_url)
                return stream_url
            finally:
                response.close()
                
        except aiohttp.ClientConnectorError as e:
            error_msg = str(e).lower()
            if "ssl" in error_msg or "certificate" in error_msg:
                logger.error(
                    f"SSL/TLS error getting stream URL from {instance}: {e}. "
                    "The instance may be using a self-signed certificate."
                )
            else:
                logger.error(f"Connection error to {instance}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Error getting stream URL for PeerTube video {video_id}: {e}"
            )
            return None

    def _classify_error(self, error: Exception) -> str:
        """Classify error type for health tracking"""
        if isinstance(
            error, (PeerTubeTimeoutError, NetworkTimeoutError, asyncio.TimeoutError)
        ):
            return "timeout"
        elif isinstance(error, PeerTubeDNSError):
            return "dns"
        elif isinstance(error, PeerTubeConnectionError):
            return "connection"
        elif isinstance(error, PlatformRateLimitError):
            return "rate_limit"
        elif isinstance(error, PeerTubeInstanceUnavailableError):
            return "instance_unavailable"
        else:
            return "unknown"

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all PeerTube instances"""
        return {
            "platform": "PeerTube",
            "total_instances": len(self.instances),
            "instance_health": self.health_tracker.get_status(),
            "circuit_breakers": self._get_circuit_breaker_status(),
        }

    def _get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get status of all instance circuit breakers"""
        resilience_manager = get_resilience_manager()
        cb_status = {}

        for instance in self.instances:
            cb_name = (
                f"peertube_instance_{instance.replace('://', '_').replace('/', '_')}"
            )
            if cb_name in resilience_manager.circuit_breakers:
                cb_status[instance] = resilience_manager.circuit_breakers[
                    cb_name
                ].get_status()

        return cb_status
