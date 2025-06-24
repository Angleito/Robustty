# Health Monitoring and Check Endpoints

This document describes the comprehensive health monitoring system implemented for Robustty, including all available health check endpoints, monitoring integration, and deployment validation.

## Overview

The enhanced health monitoring system provides:

- **Dependency-free basic health checks** for reliable Docker health checks
- **Detailed component status reporting** with hierarchical health status
- **Platform-specific health validation** including cookie status checks
- **Performance metrics and thresholds** for monitoring system health
- **Kubernetes-style readiness and liveness probes** for container orchestration
- **Security health checks** for compliance and audit requirements
- **Comprehensive monitoring integration** with Prometheus, Grafana, and alerting

## Health Check Endpoints

All health check endpoints are available on port 8080 (configurable via `METRICS_PORT` environment variable).

### Basic Health Endpoints

#### `/health` - Basic Health Status
**Dependency-free health check suitable for Docker health checks.**

```bash
curl http://localhost:8080/health
```

**Response:**
```json
{
  "status": "healthy",
  "message": "Service operational",
  "uptime": 300.5,
  "timestamp": "2024-01-25T10:30:00Z",
  "memory_percent": 45.2
}
```

**Status Values:**
- `healthy` - Service is fully operational
- `degraded` - Service operational but with warnings
- `starting` - Service is starting up (first 30 seconds)
- `error` - Health check failed

#### `/ready` - Readiness Probe
**Kubernetes-style readiness probe - determines if service can receive traffic.**

```bash
curl http://localhost:8080/ready
```

**Response:**
```json
{
  "ready": true,
  "timestamp": "2024-01-25T10:30:00Z",
  "checks": {
    "bot": {"ready": true},
    "memory": {"ready": true, "usage_percent": 45.2},
    "platforms": {"ready": true, "enabled_count": 3}
  }
}
```

**HTTP Status Codes:**
- `200` - Service is ready
- `503` - Service is not ready

#### `/live` - Liveness Probe
**Kubernetes-style liveness probe - determines if service should be restarted.**

```bash
curl http://localhost:8080/live
```

**Response:**
```json
{
  "alive": true,
  "timestamp": "2024-01-25T10:30:00Z",
  "checks": {
    "uptime": {"seconds": 300.5, "healthy": true},
    "memory": {"alive": true, "usage_percent": 45.2},
    "async": {"alive": true, "current_task": "Task-1"}
  }
}
```

### Detailed Health Endpoints

#### `/health/detailed` - Comprehensive Health Status
**Complete system health with all component details.**

```bash
curl http://localhost:8080/health/detailed
```

**Response:**
```json
{
  "overall_status": "healthy",
  "timestamp": "2024-01-25T10:30:00Z",
  "uptime": 300.5,
  "components": {
    "system": {
      "status": "healthy",
      "message": "System resources normal",
      "metrics": {
        "memory_percent": 45.2,
        "cpu_percent": 25.0,
        "disk_percent": 30.0,
        "load_average": [0.5, 0.3, 0.2]
      }
    },
    "discord": {
      "status": "healthy",
      "message": "Discord connection operational",
      "metrics": {
        "latency": 0.123,
        "guild_count": 5,
        "active_voice_connections": 2
      }
    },
    "platforms": {
      "status": "healthy",
      "message": "All platforms operational",
      "platforms": {
        "youtube": {"status": "healthy", "enabled": true},
        "peertube": {"status": "healthy", "enabled": true}
      }
    }
  }
}
```

#### `/health/discord` - Discord Health
**Discord-specific connectivity and functionality checks.**

```bash
curl http://localhost:8080/health/discord
```

#### `/health/platforms` - Platform Health
**Platform API connectivity and cookie status.**

```bash
curl http://localhost:8080/health/platforms
```

#### `/health/performance` - Performance Metrics
**Performance metrics and threshold analysis.**

```bash
curl http://localhost:8080/health/performance
```

#### `/health/infrastructure` - Infrastructure Health
**Redis, filesystem, and other infrastructure components.**

```bash
curl http://localhost:8080/health/infrastructure
```

#### `/health/security` - Security Health
**Security compliance and configuration checks.**

```bash
curl http://localhost:8080/health/security
```

### System Information Endpoints

#### `/info/system` - System Information
**Basic system and runtime information.**

#### `/info/runtime` - Runtime Information
**Application runtime configuration and environment.**

### Metrics Endpoint

#### `/metrics` - Prometheus Metrics
**Prometheus-compatible metrics for monitoring integration.**

## Health Status Hierarchy

The health monitoring system uses a hierarchical status model:

1. **healthy** - All systems operational
2. **degraded** - Some warnings but service functional
3. **starting** - Service initializing (temporary state)
4. **unhealthy** - Service has issues but responding
5. **error** - Health check failed completely

Overall status is determined by the worst component status, with specific rules for different severity levels.

## Monitoring Integration

### Docker Health Checks

Both `docker-compose.yml` and `docker-compose.vps.yml` use the dependency-free health check script:

```yaml
healthcheck:
  test: ["CMD", "python3", "/app/scripts/health-check.py", "basic"]
  interval: 30s
  timeout: 15s
  retries: 3
  start_period: 60s
```

### Kubernetes Integration

The provided `k8s/robustty-deployment.yaml` includes:

- **Startup Probe**: `/health` endpoint with 2-minute timeout
- **Readiness Probe**: `/ready` endpoint every 10 seconds
- **Liveness Probe**: `/live` endpoint every 30 seconds

### Prometheus Monitoring

Health metrics are automatically exported to Prometheus:

- `robustty_connection_status{service}` - Connection status by service
- `robustty_health_check_duration_seconds{service}` - Health check response times
- `robustty_connection_failures_total{service,error_type}` - Connection failure counts
- `robustty_consecutive_failures{service}` - Consecutive failure counts

### Grafana Dashboard

A comprehensive Grafana dashboard is provided in `monitoring/health-dashboard.json` with:

- Overall health status visualization
- System resource monitoring
- Discord connection health
- Platform status overview
- Performance metrics
- Recovery attempt tracking

## Deployment Validation

### Automated Validation Script

Use the deployment validation script to verify deployment health:

```bash
# Basic validation
./scripts/validate-deployment.py

# Wait for service and validate
./scripts/validate-deployment.py --wait --url http://localhost:8080

# JSON output for automation
./scripts/validate-deployment.py --output json

# Validate remote deployment
./scripts/validate-deployment.py --url https://robustty.example.com
```

**Exit Codes:**
- `0` - All checks passed (healthy)
- `1` - Some warnings (degraded)
- `2` - Validation failed (unhealthy)
- `3` - Unexpected error

### Manual Health Check Script

For Docker health checks and manual validation:

```bash
# Basic health check
./scripts/health-check.py basic

# Readiness check
./scripts/health-check.py ready

# Liveness check
./scripts/health-check.py live
```

## Configuration

### Health Monitoring Configuration

The `config/health-monitoring.yaml` file provides comprehensive configuration for:

- Health check thresholds for memory, CPU, disk, and latency
- Component-specific health check settings
- Monitoring integration configuration
- Alerting rules and auto-recovery settings
- VPS deployment specific settings

### Environment Variables

Health monitoring respects these environment variables:

- `METRICS_PORT` - Port for health and metrics endpoints (default: 8080)
- `HEALTH_MONITOR_ENABLED` - Enable/disable health monitoring (default: true)
- `HEALTH_CHECK_INTERVAL` - Health check interval in seconds (default: 30)
- `MAX_CONSECUTIVE_FAILURES` - Max failures before recovery (default: 3)

## VPS Deployment Considerations

For VPS deployments, the health monitoring system includes:

- **Enhanced connectivity checks** for Discord gateways and external APIs
- **Resource monitoring** with VPS-specific limits
- **Network resilience** with failover and retry logic
- **Dependency-free health checks** that work without external libraries

## Alerting and Recovery

### Prometheus Alerting Rules

The Kubernetes deployment includes Prometheus alerting rules for:

- Service down alerts
- High memory usage warnings
- Discord connection loss alerts
- High latency warnings

### Auto-Recovery

The health monitor includes automatic recovery for:

- Discord gateway disconnections
- Redis connection failures
- Platform API issues
- Voice connection problems

## Best Practices

1. **Use `/ready` for load balancer health checks** - more strict than basic health
2. **Use `/live` for container restart decisions** - more lenient to avoid unnecessary restarts
3. **Monitor `/health/detailed` for operational insights** - comprehensive status information
4. **Set up alerting on Prometheus metrics** - proactive issue detection
5. **Validate deployments with the validation script** - ensure deployment success
6. **Review security health regularly** - maintain security compliance

## Troubleshooting

### Common Issues

1. **Health checks timing out**:
   - Check if service is starting (startup probe allows 2 minutes)
   - Verify network connectivity to health endpoints
   - Review logs for initialization issues

2. **Readiness probe failing**:
   - Check Discord connection status
   - Verify platform initialization
   - Review memory usage (fails if >95%)

3. **Security health warnings**:
   - Review file permissions on sensitive directories
   - Check environment variable configuration
   - Verify process security settings

### Debug Commands

```bash
# Check specific component health
curl http://localhost:8080/health/discord
curl http://localhost:8080/health/platforms
curl http://localhost:8080/health/infrastructure

# Get detailed system information
curl http://localhost:8080/info/system
curl http://localhost:8080/info/runtime

# View Prometheus metrics
curl http://localhost:8080/metrics | grep robustty
```

## Migration from Legacy Health Checks

The enhanced health monitoring system is backward compatible with existing health checks. The legacy `/health` endpoint now provides more detailed information while maintaining the same basic interface.

To migrate:

1. Update Docker health checks to use the new script (already done in provided configs)
2. Configure Kubernetes probes to use `/ready` and `/live` endpoints
3. Set up Prometheus monitoring with the provided metrics
4. Deploy the Grafana dashboard for visualization
5. Configure alerting rules for proactive monitoring