from unittest.mock import AsyncMock, Mock

import pytest

from src.platforms.registry import PlatformRegistry
from src.services.searcher import MultiPlatformSearcher


@pytest.fixture
def mock_platform():
    platform = Mock()
    platform.name = "test_platform"
    platform.enabled = True
    platform.search_videos = AsyncMock(
        return_value=[
            {"id": "1", "title": "Test Video 1", "platform": "test_platform"},
            {"id": "2", "title": "Test Video 2", "platform": "test_platform"},
        ]
    )
    platform.get_video_details = AsyncMock(
        return_value={"id": "1", "title": "Test Video 1", "platform": "test_platform"}
    )
    platform.is_platform_url = Mock(return_value=False)
    platform.extract_video_id = Mock(return_value=None)
    return platform


@pytest.fixture
def platform_registry(mock_platform):
    registry = PlatformRegistry()
    registry.platforms = {"test_platform": mock_platform}
    return registry


@pytest.fixture
def searcher(platform_registry):
    return MultiPlatformSearcher(platform_registry)


@pytest.mark.asyncio
async def test_search_all_platforms(searcher, mock_platform):
    results = await searcher.search_all_platforms("test query")

    assert "test_platform" in results
    assert len(results["test_platform"]) == 2
    assert results["test_platform"][0]["title"] == "Test Video 1"
    mock_platform.search_videos.assert_called_once_with("test query", 10)


@pytest.mark.asyncio
async def test_search_with_url(searcher, mock_platform):
    # Setup URL detection
    mock_platform.is_platform_url.return_value = True
    mock_platform.extract_video_id.return_value = "video123"

    url = "https://test_platform.com/watch?v=video123"
    results = await searcher.search_all_platforms(url)

    assert "test_platform" in results
    mock_platform.get_video_details.assert_called_once_with("video123")


@pytest.mark.asyncio
async def test_search_error_handling(searcher, mock_platform):
    mock_platform.search_videos.side_effect = Exception("Search failed")

    results = await searcher.search_all_platforms("test query")

    assert results["test_platform"] == []


@pytest.mark.asyncio
async def test_search_multiple_platforms(platform_registry):
    # Add another platform
    mock_platform2 = Mock()
    mock_platform2.name = "test_platform2"
    mock_platform2.enabled = True
    mock_platform2.search_videos = AsyncMock(
        return_value=[
            {"id": "3", "title": "Test Video 3", "platform": "test_platform2"}
        ]
    )
    mock_platform2.get_video_details = AsyncMock(
        return_value={"id": "3", "title": "Test Video 3", "platform": "test_platform2"}
    )
    mock_platform2.is_platform_url = Mock(return_value=False)
    mock_platform2.extract_video_id = Mock(return_value=None)

    platform_registry.platforms["test_platform2"] = mock_platform2
    searcher = MultiPlatformSearcher(platform_registry)

    results = await searcher.search_all_platforms("test query")

    assert "test_platform" in results
    assert "test_platform2" in results
    assert len(results["test_platform"]) == 2
    assert len(results["test_platform2"]) == 1


@pytest.mark.asyncio
async def test_extract_video_info(searcher, mock_platform):
    mock_platform.is_platform_url.return_value = True
    mock_platform.extract_video_id.return_value = "abc123"

    url = "https://test_platform.com/video/abc123"
    info = searcher._extract_video_info(url)

    assert info is not None
    assert info["platform"] == "test_platform"
    assert info["id"] == "abc123"
    assert info["url"] == url


@pytest.mark.asyncio
async def test_search_for_mirrors(searcher, mock_platform):
    video_info = {
        "platform": "test_platform",
        "id": "123",
        "url": "https://test_platform.com/video/123",
    }

    results = await searcher._search_for_mirrors(video_info, 5)

    assert "test_platform" in results
    mock_platform.get_video_details.assert_called_once_with("123")


@pytest.fixture
def mock_rumble_platform():
    """Mock Rumble platform for testing"""
    platform = Mock()
    platform.name = "rumble"
    platform.enabled = True
    platform.search_videos = AsyncMock(
        return_value=[
            {
                "id": "v1abc123",
                "title": "Rumble Test Video 1",
                "platform": "rumble",
                "channel": "Test Channel",
                "url": "https://rumble.com/v1abc123",
            },
            {
                "id": "v2def456",
                "title": "Rumble Test Video 2",
                "platform": "rumble",
                "channel": "Another Channel",
                "url": "https://rumble.com/v2def456",
            },
        ]
    )
    platform.get_video_details = AsyncMock(
        return_value={
            "id": "v1abc123",
            "title": "Rumble Test Video 1",
            "platform": "rumble",
            "channel": "Test Channel",
            "url": "https://rumble.com/v1abc123",
            "description": "Test description",
            "duration": 300,
            "views": 1000,
        }
    )
    platform.is_platform_url = Mock(side_effect=lambda url: "rumble.com" in url)
    platform.extract_video_id = Mock(
        side_effect=lambda url: (
            url.split("/")[-1].split(".")[0] if "rumble.com" in url else None
        )
    )
    return platform


@pytest.mark.asyncio
async def test_rumble_search_query(searcher, platform_registry, mock_rumble_platform):
    """Test Rumble search functionality"""
    platform_registry.platforms["rumble"] = mock_rumble_platform
    
    results = await searcher.search_all_platforms("test video")
    
    assert "rumble" in results
    assert len(results["rumble"]) == 2
    assert results["rumble"][0]["title"] == "Rumble Test Video 1"
    assert results["rumble"][1]["title"] == "Rumble Test Video 2"
    mock_rumble_platform.search_videos.assert_called_once_with("test video", 10)


@pytest.mark.asyncio
async def test_rumble_url_detection(searcher, platform_registry, mock_rumble_platform):
    """Test Rumble URL detection and extraction"""
    platform_registry.platforms["rumble"] = mock_rumble_platform
    
    # Test standard Rumble URL
    url = "https://rumble.com/v1abc123"
    info = searcher._extract_video_info(url)
    
    assert info is not None
    assert info["platform"] == "rumble"
    assert info["id"] == "v1abc123"
    assert info["url"] == url
    
    # Test embed URL
    embed_url = "https://rumble.com/embed/v1abc123"
    mock_rumble_platform.extract_video_id.side_effect = lambda url: (
        url.split("/")[-1] if "rumble.com" in url else None
    )
    info = searcher._extract_video_info(embed_url)
    
    assert info is not None
    assert info["platform"] == "rumble"
    assert info["id"] == "v1abc123"


@pytest.mark.asyncio
async def test_rumble_url_search(searcher, platform_registry, mock_rumble_platform):
    """Test searching with Rumble URL"""
    platform_registry.platforms["rumble"] = mock_rumble_platform
    
    url = "https://rumble.com/v1abc123"
    results = await searcher.search_all_platforms(url)
    
    assert "rumble" in results
    mock_rumble_platform.get_video_details.assert_called_once_with("v1abc123")


@pytest.mark.asyncio
async def test_rumble_search_error(searcher, platform_registry, mock_rumble_platform):
    """Test Rumble search error handling"""
    platform_registry.platforms["rumble"] = mock_rumble_platform
    mock_rumble_platform.search_videos.side_effect = Exception("API error")
    
    results = await searcher.search_all_platforms("test query")
    
    assert results["rumble"] == []


@pytest.mark.asyncio
async def test_rumble_mirrors(searcher, platform_registry, mock_rumble_platform, mock_platform):
    """Test searching for mirrors of Rumble videos on other platforms"""
    platform_registry.platforms["rumble"] = mock_rumble_platform
    
    # Set up the mock platforms for mirror search
    mock_rumble_platform.get_video_details.return_value = {
        "id": "v1abc123",
        "title": "Rumble Test Video",
        "platform": "rumble",
    }
    
    video_info = {"platform": "rumble", "id": "v1abc123", "url": "https://rumble.com/v1abc123"}
    results = await searcher._search_for_mirrors(video_info, 5)
    
    assert "rumble" in results  # Original video
    assert "test_platform" in results  # Mirror search results
    mock_platform.search_videos.assert_called_once_with("Rumble Test Video", 5)


@pytest.mark.asyncio
async def test_rumble_no_api_token(searcher, platform_registry):
    """Test Rumble search when API token is not configured"""
    # Create a platform without API token
    no_token_platform = Mock()
    no_token_platform.name = "rumble"
    no_token_platform.enabled = True
    no_token_platform.search_videos = AsyncMock(return_value=[])
    no_token_platform.get_video_details = AsyncMock(return_value=None)
    no_token_platform.is_platform_url = Mock(side_effect=lambda url: "rumble.com" in url)
    no_token_platform.extract_video_id = Mock(return_value=None)
    
    platform_registry.platforms["rumble"] = no_token_platform
    
    results = await searcher.search_all_platforms("test query")
    
    assert results["rumble"] == []


@pytest.mark.asyncio
async def test_mixed_platform_search_with_rumble(platform_registry, mock_platform, mock_rumble_platform):
    """Test searching across multiple platforms including Rumble"""
    platform_registry.platforms["rumble"] = mock_rumble_platform
    searcher = MultiPlatformSearcher(platform_registry)
    
    results = await searcher.search_all_platforms("test query")
    
    assert "test_platform" in results
    assert "rumble" in results
    assert len(results["test_platform"]) == 2
    assert len(results["rumble"]) == 2
    assert results["rumble"][0]["platform"] == "rumble"
    assert results["test_platform"][0]["platform"] == "test_platform"
