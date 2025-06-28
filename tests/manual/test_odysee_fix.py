#!/usr/bin/env python3
"""Test script to verify Odysee platform connection fixes"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.platforms.odysee import OdyseePlatform

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_odysee_connection():
    """Test Odysee platform connectivity and API calls"""
    
    config = {
        "enabled": True,
        "api_url": "https://api.odysee.com/api/v1",
        "stream_url": "https://cdn.odysee.live",
        "max_results": 5,
        "api_timeout": 30,
        "search_timeout": 25,
        "stream_timeout": 20,
        "max_connections": 10,
        "max_connections_per_host": 5
    }
    
    platform = OdyseePlatform("odysee", config)
    
    try:
        print("Initializing Odysee platform...")
        await platform.initialize()
        
        # Test 1: Search for videos
        print("\n[TEST 1] Testing video search...")
        search_query = "music"
        results = await platform.search_videos(search_query, max_results=3)
        
        if results:
            print(f"✅ Search successful! Found {len(results)} results for '{search_query}'")
            for i, result in enumerate(results, 1):
                print(f"\n  Result {i}:")
                print(f"    Title: {result.get('title', 'N/A')}")
                print(f"    Channel: {result.get('channel', 'N/A')}")
                print(f"    ID: {result.get('id', 'N/A')}")
                print(f"    URL: {result.get('url', 'N/A')}")
        else:
            print(f"❌ No results found for '{search_query}'")
        
        # Test 2: Get video details
        if results:
            print("\n[TEST 2] Testing video details retrieval...")
            video_id = results[0].get('id')
            details = await platform.get_video_details(video_id)
            
            if details:
                print(f"✅ Video details retrieved successfully!")
                print(f"    Title: {details.get('title', 'N/A')}")
                print(f"    Description: {details.get('description', 'N/A')[:100]}...")
            else:
                print(f"❌ Failed to get video details for ID: {video_id}")
        
        # Test 3: Get stream URL
        if results:
            print("\n[TEST 3] Testing stream URL extraction...")
            video_id = results[0].get('id')
            stream_url = await platform.get_stream_url(video_id)
            
            if stream_url:
                print(f"✅ Stream URL extracted successfully!")
                print(f"    URL: {stream_url[:100]}...")
            else:
                print(f"❌ Failed to get stream URL for ID: {video_id}")
        
        # Test 4: Platform status
        print("\n[TEST 4] Platform status:")
        status = platform.get_platform_status()
        print(f"  Environment: {status['environment']}")
        print(f"  Session Status: {status['session_status']}")
        print(f"  Consecutive Failures: {status['consecutive_failures']}")
        print(f"  Timeout Multiplier: {status['adaptive_timeout_multiplier']}")
        print(f"  Configured Timeouts: {status['configured_timeouts']}")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nCleaning up...")
        await platform.cleanup()

async def test_api_endpoints():
    """Test raw API endpoint connectivity"""
    import aiohttp
    
    print("\n[RAW API TEST] Testing direct API connectivity...")
    
    endpoints = [
        ("https://api.odysee.com/api/v1/claim_search", "Odysee API (new)"),
        ("https://api.lbry.tv/api/v1/proxy", "LBRY API (old)"),
        ("https://cdn.odysee.live/content/claims/test/stream", "Odysee CDN"),
    ]
    
    async with aiohttp.ClientSession() as session:
        for url, name in endpoints:
            try:
                print(f"\n  Testing {name}: {url}")
                async with session.head(url, timeout=10) as response:
                    print(f"    Status: {response.status}")
                    print(f"    Headers: {dict(response.headers)}")
            except Exception as e:
                print(f"    ❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("=== Odysee Platform Connection Fix Test ===\n")
    
    # Run API endpoint tests first
    asyncio.run(test_api_endpoints())
    
    # Run platform tests
    asyncio.run(test_odysee_connection())
    
    print("\n=== Test Complete ===")