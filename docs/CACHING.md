# Caching in Robustty

Robustty includes a robust caching system to reduce API calls and improve performance. The caching system supports both in-memory and Redis-based caching.

## Overview

The cache manager provides:
- **In-memory caching**: Fast access to frequently used data
- **Redis caching**: Distributed caching for multi-instance deployments
- **Automatic TTL management**: Configurable expiration times
- **Platform-specific caching**: Optimized for each platform's needs

## Configuration

### Basic Configuration

Add the following to your `config/config.yaml`:

```yaml
cache:
  redis:
    enabled: false  # Set to true to enable Redis
    host: localhost
    port: 6379
    db: 0
    password: ""
  
  ttl:
    metadata: 3600    # 1 hour for video metadata
    stream: 1800      # 30 minutes for stream URLs
    search: 1800      # 30 minutes for search results
  
  max_memory_size: 1000  # Maximum items in memory cache
```

### Environment Variables

Configure Redis through environment variables:

```bash
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=yourpassword
```

## Features

### 1. In-Memory Caching

- Always enabled by default
- Fast access to recently used data
- Automatic eviction of expired entries
- Configurable size limits

### 2. Redis Caching (Optional)

- Distributed caching across instances
- Persistent cache that survives restarts
- Automatic failover to in-memory if Redis unavailable

### 3. Platform-Specific Caching

#### YouTube
- Video metadata (title, duration, uploader)
- Stream URLs by quality
- Search results

#### Rumble
- Video metadata with Apify responses
- Stream URLs with quality selection
- Search results with query hashing

#### PeerTube
- Instance-specific video data
- Federation-aware caching
- Search results per instance

## Cache Keys

The cache uses structured keys:
- `platform:metadata:video_id` - Video metadata
- `platform:stream:video_id:quality` - Stream URLs
- `platform:search:query_hash` - Search results

## Metrics

Access cache metrics through the API:

```json
{
  "hits": 150,
  "misses": 50,
  "evictions": 10,
  "hit_rate": 0.75,
  "in_memory_size": 250,
  "redis_connected": true
}
```

## Docker Deployment

When using Docker Compose:

```yaml
services:
  bot:
    environment:
      - REDIS_ENABLED=true
      - REDIS_HOST=redis
    depends_on:
      - redis
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
```

## Performance Benefits

1. **Reduced API Calls**: Up to 80% reduction for popular content
2. **Faster Response Times**: Cached responses served instantly
3. **Lower Costs**: Fewer API calls mean lower API costs
4. **Better User Experience**: Instant playback for cached content

## TTL Guidelines

Recommended TTL values:
- **Metadata**: 1-4 hours (content doesn't change often)
- **Stream URLs**: 30 minutes (URLs may expire)
- **Search Results**: 30-60 minutes (for fresh results)

## Monitoring

Monitor cache performance:

1. Check hit rates:
   ```python
   metrics = await cache_manager.get_metrics()
   print(f"Hit rate: {metrics['hit_rate']*100:.1f}%")
   ```

2. Monitor Redis connection:
   ```bash
   redis-cli ping
   ```

3. View cache size:
   ```bash
   redis-cli info memory
   ```

## Troubleshooting

### High Cache Misses
- Increase TTL values for stable content
- Check if Redis is properly connected
- Verify cache keys are consistent

### Memory Issues
- Reduce `max_memory_size` in config
- Enable Redis for distributed caching
- Implement cache eviction policies

### Redis Connection Failed
- Check Redis host/port configuration
- Verify Redis is running
- Check firewall rules

## Best Practices

1. **Use appropriate TTLs**: Balance freshness vs. performance
2. **Monitor metrics**: Track hit rates and adjust accordingly
3. **Enable Redis for production**: Better scalability
4. **Cache warming**: Pre-cache popular content
5. **Graceful degradation**: Always handle cache misses

## Future Enhancements

- Cache warming strategies
- Intelligent TTL adjustment
- Cache invalidation webhooks
- Multi-tier caching (L1/L2)
- Cache compression