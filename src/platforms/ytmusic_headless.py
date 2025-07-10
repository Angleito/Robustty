import logging
import re
import asyncio
import json
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote_plus

import aiohttp

from .base import VideoPlatform
from .errors import PlatformError
from ..utils.network_routing import youtube_session

logger = logging.getLogger(__name__)


class YouTubeMusicHeadlessPlatform(VideoPlatform):
    """YouTube Music platform using headless desktop app API"""

    def __init__(self, name: str, config: Dict[str, Any], cache_manager=None):
        super().__init__(name, config, cache_manager)
        self.api_url = config.get('api_url', 'http://youtube-music-headless:9863')
        self.timeout = config.get('timeout', 45)  # Increased from 30
        self.retry_attempts = config.get('retry_attempts', 2)  # Reduced from 3
        self.retry_delay = config.get('retry_delay', 2)  # Increased from 1
        
        # YouTube Music URL patterns
        self.url_patterns = [
            r'https?://music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
            r'https?://music\.youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)',
            r'https?://www\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',  # Regular YouTube URLs also work
        ]

    async def _make_api_request(self, endpoint: str, params: Optional[Dict] = None, retries: int = None) -> Dict[str, Any]:
        """Make a request to the YouTube Music headless API with retries using network routing"""
        if retries is None:
            retries = self.retry_attempts
            
        url = f"{self.api_url}{endpoint}"
        
        for attempt in range(retries + 1):
            try:
                logger.debug(f"Making API request to {url} (attempt {attempt + 1}/{retries + 1})")
                
                # Use network-aware session for YouTube Music API calls
                async with youtube_session() as session:
                    async with session.get(
                        url, 
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.debug(f"API request successful: {url}")
                            return data
                        elif response.status == 404:
                            logger.warning(f"API endpoint not found: {url}")
                            raise PlatformError(f"YouTube Music API endpoint not available: {endpoint}")
                        else:
                            error_text = await response.text()
                            logger.warning(f"API request failed with status {response.status}: {error_text}")
                            
                            if attempt < retries:
                                await asyncio.sleep(self.retry_delay * (attempt + 1))
                                continue
                            else:
                                raise PlatformError(f"YouTube Music API request failed: {response.status}")
                            
            except asyncio.TimeoutError:
                logger.warning(f"API request timeout for {url} (attempt {attempt + 1})")
                if attempt < retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    raise PlatformError("YouTube Music API request timeout")
                    
            except aiohttp.ClientError as e:
                logger.warning(f"API request client error for {url}: {e}")
                if attempt < retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    raise PlatformError(f"YouTube Music API client error: {e}")
                    
            except Exception as e:
                logger.error(f"Unexpected error in API request to {url}: {e}")
                if attempt < retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    raise PlatformError(f"YouTube Music API unexpected error: {e}")

    async def search_videos(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for videos using YouTube Music headless API"""
        try:
            # Check cache first
            cached_results = await self.get_cached_search_results(query)
            if cached_results:
                logger.debug(f"Returning cached search results for query: {query}")
                return cached_results[:max_results]

            logger.info(f"Searching YouTube Music for: {query}")
            
            # Make API request to headless YouTube Music
            params = {
                'q': query,
                'limit': max_results,
                'type': 'songs'  # Focus on songs rather than videos
            }
            
            data = await self._make_api_request('/api/search', params)
            
            if not data or 'results' not in data:
                logger.warning(f"No results returned from YouTube Music API for query: {query}")
                return []
            
            results = []
            for item in data['results'][:max_results]:
                try:
                    video_data = {
                        'id': item.get('videoId', ''),
                        'title': item.get('title', 'Unknown'),
                        'artist': item.get('artist', 'Unknown Artist'),
                        'duration': item.get('duration', 0),
                        'thumbnail': item.get('thumbnail', ''),
                        'platform': self.name,
                        'url': f"https://music.youtube.com/watch?v={item.get('videoId', '')}",
                        'album': item.get('album', ''),
                        'year': item.get('year', ''),
                        'explicit': item.get('explicit', False)
                    }
                    results.append(video_data)
                    
                except Exception as e:
                    logger.warning(f"Error parsing search result item: {e}")
                    continue
            
            # Cache the results
            await self.cache_search_results(query, results, ttl=3600)  # Cache for 1 hour
            
            logger.info(f"Found {len(results)} results for query: {query}")
            return results
            
        except PlatformError:
            raise
        except Exception as e:
            logger.error(f"Error searching YouTube Music: {e}")
            raise PlatformError(f"YouTube Music search failed: {e}")

    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video details from YouTube Music headless API"""
        try:
            # Check cache first
            cached_metadata = await self.get_cached_video_metadata(video_id)
            if cached_metadata:
                logger.debug(f"Returning cached metadata for video: {video_id}")
                return cached_metadata

            logger.info(f"Getting YouTube Music video details for: {video_id}")
            
            data = await self._make_api_request(f'/api/song/{video_id}')
            
            if not data:
                logger.warning(f"No details returned for video: {video_id}")
                return None
            
            video_details = {
                'id': video_id,
                'title': data.get('title', 'Unknown'),
                'artist': data.get('artist', 'Unknown Artist'),
                'duration': data.get('duration', 0),
                'thumbnail': data.get('thumbnail', ''),
                'platform': self.name,
                'url': f"https://music.youtube.com/watch?v={video_id}",
                'album': data.get('album', ''),
                'year': data.get('year', ''),
                'explicit': data.get('explicit', False),
                'description': data.get('description', ''),
                'lyrics': data.get('lyrics', '')
            }
            
            # Cache the metadata
            await self.cache_video_metadata(video_id, video_details, ttl=7200)  # Cache for 2 hours
            
            return video_details
            
        except PlatformError:
            raise
        except Exception as e:
            logger.error(f"Error getting YouTube Music video details: {e}")
            return None

    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL from YouTube Music headless API"""
        try:
            # Check cache first
            cached_url = await self.get_cached_stream_url(video_id)
            if cached_url:
                logger.debug(f"Returning cached stream URL for video: {video_id}")
                return cached_url

            logger.info(f"Getting YouTube Music stream URL for: {video_id}")
            
            data = await self._make_api_request(f'/api/stream/{video_id}')
            
            if not data or 'stream_url' not in data:
                logger.warning(f"No stream URL returned for video: {video_id}")
                return None
            
            stream_url = data['stream_url']
            quality = data.get('quality', 'unknown')
            
            # Cache the stream URL with shorter TTL since URLs can expire
            await self.cache_stream_url(video_id, stream_url, quality, ttl=1800)  # Cache for 30 minutes
            
            logger.info(f"Got stream URL for {video_id} (quality: {quality})")
            return stream_url
            
        except PlatformError:
            raise
        except Exception as e:
            logger.error(f"Error getting YouTube Music stream URL: {e}")
            return None

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube Music URL"""
        for pattern in self.url_patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                logger.debug(f"Extracted video ID {video_id} from URL: {url}")
                return video_id
        
        logger.debug(f"Could not extract video ID from URL: {url}")
        return None

    def is_platform_url(self, url: str) -> bool:
        """Check if URL is a YouTube Music URL"""
        youtube_music_patterns = [
            r'https?://music\.youtube\.com/',
            r'https?://www\.youtube\.com/watch\?v='  # Regular YouTube URLs also supported
        ]
        
        for pattern in youtube_music_patterns:
            if re.search(pattern, url):
                logger.debug(f"URL {url} matches YouTube Music platform")
                return True
        
        return False

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the YouTube Music headless service"""
        try:
            data = await self._make_api_request('/api/health', retries=1)
            return {
                'healthy': True,
                'status': data.get('status', 'unknown'),
                'version': data.get('version', 'unknown'),
                'uptime': data.get('uptime', 0)
            }
        except Exception as e:
            logger.warning(f"YouTube Music headless service health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e)
            }

    async def initialize(self):
        """Initialize the YouTube Music headless platform"""
        await super().initialize()
        
        # Test connection to headless service
        try:
            health = await self.get_health_status()
            if health['healthy']:
                logger.info(f"YouTube Music headless service is ready at {self.api_url}")
                
                # Check if service has authentication
                auth_status = await self._check_authentication_status()
                if auth_status.get('authenticated'):
                    logger.info("YouTube Music headless service is authenticated")
                else:
                    logger.warning("YouTube Music headless service is not authenticated - some features may be limited")
            else:
                logger.warning(f"YouTube Music headless service health check failed: {health.get('error', 'unknown')}")
        except Exception as e:
            logger.warning(f"Could not connect to YouTube Music headless service: {e}")

    async def _check_authentication_status(self) -> Dict[str, Any]:
        """Check if the YouTube Music service is authenticated"""
        try:
            data = await self._make_api_request('/api/auth/status', retries=1)
            return {
                'authenticated': data.get('authenticated', False),
                'user': data.get('user', None),
                'subscription': data.get('subscription', None)
            }
        except Exception as e:
            logger.debug(f"Could not check authentication status: {e}")
            return {'authenticated': False}

    async def cleanup(self):
        """Cleanup platform resources"""
        await super().cleanup()
        logger.info("YouTube Music headless platform cleaned up")