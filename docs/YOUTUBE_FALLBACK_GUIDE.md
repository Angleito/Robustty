# YouTube Fallback Implementation Guide

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Configuration Guide](#configuration-guide)
3. [Operational Guide](#operational-guide)
4. [Troubleshooting](#troubleshooting)
5. [API Reference](#api-reference)

## Architecture Overview

### Fallback Chain Design

The YouTube fallback system implements a multi-layered approach to ensure continuous service availability when the primary YouTube API encounters issues:

```
┌─────────────────────────────────────────────────────────────┐
│                     User Request                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Fallback Manager                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐ │
│  │ Strategy Chain  │  │ Health Monitor   │  │   Metrics  │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬─────┘ │
└───────────┼────────────────────┼───────────────────┼───────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Fallback Strategies                      │
├─────────────────────┬───────────────────┬──────────────────┤
│  1. YouTube API     │  2. yt-dlp Direct │  3. Alternative │
│     (Primary)       │     (Secondary)   │    Platforms    │
└─────────────────────┴───────────────────┴──────────────────┘
```

### Component Interactions

#### 1. **FallbackManager** (`src/platforms/youtube_fallback.py`)
- Central coordinator for all fallback operations
- Manages strategy chain execution
- Tracks health metrics and performance

#### 2. **FallbackStrategy** (Abstract Base)
- Defines interface for all fallback strategies
- Implements health checking and metrics collection
- Provides async execution context

#### 3. **Strategy Implementations**
- **YouTubeAPIStrategy**: Primary strategy using official API
- **YtdlpDirectStrategy**: Direct extraction using yt-dlp
- **AlternativePlatformStrategy**: Cross-platform search fallback

### Data Flow

```python
# Simplified data flow example
async def search_with_fallback(query: str) -> List[VideoResult]:
    fallback_manager = FallbackManager()
    
    # Primary attempt
    try:
        return await fallback_manager.execute(
            YouTubeAPIStrategy(),
            query=query
        )
    except QuotaExceededError:
        # Automatic fallback to yt-dlp
        return await fallback_manager.execute(
            YtdlpDirectStrategy(),
            query=query
        )
    except Exception as e:
        # Final fallback to alternative platforms
        return await fallback_manager.execute(
            AlternativePlatformStrategy(),
            query=query
        )
```

## Configuration Guide

### Configuration File Structure

Add to `config/config.yaml`:

```yaml
youtube:
  # Primary API configuration
  api:
    enabled: true
    key: ${YOUTUBE_API_KEY}
    quota_limit: 10000
    quota_reset_time: "00:00"  # UTC
    
  # Fallback configuration
  fallback:
    enabled: true
    strategy_order:
      - "api"
      - "ytdlp_direct"
      - "alternative_platform"
    
    # Strategy-specific settings
    strategies:
      api:
        max_retries: 3
        retry_delay: 1.0
        timeout: 30
        
      ytdlp_direct:
        enabled: true
        max_results: 10
        timeout: 45
        cookie_path: "/app/cookies/youtube.txt"
        extractors:
          - "youtube"
          - "youtube:tab"
        
      alternative_platform:
        enabled: true
        platforms:
          - "rumble"
          - "odysee"
        max_results_per_platform: 5
    
    # Health monitoring
    health:
      check_interval: 60  # seconds
      failure_threshold: 3
      recovery_threshold: 2
      
    # Circuit breaker
    circuit_breaker:
      enabled: true
      failure_threshold: 5
      recovery_timeout: 300  # seconds
      half_open_requests: 3
```

### Environment Variables

```bash
# Required
YOUTUBE_API_KEY=your_api_key_here

# Optional fallback configuration
YOUTUBE_FALLBACK_ENABLED=true
YOUTUBE_FALLBACK_LOG_LEVEL=INFO
YOUTUBE_QUOTA_BUFFER=1000  # Reserve quota amount
YOUTUBE_FALLBACK_CACHE_TTL=3600  # Cache duration in seconds
```

### Recommended Settings

#### For High-Traffic Bots

```yaml
youtube:
  fallback:
    strategies:
      api:
        quota_limit: 8000  # Leave 20% buffer
        rate_limit:
          requests_per_second: 10
          burst_size: 20
      
      ytdlp_direct:
        concurrent_requests: 5
        cache_results: true
        cache_ttl: 1800
```

#### For Development/Testing

```yaml
youtube:
  fallback:
    strategies:
      api:
        quota_limit: 1000  # Conservative limit
        mock_quota_exceeded: true  # Force fallback testing
      
      ytdlp_direct:
        verbose_logging: true
        save_debug_info: true
```

### Performance Tuning

```yaml
# Optimize for speed
performance:
  preload_strategies: true
  connection_pool_size: 10
  dns_cache_ttl: 300
  
  caching:
    redis:
      enabled: true
      ttl:
        search_results: 3600
        stream_urls: 300
        metadata: 7200
```

## Operational Guide

### Monitoring Fallback Health

#### 1. **Health Check Endpoint**

```python
# Check fallback system health
from src.platforms.youtube_fallback import FallbackManager

async def check_health():
    manager = FallbackManager()
    health_status = await manager.get_health_status()
    
    print(f"Overall Health: {health_status.overall}")
    for strategy, status in health_status.strategies.items():
        print(f"{strategy}: {status.state} "
              f"(failures: {status.consecutive_failures})")
```

#### 2. **Prometheus Metrics**

Key metrics to monitor:

```python
# Metric examples
youtube_fallback_requests_total{strategy="api", status="success"}
youtube_fallback_requests_total{strategy="ytdlp_direct", status="fallback"}
youtube_fallback_latency_seconds{strategy="api", quantile="0.95"}
youtube_quota_usage_ratio  # Current quota usage (0.0-1.0)
youtube_circuit_breaker_state{strategy="api"}  # open/closed/half-open
```

#### 3. **Log Analysis**

Important log patterns:

```bash
# Quota approaching limit
grep "WARN.*quota usage.*90%" /var/log/robustty.log

# Fallback activated
grep "INFO.*Fallback activated.*strategy=ytdlp_direct" /var/log/robustty.log

# Circuit breaker events
grep "ERROR.*Circuit breaker opened" /var/log/robustty.log
```

### Responding to Quota Issues

#### 1. **Automated Response**

The system automatically handles quota issues:

```python
# Built-in quota management
class QuotaManager:
    async def check_quota(self):
        if self.usage > self.soft_limit:
            # Trigger preemptive fallback
            await self.enable_fallback_mode()
        
        if self.usage >= self.hard_limit:
            # Force immediate fallback
            raise QuotaExceededError()
```

#### 2. **Manual Intervention**

```bash
# Force fallback mode via Redis
redis-cli SET youtube:fallback:force_mode ytdlp_direct EX 3600

# Reset quota counter (use with caution)
redis-cli DEL youtube:quota:current

# Disable specific strategy
redis-cli SET youtube:strategy:api:disabled 1
```

#### 3. **Quota Conservation Mode**

```python
# Enable quota conservation
from src.platforms.youtube_fallback import FallbackManager

manager = FallbackManager()
await manager.enable_quota_conservation(
    target_daily_usage=5000,  # Limit to 50% of quota
    prefer_cache=True,
    reduce_search_results=True
)
```

### Manual Intervention Procedures

#### 1. **Emergency Fallback Switch**

```python
# Force immediate fallback to specific strategy
async def emergency_fallback():
    manager = FallbackManager()
    
    # Disable primary strategy
    await manager.disable_strategy("api")
    
    # Force specific strategy
    await manager.set_primary_strategy("ytdlp_direct")
    
    # Set recovery timer
    await manager.schedule_recovery(minutes=30)
```

#### 2. **Cache Management**

```bash
# Clear corrupted cache entries
redis-cli --scan --pattern "youtube:cache:*" | xargs redis-cli DEL

# Warm cache with common queries
python scripts/warm_youtube_cache.py --queries popular_songs.txt

# Export cache for backup
redis-cli --rdb youtube_cache_backup.rdb
```

#### 3. **Strategy Testing**

```python
# Test individual strategies
from src.platforms.youtube_fallback import test_strategy

# Test with specific query
result = await test_strategy(
    "ytdlp_direct",
    query="test song",
    verbose=True
)

# Benchmark all strategies
results = await benchmark_all_strategies(
    queries=["song 1", "song 2"],
    iterations=10
)
```

## Troubleshooting

### Common Issues and Solutions

#### 1. **"YouTube API quota exceeded" errors**

**Symptoms:**
- Error 403 from YouTube API
- Logs show "quotaExceeded" errors

**Solutions:**
```bash
# Check current quota usage
curl -X GET http://localhost:8080/metrics | grep youtube_quota

# Force fallback mode
redis-cli SET youtube:fallback:force_mode ytdlp_direct EX 7200

# Verify fallback is working
tail -f /var/log/robustty.log | grep "strategy=ytdlp_direct"
```

#### 2. **"yt-dlp extraction failed" errors**

**Symptoms:**
- Fallback to yt-dlp fails
- "Unable to extract video info" errors

**Solutions:**
```bash
# Update yt-dlp
docker-compose exec robustty pip install --upgrade yt-dlp

# Check cookie validity
python scripts/validate_cookies.py --platform youtube

# Test extraction directly
docker-compose exec robustty yt-dlp --cookies /app/cookies/youtube.txt \
  --dump-json "https://youtube.com/watch?v=VIDEO_ID"
```

#### 3. **"Circuit breaker open" warnings**

**Symptoms:**
- Strategy marked as unavailable
- Automatic fallback not recovering

**Solutions:**
```python
# Check circuit breaker state
from src.platforms.youtube_fallback import FallbackManager

manager = FallbackManager()
states = await manager.get_circuit_states()

# Manual reset if needed
await manager.reset_circuit_breaker("api")

# Adjust sensitivity
await manager.update_circuit_config(
    failure_threshold=10,  # Increase tolerance
    recovery_timeout=600   # Longer recovery period
)
```

### Debug Procedures

#### 1. **Enable Verbose Logging**

```python
# In your code
import logging
logging.getLogger("youtube_fallback").setLevel(logging.DEBUG)

# Or via environment
export YOUTUBE_FALLBACK_LOG_LEVEL=DEBUG
```

#### 2. **Trace Request Flow**

```python
# Enable request tracing
from src.platforms.youtube_fallback import enable_tracing

with enable_tracing() as trace_id:
    result = await youtube.search("test query")
    
# View trace
traces = await get_trace_logs(trace_id)
for event in traces:
    print(f"{event.timestamp}: {event.strategy} - {event.action}")
```

#### 3. **Performance Profiling**

```python
# Profile fallback performance
from src.platforms.youtube_fallback import profile_strategies

report = await profile_strategies(
    queries=["test 1", "test 2"],
    iterations=10
)

print(f"API Strategy: {report.api.avg_latency}ms")
print(f"yt-dlp Strategy: {report.ytdlp.avg_latency}ms")
```

### Log Analysis

#### Key Log Patterns

```bash
# Fallback activation
INFO  [FallbackManager] Activating fallback: api -> ytdlp_direct (reason: quota_exceeded)

# Strategy health changes
WARN  [HealthMonitor] Strategy 'api' health degraded: 3 consecutive failures

# Circuit breaker events
ERROR [CircuitBreaker] Opening circuit for strategy 'api' after 5 failures

# Recovery events
INFO  [FallbackManager] Strategy 'api' recovered, resuming normal operation
```

#### Log Aggregation Queries

```sql
-- Find most common fallback reasons
SELECT reason, COUNT(*) as occurrences
FROM logs
WHERE message LIKE '%Activating fallback%'
GROUP BY reason
ORDER BY occurrences DESC;

-- Track fallback success rate
SELECT 
  strategy,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*) as success_rate
FROM fallback_requests
GROUP BY strategy;
```

## API Reference

### Core Classes

#### FallbackManager

```python
class FallbackManager:
    """Manages fallback strategies for YouTube operations."""
    
    async def execute(
        self,
        operation: str,
        *args,
        preferred_strategy: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Execute operation with automatic fallback.
        
        Args:
            operation: Operation to perform ('search', 'get_stream_url', etc.)
            preferred_strategy: Optional strategy preference
            *args, **kwargs: Operation arguments
            
        Returns:
            Operation result
            
        Raises:
            AllStrategiesFailedError: If all strategies fail
        """
        
    async def get_health_status(self) -> HealthStatus:
        """Get current health status of all strategies."""
        
    async def force_strategy(
        self,
        strategy_name: str,
        duration: Optional[int] = None
    ) -> None:
        """Force use of specific strategy."""
```

#### FallbackStrategy

```python
class FallbackStrategy(ABC):
    """Base class for fallback strategies."""
    
    @abstractmethod
    async def search_videos(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[VideoResult]:
        """Search for videos."""
        
    @abstractmethod
    async def get_stream_url(
        self,
        video_id: str,
        **kwargs
    ) -> str:
        """Get streaming URL for video."""
        
    async def health_check(self) -> bool:
        """Check if strategy is healthy."""
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
```

### Integration Points

#### 1. **Event Hooks**

```python
# Register fallback event handlers
from src.platforms.youtube_fallback import FallbackEvents

@FallbackEvents.on_fallback_activated
async def handle_fallback(event):
    logger.warning(f"Fallback activated: {event.from_strategy} -> {event.to_strategy}")
    await notify_admin(event)

@FallbackEvents.on_quota_warning
async def handle_quota_warning(event):
    if event.usage_percent > 90:
        await enable_conservation_mode()
```

#### 2. **Custom Strategies**

```python
from src.platforms.youtube_fallback import FallbackStrategy

class CustomCachingStrategy(FallbackStrategy):
    """Custom strategy with aggressive caching."""
    
    async def search_videos(self, query: str, **kwargs):
        # Check cache first
        cached = await self.cache.get(f"search:{query}")
        if cached:
            return cached
            
        # Fallback to another strategy
        result = await self.delegate.search_videos(query, **kwargs)
        
        # Cache aggressively
        await self.cache.set(f"search:{query}", result, ttl=7200)
        return result
```

#### 3. **Middleware Integration**

```python
# Add fallback middleware to bot
from src.platforms.youtube_fallback import FallbackMiddleware

class MusicBot(commands.Bot):
    async def setup_hook(self):
        # Add fallback middleware
        self.add_middleware(
            FallbackMiddleware(
                monitor_commands=["play", "search", "queue"],
                auto_retry=True,
                notify_users=True
            )
        )
```

### Configuration API

```python
# Runtime configuration updates
from src.platforms.youtube_fallback import FallbackConfig

config = FallbackConfig()

# Update quota limits
await config.set_quota_limit(8000)

# Adjust timeouts
await config.set_strategy_timeout("ytdlp_direct", 60)

# Enable/disable strategies
await config.enable_strategy("alternative_platform")
await config.disable_strategy("api", reason="maintenance")

# Get current configuration
current = await config.get_current()
print(json.dumps(current, indent=2))
```

### Metrics API

```python
from src.platforms.youtube_fallback import FallbackMetrics

metrics = FallbackMetrics()

# Get aggregated metrics
stats = await metrics.get_stats(
    time_range="1h",
    group_by="strategy"
)

# Get specific metric
quota_usage = await metrics.get_metric("youtube_quota_usage_ratio")

# Export for monitoring
prometheus_data = await metrics.export_prometheus()
```

## Best Practices

1. **Always monitor quota usage** - Set up alerts at 80% usage
2. **Test fallback chains regularly** - Use automated testing in staging
3. **Keep yt-dlp updated** - Schedule weekly updates
4. **Cache aggressively** - Reduce API calls where possible
5. **Document custom strategies** - Maintain clear documentation for custom implementations
6. **Monitor user experience** - Track fallback impact on response times
7. **Have manual overrides ready** - Prepare intervention procedures

## Conclusion

The YouTube fallback system provides robust protection against API quotas and service interruptions. By following this guide, you can ensure your bot maintains high availability even under challenging conditions. Regular monitoring and proactive management of the fallback system will provide the best user experience.

For additional support or questions, refer to the main project documentation or open an issue in the repository.