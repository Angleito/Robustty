"""Comprehensive tests for PeerTube platform implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientSession

from src.platforms.peertube import PeerTubePlatform
from src.platforms.peertube_types import SearchData, VideoInfo


class TestPeerTubePlatform:
    """Test suite for PeerTube platform implementation."""

    @pytest.fixture
    def config(self):
        """Sample configuration for PeerTube platform."""
        return {
            "enabled": True,
            "instances": ["https://peertube.example.com", "https://tube.test.com"],
            "max_results_per_instance": 5,
        }

    @pytest.fixture
    def platform(self, config):
        """Create a PeerTube platform instance."""
        return PeerTubePlatform(config)

    @pytest.fixture
    def mock_video_info(self) -> VideoInfo:
        """Mock video information from PeerTube API."""
        return {
            "uuid": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Test Video",
            "description": "A test video description",
            "duration": 120,
            "views": 1000,
            "likes": 50,
            "dislikes": 5,
            "publishedAt": "2023-01-01T00:00:00.000Z",
            "channel": {
                "displayName": "Test Channel",
                "name": "test_channel",
                "description": "A test channel",
                "url": "/channels/test_channel",
            },
            "thumbnailPath": "/thumbnails/test.jpg",
            "previewPath": "/previews/test.jpg",
            "files": [
                {
                    "fileUrl": "https://peertube.example.com/files/test_720p.mp4",
                    "resolution": {"id": 720, "label": "720p"},
                    "size": 10000000,
                    "torrentUrl": None,
                    "magnetUri": None,
                },
                {
                    "fileUrl": "https://peertube.example.com/files/test_480p.mp4",
                    "resolution": {"id": 480, "label": "480p"},
                    "size": 5000000,
                    "torrentUrl": None,
                    "magnetUri": None,
                },
            ],
        }

    @pytest.fixture
    def mock_search_response(self, mock_video_info) -> SearchData:
        """Mock search response from PeerTube API."""
        return {"data": [mock_video_info], "total": 1}

    @pytest.mark.asyncio
    async def test_initialization(self, platform, config):
        """Test platform initialization."""
        assert platform.name == "peertube"
        assert platform.instances == config["instances"]
        assert platform.max_results_per_instance == config["max_results_per_instance"]
        assert platform.url_pattern is not None

    @pytest.mark.asyncio
    async def test_search_videos_success(
        self, platform, mock_search_response, mock_video_info
    ):
        """Test successful video search across instances."""
        platform.instances = ["https://peertube.example.com"]  # Use only one instance for simpler testing

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_search_response)

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()

        platform.session = MagicMock(spec=ClientSession)
        platform.session.get = MagicMock(return_value=mock_context)

        results = await platform.search_videos("test query", max_results=10)

        assert len(results) == 1
        assert results[0]["id"] == mock_video_info["uuid"]
        assert results[0]["title"] == mock_video_info["name"]
        assert results[0]["channel"] == "Test Channel"
        assert results[0]["platform"] == "peertube"

    @pytest.mark.asyncio
    async def test_search_videos_no_instances(self, platform):
        """Test search with no configured instances."""
        platform.instances = []
        results = await platform.search_videos("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_videos_403_error(self, platform):
        """Test search handling 403 Forbidden error."""
        mock_response = AsyncMock()
        mock_response.status = 403

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()

        platform.session = MagicMock(spec=ClientSession)
        platform.session.get = MagicMock(return_value=mock_context)

        results = await platform.search_videos("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_videos_general_error(self, platform):
        """Test search handling general HTTP errors."""
        mock_response = AsyncMock()
        mock_response.status = 500

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()

        platform.session = MagicMock(spec=ClientSession)
        platform.session.get = MagicMock(return_value=mock_context)

        results = await platform.search_videos("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_videos_exception_handling(self, platform):
        """Test search exception handling."""
        platform.session = MagicMock(spec=ClientSession)
        platform.session.get = MagicMock(side_effect=Exception("Network error"))

        results = await platform.search_videos("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_get_video_details_success(self, platform, mock_video_info):
        """Test getting video details successfully."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_video_info)

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()

        platform.session = MagicMock(spec=ClientSession)
        platform.session.get = MagicMock(return_value=mock_context)

        details = await platform.get_video_details(mock_video_info["uuid"])

        assert details is not None
        assert details["id"] == mock_video_info["uuid"]
        assert details["title"] == mock_video_info["name"]
        assert details["likes"] == mock_video_info["likes"]
        assert details["dislikes"] == mock_video_info["dislikes"]

    @pytest.mark.asyncio
    async def test_get_video_details_not_found(self, platform):
        """Test getting video details when video is not found."""
        mock_response = AsyncMock()
        mock_response.status = 404

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()

        platform.session = MagicMock(spec=ClientSession)
        platform.session.get = MagicMock(return_value=mock_context)

        details = await platform.get_video_details("non-existent-id")
        assert details is None

    def test_extract_video_id(self, platform):
        """Test extracting video ID from PeerTube URL."""
        url = "https://peertube.example.com/videos/watch/123e4567-e89b-12d3-a456-426614174000"
        video_id = platform.extract_video_id(url)
        assert video_id == "123e4567-e89b-12d3-a456-426614174000"

        invalid_url = "https://youtube.com/watch?v=abc123"
        video_id = platform.extract_video_id(invalid_url)
        assert video_id is None

    def test_is_platform_url(self, platform):
        """Test checking if URL belongs to PeerTube platform."""
        valid_url = "https://peertube.example.com/videos/watch/123e4567-e89b-12d3-a456-426614174000"
        assert platform.is_platform_url(valid_url) is True

        invalid_url = "https://youtube.com/watch?v=abc123"
        assert platform.is_platform_url(invalid_url) is False

    @pytest.mark.asyncio
    async def test_get_stream_url_success(self, platform, mock_video_info):
        """Test getting stream URL successfully."""
        video_id = mock_video_info["uuid"]

        with patch.object(
            platform, "get_video_details", return_value={"instance": "https://peertube.example.com"}
        ):
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_video_info)

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock()

            platform.session = MagicMock(spec=ClientSession)
            platform.session.get = MagicMock(return_value=mock_context)

            stream_url = await platform.get_stream_url(video_id)

            assert stream_url == mock_video_info["files"][0]["fileUrl"]

    @pytest.mark.asyncio
    async def test_get_stream_url_no_files(self, platform, mock_video_info):
        """Test getting stream URL when no files are available."""
        video_id = mock_video_info["uuid"]
        mock_video_info_no_files = mock_video_info.copy()
        mock_video_info_no_files["files"] = []

        with patch.object(
            platform, "get_video_details", return_value={"instance": "https://peertube.example.com"}
        ):
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_video_info_no_files)

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock()

            platform.session = MagicMock(spec=ClientSession)
            platform.session.get = MagicMock(return_value=mock_context)

            stream_url = await platform.get_stream_url(video_id)

            assert stream_url is None

    @pytest.mark.asyncio
    async def test_get_stream_url_video_not_found(self, platform):
        """Test getting stream URL when video is not found."""
        with patch.object(platform, "get_video_details", return_value=None):
            stream_url = await platform.get_stream_url("non-existent-id")
            assert stream_url is None

    @pytest.mark.asyncio
    async def test_session_not_initialized(self, platform):
        """Test error handling when session is not initialized."""
        platform.session = None
        results = await platform._search_instance("https://peertube.example.com", "test", 5)
        assert results == []

    @pytest.mark.asyncio
    async def test_sorting_by_views(self, platform, mock_search_response):
        """Test that search results are sorted by views."""
        platform.instances = ["https://peertube.example.com"]  # Use only one instance

        # Create multiple videos with different view counts
        video1 = mock_search_response["data"][0].copy()
        video1["views"] = 100
        video1["uuid"] = "video1"

        video2 = mock_search_response["data"][0].copy()
        video2["views"] = 500
        video2["uuid"] = "video2"

        video3 = mock_search_response["data"][0].copy()
        video3["views"] = 300
        video3["uuid"] = "video3"

        multi_search_response = {"data": [video1, video3, video2], "total": 3}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=multi_search_response)

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()

        platform.session = MagicMock(spec=ClientSession)
        platform.session.get = MagicMock(return_value=mock_context)

        results = await platform.search_videos("test query", max_results=3)

        # Should be sorted by views descending
        assert results[0]["id"] == "video2"  # 500 views
        assert results[1]["id"] == "video3"  # 300 views
        assert results[2]["id"] == "video1"  # 100 views

    @pytest.mark.asyncio
    async def test_channel_name_fallback(self, platform, mock_video_info):
        """Test channel name fallback when channel info is missing."""
        mock_video_info_no_channel = mock_video_info.copy()
        mock_video_info_no_channel["channel"] = None

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": [mock_video_info_no_channel], "total": 1})

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()

        platform.session = MagicMock(spec=ClientSession)
        platform.session.get = MagicMock(return_value=mock_context)

        results = await platform.search_videos("test query")

        assert results[0]["channel"] == "Unknown"
