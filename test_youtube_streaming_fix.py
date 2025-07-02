#!/usr/bin/env python3
"""
YouTube Streaming Pipeline Diagnostic Tool
=========================================

This script comprehensively tests the YouTube audio streaming pipeline
to identify issues preventing videos from playing in Discord voice channels.

ANALYSIS AREAS:
1. Cookie system health and authentication
2. yt-dlp configuration and stream URL extraction
3. FFmpeg configuration and audio format handling
4. Stream URL validation and accessibility
5. Discord voice connection compatibility
6. Error handling and fallback mechanisms

Usage:
    python test_youtube_streaming_fix.py [video_id]
    
Example:
    python test_youtube_streaming_fix.py dQw4w9WgXcQ
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import tempfile
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class YouTubeStreamingDiagnostic:
    """Comprehensive YouTube streaming diagnostic tool"""
    
    def __init__(self):
        self.test_video_id = "dQw4w9WgXcQ"  # Never Gonna Give You Up - public domain test
        self.cookie_paths = [
            Path("/app/cookies"),
            Path("data/cookies"), 
            Path("./cookies"),
            Path("cookies"),
        ]
        self.results = {
            "cookie_system": {},
            "yt_dlp_config": {},
            "stream_extraction": {},
            "ffmpeg_compatibility": {},
            "discord_compatibility": {},
            "overall_health": "unknown"
        }
    
    def print_header(self):
        """Print diagnostic header"""
        print("=" * 80)
        print("🎵 YouTube Streaming Pipeline Diagnostic Tool")
        print("=" * 80)
        print(f"Test Video ID: {self.test_video_id}")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 80)
    
    def check_dependencies(self):
        """Check if required dependencies are available"""
        print("\n📦 DEPENDENCY CHECK")
        print("-" * 40)
        
        dependencies = {
            "yt-dlp": False,
            "ffmpeg": False,
            "discord.py": False,
            "aiohttp": False
        }
        
        # Check yt-dlp
        try:
            import yt_dlp
            dependencies["yt-dlp"] = True
            print(f"✅ yt-dlp: {yt_dlp.version.__version__}")
        except ImportError as e:
            print(f"❌ yt-dlp: Not available - {e}")
        
        # Check FFmpeg
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                dependencies["ffmpeg"] = True
                version_line = result.stdout.split('\n')[0]
                print(f"✅ FFmpeg: {version_line}")
            else:
                print(f"❌ FFmpeg: Command failed")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"❌ FFmpeg: Not available - {e}")
        
        # Check Discord.py
        try:
            import discord
            dependencies["discord.py"] = True
            print(f"✅ discord.py: {discord.__version__}")
        except ImportError as e:
            print(f"❌ discord.py: Not available - {e}")
        
        # Check aiohttp
        try:
            import aiohttp
            dependencies["aiohttp"] = True
            print(f"✅ aiohttp: {aiohttp.__version__}")
        except ImportError as e:
            print(f"❌ aiohttp: Not available - {e}")
        
        missing_deps = [k for k, v in dependencies.items() if not v]
        if missing_deps:
            print(f"\n⚠️  Missing dependencies: {', '.join(missing_deps)}")
            return False
        return True
    
    def analyze_cookie_system(self):
        """Analyze cookie system health"""
        print("\n🍪 COOKIE SYSTEM ANALYSIS")
        print("-" * 40)
        
        cookie_results = {
            "paths_found": [],
            "paths_missing": [],
            "cookie_files": {},
            "conversion_status": {},
            "health_issues": []
        }
        
        for path in self.cookie_paths:
            youtube_json = path / "youtube_cookies.json"
            youtube_txt = path / "youtube_cookies.txt"
            
            if path.exists():
                cookie_results["paths_found"].append(str(path))
                print(f"✅ Path exists: {path}")
                
                if youtube_json.exists():
                    try:
                        with open(youtube_json, 'r') as f:
                            cookies = json.load(f)
                        
                        file_stat = youtube_json.stat()
                        file_age_hours = (time.time() - file_stat.st_mtime) / 3600
                        
                        cookie_info = {
                            "path": str(youtube_json),
                            "size": file_stat.st_size,
                            "age_hours": file_age_hours,
                            "cookie_count": len(cookies) if isinstance(cookies, list) else 0,
                            "has_auth_cookies": self._check_auth_cookies(cookies),
                            "valid": True
                        }
                        
                        cookie_results["cookie_files"][str(path)] = cookie_info
                        
                        print(f"  📄 JSON cookies: {len(cookies)} cookies, {file_age_hours:.1f}h old")
                        
                        if file_age_hours > 24:
                            cookie_results["health_issues"].append(f"Cookies in {path} are {file_age_hours:.1f}h old")
                        
                        if not cookie_info["has_auth_cookies"]:
                            cookie_results["health_issues"].append(f"No authentication cookies found in {path}")
                        
                    except Exception as e:
                        print(f"  ❌ JSON cookies: Error reading - {e}")
                        cookie_results["health_issues"].append(f"Cannot read JSON cookies in {path}: {e}")
                else:
                    print(f"  ❌ JSON cookies: Not found")
                
                if youtube_txt.exists():
                    file_stat = youtube_txt.stat()
                    print(f"  📄 Netscape cookies: {file_stat.st_size} bytes")
                else:
                    print(f"  ❌ Netscape cookies: Not found")
            else:
                cookie_results["paths_missing"].append(str(path))
                print(f"❌ Path missing: {path}")
        
        self.results["cookie_system"] = cookie_results
        
        if cookie_results["health_issues"]:
            print(f"\n⚠️  Cookie Issues Found:")
            for issue in cookie_results["health_issues"]:
                print(f"   • {issue}")
        
        return len(cookie_results["paths_found"]) > 0
    
    def _check_auth_cookies(self, cookies) -> bool:
        """Check if authentication cookies are present"""
        if not isinstance(cookies, list):
            return False
        
        auth_cookie_names = {
            "SAPISID", "HSID", "SSID", "APISID", "SID",
            "__Secure-1PAPISID", "__Secure-3PAPISID", 
            "__Secure-1PSID", "__Secure-3PSID"
        }
        
        found_cookies = set()
        for cookie in cookies:
            if isinstance(cookie, dict) and cookie.get("name") in auth_cookie_names:
                if cookie.get("value") and cookie.get("value").strip():
                    found_cookies.add(cookie["name"])
        
        return len(found_cookies) >= 3  # Need at least 3 auth cookies
    
    async def test_stream_extraction(self, video_id: str = None):
        """Test yt-dlp stream URL extraction"""
        print("\n🎬 STREAM EXTRACTION TEST")
        print("-" * 40)
        
        test_id = video_id or self.test_video_id
        url = f"https://www.youtube.com/watch?v={test_id}"
        
        try:
            import yt_dlp
        except ImportError:
            print("❌ yt-dlp not available")
            return False
        
        # Test different yt-dlp configurations
        configs = [
            {
                "name": "Audio Only (Optimal for Discord)",
                "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best[height<=720]",
                "extract_flat": False,
            },
            {
                "name": "Best Audio Quality",
                "format": "bestaudio/best",
                "extract_flat": False,
            },
            {
                "name": "Basic Configuration",
                "format": "best[height<=720]/best",
                "extract_flat": False,
            }
        ]
        
        extraction_results = {}
        
        for config in configs:
            print(f"\n🔧 Testing: {config['name']}")
            
            ydl_opts = {
                "format": config["format"],
                "quiet": True,
                "no_warnings": False,
                "noplaylist": True,
                "extract_flat": config["extract_flat"],
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "socket_timeout": 30,
                "retries": 3,
                "ignoreerrors": False,
            }
            
            # Add cookies if available
            cookie_file = self._get_best_cookie_file()
            if cookie_file:
                ydl_opts["cookiefile"] = cookie_file
                print(f"   Using cookies: {cookie_file}")
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    if info:
                        stream_url = info.get("url")
                        formats = info.get("formats", [])
                        title = info.get("title", "Unknown")
                        duration = info.get("duration", 0)
                        
                        result = {
                            "success": True,
                            "stream_url": stream_url[:100] + "..." if stream_url else None,
                            "title": title,
                            "duration": duration,
                            "format_count": len(formats),
                            "has_audio": any(f.get("acodec", "none") != "none" for f in formats),
                            "best_audio_format": self._analyze_best_audio_format(formats)
                        }
                        
                        print(f"   ✅ Success: {title}")
                        print(f"   ⏱️  Duration: {duration}s")
                        print(f"   📊 Formats: {len(formats)}")
                        print(f"   🎵 Has Audio: {result['has_audio']}")
                        
                        if result["best_audio_format"]:
                            af = result["best_audio_format"]
                            print(f"   🎧 Best Audio: {af['format_id']} ({af['ext']}, {af.get('abr', 'unknown')}kbps)")
                        
                        extraction_results[config["name"]] = result
                    else:
                        print(f"   ❌ No info returned")
                        extraction_results[config["name"]] = {"success": False, "error": "No info returned"}
                        
            except Exception as e:
                print(f"   ❌ Error: {e}")
                extraction_results[config["name"]] = {"success": False, "error": str(e)}
        
        self.results["stream_extraction"] = extraction_results
        
        # Test stream URL accessibility
        successful_configs = [k for k, v in extraction_results.items() if v.get("success")]
        if successful_configs:
            print(f"\n✅ Successful configurations: {len(successful_configs)}")
            best_config = extraction_results[successful_configs[0]]
            if best_config.get("stream_url"):
                await self._test_stream_accessibility(best_config["stream_url"].replace("...", ""))
        else:
            print("\n❌ No configurations succeeded")
        
        return len(successful_configs) > 0
    
    def _analyze_best_audio_format(self, formats: List[Dict]) -> Optional[Dict]:
        """Find the best audio format for Discord"""
        if not formats:
            return None
        
        # Filter for audio-only formats
        audio_formats = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec", "none") != "none"]
        
        if not audio_formats:
            # Fallback to any format with audio
            audio_formats = [f for f in formats if f.get("acodec", "none") != "none"]
        
        if not audio_formats:
            return None
        
        # Sort by audio quality
        def quality_score(f):
            abr = f.get("abr", 0) or 0
            tbr = f.get("tbr", 0) or 0
            
            # Prefer common formats for Discord
            ext_bonus = 0
            if f.get("ext") in ["m4a", "webm", "ogg"]:
                ext_bonus = 10
            
            return abr + tbr + ext_bonus
        
        best_format = max(audio_formats, key=quality_score)
        return {
            "format_id": best_format.get("format_id"),
            "ext": best_format.get("ext"),
            "abr": best_format.get("abr"),
            "tbr": best_format.get("tbr"),
            "acodec": best_format.get("acodec"),
            "url": best_format.get("url", "")[:100] + "..." if best_format.get("url") else None
        }
    
    async def _test_stream_accessibility(self, stream_url: str):
        """Test if stream URL is accessible"""
        print(f"\n🌐 STREAM URL ACCESSIBILITY TEST")
        print("-" * 40)
        
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Test HEAD request first
                try:
                    async with session.head(stream_url) as response:
                        print(f"✅ HEAD request: {response.status}")
                        print(f"   Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                        print(f"   Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
                        
                        if response.status == 200:
                            # Test partial content request
                            headers = {"Range": "bytes=0-1023"}
                            async with session.get(stream_url, headers=headers) as range_response:
                                print(f"✅ Range request: {range_response.status}")
                                if range_response.status in [206, 200]:
                                    content = await range_response.read()
                                    print(f"   Downloaded {len(content)} bytes successfully")
                                    return True
                        
                except Exception as e:
                    print(f"❌ Stream accessibility test failed: {e}")
                    return False
                    
        except ImportError:
            print("❌ aiohttp not available for accessibility test")
            return False
    
    def _get_best_cookie_file(self) -> Optional[str]:
        """Get the best available cookie file"""
        for path in self.cookie_paths:
            if path.exists():
                json_file = path / "youtube_cookies.json"
                txt_file = path / "youtube_cookies.txt"
                
                if txt_file.exists():
                    return str(txt_file)
                elif json_file.exists():
                    # Try to convert JSON to Netscape format
                    try:
                        self._convert_json_to_netscape(json_file, txt_file)
                        if txt_file.exists():
                            return str(txt_file)
                    except Exception as e:
                        logger.debug(f"Cookie conversion failed: {e}")
        
        return None
    
    def _convert_json_to_netscape(self, json_file: Path, netscape_file: Path):
        """Convert JSON cookies to Netscape format"""
        with open(json_file, 'r') as f:
            cookies = json.load(f)
        
        with open(netscape_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            for cookie in cookies:
                if isinstance(cookie, dict):
                    domain = cookie.get("domain", "")
                    flag = "TRUE" if domain.startswith(".") else "FALSE"
                    path = cookie.get("path", "/")
                    secure = "TRUE" if cookie.get("secure", False) else "FALSE"
                    expiry = cookie.get("expires", 0)
                    name = cookie.get("name", "")
                    value = cookie.get("value", "")
                    
                    f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
    
    def test_ffmpeg_configuration(self):
        """Test FFmpeg configuration used by Discord.py"""
        print("\n🎛️  FFMPEG CONFIGURATION TEST")
        print("-" * 40)
        
        # Test FFmpeg configurations used in the bot
        configs = [
            {
                "name": "Discord Bot Configuration",
                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -loglevel info",
                "options": "-vn -ar 48000 -ac 2 -b:a 128k"
            },
            {
                "name": "Basic Audio Configuration",
                "before_options": "-loglevel error",
                "options": "-vn -f s16le -ar 48000 -ac 2"
            }
        ]
        
        ffmpeg_results = {}
        
        for config in configs:
            print(f"\n🔧 Testing: {config['name']}")
            
            # Create a test command
            cmd = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", "sine=frequency=440:duration=1",
                "-f", "null",
                "-"
            ]
            
            # Add before options
            if config["before_options"]:
                before_opts = config["before_options"].split()
                cmd = ["ffmpeg"] + before_opts + cmd[1:]
            
            # Add options
            if config["options"]:
                opts = config["options"].split()
                cmd = cmd[:-2] + opts + cmd[-2:]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    print(f"   ✅ Configuration works")
                    ffmpeg_results[config["name"]] = {"success": True, "error": None}
                else:
                    print(f"   ❌ Configuration failed: {result.stderr[:200]}")
                    ffmpeg_results[config["name"]] = {"success": False, "error": result.stderr}
            except Exception as e:
                print(f"   ❌ Test failed: {e}")
                ffmpeg_results[config["name"]] = {"success": False, "error": str(e)}
        
        self.results["ffmpeg_compatibility"] = ffmpeg_results
        return any(r["success"] for r in ffmpeg_results.values())
    
    def test_discord_compatibility(self):
        """Test Discord.py compatibility"""
        print("\n🤖 DISCORD.PY COMPATIBILITY TEST")
        print("-" * 40)
        
        try:
            import discord
            
            # Test if we can create audio sources
            test_url = "https://www.soundjay.com/misc/sounds/test-audio.mp3"  # Test audio file
            
            try:
                # Test basic audio source creation
                source = discord.FFmpegPCMAudio(test_url)
                print("✅ Can create FFmpegPCMAudio source")
                
                # Test volume transformer
                transformed = discord.PCMVolumeTransformer(source, volume=0.5)
                print("✅ Can create PCMVolumeTransformer")
                
                self.results["discord_compatibility"] = {"success": True, "error": None}
                return True
                
            except Exception as e:
                print(f"❌ Discord audio source creation failed: {e}")
                self.results["discord_compatibility"] = {"success": False, "error": str(e)}
                return False
                
        except ImportError as e:
            print(f"❌ Discord.py not available: {e}")
            self.results["discord_compatibility"] = {"success": False, "error": str(e)}
            return False
    
    def generate_recommendations(self):
        """Generate recommendations based on test results"""
        print("\n💡 RECOMMENDATIONS")
        print("-" * 40)
        
        recommendations = []
        
        # Cookie system recommendations
        cookie_results = self.results.get("cookie_system", {})
        if not cookie_results.get("paths_found"):
            recommendations.append("🍪 Install cookies: Run `python scripts/extract-brave-cookies.py` to extract browser cookies")
        elif cookie_results.get("health_issues"):
            recommendations.append("🔄 Refresh cookies: Your cookies are stale or incomplete - re-extract them")
        
        # Stream extraction recommendations
        stream_results = self.results.get("stream_extraction", {})
        successful_extractions = [k for k, v in stream_results.items() if v.get("success")]
        if not successful_extractions:
            recommendations.append("🎬 Fix yt-dlp: Stream extraction is failing - check yt-dlp version and YouTube restrictions")
        
        # FFmpeg recommendations
        ffmpeg_results = self.results.get("ffmpeg_compatibility", {})
        if not any(r.get("success") for r in ffmpeg_results.values()):
            recommendations.append("🎛️  Install FFmpeg: FFmpeg is required for audio processing - install it and ensure it's in PATH")
        
        # Discord recommendations
        discord_results = self.results.get("discord_compatibility", {})
        if not discord_results.get("success"):
            recommendations.append("🤖 Fix Discord.py: Discord audio source creation is failing - check discord.py version")
        
        # General recommendations
        if len(successful_extractions) > 0 and ffmpeg_results and discord_results.get("success"):
            recommendations.append("✅ Core components work - check voice connection and bot permissions")
        
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec}")
        else:
            print("✅ All systems appear to be working correctly!")
        
        return recommendations
    
    def print_summary(self):
        """Print diagnostic summary"""
        print("\n" + "=" * 80)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 80)
        
        # Calculate overall health
        scores = {
            "cookie_system": len(self.results.get("cookie_system", {}).get("paths_found", [])) > 0,
            "stream_extraction": any(v.get("success") for v in self.results.get("stream_extraction", {}).values()),
            "ffmpeg_compatibility": any(v.get("success") for v in self.results.get("ffmpeg_compatibility", {}).values()),
            "discord_compatibility": self.results.get("discord_compatibility", {}).get("success", False)
        }
        
        total_score = sum(scores.values())
        max_score = len(scores)
        
        print(f"Overall Health: {total_score}/{max_score} ({total_score/max_score*100:.1f}%)")
        print()
        
        for component, status in scores.items():
            emoji = "✅" if status else "❌"
            print(f"{emoji} {component.replace('_', ' ').title()}: {'PASS' if status else 'FAIL'}")
        
        if total_score == max_score:
            self.results["overall_health"] = "excellent"
            print("\n🎉 All systems are working correctly!")
        elif total_score >= max_score * 0.75:
            self.results["overall_health"] = "good"
            print("\n👍 Most systems are working - minor issues to resolve")
        elif total_score >= max_score * 0.5:
            self.results["overall_health"] = "fair"
            print("\n⚠️  Some critical issues need attention")
        else:
            self.results["overall_health"] = "poor"
            print("\n🚨 Multiple critical issues - significant fixes needed")
    
    async def run_full_diagnostic(self, video_id: str = None):
        """Run complete diagnostic suite"""
        self.print_header()
        
        if not self.check_dependencies():
            print("\n🚨 Cannot continue - missing critical dependencies")
            return False
        
        success_count = 0
        total_tests = 4
        
        # Test 1: Cookie System
        if self.analyze_cookie_system():
            success_count += 1
        
        # Test 2: Stream Extraction
        if await self.test_stream_extraction(video_id):
            success_count += 1
        
        # Test 3: FFmpeg Configuration
        if self.test_ffmpeg_configuration():
            success_count += 1
        
        # Test 4: Discord Compatibility
        if self.test_discord_compatibility():
            success_count += 1
        
        # Generate recommendations
        self.generate_recommendations()
        
        # Print summary
        self.print_summary()
        
        return success_count == total_tests

async def main():
    """Main diagnostic function"""
    video_id = None
    if len(sys.argv) > 1:
        video_id = sys.argv[1]
        print(f"Using custom video ID: {video_id}")
    
    diagnostic = YouTubeStreamingDiagnostic()
    success = await diagnostic.run_full_diagnostic(video_id)
    
    # Save results to file
    results_file = Path("youtube_streaming_diagnostic_results.json")
    with open(results_file, 'w') as f:
        json.dump(diagnostic.results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    if success:
        print("\n✅ Diagnostic completed successfully - YouTube streaming should work")
        sys.exit(0)
    else:
        print("\n❌ Diagnostic found issues - YouTube streaming may not work properly")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())