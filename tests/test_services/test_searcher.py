import pytest
from unittest.mock import Mock, AsyncMock
from src.services.searcher import MultiPlatformSearcher
from src.platforms.registry import PlatformRegistry

@pytest.fixture
def mock_platform():
    platform = Mock()
    platform.name = "test_platform"
    platform.enabled = True
    platform.search_videos = AsyncMock(return_value=[
        {'id': '1', 'title': 'Test Video 1', 'platform': 'test_platform'},
        {'id': '2', 'title': 'Test Video 2', 'platform': 'test_platform'}
    ])
    platform.get_video_details = AsyncMock(return_value={
        'id': '1', 
        'title': 'Test Video 1', 
        'platform': 'test_platform'
    })
    platform.is_platform_url = Mock(return_value=False)
    platform.extract_video_id = Mock(return_value=None)
    return platform

@pytest.fixture
def platform_registry(mock_platform):
    registry = PlatformRegistry()
    registry.platforms = {'test_platform': mock_platform}
    return registry

@pytest.fixture
def searcher(platform_registry):
    return MultiPlatformSearcher(platform_registry)

@pytest.mark.asyncio
async def test_search_all_platforms(searcher, mock_platform):
    results = await searcher.search_all_platforms("test query")
    
    assert 'test_platform' in results
    assert len(results['test_platform']) == 2
    assert results['test_platform'][0]['title'] == 'Test Video 1'
    mock_platform.search_videos.assert_called_once_with("test query", 10)

@pytest.mark.asyncio
async def test_search_with_url(searcher, mock_platform):
    # Setup URL detection
    mock_platform.is_platform_url.return_value = True
    mock_platform.extract_video_id.return_value = "video123"
    
    url = "https://test_platform.com/watch?v=video123"
    results = await searcher.search_all_platforms(url)
    
    assert 'test_platform' in results
    mock_platform.get_video_details.assert_called_once_with("video123")

@pytest.mark.asyncio
async def test_search_error_handling(searcher, mock_platform):
    mock_platform.search_videos.side_effect = Exception("Search failed")
    
    results = await searcher.search_all_platforms("test query")
    
    assert results['test_platform'] == []

@pytest.mark.asyncio
async def test_search_multiple_platforms(platform_registry):
    # Add another platform
    mock_platform2 = Mock()
    mock_platform2.name = "test_platform2"
    mock_platform2.enabled = True
    mock_platform2.search_videos = AsyncMock(return_value=[
        {'id': '3', 'title': 'Test Video 3', 'platform': 'test_platform2'}
    ])
    
    platform_registry.platforms['test_platform2'] = mock_platform2
    searcher = MultiPlatformSearcher(platform_registry)
    
    results = await searcher.search_all_platforms("test query")
    
    assert 'test_platform' in results
    assert 'test_platform2' in results
    assert len(results['test_platform']) == 2
    assert len(results['test_platform2']) == 1

@pytest.mark.asyncio
async def test_extract_video_info(searcher, mock_platform):
    mock_platform.is_platform_url.return_value = True
    mock_platform.extract_video_id.return_value = "abc123"
    
    url = "https://test_platform.com/video/abc123"
    info = searcher._extract_video_info(url)
    
    assert info is not None
    assert info['platform'] == 'test_platform'
    assert info['id'] == 'abc123'
    assert info['url'] == url

@pytest.mark.asyncio
async def test_search_for_mirrors(searcher, mock_platform):
    video_info = {
        'platform': 'test_platform',
        'id': '123',
        'url': 'https://test_platform.com/video/123'
    }
    
    results = await searcher._search_for_mirrors(video_info, 5)
    
    assert 'test_platform' in results
    mock_platform.get_video_details.assert_called_once_with('123')