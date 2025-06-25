#!/usr/bin/env python3
"""
Test script for YouTube platform yt-dlp fallback functionality
"""

import asyncio
import logging
from src.platforms.youtube import YouTubePlatform

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ytdlp_search():
    """Test the new yt-dlp search functionality"""
    
    # Create YouTube platform instance without API key to test fallback
    config = {
        "api_key": None,  # No API key to force fallback
        "enable_fallbacks": True
    }
    
    youtube_platform = YouTubePlatform("youtube", config)
    await youtube_platform.initialize()
    
    print("=" * 60)
    print("Testing YouTube yt-dlp fallback search")
    print("=" * 60)
    
    # Test 1: Search for music
    print("\n1. Testing search for 'never gonna give you up'...")
    try:
        results = await youtube_platform.search_videos("never gonna give you up", max_results=3)
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result['title']} by {result['channel']}")
            print(f"     Duration: {result['duration']}, Views: {result['views']}")
            print(f"     URL: {result['url']}")
    except Exception as e:
        print(f"Search failed: {e}")
    
    # Test 2: Search with URL
    print("\n2. Testing search with YouTube URL...")
    try:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        results = await youtube_platform.search_videos(url, max_results=1)
        print(f"Found {len(results)} results:")
        for result in results:
            print(f"  Title: {result['title']} by {result['channel']}")
            print(f"  Duration: {result['duration']}, Views: {result['views']}")
    except Exception as e:
        print(f"URL search failed: {e}")
    
    # Test 3: Test the new _extract_metadata_from_ytdlp_result method
    print("\n3. Testing metadata extraction...")
    test_info = {
        "id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up (Video)",
        "uploader": "RickAstleyVEVO",
        "description": "Rick Astley's official music video for Never Gonna Give You Up",
        "duration": 212,
        "view_count": 1234567890,
        "upload_date": "20091024",
        "thumbnails": [
            {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg", "width": 1280, "height": 720}
        ]
    }
    
    metadata = youtube_platform._extract_metadata_from_ytdlp_result(test_info)
    if metadata:
        print("  Metadata extraction successful:")
        print(f"    Title: {metadata['title']}")
        print(f"    Channel: {metadata['channel']}")
        print(f"    Duration: {metadata['duration']}")
        print(f"    Views: {metadata['views']}")
        print(f"    Published: {metadata['published']}")
    else:
        print("  Metadata extraction failed")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_ytdlp_search())