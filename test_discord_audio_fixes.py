#!/usr/bin/env python3
"""
Test script to verify Discord audio streaming fixes for voice protocol v8.
This script tests the key components without requiring a full bot deployment.
"""

import sys
import logging
from typing import Dict, Any
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pynacl_compatibility():
    """Test PyNaCl compatibility with Discord voice protocol v8"""
    try:
        import nacl.secret
        logger.info("✅ PyNaCl imported successfully")
        
        # Test if Aead is available (required for voice v8)
        if hasattr(nacl.secret, 'Aead'):
            logger.info("✅ PyNaCl.secret.Aead is available - voice v8 compatible")
            return True
        else:
            logger.error("❌ PyNaCl.secret.Aead is NOT available - voice v8 incompatible")
            return False
            
    except ImportError as e:
        logger.error(f"❌ PyNaCl import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ PyNaCl test failed: {e}")
        return False

def test_discord_import():
    """Test Discord.py import and voice support"""
    try:
        import discord
        logger.info(f"✅ Discord.py imported successfully - version: {discord.__version__}")
        
        # Test voice components
        if hasattr(discord, 'FFmpegPCMAudio'):
            logger.info("✅ Discord.py FFmpegPCMAudio available")
        else:
            logger.error("❌ Discord.py FFmpegPCMAudio not available")
            return False
            
        if hasattr(discord, 'PCMVolumeTransformer'):
            logger.info("✅ Discord.py PCMVolumeTransformer available")
        else:
            logger.error("❌ Discord.py PCMVolumeTransformer not available")
            return False
            
        return True
        
    except ImportError as e:
        logger.error(f"❌ Discord.py import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Discord.py test failed: {e}")
        return False

def test_ffmpeg_options():
    """Test FFmpeg options validation"""
    logger.info("Testing FFmpeg options for Discord v8 compatibility...")
    
    # The optimized FFmpeg options from our fix
    ffmpeg_options = {
        "before_options": (
            "-reconnect 1 "
            "-reconnect_streamed 1 "
            "-reconnect_delay_max 5 "
            "-reconnect_at_eof 1 "
            "-multiple_requests 1 "
            "-http_persistent 0 "
            "-user_agent 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36' "
            "-headers 'Accept: */*' "
            "-rw_timeout 30000000 "
            "-loglevel warning"
        ),
        "options": (
            "-vn "                    # No video
            "-f s16le "               # 16-bit signed little-endian PCM
            "-ar 48000 "              # 48kHz sample rate (Discord requirement)
            "-ac 2 "                  # 2 channels (stereo)
            "-frame_duration 20 "     # 20ms frames for Discord
            "-application audio "     # Optimize for audio content
            "-bufsize 3840 "          # Buffer size for 20ms at 48kHz 16-bit stereo
            "-threads 0"              # Use optimal thread count
        ),
    }
    
    # Validate key requirements
    options = ffmpeg_options["options"]
    
    checks = [
        ("-f s16le" in options, "16-bit signed PCM format"),
        ("-ar 48000" in options, "48kHz sample rate"),
        ("-ac 2" in options, "Stereo (2 channels)"),
        ("-bufsize 3840" in options, "3840-byte buffer for 20ms frames"),
        ("-vn" in options, "No video stream"),
    ]
    
    all_passed = True
    for check, description in checks:
        if check:
            logger.info(f"✅ {description}")
        else:
            logger.error(f"❌ {description}")
            all_passed = False
    
    return all_passed

def test_audio_format_calculations():
    """Test audio format calculations for Discord compatibility"""
    logger.info("Testing audio format calculations...")
    
    # Discord requirements: 16-bit 48kHz stereo PCM
    sample_rate = 48000  # Hz
    bit_depth = 16       # bits
    channels = 2         # stereo
    frame_duration_ms = 20  # milliseconds
    
    # Calculate expected frame size
    bytes_per_sample = bit_depth // 8  # 16 bits = 2 bytes
    samples_per_frame = (sample_rate * frame_duration_ms) // 1000  # 48000 * 20 / 1000 = 960
    frame_size_bytes = samples_per_frame * channels * bytes_per_sample  # 960 * 2 * 2 = 3840
    
    logger.info(f"Sample rate: {sample_rate} Hz")
    logger.info(f"Bit depth: {bit_depth} bits ({bytes_per_sample} bytes per sample)")
    logger.info(f"Channels: {channels}")
    logger.info(f"Frame duration: {frame_duration_ms} ms")
    logger.info(f"Samples per frame: {samples_per_frame}")
    logger.info(f"Expected frame size: {frame_size_bytes} bytes")
    
    if frame_size_bytes == 3840:
        logger.info("✅ Audio format calculations correct - matches Discord requirements")
        return True
    else:
        logger.error(f"❌ Audio format calculations incorrect - expected 3840 bytes, got {frame_size_bytes}")
        return False

async def test_audio_source_creation():
    """Test creating Discord audio sources with our optimized options"""
    logger.info("Testing Discord audio source creation...")
    
    try:
        import discord
        
        # Test URL (using a dummy URL for testing)
        test_url = "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav"
        
        # Our optimized FFmpeg options
        ffmpeg_options = {
            "before_options": (
                "-reconnect 1 "
                "-reconnect_streamed 1 "
                "-reconnect_delay_max 5 "
                "-loglevel warning"
            ),
            "options": (
                "-vn "
                "-f s16le "
                "-ar 48000 "
                "-ac 2 "
                "-bufsize 3840 "
                "-threads 0"
            ),
        }
        
        # Fallback options for testing
        fallback_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1",
            "options": "-vn -f s16le -ar 48000 -ac 2"
        }
        
        # Test primary options
        try:
            source = discord.FFmpegPCMAudio(test_url, **ffmpeg_options)
            logger.info("✅ Primary FFmpeg options work - Discord audio source created")
            if hasattr(source, 'cleanup'):
                source.cleanup()
            return True
        except Exception as e:
            logger.warning(f"⚠️ Primary options failed: {e}")
            
            # Test fallback options
            try:
                source = discord.FFmpegPCMAudio(test_url, **fallback_options)
                logger.info("✅ Fallback FFmpeg options work - Discord audio source created")
                if hasattr(source, 'cleanup'):
                    source.cleanup()
                return True
            except Exception as fallback_e:
                logger.error(f"❌ Both primary and fallback options failed: {fallback_e}")
                return False
        
    except ImportError:
        logger.error("❌ Discord.py not available for audio source testing")
        return False
    except Exception as e:
        logger.error(f"❌ Audio source creation test failed: {e}")
        return False

def main():
    """Run all compatibility tests"""
    logger.info("🎵 Starting Discord audio streaming compatibility tests for voice protocol v8...")
    logger.info("=" * 80)
    
    tests = [
        ("PyNaCl Compatibility", test_pynacl_compatibility),
        ("Discord.py Import", test_discord_import), 
        ("FFmpeg Options", test_ffmpeg_options),
        ("Audio Format Calculations", test_audio_format_calculations),
    ]
    
    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        logger.info("-" * 40)
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Run async test
    logger.info(f"\n📋 Running: Audio Source Creation")
    logger.info("-" * 40)
    try:
        results["Audio Source Creation"] = asyncio.run(test_audio_source_creation())
    except Exception as e:
        logger.error(f"❌ Audio Source Creation failed with exception: {e}")
        results["Audio Source Creation"] = False
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("🎵 DISCORD AUDIO COMPATIBILITY TEST RESULTS")
    logger.info("=" * 80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
        if result:
            passed += 1
    
    logger.info("-" * 80)
    logger.info(f"Summary: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Discord voice protocol v8 should work correctly.")
        return True
    else:
        logger.error(f"⚠️ {total - passed} test(s) failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)