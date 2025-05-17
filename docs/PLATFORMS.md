# Platform Integration Guide

## Adding a New Platform

To add a new video platform to Robustty:

### 1. Create a Platform Class

Create a new file in `src/platforms/myplatform.py`:

```python
# src/platforms/myplatform.py
from .base import VideoPlatform
import re

class MyPlatform(VideoPlatform):
    def __init__(self, config: dict):
        super().__init__("myplatform", config)
        # Platform-specific initialization
        
    async def search_videos(self, query: str, max_results: int = 10):
        # Implement search logic
        pass
        
    async def get_video_details(self, video_id: str):
        # Implement video details fetching
        pass
        
    def extract_video_id(self, url: str):
        # Extract video ID from URL
        pattern = r'myplatform\.com/video/([a-zA-Z0-9]+)'
        match = re.search(pattern, url)
        return match.group(1) if match else None
        
    def is_platform_url(self, url: str):
        return 'myplatform.com' in url
        
    async def get_stream_url(self, video_id: str):
        # Get stream URL for the video
        pass
```

### 2. Register the Platform

Add to `src/bot/bot.py` in the setup_hook method:

```python
from ..platforms.myplatform import MyPlatform
self.platform_registry.register_platform('myplatform', MyPlatform)
```

### 3. Add Configuration

Update `config/config.yaml`:

```yaml
platforms:
  # ... existing platforms ...
  myplatform:
    enabled: true
    api_key: ${MYPLATFORM_API_KEY}
    # Other platform-specific config
```

Update `.env`:

```env
MYPLATFORM_API_KEY=your_api_key_here
```

## Platform Requirements

Each platform must implement:

### 1. Search Functionality
- Find videos based on text queries
- Return structured results with title, URL, thumbnail, etc.

### 2. URL Parsing
- Extract video IDs from platform URLs
- Identify if a URL belongs to the platform

### 3. Video Details
- Fetch metadata about videos
- Include duration, views, channel info

### 4. Stream Extraction
- Get playable stream URLs
- Handle authentication if needed

## Example Implementations

### YouTube Platform

```python
class YouTubePlatform(VideoPlatform):
    async def search_videos(self, query: str, max_results: int = 10):
        request = self.youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results
        )
        response = request.execute()
        
        results = []
        for item in response.get('items', []):
            results.append({
                'id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                'platform': 'youtube'
            })
        return results
```

### PeerTube Platform with Type Annotations

PeerTube now includes comprehensive type definitions for better code reliability:

```python
# src/platforms/peertube_types.py
from typing import TypedDict, Optional, List

class ChannelInfo(TypedDict):
    """PeerTube channel information."""
    displayName: str
    name: str
    description: Optional[str]
    url: Optional[str]

class VideoDetails(TypedDict):
    """Standardized video details for internal use."""
    id: str
    title: str
    channel: str
    thumbnail: str
    url: str
    platform: str
    instance: str
    description: str
    duration: Optional[int]
    views: int
```

Implementation with proper type hints:

```python
from src.platforms.peertube_types import VideoDetails, ChannelInfo, VideoInfo

class PeerTubePlatform(VideoPlatform):
    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__("peertube", config)
        self.instances: List[str] = config.get("instances", [])
        
    async def search_videos(self, query: str, max_results: int = 10) -> List[VideoDetails]:
        results: List[VideoDetails] = []
        tasks: List[Coroutine[Any, Any, List[VideoDetails]]] = []
        
        for instance in self.instances:
            task = self._search_instance(instance, query, max_results)
            tasks.append(task)
            
        instance_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(instance_results):
            if isinstance(result, Exception):
                logger.error(f"Error searching {self.instances[i]}: {result}")
            elif isinstance(result, list):
                results.extend(result)
                
        return results
```

## Testing Your Platform

Create tests in `tests/test_platforms/test_myplatform.py`:

```python
import pytest
from src.platforms.myplatform import MyPlatform

@pytest.mark.asyncio
async def test_search():
    platform = MyPlatform({'enabled': True})
    await platform.initialize()
    
    results = await platform.search_videos("test query")
    assert len(results) > 0
    
    await platform.cleanup()

@pytest.mark.asyncio
async def test_url_parsing():
    platform = MyPlatform({'enabled': True})
    
    url = "https://myplatform.com/video/abc123"
    assert platform.is_platform_url(url)
    assert platform.extract_video_id(url) == "abc123"
```

## Best Practices

### 1. Type Safety

Use proper type annotations throughout your code:

```python
from typing import List, Optional, Dict, Any, Union
from src.platforms.base import VideoPlatform
from src.platforms.my_types import VideoDetails, SearchResult

class MyPlatform(VideoPlatform):
    async def search_videos(self, query: str, max_results: int = 10) -> List[VideoDetails]:
        # Type-safe implementation
        results: List[VideoDetails] = []
        return results
```

### 2. Error Handling

Handle API failures with custom exception types:

```python
class MyPlatformError(Exception):
    """Base exception for MyPlatform"""
    pass

class MyPlatformAPIError(MyPlatformError):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

try:
    response = await self.session.get(url)
    data = await response.json()
except aiohttp.ClientError as e:
    raise MyPlatformAPIError(f"API request failed: {e}", response.status)
```

### 2. Rate Limiting

Implement rate limiting for API requests:

```python
async def _make_request_with_retry(self, url, max_retries=3):
    for attempt in range(max_retries):
        try:
            async with self.session.get(url) as response:
                if response.status == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                return await response.json()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)
```

### 3. Caching

Cache responses to reduce API calls:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
async def get_cached_video_details(self, video_id: str):
    return await self.get_video_details(video_id)
```

### 4. Authentication

Handle authenticated requests:

```python
async def _get_authenticated_headers(self):
    if self.api_key:
        return {'Authorization': f'Bearer {self.api_key}'}
    elif self.cookies:
        return {'Cookie': self.cookies}
    return {}
```

## Common Issues

### API Authentication

Some platforms require API keys or OAuth:

```python
def __init__(self, config):
    super().__init__("myplatform", config)
    self.api_key = config.get('api_key')
    if not self.api_key:
        logger.warning("API key not provided for MyPlatform")
```

### Stream URL Expiration

Handle expiring stream URLs:

```python
async def get_stream_url(self, video_id: str):
    # Get fresh stream URL
    stream_info = await self._fetch_stream_info(video_id)
    
    # Include expiration time
    return {
        'url': stream_info['url'],
        'expires_at': time.time() + stream_info['ttl']
    }
```

### Regional Restrictions

Handle geo-blocked content:

```python
async def search_videos(self, query: str, region: str = None):
    params = {'q': query}
    if region:
        params['region'] = region
    
    try:
        results = await self._api_search(params)
    except GeoBlockedError:
        logger.warning(f"Content blocked in region: {region}")
        return []
```

## Platform-Specific Features

### Live Streams

Support live streaming:

```python
async def get_video_details(self, video_id: str):
    details = await super().get_video_details(video_id)
    
    if details.get('is_live'):
        details['stream_type'] = 'live'
        details['duration'] = 'LIVE'
    
    return details
```

### Playlists

Support playlist extraction:

```python
async def get_playlist_videos(self, playlist_id: str):
    videos = []
    page_token = None
    
    while True:
        response = await self._api_playlist_items(
            playlist_id, 
            page_token
        )
        videos.extend(response['items'])
        
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    
    return videos
```

### Quality Selection

Allow quality selection:

```python
async def get_stream_url(self, video_id: str, quality: str = 'best'):
    streams = await self._get_all_streams(video_id)
    
    if quality == 'best':
        return streams[0]['url']
    
    for stream in streams:
        if stream['quality'] == quality:
            return stream['url']
    
    # Fallback to best available
    return streams[0]['url']
```