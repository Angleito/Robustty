"""
Tests for the cache manager service.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch

from src.services.cache_manager import CacheManager
from src.utils.config_loader import ConfigLoader


class TestCacheManager:
    """Test cases for the CacheManager class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config loader."""
        config = Mock(spec=ConfigLoader)
        config.get.return_value = False  # Redis disabled by default
        return config
    
    @pytest.fixture
    async def cache_manager(self, mock_config):
        """Create a cache manager instance for testing."""
        manager = CacheManager(mock_config)
        await manager.initialize()
        yield manager
        await manager.close()
    
    @pytest.mark.asyncio
    async def test_initialize_no_redis(self, cache_manager):
        """Test initialization without Redis."""
        assert cache_manager.redis_client is None
        assert cache_manager.use_redis is False
    
    @pytest.mark.asyncio
    async def test_initialize_with_redis_failure(self, mock_config):
        """Test initialization with Redis connection failure."""
        mock_config.get.side_effect = lambda key, default=None: {
            'cache.redis.enabled': True,
            'cache.redis': {'host': 'badhost', 'port': 6379}
        }.get(key, default)
        
        manager = CacheManager(mock_config)
        await manager.initialize()
        
        # Should gracefully handle connection failure
        assert manager.redis_client is None
        assert manager.use_redis is False
    
    @pytest.mark.asyncio
    async def test_in_memory_cache_set_get(self, cache_manager):
        """Test in-memory cache set and get operations."""
        await cache_manager.set("test_key", "test_value", ttl=5)
        
        # Should retrieve from cache
        value = await cache_manager.get("test_key")
        assert value == "test_value"
        assert cache_manager.metrics['hits'] == 1
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_manager):
        """Test cache miss increments counter."""
        value = await cache_manager.get("nonexistent_key")
        assert value is None
        assert cache_manager.metrics['misses'] == 1
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache_manager):
        """Test that cached items expire."""
        await cache_manager.set("expire_test", "value", ttl=1)
        
        # Should be in cache
        value = await cache_manager.get("expire_test")
        assert value == "value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        value = await cache_manager.get("expire_test")
        assert value is None
        assert cache_manager.metrics['evictions'] == 1
    
    @pytest.mark.asyncio
    async def test_delete_from_cache(self, cache_manager):
        """Test deleting items from cache."""
        await cache_manager.set("delete_test", "value")
        
        # Verify it's in cache
        value = await cache_manager.get("delete_test")
        assert value == "value"
        
        # Delete it
        await cache_manager.delete("delete_test")
        
        # Should be gone
        value = await cache_manager.get("delete_test")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_clear_expired(self, cache_manager):
        """Test clearing expired entries."""
        # Add some items with short TTL
        await cache_manager.set("expire1", "value1", ttl=1)
        await cache_manager.set("expire2", "value2", ttl=1)
        await cache_manager.set("keep", "value3", ttl=10)
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Clear expired
        await cache_manager.clear_expired()
        
        # Only non-expired should remain
        assert "keep" in cache_manager.in_memory_cache
        assert "expire1" not in cache_manager.in_memory_cache
        assert "expire2" not in cache_manager.in_memory_cache
        assert cache_manager.metrics['evictions'] == 2
    
    @pytest.mark.asyncio
    async def test_video_metadata_cache(self, cache_manager):
        """Test video metadata caching methods."""
        metadata = {
            "title": "Test Video",
            "duration": 300,
            "uploader": "Test User"
        }
        
        # Cache metadata
        await cache_manager.set_video_metadata("rumble", "video123", metadata)
        
        # Retrieve metadata
        cached = await cache_manager.get_video_metadata("rumble", "video123")
        assert cached == metadata
    
    @pytest.mark.asyncio
    async def test_stream_url_cache(self, cache_manager):
        """Test stream URL caching methods."""
        stream_url = "https://stream.example.com/video.mp4"
        
        # Cache stream URL
        await cache_manager.set_stream_url("rumble", "video123", stream_url, "high")
        
        # Retrieve stream URL
        cached = await cache_manager.get_stream_url("rumble", "video123", "high")
        assert cached == stream_url
        
        # Different quality should be different cache entry
        cached_other = await cache_manager.get_stream_url("rumble", "video123", "low")
        assert cached_other is None
    
    @pytest.mark.asyncio  
    async def test_search_results_cache(self, cache_manager):
        """Test search results caching methods."""
        results = [
            {"id": "1", "title": "Video 1"},
            {"id": "2", "title": "Video 2"}
        ]
        
        # Cache search results
        await cache_manager.set_search_results("rumble", "test query", results)
        
        # Retrieve search results
        cached = await cache_manager.get_search_results("rumble", "test query")
        assert cached == results
        
        # Different query should be different cache entry
        cached_other = await cache_manager.get_search_results("rumble", "other query")
        assert cached_other is None
    
    @pytest.mark.asyncio
    async def test_get_metrics(self, cache_manager):
        """Test getting cache metrics."""
        # Perform some operations
        await cache_manager.set("key1", "value1")
        await cache_manager.get("key1")  # Hit
        await cache_manager.get("key2")  # Miss
        
        metrics = await cache_manager.get_metrics()
        
        assert metrics['hits'] == 1
        assert metrics['misses'] == 1
        assert metrics['evictions'] == 0
        assert metrics['hit_rate'] == 0.5
        assert metrics['in_memory_size'] == 1
        assert metrics['redis_connected'] is False
    
    @pytest.mark.asyncio
    async def test_redis_operations(self, mock_config):
        """Test operations with Redis (mocked)."""
        # Configure for Redis use
        mock_config.get.side_effect = lambda key, default=None: {
            'cache.redis.enabled': True,
            'cache.redis': {'host': 'localhost', 'port': 6379}
        }.get(key, default)
        
        # Patch both possible imports
        with patch('redis.asyncio.Redis') as mock_redis_new, \
             patch('aioredis.create_redis_pool') as mock_redis_legacy:
            # Mock Redis client
            mock_client = AsyncMock()
            
            # Set up both mocks to return the same client
            mock_redis_new.return_value = mock_client
            mock_redis_legacy.return_value = mock_client
            
            mock_client.get.return_value = None
            mock_client.ttl.return_value = 10
            
            manager = CacheManager(mock_config)
            await manager.initialize()
            
            # Should have Redis client
            assert manager.redis_client is not None
            assert manager.use_redis is True
            
            # Test set operation
            await manager.set("test_key", "test_value", ttl=60)
            mock_client.setex.assert_called_once_with("test_key", 60, '\"test_value\"')
            
            # Test get operation
            mock_client.get.return_value = b'"cached_value"'
            value = await manager.get("test_key")
            assert value == "cached_value"
            mock_client.get.assert_called_with("test_key")
            
            await manager.close()
            mock_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache_manager):
        """Test cache key generation methods."""
        # Test basic key generation
        key = cache_manager._generate_cache_key("prefix", "id")
        assert key == "prefix:id"
        
        # Test with suffix
        key = cache_manager._generate_cache_key("prefix", "id", "suffix")
        assert key == "prefix:id:suffix"
        
        # Test query hash generation
        hash1 = cache_manager._generate_query_hash("test query")
        hash2 = cache_manager._generate_query_hash("test query")
        hash3 = cache_manager._generate_query_hash("different query")
        
        assert hash1 == hash2  # Same query produces same hash
        assert hash1 != hash3  # Different queries produce different hashes
        assert len(hash1) == 16  # Hash is truncated to 16 chars