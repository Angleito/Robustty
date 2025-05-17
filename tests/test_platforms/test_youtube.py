import pytest
from unittest.mock import Mock, patch
from src.platforms.youtube import YouTubePlatform

@pytest.fixture
def youtube_platform():
    config = {
        'enabled': True,
        'api_key': 'test_api_key'
    }
    return YouTubePlatform(config)

@pytest.mark.asyncio
async def test_search_videos(youtube_platform):
    with patch.object(youtube_platform, 'youtube') as mock_youtube:
        # Mock YouTube API response
        mock_search = Mock()
        mock_youtube.search.return_value.list.return_value = mock_search
        mock_search.execute.return_value = {
            'items': [{
                'id': {'videoId': 'test123'},
                'snippet': {
                    'title': 'Test Video',
                    'channelTitle': 'Test Channel',
                    'thumbnails': {'high': {'url': 'http://example.com/thumb.jpg'}}
                }
            }]
        }
        
        results = await youtube_platform.search_videos('test query')
        
        assert len(results) == 1
        assert results[0]['id'] == 'test123'
        assert results[0]['title'] == 'Test Video'
        assert results[0]['platform'] == 'youtube'

def test_extract_video_id(youtube_platform):
    # Test various YouTube URL formats
    urls = [
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
        ('https://youtu.be/dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
        ('https://www.youtube.com/embed/dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
    ]
    
    for url, expected_id in urls:
        assert youtube_platform.extract_video_id(url) == expected_id

def test_is_platform_url(youtube_platform):
    assert youtube_platform.is_platform_url('https://www.youtube.com/watch?v=test')
    assert youtube_platform.is_platform_url('https://youtu.be/test')
    assert not youtube_platform.is_platform_url('https://vimeo.com/test')

@pytest.mark.asyncio
async def test_get_video_details(youtube_platform):
    with patch.object(youtube_platform, 'youtube') as mock_youtube:
        mock_videos = Mock()
        mock_youtube.videos.return_value.list.return_value = mock_videos
        mock_videos.execute.return_value = {
            'items': [{
                'snippet': {
                    'title': 'Test Video',
                    'channelTitle': 'Test Channel',
                    'thumbnails': {'high': {'url': 'http://example.com/thumb.jpg'}},
                    'description': 'Test description'
                },
                'contentDetails': {
                    'duration': 'PT3M45S'
                },
                'statistics': {
                    'viewCount': '1000'
                }
            }]
        }
        
        details = await youtube_platform.get_video_details('test123')
        
        assert details['title'] == 'Test Video'
        assert details['duration'] == 'PT3M45S'
        assert details['views'] == '1000'

@pytest.mark.asyncio
async def test_initialize(youtube_platform):
    await youtube_platform.initialize()
    assert youtube_platform.session is not None
    assert youtube_platform.youtube is not None
    await youtube_platform.cleanup()

@pytest.mark.asyncio
async def test_search_error_handling(youtube_platform):
    with patch.object(youtube_platform, 'youtube') as mock_youtube:
        mock_youtube.search.side_effect = Exception("API Error")
        
        results = await youtube_platform.search_videos('test query')
        assert results == []