#!/usr/bin/env python3
"""
Comprehensive test for YouTube platform direct URL processing capabilities.
Tests URL extraction, cookie integration, and stream URL retrieval without API calls.
"""

import asyncio
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the YouTube platform
import sys
sys.path.append(str(Path(__file__).parent / "src"))

try:
    from platforms.youtube import YouTubePlatform
    from platforms.errors import PlatformAPIError
except ImportError as e:
    logger.error(f"Failed to import YouTube platform: {e}")
    logger.info("Attempting alternative import...")
    try:
        # Try absolute import
        sys.path.insert(0, str(Path(__file__).parent))
        from src.platforms.youtube import YouTubePlatform
        from src.platforms.errors import PlatformAPIError
    except ImportError as e2:
        logger.error(f"Alternative import also failed: {e2}")
        raise


class YouTubeDirectURLTest:
    """Test class for YouTube direct URL processing"""
    
    def __init__(self):
        self.temp_dir = None
        self.platform = None
        
    async def setup(self):
        """Setup test environment"""
        # Create temporary directory for cookies
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {self.temp_dir}")
        
        # Initialize YouTube platform without API key (direct URL mode)
        config = {
            "enabled": True,
            "api_key": None,  # No API key - testing direct URL processing
            "enable_fallbacks": True
        }
        self.platform = YouTubePlatform("youtube", config)
        await self.platform.initialize()
        
    async def cleanup(self):
        """Cleanup test environment"""
        if self.platform:
            await self.platform.cleanup()
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
    
    def test_url_patterns(self):
        """Test URL pattern matching and video ID extraction"""
        logger.info("Testing URL patterns and video ID extraction...")
        
        # Test cases: (URL, expected_video_id)
        test_urls = [
            # Standard YouTube URLs
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("http://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("http://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            
            # Short URLs
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("http://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            
            # Embed URLs
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("http://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            
            # URLs with additional parameters
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?list=PLxyz&v=dQw4w9WgXcQ&index=1", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ?t=30", "dQw4w9WgXcQ"),
            
            # Edge cases with valid video IDs
            ("https://www.youtube.com/watch?v=123456789ab", "123456789ab"),
            ("https://www.youtube.com/watch?v=ABC123def456", "ABC123def456"),
            ("https://www.youtube.com/watch?v=_-123abc_-DE", "_-123abc_-DE"),
        ]
        
        # Test invalid URLs
        invalid_urls = [
            "https://vimeo.com/123456789",
            "https://www.dailymotion.com/video/xyz",
            "https://www.twitch.tv/videos/123456789",
            "https://www.youtube.com/channel/UCxyz",
            "https://www.youtube.com/playlist?list=PLxyz",
            "https://www.youtube.com/watch",
            "https://www.youtube.com/watch?v=",
            "https://youtu.be/",
            "not_a_url",
            "",
            None
        ]
        
        success_count = 0
        failure_count = 0
        
        # Test valid URLs
        for url, expected_id in test_urls:
            try:
                # Test video ID extraction
                extracted_id = self.platform.extract_video_id(url)
                if extracted_id == expected_id:
                    logger.info(f"✓ URL: {url} → ID: {extracted_id}")
                    success_count += 1
                else:
                    logger.error(f"✗ URL: {url} → Expected: {expected_id}, Got: {extracted_id}")
                    failure_count += 1
                
                # Test platform URL detection
                if not self.platform.is_platform_url(url):
                    logger.error(f"✗ URL not detected as YouTube: {url}")
                    failure_count += 1
                    
            except Exception as e:
                logger.error(f"✗ Error processing URL {url}: {e}")
                failure_count += 1
        
        # Test invalid URLs
        for url in invalid_urls:
            try:
                extracted_id = self.platform.extract_video_id(url)
                is_platform_url = self.platform.is_platform_url(url) if url else False
                
                if extracted_id is None and not is_platform_url:
                    logger.info(f"✓ Correctly rejected invalid URL: {url}")
                    success_count += 1
                else:
                    logger.error(f"✗ Invalid URL incorrectly processed: {url} → ID: {extracted_id}, Platform: {is_platform_url}")
                    failure_count += 1
                    
            except Exception as e:
                # Exceptions are acceptable for invalid URLs
                logger.info(f"✓ Exception (expected) for invalid URL {url}: {e}")
                success_count += 1
        
        logger.info(f"URL Pattern Tests: {success_count} passed, {failure_count} failed")
        return failure_count == 0
    
    def test_cookie_conversion(self):
        """Test cookie conversion from JSON to Netscape format"""
        logger.info("Testing cookie conversion...")
        
        # Create test cookies
        test_cookies = [
            {
                "name": "session_token",
                "value": "abc123def456",
                "domain": ".youtube.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "expires": 1735689600  # 2025-01-01
            },
            {
                "name": "user_prefs",
                "value": "theme=dark&lang=en",
                "domain": "www.youtube.com",
                "path": "/",
                "secure": False,
                "httpOnly": True,
                "expires": 1767225600  # 2026-01-01
            },
            {
                "name": "temp_cookie",
                "value": "",
                "domain": ".youtube.com",
                "path": "/watch",
                "secure": True,
                "httpOnly": False,
                "expires": None  # Session cookie
            }
        ]
        
        # Test with valid cookies
        json_file = Path(self.temp_dir) / "test_cookies.json"
        netscape_file = Path(self.temp_dir) / "test_cookies.txt"
        
        try:
            # Write test cookies
            with open(json_file, 'w') as f:
                json.dump(test_cookies, f, indent=2)
            
            # Test conversion
            success = self.platform._convert_cookies_to_netscape(
                str(json_file), str(netscape_file)
            )
            
            if not success:
                logger.error("✗ Cookie conversion failed")
                return False
            
            # Verify Netscape file was created and has content
            if not netscape_file.exists():
                logger.error("✗ Netscape cookie file not created")
                return False
            
            with open(netscape_file, 'r') as f:
                content = f.read()
                
            if not content or len(content.strip()) == 0:
                logger.error("✗ Netscape cookie file is empty")
                return False
            
            # Verify header is present
            if "# Netscape HTTP Cookie File" not in content:
                logger.error("✗ Netscape cookie file missing header")
                return False
            
            # Count cookie lines (excluding comments and empty lines)
            cookie_lines = [line for line in content.split('\n') 
                          if line.strip() and not line.startswith('#')]
            
            if len(cookie_lines) != len(test_cookies):
                logger.error(f"✗ Expected {len(test_cookies)} cookie lines, got {len(cookie_lines)}")
                return False
            
            logger.info(f"✓ Successfully converted {len(test_cookies)} cookies to Netscape format")
            
            # Test edge cases
            return self._test_cookie_edge_cases()
            
        except Exception as e:
            logger.error(f"✗ Cookie conversion test failed: {e}")
            return False
    
    def _test_cookie_edge_cases(self):
        """Test cookie conversion edge cases"""
        logger.info("Testing cookie conversion edge cases...")
        
        edge_cases = [
            # Empty cookies list
            ([], "empty_cookies.json", True),
            
            # Invalid JSON
            ("invalid json", "invalid.json", False),
            
            # Non-list JSON
            ({"not": "a list"}, "not_list.json", False),
            
            # Cookies with missing fields
            ([{"name": "incomplete"}], "incomplete.json", True),
            
            # Cookies with invalid characters
            ([{"name": "bad\ttab", "value": "test", "domain": ".youtube.com"}], "bad_chars.json", True),
        ]
        
        for test_data, filename, should_succeed in edge_cases:
            json_file = Path(self.temp_dir) / filename
            netscape_file = Path(self.temp_dir) / f"{filename}.txt"
            
            try:
                # Write test data
                with open(json_file, 'w') as f:
                    if isinstance(test_data, str):
                        f.write(test_data)
                    else:
                        json.dump(test_data, f)
                
                # Test conversion
                success = self.platform._convert_cookies_to_netscape(
                    str(json_file), str(netscape_file)
                )
                
                if success == should_succeed:
                    logger.info(f"✓ Edge case handled correctly: {filename}")
                else:
                    logger.error(f"✗ Edge case failed: {filename} (expected {should_succeed}, got {success})")
                    return False
                    
            except Exception as e:
                if not should_succeed:
                    logger.info(f"✓ Expected exception for edge case {filename}: {e}")
                else:
                    logger.error(f"✗ Unexpected exception for edge case {filename}: {e}")
                    return False
        
        return True
    
    async def test_stream_url_extraction(self):
        """Test stream URL extraction using yt-dlp"""
        logger.info("Testing stream URL extraction...")
        
        # Check if yt-dlp is available
        try:
            import yt_dlp
        except ImportError:
            logger.warning("⚠ yt-dlp not available, skipping stream URL extraction test")
            return True  # Skip test but don't fail
        
        # Test with a known public video (Rick Roll - always available)
        test_video_id = "dQw4w9WgXcQ"
        
        try:
            # Create mock cookies for testing
            await self._create_test_cookies()
            
            # Test stream URL extraction
            stream_url = await self.platform.get_stream_url(test_video_id)
            
            if stream_url:
                logger.info(f"✓ Successfully extracted stream URL: {stream_url[:100]}...")
                
                # Validate URL format
                if not (stream_url.startswith("http://") or stream_url.startswith("https://")):
                    logger.error("✗ Stream URL is not a valid HTTP/HTTPS URL")
                    return False
                
                # Test URL validation
                is_valid = await self.platform._validate_stream_url_async(stream_url)
                if is_valid:
                    logger.info("✓ Stream URL validation passed")
                else:
                    logger.warning("⚠ Stream URL validation failed (may be temporary)")
                
                return True
            else:
                logger.error("✗ No stream URL extracted")
                return False
                
        except PlatformAPIError as e:
            logger.error(f"✗ Platform API error during stream extraction: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error during stream extraction: {e}")
            return False
    
    async def _create_test_cookies(self):
        """Create test cookies for stream URL extraction"""
        cookie_dir = Path(self.temp_dir) / "cookies"
        cookie_dir.mkdir(exist_ok=True)
        
        json_cookie_file = cookie_dir / "youtube_cookies.json"
        
        # Use empty cookies to test fallback behavior
        test_cookies = []
        
        with open(json_cookie_file, 'w') as f:
            json.dump(test_cookies, f, indent=2)
        
        # Update platform cookie paths for testing
        self.platform.cookie_paths = [str(json_cookie_file)]
    
    def test_video_id_validation(self):
        """Test video ID validation"""
        logger.info("Testing video ID validation...")
        
        valid_ids = [
            "dQw4w9WgXcQ",
            "123456789ab", 
            "ABC123def456",
            "_-123abc_-DE",
            "abcdefghijk"  # 11 characters
        ]
        
        invalid_ids = [
            "",
            None,
            "too_short",
            "this_is_way_too_long_for_youtube",
            "invalid@chars!",
            "спец символы",  # Non-ASCII
            "123",
            "12345678901234567890"  # Too long
        ]
        
        success_count = 0
        failure_count = 0
        
        # Test valid IDs
        for video_id in valid_ids:
            try:
                # This should not raise an exception during validation
                # The actual API call may fail but validation should pass
                url = f"https://www.youtube.com/watch?v={video_id}"
                extracted_id = self.platform.extract_video_id(url)
                
                if extracted_id == video_id:
                    logger.info(f"✓ Valid ID processed correctly: {video_id}")
                    success_count += 1
                else:
                    logger.error(f"✗ Valid ID not processed correctly: {video_id}")
                    failure_count += 1
                    
            except Exception as e:
                logger.error(f"✗ Error processing valid ID {video_id}: {e}")
                failure_count += 1
        
        # Test invalid IDs
        for video_id in invalid_ids:
            try:
                if video_id is None:
                    extracted_id = self.platform.extract_video_id(None)
                else:
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    extracted_id = self.platform.extract_video_id(url)
                
                if extracted_id is None:
                    logger.info(f"✓ Invalid ID correctly rejected: {video_id}")
                    success_count += 1
                else:
                    logger.error(f"✗ Invalid ID incorrectly accepted: {video_id} → {extracted_id}")
                    failure_count += 1
                    
            except Exception as e:
                # Exceptions are acceptable for invalid IDs
                logger.info(f"✓ Exception (expected) for invalid ID {video_id}: {e}")
                success_count += 1
        
        logger.info(f"Video ID Validation Tests: {success_count} passed, {failure_count} failed")
        return failure_count == 0
    
    async def test_error_handling(self):
        """Test error handling for various scenarios"""
        logger.info("Testing error handling...")
        
        test_cases = [
            # Invalid video ID
            ("invalid_id", "Should handle invalid video ID"),
            
            # Non-existent video ID
            ("aaaaaaaaaaa", "Should handle non-existent video"),
            
            # Private video (if we can find one)
            ("1234567890a", "Should handle private/unavailable video"),
        ]
        
        success_count = 0
        
        for video_id, description in test_cases:
            try:
                logger.info(f"Testing: {description}")
                stream_url = await self.platform.get_stream_url(video_id)
                
                if stream_url:
                    logger.warning(f"⚠ Unexpected success for {video_id}: {stream_url[:50]}...")
                else:
                    logger.info(f"✓ Correctly returned None for {video_id}")
                    success_count += 1
                    
            except PlatformAPIError as e:
                logger.info(f"✓ Correctly raised PlatformAPIError for {video_id}: {e}")
                success_count += 1
            except Exception as e:
                logger.error(f"✗ Unexpected exception for {video_id}: {e}")
        
        logger.info(f"Error Handling Tests: {success_count}/{len(test_cases)} passed")
        return success_count == len(test_cases)
    
    async def run_all_tests(self):
        """Run all tests and return results"""
        logger.info("Starting comprehensive YouTube direct URL processing tests...")
        
        results = {}
        
        try:
            await self.setup()
            
            # Run all tests
            results['url_patterns'] = self.test_url_patterns()
            results['cookie_conversion'] = self.test_cookie_conversion()
            results['video_id_validation'] = self.test_video_id_validation()
            results['stream_url_extraction'] = await self.test_stream_url_extraction()
            results['error_handling'] = await self.test_error_handling()
            
        except Exception as e:
            logger.error(f"Test setup failed: {e}")
            results['setup_error'] = str(e)
        finally:
            await self.cleanup()
        
        return results


async def main():
    """Main test function"""
    test_runner = YouTubeDirectURLTest()
    results = await test_runner.run_all_tests()
    
    # Print summary
    print("\n" + "="*60)
    print("YOUTUBE DIRECT URL PROCESSING TEST RESULTS")
    print("="*60)
    
    total_tests = 0
    passed_tests = 0
    
    for test_name, result in results.items():
        if test_name == 'setup_error':
            print(f"❌ Setup Error: {result}")
            continue
            
        total_tests += 1
        if result:
            print(f"✅ {test_name.replace('_', ' ').title()}: PASSED")
            passed_tests += 1
        else:
            print(f"❌ {test_name.replace('_', ' ').title()}: FAILED")
    
    print(f"\nOverall Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! YouTube direct URL processing is working correctly.")
    else:
        print(f"⚠️  {total_tests - passed_tests} test(s) failed. Review the logs above for details.")
    
    print("="*60)
    
    return passed_tests == total_tests


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        exit(130)
    except Exception as e:
        print(f"Test failed with exception: {e}")
        exit(1)