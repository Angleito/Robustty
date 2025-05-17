import os
import sys
sys.path.append('/Users/angel/Documents/Projects/robustty/robustty')

from dotenv import load_dotenv
from src.platforms.youtube import YouTubePlatform

# Load environment variables
load_dotenv('.env')

# Create YouTube platform instance
config = {
    'api_key': os.getenv('YOUTUBE_API_KEY')
}
youtube = YouTubePlatform('youtube', config)

# Search for a song
import asyncio

async def main():
    # Initialize the platform
    await youtube.initialize()
    
    query = "Joji SLOW DANCING IN THE DARK"
    print(f"Searching for: {query}")
    
    results = await youtube.search_videos(query, 5)
    print(f"Found {len(results)} results")
    
    for i, result in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"  Title: {result['title']}")
        print(f"  ID: {result['id']} (length: {len(result['id'])})")
        print(f"  URL: {result['url']}")
        print(f"  Platform: {result['platform']}")
        print(f"  Channel: {result.get('channel', 'Unknown')}")

asyncio.run(main())