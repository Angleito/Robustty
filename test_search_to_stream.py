#!/usr/bin/env python3
import asyncio
import os
import aiohttp
from src.platforms.youtube import YouTubePlatform
from src.services.searcher import Searcher
from src.platforms.registry import PlatformRegistry

async def test_flow():
    # Initialize registry and platforms
    registry = PlatformRegistry()
    
    # Create YouTube platform
    yt_config = {
        'api_key': os.getenv('YOUTUBE_API_KEY'),
        'enabled': True
    }
    youtube = YouTubePlatform(yt_config)
    registry.register_platform('youtube', YouTubePlatform)
    registry.loaded_platforms['youtube'] = youtube
    
    # Create searcher
    searcher = Searcher(registry.loaded_platforms, {'enabled': True, 'max_results': 3})
    
    # Search for a song
    query = "Joji - SLOW DANCING IN THE DARK"
    print(f"Searching for: {query}")
    results = await searcher.search(query)
    
    if not results or not results.get('youtube'):
        print("No results found")
        return
        
    # Get first result
    first_result = results['youtube'][0]
    print(f"\nFirst result:")
    print(f"  Title: {first_result['title']}")
    print(f"  ID: {first_result['id']} (length: {len(first_result['id'])})")
    print(f"  URL: {first_result['url']}")
    
    # Test stream service
    stream_service_url = "http://localhost:5000"
    platform = first_result['platform']
    video_id = first_result['id']
    
    stream_url = f"{stream_service_url}/stream/{platform}/{video_id}"
    print(f"\nTesting stream service:")
    print(f"  URL: {stream_url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(stream_url) as response:
                print(f"  Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"  Stream URL: {data.get('stream_url', 'Not found')[:50]}...")
                else:
                    print(f"  Error: {await response.text()}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_flow())