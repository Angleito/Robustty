# Metrics Monitoring

Robustty includes comprehensive metrics collection for monitoring platform performance, API usage, and system health.

## Overview

The metrics system is built on Prometheus and provides real-time monitoring of:
- API call rates and response times
- Cache performance
- Error rates and types
- Rate limit encounters
- Queue sizes and active connections

## Metrics Endpoint

The metrics server exposes the following endpoints:

- **Prometheus Metrics**: `http://localhost:8080/metrics`
- **Health Check**: `http://localhost:8080/health`

## Available Metrics

### API Metrics

**rumble_api_calls_total**
- Type: Counter
- Labels: `endpoint`, `status`
- Description: Total number of API calls made to the Apify API
- Endpoints: `search`, `metadata`, `stream`
- Status: `success`, `error`

**rumble_api_response_time_seconds**
- Type: Histogram
- Labels: `endpoint`
- Description: API response time in seconds
- Buckets: 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0

### Cache Metrics

**rumble_cache_hits_total**
- Type: Counter
- Labels: `cache_type`
- Description: Total number of cache hits
- Cache types: `metadata`, `stream`

**rumble_cache_misses_total**
- Type: Counter
- Labels: `cache_type`
- Description: Total number of cache misses

### Error Metrics

**rumble_errors_total**
- Type: Counter
- Labels: `error_type`
- Description: Total number of errors by type
- Common types: `PlatformAPIError`, `PlatformRateLimitError`, `PlatformAuthenticationError`

**rumble_rate_limits_total**
- Type: Counter
- Description: Total number of rate limit encounters

### System Metrics

**rumble_queue_size**
- Type: Gauge
- Description: Current size of the music queue

**rumble_active_connections**
- Type: Gauge
- Description: Number of active voice connections

## Configuration

### Enabling Metrics Server

The metrics server is automatically started when the bot starts. Configuration is done in the main bot file:

```python
# In src/main.py
from src.services.metrics_server import MetricsServer

# Start metrics server
metrics_server = MetricsServer(host="0.0.0.0", port=8080)
await metrics_server.start()
```

### Docker Configuration

If running in Docker, expose the metrics port:

```yaml
# docker-compose.yml
services:
  bot:
    ports:
      - "8080:8080"  # Metrics port
```

## Dashboard Configuration

A Grafana dashboard configuration is provided in `config/metrics_dashboard.json`. Import this into Grafana for pre-configured visualizations.

### Key Dashboard Panels

1. **API Call Rate**: Real-time requests per second by endpoint
2. **API Response Times**: 95th and 50th percentile response times
3. **Cache Hit Ratio**: Cache effectiveness by type
4. **Error Rate**: Errors per second by type
5. **Rate Limit Encounters**: Hourly rate limit hit count
6. **API Success Rate**: Percentage of successful API calls
7. **Queue Size**: Current music queue size with sparkline
8. **Active Connections**: Current voice connections with sparkline

## Alerts

The system includes pre-configured alerts for:

### High API Error Rate
- Condition: Error rate > 0.1 errors/s for 5 minutes
- Severity: Warning

### Rate Limit Critical
- Condition: Rate limit encounters > 10/hour for 5 minutes
- Severity: Critical

### Slow API Response
- Condition: 95th percentile response time > 5s for 10 minutes
- Severity: Warning

### Low Cache Hit Rate
- Condition: Cache hit rate < 50% for 15 minutes
- Severity: Info

## Integration Examples

### Using Metrics in Code

```python
from src.services.metrics_collector import get_metrics_collector

# Get the global metrics collector
metrics = get_metrics_collector()

# Record an API call
with metrics.api_call_timer("search"):
    result = await api_client.search(query)

# Record cache hit/miss
if cached_data:
    metrics.record_cache_hit("metadata")
else:
    metrics.record_cache_miss("metadata")

# Record rate limit
if response.status == 429:
    metrics.record_rate_limit()

# Record error
metrics.record_error("PlatformAPIError")

# Update gauges
metrics.set_queue_size(len(queue))
metrics.set_active_connections(len(voice_clients))
```

### Prometheus Query Examples

```promql
# API call rate by endpoint
rate(rumble_api_calls_total[5m])

# 95th percentile response time
histogram_quantile(0.95, rate(rumble_api_response_time_seconds_bucket[5m]))

# Cache hit ratio
rate(rumble_cache_hits_total[5m]) / (rate(rumble_cache_hits_total[5m]) + rate(rumble_cache_misses_total[5m]))

# Error rate
rate(rumble_errors_total[5m])

# Rate limits per hour
rate(rumble_rate_limits_total[1h]) * 3600
```

## Best Practices

1. **Regular Monitoring**: Check dashboards regularly for anomalies
2. **Alert Tuning**: Adjust alert thresholds based on normal patterns
3. **Capacity Planning**: Use metrics to plan for scale
4. **Performance Optimization**: Identify bottlenecks using response time metrics
5. **Cache Tuning**: Optimize cache settings based on hit rates

## Troubleshooting

### No Metrics Available
- Verify metrics server is running: `curl http://localhost:8080/metrics`
- Check logs for errors
- Ensure port 8080 is not blocked

### Missing Metrics
- Verify the platform is properly initialized
- Check that metrics collector is imported
- Ensure API calls are wrapped with metrics collection

### High Memory Usage
- Metrics are stored in memory
- Prometheus scraping interval affects memory usage
- Consider adjusting retention settings

## Security Considerations

1. **Access Control**: Restrict metrics endpoint access in production
2. **Sensitive Data**: Metrics don't include sensitive information
3. **Rate Limiting**: Monitor metrics endpoint for abuse
4. **Network Security**: Use firewall rules to limit access

## Future Enhancements

- Support for additional metrics backends (StatsD, InfluxDB)
- Custom business metrics
- Distributed tracing integration
- Advanced anomaly detection
- Machine learning-based alerting