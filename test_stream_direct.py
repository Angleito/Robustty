#!/usr/bin/env python3
"""
Direct stream test to verify stream URL extraction and Discord audio processing
"""

import asyncio
import logging
import discord
from io import StringIO
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_stream_url_extraction():
    """Test direct stream URL extraction"""
    logger.info("=== Testing Stream URL Extraction ===")
    
    try:
        from src.platforms.youtube import YouTubePlatform
        import os
        
        # Initialize platform
        config = {
            "enabled": True,
            "api_key": os.getenv("YOUTUBE_API_KEY")
        }
        
        platform = YouTubePlatform("youtube", config)
        await platform.initialize()
        
        # Test with a known working video ID
        test_video_id = "dQw4w9WgXcQ"  # Rick Roll
        logger.info(f"Testing stream extraction for video ID: {test_video_id}")
        
        stream_url = await platform.get_stream_url(test_video_id)
        
        if stream_url:
            logger.info(f"✅ Stream URL extracted successfully")
            logger.info(f"URL: {stream_url[:100]}...")
            return stream_url
        else:
            logger.error("❌ No stream URL extracted")
            return None
            
    except Exception as e:
        logger.error(f"❌ Stream extraction failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def test_discord_audio_source(stream_url):
    """Test Discord audio source creation"""
    logger.info("=== Testing Discord Audio Source ===")
    
    try:
        # Test FFmpeg options that the bot uses
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -loglevel info",
            "options": "-vn -ar 48000 -ac 2 -b:a 128k",
        }
        
        logger.info("Creating Discord FFmpeg audio source...")
        source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)
        
        # If we get here without exception, the source was created successfully
        logger.info("✅ Discord audio source created successfully")
        
        # Test volume transformer
        transformed_source = discord.PCMVolumeTransformer(source, volume=1.0)
        logger.info("✅ Volume transformer created successfully")
        
        # Clean up
        source.cleanup()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Discord audio source creation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_ffmpeg_direct(stream_url):
    """Test FFmpeg directly with the stream URL"""
    logger.info("=== Testing FFmpeg Direct Processing ===")
    
    try:
        import subprocess
        
        # Test the exact FFmpeg command that Discord.py would use
        cmd = [
            'ffmpeg',
            '-reconnect', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5',
            '-loglevel', 'info',
            '-i', stream_url,
            '-vn',
            '-ar', '48000',
            '-ac', '2',
            '-b:a', '128k',
            '-f', 's16le',  # Discord PCM format
            '-t', '5',  # Only 5 seconds
            '-'  # Output to stdout
        ]
        
        logger.info("Running FFmpeg with Discord-compatible options...")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False  # Binary output
        )
        
        # Read a small amount of output to verify it works
        output, error = process.communicate(timeout=15)
        
        if process.returncode == 0 and len(output) > 0:
            logger.info(f"✅ FFmpeg processed {len(output)} bytes of audio data")
            return True
        else:
            logger.error(f"❌ FFmpeg failed with return code {process.returncode}")
            logger.error(f"FFmpeg stderr: {error.decode()}")
            return False
            
    except subprocess.TimeoutExpired:
        process.kill()
        logger.error("❌ FFmpeg test timed out")
        return False
    except Exception as e:
        logger.error(f"❌ FFmpeg direct test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🎵 Starting Direct Stream Audio Tests 🎵")
    
    # Test 1: Extract stream URL
    stream_url = await test_stream_url_extraction()
    if not stream_url:
        logger.error("Cannot proceed without stream URL")
        return
    
    # Test 2: Test Discord audio source creation
    discord_test = await test_discord_audio_source(stream_url)
    
    # Test 3: Test FFmpeg direct processing
    ffmpeg_test = await test_ffmpeg_direct(stream_url)
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("🔍 DIRECT STREAM TEST RESULTS:")
    logger.info("="*50)
    logger.info(f"Stream URL Extraction: ✅ PASS")
    logger.info(f"Discord Audio Source: {'✅ PASS' if discord_test else '❌ FAIL'}")
    logger.info(f"FFmpeg Direct Processing: {'✅ PASS' if ffmpeg_test else '❌ FAIL'}")
    
    if discord_test and ffmpeg_test:
        logger.info("🎉 Audio pipeline is fully functional!")
        logger.info("The bot should be able to play audio in Discord voice channels.")
    else:
        logger.info("⚠️ Some audio pipeline components failed.")

if __name__ == "__main__":
    asyncio.run(main())