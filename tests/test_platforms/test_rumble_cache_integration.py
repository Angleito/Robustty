"""
Integration tests for Rumble platform with caching.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.platforms.rumble_platform import RumblePlatform
from src.services.cache_manager import CacheManager
from src.utils.config_loader import ConfigLoader


class TestRumbleCacheIntegration:
    """Test integration between Rumble platform and cache manager."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config loader."""
        config = Mock(spec=ConfigLoader)
        config.get.side_effect = lambda key, default=None: {
            'cache.redis.enabled': False,
            'rumble.apify_api_token': 'test_token',
            'rumble.enabled': True
        }.get(key, default)
        return config
    
    @pytest.fixture
    async def cache_manager(self, mock_config):
        """Create a cache manager instance."""
        manager = CacheManager(mock_config)
        await manager.initialize()
        yield manager
        await manager.close()
    
    @pytest.fixture
    async def rumble_platform(self, mock_config, cache_manager):
        """Create Rumble platform with cache support."""
        # Create platform instance
        platform = RumblePlatform()
        
        # Initialize with cache
        await platform.initialize(mock_config, cache_manager)
        
        yield platform
        
        # Clean up
        await platform.close()
    
    @pytest.mark.asyncio
    async def test_search_uses_cache(self, rumble_platform):
        """Test that search results are cached properly."""
        query = "test search"
        
        # First search - should hit API
        with patch.object(rumble_platform._extractor, '_make_actor_call') as mock_api:
            mock_api.return_value = {
                "items": [
                    {
                        "id": "v123",
                        "title": "Test Video",
                        "url": "https://rumble.com/v123-test.html",
                        "creator": "Test Channel",
                        "viewsCount": 1000,
                        "duration": 300
                    }
                ]
            }
            
            results = await rumble_platform.search(query, limit=1)
            
            # API should be called
            mock_api.assert_called_once()
            assert len(results) == 1
            assert results[0].title == "Test Video"
        
        # Second search with same query - should use cache
        with patch.object(rumble_platform._extractor, '_make_actor_call') as mock_api:
            results_cached = await rumble_platform.search(query, limit=1)
            
            # API should NOT be called
            mock_api.assert_not_called()
            
            # Results should be the same
            assert len(results_cached) == 1
            assert results_cached[0].title == "Test Video"
    
    @pytest.mark.asyncio
    async def test_get_stream_caches_urls(self, rumble_platform):
        """Test that stream URLs are cached."""
        video_id = "v123"
        
        # First stream request - should hit API
        with patch.object(rumble_platform._extractor, 'get_video_metadata') as mock_metadata, \
             patch.object(rumble_platform._extractor, 'download_audio') as mock_download:
            
            mock_metadata.return_value = {
                "title": "Test Video",
                "duration": 300
            }
            mock_download.return_value = "https://stream.example.com/video.mp4"
            
            stream_url = await rumble_platform.get_stream(video_id)
            
            # API should be called
            mock_download.assert_called_once()
            assert stream_url == "https://stream.example.com/video.mp4"
        
        # Second request - should use cache
        with patch.object(rumble_platform._extractor, 'download_audio') as mock_download:
            stream_url_cached = await rumble_platform.get_stream(video_id)
            
            # Download should NOT be called (cache hit)
            mock_download.assert_not_called()
            
            # URL should be the same
            assert stream_url_cached == "https://stream.example.com/video.mp4"
    
    @pytest.mark.asyncio
    async def test_cache_metrics_available(self, rumble_platform):
        """Test that cache metrics are accessible through the platform."""
        # Perform some operations
        with patch.object(rumble_platform._extractor, '_make_actor_call') as mock_api:
            mock_api.return_value = {"items": [{"title": "Video"}]}
            
            await rumble_platform.search("test", limit=1)
            await rumble_platform.search("test", limit=1)  # Cache hit
            await rumble_platform.search("other", limit=1)  # Cache miss
        
        # Get cache metrics through extractor
        metrics = await rumble_platform._extractor.get_cache_metrics()
        
        assert metrics['hits'] >= 1
        assert metrics['misses'] >= 1
        assert 'hit_rate' in metrics
        assert 'in_memory_size' in metrics
    
    @pytest.mark.asyncio
    async def test_platform_close_cleans_cache(self, rumble_platform):
        """Test that closing the platform also closes cache resources."""
        # Spy on cache close method
        with patch.object(rumble_platform._cache_manager, 'close') as mock_close:
            await rumble_platform.close()
            
            # Cache should be closed
            mock_close.assert_called_once()