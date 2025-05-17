# API Documentation

This document describes the internal APIs used by Robustty components.

## Platform API

All platforms must implement the `VideoPlatform` base class:

### Base Methods

#### search_videos(query: str, max_results: int = 10) -> List[Dict]

Search for videos on the platform.

**Parameters:**
- `query`: Search string
- `max_results`: Maximum number of results to return

**Returns:**
List of video dictionaries containing:
- `id`: Unique video identifier
- `title`: Video title
- `url`: Full URL to the video
- `platform`: Platform name
- `channel`: Channel/uploader name
- `thumbnail`: Thumbnail URL (optional)
- `duration`: Video duration (optional)

#### get_video_details(video_id: str) -> Optional[Dict]

Get detailed information about a video.

**Parameters:**
- `video_id`: Platform-specific video identifier

**Returns:**
Video dictionary with extended information:
- All fields from search_videos
- `description`: Full video description
- `views`: View count
- `likes`: Like count (optional)
- `upload_date`: Upload date (optional)

#### extract_video_id(url: str) -> Optional[str]

Extract video ID from a platform URL.

**Parameters:**
- `url`: Full URL to the video

**Returns:**
- Video ID string or None if not a valid URL

#### is_platform_url(url: str) -> bool

Check if a URL belongs to this platform.

**Parameters:**
- `url`: URL to check

**Returns:**
- True if URL is from this platform

#### get_stream_url(video_id: str) -> Optional[str]

Get the stream URL for a video.

**Parameters:**
- `video_id`: Video identifier

**Returns:**
- Direct stream URL or service endpoint

## Service APIs

### MultiPlatformSearcher

#### search_all_platforms(query: str, max_results: int = 10) -> Dict[str, List[Dict]]

Search across all enabled platforms.

**Parameters:**
- `query`: Search string or URL
- `max_results`: Maximum results per platform

**Returns:**
Dictionary mapping platform names to result lists.

### AudioPlayer

#### add_to_queue(song_info: Dict)

Add a song to the queue.

**Parameters:**
- `song_info`: Video dictionary from platform search

**Raises:**
- `ValueError`: If queue is full

#### play_next()

Play the next song in queue.

**Effects:**
- Dequeues next song
- Starts playback
- Updates current song

#### skip()

Skip the current song.

**Effects:**
- Stops current playback
- Triggers play_next()

#### set_volume(volume: int)

Set playback volume.

**Parameters:**
- `volume`: Volume level (0-100)

### CookieManager

#### get_cookies(platform: str) -> Optional[Dict]

Get stored cookies for a platform.

**Parameters:**
- `platform`: Platform name

**Returns:**
- Cookie dictionary or None

#### save_cookies(platform: str, cookies: Dict)

Save cookies for a platform.

**Parameters:**
- `platform`: Platform name
- `cookies`: Cookie dictionary

## Bot Commands API

### Music Commands

#### play(query: str)

Play a song from any platform.

**Parameters:**
- `query`: Search string or URL

**Process:**
1. Search all platforms
2. Display results
3. Wait for selection
4. Add to queue
5. Start playback

#### skip()

Skip current song.

**Requirements:**
- User in same voice channel
- Song currently playing

#### queue()

Display current queue.

**Returns:**
Embed showing:
- Current song
- Upcoming songs
- Queue length

#### volume(level: int = None)

Get or set volume.

**Parameters:**
- `level`: Volume (0-100) or None to get current

### Admin Commands

#### reload(extension: str = None)

Reload bot extensions.

**Parameters:**
- `extension`: Specific extension or None for all

**Requirements:**
- Administrator permission

#### status()

Show bot status.

**Returns:**
Embed showing:
- Guild count
- User count
- Platform status
- Memory usage

## Event Hooks

### Bot Events

#### on_ready()

Called when bot connects to Discord.

**Actions:**
- Log connection
- Set presence
- Initialize services

#### on_guild_join(guild)

Called when bot joins a server.

**Parameters:**
- `guild`: Discord guild object

**Actions:**
- Log join
- Create guild configuration

#### on_guild_remove(guild)

Called when bot leaves a server.

**Parameters:**
- `guild`: Discord guild object

**Actions:**
- Cleanup resources
- Save queue if enabled

### Player Events

#### on_playback_finished(error)

Called when song finishes.

**Parameters:**
- `error`: Error object or None

**Actions:**
- Log any errors
- Play next song
- Update presence

## Error Handling

### Custom Exceptions

```python
class PlatformError(Exception):
    """Base exception for platform errors"""
    pass

class SearchError(PlatformError):
    """Raised when search fails"""
    pass

class StreamError(PlatformError):
    """Raised when stream extraction fails"""
    pass

class QueueFullError(Exception):
    """Raised when queue is at capacity"""
    pass
```

### Error Responses

All API methods should handle errors gracefully:

```python
try:
    results = await platform.search_videos(query)
except PlatformError as e:
    logger.error(f"Platform error: {e}")
    return []
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return []
```

## Rate Limiting

### Platform Rate Limits

Each platform may have different rate limits:

```python
RATE_LIMITS = {
    'youtube': {'requests': 100, 'window': 60},
    'peertube': {'requests': 1000, 'window': 3600},
}
```

### Implementation

```python
from asyncio import Semaphore

class RateLimiter:
    def __init__(self, rate, per):
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()
        self.lock = Semaphore(1)
    
    async def acquire(self):
        async with self.lock:
            current = time.time()
            elapsed = current - self.last_check
            self.last_check = current
            self.allowance += elapsed * (self.rate / self.per)
            
            if self.allowance > self.rate:
                self.allowance = self.rate
            
            if self.allowance < 1:
                sleep_time = (1 - self.allowance) * (self.per / self.rate)
                await asyncio.sleep(sleep_time)
                self.allowance = 0
            else:
                self.allowance -= 1
```

## Caching

### Cache Keys

Standard cache key format:

```python
def get_cache_key(platform: str, operation: str, identifier: str) -> str:
    return f"{platform}:{operation}:{identifier}"
```

### Cache Operations

```python
async def get_cached(key: str) -> Optional[Any]:
    """Get cached value"""
    return await redis.get(key)

async def set_cached(key: str, value: Any, ttl: int = 3600):
    """Set cached value with TTL"""
    await redis.setex(key, ttl, value)
```

## Webhook Support

### Event Webhooks

Send notifications for events:

```python
async def send_webhook(url: str, event: str, data: Dict):
    payload = {
        'event': event,
        'timestamp': time.time(),
        'data': data
    }
    
    async with aiohttp.ClientSession() as session:
        await session.post(url, json=payload)
```

### Supported Events

- `song_start`: New song starts playing
- `queue_add`: Song added to queue
- `bot_join`: Bot joins voice channel
- `bot_leave`: Bot leaves voice channel