#!/usr/bin/env python3
"""Quick test for cookie extraction"""
import logging
from src.extractors.cross_platform_cookies import CrossPlatformCookieExtractor

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def test_extraction():
    """Test basic cookie extraction"""
    print("Testing cookie extraction...")
    
    # Create extractor
    extractor = CrossPlatformCookieExtractor()
    
    # Test OS detection
    print(f"\nDetected OS: {extractor.os_name}")
    
    # Extract all cookies
    print("\nExtracting cookies from all browsers...")
    all_cookies = extractor.extract_all_cookies()
    
    # Show results
    for browser, cookies in all_cookies.items():
        print(f"\n{browser.upper()}:")
        print(f"  Found {len(cookies)} total cookies")
        
        # Show first few cookies (without values for security)
        for i, cookie in enumerate(cookies[:3]):
            print(f"  - {cookie.name} ({cookie.host_key})")
        if len(cookies) > 3:
            print(f"  ... and {len(cookies) - 3} more")
    
    # Test YouTube specific extraction
    print("\n\nExtracting YouTube cookies...")
    youtube_jar = extractor.find_youtube_cookies()
    print(f"Found {len(youtube_jar)} YouTube cookies")
    
    # Show YouTube cookie names
    for cookie in youtube_jar:
        print(f"  - {cookie.name}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_extraction()