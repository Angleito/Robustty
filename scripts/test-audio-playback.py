#!/usr/bin/env python3
"""
Comprehensive Audio Pipeline Diagnostic Script for Robustty

This script tests the complete audio pipeline from YouTube URL extraction
to Discord audio format validation, helping identify where failures occur.

Usage:
    python scripts/test-audio-playback.py [youtube-url]
    python scripts/test-audio-playback.py --test-all
    python scripts/test-audio-playback.py --help

Examples:
    python scripts/test-audio-playback.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    python scripts/test-audio-playback.py --test-all
"""

import asyncio
import logging
import sys
import argparse
import os
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import traceback

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import aiohttp
    import yt_dlp
    import discord
    import ffmpeg
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Please install requirements: pip install -r requirements.txt")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('audio_pipeline_test.log')
    ]
)
logger = logging.getLogger(__name__)

# Test YouTube URLs for comprehensive testing
TEST_URLS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll - common test
    "https://youtu.be/dQw4w9WgXcQ",  # Short URL format
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # Me at the zoo - first YouTube video
    "https://www.youtube.com/watch?v=9bZkp7q19f0",  # PSY - Gangnam Style
]

class AudioPipelineTester:
    """Comprehensive audio pipeline testing class"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "config.yaml"
        self.results: Dict[str, Dict] = {}
        self.temp_dir = tempfile.mkdtemp(prefix="audio_test_")
        self.cookie_paths = [
            "/app/cookies/youtube_cookies.json",
            "data/cookies/youtube_cookies.json", 
            "./cookies/youtube_cookies.json",
            "cookies/youtube_cookies.json"
        ]
        
    async def run_full_test(self, url: str) -> Dict[str, any]:
        """Run complete audio pipeline test for a given URL"""
        test_results = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "tests": {}
        }
        
        logger.info(f"Starting full audio pipeline test for: {url}")
        
        try:
            # Test 1: URL validation and ID extraction
            test_results["tests"]["url_validation"] = await self._test_url_validation(url)
            
            # Test 2: YouTube platform initialization
            test_results["tests"]["platform_init"] = await self._test_platform_initialization()
            
            # Test 3: Cookie extraction and validation
            test_results["tests"]["cookie_validation"] = await self._test_cookie_validation()
            
            # Test 4: yt-dlp stream URL extraction
            test_results["tests"]["stream_extraction"] = await self._test_stream_extraction(url)
            
            # Test 5: FFmpeg compatibility check
            test_results["tests"]["ffmpeg_compatibility"] = await self._test_ffmpeg_compatibility(
                test_results["tests"]["stream_extraction"].get("stream_url")
            )
            
            # Test 6: Discord audio format validation
            test_results["tests"]["discord_audio_format"] = await self._test_discord_audio_format(
                test_results["tests"]["stream_extraction"].get("stream_url")
            )
            
            # Test 7: Network connectivity and reliability
            test_results["tests"]["network_reliability"] = await self._test_network_reliability(
                test_results["tests"]["stream_extraction"].get("stream_url")
            )
            
            # Test 8: Error handling and recovery
            test_results["tests"]["error_handling"] = await self._test_error_handling()
            
            # Generate summary
            test_results["summary"] = self._generate_test_summary(test_results["tests"])
            
        except Exception as e:
            logger.error(f"Critical failure in audio pipeline test: {e}")
            test_results["critical_error"] = str(e)
            test_results["traceback"] = traceback.format_exc()
            
        self.results[url] = test_results
        return test_results
    
    async def _test_url_validation(self, url: str) -> Dict[str, any]:
        """Test URL validation and video ID extraction"""
        logger.info("Testing URL validation...")
        
        result = {
            "status": "success",
            "url": url,
            "issues": []
        }
        
        try:
            # Import YouTube platform for URL validation
            from platforms.youtube import YouTubePlatform
            
            # Create platform instance with dummy config
            platform = YouTubePlatform("youtube", {"enabled": True})
            
            # Test URL validation
            if not platform.is_platform_url(url):
                result["status"] = "failed"
                result["issues"].append("URL not recognized as YouTube URL")
                return result
            
            # Test video ID extraction
            video_id = platform.extract_video_id(url)
            if not video_id:
                result["status"] = "failed"
                result["issues"].append("Could not extract video ID from URL")
                return result
            
            result["video_id"] = video_id
            logger.info(f"✓ URL validation passed, video ID: {video_id}")
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["issues"].append(f"URL validation error: {e}")
            logger.error(f"✗ URL validation failed: {e}")
            
        return result
    
    async def _test_platform_initialization(self) -> Dict[str, any]:
        """Test YouTube platform initialization"""
        logger.info("Testing platform initialization...")
        
        result = {
            "status": "success",
            "issues": []
        }
        
        try:
            # Load environment variables
            load_dotenv()
            
            # Check for YouTube API key
            api_key = os.getenv("YOUTUBE_API_KEY")
            if not api_key:
                result["status"] = "warning"
                result["issues"].append("YouTube API key not found in environment")
                logger.warning("⚠ YouTube API key not configured")
            else:
                result["api_key_configured"] = True
                logger.info("✓ YouTube API key found")
            
            # Test platform initialization
            from platforms.youtube import YouTubePlatform
            
            config = {"enabled": True}
            if api_key:
                config["api_key"] = api_key
                
            platform = YouTubePlatform("youtube", config)
            await platform.initialize()
            
            result["platform_initialized"] = True
            logger.info("✓ Platform initialization successful")
            
            # Cleanup
            await platform.cleanup()
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["issues"].append(f"Platform initialization error: {e}")
            logger.error(f"✗ Platform initialization failed: {e}")
            
        return result
    
    async def _test_cookie_validation(self) -> Dict[str, any]:
        """Test cookie extraction and validation"""
        logger.info("Testing cookie validation...")
        
        result = {
            "status": "success",
            "issues": [],
            "cookies_found": []
        }
        
        try:
            # Check for existing cookie files
            for cookie_path in self.cookie_paths:
                if Path(cookie_path).exists():
                    result["cookies_found"].append(cookie_path)
                    logger.info(f"✓ Found cookie file: {cookie_path}")
                    
                    # Validate cookie file content
                    try:
                        with open(cookie_path, 'r') as f:
                            cookies = json.load(f)
                            if isinstance(cookies, list) and len(cookies) > 0:
                                result["valid_cookies"] = len(cookies)
                                logger.info(f"✓ Cookie file contains {len(cookies)} cookies")
                            else:
                                result["issues"].append(f"Cookie file {cookie_path} is empty or invalid")
                    except Exception as e:
                        result["issues"].append(f"Cookie file {cookie_path} is corrupted: {e}")
            
            if not result["cookies_found"]:
                result["status"] = "warning"
                result["issues"].append("No YouTube cookies found")
                logger.warning("⚠ No YouTube cookies found - may affect stream quality")
            
            # Test cookie conversion
            from platforms.youtube import YouTubePlatform
            platform = YouTubePlatform("youtube", {"enabled": True})
            
            if result["cookies_found"]:
                json_cookie_file = result["cookies_found"][0]
                netscape_cookie_file = Path(self.temp_dir) / "test_cookies.txt"
                
                if platform._convert_cookies_to_netscape(str(json_cookie_file), str(netscape_cookie_file)):
                    result["cookie_conversion"] = "success"
                    logger.info("✓ Cookie conversion successful")
                else:
                    result["cookie_conversion"] = "failed"
                    result["issues"].append("Cookie conversion to Netscape format failed")
                    logger.error("✗ Cookie conversion failed")
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["issues"].append(f"Cookie validation error: {e}")
            logger.error(f"✗ Cookie validation failed: {e}")
            
        return result
    
    async def _test_stream_extraction(self, url: str) -> Dict[str, any]:
        """Test yt-dlp stream URL extraction"""
        logger.info("Testing stream extraction...")
        
        result = {
            "status": "success",
            "issues": [],
            "url": url
        }
        
        try:
            # Configure yt-dlp options
            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
                "quiet": True,
                "no_warnings": False,
                "noplaylist": True,
                "extract_flat": False,
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "http_chunk_size": 10485760,
                "prefer_insecure": False,
                "verbose": False,
            }
            
            # Add cookies if available
            for cookie_path in self.cookie_paths:
                if Path(cookie_path).exists():
                    netscape_cookie_file = Path(self.temp_dir) / "cookies.txt"
                    
                    # Convert cookies to netscape format
                    from platforms.youtube import YouTubePlatform
                    platform = YouTubePlatform("youtube", {"enabled": True})
                    
                    if platform._convert_cookies_to_netscape(cookie_path, str(netscape_cookie_file)):
                        ydl_opts["cookiefile"] = str(netscape_cookie_file)
                        result["cookies_used"] = cookie_path
                        logger.info(f"Using cookies from: {cookie_path}")
                        break
            
            # Extract stream information
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    result["status"] = "failed"
                    result["issues"].append("yt-dlp returned no information")
                    return result
                
                # Extract stream URL
                stream_url = None
                
                if "url" in info:
                    stream_url = info["url"]
                elif "formats" in info and info["formats"]:
                    formats = info["formats"]
                    
                    # Find best audio format
                    audio_formats = [
                        f for f in formats 
                        if f.get("vcodec") == "none" and f.get("url")
                    ]
                    
                    if audio_formats:
                        # Prefer direct URLs over HLS/DASH
                        direct_formats = [
                            f for f in audio_formats
                            if not any(x in f.get("url", "") for x in ["m3u8", "mpd", "manifest"])
                        ]
                        
                        if direct_formats:
                            direct_formats.sort(key=lambda f: f.get("abr", 0), reverse=True)
                            stream_url = direct_formats[0]["url"]
                            result["format_type"] = "direct"
                        else:
                            audio_formats.sort(key=lambda f: f.get("abr", 0), reverse=True)
                            stream_url = audio_formats[0]["url"]
                            result["format_type"] = "hls"
                    else:
                        # Fallback to any available format
                        valid_formats = [f for f in formats if f.get("url")]
                        if valid_formats:
                            stream_url = valid_formats[-1]["url"]
                            result["format_type"] = "fallback"
                
                if stream_url:
                    result["stream_url"] = stream_url
                    result["title"] = info.get("title", "Unknown")
                    result["duration"] = info.get("duration", 0)
                    result["uploader"] = info.get("uploader", "Unknown")
                    logger.info(f"✓ Stream URL extracted: {stream_url[:100]}...")
                else:
                    result["status"] = "failed"
                    result["issues"].append("No valid stream URL found")
                    logger.error("✗ No valid stream URL found")
                
        except yt_dlp.DownloadError as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["issues"].append(f"yt-dlp download error: {e}")
            logger.error(f"✗ yt-dlp download error: {e}")
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["issues"].append(f"Stream extraction error: {e}")
            logger.error(f"✗ Stream extraction failed: {e}")
            
        return result
    
    async def _test_ffmpeg_compatibility(self, stream_url: Optional[str]) -> Dict[str, any]:
        """Test FFmpeg compatibility with extracted stream"""
        logger.info("Testing FFmpeg compatibility...")
        
        result = {
            "status": "success",
            "issues": []
        }
        
        if not stream_url:
            result["status"] = "skipped"
            result["issues"].append("No stream URL available for FFmpeg test")
            return result
        
        try:
            # Check if FFmpeg is available
            try:
                ffmpeg_version = subprocess.run(
                    ["ffmpeg", "-version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if ffmpeg_version.returncode == 0:
                    result["ffmpeg_available"] = True
                    result["ffmpeg_version"] = ffmpeg_version.stdout.split('\n')[0]
                    logger.info(f"✓ FFmpeg available: {result['ffmpeg_version']}")
                else:
                    result["status"] = "failed"
                    result["issues"].append("FFmpeg not available")
                    return result
            except subprocess.TimeoutExpired:
                result["status"] = "failed"
                result["issues"].append("FFmpeg version check timed out")
                return result
            except FileNotFoundError:
                result["status"] = "failed"
                result["issues"].append("FFmpeg not found in PATH")
                return result
            
            # Test FFmpeg with stream URL (probe only, no download)
            probe_cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                "-rw_timeout", "10000000",  # 10 seconds
                stream_url
            ]
            
            try:
                probe_result = subprocess.run(
                    probe_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if probe_result.returncode == 0:
                    probe_data = json.loads(probe_result.stdout)
                    result["probe_success"] = True
                    result["format_info"] = probe_data.get("format", {})
                    result["streams"] = probe_data.get("streams", [])
                    
                    # Analyze audio streams
                    audio_streams = [s for s in result["streams"] if s.get("codec_type") == "audio"]
                    if audio_streams:
                        result["audio_streams"] = len(audio_streams)
                        result["audio_codec"] = audio_streams[0].get("codec_name")
                        result["sample_rate"] = audio_streams[0].get("sample_rate")
                        result["channels"] = audio_streams[0].get("channels")
                        logger.info(f"✓ FFmpeg probe successful - {result['audio_codec']} audio")
                    else:
                        result["issues"].append("No audio streams found in probe")
                        logger.warning("⚠ No audio streams detected")
                else:
                    result["status"] = "failed"
                    result["issues"].append(f"FFmpeg probe failed: {probe_result.stderr}")
                    logger.error(f"✗ FFmpeg probe failed: {probe_result.stderr}")
                    
            except subprocess.TimeoutExpired:
                result["status"] = "failed"
                result["issues"].append("FFmpeg probe timed out")
                logger.error("✗ FFmpeg probe timed out")
            except json.JSONDecodeError:
                result["status"] = "failed"
                result["issues"].append("FFmpeg probe returned invalid JSON")
                logger.error("✗ FFmpeg probe returned invalid JSON")
            
            # Test Discord-specific FFmpeg options
            if result.get("probe_success"):
                discord_ffmpeg_cmd = [
                    "ffmpeg",
                    "-reconnect", "1",
                    "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "5",
                    "-i", stream_url,
                    "-vn",
                    "-ar", "48000",
                    "-ac", "2",
                    "-b:a", "128k",
                    "-f", "wav",
                    "-t", "1",  # Only test 1 second
                    "-y",
                    f"{self.temp_dir}/discord_test.wav"
                ]
                
                try:
                    discord_test = subprocess.run(
                        discord_ffmpeg_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if discord_test.returncode == 0:
                        result["discord_ffmpeg_test"] = "success"
                        logger.info("✓ Discord FFmpeg options test passed")
                    else:
                        result["discord_ffmpeg_test"] = "failed"
                        result["issues"].append(f"Discord FFmpeg test failed: {discord_test.stderr}")
                        logger.error(f"✗ Discord FFmpeg test failed: {discord_test.stderr}")
                        
                except subprocess.TimeoutExpired:
                    result["discord_ffmpeg_test"] = "timeout"
                    result["issues"].append("Discord FFmpeg test timed out")
                    logger.error("✗ Discord FFmpeg test timed out")
                    
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["issues"].append(f"FFmpeg compatibility test error: {e}")
            logger.error(f"✗ FFmpeg compatibility test failed: {e}")
            
        return result
    
    async def _test_discord_audio_format(self, stream_url: Optional[str]) -> Dict[str, any]:
        """Test Discord audio format compatibility"""
        logger.info("Testing Discord audio format...")
        
        result = {
            "status": "success",
            "issues": []
        }
        
        if not stream_url:
            result["status"] = "skipped"
            result["issues"].append("No stream URL available for Discord format test")
            return result
        
        try:
            # Test Discord FFmpegPCMAudio creation (without actually playing)
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
                    "-vn -ar 48000 -ac 2 -b:a 128k -bufsize 512k -maxrate 256k"
                ),
            }
            
            # Create FFmpegPCMAudio source (this validates the format)
            try:
                source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)
                result["discord_source_created"] = True
                logger.info("✓ Discord FFmpegPCMAudio source created successfully")
                
                # Test PCMVolumeTransformer
                try:
                    transformed_source = discord.PCMVolumeTransformer(source, volume=0.5)
                    result["volume_transformer_created"] = True
                    logger.info("✓ Discord PCMVolumeTransformer created successfully")
                    
                    # Cleanup
                    if hasattr(transformed_source, 'cleanup'):
                        transformed_source.cleanup()
                    if hasattr(source, 'cleanup'):
                        source.cleanup()
                        
                except Exception as e:
                    result["issues"].append(f"Volume transformer creation failed: {e}")
                    logger.error(f"✗ Volume transformer creation failed: {e}")
                    
            except Exception as e:
                result["status"] = "failed"
                result["issues"].append(f"Discord audio source creation failed: {e}")
                logger.error(f"✗ Discord audio source creation failed: {e}")
                
            # Test Discord audio format requirements
            result["format_requirements"] = {
                "sample_rate": "48000 Hz",
                "channels": "2 (stereo)",
                "bitrate": "128k",
                "format": "PCM"
            }
            
            logger.info("✓ Discord audio format requirements documented")
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["issues"].append(f"Discord audio format test error: {e}")
            logger.error(f"✗ Discord audio format test failed: {e}")
            
        return result
    
    async def _test_network_reliability(self, stream_url: Optional[str]) -> Dict[str, any]:
        """Test network connectivity and stream reliability"""
        logger.info("Testing network reliability...")
        
        result = {
            "status": "success",
            "issues": [],
            "tests_performed": []
        }
        
        if not stream_url:
            result["status"] = "skipped"
            result["issues"].append("No stream URL available for network test")
            return result
        
        try:
            # Test basic connectivity
            async with aiohttp.ClientSession() as session:
                # Test 1: HEAD request
                try:
                    async with session.head(stream_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        result["head_request"] = {
                            "status": response.status,
                            "headers": dict(response.headers),
                            "success": response.status < 400
                        }
                        result["tests_performed"].append("head_request")
                        
                        if response.status < 400:
                            logger.info(f"✓ HEAD request successful: {response.status}")
                        else:
                            result["issues"].append(f"HEAD request failed: {response.status}")
                            logger.error(f"✗ HEAD request failed: {response.status}")
                            
                except asyncio.TimeoutError:
                    result["head_request"] = {"success": False, "error": "timeout"}
                    result["issues"].append("HEAD request timed out")
                    logger.error("✗ HEAD request timed out")
                
                # Test 2: Partial content download
                try:
                    headers = {"Range": "bytes=0-1023"}  # First 1KB
                    async with session.get(
                        stream_url, 
                        headers=headers, 
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        if response.status in [200, 206]:  # OK or Partial Content
                            content = await response.read()
                            result["partial_download"] = {
                                "status": response.status,
                                "bytes_received": len(content),
                                "success": True
                            }
                            logger.info(f"✓ Partial download successful: {len(content)} bytes")
                        else:
                            result["partial_download"] = {
                                "status": response.status,
                                "success": False
                            }
                            result["issues"].append(f"Partial download failed: {response.status}")
                            logger.error(f"✗ Partial download failed: {response.status}")
                            
                        result["tests_performed"].append("partial_download")
                        
                except asyncio.TimeoutError:
                    result["partial_download"] = {"success": False, "error": "timeout"}
                    result["issues"].append("Partial download timed out")
                    logger.error("✗ Partial download timed out")
                
                # Test 3: Multiple requests (reliability test)
                success_count = 0
                total_requests = 3
                
                for i in range(total_requests):
                    try:
                        async with session.head(
                            stream_url, 
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            if response.status < 400:
                                success_count += 1
                    except:
                        pass
                
                result["reliability_test"] = {
                    "successful_requests": success_count,
                    "total_requests": total_requests,
                    "success_rate": success_count / total_requests
                }
                result["tests_performed"].append("reliability_test")
                
                if success_count == total_requests:
                    logger.info(f"✓ Reliability test: {success_count}/{total_requests} successful")
                else:
                    result["issues"].append(f"Reliability test: only {success_count}/{total_requests} successful")
                    logger.warning(f"⚠ Reliability test: only {success_count}/{total_requests} successful")
                    
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["issues"].append(f"Network reliability test error: {e}")
            logger.error(f"✗ Network reliability test failed: {e}")
            
        return result
    
    async def _test_error_handling(self) -> Dict[str, any]:
        """Test error handling and recovery mechanisms"""
        logger.info("Testing error handling...")
        
        result = {
            "status": "success",
            "issues": [],
            "tests_performed": []
        }
        
        try:
            # Test 1: Invalid URL handling
            try:
                from platforms.youtube import YouTubePlatform
                platform = YouTubePlatform("youtube", {"enabled": True})
                
                invalid_urls = [
                    "https://invalid-url.com/watch?v=invalid",
                    "not-a-url-at-all",
                    "https://youtube.com/watch?v=",  # Empty video ID
                ]
                
                for invalid_url in invalid_urls:
                    try:
                        video_id = platform.extract_video_id(invalid_url)
                        if video_id:
                            result["issues"].append(f"Invalid URL {invalid_url} incorrectly parsed as valid")
                    except Exception:
                        pass  # Expected to fail
                
                result["invalid_url_handling"] = "success"
                result["tests_performed"].append("invalid_url_handling")
                logger.info("✓ Invalid URL handling test passed")
                
            except Exception as e:
                result["invalid_url_handling"] = "failed"
                result["issues"].append(f"Invalid URL handling test failed: {e}")
                logger.error(f"✗ Invalid URL handling test failed: {e}")
            
            # Test 2: yt-dlp error handling
            try:
                ydl_opts = {
                    "format": "bestaudio",
                    "quiet": True,
                    "no_warnings": True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        # Try to extract from a non-existent video
                        info = ydl.extract_info("https://www.youtube.com/watch?v=nonexistent123", download=False)
                        result["issues"].append("Non-existent video extraction should have failed")
                    except yt_dlp.DownloadError:
                        # Expected error
                        pass
                    except Exception as e:
                        result["issues"].append(f"Unexpected error type for non-existent video: {e}")
                
                result["ytdlp_error_handling"] = "success"
                result["tests_performed"].append("ytdlp_error_handling")
                logger.info("✓ yt-dlp error handling test passed")
                
            except Exception as e:
                result["ytdlp_error_handling"] = "failed"
                result["issues"].append(f"yt-dlp error handling test failed: {e}")
                logger.error(f"✗ yt-dlp error handling test failed: {e}")
            
            # Test 3: Network timeout handling
            try:
                async with aiohttp.ClientSession() as session:
                    try:
                        # Try to connect to a non-responsive endpoint with short timeout
                        async with session.get(
                            "http://httpbin.org/delay/10",  # 10 second delay
                            timeout=aiohttp.ClientTimeout(total=1)  # 1 second timeout
                        ) as response:
                            result["issues"].append("Timeout test should have failed")
                    except asyncio.TimeoutError:
                        # Expected timeout
                        pass
                    except Exception as e:
                        result["issues"].append(f"Unexpected error type for timeout test: {e}")
                
                result["timeout_handling"] = "success"
                result["tests_performed"].append("timeout_handling")
                logger.info("✓ Network timeout handling test passed")
                
            except Exception as e:
                result["timeout_handling"] = "failed"
                result["issues"].append(f"Network timeout handling test failed: {e}")
                logger.error(f"✗ Network timeout handling test failed: {e}")
                
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["issues"].append(f"Error handling test failed: {e}")
            logger.error(f"✗ Error handling test failed: {e}")
            
        return result
    
    def _generate_test_summary(self, tests: Dict[str, Dict]) -> Dict[str, any]:
        """Generate a summary of all test results"""
        summary = {
            "total_tests": len(tests),
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "skipped": 0,
            "critical_issues": [],
            "recommendations": []
        }
        
        for test_name, test_result in tests.items():
            status = test_result.get("status", "unknown")
            
            if status == "success":
                summary["passed"] += 1
            elif status == "failed":
                summary["failed"] += 1
                summary["critical_issues"].extend(test_result.get("issues", []))
            elif status == "warning":
                summary["warnings"] += 1
            elif status == "skipped":
                summary["skipped"] += 1
        
        # Generate recommendations based on test results
        if tests.get("cookie_validation", {}).get("status") == "warning":
            summary["recommendations"].append(
                "Configure YouTube cookies for better stream quality and reliability"
            )
        
        if tests.get("ffmpeg_compatibility", {}).get("status") == "failed":
            summary["recommendations"].append(
                "Install or update FFmpeg for audio processing"
            )
        
        if tests.get("platform_init", {}).get("status") == "warning":
            summary["recommendations"].append(
                "Configure YouTube API key for search functionality"
            )
        
        if tests.get("network_reliability", {}).get("reliability_test", {}).get("success_rate", 1) < 0.8:
            summary["recommendations"].append(
                "Check network connectivity and consider using a more stable connection"
            )
        
        return summary
    
    def generate_report(self) -> str:
        """Generate a comprehensive test report"""
        report = []
        report.append("=" * 80)
        report.append("ROBUSTTY AUDIO PIPELINE DIAGNOSTIC REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")
        
        for url, test_results in self.results.items():
            report.append(f"URL: {url}")
            report.append("-" * 80)
            
            if "critical_error" in test_results:
                report.append(f"CRITICAL ERROR: {test_results['critical_error']}")
                report.append("")
                continue
            
            summary = test_results.get("summary", {})
            report.append(f"Test Summary:")
            report.append(f"  Total Tests: {summary.get('total_tests', 0)}")
            report.append(f"  Passed: {summary.get('passed', 0)}")
            report.append(f"  Failed: {summary.get('failed', 0)}")
            report.append(f"  Warnings: {summary.get('warnings', 0)}")
            report.append(f"  Skipped: {summary.get('skipped', 0)}")
            report.append("")
            
            # Detailed test results
            tests = test_results.get("tests", {})
            
            for test_name, test_result in tests.items():
                status = test_result.get("status", "unknown")
                status_symbol = {
                    "success": "✓",
                    "failed": "✗",
                    "warning": "⚠",
                    "skipped": "○"
                }.get(status, "?")
                
                report.append(f"{status_symbol} {test_name.replace('_', ' ').title()}: {status.upper()}")
                
                if test_result.get("issues"):
                    for issue in test_result["issues"]:
                        report.append(f"    - {issue}")
                
                if test_result.get("error"):
                    report.append(f"    Error: {test_result['error']}")
                
                report.append("")
            
            # Recommendations
            if summary.get("recommendations"):
                report.append("Recommendations:")
                for rec in summary["recommendations"]:
                    report.append(f"  • {rec}")
                report.append("")
            
            # Critical issues
            if summary.get("critical_issues"):
                report.append("Critical Issues:")
                for issue in summary["critical_issues"]:
                    report.append(f"  • {issue}")
                report.append("")
            
            report.append("=" * 80)
            report.append("")
        
        return "\n".join(report)
    
    def cleanup(self):
        """Cleanup temporary files"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            logger.info("Temporary files cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up temporary files: {e}")

async def main():
    """Main function to run audio pipeline tests"""
    parser = argparse.ArgumentParser(
        description="Robustty Audio Pipeline Diagnostic Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/test-audio-playback.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  python scripts/test-audio-playback.py --test-all
  python scripts/test-audio-playback.py --test-all --output report.txt
        """
    )
    
    parser.add_argument(
        "url",
        nargs="?",
        help="YouTube URL to test (optional if using --test-all)"
    )
    
    parser.add_argument(
        "--test-all",
        action="store_true",
        help="Test multiple URLs for comprehensive validation"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for test report (default: print to console)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate arguments
    if not args.url and not args.test_all:
        parser.error("Either provide a URL or use --test-all")
    
    # Initialize tester
    tester = AudioPipelineTester()
    
    try:
        # Run tests
        if args.test_all:
            logger.info("Running comprehensive audio pipeline tests...")
            for url in TEST_URLS:
                logger.info(f"Testing URL: {url}")
                await tester.run_full_test(url)
        else:
            logger.info(f"Testing single URL: {args.url}")
            await tester.run_full_test(args.url)
        
        # Generate report
        report = tester.generate_report()
        
        # Output report
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            logger.info(f"Report saved to: {args.output}")
        else:
            print(report)
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        logger.debug(traceback.format_exc())
    finally:
        tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())