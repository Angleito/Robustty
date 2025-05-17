"""
Cache manager for reducing API calls across the application.
Provides both in-memory and Redis caching layers with TTL support.
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

try:
    # Try the newer redis package first (aioredis was renamed)
    import redis.asyncio as aioredis
except ImportError:
    try:
        # Fall back to legacy aioredis package
        import aioredis
    except ImportError:
        # If neither is available, we'll run without Redis
        aioredis = None

# Configuration loading is handled by bot initialization


class CacheManager:
    """
    Manages caching for frequently accessed resources like video metadata
    and stream URLs to reduce API calls.
    """
    
    DEFAULT_METADATA_TTL = 3600  # 1 hour for metadata
    DEFAULT_STREAM_TTL = 1800    # 30 minutes for stream URLs
    
    def __init__(self, config_loader: Dict[str, Any]):
        self.config = config_loader
        self.in_memory_cache: Dict[str, Dict[str, Any]] = {}
        self.redis_client: Optional[aioredis.Redis] = None
        self.use_redis = self.config.get('cache.redis.enabled', False)
        self.metrics = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
    async def initialize(self):
        """Initialize Redis connection if enabled."""
        if self.use_redis and aioredis:
            try:
                redis_config = self.config.get('cache.redis', {})
                
                # Try new redis.asyncio API first
                if hasattr(aioredis, 'Redis'):
                    self.redis_client = aioredis.Redis(
                        host=redis_config.get('host', 'localhost'),
                        port=redis_config.get('port', 6379),
                        db=redis_config.get('db', 0),
                        password=redis_config.get('password'),
                        decode_responses=True
                    )
                else:
                    # Fall back to legacy aioredis API
                    self.redis_client = await aioredis.create_redis_pool(
                        f"redis://{redis_config.get('host', 'localhost')}:{redis_config.get('port', 6379)}",
                        db=redis_config.get('db', 0),
                        password=redis_config.get('password'),
                        minsize=5,
                        maxsize=20
                    )
            except Exception as e:
                print(f"Failed to connect to Redis: {e}")
                self.use_redis = False
        elif self.use_redis and not aioredis:
            print("Redis client not available - caching will use in-memory only")
            self.use_redis = False
                
    async def close(self):
        """Close Redis connection if open."""
        if self.redis_client:
            if hasattr(self.redis_client, 'close'):
                await self.redis_client.close()
            else:
                # Legacy aioredis
                self.redis_client.close()
                await self.redis_client.wait_closed()
            
    def _generate_cache_key(self, prefix: str, identifier: str, suffix: Optional[str] = None) -> str:
        """Generate a cache key with optional suffix."""
        key_parts = [prefix, identifier]
        if suffix:
            key_parts.append(suffix)
        return ":".join(key_parts)
        
    def _generate_query_hash(self, query: str) -> str:
        """Generate a hash for search queries to use as cache key."""
        return hashlib.md5(query.encode()).hexdigest()[:16]
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache, checking in-memory first, then Redis."""
        # Check in-memory cache first
        if key in self.in_memory_cache:
            entry = self.in_memory_cache[key]
            if entry['expires_at'] > time.time():
                self.metrics['hits'] += 1
                return entry['value']
            else:
                # Expired, remove from cache
                del self.in_memory_cache[key]
                self.metrics['evictions'] += 1
                
        # Check Redis if available
        if self.use_redis and self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    self.metrics['hits'] += 1
                    data = json.loads(value)
                    # Also cache in memory for faster access
                    ttl = await self.redis_client.ttl(key)
                    if ttl > 0:
                        self.in_memory_cache[key] = {
                            'value': data,
                            'expires_at': time.time() + ttl
                        }
                    return data
            except Exception as e:
                print(f"Redis get error: {e}")
                
        self.metrics['misses'] += 1
        return None
        
    async def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache with TTL."""
        if ttl is None:
            ttl = self.DEFAULT_METADATA_TTL
            
        expires_at = time.time() + ttl
        
        # Store in in-memory cache
        self.in_memory_cache[key] = {
            'value': value,
            'expires_at': expires_at
        }
        
        # Store in Redis if available
        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.setex(
                    key, 
                    ttl, 
                    json.dumps(value)
                )
            except Exception as e:
                print(f"Redis set error: {e}")
                
    async def delete(self, key: str):
        """Delete value from cache."""
        # Remove from in-memory cache
        if key in self.in_memory_cache:
            del self.in_memory_cache[key]
            
        # Remove from Redis if available
        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception as e:
                print(f"Redis delete error: {e}")
                
    async def clear_expired(self):
        """Clear expired entries from in-memory cache."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.in_memory_cache.items()
            if entry['expires_at'] <= current_time
        ]
        
        for key in expired_keys:
            del self.in_memory_cache[key]
            self.metrics['evictions'] += 1
            
    async def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics for monitoring."""
        hit_rate = 0
        total_requests = self.metrics['hits'] + self.metrics['misses']
        if total_requests > 0:
            hit_rate = self.metrics['hits'] / total_requests
            
        return {
            'hits': self.metrics['hits'],
            'misses': self.metrics['misses'],
            'evictions': self.metrics['evictions'],
            'hit_rate': hit_rate,
            'in_memory_size': len(self.in_memory_cache),
            'redis_connected': self.redis_client is not None if self.use_redis else False
        }
        
    # Platform-specific cache methods
    
    async def get_video_metadata(self, platform: str, video_id: str) -> Optional[Dict[str, Any]]:
        """Get cached video metadata."""
        key = self._generate_cache_key(f"{platform}:metadata", video_id)
        return await self.get(key)
        
    async def set_video_metadata(self, platform: str, video_id: str, metadata: Dict[str, Any], ttl: int = None):
        """Cache video metadata."""
        key = self._generate_cache_key(f"{platform}:metadata", video_id)
        if ttl is None:
            ttl = self.DEFAULT_METADATA_TTL
        await self.set(key, metadata, ttl)
        
    async def get_stream_url(self, platform: str, video_id: str, quality: Optional[str] = None) -> Optional[str]:
        """Get cached stream URL."""
        key = self._generate_cache_key(f"{platform}:stream", video_id, quality)
        return await self.get(key)
        
    async def set_stream_url(self, platform: str, video_id: str, stream_url: str, quality: Optional[str] = None, ttl: int = None):
        """Cache stream URL."""
        key = self._generate_cache_key(f"{platform}:stream", video_id, quality)
        if ttl is None:
            ttl = self.DEFAULT_STREAM_TTL
        await self.set(key, stream_url, ttl)
        
    async def get_search_results(self, platform: str, query: str) -> Optional[list]:
        """Get cached search results."""
        query_hash = self._generate_query_hash(query)
        key = self._generate_cache_key(f"{platform}:search", query_hash)
        return await self.get(key)
        
    async def set_search_results(self, platform: str, query: str, results: list, ttl: int = None):
        """Cache search results."""
        query_hash = self._generate_query_hash(query)
        key = self._generate_cache_key(f"{platform}:search", query_hash)
        if ttl is None:
            ttl = self.DEFAULT_STREAM_TTL  # Use shorter TTL for search results
        await self.set(key, results, ttl)