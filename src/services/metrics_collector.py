"""
Metrics collector for monitoring Apify API usage and system performance.
"""

import time
import asyncio
from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from functools import wraps

# Define metrics
# API call counter - tracks total API calls per endpoint and status
api_calls_total = Counter(
    'rumble_api_calls_total',
    'Total number of API calls made',
    ['endpoint', 'status']
)

# API response time histogram - tracks response times per endpoint
api_response_time = Histogram(
    'rumble_api_response_time_seconds',
    'API response time in seconds',
    ['endpoint'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Cache hits counter - tracks cache hits by cache type
cache_hits_total = Counter(
    'rumble_cache_hits_total',
    'Total number of cache hits',
    ['cache_type']
)

# Cache misses counter - tracks cache misses by cache type
cache_misses_total = Counter(
    'rumble_cache_misses_total', 
    'Total number of cache misses',
    ['cache_type']
)

# Rate limit counter - tracks rate limit encounters
rate_limits_total = Counter(
    'rumble_rate_limits_total',
    'Total number of rate limit encounters',
    []
)

# Error counter - tracks errors by type
errors_total = Counter(
    'rumble_errors_total',
    'Total number of errors',
    ['error_type']
)

# Current queue size gauge
queue_size = Gauge(
    'rumble_queue_size',
    'Current size of the music queue'
)

# Active connections gauge
active_connections = Gauge(
    'rumble_active_connections',
    'Number of active voice connections'
)


class MetricsCollector:
    """Centralized metrics collection for the Rumble platform."""
    
    def __init__(self):
        self._start_time = time.time()
        
    def record_api_call(self, endpoint: str, status: str):
        """Record an API call with endpoint and status."""
        api_calls_total.labels(endpoint=endpoint, status=status).inc()
        
    def record_api_response_time(self, endpoint: str, duration: float):
        """Record API response time."""
        api_response_time.labels(endpoint=endpoint).observe(duration)
        
    def record_cache_hit(self, cache_type: str):
        """Record a cache hit."""
        cache_hits_total.labels(cache_type=cache_type).inc()
        
    def record_cache_miss(self, cache_type: str):
        """Record a cache miss."""
        cache_misses_total.labels(cache_type=cache_type).inc()
        
    def record_rate_limit(self):
        """Record a rate limit encounter."""
        rate_limits_total.inc()
        
    def record_error(self, error_type: str):
        """Record an error occurrence."""
        errors_total.labels(error_type=error_type).inc()
        
    def set_queue_size(self, size: int):
        """Set the current queue size."""
        queue_size.set(size)
        
    def set_active_connections(self, count: int):
        """Set the number of active connections."""
        active_connections.set(count)
        
    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format."""
        return generate_latest()
        
    def api_call_timer(self, endpoint: str):
        """Context manager for timing API calls."""
        class Timer:
            def __init__(self, collector, endpoint):
                self.collector = collector
                self.endpoint = endpoint
                self.start_time = None
                
            def __enter__(self):
                self.start_time = time.time()
                return self
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                self.collector.record_api_response_time(self.endpoint, duration)
                
                # Record the call status
                if exc_type is None:
                    self.collector.record_api_call(self.endpoint, 'success')
                else:
                    self.collector.record_api_call(self.endpoint, 'error')
                    # Also record the specific error type
                    error_type = exc_type.__name__ if exc_type else 'unknown'
                    self.collector.record_error(error_type)
                    
        return Timer(self, endpoint)
    
    def async_api_call_timer(self, endpoint: str):
        """Decorator for timing async API calls."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    self.record_api_response_time(endpoint, duration)
                    self.record_api_call(endpoint, 'success')
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self.record_api_response_time(endpoint, duration)
                    self.record_api_call(endpoint, 'error')
                    self.record_error(type(e).__name__)
                    raise
            return wrapper
        return decorator
    
    def track_cache(self, cache_type: str):
        """Decorator for tracking cache hits/misses."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                if result is not None:
                    self.record_cache_hit(cache_type)
                else:
                    self.record_cache_miss(cache_type)
                return result
            return wrapper
        return decorator


# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector