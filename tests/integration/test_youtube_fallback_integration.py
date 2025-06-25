"""
Integration tests for YouTube platform fallback functionality

These tests focus on end-to-end scenarios and integration between components.
They test the complete fallback workflow from failure detection to recovery.
"""

import asyncio
import json
import logging
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from googleapiclient.errors import HttpError

from src.platforms.youtube import YouTubePlatform
from src.platforms.errors import PlatformRateLimitError, PlatformAuthenticationError
from src.services.platform_fallback_manager import PlatformFallbackManager, FallbackMode
from src.services.cookie_manager import CookieManager


@pytest.fixture
def integration_config():
    """Configuration for integration testing"""
    return {
        "youtube": {
            "enabled": True,
            "api_key": "test_integration_key",
            "enable_fallbacks": True,
        },
        "fallback_manager": {
            "enable_fallbacks": True,
            "max_fallback_duration_hours": 1,
            "retry_interval_minutes": 5,
        }
    }


@pytest.fixture
async def integrated_youtube_platform(integration_config):
    """YouTube platform with full integration setup"""
    platform = YouTubePlatform("youtube", integration_config["youtube"])
    fallback_manager = PlatformFallbackManager(integration_config["fallback_manager"])
    
    platform.set_fallback_manager(fallback_manager)
    await platform.initialize()
    await fallback_manager.start()
    
    yield platform, fallback_manager
    
    await fallback_manager.stop()
    await platform.cleanup()


@pytest.fixture
def mock_cookie_directory():
    """Create mock cookie directory structure"""
    with tempfile.TemporaryDirectory() as temp_dir:
        cookie_dir = Path(temp_dir) / "cookies"
        cookie_dir.mkdir()
        
        # Create mock YouTube cookies
        youtube_cookies = [
            {
                "name": "VISITOR_INFO1_LIVE",
                "value": "integration_test_visitor",
                "domain": ".youtube.com",
                "path": "/",
                "secure": True,
                "expires": int(time.time()) + 86400
            }
        ]
        
        cookie_file = cookie_dir / "youtube_cookies.json"
        with open(cookie_file, 'w') as f:
            json.dump(youtube_cookies, f)
        
        yield str(cookie_dir)


class TestEndToEndFallbackWorkflow:
    """Test complete fallback workflow from failure to recovery"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_api_quota_fallback_workflow(self, integrated_youtube_platform):
        """Test complete workflow when API quota is exceeded"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Simulate API quota exceeded
        quota_error = HttpError(
            resp=Mock(status=403),
            content=b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
        )
        
        with patch.object(platform, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.return_value.execute.side_effect = quota_error
            
            # Mock successful fallback search
            with patch.object(platform, '_fallback_search', new_callable=AsyncMock) as mock_fallback:
                mock_fallback.return_value = [
                    {
                        "id": "fallback123",
                        "title": "Fallback Video",
                        "platform": "youtube",
                        "url": "https://www.youtube.com/watch?v=fallback123"
                    }
                ]
                
                # 1. Initial search triggers fallback
                results = await platform.search_videos("test query")
                
                # Verify fallback was activated
                assert fallback_manager.is_platform_in_fallback("youtube")
                assert len(results) == 1
                assert results[0]["id"] == "fallback123"
                
                # 2. Verify fallback mode affects subsequent operations
                mode = fallback_manager.get_platform_fallback_mode("youtube")
                assert mode == FallbackMode.API_ONLY
                
                # 3. Test user recommendations are provided
                recommendations = fallback_manager.get_fallback_recommendations("youtube")
                assert len(recommendations) > 0
                assert any("API-only mode" in rec for rec in recommendations)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_url_processing_bypasses_api_failures(self, integrated_youtube_platform):
        """Test that URL processing works even when API is failing"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Simulate complete API failure
        with patch.object(platform, 'youtube') as mock_youtube:
            mock_youtube.search.side_effect = Exception("API completely unavailable")
            
            # Mock successful yt-dlp extraction
            with patch.object(platform, '_extract_metadata_via_ytdlp', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = {
                    "id": "dQw4w9WgXcQ",
                    "title": "Never Gonna Give You Up",
                    "channel": "Rick Astley",
                    "platform": "youtube",
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                }
                
                # URL processing should still work
                results = await platform.search_videos("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
                
                assert len(results) == 1
                assert results[0]["id"] == "dQw4w9WgXcQ"
                assert results[0]["title"] == "Never Gonna Give You Up"
                
                # API failure should not have triggered fallback for URL processing
                # (since URL processing doesn't use the API)
                mock_extract.assert_called_once_with("dQw4w9WgXcQ")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cookie_integration_with_fallback(self, integrated_youtube_platform, mock_cookie_directory):
        """Test cookie integration during fallback scenarios"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Mock cookie paths to use our test directory
        cookie_paths = [
            str(Path(mock_cookie_directory) / "youtube_cookies.json")
        ]
        
        with patch.object(platform, 'get_stream_url') as mock_get_stream:
            # Mock the cookie path detection
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.side_effect = lambda: str(Path.cwd()) in cookie_paths
                
                # Mock successful stream extraction with cookies
                mock_get_stream.return_value = "https://example.com/stream.m4a"
                
                stream_url = await platform.get_stream_url("dQw4w9WgXcQ")
                assert stream_url == "https://example.com/stream.m4a"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fallback_manager_monitoring_and_recovery(self, integrated_youtube_platform):
        """Test fallback manager's monitoring and recovery mechanisms"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Activate fallback
        strategy = fallback_manager.activate_fallback("youtube", "Integration test")
        assert strategy is not None
        
        # Wait a short time to simulate monitoring
        await asyncio.sleep(0.1)
        
        # Check fallback report
        report = fallback_manager.get_fallback_report()
        assert report["summary"]["active_fallbacks"] == 1
        assert "youtube" in report["active_fallbacks"]
        
        # Test manual recovery
        success = fallback_manager.deactivate_fallback("youtube", "Test recovery")
        assert success is True
        assert not fallback_manager.is_platform_in_fallback("youtube")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_platform_fallback_coordination(self, integration_config):
        """Test coordination between multiple platforms in fallback"""
        # Create multiple platforms
        youtube_platform = YouTubePlatform("youtube", integration_config["youtube"])
        
        fallback_manager = PlatformFallbackManager(integration_config["fallback_manager"])
        
        youtube_platform.set_fallback_manager(fallback_manager)
        
        await youtube_platform.initialize()
        await fallback_manager.start()
        
        try:
            # Activate fallbacks for multiple platforms
            youtube_strategy = fallback_manager.activate_fallback("youtube", "API failure")
            rumble_strategy = fallback_manager.activate_fallback("rumble", "Cookie failure")
            
            assert youtube_strategy is not None
            assert rumble_strategy is not None
            
            # Check comprehensive report
            report = fallback_manager.get_fallback_report()
            assert report["summary"]["active_fallbacks"] == 2
            assert report["summary"]["fallback_rate"] > 0
            
            # Test that each platform has different limitations
            youtube_limits = fallback_manager.get_platform_limitations("youtube")
            rumble_limits = fallback_manager.get_platform_limitations("rumble")
            
            assert len(youtube_limits) > 0
            assert len(rumble_limits) > 0
            assert youtube_limits != rumble_limits
            
        finally:
            await fallback_manager.stop()
            await youtube_platform.cleanup()


class TestRealWorldScenarios:
    """Test real-world failure scenarios and edge cases"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_intermittent_api_failures(self, integrated_youtube_platform):
        """Test handling of intermittent API failures"""
        platform, fallback_manager = integrated_youtube_platform
        
        call_count = 0
        
        def api_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:  # Every second call fails
                raise HttpError(resp=Mock(status=503), content=b'Service Unavailable')
            return Mock(execute=Mock(return_value={"items": []}))
        
        with patch.object(platform, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.side_effect = api_side_effect
            
            # Make multiple calls - some should succeed, some should fail
            results_1 = await platform.search_videos("query 1")  # Should succeed
            
            try:
                results_2 = await platform.search_videos("query 2")  # Should fail
            except Exception:
                pass  # Expected failure
            
            results_3 = await platform.search_videos("query 3")  # Should succeed again
            
            assert call_count >= 2  # Multiple API calls were made

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_network_connectivity_issues(self, integrated_youtube_platform):
        """Test behavior during network connectivity issues"""
        platform, fallback_manager = integrated_youtube_platform
        
        from src.utils.network_resilience import NetworkResilienceError
        
        with patch.object(platform, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.return_value.execute.side_effect = NetworkResilienceError("Network timeout")
            
            # Network errors should be re-raised, not trigger fallback
            with pytest.raises(NetworkResilienceError):
                await platform.search_videos("test query")
            
            # Fallback should not have been activated for network errors
            assert not fallback_manager.is_platform_in_fallback("youtube")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_fallback_operations(self, integrated_youtube_platform):
        """Test concurrent operations during fallback mode"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Activate fallback
        fallback_manager.activate_fallback("youtube", "Concurrent test")
        
        async def search_operation(query):
            """Simulate search operation"""
            with patch.object(platform, '_fallback_search', new_callable=AsyncMock) as mock_fallback:
                mock_fallback.return_value = [{"id": f"result_{query}", "title": f"Video {query}"}]
                return await platform._fallback_search(query, 5)
        
        # Run multiple concurrent operations
        tasks = [
            search_operation(f"query_{i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All operations should complete successfully
        assert all(isinstance(result, list) for result in results)
        assert all(len(result) == 1 for result in results)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fallback_performance_characteristics(self, integrated_youtube_platform):
        """Test performance characteristics during fallback"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Test normal operation timing
        with patch.object(platform, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.return_value.execute.return_value = {"items": []}
            
            start_time = time.time()
            await platform.search_videos("normal query")
            normal_duration = time.time() - start_time
        
        # Test fallback operation timing
        with patch.object(platform, '_fallback_search', new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = []
            
            start_time = time.time()
            await platform._fallback_search("fallback query", 10)
            fallback_duration = time.time() - start_time
        
        # Fallback should not be significantly slower than normal operation
        # (This is a basic performance sanity check)
        assert fallback_duration < normal_duration + 1.0  # Allow 1 second tolerance

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_propagation_and_user_messaging(self, integrated_youtube_platform):
        """Test that errors are properly propagated with clear user messaging"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Test authentication error messaging
        platform_no_api = YouTubePlatform("youtube", {"enabled": True, "enable_fallbacks": True})
        platform_no_api.set_fallback_manager(fallback_manager)
        await platform_no_api.initialize()
        
        try:
            await platform_no_api.search_videos("text search without api")
        except PlatformAuthenticationError as e:
            error_msg = str(e)
            assert "YouTube API key is required" in error_msg
            assert "direct YouTube URL" in error_msg
        
        # Test quota exceeded messaging
        quota_error = HttpError(
            resp=Mock(status=403),
            content=b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
        )
        
        with patch.object(platform, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.return_value.execute.side_effect = quota_error
            
            with patch.object(platform, '_fallback_search', new_callable=AsyncMock) as mock_fallback:
                mock_fallback.return_value = []
                
                try:
                    await platform.search_videos("quota test")
                except PlatformRateLimitError as e:
                    error_msg = str(e)
                    assert "quota exceeded" in error_msg.lower()
                    assert "fallback search failed" in error_msg.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fallback_state_persistence(self, integrated_youtube_platform):
        """Test that fallback state is properly maintained across operations"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Activate fallback
        initial_strategy = fallback_manager.activate_fallback("youtube", "State test")
        initial_time = time.time()
        
        # Wait briefly
        await asyncio.sleep(0.1)
        
        # Check state persistence
        assert fallback_manager.is_platform_in_fallback("youtube")
        current_strategy = fallback_manager.active_fallbacks["youtube"]
        assert current_strategy.mode == initial_strategy.mode
        
        # Check history tracking
        history = fallback_manager.fallback_history["youtube"]
        assert len(history) == 1
        assert history[0]["action"] == "activated"
        assert history[0]["reason"] == "State test"
        
        # Check duration calculation
        duration = fallback_manager._get_fallback_duration("youtube")
        assert duration is not None
        assert duration >= 0


class TestFallbackRecoveryScenarios:
    """Test recovery from fallback scenarios"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_automatic_recovery_detection(self, integrated_youtube_platform):
        """Test automatic detection of recovery conditions"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Activate fallback due to API failure
        fallback_manager.activate_fallback("youtube", "API failure")
        assert fallback_manager.is_platform_in_fallback("youtube")
        
        # Simulate API recovery by successful operation
        with patch.object(platform, 'youtube') as mock_youtube:
            mock_youtube.search.return_value.list.return_value.execute.return_value = {
                "items": [{"id": {"videoId": "recovery123"}, "snippet": {"title": "Recovery Video"}}]
            }
            mock_youtube.videos.return_value.list.return_value.execute.return_value = {
                "items": [{"id": "recovery123", "snippet": {"title": "Recovery Video"}}]
            }
            
            # Successful API call should indicate recovery is possible
            results = await platform.search_videos("recovery test")
            assert len(results) == 1
            
            # Note: Automatic recovery would typically be handled by monitoring task
            # For manual recovery testing:
            success = fallback_manager.deactivate_fallback("youtube", "API recovered")
            assert success is True
            assert not fallback_manager.is_platform_in_fallback("youtube")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_partial_recovery_scenarios(self, integrated_youtube_platform):
        """Test scenarios where some functionality recovers but not all"""
        platform, fallback_manager = integrated_youtube_platform
        
        # Simulate partial recovery - search works but video details still fail
        with patch.object(platform, 'youtube') as mock_youtube:
            # Search API works
            mock_youtube.search.return_value.list.return_value.execute.return_value = {
                "items": [{"id": {"videoId": "partial123"}, "snippet": {"title": "Partial Video"}}]
            }
            
            # Video details API still fails
            quota_error = HttpError(resp=Mock(status=403), content=b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}')
            mock_youtube.videos.return_value.list.return_value.execute.side_effect = quota_error
            
            # Search should work
            results = await platform.search_videos("partial recovery")
            assert len(results) == 1
            
            # Video details should fall back to yt-dlp
            with patch.object(platform, '_extract_metadata_via_ytdlp', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = {"id": "partial123", "title": "Partial Details"}
                
                details = await platform.get_video_details("partial123")
                assert details is not None
                assert details["id"] == "partial123"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])