# YouTube Music Headless Service Troubleshooting Guide

## Overview

The YouTube Music headless service provides an API interface for searching and streaming music from YouTube. It runs as a separate Docker container and communicates with the main bot via HTTP.

## Common Connection Issues

### 1. Connection Reset by Peer

**Symptoms:**
- Error message: `ClientConnectorError: Cannot connect to host youtube-music-headless:9863 ssl:default [Connection reset by peer]`
- Bot falls back to regular YouTube platform
- Intermittent connectivity issues

**Causes:**
- Container not running or crashed
- Network configuration issues between containers
- Resource constraints (memory/CPU)
- DNS resolution problems in Docker network

**Solutions:**

1. **Check container status:**
```bash
docker ps | grep youtube-music
docker logs robustty-youtube-music --tail 50
```

2. **Restart the container:**
```bash
docker-compose restart youtube-music-headless
# Wait for health check
docker-compose ps
```

3. **Fix networking issues:**
```bash
# Run the fix script
./scripts/fix-youtube-music-connection.sh

# Or manually fix:
docker-compose down
docker network prune -f
docker-compose up -d
```

### 2. Service Not Starting

**Symptoms:**
- Container exits immediately after starting
- Health check fails continuously
- No logs from the container

**Solutions:**

1. **Check for port conflicts:**
```bash
# Check if port 9863 is already in use
sudo lsof -i :9863
# or
sudo netstat -tlnp | grep 9863
```

2. **Verify Docker resources:**
```bash
# Check available memory
free -h
# Check disk space
df -h
# Check Docker system resources
docker system df
```

3. **Clean up and rebuild:**
```bash
docker-compose down
docker system prune -a --volumes
docker-compose up -d --build youtube-music-headless
```

### 3. DNS Resolution Failures

**Symptoms:**
- Cannot resolve `youtube-music-headless` hostname
- Works with IP address but not hostname
- Intermittent resolution failures

**Solutions:**

1. **Verify Docker network configuration:**
```bash
# Inspect network
docker network inspect robustty_robustty-network

# Test DNS from bot container
docker exec robustty-bot nslookup youtube-music-headless
docker exec robustty-bot ping youtube-music-headless
```

2. **Add explicit container links:**
```bash
# Edit docker-compose.yml to add links
# Under robustty service:
links:
  - youtube-music-headless
```

3. **Use container IP directly (temporary fix):**
```bash
# Get container IP
docker inspect robustty-youtube-music | grep IPAddress

# Set environment variable
export YOUTUBE_MUSIC_API_URL=http://<container-ip>:9863
docker-compose up -d robustty
```

## Testing and Monitoring

### Quick Connectivity Test

Run the provided test script:
```bash
# From host
python3 scripts/test-youtube-music-vps.py

# From inside bot container
docker exec robustty-bot python3 scripts/test-youtube-music-vps.py
```

### Continuous Monitoring

Monitor the service health:
```bash
# Basic monitoring
python3 scripts/monitor-youtube-music.py

# With search tests
python3 scripts/monitor-youtube-music.py --include-search

# Quick test only
python3 scripts/monitor-youtube-music.py --quick-test
```

### Manual API Testing

Test the API endpoints directly:
```bash
# Health check
curl http://localhost:9863/api/health

# Search test
curl "http://localhost:9863/api/search?q=test&limit=1"

# From inside Docker network
docker exec robustty-bot curl http://youtube-music-headless:9863/api/health
```

## Configuration Options

### Environment Variables

```bash
# Enable/disable YouTube Music
YOUTUBE_MUSIC_ENABLED=true

# API URL configuration
YOUTUBE_MUSIC_API_URL=http://youtube-music-headless:9863

# Timeout settings
YOUTUBE_MUSIC_TIMEOUT=30
YOUTUBE_MUSIC_RETRY_ATTEMPTS=3
YOUTUBE_MUSIC_RETRY_DELAY=1
```

### Platform Priority

YouTube Music has the highest priority in the platform order:
1. `youtube_music_headless` (highest priority)
2. `youtube`
3. `odysee`
4. `peertube`
5. `rumble`

When YouTube Music fails, the bot automatically falls back to the regular YouTube platform.

### Stability Mode

If YouTube Music consistently fails, the stability monitor may automatically disable it:
- Failure threshold: 10 consecutive failures
- Recovery check: Every 3 minutes
- Re-enabled automatically when service recovers

## Fallback Behavior

When YouTube Music is unavailable:

1. **Automatic Fallback:** Bot seamlessly falls back to regular YouTube platform
2. **Cache Usage:** Previously cached results from YouTube Music are still served
3. **Status Indicators:** Users see fallback indicators if enabled (`SHOW_FALLBACK_INDICATORS=true`)
4. **Health Monitoring:** Service health is continuously monitored for automatic recovery

## VPS-Specific Considerations

### Resource Constraints

YouTube Music headless requires:
- Memory: ~512MB minimum
- CPU: Low usage, but benefits from dedicated core
- Disk: Minimal (~100MB for container + cache)

### Network Optimization

For VPS deployments:
```yaml
# docker-compose.yml optimizations
services:
  youtube-music-headless:
    # Resource limits
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
    
    # Network optimizations
    sysctls:
      - net.ipv4.tcp_keepalive_time=120
      - net.ipv4.tcp_keepalive_probes=3
      - net.ipv4.tcp_keepalive_intvl=30
```

### Firewall Considerations

Ensure internal Docker communication is allowed:
```bash
# Check UFW status
sudo ufw status

# Allow Docker internal communication (if needed)
sudo ufw allow from 172.16.0.0/12 to any port 9863
```

## Diagnostic Commands

### Container Health
```bash
# Full container inspection
docker inspect robustty-youtube-music

# Resource usage
docker stats robustty-youtube-music --no-stream

# Process list inside container
docker exec robustty-youtube-music ps aux
```

### Network Diagnostics
```bash
# Test connectivity between containers
docker exec robustty-bot ping -c 3 youtube-music-headless
docker exec robustty-bot nc -zv youtube-music-headless 9863

# Check routing
docker exec robustty-bot traceroute youtube-music-headless
```

### API Performance
```bash
# Measure response times
time docker exec robustty-bot curl -s http://youtube-music-headless:9863/api/health

# Load test (be careful on VPS)
for i in {1..10}; do 
  time curl -s http://localhost:9863/api/health > /dev/null
done
```

## Recovery Procedures

### Full Service Reset
```bash
# 1. Stop all services
docker-compose down

# 2. Clean up
docker system prune -f
docker volume prune -f

# 3. Rebuild and start
docker-compose up -d --build

# 4. Verify health
./scripts/test-youtube-music-vps.py
```

### Emergency Disable
If YouTube Music causes persistent issues:
```bash
# Disable via environment
export YOUTUBE_MUSIC_ENABLED=false
docker-compose up -d robustty

# Or remove from docker-compose.yml dependencies
# Edit docker-compose.yml and remove youtube-music-headless from depends_on
```

## Logs and Monitoring

### Important Log Locations
- Container logs: `docker logs robustty-youtube-music`
- Bot logs: `docker logs robustty-bot | grep -i "youtube.*music"`
- Health check logs: Check bot logs for platform health status

### Key Log Patterns to Watch
- `"YouTube Music headless service is ready"` - Service initialized successfully
- `"Connection reset by peer"` - Network connectivity issues
- `"health check failed"` - Service unhealthy
- `"platform disabled due to failures"` - Stability monitor disabled the platform

## Performance Optimization

### Caching
YouTube Music results are cached:
- Search results: 1 hour
- Stream URLs: 30 minutes
- Metadata: 2 hours

### Connection Pooling
The platform uses connection pooling for efficiency:
- Default pool size: 10 connections
- Keep-alive enabled
- Automatic connection recycling

### Request Optimization
- Concurrent request limit: 5
- Request timeout: 30 seconds
- Automatic retry with exponential backoff