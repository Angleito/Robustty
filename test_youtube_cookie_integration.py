#!/usr/bin/env python3
"""Test YouTube cookie integration end-to-end"""
import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.platforms.youtube import YouTubePlatform

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_cookies():
    """Create test YouTube cookies in the expected format"""
    test_cookies = [
        {
            "name": "CONSENT",
            "value": "PENDING+123",
            "domain": ".youtube.com",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expires": 1735689600  # Future timestamp
        },
        {
            "name": "VISITOR_INFO1_LIVE",
            "value": "test_visitor_info",
            "domain": ".youtube.com", 
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expires": 1735689600
        },
        {
            "name": "__Secure-YEC",
            "value": "test_yec_value",
            "domain": ".youtube.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "expires": 1735689600
        }
    ]
    
    # Create cookies directory and save test cookies
    cookie_dir = Path('test_cookies')
    cookie_dir.mkdir(exist_ok=True)
    
    json_file = cookie_dir / 'youtube_cookies.json'
    with open(json_file, 'w') as f:
        json.dump(test_cookies, f, indent=2)
    
    logger.info(f"Created test cookies at {json_file}")
    return json_file


def test_cookie_conversion():
    """Test cookie conversion from JSON to Netscape format"""
    logger.info("Testing cookie conversion...")
    
    # Create test cookies
    json_file = create_test_cookies()
    netscape_file = json_file.parent / 'youtube_cookies.txt'
    
    # Create YouTube platform instance
    config = {'api_key': 'test_key'}
    platform = YouTubePlatform('youtube', config)
    
    # Test conversion
    success = platform._convert_cookies_to_netscape(str(json_file), str(netscape_file))
    
    if success and netscape_file.exists():
        logger.info("✓ Cookie conversion successful")
        
        # Read and validate Netscape format
        with open(netscape_file, 'r') as f:
            content = f.read()
            logger.info(f"Netscape file content preview:\n{content[:200]}...")
            
            # Basic validation
            assert "# Netscape HTTP Cookie File" in content
            assert ".youtube.com" in content
            assert "CONSENT" in content
            
        return True
    else:
        logger.error("✗ Cookie conversion failed")
        return False


async def test_stream_url_extraction():
    """Test stream URL extraction with cookie handling"""
    logger.info("Testing stream URL extraction...")
    
    # Create test cookies
    json_file = create_test_cookies()
    
    # Mock the cookies directory to point to our test location
    with patch('pathlib.Path') as mock_path:
        # Setup mock for cookie file existence check
        mock_json_path = MagicMock()
        mock_json_path.exists.return_value = True
        
        mock_netscape_path = MagicMock()
        mock_netscape_path.parent.mkdir = MagicMock()
        
        def path_side_effect(path_str):
            if 'youtube_cookies.json' in path_str:
                return mock_json_path
            elif 'youtube_cookies.txt' in path_str:
                return mock_netscape_path
            else:
                return Path(path_str)
        
        mock_path.side_effect = path_side_effect
        
        # Create platform instance
        config = {'api_key': 'test_key'}
        platform = YouTubePlatform('youtube', config)
        
        # Mock the conversion method to use our test files
        original_convert = platform._convert_cookies_to_netscape
        def mock_convert(json_path, netscape_path):
            return original_convert(str(json_file), str(json_file.parent / 'youtube_cookies.txt'))
        
        platform._convert_cookies_to_netscape = mock_convert
        
        # Mock yt-dlp to avoid actual network calls
        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            mock_ydl_instance = MagicMock()
            mock_ydl_instance.extract_info.return_value = {
                'url': 'https://example.com/test_stream.m4a'
            }
            mock_ydl.return_value.__enter__.return_value = mock_ydl_instance
            
            # Mock URL validation
            with patch('requests.head') as mock_head:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_head.return_value = mock_response
                
                # Test stream URL extraction
                stream_url = await platform.get_stream_url('test_video_id')
                
                if stream_url:
                    logger.info(f"✓ Stream URL extraction successful: {stream_url}")
                    
                    # Verify that cookiefile was set in yt-dlp options
                    mock_ydl.assert_called_once()
                    call_args = mock_ydl.call_args[0][0]  # First positional argument (ydl_opts)
                    
                    # Check if cookiefile is in the options (should be set by conversion)
                    if 'cookiefile' in call_args:
                        logger.info("✓ Cookies were used in yt-dlp extraction")
                    else:
                        logger.warning("⚠ No cookiefile found in yt-dlp options")
                    
                    return True
                else:
                    logger.error("✗ Stream URL extraction failed")
                    return False


def test_cookie_path_standardization():
    """Test that all components use the standardized cookie paths"""
    logger.info("Testing cookie path standardization...")
    
    expected_json_path = "/app/cookies/youtube_cookies.json"
    expected_netscape_path = "/app/cookies/youtube_cookies.txt"
    
    # Test YouTube platform
    config = {'api_key': 'test_key'}
    platform = YouTubePlatform('youtube', config)
    
    # Mock file paths in get_stream_url to capture what paths are used
    original_get_stream = platform.get_stream_url
    captured_paths = {}
    
    async def mock_get_stream(video_id):
        # Capture the paths used in the method
        import inspect
        source = inspect.getsource(platform.get_stream_url)
        
        if expected_json_path in source:
            captured_paths['json'] = expected_json_path
        if expected_netscape_path in source:
            captured_paths['netscape'] = expected_netscape_path
            
        return None  # Don't actually extract
    
    platform.get_stream_url = mock_get_stream
    
    # Trigger the method to capture paths
    asyncio.create_task(platform.get_stream_url('test'))
    
    # Check captured paths
    if captured_paths.get('json') == expected_json_path:
        logger.info("✓ JSON cookie path is standardized")
    else:
        logger.error("✗ JSON cookie path not standardized")
        
    if captured_paths.get('netscape') == expected_netscape_path:
        logger.info("✓ Netscape cookie path is standardized")
    else:
        logger.error("✗ Netscape cookie path not standardized")
    
    return len(captured_paths) == 2


def cleanup_test_files():
    """Clean up test files"""
    import shutil
    test_dir = Path('test_cookies')
    if test_dir.exists():
        shutil.rmtree(test_dir)
        logger.info("✓ Test files cleaned up")


async def main():
    """Run all integration tests"""
    logger.info("YouTube Cookie Integration Test")
    logger.info("===============================")
    
    success_count = 0
    total_tests = 3
    
    try:
        # Test 1: Cookie conversion
        if test_cookie_conversion():
            success_count += 1
        
        # Test 2: Stream URL extraction
        if await test_stream_url_extraction():
            success_count += 1
        
        # Test 3: Path standardization
        if test_cookie_path_standardization():
            success_count += 1
        
        # Summary
        logger.info(f"\nTest Results: {success_count}/{total_tests} tests passed")
        
        if success_count == total_tests:
            logger.info("🎉 All YouTube cookie integration tests passed!")
        else:
            logger.warning(f"⚠ {total_tests - success_count} test(s) failed")
            
    finally:
        cleanup_test_files()


if __name__ == "__main__":
    asyncio.run(main())