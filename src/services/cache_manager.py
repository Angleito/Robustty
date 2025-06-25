"""
Cache manager for reducing API calls across the application.
Provides both in-memory and Redis caching layers with TTL support.
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union, List, Tuple
from collections import defaultdict
import logging

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

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caching for frequently accessed resources like video metadata
    and stream URLs to reduce API calls.
    """
    
    DEFAULT_METADATA_TTL = 3600  # 1 hour for metadata
    DEFAULT_STREAM_TTL = 1800    # 30 minutes for stream URLs
    
    # Tiered cache TTLs
    EXTENDED_TTL = 86400        # 24 hours for fallback mode
    EMERGENCY_TTL = 604800      # 7 days for emergency mode
    
    # Cache tiers
    TIER_SHORT = 'short'
    TIER_MEDIUM = 'medium'
    TIER_LONG = 'long'
    
    def __init__(self, config_loader: Dict[str, Any]):
        self.config = config_loader
        self.in_memory_cache: Dict[str, Dict[str, Any]] = {}
        self.redis_client: Optional[aioredis.Redis] = None
        self.use_redis = self.config.get('cache.redis.enabled', False)
        self.metrics = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'stale_hits': 0,
            'source_distribution': defaultdict(int),
            'age_distribution': defaultdict(int),
            'tier_distribution': defaultdict(int)
        }
        
        # Cache warming configuration
        self.warm_cache_enabled = self.config.get('cache.warm_cache_enabled', True)
        self.popular_queries: List[Tuple[str, int]] = []  # (query, access_count)
        self.access_counts: Dict[str, int] = defaultdict(int)
        self.last_warm_time = 0
        self.warm_interval = 3600  # 1 hour
        
    async def initialize(self):
        """Initialize Redis connection if enabled."""
        if self.use_redis and aioredis:
            try:
                redis_config = self.config.get('cache.redis', {})
                
                # Try new redis.asyncio API first
                if hasattr(aioredis, 'Redis'):
                    # Check if REDIS_URL is configured, use it preferentially
                    redis_url = redis_config.get('url')
                    if redis_url:
                        self.redis_client = aioredis.from_url(
                            redis_url,
                            decode_responses=True
                        )
                    else:
                        # Fall back to individual parameters
                        self.redis_client = aioredis.Redis(
                            host=redis_config.get('host', 'localhost'),
                            port=redis_config.get('port', 6379),
                            db=redis_config.get('db', 0),
                            password=redis_config.get('password'),
                            decode_responses=True
                        )
                else:
                    # Fall back to legacy aioredis API
                    redis_url = redis_config.get('url')
                    if redis_url:
                        # Parse URL for legacy API (limited URL support)
                        import urllib.parse
                        parsed = urllib.parse.urlparse(redis_url)
                        host = parsed.hostname or 'localhost'
                        port = parsed.port or 6379
                        db = int(parsed.path[1:]) if parsed.path and parsed.path != '/' else 0
                        password = parsed.password
                    else:
                        host = redis_config.get('host', 'localhost')
                        port = redis_config.get('port', 6379)
                        db = redis_config.get('db', 0)
                        password = redis_config.get('password')
                    
                    self.redis_client = await aioredis.create_redis_pool(
                        f"redis://{host}:{port}",
                        db=db,
                        password=password,
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
            
    def _generate_cache_key(self, prefix: str, identifier: str, suffix: Optional[str] = None, tier: str = None) -> str:
        """Generate a cache key with optional suffix and tier."""
        key_parts = [prefix, identifier]
        if suffix:
            key_parts.append(suffix)
        if tier and tier != self.TIER_SHORT:
            key_parts.append(tier)
        return ":".join(key_parts)
        
    def _generate_query_hash(self, query: str) -> str:
        """Generate a hash for search queries to use as cache key."""
        return hashlib.md5(query.encode()).hexdigest()[:16]
        
    async def get(self, key: str, track_access: bool = True) -> Optional[Any]:
        """Get value from cache, checking in-memory first, then Redis."""
        # Check in-memory cache first
        if key in self.in_memory_cache:
            entry = self.in_memory_cache[key]
            if entry['expires_at'] > time.time():
                self.metrics['hits'] += 1
                if track_access:
                    self._track_access(key, entry)
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
                        entry = {
                            'value': data,
                            'expires_at': time.time() + ttl,
                            'created_at': time.time() - (self.DEFAULT_METADATA_TTL - ttl),  # Estimate creation time
                            'metadata': data.get('_cache_metadata', {})
                        }
                        self.in_memory_cache[key] = entry
                        if track_access:
                            self._track_access(key, entry)
                    return data
            except Exception as e:
                print(f"Redis get error: {e}")
                
        self.metrics['misses'] += 1
        return None
        
    async def set(self, key: str, value: Any, ttl: int = None, metadata: Dict[str, Any] = None):
        """Set value in cache with TTL and optional metadata."""
        if ttl is None:
            ttl = self.DEFAULT_METADATA_TTL
            
        expires_at = time.time() + ttl
        created_at = time.time()
        
        # Add cache metadata to value if provided
        if metadata:
            if isinstance(value, dict):
                value['_cache_metadata'] = metadata
            else:
                # Wrap non-dict values
                value = {
                    '_cache_value': value,
                    '_cache_metadata': metadata
                }
        
        # Store in in-memory cache
        self.in_memory_cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': created_at,
            'metadata': metadata or {}
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
            
        # Calculate age distribution
        current_time = time.time()
        age_buckets = defaultdict(int)
        for entry in self.in_memory_cache.values():
            age = current_time - entry.get('created_at', current_time)
            if age < 3600:  # < 1 hour
                age_buckets['<1h'] += 1
            elif age < 86400:  # < 24 hours
                age_buckets['1h-24h'] += 1
            elif age < 604800:  # < 7 days
                age_buckets['1d-7d'] += 1
            else:
                age_buckets['>7d'] += 1
            
        return {
            'hits': self.metrics['hits'],
            'misses': self.metrics['misses'],
            'evictions': self.metrics['evictions'],
            'stale_hits': self.metrics['stale_hits'],
            'hit_rate': hit_rate,
            'in_memory_size': len(self.in_memory_cache),
            'redis_connected': self.redis_client is not None if self.use_redis else False,
            'source_distribution': dict(self.metrics['source_distribution']),
            'age_distribution': dict(age_buckets),
            'tier_distribution': dict(self.metrics['tier_distribution']),
            'popular_queries': self.popular_queries[:10]  # Top 10
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
    
    # Enhanced caching methods for fallback support
    
    async def cache_with_extended_ttl(self, key: str, value: Any, source: str = 'unknown', tier: str = None):
        """Cache with extended TTL for fallback scenarios."""
        if tier == self.TIER_LONG:
            ttl = self.EMERGENCY_TTL
        elif tier == self.TIER_MEDIUM:
            ttl = self.EXTENDED_TTL
        else:
            ttl = self.DEFAULT_METADATA_TTL
            
        metadata = {
            'source': source,
            'tier': tier or self.TIER_SHORT,
            'cached_at': datetime.utcnow().isoformat(),
            'extended_ttl': True
        }
        
        # Update metrics
        self.metrics['source_distribution'][source] += 1
        self.metrics['tier_distribution'][tier or self.TIER_SHORT] += 1
        
        await self.set(key, value, ttl, metadata)
        logger.info(f"Cached {key} with extended TTL ({ttl}s) from source: {source}")
    
    async def get_stale_ok(self, key: str) -> Optional[Any]:
        """Get cached value even if expired (for emergency fallback)."""
        # Check in-memory cache including expired entries
        if key in self.in_memory_cache:
            entry = self.in_memory_cache[key]
            value = entry['value']
            
            # Track stale hit
            if entry['expires_at'] <= time.time():
                self.metrics['stale_hits'] += 1
                logger.warning(f"Returning stale cache entry for {key}")
                
                # Update metadata to indicate staleness
                if isinstance(value, dict) and '_cache_metadata' in value:
                    value['_cache_metadata']['is_stale'] = True
                    value['_cache_metadata']['stale_since'] = datetime.utcnow().isoformat()
            
            self._track_access(key, entry)
            return value
            
        # Try Redis for stale data
        if self.use_redis and self.redis_client:
            try:
                # Try to get even if expired (Redis doesn't auto-delete immediately)
                value = await self.redis_client.get(key)
                if value:
                    self.metrics['stale_hits'] += 1
                    data = json.loads(value)
                    logger.warning(f"Returning potentially stale Redis entry for {key}")
                    
                    # Mark as stale
                    if isinstance(data, dict):
                        if '_cache_metadata' not in data:
                            data['_cache_metadata'] = {}
                        data['_cache_metadata']['is_stale'] = True
                        data['_cache_metadata']['retrieved_stale'] = True
                    
                    return data
            except Exception as e:
                logger.error(f"Redis stale get error: {e}")
                
        return None
    
    async def update_cache_metadata(self, key: str, metadata_updates: Dict[str, Any]):
        """Update metadata for a cached entry without changing the value."""
        # Update in-memory cache
        if key in self.in_memory_cache:
            entry = self.in_memory_cache[key]
            if 'metadata' not in entry:
                entry['metadata'] = {}
            entry['metadata'].update(metadata_updates)
            
            # Update embedded metadata in value if it's a dict
            if isinstance(entry['value'], dict):
                if '_cache_metadata' not in entry['value']:
                    entry['value']['_cache_metadata'] = {}
                entry['value']['_cache_metadata'].update(metadata_updates)
        
        # Update in Redis if available
        if self.use_redis and self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    data = json.loads(value)
                    if isinstance(data, dict):
                        if '_cache_metadata' not in data:
                            data['_cache_metadata'] = {}
                        data['_cache_metadata'].update(metadata_updates)
                        
                        # Get remaining TTL and re-set with updated data
                        ttl = await self.redis_client.ttl(key)
                        if ttl > 0:
                            await self.redis_client.setex(key, ttl, json.dumps(data))
            except Exception as e:
                logger.error(f"Redis metadata update error: {e}")
    
    def _track_access(self, key: str, entry: Dict[str, Any]):
        """Track access patterns for cache warming."""
        self.access_counts[key] += 1
        
        # Update access metadata
        if 'metadata' not in entry:
            entry['metadata'] = {}
        entry['metadata']['last_accessed'] = time.time()
        entry['metadata']['access_count'] = self.access_counts[key]
    
    async def warm_popular_cache(self, platform_callback=None):
        """Background task to refresh popular cached queries."""
        if not self.warm_cache_enabled:
            return
            
        current_time = time.time()
        if current_time - self.last_warm_time < self.warm_interval:
            return
            
        self.last_warm_time = current_time
        
        # Get top accessed keys
        sorted_keys = sorted(
            self.access_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]  # Top 20 most accessed
        
        logger.info(f"Warming cache for {len(sorted_keys)} popular entries")
        
        for key, count in sorted_keys:
            if count < 5:  # Skip if accessed less than 5 times
                continue
                
            # Check if entry is about to expire
            if key in self.in_memory_cache:
                entry = self.in_memory_cache[key]
                time_to_expire = entry['expires_at'] - current_time
                
                # Refresh if expiring within 10 minutes
                if time_to_expire < 600 and platform_callback:
                    try:
                        # Extract platform and query from key
                        parts = key.split(':')
                        if len(parts) >= 3 and parts[1] == 'search':
                            platform = parts[0]
                            query_hash = parts[2]
                            
                            # Callback to platform to refresh
                            logger.debug(f"Warming cache for {platform} query (hash: {query_hash})")
                            await platform_callback(platform, key)
                    except Exception as e:
                        logger.error(f"Cache warming error for {key}: {e}")
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get detailed cache statistics for monitoring and optimization."""
        current_time = time.time()
        stats = {
            'total_entries': len(self.in_memory_cache),
            'total_accesses': sum(self.access_counts.values()),
            'unique_accessed': len(self.access_counts),
            'memory_usage_bytes': 0,  # Estimate
            'by_tier': defaultdict(int),
            'by_source': defaultdict(int),
            'by_age': defaultdict(int),
            'expiring_soon': 0,
            'already_expired': 0
        }
        
        for key, entry in self.in_memory_cache.items():
            # Estimate memory usage
            stats['memory_usage_bytes'] += len(json.dumps(entry['value']))
            
            # Count by tier
            tier = entry.get('metadata', {}).get('tier', self.TIER_SHORT)
            stats['by_tier'][tier] += 1
            
            # Count by source
            source = entry.get('metadata', {}).get('source', 'unknown')
            stats['by_source'][source] += 1
            
            # Count by age
            age = current_time - entry.get('created_at', current_time)
            if age < 3600:
                stats['by_age']['<1h'] += 1
            elif age < 86400:
                stats['by_age']['1h-24h'] += 1
            elif age < 604800:
                stats['by_age']['1d-7d'] += 1
            else:
                stats['by_age']['>7d'] += 1
            
            # Check expiration
            time_to_expire = entry['expires_at'] - current_time
            if time_to_expire <= 0:
                stats['already_expired'] += 1
            elif time_to_expire < 600:  # Expiring in 10 minutes
                stats['expiring_soon'] += 1
        
        return stats
    
    # Tiered caching convenience methods
    
    async def set_short_term(self, key: str, value: Any, source: str = 'api'):
        """Set short-term cache (default TTL)."""
        await self.cache_with_extended_ttl(key, value, source, self.TIER_SHORT)
    
    async def set_medium_term(self, key: str, value: Any, source: str = 'ytdlp'):
        """Set medium-term cache (24 hours)."""
        await self.cache_with_extended_ttl(key, value, source, self.TIER_MEDIUM)
    
    async def set_long_term(self, key: str, value: Any, source: str = 'emergency'):
        """Set long-term cache (7 days)."""
        await self.cache_with_extended_ttl(key, value, source, self.TIER_LONG)