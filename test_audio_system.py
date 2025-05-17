#!/usr/bin/env python3
import asyncio
import os
import sys
import logging
import aiohttp
from unittest.mock import Mock, AsyncMock

# Add src to path
sys.path.insert(0, '/Users/angel/Documents/Projects/robustty/robustty')

from src.platforms.youtube import YouTubePlatform
from src.services.audio_player import AudioPlayer
from src.platforms.registry import PlatformRegistry

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_youtube_search():
    """Test YouTube search functionality"""
    print("\n=== Testing YouTube Search ===")
    
    yt_config = {
        'api_key': os.getenv('YOUTUBE_API_KEY'),
        'enabled': True
    }
    
    youtube = YouTubePlatform("youtube", yt_config)
    await youtube.initialize()
    
    try:
        results = await youtube.search_videos("Joji SLOW DANCING IN THE DARK", max_results=1)
        if results:
            first_result = results[0]
            print(f"✓ YouTube Search successful")
            print(f"  Title: {first_result['title']}")
            print(f"  ID: {first_result['id']} (length: {len(first_result['id'])})")
            print(f"  URL: {first_result['url']}")
            return first_result
        else:
            print("✗ No results found")
            return None
    except Exception as e:
        print(f"✗ YouTube search failed: {e}")
        return None

async def test_stream_service(video_info):
    """Test stream service extraction"""
    print("\n=== Testing Stream Service ===")
    
    platform = video_info['platform']
    video_id = video_info['id']
    
    # Test against the Docker stream service
    stream_service_url = "http://localhost:5001"  # External port
    url = f"{stream_service_url}/stream/{platform}/{video_id}"
    
    print(f"Calling stream service: {url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    stream_url = data.get('url')  # Changed from 'stream_url' to 'url'
                    if stream_url:
                        print(f"✓ Stream URL obtained successfully")
                        print(f"  Stream URL: {stream_url[:100]}...")
                        print(f"  Cached: {data.get('cached', False)}")
                        return stream_url
                    else:
                        print(f"✗ No stream URL in response: {data}")
                        return None
                else:
                    error_text = await response.text()
                    print(f"✗ Stream service error: {error_text}")
                    return None
    except Exception as e:
        print(f"✗ Failed to connect to stream service: {e}")
        return None

async def test_audio_player(video_info):
    """Test audio player with mock Discord components"""
    print("\n=== Testing Audio Player ===")
    
    # Create mock Discord components
    mock_bot = Mock()
    mock_bot.loop = asyncio.get_event_loop()
    
    mock_voice_client = Mock()
    mock_voice_client.is_connected = Mock(return_value=True)
    mock_voice_client.is_playing = Mock(return_value=False)
    mock_voice_client.play = Mock()
    
    # Create audio player
    config = {"max_queue_size": 100}
    audio_player = AudioPlayer(config, bot=mock_bot)
    audio_player.voice_client = mock_voice_client
    
    # Add song to queue
    await audio_player.add_to_queue(video_info)
    print(f"✓ Added to queue: {video_info['title']}")
    
    # Override _get_stream_url to use Docker port
    original_get_stream_url = audio_player._get_stream_url
    
    async def mock_get_stream_url(song_info):
        """Override to use external Docker port"""
        platform = song_info["platform"]
        video_id = song_info["id"]
        
        stream_service_url = "http://localhost:5001"  # External port
        url = f"{stream_service_url}/stream/{platform}/{video_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("url")  # Changed from 'stream_url' to 'url'
                else:
                    raise Exception(f"Failed to get stream URL: {response.status}")
    
    audio_player._get_stream_url = mock_get_stream_url
    
    # Test play_next
    try:
        await audio_player.play_next()
        print("✓ play_next called successfully")
        
        # Check if play was called
        if mock_voice_client.play.called:
            print("✓ Discord play method was called")
            
            # Get the audio source that was passed to play
            args = mock_voice_client.play.call_args
            if args:
                audio_source = args[0][0]
                print(f"✓ Audio source created: {type(audio_source)}")
                return True
        else:
            print("✗ Discord play method was not called")
            return False
    except Exception as e:
        print(f"✗ Error in play_next: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_direct_stream_extraction():
    """Test direct yt-dlp extraction"""
    print("\n=== Testing Direct yt-dlp Extraction ===")
    
    import yt_dlp
    
    url = "https://www.youtube.com/watch?v=j89Qu0xu188"  # Full 11-character ID
    
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                print(f"✓ Direct extraction successful")
                print(f"  Title: {info.get('title')}")
                print(f"  ID: {info.get('id')}")
                print(f"  Format: {info.get('format')}")
                print(f"  Has URL: {'url' in info}")
                return True
            else:
                print("✗ No info extracted")
                return False
    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("Starting Robustty Audio System Tests")
    print("=" * 40)
    
    # Test 1: YouTube Search
    video_info = await test_youtube_search()
    if not video_info:
        print("\n❌ YouTube search failed. Cannot continue tests.")
        return
    
    # Test 2: Stream Service
    stream_url = await test_stream_service(video_info)
    if not stream_url:
        print("\n⚠️  Stream service test failed, but continuing...")
    
    # Test 3: Audio Player
    audio_success = await test_audio_player(video_info)
    
    # Test 4: Direct extraction
    direct_success = await test_direct_stream_extraction()
    
    # Summary
    print("\n" + "=" * 40)
    print("Test Summary:")
    print(f"✓ YouTube Search: {'PASSED' if video_info else 'FAILED'}")
    print(f"{'✓' if stream_url else '✗'} Stream Service: {'PASSED' if stream_url else 'FAILED'}")
    print(f"{'✓' if audio_success else '✗'} Audio Player: {'PASSED' if audio_success else 'FAILED'}")
    print(f"{'✓' if direct_success else '✗'} Direct yt-dlp: {'PASSED' if direct_success else 'FAILED'}")
    print("=" * 40)

if __name__ == "__main__":
    asyncio.run(main())