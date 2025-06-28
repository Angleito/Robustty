# VPS Health Monitor Improvements

## Overview

The health monitoring system has been enhanced with VPS-specific optimizations to better handle unstable network conditions and resource constraints commonly found on VPS deployments.

## Key Improvements

### 1. Environment Detection

The health monitor now automatically detects the deployment environment:
- **Local**: Development environment with fast, stable network
- **Docker**: Containerized environment (may be on VPS)
- **VPS**: Virtual Private Server with potentially unstable network

Detection is based on:
- Environment variables (`IS_VPS`, `DEPLOYMENT_TYPE`)
- Redis URL patterns (container networking)
- Hostname patterns
- Headless environment indicators

### 2. VPS-Specific Parameters

When VPS environment is detected:
- **Check Interval**: 60 seconds (vs 30s for local/Docker)
- **Max Consecutive Failures**: 5 (vs 3) - More tolerance before marking unhealthy
- **Timeout Multiplier**: 2x - All operations get double the timeout
- **Network Tolerance**: 3 network errors before marking unhealthy

### 3. Error Categorization

Errors are now categorized for better handling:
- **NETWORK**: Connection timeouts, refused connections, DNS failures
- **API**: Rate limits, authentication errors, forbidden access
- **TIMEOUT**: Async operation timeouts
- **UNKNOWN**: Other errors

### 4. Network Error Tolerance

For VPS environments:
- First few network errors result in DEGRADED status instead of UNHEALTHY
- Network error count is tracked per service
- Helps distinguish between transient network issues and actual service problems

### 5. Adaptive Failure Thresholds

- Recent network errors (within 5 minutes) grant +2 additional failures before triggering recovery
- Prevents aggressive recovery attempts during network instability
- Automatically resets when network stabilizes

### 6. Enhanced Recovery Delays

VPS environments get longer recovery delays:
- **Exponential Backoff Base**: 20s for VPS (vs 10s)
- **Linear Backoff Base**: 60s for VPS (vs 30s)
- All delays multiplied by timeout multiplier (2x on VPS)

Example recovery delays for VPS:
- Attempt 1: 40s
- Attempt 2: 80s
- Attempt 3: 160s
- Attempt 4: 320s
- Attempt 5: 600s (max)

## Configuration

### Environment Variables

```bash
# Force VPS environment detection
IS_VPS=true

# Or use deployment type
DEPLOYMENT_TYPE=vps

# Container networking also triggers VPS mode
REDIS_URL=redis://redis:6379
```

### Health Monitor Config

```yaml
health_monitor:
  check_interval: 60  # Override default (seconds)
  max_consecutive_failures: 5  # Override default
  recovery:
    exponential_backoff: true
    max_attempts: 5
    max_delay: 600  # 10 minutes
```

## Benefits

1. **Reduced False Positives**: Less likely to mark services unhealthy due to transient network issues
2. **Lower Resource Usage**: Less frequent health checks on resource-constrained VPS
3. **Better Recovery**: Smarter recovery timing prevents overwhelming unstable networks
4. **Improved Stability**: Distinguishes between network issues and actual service failures

## Monitoring

The health status endpoint now includes:
- Current environment
- Check interval
- Timeout multiplier
- Network error counts per service

Example response:
```json
{
  "overall_status": "healthy",
  "environment": "vps",
  "check_interval": 60,
  "timeout_multiplier": 2.0,
  "network_error_counts": {
    "platform_youtube": 1,
    "redis": 0
  },
  "services": {
    "discord_gateway": {
      "status": "healthy",
      "consecutive_failures": 0,
      "avg_response_time": 0.15
    }
  }
}
```

## Testing

Run the test script to verify VPS optimizations:
```bash
python3 test_vps_health_monitor.py
```

For production VPS:
```bash
# Set environment variable before starting bot
export IS_VPS=true
docker-compose up -d
```

## Troubleshooting

1. **Service marked unhealthy too quickly**: Check if VPS environment is detected correctly
2. **Recovery attempts too frequent**: Verify timeout multiplier is applied
3. **Network errors not tolerated**: Ensure error categorization is working correctly

Check logs for:
- "Health monitor initialized in vps environment"
- "Network error" categorization in error messages
- Extended threshold messages for recent network errors