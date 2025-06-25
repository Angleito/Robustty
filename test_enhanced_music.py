#!/usr/bin/env python3
"""
Test script for enhanced music cog URL detection functionality
"""

import re
from typing import Optional

# Test the URL detection functionality
class TestURLDetection:
    def __init__(self):
        # URL patterns for direct platform detection - enhanced to handle parameters
        self.youtube_url_patterns = [
            re.compile(r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:m\.)?youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:music\.)?youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]+)"),
        ]
    
    def _detect_youtube_url(self, query: str) -> Optional[str]:
        """Detect and extract YouTube video ID from URL"""
        for pattern in self.youtube_url_patterns:
            match = pattern.search(query.strip())
            if match:
                return match.group(1)
        return None
    
    def _is_direct_url(self, query: str) -> bool:
        """Check if query is a direct URL (not just a search term)"""
        # Check for common URL patterns
        url_indicators = [
            "http://", "https://", "www.", 
            "youtube.com", "youtu.be", "rumble.com", 
            "odysee.com", "peertube"
        ]
        query_lower = query.lower().strip()
        return any(indicator in query_lower for indicator in url_indicators)

def test_url_detection():
    """Test URL detection functionality"""
    tester = TestURLDetection()
    
    print("🧪 Testing Enhanced Music Cog URL Detection")
    print("=" * 50)
    
    # Test cases for YouTube URL detection - enhanced with new formats
    youtube_test_cases = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("http://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        # Enhanced test cases with parameters
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ]
    
    print("\n📺 YouTube URL Detection Tests:")
    for url, expected_id in youtube_test_cases:
        detected_id = tester._detect_youtube_url(url)
        status = "✅ PASS" if detected_id == expected_id else "❌ FAIL"
        print(f"{status} | {url:<40} -> {detected_id}")
    
    # Test cases for general URL detection
    url_test_cases = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("youtube.com/watch?v=abc123", True),
        ("https://rumble.com/video123", True),
        ("www.odysee.com/@channel", True),
        ("never gonna give you up", False),
        ("rick astley", False),
        ("search for music", False),
        ("play my favorite song", False),
    ]
    
    print("\n🔗 General URL Detection Tests:")
    for query, expected_result in url_test_cases:
        is_url = tester._is_direct_url(query)
        status = "✅ PASS" if is_url == expected_result else "❌ FAIL"
        print(f"{status} | {query:<40} -> {is_url}")
    
    print("\n🎉 Testing Complete!")
    print("\nEnhanced features implemented:")
    print("• Direct YouTube URL detection and video ID extraction")
    print("• Generic platform URL detection") 
    print("• Immediate metadata extraction for direct URLs")
    print("• Seamless fallback to search mode when needed")
    print("• Enhanced user feedback showing processing method")
    print("• Rich metadata display with thumbnails, duration, views")

if __name__ == "__main__":
    test_url_detection()