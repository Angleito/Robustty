#!/usr/bin/env python3
"""
Comprehensive audio system test for Discord bot
Tests cookie extraction, YouTube integration, and FFmpeg compatibility
"""

import asyncio
import logging
import os
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_cookie_extraction():
    """Test cookie extraction process"""
    logger.info("=== Testing Cookie Extraction ===")
    
    try:
        # Import and run cookie extraction
        import sys
        sys.path.append('scripts')
        from scripts.extract_brave_cookies import extract_brave_cookies_from_host, save_cookies_to_files
        
        # Extract cookies
        cookies = extract_brave_cookies_from_host()
        
        if not cookies:
            logger.warning("No cookies extracted - this may be normal if Brave isn't used")
            return False
        
        # Save cookies
        save_cookies_to_files(cookies)
        
        # Verify YouTube cookies exist
        cookie_file = Path('/app/cookies/youtube_cookies.json')
        if not cookie_file.exists():
            cookie_file = Path('./cookies/youtube_cookies.json')
        
        if cookie_file.exists():
            with open(cookie_file) as f:
                youtube_cookies = json.load(f)
            logger.info(f"✅ Found {len(youtube_cookies)} YouTube cookies")
            return True
        else:
            logger.warning("❌ No YouTube cookies file found")
            return False
            
    except Exception as e:
        logger.error(f"❌ Cookie extraction failed: {e}")
        return False

async def test_youtube_platform():
    """Test YouTube platform integration"""
    logger.info("=== Testing YouTube Platform ===")
    
    try:
        from src.platforms.youtube import YouTubePlatform
        
        # Configure platform
        config = {
            "enabled": True,
            "api_key": os.getenv("YOUTUBE_API_KEY")
        }
        
        if not config["api_key"]:
            logger.warning("❌ YouTube API key not found in environment")
            return False
        
        # Initialize platform
        platform = YouTubePlatform("youtube", config)
        await platform.initialize()
        
        # Test search
        logger.info("Testing YouTube search...")
        results = await platform.search_videos("test audio", max_results=1)
        
        if not results:
            logger.error("❌ No search results returned")
            return False
        
        video = results[0]
        logger.info(f"✅ Search successful: {video['title']}")
        
        # Test stream URL extraction
        logger.info("Testing stream URL extraction...")
        stream_url = await platform.get_stream_url(video['id'])
        
        if not stream_url:
            logger.error("❌ No stream URL extracted")
            return False
        
        logger.info(f"✅ Stream URL extracted: {stream_url[:100]}...")
        return True
        
    except Exception as e:
        logger.error(f"❌ YouTube platform test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_ffmpeg_config():
    """Test FFmpeg configuration"""
    logger.info("=== Testing FFmpeg Configuration ===")
    
    try:
        import subprocess
        
        # Test FFmpeg availability
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("❌ FFmpeg not available")
            return False
        
        logger.info("✅ FFmpeg is available")
        
        # Test audio conversion with Discord-compatible options
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
        cmd = [
            'ffmpeg', '-i', test_url,
            '-vn', '-ar', '48000', '-ac', '2', '-b:a', '128k',
            '-f', 'wav', '-t', '5',  # 5 seconds only
            '/tmp/test_audio.wav', '-y'
        ]
        
        logger.info("Testing FFmpeg audio processing...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info("✅ FFmpeg audio processing successful")
            # Clean up test file
            Path('/tmp/test_audio.wav').unlink(missing_ok=True)
            return True
        else:
            logger.error(f"❌ FFmpeg test failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ FFmpeg test error: {e}")
        return False

async def test_discord_bot_integration():
    """Test Discord bot integration (if token available)"""
    logger.info("=== Testing Discord Bot Integration ===")
    
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.warning("❌ Discord token not found - skipping bot test")
        return False
    
    try:
        import discord
        from discord.ext import commands
        
        # Create minimal bot for testing
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        
        bot = commands.Bot(command_prefix='!', intents=intents)
        
        @bot.event
        async def on_ready():
            logger.info(f"✅ Bot connected as {bot.user}")
            await bot.close()
        
        # Test connection
        await bot.start(token)
        return True
        
    except Exception as e:
        logger.error(f"❌ Discord bot test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🎵 Starting Audio System Diagnostic Tests 🎵")
    
    tests = [
        ("Cookie Extraction", test_cookie_extraction),
        ("YouTube Platform", test_youtube_platform),
        ("FFmpeg Configuration", test_ffmpeg_config),
        ("Discord Bot Integration", test_discord_bot_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("🔍 DIAGNOSTIC RESULTS:")
    logger.info("="*50)
    
    passed = 0
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        logger.info("🎉 All systems operational! Audio should work.")
    else:
        logger.info("⚠️  Some issues detected. See logs above for details.")

if __name__ == "__main__":
    asyncio.run(main())