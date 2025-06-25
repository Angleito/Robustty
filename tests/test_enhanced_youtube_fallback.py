"""
Tests for the enhanced YouTube fallback system.

Tests the complete fallback chain, quota monitoring, progressive degradation,
cache behavior, and configuration handling.
"""

import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, List, Optional, Any

import pytest
import aiohttp
from freezegun import freeze_time

from src.platforms.youtube import YouTubePlatform
from src.services.cache_manager import CacheManager
from src.core.config import Config


# Test fixtures
@pytest.fixture
def mock_config():
    """Create a mock configuration with fallback settings."""
    config = MagicMock(spec=Config)
    config.get.side_effect = lambda key, default=None: {
        'platforms.youtube.api_key': 'test_api_key',
        'platforms.youtube.fallback.enabled': True,
        'platforms.youtube.fallback.methods': ['api', 'yt-dlp-auth', 'yt-dlp-public', 'cache', 'cross-platform'],
        'platforms.youtube.fallback.cache_first_on_degraded': True,
        'platforms.youtube.fallback.extended_cache_ttl': 86400,
        'platforms.youtube.fallback.stale_cache_max_age': 604800,
        'platforms.youtube.quota.daily_limit': 10000,
        'platforms.youtube.quota.conservation_threshold': 0.2,
        'platforms.youtube.quota.monitoring_interval': 300,
        'platforms.youtube.quota.prediction_window': 3600,
        'cache.redis_url': 'redis://localhost:6379',
        'cache.default_ttl': 3600,
    }.get(key, default)
    return config


@pytest.fixture
def mock_cache_manager():
    """Create a mock cache manager."""
    cache = AsyncMock(spec=CacheManager)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.get_with_metadata = AsyncMock(return_value=(None, None))
    return cache


@pytest.fixture
def mock_youtube_api():
    """Create a mock YouTube API client."""
    api = MagicMock()
    api.search = MagicMock()
    api.videos = MagicMock()
    return api


@pytest.fixture
async def youtube_platform(mock_config, mock_cache_manager):
    """Create a YouTube platform instance with mocked dependencies."""
    with patch('src.platforms.youtube.CacheManager', return_value=mock_cache_manager):
        platform = YouTubePlatform(mock_config)
        platform.cache_manager = mock_cache_manager
        platform._quota_tracker = MagicMock()
        platform._quota_tracker.can_make_request = MagicMock(return_value=True)
        platform._quota_tracker.record_usage = MagicMock()
        platform._quota_tracker.get_remaining_quota = MagicMock(return_value=5000)
        platform._quota_tracker.is_exhausted = MagicMock(return_value=False)
        yield platform


@pytest.fixture
def sample_search_results():
    """Sample search results for testing."""
    return [
        {
            'id': 'video1',
            'title': 'Test Video 1',
            'channel': 'Test Channel 1',
            'duration': 180,
            'url': 'https://youtube.com/watch?v=video1'
        },
        {
            'id': 'video2',
            'title': 'Test Video 2',
            'channel': 'Test Channel 2',
            'duration': 240,
            'url': 'https://youtube.com/watch?v=video2'
        }
    ]


@pytest.fixture
def sample_cache_results():
    """Sample cached search results."""
    return {
        'results': [
            {
                'id': 'cached1',
                'title': 'Cached Video 1',
                'channel': 'Cached Channel',
                'duration': 300,
                'url': 'https://youtube.com/watch?v=cached1'
            }
        ],
        'timestamp': datetime.datetime.utcnow().isoformat()
    }


class TestFallbackChain:
    """Test the complete fallback chain functionality."""
    
    @pytest.mark.asyncio
    async def test_fallback_chain_order(self, youtube_platform, sample_search_results):
        """Test that fallback methods are tried in the correct order."""
        # Mock all fallback methods
        youtube_platform._search_with_api = AsyncMock(side_effect=Exception("API failed"))
        youtube_platform._search_with_ytdlp_auth = AsyncMock(side_effect=Exception("Auth failed"))
        youtube_platform._search_with_ytdlp_public = AsyncMock(side_effect=Exception("Public failed"))
        youtube_platform._search_from_cache = AsyncMock(side_effect=Exception("Cache failed"))
        youtube_platform._search_cross_platform = AsyncMock(return_value=sample_search_results)
        
        # Execute search
        results = await youtube_platform.search_videos("test query")
        
        # Verify all methods were called in order
        youtube_platform._search_with_api.assert_called_once_with("test query", 10)
        youtube_platform._search_with_ytdlp_auth.assert_called_once_with("test query", 10)
        youtube_platform._search_with_ytdlp_public.assert_called_once_with("test query", 10)
        youtube_platform._search_from_cache.assert_called_once_with("test query", 10)
        youtube_platform._search_cross_platform.assert_called_once_with("test query", 10)
        
        assert results == sample_search_results
    
    @pytest.mark.asyncio
    async def test_fallback_stops_on_success(self, youtube_platform, sample_search_results):
        """Test that fallback chain stops when a method succeeds."""
        # API fails, yt-dlp auth succeeds
        youtube_platform._search_with_api = AsyncMock(side_effect=Exception("API failed"))
        youtube_platform._search_with_ytdlp_auth = AsyncMock(return_value=sample_search_results)
        youtube_platform._search_with_ytdlp_public = AsyncMock()
        youtube_platform._search_from_cache = AsyncMock()
        youtube_platform._search_cross_platform = AsyncMock()
        
        results = await youtube_platform.search_videos("test query")
        
        # Verify only first two methods were called
        youtube_platform._search_with_api.assert_called_once()
        youtube_platform._search_with_ytdlp_auth.assert_called_once()
        youtube_platform._search_with_ytdlp_public.assert_not_called()
        youtube_platform._search_from_cache.assert_not_called()
        youtube_platform._search_cross_platform.assert_not_called()
        
        assert results == sample_search_results
    
    @pytest.mark.asyncio
    async def test_api_recovery_after_fallback(self, youtube_platform, sample_search_results):
        """Test that system recovers back to API when conditions improve."""
        # First search: API fails, use fallback
        youtube_platform._search_with_api = AsyncMock(side_effect=Exception("API failed"))
        youtube_platform._search_with_ytdlp_auth = AsyncMock(return_value=sample_search_results)
        
        results1 = await youtube_platform.search_videos("test query 1")
        assert results1 == sample_search_results
        
        # Reset mocks and simulate API recovery
        youtube_platform._search_with_api = AsyncMock(return_value=sample_search_results)
        youtube_platform._search_with_ytdlp_auth = AsyncMock()
        youtube_platform._quota_tracker.is_exhausted = MagicMock(return_value=False)
        
        # Second search: API should work now
        results2 = await youtube_platform.search_videos("test query 2")
        
        youtube_platform._search_with_api.assert_called_once_with("test query 2", 10)
        youtube_platform._search_with_ytdlp_auth.assert_not_called()
        assert results2 == sample_search_results
    
    @pytest.mark.asyncio
    async def test_cache_first_when_degraded(self, youtube_platform, mock_cache_manager, sample_cache_results):
        """Test cache-first behavior when system is degraded."""
        # Set system as degraded
        youtube_platform._is_degraded = True
        youtube_platform._config.get.side_effect = lambda key, default=None: {
            'platforms.youtube.fallback.cache_first_on_degraded': True,
        }.get(key, default)
        
        # Setup cache to return results
        mock_cache_manager.get.return_value = sample_cache_results
        
        # Mock other methods
        youtube_platform._search_with_api = AsyncMock()
        youtube_platform._format_cache_results = MagicMock(return_value=sample_cache_results['results'])
        
        results = await youtube_platform.search_videos("test query")
        
        # Verify cache was checked first
        mock_cache_manager.get.assert_called_once()
        youtube_platform._search_with_api.assert_not_called()
        assert results == sample_cache_results['results']


class TestQuotaMonitoring:
    """Test quota monitoring and conservation features."""
    
    @pytest.mark.asyncio
    async def test_quota_tracking_accuracy(self, youtube_platform):
        """Test that quota usage is accurately tracked."""
        youtube_platform._quota_tracker = MagicMock()
        youtube_platform._quota_tracker.record_usage = MagicMock()
        youtube_platform._search_with_api = AsyncMock(return_value=[])
        
        # Make several API calls
        for i in range(5):
            await youtube_platform.search_videos(f"query {i}")
        
        # Verify quota was recorded for each call
        assert youtube_platform._quota_tracker.record_usage.call_count == 5
        
        # Check that correct cost was recorded (100 units per search)
        for call in youtube_platform._quota_tracker.record_usage.call_args_list:
            assert call[0][0] == 100  # Search costs 100 units
    
    @pytest.mark.asyncio
    async def test_conservation_mode_activation(self, youtube_platform):
        """Test that conservation mode activates at threshold."""
        # Set quota near threshold (20% remaining = 2000 units)
        youtube_platform._quota_tracker.get_remaining_quota = MagicMock(return_value=1900)
        youtube_platform._quota_tracker.get_usage_percentage = MagicMock(return_value=0.81)
        
        # Check conservation mode
        assert youtube_platform._is_conservation_mode() is True
        
        # Verify reduced functionality in conservation mode
        youtube_platform._search_with_api = AsyncMock(return_value=[])
        youtube_platform._should_use_api = MagicMock(return_value=False)
        
        await youtube_platform.search_videos("test query")
        
        # API should not be called in conservation mode
        youtube_platform._search_with_api.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_quota_exhaustion_prediction(self, youtube_platform):
        """Test quota exhaustion prediction accuracy."""
        with freeze_time("2024-01-25 12:00:00") as frozen_time:
            # Simulate usage pattern
            usage_history = [
                (datetime.datetime(2024, 1, 25, 10, 0), 1000),
                (datetime.datetime(2024, 1, 25, 11, 0), 2000),
                (datetime.datetime(2024, 1, 25, 12, 0), 3000),
            ]
            
            youtube_platform._quota_tracker.get_usage_history = MagicMock(return_value=usage_history)
            youtube_platform._quota_tracker.predict_exhaustion_time = MagicMock(
                return_value=datetime.datetime(2024, 1, 25, 15, 0)
            )
            
            # Check prediction
            exhaustion_time = youtube_platform._predict_quota_exhaustion()
            assert exhaustion_time == datetime.datetime(2024, 1, 25, 15, 0)
            
            # Verify conservation mode activates based on prediction
            youtube_platform._quota_tracker.get_remaining_quota = MagicMock(return_value=4000)
            
            # Should enter conservation if exhaustion predicted within 3 hours
            frozen_time.move_to("2024-01-25 13:00:00")
            assert youtube_platform._should_conserve_quota() is True


class TestProgressiveDegradation:
    """Test progressive degradation functionality."""
    
    @pytest.mark.asyncio
    async def test_graceful_functionality_reduction(self, youtube_platform):
        """Test that functionality reduces gracefully under stress."""
        # Start with full functionality
        youtube_platform._degradation_level = 0
        features = youtube_platform._get_available_features()
        assert 'search' in features
        assert 'detailed_metadata' in features
        assert 'thumbnails' in features
        
        # Increase degradation
        youtube_platform._degradation_level = 1
        features = youtube_platform._get_available_features()
        assert 'search' in features
        assert 'detailed_metadata' not in features
        assert 'thumbnails' in features
        
        # Maximum degradation
        youtube_platform._degradation_level = 3
        features = youtube_platform._get_available_features()
        assert 'search' in features  # Basic search always available
        assert 'detailed_metadata' not in features
        assert 'thumbnails' not in features
    
    @pytest.mark.asyncio
    async def test_user_messaging_during_degradation(self, youtube_platform):
        """Test appropriate user messaging during degraded conditions."""
        youtube_platform._degradation_level = 2
        youtube_platform._get_degradation_message = MagicMock(
            return_value="Service is running with reduced functionality due to high load."
        )
        
        message = youtube_platform._get_user_message()
        assert "reduced functionality" in message
        assert "high load" in message
    
    @pytest.mark.asyncio
    async def test_performance_under_degradation(self, youtube_platform, sample_search_results):
        """Test that performance is maintained under degraded conditions."""
        youtube_platform._degradation_level = 2
        youtube_platform._search_with_ytdlp_public = AsyncMock(return_value=sample_search_results)
        
        # Measure response time
        import time
        start = time.time()
        results = await youtube_platform.search_videos("test query")
        duration = time.time() - start
        
        # Should still return results quickly (under 5 seconds)
        assert results == sample_search_results
        assert duration < 5.0


class TestCacheBehavior:
    """Test cache behavior during fallback scenarios."""
    
    @pytest.mark.asyncio
    async def test_cache_first_search(self, youtube_platform, mock_cache_manager, sample_cache_results):
        """Test cache-first search behavior."""
        youtube_platform._is_degraded = True
        mock_cache_manager.get.return_value = sample_cache_results
        youtube_platform._format_cache_results = MagicMock(return_value=sample_cache_results['results'])
        
        results = await youtube_platform.search_videos("cached query")
        
        # Cache should be checked first
        mock_cache_manager.get.assert_called_once_with("youtube:search:cached query:10")
        assert results == sample_cache_results['results']
    
    @pytest.mark.asyncio
    async def test_stale_cache_serving(self, youtube_platform, mock_cache_manager, sample_cache_results):
        """Test serving stale cache during outages."""
        # Simulate all methods failing except stale cache
        youtube_platform._search_with_api = AsyncMock(side_effect=Exception("API down"))
        youtube_platform._search_with_ytdlp_auth = AsyncMock(side_effect=Exception("Auth failed"))
        youtube_platform._search_with_ytdlp_public = AsyncMock(side_effect=Exception("Public failed"))
        
        # Setup stale cache (7 days old)
        stale_timestamp = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat()
        stale_results = {**sample_cache_results, 'timestamp': stale_timestamp}
        
        mock_cache_manager.get.return_value = None  # No fresh cache
        mock_cache_manager.get_with_metadata.return_value = (stale_results, {'ttl': -1})
        youtube_platform._format_cache_results = MagicMock(return_value=stale_results['results'])
        
        results = await youtube_platform.search_videos("test query")
        
        # Should serve stale cache
        assert results == stale_results['results']
    
    @pytest.mark.asyncio
    async def test_extended_cache_ttl(self, youtube_platform, mock_cache_manager, sample_search_results):
        """Test extended cache TTL during outages."""
        youtube_platform._is_degraded = True
        youtube_platform._search_with_api = AsyncMock(return_value=sample_search_results)
        
        await youtube_platform.search_videos("test query")
        
        # Verify cache was set with extended TTL (24 hours)
        mock_cache_manager.set.assert_called_once()
        call_args = mock_cache_manager.set.call_args
        assert call_args[1]['ttl'] == 86400  # 24 hours


class TestConfiguration:
    """Test configuration handling and backward compatibility."""
    
    def test_all_config_options_work(self, mock_config):
        """Test that all new config options are properly handled."""
        platform = YouTubePlatform(mock_config)
        
        # Verify all config options are accessible
        assert platform._config.get('platforms.youtube.fallback.enabled') is True
        assert platform._config.get('platforms.youtube.fallback.methods') == [
            'api', 'yt-dlp-auth', 'yt-dlp-public', 'cache', 'cross-platform'
        ]
        assert platform._config.get('platforms.youtube.quota.daily_limit') == 10000
        assert platform._config.get('platforms.youtube.quota.conservation_threshold') == 0.2
    
    def test_backward_compatibility(self):
        """Test backward compatibility with old configs."""
        # Old config without fallback settings
        old_config = MagicMock()
        old_config.get.side_effect = lambda key, default=None: {
            'platforms.youtube.api_key': 'test_key',
        }.get(key, default)
        
        platform = YouTubePlatform(old_config)
        
        # Should use defaults for missing options
        assert platform._fallback_enabled is True  # Default
        assert platform._fallback_methods == ['api', 'yt-dlp-auth', 'yt-dlp-public', 'cache', 'cross-platform']
    
    def test_environment_variable_overrides(self, mock_config):
        """Test that environment variables override config values."""
        with patch.dict('os.environ', {
            'YOUTUBE_FALLBACK_ENABLED': 'false',
            'YOUTUBE_QUOTA_LIMIT': '5000',
            'YOUTUBE_CONSERVATION_THRESHOLD': '0.3'
        }):
            platform = YouTubePlatform(mock_config)
            
            # Environment variables should override config
            assert platform._fallback_enabled is False
            assert platform._quota_limit == 5000
            assert platform._conservation_threshold == 0.3


class TestIntegrationScenarios:
    """Integration tests simulating real-world scenarios."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_api_outage(self, youtube_platform, sample_search_results):
        """Simulate complete API outage scenario."""
        # API completely down
        youtube_platform._search_with_api = AsyncMock(
            side_effect=aiohttp.ClientError("API unreachable")
        )
        
        # yt-dlp auth works as backup
        youtube_platform._search_with_ytdlp_auth = AsyncMock(return_value=sample_search_results)
        
        # Multiple searches should work via fallback
        for i in range(10):
            results = await youtube_platform.search_videos(f"query {i}")
            assert results == sample_search_results
        
        # Verify API was attempted but fallback was used
        assert youtube_platform._search_with_api.call_count == 10
        assert youtube_platform._search_with_ytdlp_auth.call_count == 10
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_quota_exhaustion_mid_session(self, youtube_platform, sample_search_results):
        """Simulate quota exhaustion during active session."""
        call_count = 0
        
        def api_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 5:
                return sample_search_results
            else:
                raise Exception("Quota exceeded")
        
        youtube_platform._search_with_api = AsyncMock(side_effect=api_side_effect)
        youtube_platform._search_with_ytdlp_auth = AsyncMock(return_value=sample_search_results)
        
        # First 5 searches use API
        for i in range(5):
            results = await youtube_platform.search_videos(f"query {i}")
            assert results == sample_search_results
        
        # Next searches should fall back
        for i in range(5, 10):
            results = await youtube_platform.search_videos(f"query {i}")
            assert results == sample_search_results
        
        # Verify transition from API to fallback
        assert youtube_platform._search_with_api.call_count == 10
        assert youtube_platform._search_with_ytdlp_auth.call_count == 5
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cookie_expiration_handling(self, youtube_platform, sample_search_results):
        """Simulate cookie expiration scenario."""
        # yt-dlp auth fails due to expired cookies
        youtube_platform._search_with_ytdlp_auth = AsyncMock(
            side_effect=Exception("HTTP Error 403: Forbidden")
        )
        
        # Public yt-dlp works as fallback
        youtube_platform._search_with_ytdlp_public = AsyncMock(return_value=sample_search_results)
        
        # Should detect cookie issue and use public method
        results = await youtube_platform.search_videos("test query")
        assert results == sample_search_results
        
        # Verify cookie refresh was triggered
        youtube_platform._trigger_cookie_refresh = AsyncMock()
        await youtube_platform._handle_cookie_error()
        youtube_platform._trigger_cookie_refresh.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_network_issues_recovery(self, youtube_platform, sample_search_results, sample_cache_results):
        """Simulate network issues and recovery."""
        # Network issues affect all external methods
        network_error = aiohttp.ClientError("Network unreachable")
        youtube_platform._search_with_api = AsyncMock(side_effect=network_error)
        youtube_platform._search_with_ytdlp_auth = AsyncMock(side_effect=network_error)
        youtube_platform._search_with_ytdlp_public = AsyncMock(side_effect=network_error)
        
        # Only cache works
        youtube_platform.cache_manager.get.return_value = sample_cache_results
        youtube_platform._format_cache_results = MagicMock(return_value=sample_cache_results['results'])
        
        # Should use cache during network issues
        results = await youtube_platform.search_videos("cached query")
        assert results == sample_cache_results['results']
        
        # Simulate network recovery
        youtube_platform._search_with_api = AsyncMock(return_value=sample_search_results)
        
        # Should resume using API
        results = await youtube_platform.search_videos("new query")
        assert results == sample_search_results


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_all_methods_fail(self, youtube_platform):
        """Test behavior when all fallback methods fail."""
        # All methods fail
        youtube_platform._search_with_api = AsyncMock(side_effect=Exception("API failed"))
        youtube_platform._search_with_ytdlp_auth = AsyncMock(side_effect=Exception("Auth failed"))
        youtube_platform._search_with_ytdlp_public = AsyncMock(side_effect=Exception("Public failed"))
        youtube_platform._search_from_cache = AsyncMock(side_effect=Exception("Cache failed"))
        youtube_platform._search_cross_platform = AsyncMock(side_effect=Exception("Cross-platform failed"))
        
        # Should return empty results with error flag
        results = await youtube_platform.search_videos("test query")
        assert results == []
        assert youtube_platform._last_error is not None
    
    @pytest.mark.asyncio
    async def test_partial_results_handling(self, youtube_platform):
        """Test handling of partial results from degraded sources."""
        partial_results = [{'id': 'video1', 'title': 'Partial Result', 'channel': 'Unknown'}]
        
        youtube_platform._search_with_api = AsyncMock(side_effect=Exception("API failed"))
        youtube_platform._search_with_ytdlp_public = AsyncMock(return_value=partial_results)
        
        results = await youtube_platform.search_videos("test query")
        
        # Should return partial results
        assert len(results) == 1
        assert results[0]['title'] == 'Partial Result'
        
        # Should mark results as partial
        assert youtube_platform._last_result_quality == 'partial'
    
    @pytest.mark.asyncio
    async def test_concurrent_fallback_requests(self, youtube_platform, sample_search_results):
        """Test handling of concurrent requests during fallback."""
        youtube_platform._search_with_api = AsyncMock(side_effect=Exception("API failed"))
        youtube_platform._search_with_ytdlp_auth = AsyncMock(return_value=sample_search_results)
        
        # Make multiple concurrent requests
        tasks = [
            youtube_platform.search_videos(f"query {i}")
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed via fallback
        assert all(r == sample_search_results for r in results)
        assert youtube_platform._search_with_ytdlp_auth.call_count == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])