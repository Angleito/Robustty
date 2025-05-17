"""
Rumble extractor module for handling video and audio extraction from Rumble platform.

This module uses the Apify API to interact with Rumble content.
"""

import os
import json
import logging
import time
import random
import asyncio
import uuid
from functools import wraps
from typing import Optional, Dict, Any, List, Callable, TypeVar
from urllib.parse import urlparse, parse_qs

try:
    from apify_client import ApifyClient
except ImportError:
    # For testing environments where apify_client is not installed
    ApifyClient = None

from ..platforms.errors import (
    PlatformError,
    PlatformNotAvailableError,
    PlatformAPIError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
    from_http_status
)
from ..services.cache_manager import CacheManager
from ..services.metrics_collector import get_metrics_collector

logger: logging.Logger = logging.getLogger(__name__)

# Type variable for retry decorator
T = TypeVar('T')


class StructuredLogger(logging.LoggerAdapter):
    """
    Logger adapter for structured logging with contextual information.
    
    Provides consistent context fields across all log messages in the RumbleExtractor.
    """
    
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any]) -> None:
        """Initialize the structured logger adapter."""
        super().__init__(logger, extra)
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Process log messages to include structured context."""
        # Merge base extra context with any additional context
        extra = kwargs.get('extra', {})
        combined_extra = {**self.extra, **extra}
        
        # Add timing information if start_time is available
        if 'start_time' in combined_extra:
            combined_extra['duration_ms'] = int((time.time() - combined_extra['start_time']) * 1000)
            combined_extra.pop('start_time', None)
        
        kwargs['extra'] = combined_extra
        return msg, kwargs
    
    def with_context(self, **additional_context) -> 'StructuredLogger':
        """Create a new logger with additional context."""
        combined_extra = {**self.extra, **additional_context}
        return StructuredLogger(self.logger, combined_extra)
    
    def log_operation_start(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Log the start of an operation and return context for timing."""
        start_time = time.time()
        context = {
            'operation': operation,
            'start_time': start_time,
            'trace_id': str(uuid.uuid4()),
            **kwargs
        }
        
        self.info(f"Starting {operation} operation", extra=context)
        return context
    
    def log_operation_complete(self, operation: str, context: Dict[str, Any], **kwargs) -> None:
        """Log the completion of an operation with timing."""
        self.info(
            f"Completed {operation} operation",
            extra={**context, **kwargs}
        )
    
    def log_operation_error(self, operation: str, error: Exception, context: Dict[str, Any], **kwargs) -> None:
        """Log an operation error with context."""
        self.error(
            f"Failed {operation} operation: {str(error)}",
            extra={
                **context,
                'error_type': type(error).__name__,
                'error_message': str(error),
                **kwargs
            }
        )


def retry_with_exponential_backoff(max_retries: int = 3,
                                   initial_delay: float = 1.0,
                                   max_delay: float = 30.0,
                                   exponential_base: float = 2.0,
                                   jitter: bool = True) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 30.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        jitter: Whether to add random jitter to prevent thundering herd (default: True)
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            attempt = 0
            delay = initial_delay
            
            # Get logger from the instance if available
            instance_logger = getattr(args[0], 'logger', logger) if args else logger
            
            while attempt <= max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # Check if it's a retryable error
                    if not _is_retryable_error(e):
                        raise
                    
                    if attempt >= max_retries:
                        instance_logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}", 
                                            extra={'retry_attempt': attempt})
                        raise
                    
                    # Add jitter to delay if enabled
                    actual_delay = delay
                    if jitter:
                        actual_delay *= (0.5 + random.random())
                    
                    instance_logger.warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                                          f"after {actual_delay:.2f}s delay. Error: {str(e)}",
                                          extra={
                                              'retry_attempt': attempt + 1,
                                              'retry_delay': actual_delay,
                                              'error_type': type(e).__name__
                                          })
                    await asyncio.sleep(actual_delay)
                    
                    # Calculate next delay with exponential backoff
                    delay = min(delay * exponential_base, max_delay)
                    attempt += 1
            
            # This should never be reached due to the raise in the loop
            raise Exception(f"Unexpected error in retry logic for {func.__name__}")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            attempt = 0
            delay = initial_delay
            
            # Get logger from the instance if available
            instance_logger = getattr(args[0], 'logger', logger) if args else logger
            
            while attempt <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if it's a retryable error
                    if not _is_retryable_error(e):
                        raise
                    
                    if attempt >= max_retries:
                        instance_logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}",
                                            extra={'retry_attempt': attempt})
                        raise
                    
                    # Add jitter to delay if enabled
                    actual_delay = delay
                    if jitter:
                        actual_delay *= (0.5 + random.random())
                    
                    instance_logger.warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                                          f"after {actual_delay:.2f}s delay. Error: {str(e)}",
                                          extra={
                                              'retry_attempt': attempt + 1,
                                              'retry_delay': actual_delay,
                                              'error_type': type(e).__name__
                                          })
                    time.sleep(actual_delay)
                    
                    # Calculate next delay with exponential backoff
                    delay = min(delay * exponential_base, max_delay)
                    attempt += 1
            
            # This should never be reached due to the raise in the loop
            raise Exception(f"Unexpected error in retry logic for {func.__name__}")
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def _is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        error: The exception to check
    
    Returns:
        True if the error is retryable, False otherwise
    """
    # Check for Apify API errors (once the client is implemented)
    error_message = str(error).lower()
    
    # 429 Rate Limit
    if "429" in error_message or "rate limit" in error_message:
        return True
    
    # 5xx Server Errors
    if any(str(code) in error_message for code in range(500, 600)):
        return True
    
    # Connection errors - check types too
    if any(term in error_message for term in ["connection", "timeout", "network"]):
        return True
    
    # Check error types directly
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    
    # Check if it's an Apify-specific retryable error
    if hasattr(error, '__module__') and 'apify' in error.__module__:
        # Apify-specific errors that are retryable
        return True
    
    return False


class RumbleExtractor:
    """
    Extractor for Rumble video content using Apify actors.
    """
    
    api_token: Optional[str]
    client: Optional[ApifyClient]
    actor_timeout: int
    max_retries: int
    logger: StructuredLogger
    cache_manager: Optional[CacheManager]
    metrics: Any  # MetricsCollector
    
    def __init__(self, apify_api_token: Optional[str] = None, 
                 max_retries: int = 3,
                 actor_timeout: int = 60_000,
                 cache_manager: Optional[CacheManager] = None) -> None:
        """
        Initialize the Rumble extractor.
        
        Args:
            apify_api_token: Apify API token for actor calls
            max_retries: Maximum number of retries for Apify API calls (default: 3)
            actor_timeout: Timeout in milliseconds for actor calls (default: 60,000ms = 60s)
            cache_manager: Optional cache manager for reducing API calls
        """
        self.api_token = apify_api_token or os.getenv('APIFY_API_TOKEN')
        self.max_retries = max_retries
        self.actor_timeout = actor_timeout
        self.cache_manager = cache_manager
        
        # Initialize Apify client
        if self.api_token and ApifyClient:
            self.client = ApifyClient(self.api_token)
        elif self.api_token and not ApifyClient:
            logger.warning("apify_client package not installed - Rumble extraction will not work")
            self.client = None
        else:
            self.client = None
        
        # Initialize structured logger with base context
        self.logger = StructuredLogger(logger, {
            'extractor': 'rumble',
            'has_api_token': bool(self.api_token),
            'max_retries': self.max_retries,
            'actor_timeout': self.actor_timeout,
            'cache_enabled': self.cache_manager is not None
        })
        
        # Initialize metrics collector
        self.metrics = get_metrics_collector()
        
        if not self.api_token:
            self.logger.warning("APIFY_API_TOKEN not found. Rumble extraction may fail.")
        
        self.logger.info(f"Initialized RumbleExtractor")
    
    async def get_video_metadata(self, url: str) -> Dict[str, Any]:
        """
        Extract video metadata from a Rumble URL.
        
        Args:
            url: Rumble video URL
            
        Returns:
            Dictionary containing video metadata including:
            - title
            - description
            - duration
            - uploader
            - view_count
            - publish_date
            - thumbnail_url
            - available_qualities
            
        Raises:
            PlatformAPIError: If URL is invalid or extraction fails
        """
        # Create logger with URL context
        log = self.logger.with_context(video_url=url)
        
        # Start operation tracking
        video_id = self._extract_video_id(url) or 'unknown'
        context = log.log_operation_start(
            'metadata',
            video_id=video_id
        )
        
        try:
            if not self.api_token:
                raise PlatformAuthenticationError(
                    "API token is required for metadata extraction",
                    platform="Rumble"
                )
            
            if not self._validate_rumble_url(url):
                raise ValueError(f"Invalid Rumble URL: {url}")
            
            # Check cache first if available
            if self.cache_manager and video_id != 'unknown':
                cached_metadata = await self.cache_manager.get_video_metadata("rumble", video_id)
                if cached_metadata:
                    self.metrics.record_cache_hit("metadata")
                    log.info("Retrieved metadata from cache", extra={'video_id': video_id})
                    log.log_operation_complete('metadata', context, has_metadata=True, from_cache=True)
                    return cached_metadata
                else:
                    self.metrics.record_cache_miss("metadata")
            
            # Use the Rumble video extractor actor
            # Actor: junglee/rumble-video-extractor
            actor_input = {
                "urls": [url],
                "proxyConfig": {
                    "useApifyProxy": True
                }
            }
            
            # Call the Apify actor
            result = await self._make_actor_call("junglee/rumble-video-extractor", actor_input)
            
            # Extract the first video metadata from results
            if result and "items" in result and len(result["items"]) > 0:
                item = result["items"][0]
                metadata = {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "duration": item.get("duration", 0),
                    "uploader": item.get("author", {}).get("name", ""),
                    "view_count": item.get("viewCount", 0),
                    "like_count": item.get("likeCount", 0),
                    "publish_date": item.get("uploadDate", ""),
                    "thumbnail_url": item.get("thumbnail", ""),
                    "url": url,
                    "available_qualities": item.get("videoQualities", ["auto"])
                }
                
                # Cache the metadata if cache manager is available
                if self.cache_manager and video_id != 'unknown':
                    await self.cache_manager.set_video_metadata("rumble", video_id, metadata)
                    log.info("Cached metadata", extra={'video_id': video_id})
                
                log.log_operation_complete('metadata', context, has_metadata=True, from_cache=False)
                return metadata
            else:
                raise PlatformNotAvailableError(
                    f"No metadata found for video: {url}",
                    platform="Rumble"
                )
            
        except Exception as e:
            log.log_operation_error('metadata', e, context)
            raise
    
    async def download_audio(self, url: str, quality: str = 'best') -> str:
        """
        Extract audio stream URL from a Rumble video.
        
        Args:
            url: Rumble video URL
            quality: Desired audio quality (best, medium, low)
            
        Returns:
            Direct URL to audio stream or path to downloaded file
            
        Raises:
            PlatformAPIError: If URL is invalid or extraction fails
        """
        # Create logger with URL context
        log = self.logger.with_context(video_url=url, quality=quality)
        
        # Start operation tracking
        video_id = self._extract_video_id(url) or 'unknown'
        context = log.log_operation_start(
            'download',
            video_id=video_id,
            quality=quality
        )
        
        try:
            if not self.api_token:
                raise PlatformAuthenticationError(
                    "API token is required for audio extraction",
                    platform="Rumble"
                )
            
            if not self._validate_rumble_url(url):
                raise ValueError(f"Invalid Rumble URL: {url}")
            
            # Check cache first for stream URL
            if self.cache_manager and video_id != 'unknown':
                cached_stream_url = await self.cache_manager.get_stream_url("rumble", video_id, quality)
                if cached_stream_url:
                    self.metrics.record_cache_hit("stream")
                    log.info("Retrieved stream URL from cache", extra={'video_id': video_id, 'quality': quality})
                    log.log_operation_complete('download', context, has_stream=True, from_cache=True)
                    return cached_stream_url
                else:
                    self.metrics.record_cache_miss("stream")
            
            # First get metadata to get available video streams
            metadata = await self.get_video_metadata(url)
            
            # Use the video extractor actor to get stream URLs
            # We'll request the highest quality available
            actor_input = {
                "urls": [url],
                "downloadVideo": True,  # Request download URLs
                "proxyConfig": {
                    "useApifyProxy": True
                }
            }
            
            # Call the Apify actor for stream URLs
            result = await self._make_actor_call("junglee/rumble-video-extractor", actor_input)
            
            # Extract the stream URL from results
            if result and "items" in result and len(result["items"]) > 0:
                item = result["items"][0]
                
                # Get the appropriate quality stream URL
                if quality == 'best' and "videoUrl" in item:
                    stream_url = item["videoUrl"]
                elif "videoStreams" in item:
                    # Select from available streams based on quality
                    streams = item["videoStreams"]
                    if quality == 'best' and streams:
                        stream_url = streams[0].get("url", "")
                    elif quality == 'medium' and len(streams) > 1:
                        stream_url = streams[len(streams) // 2].get("url", "")
                    elif quality == 'low' and streams:
                        stream_url = streams[-1].get("url", "")
                    else:
                        stream_url = streams[0].get("url", "") if streams else ""
                else:
                    raise PlatformNotAvailableError(
                        "No stream URL found in video data",
                        platform="Rumble"
                    )
                
                if stream_url:
                    # Cache the stream URL if cache manager is available
                    if self.cache_manager and video_id != 'unknown':
                        await self.cache_manager.set_stream_url("rumble", video_id, stream_url, quality)
                        log.info("Cached stream URL", extra={'video_id': video_id, 'quality': quality})
                    
                    log.log_operation_complete('download', context, has_stream=True, from_cache=False)
                    return stream_url
                else:
                    raise PlatformNotAvailableError(
                        "Stream URL is empty",
                        platform="Rumble"
                    )
            else:
                raise PlatformNotAvailableError(
                    f"No download data found for video: {url}",
                    platform="Rumble"
                )
            
        except Exception as e:
            log.log_operation_error('download', e, context)
            raise
    
    async def search_videos(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for videos on Rumble.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of video metadata dictionaries
            
        Raises:
            PlatformAPIError: If search fails
        """
        # Create logger with query context
        log = self.logger.with_context(query=query, max_results=max_results)
        
        # Start operation tracking
        context = log.log_operation_start('search')
        
        try:
            if not self.api_token:
                raise PlatformAuthenticationError(
                    "API token is required for search operations",
                    platform="Rumble"
                )
            
            # Check cache first for search results
            if self.cache_manager:
                cached_results = await self.cache_manager.get_search_results("rumble", query)
                if cached_results and len(cached_results) >= max_results:
                    log.info("Retrieved search results from cache", extra={'query': query})
                    log.log_operation_complete('search', context, result_count=len(cached_results[:max_results]), from_cache=True)
                    return cached_results[:max_results]
            
            # Use the Rumble scraper actor for search
            # Actor: apify/rumble-scraper
            actor_input = {
                "searchQuery": query,
                "maxResults": max_results,
                "proxyConfig": {
                    "useApifyProxy": True
                }
            }
            
            # Call the Apify actor
            result = await self._make_actor_call("apify/rumble-scraper", actor_input)
            
            # Process the results
            videos = []
            if result and "items" in result:
                for item in result["items"]:
                    videos.append({
                        "id": item.get("id", ""),
                        "title": item.get("title", ""),
                        "description": item.get("description", ""),
                        "duration": item.get("duration", 0),
                        "uploader": item.get("creator", ""),
                        "view_count": item.get("viewsCount", 0),
                        "publish_date": item.get("publishedAt", ""),
                        "thumbnail_url": item.get("thumbnail", ""),
                        "url": item.get("url", "")
                    })
            
            # Cache the search results if cache manager is available
            if self.cache_manager and videos:
                await self.cache_manager.set_search_results("rumble", query, videos)
                log.info("Cached search results", extra={'query': query, 'count': len(videos)})
            
            log.log_operation_complete('search', context, result_count=len(videos), from_cache=False)
            return videos
            
        except Exception as e:
            log.log_operation_error('search', e, context)
            raise
    
    def validate_url(self, url: str) -> bool:
        """
        Validate if the provided URL is a valid Rumble video URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid Rumble URL, False otherwise
        """
        if not url or not isinstance(url, str):
            return False
            
        try:
            # Basic validation - must be a string with content
            url = url.strip()
            if not url:
                return False
                
            # Check for malformed patterns
            if "\n" in url or "//" in url.replace("://", ""):
                return False
                
            # URL encode check
            if "%20" in url or " " in url:
                return False
            
            parsed = urlparse(url)
            
            # Check protocol
            if parsed.scheme and parsed.scheme not in ['http', 'https']:
                return False
            
            # Check if it's a proper URL structure
            if not parsed.netloc and not parsed.path:
                return False
            
            # Allow both with and without protocol
            if parsed.netloc:
                if parsed.netloc not in ['rumble.com', 'www.rumble.com']:
                    return False
            elif parsed.path:
                # Handle case where URL is without protocol
                path_parts = parsed.path.split('/')
                if path_parts[0] not in ['rumble.com', 'www.rumble.com']:
                    return False
            
            # Check for video pattern
            full_path = parsed.path if parsed.netloc else '/' + '/'.join(parsed.path.split('/')[1:])
            return '/v' in full_path and full_path.startswith('/v')
        except Exception:
            return False
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from a Rumble URL.
        
        Args:
            url: Rumble video URL
            
        Returns:
            Video ID if found, None otherwise
        """
        try:
            if not self.validate_url(url):
                return None
                
            parsed = urlparse(url)
            
            # Handle both with and without protocol
            if parsed.netloc:
                path = parsed.path
            else:
                # URL without protocol
                path_parts = parsed.path.split('/')
                path = '/' + '/'.join(path_parts[1:])
            
            # Extract video ID from path
            # Rumble URLs typically look like: https://rumble.com/vXXXXX-title.html
            path = path.strip('/')
            if path.startswith('v'):
                # Extract ID up to first dash or dot
                video_id = path.split('-')[0].split('.')[0]
                return video_id
            
            return None
        except Exception:
            return None
    
    def _validate_rumble_url(self, url: str) -> bool:
        """
        Validate if the provided URL is a valid Rumble video URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid Rumble URL, False otherwise
        """
        return self.validate_url(url)
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from a Rumble URL.
        
        Args:
            url: Rumble video URL
            
        Returns:
            Video ID if found, None otherwise
        """
        return self.extract_video_id(url)
    
    @retry_with_exponential_backoff()
    async def _make_actor_call(self, actor_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a call to an Apify actor with timeout and cancellation handling.
        
        Args:
            actor_id: Apify actor ID (e.g., 'junglee/rumble-video-extractor')
            input_data: Input data for the actor
            
        Returns:
            Actor response data
            
        Raises:
            asyncio.TimeoutError: If actor call times out
            asyncio.CancelledError: If actor call is cancelled
            Exception: If actor call fails
        """
        # Create logger context for the actor call
        log = self.logger.with_context(
            actor_id=actor_id,
            input_size=len(str(input_data))
        )
        
        # Start operation tracking
        context = log.log_operation_start('actor_call')
        
        try:
            # Convert milliseconds to seconds for asyncio
            timeout_seconds = self.actor_timeout / 1000
            
            # Create a task for the actor call
            actor_task = self._call_apify_actor(actor_id, input_data)
            
            # Wrap the call with timeout
            result = await asyncio.wait_for(
                actor_task,
                timeout=timeout_seconds
            )
            
            log.log_operation_complete(
                'actor_call',
                context,
                result_size=len(str(result))
            )
            return result
            
        except asyncio.TimeoutError:
            raise PlatformNotAvailableError(
                f"Request timed out after {self.actor_timeout}ms",
                platform="Rumble"
            )
            
        except asyncio.CancelledError:
            log.warning("Actor call was cancelled", extra=context)
            raise PlatformError(
                "Request was cancelled",
                platform="Rumble"
            )
            
        except Exception as e:
            log.log_operation_error('actor_call', e, context)
            
            # Categorize the error based on its content
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise PlatformRateLimitError(
                    "API rate limit exceeded",
                    platform="Rumble",
                    original_error=e
                )
            elif "unauthorized" in error_msg or "401" in error_msg:
                raise PlatformAuthenticationError(
                    "Authentication failed",
                    platform="Rumble",
                    original_error=e
                )
            else:
                raise PlatformAPIError(
                    f"Actor call failed: {str(e)}",
                    platform="Rumble",
                    original_error=e
                )
    
    async def _call_apify_actor(self, actor_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal method to make the actual Apify actor call.
        
        This is separated from _make_actor_call to allow for proper timeout handling.
        
        Args:
            actor_id: Apify actor ID
            input_data: Input data for the actor
            
        Returns:
            Actor response data
        """
        if not self.client:
            raise PlatformAuthenticationError(
                "Apify client not initialized. API token required.",
                platform="Rumble"
            )
        
        # Get the actor
        actor = self.client.actor(actor_id)
        
        # Run the actor with input data
        # Note: Apify client might have its own timeout parameter
        try:
            # Convert timeout from milliseconds to seconds
            timeout_secs = self.actor_timeout / 1000
            
            # Call the actor and wait for it to finish
            run = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: actor.call(
                    input_json=input_data,
                    wait_secs=timeout_secs
                )
            )
            
            # Get the results from the default dataset
            if run and run.get("defaultDatasetId"):
                dataset = self.client.dataset(run["defaultDatasetId"])
                items = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: list(dataset.iterate_items())
                )
                return {"items": items}
            else:
                return {}
                
        except Exception as e:
            # Re-raise the exception to be handled by _make_actor_call
            raise
    
    async def get_cache_metrics(self) -> Dict[str, Any]:
        """
        Get cache metrics if cache manager is available.
        
        Returns:
            Dictionary containing cache metrics or empty dict if no cache
        """
        if self.cache_manager:
            return await self.cache_manager.get_metrics()
        return {}
    
    async def close(self):
        """
        Clean up resources including cache connections.
        """
        if self.cache_manager:
            await self.cache_manager.close()
        # Close any other resources if needed
        self.logger.info("Closed RumbleExtractor resources")


# Future enhancements:
# - Add quality selection for search results
# - Implement format conversion utilities
# - Response caching layer implemented
# - Implement batch processing for multiple URLs
# - Add support for playlist extraction