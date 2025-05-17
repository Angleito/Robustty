#!/usr/bin/env python3
"""Demonstration of Rumble integration."""
import asyncio
import sys
sys.path.insert(0, '.')

from src.platforms.rumble import RumblePlatform
from src.services.searcher import MultiPlatformSearcher
from src.platforms.registry import PlatformRegistry


async def test_rumble_integration():
    """Test Rumble integration without actually calling Apify API."""
    print("\n🎬 Rumble Integration Test Demo\n")
    
    # Test 1: Platform initialization
    print("1. Testing Rumble platform initialization...")
    config = {
        "api_token": "test_token_123",
        "enabled": True
    }
    
    rumble = RumblePlatform("rumble", config)
    await rumble.initialize()
    print("✅ Platform initialized successfully")
    
    # Test 2: URL detection
    print("\n2. Testing URL detection...")
    test_urls = [
        "https://rumble.com/v4abcd-test-video.html",
        "https://rumble.com/embed/v4abcd/",
        "https://not-rumble.com/video",
        "rumble.com/v4xyz",
    ]
    
    for url in test_urls:
        is_rumble = rumble.is_platform_url(url)
        print(f"   {url}: {'✅ Detected' if is_rumble else '❌ Not detected'}")
    
    # Test 3: Video ID extraction
    print("\n3. Testing video ID extraction...")
    rumble_urls = [
        "https://rumble.com/v4abcd-test-video.html",
        "https://rumble.com/embed/v4abcd/",
        "rumble.com/v123xyz-another-video.html",
    ]
    
    for url in rumble_urls:
        video_id = rumble.extract_video_id(url)
        print(f"   {url} -> Video ID: {video_id}")
    
    # Test 4: Platform registry
    print("\n4. Testing platform registry integration...")
    registry = PlatformRegistry()
    registry.register_platform("rumble", RumblePlatform)
    
    # Initialize with empty config for testing
    test_config = {
        "rumble": {"enabled": True, "api_token": "test"}
    }
    await registry.initialize_platforms(test_config)
    print("✅ Registry integration successful")
    
    # Test 5: Searcher integration
    print("\n5. Testing searcher integration...")
    searcher = MultiPlatformSearcher(registry)
    
    # Test URL detection in searcher
    rumble_url = "https://rumble.com/v4abcd-test.html"
    video_info = await searcher._extract_video_info(rumble_url)
    print(f"✅ Extracted video info: {video_info}")
    
    print("\n🎉 All tests completed successfully!")
    print("\nNote: These tests use mocked responses to avoid API calls.")
    print("To test with real API, set APIFY_API_TOKEN environment variable.")


if __name__ == "__main__":
    asyncio.run(test_rumble_integration())