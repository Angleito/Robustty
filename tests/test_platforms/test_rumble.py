"""Comprehensive tests for Rumble platform implementation."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.platforms.rumble import RumblePlatform
from src.platforms.errors import (
    PlatformAuthenticationError,
    PlatformNotAvailableError,
    PlatformRateLimitError,
    PlatformAPIError,
)


class TestRumblePlatform:
    """Test suite for Rumble platform implementation."""

    @pytest.fixture
    def config(self):
        """Sample configuration for Rumble platform."""
        return {
            "enabled": True,
            "api_token": "test_api_token_123",
        }

    @pytest.fixture
    def platform(self, config):
        """Create a Rumble platform instance."""
        return RumblePlatform("rumble", config)

    @pytest.fixture
    def mock_search_response(self):
        """Mock search response from Rumble extractor."""
        return [
            {
                "id": "v4abcd",
                "title": "Test Video 1",
                "uploader": "Test Channel 1",
                "thumbnail_url": "https://sp.rmbl.ws/thumb1.jpg",
                "description": "Test description 1",
                "duration": 330,
                "view_count": 15000,
                "url": "https://rumble.com/v4abcd-test-video-1.html",
                "publish_date": "2023-01-01",
            },
            {
                "id": "v4efgh",
                "title": "Test Video 2",
                "uploader": "Test Channel 2",
                "thumbnail_url": "https://sp.rmbl.ws/thumb2.jpg",
                "description": "Test description 2",
                "duration": 615,
                "view_count": 25000,
                "url": "https://rumble.com/v4efgh-test-video-2.html",
                "publish_date": "2023-01-02",
            },
        ]

    @pytest.fixture
    def mock_video_details_response(self):
        """Mock video details response from Rumble extractor."""
        return {
            "title": "Test Video 1",
            "uploader": "Test Channel 1",
            "thumbnail_url": "https://sp.rmbl.ws/thumb1.jpg",
            "description": "Test description 1",
            "duration": 330,
            "view_count": 15000,
            "like_count": 1200,
            "url": "https://rumble.com/v4abcd-test-video-1.html",
            "publish_date": "2023-01-01",
        }

    @pytest.mark.asyncio
    async def test_initialization(self, platform, config):
        """Test platform initialization."""
        assert platform.name == "rumble"
        assert platform.api_token == config["api_token"]
        assert platform.url_patterns is not None
        assert len(platform.url_patterns) == 2

    @pytest.mark.asyncio
    async def test_initialize_with_token(self, platform):
        """Test platform initialization with API token."""
        with patch("src.platforms.rumble.logger") as mock_logger:
            with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
                await platform.initialize()
                assert platform.session is not None
                assert platform.extractor is not None
                mock_logger.info.assert_called_with("Rumble API token provided, extractor initialized")
                mock_extractor_class.assert_called_once_with(apify_api_token=platform.api_token)

    @pytest.mark.asyncio
    async def test_initialize_without_token(self, config):
        """Test platform initialization without API token."""
        config["api_token"] = None
        platform = RumblePlatform("rumble", config)
        
        with patch("src.platforms.rumble.logger") as mock_logger:
            await platform.initialize()
            assert platform.session is not None
            assert platform.extractor is None
            mock_logger.warning.assert_called_with("Rumble API token not provided, searches will fail")

    @pytest.mark.asyncio
    async def test_search_videos_success(self, platform, mock_search_response):
        """Test successful video search."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.search_videos = AsyncMock(return_value=mock_search_response)
            
            platform.extractor = mock_extractor
            results = await platform.search_videos("test query", max_results=10)
            
            assert isinstance(results, list)
            assert len(results) == 2
            assert results[0]["title"] == "Test Video 1"
            assert results[0]["platform"] == "rumble"
            mock_extractor.search_videos.assert_called_once_with("test query", 10)

    @pytest.mark.asyncio
    async def test_search_videos_no_token(self, config):
        """Test search fails without API token."""
        config["api_token"] = None
        platform = RumblePlatform("rumble", config)
        await platform.initialize()
        
        with pytest.raises(PlatformAuthenticationError, match="API token is required for Rumble searches"):
            await platform.search_videos("test query")

    @pytest.mark.asyncio
    async def test_search_videos_empty_results(self, platform):
        """Test search with empty results."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.search_videos = AsyncMock(return_value=[])
            
            platform.extractor = mock_extractor
            results = await platform.search_videos("test query", max_results=10)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_videos_exception_handling(self, platform):
        """Test search exception handling."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.search_videos = AsyncMock(side_effect=Exception("Test error"))
            
            platform.extractor = mock_extractor
            
            with pytest.raises(PlatformAPIError, match="Search failed: Test error"):
                await platform.search_videos("test query")

    @pytest.mark.asyncio
    async def test_get_video_details_success(self, platform, mock_video_details_response):
        """Test getting video details successfully."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.get_video_metadata = AsyncMock(return_value=mock_video_details_response)
            
            platform.extractor = mock_extractor
            details = await platform.get_video_details("v4abcd")
            
            assert details is not None
            assert details["id"] == "v4abcd"
            assert details["title"] == "Test Video 1"
            assert details["platform"] == "rumble"
            mock_extractor.get_video_metadata.assert_called_once_with("https://rumble.com/v4abcd")

    @pytest.mark.asyncio
    async def test_get_video_details_no_token(self, config):
        """Test getting video details without API token."""
        config["api_token"] = None
        platform = RumblePlatform("rumble", config)
        await platform.initialize()
        
        with pytest.raises(PlatformAuthenticationError, match="API token is required for video details"):
            await platform.get_video_details("v4abcd")

    @pytest.mark.asyncio
    async def test_get_video_details_not_found(self, platform):
        """Test getting video details when video is not found."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.get_video_metadata = AsyncMock(
                side_effect=PlatformNotAvailableError("No metadata found", platform="Rumble")
            )
            
            platform.extractor = mock_extractor
            
            with pytest.raises(PlatformNotAvailableError):
                await platform.get_video_details("non-existent-id")

    @pytest.mark.asyncio
    async def test_get_video_details_exception_handling(self, platform):
        """Test video details exception handling."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.get_video_metadata = AsyncMock(side_effect=Exception("Test error"))
            
            platform.extractor = mock_extractor
            
            with pytest.raises(PlatformAPIError, match="Failed to get video details: Test error"):
                await platform.get_video_details("v4abcd")

    def test_extract_video_id_standard_url(self, platform):
        """Test extracting video ID from standard Rumble URL."""
        urls = [
            ("https://rumble.com/v4abcd-test-video.html", "v4abcd"),
            ("https://www.rumble.com/v4abcd-test-video.html", "v4abcd"),
            ("http://rumble.com/v4abcd-test-video.html", "v4abcd"),
            ("rumble.com/v4abcd-test-video.html", "v4abcd"),
        ]
        
        for url, expected_id in urls:
            assert platform.extract_video_id(url) == expected_id

    def test_extract_video_id_embed_url(self, platform):
        """Test extracting video ID from Rumble embed URL."""
        urls = [
            ("https://rumble.com/embed/v4abcd/", "v4abcd"),
            ("https://www.rumble.com/embed/v4abcd/", "v4abcd"),
            ("http://rumble.com/embed/v4abcd/", "v4abcd"),
            ("rumble.com/embed/v4abcd/", "v4abcd"),
        ]
        
        for url, expected_id in urls:
            assert platform.extract_video_id(url) == expected_id

    def test_extract_video_id_with_query_params(self, platform):
        """Test extracting video ID from URLs with query parameters."""
        urls_with_params = [
            ("https://rumble.com/v4abcd-test-video.html?t=120", "v4abcd"),
            ("https://www.rumble.com/v4abcd-test-video.html?autoplay=true", "v4abcd"),
            ("rumble.com/v4abcd-test-video.html?feature=share", "v4abcd"),
            ("https://rumble.com/embed/v4abcd/?pub=4", "v4abcd"),
        ]
        
        for url, expected_id in urls_with_params:
            assert platform.extract_video_id(url) == expected_id
    
    def test_extract_video_id_edge_cases(self, platform):
        """Test extracting video ID from edge case URLs."""
        edge_cases = [
            ("https://rumble.com/v4abcd", "v4abcd"),  # No trailing slash or .html
            ("https://rumble.com/v4abcd/", "v4abcd"),  # With trailing slash
            ("https://rumble.com/v4abcd#timestamp", "v4abcd"),  # With hash fragment
            ("https://rumble.com/embed/v4abcd", "v4abcd"),  # Embed without trailing slash
        ]
        
        for url, expected_id in edge_cases:
            assert platform.extract_video_id(url) == expected_id
    
    def test_extract_video_id_invalid_url(self, platform):
        """Test extracting video ID from invalid URL."""
        invalid_urls = [
            "https://youtube.com/watch?v=abc123",
            "https://vimeo.com/123456",
            "https://rumble.com/",
            "https://rumble.com/search?q=test",
            "not-a-url",
            "",
            "https://rumble.com/user/username",  # User profile URL
            "https://rumble.com/c/channel",  # Channel URL  
        ]
        
        for url in invalid_urls:
            assert platform.extract_video_id(url) is None

    def test_is_platform_url_valid(self, platform):
        """Test checking if URL belongs to Rumble platform."""
        valid_urls = [
            "https://rumble.com/v4abcd-test-video.html",
            "https://www.rumble.com/v4abcd-test-video.html",
            "http://rumble.com/v4abcd-test-video.html",
            "rumble.com/v4abcd-test-video.html",
            "https://rumble.com/embed/v4abcd/",
            "https://www.rumble.com/embed/v4abcd/",
        ]
        
        for url in valid_urls:
            assert platform.is_platform_url(url) is True

    def test_is_platform_url_invalid(self, platform):
        """Test checking if non-Rumble URLs are detected correctly."""
        invalid_urls = [
            "https://youtube.com/watch?v=abc123",
            "https://vimeo.com/123456",
            "https://peertube.example.com/videos/watch/abc",
            "https://example.com/rumble/video",
            "",
        ]
        
        for url in invalid_urls:
            assert platform.is_platform_url(url) is False

    @pytest.mark.asyncio
    async def test_get_stream_url(self, platform):
        """Test getting stream URL for a Rumble video."""
        video_id = "v4abcd"
        stream_url = await platform.get_stream_url(video_id)
        
        assert stream_url == f"http://robustty-stream:5000/stream/rumble/{video_id}"

    @pytest.mark.asyncio
    async def test_search_videos_max_results(self, platform, mock_search_response):
        """Test search respects max_results parameter."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.search_videos = AsyncMock(return_value=mock_search_response[:1])
            
            platform.extractor = mock_extractor
            results = await platform.search_videos("test query", max_results=1)
            assert len(results) == 1
            mock_extractor.search_videos.assert_called_once_with("test query", 1)

    @pytest.mark.asyncio
    async def test_cleanup(self, platform):
        """Test platform cleanup."""
        platform.session = MagicMock()
        platform.session.close = AsyncMock()
        
        await platform.cleanup()
        
        platform.session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_videos_with_special_characters(self, platform, mock_search_response):
        """Test search with special characters in query."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.search_videos = AsyncMock(return_value=mock_search_response)
            
            platform.extractor = mock_extractor
            
            # Test with special characters
            special_queries = [
                "test & query",
                "test | query",
                "test \"quoted\" query",
                "test 'single' query",
                "test @ # $ % query",
            ]
            
            for query in special_queries:
                results = await platform.search_videos(query)
                assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_missing_api_token_scenario(self, config):
        """Test behavior when API token is missing."""
        # Test with None token
        config["api_token"] = None
        platform = RumblePlatform("rumble", config)
        await platform.initialize()
        
        # Should raise authentication error
        with pytest.raises(PlatformAuthenticationError):
            await platform.search_videos("test")
        
        # Test video details should raise authentication error
        with pytest.raises(PlatformAuthenticationError):
            await platform.get_video_details("v4abcd")
        
        # Test with empty string token
        config["api_token"] = ""
        platform = RumblePlatform("rumble", config)
        await platform.initialize()
        
        with pytest.raises(PlatformAuthenticationError):
            await platform.search_videos("test")

    @pytest.mark.asyncio
    async def test_empty_search_results(self, platform):
        """Test handling of empty search results."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.search_videos = AsyncMock(return_value=[])
            
            platform.extractor = mock_extractor
            results = await platform.search_videos("very_specific_query_with_no_results")
            assert results == []
            assert isinstance(results, list)
        
    @pytest.mark.asyncio
    async def test_invalid_video_id_format(self, platform, mock_video_details_response):
        """Test handling of invalid video ID formats."""
        with patch("src.platforms.rumble.RumbleExtractor") as mock_extractor_class:
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.get_video_metadata = AsyncMock(return_value=mock_video_details_response)
            
            platform.extractor = mock_extractor
            
            invalid_ids = [
                "",  # Empty ID
                " ",  # Whitespace only
                "abc123",  # No 'v' prefix
                "v",  # Just 'v' without ID
                "v!@#$%",  # Special characters
                "v4abcd\n",  # Newline in ID
                "v4abcd v4efgh",  # Multiple IDs
            ]
            
            for invalid_id in invalid_ids:
                details = await platform.get_video_details(invalid_id)
                assert details is not None  # The platform will construct URL and let extractor handle