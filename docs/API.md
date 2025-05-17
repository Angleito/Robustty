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

## Platform-Specific Examples

### Rumble

Rumble integration uses the Apify API to extract video information and streaming URLs. This example shows how to configure and use Rumble with the bot.

#### Configuration

First, set up your Rumble configuration in `config/config.yaml`:

```yaml
platforms:
  rumble:
    enabled: true
    api_endpoint: "https://api.apify.com/v2"
    actor_id: "tO3W1apGqJXZBKvGP"  # Rumble scraper actor
    debug: false
```

Add your Apify API token to `.env`:

```bash
APIFY_API_TOKEN=your_apify_api_token_here
```

#### Step-by-Step Usage Example

1. **Basic Rumble Video Playback**

```
User: !play https://rumble.com/v12345-funny-cat-video.html
Bot: Searching for videos...

Bot: Found on Rumble:
  🎬 Funny Cat Video
  👤 Channel: CatLovers
  ⏱️ Duration: 3:45
  🔗 https://rumble.com/v12345-funny-cat-video.html

Bot: Added to queue: Funny Cat Video
Bot: Now playing: Funny Cat Video
```

2. **Search Query Example**

```
User: !play rumble funny cats compilation
Bot: Searching for videos...

Bot: Found 3 results on Rumble:
  1. Funny Cats Compilation 2024
  2. Hilarious Cat Fails 
  3. Cute Kittens Playing

Bot: React with the number to select (1-3) or ❌ to cancel

User: (reacts with 1️⃣)
Bot: Added to queue: Funny Cats Compilation 2024
```

3. **Queue Multiple Rumble Videos**

```
User: !play https://rumble.com/v12345-video1.html
Bot: Added to queue: Video 1 Title

User: !play https://rumble.com/v12346-video2.html  
Bot: Added to queue: Video 2 Title

User: !queue
Bot: 📋 Queue (2 songs):
  🎵 Now Playing: Video 1 Title
  1. Video 2 Title
```

#### Error Handling Examples

1. **Invalid URL**
```
User: !play https://rumble.com/invalid-url
Bot: ❌ Error: Invalid Rumble URL format
```

2. **API Token Missing**
```
User: !play rumble cats
Bot: ❌ Error: Rumble API token not configured. Please contact an administrator.
```

3. **Rate Limit Exceeded**
```
User: !play rumble dogs
Bot: ❌ Error: Rate limit exceeded. Please try again in a few minutes.
```

4. **Network/API Error**
```
User: !play rumble music
Bot: ❌ Error: Failed to connect to Rumble API. Please try again later.
```

#### Troubleshooting Tips

1. **Video Won't Play**
   - Check if the Apify API token is valid
   - Verify the Rumble URL is properly formatted
   - Look for specific error messages in logs

2. **Search Not Working**
   - Currently only direct URLs are supported
   - Search functionality may be limited by API

3. **Common Error Patterns**

   **HTTP 403 Error:**
   ```
   Bot: ❌ Error: Unable to access Rumble video (403 Forbidden)
   ```
   This usually means the video is restricted or private.

   **Extraction Timeout:**
   ```
   Bot: ❌ Error: Video extraction timed out. Please try a different video.
   ```
   Some videos may take too long to process.

   **Invalid API Token:**
   ```
   Bot: ❌ Error: Invalid API credentials. Please check your configuration.
   ```
   The Apify token may be expired or incorrect.

4. **Debug Mode**

   Enable debug mode in config for detailed logs:
   ```yaml
   platforms:
     rumble:
       debug: true
   ```

   This will show:
   - API request details
   - Response data
   - Extraction progress
   - URL parsing information

5. **Performance Tips**

   - Use direct video URLs for faster response
   - Avoid rapid consecutive requests
   - Consider implementing caching for frequently played videos

#### Complete Code Example

Here's a minimal bot setup for Rumble playback:

```python
import discord
from discord.ext import commands
from src.bot.bot import Robustty

# Initialize bot
bot = Robustty(
    command_prefix='!',
    intents=discord.Intents.all()
)

# Example usage in a cog
class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def play(self, ctx, *, query):
        """Play a Rumble video by URL"""
        try:
            # Check if it's a Rumble URL
            if "rumble.com" in query:
                # Extract video ID
                video_id = self.bot.platform_registry.get_platform('rumble').extract_video_id(query)
                if not video_id:
                    await ctx.send("❌ Invalid Rumble URL")
                    return
                
                # Get video details
                video_info = await self.bot.platform_registry.get_platform('rumble').get_video_details(video_id)
                if not video_info:
                    await ctx.send("❌ Failed to get video information")
                    return
                
                # Add to queue
                await self.bot.audio_player.add_to_queue(video_info)
                await ctx.send(f"✅ Added to queue: {video_info['title']}")
                
                # Start playing if not already
                if not self.bot.audio_player.is_playing():
                    await self.bot.audio_player.play_next()
            else:
                await ctx.send("❌ Please provide a valid Rumble URL")
                
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")

# Run the bot
if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN'))
```

#### Testing Rumble Integration

1. **Unit Test Example**

```python
import pytest
from src.platforms.rumble import RumblePlatform

@pytest.mark.asyncio
async def test_extract_video_id():
    platform = RumblePlatform()
    
    # Test standard URL
    url = "https://rumble.com/v12345-test-video.html"
    video_id = platform.extract_video_id(url)
    assert video_id == "v12345"
    
    # Test embed URL
    embed_url = "https://rumble.com/embed/v12345/"
    video_id = platform.extract_video_id(embed_url)
    assert video_id == "v12345"
    
    # Test invalid URL
    invalid_url = "https://youtube.com/watch?v=12345"
    video_id = platform.extract_video_id(invalid_url)
    assert video_id is None
```

2. **Integration Test**

```python
@pytest.mark.asyncio
async def test_rumble_playback():
    # Initialize bot
    bot = Robustty()
    
    # Test video URL
    test_url = "https://rumble.com/v12345-test.html"
    
    # Get video info
    video_info = await bot.platform_registry.get_platform('rumble').get_video_by_url(test_url)
    
    # Verify fields
    assert video_info['title']
    assert video_info['url'] == test_url
    assert video_info['platform'] == 'rumble'
    assert video_info['stream_url']
```

3. **Mock Testing**

```python
from unittest.mock import Mock, patch

@patch('src.platforms.rumble.RumblePlatform._make_api_call')
async def test_rumble_with_mock(mock_api):
    # Mock API response
    mock_api.return_value = {
        'title': 'Test Video',
        'url': 'https://rumble.com/v12345.html',
        'stream_url': 'https://stream.rumble.com/video.mp4'
    }
    
    platform = RumblePlatform()
    result = await platform.get_video_details('v12345')
    
    assert result['title'] == 'Test Video'
    mock_api.assert_called_once()
```

#### Advanced Configuration

For production use, consider these additional settings:

```yaml
platforms:
  rumble:
    enabled: true
    api_endpoint: "https://api.apify.com/v2"
    actor_id: "tO3W1apGqJXZBKvGP"
    debug: false
    timeout: 30  # API call timeout in seconds
    retry_count: 3  # Number of retries on failure
    cache_ttl: 3600  # Cache duration in seconds
    rate_limit:
      requests: 100
      window: 3600  # Per hour
```

Environment variables:
```bash
APIFY_API_TOKEN=your_token
RUMBLE_DEBUG=false
RUMBLE_TIMEOUT=30
RUMBLE_CACHE_ENABLED=true
```