"""
Tests for RumbleExtractor caching functionality.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.extractors.rumble_extractor import RumbleExtractor
from src.services.cache_manager import CacheManager
# ConfigLoader import removed - using dict config instead


class TestRumbleExtractorCache:
    """Test cache integration in RumbleExtractor."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config dictionary."""
        return {
            'cache': {
                'redis': {
                    'enabled': False  # Redis disabled by default
                }
            }
        }
    
    @pytest.fixture
    async def cache_manager(self, mock_config):
        """Create a cache manager instance."""
        manager = CacheManager(mock_config)
        await manager.initialize()
        yield manager
        await manager.close()
    
    @pytest.fixture
    def extractor_with_cache(self, cache_manager):
        """Create RumbleExtractor with cache manager."""
        return RumbleExtractor(
            apify_api_token="test_token",
            cache_manager=cache_manager
        )
    
    @pytest.mark.asyncio
    async def test_metadata_cache_hit(self, extractor_with_cache):
        """Test that cached metadata is returned without API call."""
        video_url = "https://rumble.com/v12345-test-video.html"
        video_id = "v12345"
        
        # Pre-populate cache
        metadata = {
            "title": "Cached Video",
            "duration": 300,
            "uploader": "Test User"
        }
        await extractor_with_cache.cache_manager.set_video_metadata("rumble", video_id, metadata)
        
        # Mock the API call - it should not be called
        with patch.object(extractor_with_cache, '_make_actor_call') as mock_api:
            result = await extractor_with_cache.get_video_metadata(video_url)
            
            # API should not be called
            mock_api.assert_not_called()
            
            # Should return cached data
            assert result == metadata
            
            # Check cache metrics
            metrics = await extractor_with_cache.cache_manager.get_metrics()
            assert metrics['hits'] >= 1
    
    @pytest.mark.asyncio
    async def test_metadata_cache_miss(self, extractor_with_cache):
        """Test that API is called on cache miss and result is cached."""
        video_url = "https://rumble.com/v12345-test-video.html"
        video_id = "v12345"
        
        # Mock API response
        api_response = {
            "items": [{
                "title": "Test Video",
                "description": "Test Description",
                "duration": 600,
                "author": {"name": "Test Channel"},
                "viewCount": 1000,
                "likeCount": 100,
                "uploadDate": "2024-01-01",
                "thumbnail": "https://example.com/thumb.jpg",
                "videoQualities": ["720p", "480p"]
            }]
        }
        
        with patch.object(extractor_with_cache, '_make_actor_call') as mock_api:
            mock_api.return_value = api_response
            
            result = await extractor_with_cache.get_video_metadata(video_url)
            
            # API should be called
            mock_api.assert_called_once()
            
            # Check result
            assert result["title"] == "Test Video"
            assert result["duration"] == 600
            
            # Verify data was cached
            cached = await extractor_with_cache.cache_manager.get_video_metadata("rumble", video_id)
            assert cached == result
    
    @pytest.mark.asyncio
    async def test_stream_url_cache_hit(self, extractor_with_cache):
        """Test that cached stream URL is returned without API call."""
        video_url = "https://rumble.com/v12345-test-video.html"
        video_id = "v12345"
        quality = "best"
        
        # Pre-populate cache
        stream_url = "https://stream.example.com/video.mp4"
        await extractor_with_cache.cache_manager.set_stream_url("rumble", video_id, stream_url, quality)
        
        # Mock get_video_metadata since download_audio calls it
        metadata = {"title": "Test Video"}
        with patch.object(extractor_with_cache, 'get_video_metadata') as mock_metadata:
            mock_metadata.return_value = metadata
            
            # Mock the API call - it should not be called
            with patch.object(extractor_with_cache, '_make_actor_call') as mock_api:
                result = await extractor_with_cache.download_audio(video_url, quality)
                
                # API should not be called for stream URL
                mock_api.assert_not_called()
                
                # Should return cached stream URL
                assert result == stream_url
    
    @pytest.mark.asyncio
    async def test_stream_url_cache_miss(self, extractor_with_cache):
        """Test that API is called on stream URL cache miss."""
        video_url = "https://rumble.com/v12345-test-video.html"
        video_id = "v12345"
        quality = "best"
        
        # Mock metadata response
        metadata = {"title": "Test Video"}
        with patch.object(extractor_with_cache, 'get_video_metadata') as mock_metadata:
            mock_metadata.return_value = metadata
            
            # Mock API response for stream URL
            api_response = {
                "items": [{
                    "videoUrl": "https://stream.example.com/video.mp4"
                }]
            }
            
            with patch.object(extractor_with_cache, '_make_actor_call') as mock_api:
                mock_api.return_value = api_response
                
                result = await extractor_with_cache.download_audio(video_url, quality)
                
                # API should be called
                mock_api.assert_called_once()
                
                # Check result
                assert result == "https://stream.example.com/video.mp4"
                
                # Verify stream URL was cached
                cached = await extractor_with_cache.cache_manager.get_stream_url("rumble", video_id, quality)
                assert cached == result
    
    @pytest.mark.asyncio
    async def test_search_results_cache_hit(self, extractor_with_cache):
        """Test that cached search results are returned."""
        query = "test query"
        max_results = 5
        
        # Pre-populate cache with more results than requested
        cached_results = [
            {"id": f"vid{i}", "title": f"Video {i}"} 
            for i in range(10)
        ]
        await extractor_with_cache.cache_manager.set_search_results("rumble", query, cached_results)
        
        # Mock the API call - it should not be called
        with patch.object(extractor_with_cache, '_make_actor_call') as mock_api:
            results = await extractor_with_cache.search_videos(query, max_results)
            
            # API should not be called
            mock_api.assert_not_called()
            
            # Should return requested number of results from cache
            assert len(results) == max_results
            assert results[0]["id"] == "vid0"
    
    @pytest.mark.asyncio
    async def test_search_results_cache_miss(self, extractor_with_cache):
        """Test that API is called on search cache miss."""
        query = "test query"
        max_results = 5
        
        # Mock API response
        api_response = {
            "items": [
                {
                    "id": f"vid{i}",
                    "title": f"Video {i}",
                    "description": f"Description {i}",
                    "duration": i * 100,
                    "creator": f"Creator {i}",
                    "viewsCount": i * 1000,
                    "publishedAt": f"2024-01-0{i+1}",
                    "thumbnail": f"https://example.com/thumb{i}.jpg",
                    "url": f"https://rumble.com/v{i}-video.html"
                }
                for i in range(max_results)
            ]
        }
        
        with patch.object(extractor_with_cache, '_make_actor_call') as mock_api:
            mock_api.return_value = api_response
            
            results = await extractor_with_cache.search_videos(query, max_results)
            
            # API should be called
            mock_api.assert_called_once()
            
            # Check results
            assert len(results) == max_results
            assert results[0]["title"] == "Video 0"
            
            # Verify results were cached
            cached = await extractor_with_cache.cache_manager.get_search_results("rumble", query)
            assert len(cached) == max_results
    
    @pytest.mark.asyncio
    async def test_cache_metrics_tracking(self, extractor_with_cache):
        """Test that cache metrics are properly tracked."""
        video_url = "https://rumble.com/v12345-test-video.html"
        
        # Perform some cache operations
        await extractor_with_cache.cache_manager.set_video_metadata("rumble", "v12345", {"title": "Test"})
        await extractor_with_cache.get_video_metadata(video_url)  # Hit
        
        # Try non-existent video
        with patch.object(extractor_with_cache, '_make_actor_call') as mock_api:
            mock_api.return_value = {"items": [{"title": "New Video"}]}
            await extractor_with_cache.get_video_metadata("https://rumble.com/v99999-new.html")  # Miss
        
        # Get metrics from extractor
        metrics = await extractor_with_cache.get_cache_metrics()
        
        assert metrics['hits'] >= 1
        assert metrics['misses'] >= 1
        assert metrics['hit_rate'] > 0
    
    @pytest.mark.asyncio
    async def test_extractor_close_with_cache(self, extractor_with_cache):
        """Test that extractor properly closes cache resources."""
        # Mock the cache manager close method
        with patch.object(extractor_with_cache.cache_manager, 'close') as mock_close:
            await extractor_with_cache.close()
            
            # Cache manager should be closed
            mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """Test extractor works without cache manager."""
        extractor = RumbleExtractor(apify_api_token="test_token", cache_manager=None)
        
        # Mock API response
        api_response = {
            "items": [{
                "title": "Test Video",
                "duration": 600
            }]
        }
        
        with patch.object(extractor, '_make_actor_call') as mock_api:
            mock_api.return_value = api_response
            
            result = await extractor.get_video_metadata("https://rumble.com/v12345-test.html")
            
            # API should be called (no cache)
            mock_api.assert_called_once()
            
            # Should still work without cache
            assert result["title"] == "Test Video"