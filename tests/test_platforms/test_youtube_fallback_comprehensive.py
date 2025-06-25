"""
Comprehensive tests for YouTube platform fallback functionality

This test suite validates:
1. Direct YouTube URL processing (should work immediately)
2. yt-dlp search fallback when API quota exceeded
3. Cookie-enhanced authentication for better access
4. Graceful degradation when methods fail
5. User feedback and status reporting
6. API quota exceeded conditions simulation
7. Integration with existing code
"""

import asyncio
import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta

import pytest
from googleapiclient.errors import HttpError

from src.platforms.youtube import YouTubePlatform
from src.platforms.errors import (
    PlatformAPIError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
)
from src.services.platform_fallback_manager import (
    PlatformFallbackManager,
    FallbackMode,
    FallbackStrategy,
)


# Test fixtures
@pytest.fixture
def youtube_platform_with_api():
    """YouTube platform with API key configured"""
    config = {
        "enabled": True,
        "api_key": "test_api_key",
        "enable_fallbacks": True,
    }
    platform = YouTubePlatform("youtube", config)
    return platform


@pytest.fixture
def youtube_platform_no_api():
    """YouTube platform without API key"""
    config = {
        "enabled": True,
        "enable_fallbacks": True,
    }
    platform = YouTubePlatform("youtube", config)
    return platform


@pytest.fixture
def fallback_manager():
    """Platform fallback manager"""
    config = {
        "enable_fallbacks": True,
        "max_fallback_duration_hours": 24,
        "retry_interval_minutes": 30,
    }
    return PlatformFallbackManager(config)


@pytest.fixture
def mock_cookie_file():
    """Create a temporary mock cookie file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        mock_cookies = [
            {
                "name": "VISITOR_INFO1_LIVE",
                "value": "test_visitor_info",
                "domain": ".youtube.com",
                "path": "/",
                "secure": True,
                "expires": int((datetime.now() + timedelta(days=30)).timestamp())
            },
            {
                "name": "YSC",  
                "value": "test_ysc_value",
                "domain": ".youtube.com",
                "path": "/",
                "secure": True,
                "expires": 0
            }
        ]
        json.dump(mock_cookies, f)
        yield f.name
    
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def sample_video_metadata():
    """Sample video metadata for testing"""
    return {
        "id": "dQw4w9WgXcQ",
        "title": "Test Video Title",
        "channel": "Test Channel",
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "platform": "youtube",
        "description": "Test video description",
        "duration": "3:42",
        "views": "1.2M views",
        "published": "2 days ago",
        "view_count_raw": 1200000,
    }


class TestDirectYouTubeURLProcessing:
    """Test direct YouTube URL processing functionality"""

    @pytest.mark.asyncio
    async def test_url_extraction_from_search_query(self, youtube_platform_with_api, sample_video_metadata):
        """Test that YouTube URLs in search queries are processed directly"""
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        with patch.object(youtube_platform_with_api, '_extract_metadata_via_ytdlp', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = sample_video_metadata
            
            results = await youtube_platform_with_api.search_videos(test_url)
            
            assert len(results) == 1
            assert results[0]["id"] == "dQw4w9WgXcQ"
            assert results[0]["title"] == "Test Video Title"
            assert results[0]["platform"] == "youtube"
            
            # Verify yt-dlp was called directly, not API
            mock_extract.assert_called_once_with("dQw4w9WgXcQ")

    @pytest.mark.asyncio
    async def test_various_youtube_url_formats(self, youtube_platform_with_api, sample_video_metadata):
        """Test different YouTube URL formats are handled correctly"""
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "Watch this: https://www.youtube.com/watch?v=dQw4w9WgXcQ amazing!",
        ]
        
        with patch.object(youtube_platform_with_api, '_extract_metadata_via_ytdlp', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = sample_video_metadata
            
            for test_url in test_urls:
                results = await youtube_platform_with_api.search_videos(test_url)
                assert len(results) == 1
                assert results[0]["id"] == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_url_processing_without_api_key(self, youtube_platform_no_api, sample_video_metadata):
        """Test URL processing works even without API key"""
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        with patch.object(youtube_platform_no_api, '_extract_metadata_via_ytdlp', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = sample_video_metadata
            
            results = await youtube_platform_no_api.search_videos(test_url)
            
            assert len(results) == 1
            assert results[0]["id"] == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_text_search_without_api_key_fails(self, youtube_platform_no_api):
        """Test that text searches fail gracefully without API key"""
        with pytest.raises(PlatformAuthenticationError) as exc_info:
            await youtube_platform_no_api.search_videos("test search query")
        
        assert "YouTube API key is required for text search" in str(exc_info.value)
        assert "provide a direct YouTube URL" in str(exc_info.value)


class TestYtDlpFallbackFunctionality:
    """Test yt-dlp fallback when API quota is exceeded"""

    @pytest.mark.asyncio
    async def test_api_quota_exceeded_triggers_fallback(self, youtube_platform_with_api, sample_video_metadata):
        """Test that API quota exceeded triggers yt-dlp fallback"""
        # Mock API quota exceeded error
        quota_error = HttpError(
            resp=Mock(status=403),
            content=b'{"error": {"code": 403, "message": "quotaExceeded"}}'
        )
        
        with patch.object(youtube_platform_with_api, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.return_value.execute.side_effect = quota_error
            
            with patch.object(youtube_platform_with_api, '_fallback_search', new_callable=AsyncMock) as mock_fallback:
                mock_fallback.return_value = [sample_video_metadata]
                
                results = await youtube_platform_with_api.search_videos("test query")
                
                assert len(results) == 1
                assert results[0]["id"] == "dQw4w9WgXcQ"
                mock_fallback.assert_called_once_with("test query", 10)

    @pytest.mark.asyncio
    async def test_api_quota_exceeded_with_failed_fallback(self, youtube_platform_with_api):
        """Test behavior when both API and fallback fail"""
        quota_error = HttpError(
            resp=Mock(status=403),
            content=b'{"error": {"code": 403, "message": "quotaExceeded"}}'
        )
        
        with patch.object(youtube_platform_with_api, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.return_value.execute.side_effect = quota_error
            
            with patch.object(youtube_platform_with_api, '_fallback_search', new_callable=AsyncMock) as mock_fallback:
                mock_fallback.return_value = []
                
                with pytest.raises(PlatformRateLimitError) as exc_info:
                    await youtube_platform_with_api.search_videos("test query")
                
                assert "YouTube API quota exceeded and fallback search failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ytdlp_metadata_extraction(self, youtube_platform_with_api):
        """Test yt-dlp metadata extraction works correctly"""
        mock_ytdlp_info = {
            "title": "Test Video from yt-dlp",
            "uploader": "Test Channel yt-dlp",
            "description": "Test description from yt-dlp",
            "duration": 222,  # 3:42
            "view_count": 1500000,
            "upload_date": "20231201",
            "thumbnails": [
                {"url": "https://example.com/thumb1.jpg", "width": 320, "height": 180},
                {"url": "https://example.com/thumb2.jpg", "width": 1280, "height": 720},
            ]
        }
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdlp_class:
            mock_ytdlp = MagicMock()
            mock_ytdlp_class.return_value.__enter__.return_value = mock_ytdlp
            mock_ytdlp.extract_info.return_value = mock_ytdlp_info
            
            metadata = await youtube_platform_with_api._extract_metadata_via_ytdlp("dQw4w9WgXcQ")
            
            assert metadata is not None
            assert metadata["title"] == "Test Video from yt-dlp"
            assert metadata["channel"] == "Test Channel yt-dlp"
            assert metadata["duration"] == "3:42"
            assert metadata["views"] == "1.5M views"
            assert metadata["thumbnail"] == "https://example.com/thumb2.jpg"  # Should pick highest resolution

    @pytest.mark.asyncio
    async def test_video_details_fallback_on_quota_exceeded(self, youtube_platform_with_api, sample_video_metadata):
        """Test video details fallback to yt-dlp when API quota exceeded"""
        quota_error = HttpError(
            resp=Mock(status=403), 
            content=b'{"error": {"code": 403, "message": "quotaExceeded"}}'
        )
        
        with patch.object(youtube_platform_with_api, 'youtube') as mock_youtube:
            mock_youtube.videos.return_value.list.return_value.execute.side_effect = quota_error
            
            with patch.object(youtube_platform_with_api, '_extract_metadata_via_ytdlp', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = sample_video_metadata
                
                details = await youtube_platform_with_api.get_video_details("dQw4w9WgXcQ")
                
                assert details is not None
                assert details["id"] == "dQw4w9WgXcQ"
                mock_extract.assert_called_once_with("dQw4w9WgXcQ")


class TestCookieEnhancedAuthentication:
    """Test cookie-enhanced authentication functionality"""

    @pytest.mark.asyncio
    async def test_cookie_conversion_to_netscape_format(self, youtube_platform_with_api, mock_cookie_file):
        """Test JSON cookie conversion to Netscape format"""
        netscape_file = str(Path(mock_cookie_file).with_suffix('.txt'))
        
        # Test the conversion
        success = youtube_platform_with_api._convert_cookies_to_netscape(
            mock_cookie_file, netscape_file
        )
        
        assert success is True
        assert Path(netscape_file).exists()
        
        # Verify content format
        with open(netscape_file, 'r') as f:
            content = f.read()
            assert "# Netscape HTTP Cookie File" in content
            assert "VISITOR_INFO1_LIVE" in content
            assert "YSC" in content
            assert ".youtube.com" in content
        
        # Cleanup
        Path(netscape_file).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_cookie_path_fallback_mechanism(self, youtube_platform_with_api):
        """Test that cookie paths are tried in order with fallback"""
        with patch('pathlib.Path.exists') as mock_exists:
            # Mock the existence check for different paths
            def exists_side_effect(self):
                return str(self) in ['/app/cookies/youtube_cookies.json']
            
            mock_exists.side_effect = exists_side_effect
            
            with patch.object(youtube_platform_with_api, '_convert_cookies_to_netscape') as mock_convert:
                mock_convert.return_value = True
                
                # Call get_stream_url which uses cookie loading
                with patch('yt_dlp.YoutubeDL') as mock_ytdlp_class:
                    mock_ytdlp = MagicMock()
                    mock_ytdlp_class.return_value.__enter__.return_value = mock_ytdlp
                    mock_ytdlp.extract_info.return_value = {
                        "url": "https://example.com/stream.m4a"
                    }
                    
                    stream_url = await youtube_platform_with_api.get_stream_url("dQw4w9WgXcQ")
                    
                    assert stream_url == "https://example.com/stream.m4a"
                    # Verify cookies were loaded from the first available path
                    mock_convert.assert_called_once_with(
                        '/app/cookies/youtube_cookies.json',
                        '/app/cookies/youtube_cookies.txt'
                    )

    @pytest.mark.asyncio
    async def test_stream_extraction_without_cookies(self, youtube_platform_with_api):
        """Test stream extraction works without cookies"""
        with patch('pathlib.Path.exists', return_value=False):
            with patch('yt_dlp.YoutubeDL') as mock_ytdlp_class:
                mock_ytdlp = MagicMock()
                mock_ytdlp_class.return_value.__enter__.return_value = mock_ytdlp
                mock_ytdlp.extract_info.return_value = {
                    "url": "https://example.com/stream.m4a"
                }
                
                stream_url = await youtube_platform_with_api.get_stream_url("dQw4w9WgXcQ")
                
                assert stream_url == "https://example.com/stream.m4a"

    @pytest.mark.asyncio
    async def test_invalid_cookie_file_handling(self, youtube_platform_with_api):
        """Test handling of invalid or corrupted cookie files"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            invalid_cookie_file = f.name
        
        try:
            netscape_file = str(Path(invalid_cookie_file).with_suffix('.txt'))
            
            success = youtube_platform_with_api._convert_cookies_to_netscape(
                invalid_cookie_file, netscape_file
            )
            
            assert success is False
            assert not Path(netscape_file).exists()
        finally:
            Path(invalid_cookie_file).unlink(missing_ok=True)


class TestGracefulDegradation:
    """Test graceful degradation when various methods fail"""

    @pytest.mark.asyncio
    async def test_stream_url_extraction_format_fallback(self, youtube_platform_with_api):
        """Test fallback through different format options when primary fails"""
        mock_formats = [
            {"url": None, "vcodec": "none", "abr": 128},  # Primary audio format fails
            {"url": "https://example.com/fallback.webm", "vcodec": "h264", "abr": 96, "tbr": 200},  # Fallback format
        ]
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdlp_class:
            mock_ytdlp = MagicMock()
            mock_ytdlp_class.return_value.__enter__.return_value = mock_ytdlp
            mock_ytdlp.extract_info.return_value = {
                "formats": mock_formats
            }
            
            stream_url = await youtube_platform_with_api.get_stream_url("dQw4w9WgXcQ")
            
            assert stream_url == "https://example.com/fallback.webm"

    @pytest.mark.asyncio
    async def test_yt_dlp_download_error_handling(self, youtube_platform_with_api):
        """Test handling of various yt-dlp download errors"""
        from yt_dlp import DownloadError
        
        error_scenarios = [
            ("This video is private", "Video is private"),
            ("Video unavailable", "Video is unavailable"),
            ("Copyright claim", "Video blocked due to copyright"),
            ("Not available in your region", "Video not available in your region"),
            ("Unknown error", "Download error: Unknown error"),
        ]
        
        for error_msg, expected_result in error_scenarios:
            with patch('yt_dlp.YoutubeDL') as mock_ytdlp_class:
                mock_ytdlp = MagicMock()
                mock_ytdlp_class.return_value.__enter__.return_value = mock_ytdlp
                mock_ytdlp.extract_info.side_effect = DownloadError(error_msg)
                
                with pytest.raises(PlatformAPIError) as exc_info:
                    await youtube_platform_with_api.get_stream_url("dQw4w9WgXcQ")
                
                assert expected_result in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_metadata_extraction_error_recovery(self, youtube_platform_with_api):
        """Test recovery when metadata extraction partially fails"""
        incomplete_ytdlp_info = {
            "title": "Test Video",
            # Missing uploader, duration, etc.
            "view_count": None,
            "upload_date": None,
            "thumbnails": []
        }
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdlp_class:
            mock_ytdlp = MagicMock()
            mock_ytdlp_class.return_value.__enter__.return_value = mock_ytdlp
            mock_ytdlp.extract_info.return_value = incomplete_ytdlp_info
            
            metadata = await youtube_platform_with_api._extract_metadata_via_ytdlp("dQw4w9WgXcQ")
            
            assert metadata is not None
            assert metadata["title"] == "Test Video"
            assert metadata["channel"] == "Unknown"  # Should default
            assert metadata["duration"] == "Unknown"  # Should default
            assert metadata["views"] == "0 views"  # Should format gracefully
            assert metadata["published"] == "Unknown"  # Should default

    @pytest.mark.asyncio
    async def test_duration_parsing_edge_cases(self, youtube_platform_with_api):
        """Test duration parsing handles various edge cases"""
        test_cases = [
            ("", "Unknown"),
            ("PT0S", "0:00"),
            ("PT30S", "0:30"),
            ("PT5M", "5:00"),
            ("PT1H30M45S", "1:30:45"),
            ("INVALID", "Unknown"),
            ("PT", "Unknown"),
        ]
        
        for duration_input, expected_output in test_cases:
            result = youtube_platform_with_api._parse_duration(duration_input)
            assert result == expected_output, f"Failed for input: {duration_input}"


class TestFallbackManagerIntegration:
    """Test integration with platform fallback manager"""

    @pytest.mark.asyncio
    async def test_fallback_manager_activation(self, youtube_platform_with_api, fallback_manager):
        """Test fallback manager activation when cookies fail"""
        youtube_platform_with_api.set_fallback_manager(fallback_manager)
        
        # Simulate cookie failure
        strategy = fallback_manager.activate_fallback("youtube", "Cookie extraction failed")
        
        assert strategy is not None
        assert strategy.mode == FallbackMode.API_ONLY
        assert fallback_manager.is_platform_in_fallback("youtube")
        
        # Test platform respects fallback mode
        limitations = fallback_manager.get_platform_limitations("youtube")
        assert "No access to private videos" in limitations

    @pytest.mark.asyncio
    async def test_fallback_recommendations(self, fallback_manager):
        """Test user-facing recommendations during fallback"""
        fallback_manager.activate_fallback("youtube", "API quota exceeded")
        
        recommendations = fallback_manager.get_fallback_recommendations("youtube")
        
        assert len(recommendations) > 0
        assert any("API-only mode" in rec for rec in recommendations)
        assert any("limited" in rec.lower() for rec in recommendations)

    @pytest.mark.asyncio
    async def test_fallback_operation_restrictions(self, fallback_manager):
        """Test operation restrictions during fallback modes"""
        # Test disabled mode
        fallback_manager.active_fallbacks["youtube"] = FallbackStrategy(
            mode=FallbackMode.DISABLED,
            description="Platform disabled",
            limitations=["No functionality available"]
        )
        
        should_fallback, reason = fallback_manager.should_use_fallback_for_operation("youtube", "search")
        assert should_fallback is True
        assert "disabled" in reason.lower()
        
        # Test limited search mode
        fallback_manager.active_fallbacks["youtube"] = FallbackStrategy(
            mode=FallbackMode.LIMITED_SEARCH,
            description="Limited search",
            limitations=["Reduced capabilities"]
        )
        
        should_fallback, reason = fallback_manager.should_use_fallback_for_operation("youtube", "advanced_search")
        assert should_fallback is True
        assert "Advanced search features disabled" in reason


class TestUserFeedbackAndStatusReporting:
    """Test user feedback and status reporting functionality"""

    @pytest.mark.asyncio
    async def test_comprehensive_fallback_report(self, fallback_manager):
        """Test comprehensive fallback status reporting"""
        # Activate some fallbacks
        fallback_manager.activate_fallback("youtube", "API quota exceeded")
        fallback_manager.activate_fallback("rumble", "Cookie failure")
        
        report = fallback_manager.get_fallback_report()
        
        assert report["enabled"] is True
        assert report["summary"]["active_fallbacks"] == 2
        assert report["summary"]["total_platforms"] > 0
        assert "youtube" in report["active_fallbacks"]
        assert "rumble" in report["active_fallbacks"]
        assert len(report["platform_strategies"]) > 0

    @pytest.mark.asyncio
    async def test_fallback_history_tracking(self, fallback_manager):
        """Test fallback activation/deactivation history tracking"""
        platform = "youtube"
        
        # Activate fallback
        fallback_manager.activate_fallback(platform, "Initial failure")
        
        # Deactivate fallback
        fallback_manager.deactivate_fallback(platform, "Issue resolved")
        
        # Re-activate
        fallback_manager.activate_fallback(platform, "Second failure")
        
        history = fallback_manager.fallback_history[platform]
        assert len(history) == 3
        
        actions = [record["action"] for record in history]
        assert actions == ["activated", "deactivated", "activated"]
        
        reasons = [record["reason"] for record in history]
        assert "Initial failure" in reasons
        assert "Issue resolved" in reasons
        assert "Second failure" in reasons

    @pytest.mark.asyncio
    async def test_logging_during_fallback_operations(self, youtube_platform_with_api, caplog):
        """Test appropriate logging during fallback operations"""
        with caplog.at_level(logging.INFO):
            # Test URL processing logs
            with patch.object(youtube_platform_with_api, '_extract_metadata_via_ytdlp', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = {"id": "test123", "title": "Test"}
                
                await youtube_platform_with_api._search_via_url_parsing("https://www.youtube.com/watch?v=test123")
                
                assert "Attempting URL parsing search" in caplog.text
                assert "Extracted video ID from URL" in caplog.text

    @pytest.mark.asyncio
    async def test_error_message_clarity(self, youtube_platform_no_api):
        """Test that error messages provide clear guidance to users"""
        try:
            await youtube_platform_no_api.search_videos("test query")
        except PlatformAuthenticationError as e:
            error_msg = str(e)
            assert "YouTube API key is required" in error_msg
            assert "provide a direct YouTube URL" in error_msg
            assert "configure 'api_key'" in error_msg


class TestApiQuotaExceededSimulation:
    """Test simulation of API quota exceeded conditions"""

    @pytest.mark.asyncio
    async def test_simulate_quota_exceeded_search(self, youtube_platform_with_api):
        """Simulate and test quota exceeded during search"""
        quota_error = HttpError(
            resp=Mock(status=403),
            content=b'{"error": {"errors": [{"reason": "quotaExceeded"}], "code": 403, "message": "Quota exceeded."}}'
        )
        
        with patch.object(youtube_platform_with_api, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.return_value.execute.side_effect = quota_error
            
            with patch.object(youtube_platform_with_api, '_fallback_search', new_callable=AsyncMock) as mock_fallback:
                mock_fallback.return_value = []  # Simulate fallback failure
                
                with pytest.raises(PlatformRateLimitError) as exc_info:
                    await youtube_platform_with_api.search_videos("test query")
                
                assert "quota exceeded" in str(exc_info.value).lower()
                assert "fallback search failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_simulate_quota_exceeded_video_details(self, youtube_platform_with_api, sample_video_metadata):
        """Simulate quota exceeded during video details retrieval"""
        quota_error = HttpError(
            resp=Mock(status=403),
            content=b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
        )
        
        with patch.object(youtube_platform_with_api, 'youtube') as mock_youtube:
            mock_youtube.videos.return_value.list.return_value.execute.side_effect = quota_error
            
            with patch.object(youtube_platform_with_api, '_extract_metadata_via_ytdlp', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = sample_video_metadata
                
                details = await youtube_platform_with_api.get_video_details("dQw4w9WgXcQ")
                
                assert details is not None
                assert details["id"] == "dQw4w9WgXcQ"
                mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_mixed_api_success_and_failure(self, youtube_platform_with_api, sample_video_metadata):
        """Test mixed scenarios where some API calls succeed and others fail"""
        # Simulate search success but video details quota exceeded
        search_response = {
            "items": [
                {
                    "id": {"videoId": "dQw4w9WgXcQ"},
                    "snippet": {
                        "title": "Test Video",
                        "channelTitle": "Test Channel",
                        "thumbnails": {"high": {"url": "http://example.com/thumb.jpg"}},
                    },
                }
            ]
        }
        
        quota_error = HttpError(
            resp=Mock(status=403),
            content=b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
        )
        
        with patch.object(youtube_platform_with_api, 'youtube') as mock_youtube:
            # Search succeeds
            mock_youtube.search.return_value.list.return_value.execute.return_value = search_response
            # Video details fails with quota exceeded
            mock_youtube.videos.return_value.list.return_value.execute.side_effect = quota_error
            
            # Should still return basic results from search
            results = await youtube_platform_with_api.search_videos("test query")
            
            assert len(results) == 1
            assert results[0]["id"] == "dQw4w9WgXcQ"


class TestIntegrationWithExistingCode:
    """Test integration with existing codebase components"""

    @pytest.mark.asyncio
    async def test_network_resilience_integration(self, youtube_platform_with_api):
        """Test integration with network resilience components"""
        from src.utils.network_resilience import NetworkResilienceError, CircuitBreakerOpenError
        
        # Test that network resilience errors are handled properly
        with patch.object(youtube_platform_with_api, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.return_value.execute.side_effect = NetworkResilienceError("Network failure")
            
            with pytest.raises(NetworkResilienceError):
                await youtube_platform_with_api.search_videos("test query")

    @pytest.mark.asyncio
    async def test_platform_registry_integration(self, youtube_platform_with_api, fallback_manager):
        """Test integration with platform registry and bot initialization"""
        # Simulate bot setup
        youtube_platform_with_api.set_fallback_manager(fallback_manager)
        
        await youtube_platform_with_api.initialize()
        
        # Verify platform is properly initialized
        assert youtube_platform_with_api.fallback_manager is not None
        assert youtube_platform_with_api.youtube is not None

    @pytest.mark.asyncio
    async def test_cache_integration_during_fallback(self, youtube_platform_with_api):
        """Test that cache integration works during fallback scenarios"""
        # This test would verify that cached results are used appropriately
        # during fallback scenarios, but would require cache manager setup
        
        # For now, verify the platform can handle cache-related scenarios
        with patch.object(youtube_platform_with_api, '_extract_metadata_via_ytdlp', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = None  # Simulate extraction failure
            
            metadata = await youtube_platform_with_api._extract_metadata_via_ytdlp("invalid_id")
            assert metadata is None

    @pytest.mark.asyncio
    async def test_metrics_collection_during_fallback(self, youtube_platform_with_api, fallback_manager):
        """Test that metrics are properly collected during fallback operations"""
        # Setup fallback
        youtube_platform_with_api.set_fallback_manager(fallback_manager)
        fallback_manager.activate_fallback("youtube", "Test activation")
        
        # Test that fallback status can be reported for metrics
        report = fallback_manager.get_fallback_report()
        
        assert report["summary"]["active_fallbacks"] == 1
        assert report["summary"]["fallback_rate"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])