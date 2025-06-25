#!/usr/bin/env python3
"""
Test script for YouTube platform enhancements
"""

import asyncio
import logging
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from platforms.youtube import YouTubePlatform

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_url_parsing():
    """Test URL parsing functionality"""
    print("=== Testing URL Parsing ===")
    
    config = {
        "api_key": None,  # Simulate no API key
        "enable_fallbacks": True
    }
    
    platform = YouTubePlatform("youtube", config)
    await platform.initialize()
    
    # Test YouTube URL
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    try:
        results = await platform._search_via_url_parsing(test_url)
        if results:
            print(f"✓ URL parsing successful: Found {len(results)} results")
            for result in results:
                print(f"  - Title: {result.get('title', 'Unknown')}")
                print(f"  - Channel: {result.get('channel', 'Unknown')}")
                print(f"  - Duration: {result.get('duration', 'Unknown')}")
        else:
            print("✗ URL parsing failed: No results returned")
    except Exception as e:
        print(f"✗ URL parsing failed: {e}")
    
    await platform.cleanup()

async def test_metadata_extraction():
    """Test metadata extraction via yt-dlp"""
    print("\n=== Testing Metadata Extraction ===")
    
    config = {
        "api_key": None,  # Simulate no API key
        "enable_fallbacks": True
    }
    
    platform = YouTubePlatform("youtube", config)
    await platform.initialize()
    
    # Test video ID
    test_video_id = "dQw4w9WgXcQ"
    
    try:
        metadata = await platform._extract_metadata_via_ytdlp(test_video_id)
        if metadata:
            print(f"✓ Metadata extraction successful")
            print(f"  - ID: {metadata.get('id', 'Unknown')}")
            print(f"  - Title: {metadata.get('title', 'Unknown')}")
            print(f"  - Channel: {metadata.get('channel', 'Unknown')}")
            print(f"  - Duration: {metadata.get('duration', 'Unknown')}")
            print(f"  - Views: {metadata.get('views', 'Unknown')}")
            print(f"  - Published: {metadata.get('published', 'Unknown')}")
        else:
            print("✗ Metadata extraction failed: No metadata returned")
    except Exception as e:
        print(f"✗ Metadata extraction failed: {e}")
    
    await platform.cleanup()

async def test_search_with_url():
    """Test search method with URL"""
    print("\n=== Testing Search with URL ===")
    
    config = {
        "api_key": None,  # Simulate no API key
        "enable_fallbacks": True
    }
    
    platform = YouTubePlatform("youtube", config)
    await platform.initialize()
    
    # Test YouTube URL
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    try:
        results = await platform.search_videos(test_url)
        if results:
            print(f"✓ Search with URL successful: Found {len(results)} results")
            for result in results:
                print(f"  - Title: {result.get('title', 'Unknown')}")
                print(f"  - URL: {result.get('url', 'Unknown')}")
        else:
            print("✗ Search with URL failed: No results returned")
    except Exception as e:
        print(f"✗ Search with URL failed: {e}")
    
    await platform.cleanup()

async def test_video_details_fallback():
    """Test video details with fallback"""
    print("\n=== Testing Video Details Fallback ===")
    
    config = {
        "api_key": None,  # Simulate no API key
        "enable_fallbacks": True
    }
    
    platform = YouTubePlatform("youtube", config)
    await platform.initialize()
    
    # Test video ID
    test_video_id = "dQw4w9WgXcQ"
    
    try:
        details = await platform.get_video_details(test_video_id)
        if details:
            print(f"✓ Video details fallback successful")
            print(f"  - ID: {details.get('id', 'Unknown')}")
            print(f"  - Title: {details.get('title', 'Unknown')}")
            print(f"  - Channel: {details.get('channel', 'Unknown')}")
            print(f"  - Platform: {details.get('platform', 'Unknown')}")
        else:
            print("✗ Video details fallback failed: No details returned")
    except Exception as e:
        print(f"✗ Video details fallback failed: {e}")
    
    await platform.cleanup()

async def main():
    """Run all tests"""
    print("YouTube Platform Enhancement Tests")
    print("=" * 40)
    
    try:
        await test_url_parsing()
        await test_metadata_extraction()
        await test_search_with_url()
        await test_video_details_fallback()
        
        print("\n" + "=" * 40)
        print("All tests completed!")
        
    except Exception as e:
        print(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())