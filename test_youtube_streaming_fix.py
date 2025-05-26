#!/usr/bin/env python3
"""
Test script to verify YouTube streaming and cookie integration fixes
"""

import asyncio
import json
import logging
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from platforms.youtube import YouTubePlatform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_cookies():
    """Create test cookies for YouTube platform"""
    # Create test cookie directory
    cookie_dir = Path('/app/cookies')
    if not cookie_dir.exists():
        cookie_dir = Path('./cookies')
    cookie_dir.mkdir(exist_ok=True)
    
    # Create sample YouTube cookies (these would normally come from browser)
    test_cookies = [
        {
            'name': 'VISITOR_INFO1_LIVE',
            'value': 'test_visitor_info',
            'domain': '.youtube.com',
            'path': '/',
            'secure': True,
            'httpOnly': False,
            'expires': 9999999999  # Far future
        },
        {
            'name': 'YSC',
            'value': 'test_ysc_value',
            'domain': '.youtube.com',
            'path': '/',
            'secure': True,
            'httpOnly': True,
            'expires': 9999999999
        }
    ]
    
    cookie_file = cookie_dir / 'youtube_cookies.json'
    with open(cookie_file, 'w') as f:
        json.dump(test_cookies, f, indent=2)
    
    logger.info(f"Created test cookies at {cookie_file}")
    return cookie_file


async def test_youtube_platform():
    """Test YouTube platform functionality"""
    
    # Get API key from environment or skip if not available
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        logger.warning("No YOUTUBE_API_KEY found, some tests will be skipped")
    
    # Initialize YouTube platform
    config = {
        'api_key': api_key,
        'enabled': True
    }
    
    youtube = YouTubePlatform('youtube', config)
    await youtube.initialize()
    
    # Test 1: Cookie conversion
    logger.info("=== Testing Cookie Conversion ===")
    create_test_cookies()
    
    # Find cookie file
    cookie_paths = [
        Path('/app/cookies/youtube_cookies.json'),
        Path('./cookies/youtube_cookies.json'),
        Path('data/cookies/youtube_cookies.json')
    ]
    
    json_cookie_file = None
    for path in cookie_paths:
        if path.exists():
            json_cookie_file = str(path)
            break
    
    if json_cookie_file:
        netscape_file = str(Path(json_cookie_file).parent / 'youtube_cookies.txt')
        success = youtube._convert_cookies_to_netscape(json_cookie_file, netscape_file)
        
        if success:
            logger.info("✓ Cookie conversion successful")
            # Check if netscape file was created
            if Path(netscape_file).exists():
                logger.info(f"✓ Netscape cookie file created: {netscape_file}")
                # Show content
                with open(netscape_file, 'r') as f:
                    content = f.read()
                    logger.debug(f"Cookie file content:\n{content}")
            else:
                logger.error("✗ Netscape cookie file not created")
        else:
            logger.error("✗ Cookie conversion failed")
    else:
        logger.warning("No cookie file found for testing")
    
    # Test 2: URL validation
    logger.info("\n=== Testing URL Validation ===")
    
    # Test with a known good URL
    test_url = "https://www.google.com"
    is_valid = await youtube._validate_stream_url_async(test_url)
    logger.info(f"URL validation for {test_url}: {'✓ Valid' if is_valid else '✗ Invalid'}")
    
    # Test 3: Video ID extraction
    logger.info("\n=== Testing Video ID Extraction ===")
    
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "invalid_url"
    ]
    
    for url in test_urls:
        video_id = youtube.extract_video_id(url)
        logger.info(f"URL: {url[:40]}... -> Video ID: {video_id or 'None'}")
    
    # Test 4: Search (if API key available)
    if api_key:
        logger.info("\n=== Testing YouTube Search ===")
        try:
            results = await youtube.search_videos("test", max_results=3)
            logger.info(f"✓ Search returned {len(results)} results")
            for i, result in enumerate(results[:2], 1):
                logger.info(f"  {i}. {result.get('title', 'Unknown')} ({result.get('id', 'No ID')})")
        except Exception as e:
            logger.error(f"✗ Search failed: {e}")
    else:
        logger.info("Skipping search test (no API key)")
    
    # Test 5: Stream URL extraction (careful - this makes real requests)
    logger.info("\n=== Testing Stream URL Extraction ===")
    
    # Use a known short video for testing (Rick Roll is always available)
    test_video_id = "dQw4w9WgXcQ"
    
    try:
        logger.info(f"Attempting to get stream URL for video: {test_video_id}")
        stream_url = await youtube.get_stream_url(test_video_id)
        
        if stream_url:
            logger.info(f"✓ Stream URL obtained: {stream_url[:100]}...")
            
            # Validate the stream URL
            is_valid = await youtube._validate_stream_url_async(stream_url)
            logger.info(f"Stream URL validation: {'✓ Valid' if is_valid else '✗ Invalid'}")
        else:
            logger.error("✗ No stream URL returned")
            
    except Exception as e:
        logger.error(f"✗ Stream extraction failed: {e}")
        import traceback
        logger.debug(f"Full traceback: {traceback.format_exc()}")
    
    logger.info("\n=== Test Complete ===")


async def main():
    """Main test function"""
    logger.info("Starting YouTube streaming and cookie integration tests")
    
    try:
        await test_youtube_platform()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)