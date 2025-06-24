# Cookie Synchronization Error Handling & Fallbacks

This document describes the comprehensive cookie error handling and fallback system implemented in Robustty for robust VPS deployments.

## Overview

The cookie error handling system ensures that Robustty continues operating even when cookie synchronization fails, providing graceful degradation and automatic recovery mechanisms.

## Architecture

### Core Components

1. **Cookie Health Monitor** (`src/services/cookie_health_monitor.py`)
   - Monitors cookie validity and freshness
   - Validates cookies with test requests
   - Tracks cookie age and expiration
   - Provides health status for all platforms

2. **Platform Fallback Manager** (`src/services/platform_fallback_manager.py`)
   - Manages fallback strategies for each platform
   - Activates/deactivates fallback modes
   - Provides platform-specific limitations and recommendations
   - Tracks fallback history and duration

3. **Cookie Sync Recovery** (`src/services/cookie_sync_recovery.py`)
   - Handles cookie synchronization failures
   - Implements multi-stage recovery strategies
   - Provides manual intervention mechanisms
   - Maintains sync attempt history

4. **Enhanced Cookie Managers** (`src/services/enhanced_cookie_manager.py`)
   - Robust error handling with retry logic
   - Atomic cookie file operations with backups
   - Cookie validation and filtering
   - Health-aware cookie retrieval

5. **Health Endpoints** (`src/services/health_endpoints.py`)
   - HTTP endpoints for monitoring cookie status
   - Real-time validation and refresh capabilities
   - External monitoring integration
   - CORS support for web dashboards

## Fallback Strategies

### YouTube Platform
- **API Only**: Use YouTube API without cookies (public content only)
- **Limited Search**: Basic search with reduced functionality
- **Disabled**: Platform completely disabled

### Rumble Platform
- **Public Only**: Access public content without authentication
- **Limited Search**: Basic public search functionality
- **Disabled**: Platform disabled

### Odysee Platform
- **Public Only**: Access public content without authentication
- **Disabled**: Platform disabled

### PeerTube Platform
- **Public Only**: Access public federated content
- **Disabled**: Platform disabled

## Error Recovery Mechanisms

### 1. Cookie Health Monitoring
- **Frequency**: Every 5 minutes (configurable)
- **Checks**: File age, cookie validity, test requests
- **Thresholds**: 12-hour max age, minimum cookie count
- **Actions**: Automatic fallback activation on health issues

### 2. Sync Failure Recovery
- **Detection**: Tracks consecutive sync failures
- **Threshold**: 3 consecutive failures trigger recovery
- **Strategies** (in order):
  1. Try alternative cookie sources
  2. Request manual intervention
  3. Activate emergency fallback
  4. Notify administrators

### 3. Platform-Specific Fallbacks
- **Activation**: Automatic on cookie or API failures
- **Modes**: Configurable per platform
- **Duration**: Max 24 hours before escalation
- **Deactivation**: Automatic when cookies are restored

## Configuration

### Basic Configuration (config.yaml)
```yaml
# Cookie Health Monitoring
cookies:
  enable_health_monitoring: true
  health_check_interval: 300  # 5 minutes
  cookie_max_age_hours: 12
  validation_timeout: 10

# Platform Fallbacks
fallbacks:
  enable_fallbacks: true
  max_fallback_duration_hours: 24
  retry_interval_minutes: 30

# Sync Recovery
cookie_sync:
  sync_check_interval_minutes: 15
  max_sync_failures: 3
  enable_auto_recovery: true

# Health Endpoints
health_endpoints:
  enabled: true
  port: 8080
  host: "0.0.0.0"
```

### Platform-Specific Fallback Configuration
```yaml
platforms:
  youtube:
    enable_fallbacks: true
    fallback_strategies:
      - mode: "api_only"
        priority: 1
      - mode: "limited_search"
        priority: 2
      - mode: "disabled"
        priority: 3
```

## Monitoring & Alerting

### Health Endpoints

| Endpoint | Description |
|----------|-------------|
| `/health` | Basic service health |
| `/health/cookies` | Cookie health for all platforms |
| `/health/cookies/{platform}` | Platform-specific cookie health |
| `/health/platforms` | Overall platform status |
| `/health/fallbacks` | Fallback system status |
| `/health/detailed` | Comprehensive health report |
| `/health/refresh/{platform}` | Force cookie refresh |
| `/health/validate` | Force validation |

### Example Health Response
```json
{
  "timestamp": "2025-01-25T12:00:00Z",
  "overall_health": {
    "healthy_count": 3,
    "total_count": 4,
    "unhealthy_platforms": ["rumble"],
    "refresh_needed": ["youtube"]
  },
  "platform_details": {
    "youtube": {
      "is_healthy": true,
      "cookie_count": 15,
      "age_hours": 8.5,
      "needs_refresh": true
    },
    "rumble": {
      "is_healthy": false,
      "validation_error": "Cookies too old (13.2 hours)"
    }
  }
}
```

## VPS Deployment Integration

### Validation Script (`scripts/vps_cookie_validation.py`)
```bash
# Basic validation
./scripts/vps_cookie_validation.py

# Continuous monitoring
./scripts/vps_cookie_validation.py --watch 300

# Exit with error codes for CI/CD
./scripts/vps_cookie_validation.py --exit-code

# Custom configuration
./scripts/vps_cookie_validation.py --config vps_config.json
```

### Deployment Script (`scripts/deploy_with_validation.sh`)
```bash
# Deploy with validation
./scripts/deploy_with_validation.sh

# Validation only
./scripts/deploy_with_validation.sh --validate-only

# Force deploy despite issues
./scripts/deploy_with_validation.sh --force

# Build and deploy
./scripts/deploy_with_validation.sh --build
```

## Error Scenarios & Responses

### Scenario 1: Cookie File Missing
- **Detection**: Health monitor checks file existence
- **Response**: Activate fallback mode for platform
- **Recovery**: Attempt cookie extraction/sync
- **Fallback**: API-only or public-only mode

### Scenario 2: Cookies Expired
- **Detection**: Health monitor validates cookie age
- **Response**: Mark platform for refresh
- **Recovery**: Attempt fresh cookie extraction
- **Fallback**: Use expired cookies with warnings

### Scenario 3: Cookie Validation Fails
- **Detection**: Test requests return 403/401
- **Response**: Immediate fallback activation
- **Recovery**: Try alternative cookie sources
- **Fallback**: Platform-specific limited mode

### Scenario 4: Sync System Failure
- **Detection**: Multiple consecutive sync failures
- **Response**: Multi-stage recovery process
- **Recovery**: Alternative sources → Manual → Emergency
- **Fallback**: All platforms in emergency mode

### Scenario 5: VPS Network Issues
- **Detection**: Health endpoint timeouts
- **Response**: Local validation continues
- **Recovery**: Retry with exponential backoff
- **Fallback**: Offline operation mode

## Best Practices

### Development Environment
1. Test cookie extraction regularly
2. Validate cookie format and content
3. Test platform fallback modes
4. Monitor health endpoints

### VPS Deployment
1. Always run pre-deployment validation
2. Monitor health endpoints continuously
3. Set up external alerting
4. Maintain backup cookie sources
5. Test recovery procedures

### Monitoring Setup
1. **External Health Checks**: Monitor `/health` endpoint
2. **Log Monitoring**: Watch for fallback activations
3. **Cookie Age Alerts**: Alert on stale cookies
4. **Sync Failure Alerts**: Alert on consecutive failures
5. **Platform Status**: Monitor fallback modes

## Troubleshooting

### Common Issues

#### Cookie Files Not Found
```bash
# Check cookie directory
ls -la /app/cookies/

# Run extraction manually
python scripts/extract-brave-cookies.py

# Check permissions
docker exec robustty ls -la /app/cookies/
```

#### Health Endpoint Not Responding
```bash
# Check container status
docker ps -f name=robustty

# Check port mapping
docker port robustty

# Test endpoint directly
curl http://localhost:8080/health
```

#### Platform in Permanent Fallback
```bash
# Check fallback status
curl http://localhost:8080/health/fallbacks

# Force cookie refresh
curl -X POST http://localhost:8080/health/refresh/youtube

# Check detailed status
curl http://localhost:8080/health/detailed
```

### Log Analysis

#### Cookie Health Issues
```bash
# Filter cookie health logs
docker logs robustty 2>&1 | grep "cookie.*health"

# Check validation errors
docker logs robustty 2>&1 | grep "validation.*failed"
```

#### Fallback Activations
```bash
# Find fallback activations
docker logs robustty 2>&1 | grep "fallback.*activated"

# Check recovery attempts
docker logs robustty 2>&1 | grep "recovery.*strategy"
```

## Recovery Procedures

### Manual Cookie Sync
1. Extract cookies from development environment
2. Copy to VPS cookie directory
3. Restart bot or trigger refresh
4. Validate with health endpoints

### Emergency Recovery
1. Activate all fallbacks: `POST /health/activate-emergency`
2. Check platform limitations
3. Notify users of reduced functionality
4. Work on cookie restoration

### System Reset
1. Stop bot container
2. Clear cookie directory
3. Fresh cookie extraction
4. Redeploy with validation

## Performance Impact

### Monitoring Overhead
- **Health Checks**: ~1% CPU overhead
- **Validation Requests**: ~2-5 seconds per platform
- **Memory Usage**: ~10MB additional for monitoring
- **Network**: Minimal for validation requests

### Fallback Performance
- **API-Only Mode**: 20-30% slower searches
- **Public-Only Mode**: 40-50% reduced functionality
- **Limited Search**: 60-70% reduced capabilities

## Security Considerations

### Cookie Security
- Store cookies in secure directories
- Use proper file permissions (600)
- Rotate cookies regularly
- Monitor for unauthorized access

### Health Endpoint Security
- Use CORS restrictions
- Implement rate limiting
- Consider authentication for sensitive endpoints
- Monitor access logs

## Future Enhancements

### Planned Features
1. **Machine Learning**: Predict cookie failures
2. **Advanced Sync**: Multi-source cookie merging
3. **Performance Metrics**: Detailed fallback analytics
4. **Auto-Recovery**: Smarter recovery strategies
5. **Dashboard**: Web-based monitoring interface

### Integration Opportunities
1. **Prometheus**: Enhanced metrics collection
2. **Grafana**: Visual monitoring dashboards
3. **PagerDuty**: Advanced alerting
4. **Kubernetes**: Health checks and probes
5. **CI/CD**: Automated validation in pipelines

## Support

For issues related to cookie synchronization and error handling:

1. Check health endpoints first
2. Review log files for errors
3. Run validation script manually
4. Test fallback modes
5. Consult this documentation

The system is designed to be self-healing and provide clear diagnostics for any issues that arise.