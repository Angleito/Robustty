#!/usr/bin/env python3
"""
Standalone test for YouTube URL pattern matching and video ID extraction.
Tests the regex patterns used by the YouTube platform without requiring dependencies.
"""

import re
import logging
from typing import Optional, List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class YouTubeURLTester:
    """Standalone YouTube URL pattern tester"""
    
    def __init__(self):
        # URL patterns from YouTube platform (copied from src/platforms/youtube.py)
        self.url_patterns = [
            re.compile(
                r"(?:https?:\/\/)?(?:www\.)?" r"youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)"
            ),
            re.compile(r"(?:https?:\/\/)?(?:www\.)?" r"youtu\.be\/([a-zA-Z0-9_-]+)"),
            re.compile(
                r"(?:https?:\/\/)?(?:www\.)?" r"youtube\.com\/embed\/([a-zA-Z0-9_-]+)"
            ),
        ]
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL using the same logic as the platform"""
        if not url:
            return None
            
        for pattern in self.url_patterns:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None
    
    def is_platform_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL using the same logic as the platform"""
        if not url:
            return False
        return any(pattern.search(url) for pattern in self.url_patterns)
    
    def test_url_patterns(self) -> bool:
        """Test URL pattern matching and video ID extraction"""
        logger.info("Testing YouTube URL patterns and video ID extraction...")
        
        # Test cases: (URL, expected_video_id, should_be_detected)
        test_cases = [
            # Standard YouTube URLs
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("http://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("http://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            
            # Short URLs
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("http://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("www.youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            
            # Embed URLs
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("https://youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("http://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            ("youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ", True),
            
            # URLs with additional parameters (should extract ID ignoring params)
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s", "dQw4w9WgXcQ", True),
            ("https://www.youtube.com/watch?list=PLxyz&v=dQw4w9WgXcQ&index=1", "dQw4w9WgXcQ", True),
            ("https://youtu.be/dQw4w9WgXcQ?t=30", "dQw4w9WgXcQ", True),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxyz", "dQw4w9WgXcQ", True),
            
            # Edge cases with various video ID formats
            ("https://www.youtube.com/watch?v=123456789ab", "123456789ab", True),
            ("https://www.youtube.com/watch?v=ABC123def456", "ABC123def456", True),
            ("https://www.youtube.com/watch?v=_-123abc_-DE", "_-123abc_-DE", True),
            ("https://youtu.be/_-123abc_-DE", "_-123abc_-DE", True),
            ("https://www.youtube.com/embed/ABC-123_def", "ABC-123_def", True),
            
            # Invalid URLs that should not be detected
            ("https://vimeo.com/123456789", None, False),
            ("https://www.dailymotion.com/video/xyz", None, False),
            ("https://www.twitch.tv/videos/123456789", None, False),
            ("https://www.youtube.com/channel/UCxyz", None, False),
            ("https://www.youtube.com/playlist?list=PLxyz", None, False),
            ("https://www.youtube.com/user/testuser", None, False),
            ("https://www.youtube.com/c/testchannel", None, False),
            ("https://www.youtube.com/watch", None, False),
            ("https://www.youtube.com/watch?v=", None, False),
            ("https://youtu.be/", None, False),
            ("https://www.youtube.com/watch?list=PLxyz", None, False),
            ("not_a_url", None, False),
            ("", None, False),
            ("https://example.com", None, False),
            ("https://www.google.com/search?q=youtube", None, False),
        ]
        
        success_count = 0
        failure_count = 0
        
        for url, expected_id, should_be_detected in test_cases:
            try:
                # Test video ID extraction
                extracted_id = self.extract_video_id(url)
                
                # Test platform URL detection
                is_detected = self.is_platform_url(url)
                
                # Check results
                id_correct = extracted_id == expected_id
                detection_correct = is_detected == should_be_detected
                
                if id_correct and detection_correct:
                    if should_be_detected:
                        logger.info(f"✓ URL: {url} → ID: {extracted_id}")
                    else:
                        logger.info(f"✓ Correctly rejected: {url}")
                    success_count += 1
                else:
                    logger.error(f"✗ URL: {url}")
                    if not id_correct:
                        logger.error(f"  Expected ID: {expected_id}, Got: {extracted_id}")
                    if not detection_correct:
                        logger.error(f"  Expected detection: {should_be_detected}, Got: {is_detected}")
                    failure_count += 1
                    
            except Exception as e:
                logger.error(f"✗ Error processing URL {url}: {e}")
                failure_count += 1
        
        logger.info(f"\nURL Pattern Tests: {success_count} passed, {failure_count} failed")
        return failure_count == 0
    
    def test_regex_patterns_directly(self) -> bool:
        """Test regex patterns directly for comprehensive coverage"""
        logger.info("\nTesting regex patterns directly...")
        
        # Test each pattern individually
        patterns_to_test = [
            (
                "youtube.com/watch pattern",
                self.url_patterns[0],
                [
                    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
                    ("youtube.com/watch?v=test123", "test123"),
                    ("www.youtube.com/watch?v=ABC_123", "ABC_123"),
                    ("https://youtube.com/watch?v=test-video", "test-video"),
                ],
                [
                    "https://youtu.be/dQw4w9WgXcQ",
                    "https://vimeo.com/123456",
                    "https://www.youtube.com/embed/test123",
                    "https://www.youtube.com/channel/test",
                ]
            ),
            (
                "youtu.be pattern",
                self.url_patterns[1],
                [
                    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
                    ("youtu.be/test123", "test123"),
                    ("www.youtu.be/ABC_123", "ABC_123"),
                    ("http://youtu.be/test-video", "test-video"),
                ],
                [
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "https://vimeo.com/123456",
                    "https://www.youtube.com/embed/test123",
                    "https://youtu.be/",
                ]
            ),
            (
                "youtube.com/embed pattern",
                self.url_patterns[2],
                [
                    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
                    ("youtube.com/embed/test123", "test123"),
                    ("www.youtube.com/embed/ABC_123", "ABC_123"),
                    ("http://youtube.com/embed/test-video", "test-video"),
                ],
                [
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "https://youtu.be/dQw4w9WgXcQ",
                    "https://vimeo.com/123456",
                    "https://www.youtube.com/embed/",
                ]
            )
        ]
        
        success_count = 0
        failure_count = 0
        
        for pattern_name, pattern, positive_tests, negative_tests in patterns_to_test:
            logger.info(f"\nTesting {pattern_name}:")
            
            # Test positive cases
            for url, expected_id in positive_tests:
                match = pattern.search(url)
                if match and match.group(1) == expected_id:
                    logger.info(f"  ✓ {url} → {expected_id}")
                    success_count += 1
                else:
                    actual_id = match.group(1) if match else None
                    logger.error(f"  ✗ {url} → Expected: {expected_id}, Got: {actual_id}")
                    failure_count += 1
            
            # Test negative cases
            for url in negative_tests:
                match = pattern.search(url)
                if not match:
                    logger.info(f"  ✓ Correctly rejected: {url}")
                    success_count += 1
                else:
                    logger.error(f"  ✗ Incorrectly matched: {url} → {match.group(1)}")
                    failure_count += 1
        
        logger.info(f"\nRegex Pattern Tests: {success_count} passed, {failure_count} failed")
        return failure_count == 0
    
    def test_video_id_format_validation(self) -> bool:
        """Test various video ID formats"""
        logger.info("\nTesting video ID format validation...")
        
        # YouTube video IDs are typically 11 characters long
        # and can contain letters, numbers, underscores, and hyphens
        valid_id_formats = [
            "dQw4w9WgXcQ",  # Standard format
            "123456789ab",  # Numbers and letters
            "ABC123def456", # Mixed case - but pattern extracts as-is
            "_-123abc_-DE", # With underscores and hyphens
            "abcdefghijk",  # All lowercase
            "ABCDEFGHIJK",  # All uppercase
            "1234567890a",  # Mostly numbers
            "_________ab",   # Mostly underscores
            "-------abcd",  # Mostly hyphens
        ]
        
        success_count = 0
        failure_count = 0
        
        for video_id in valid_id_formats:
            # Test with different URL formats
            test_urls = [
                f"https://www.youtube.com/watch?v={video_id}",
                f"https://youtu.be/{video_id}",
                f"https://www.youtube.com/embed/{video_id}",
            ]
            
            for url in test_urls:
                extracted_id = self.extract_video_id(url)
                if extracted_id == video_id:
                    success_count += 1
                else:
                    logger.error(f"✗ Failed to extract ID from {url}: got {extracted_id}")
                    failure_count += 1
        
        # Test some edge cases and special characters
        edge_cases = [
            ("https://www.youtube.com/watch?v=test@123", None),  # Invalid char @
            ("https://www.youtube.com/watch?v=test 123", None),  # Space
            ("https://www.youtube.com/watch?v=test%20123", None),  # URL encoded space
            ("https://www.youtube.com/watch?v=", None),  # Empty ID
            ("https://youtu.be/", None),  # Empty short URL
        ]
        
        for url, expected_id in edge_cases:
            extracted_id = self.extract_video_id(url)
            if extracted_id == expected_id:
                logger.info(f"✓ Edge case handled correctly: {url}")
                success_count += 1
            else:
                logger.error(f"✗ Edge case failed: {url} → Expected: {expected_id}, Got: {extracted_id}")
                failure_count += 1
        
        logger.info(f"\nVideo ID Format Tests: {success_count} passed, {failure_count} failed")
        return failure_count == 0
    
    def run_all_tests(self) -> bool:
        """Run all URL pattern tests"""
        logger.info("="*70)
        logger.info("YOUTUBE URL PATTERN TESTING")
        logger.info("="*70)
        
        results = []
        
        # Run individual tests
        results.append(("URL Patterns", self.test_url_patterns()))
        results.append(("Regex Patterns", self.test_regex_patterns_directly()))
        results.append(("Video ID Formats", self.test_video_id_format_validation()))
        
        # Print summary
        logger.info("\n" + "="*70)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("="*70)
        
        passed_tests = 0
        total_tests = len(results)
        
        for test_name, passed in results:
            if passed:
                logger.info(f"✅ {test_name}: PASSED")
                passed_tests += 1
            else:
                logger.info(f"❌ {test_name}: FAILED")
        
        logger.info(f"\nOverall: {passed_tests}/{total_tests} test suites passed")
        
        if passed_tests == total_tests:
            logger.info("🎉 All YouTube URL pattern tests passed!")
            logger.info("The YouTube platform can correctly:")
            logger.info("  • Extract video IDs from various YouTube URL formats")
            logger.info("  • Detect YouTube URLs vs non-YouTube URLs")
            logger.info("  • Handle edge cases and invalid inputs")
            logger.info("  • Support all major YouTube URL patterns")
        else:
            logger.info("⚠️  Some tests failed. Review the output above for details.")
        
        logger.info("="*70)
        
        return passed_tests == total_tests


def main():
    """Main test function"""
    tester = YouTubeURLTester()
    success = tester.run_all_tests()
    return success


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        exit(130)
    except Exception as e:
        print(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)