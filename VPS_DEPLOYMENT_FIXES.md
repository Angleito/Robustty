# VPS Deployment Fixes Checklist

This document summarizes all fixes made to Robustty and provides step-by-step deployment instructions.

## Summary of Fixes Implemented

### 1. DNS Resolution & Network Connectivity
- [x] Fixed DNS resolution in Docker containers by adding Google DNS (8.8.8.8, 8.8.4.4)
- [x] Added network connectivity checks before platform operations
- [x] Implemented retry logic with exponential backoff for network failures
- [x] Enhanced error handling for DNS resolution failures

### 2. Platform-Specific Fixes

#### Odysee Platform
- [x] Fixed URL construction for Odysee API endpoints
- [x] Corrected video ID extraction from claim names
- [x] Added proper error handling for API responses
- [x] Fixed stream URL generation for direct playback

#### PeerTube Platform
- [x] Implemented instance discovery fallback mechanism
- [x] Fixed video search across multiple instances
- [x] Added proper video URL construction
- [x] Enhanced error handling for instance failures

#### All Platforms
- [x] Added DNS resolution checks before API calls
- [x] Implemented platform health monitoring
- [x] Enhanced logging for debugging network issues

### 3. Cookie Management Improvements
- [x] Standardized cookie paths across all components
- [x] Fixed cookie extraction for VPS environment
- [x] Added automatic cookie sync from macOS to VPS
- [x] Improved cookie format conversion (JSON to Netscape)

### 4. Voice Connection Enhancements
- [x] Added VPS-specific voice connection optimizations
- [x] Implemented environment detection (Local/Docker/VPS)
- [x] Extended timeouts and retry delays for VPS networks
- [x] Added circuit breaker pattern for connection failures
- [x] Enhanced session management for WebSocket errors

### 5. Docker Networking Fixes
- [x] Configured proper DNS settings in docker-compose.yml
- [x] Fixed container-to-container communication
- [x] Optimized Docker builds with .dockerignore
- [x] Separated macOS and VPS Docker configurations

## Pre-Deployment Checklist

### 1. Local Validation
```bash
# Run pre-deployment validation
cd /path/to/robustty
./scripts/validate-pre-deployment.sh

# Test specific platforms
pytest tests/test_platforms/test_odysee.py -v
pytest tests/test_platforms/test_peertube.py -v

# Test voice connection fixes
python test_voice_connection_fix.py vps
```

### 2. Prepare Files for Deployment
Ensure these files are up-to-date:
- [x] `docker-compose.yml` (with DNS configuration)
- [x] `Dockerfile` (with DNS fixes)
- [x] `src/platforms/odysee.py` (URL construction fixes)
- [x] `src/platforms/peertube.py` (instance discovery fixes)
- [x] `src/platforms/base.py` (DNS check implementation)
- [x] `src/services/voice_connection_manager.py` (VPS optimizations)
- [x] `src/utils/network_utils.py` (network utilities)
- [x] `.dockerignore` (build optimization)
- [x] All test files in `tests/test_platforms/`

## Deployment Steps

### 1. Connect to VPS
```bash
ssh ubuntu@<vps-ip>
```

### 2. Backup Current Deployment
```bash
cd ~/robustty-bot
# Create backup
tar -czf robustty-backup-$(date +%Y%m%d-%H%M%S).tar.gz .
# Save current .env
cp .env .env.backup
```

### 3. Update Code
```bash
# Pull latest changes
git pull origin main

# Or if using deployment script from local machine:
# ./deploy-vps-with-validation.sh <vps-ip> ubuntu full auto
```

### 4. Update Docker Configuration
```bash
# Ensure docker-compose.yml has DNS settings:
cat docker-compose.yml | grep -A2 "dns:"
# Should show:
#   dns:
#     - 8.8.8.8
#     - 8.8.4.4
```

### 5. Rebuild and Deploy
```bash
# Stop current services
docker-compose down

# Clean up old images (optional, but recommended)
docker system prune -f

# Build and start with new fixes
docker-compose up -d --build

# Monitor logs
docker-compose logs -f robustty
```

### 6. Verify DNS Resolution
```bash
# Test DNS inside container
docker-compose exec robustty nslookup google.com
docker-compose exec robustty ping -c 4 google.com

# Test platform connectivity
docker-compose exec robustty python -c "
from src.utils.network_utils import check_dns_resolution
print('DNS Check:', check_dns_resolution('api.odysee.tv'))
"
```

### 7. Test Platform Functionality
```bash
# Test each platform from Discord:
!search odysee bitcoin
!search peertube linux
!search youtube music
!search rumble news

# Check voice connection
!voicehealth
!voiceenv  # Should show "VPS" environment
```

### 8. Verify Cookie System (if using cookies)
```bash
# Check cookie directories
docker-compose exec robustty ls -la /app/cookies/
docker-compose exec robustty ls -la /app/data/cookies/

# Test cookie extraction (if needed)
docker-compose exec robustty python scripts/extract-brave-cookies.py
```

## Post-Deployment Verification

### 1. Run VPS Validation Scripts
```bash
cd ~/robustty-bot
./scripts/validate-vps-core.sh
./scripts/validate-vps-deployment.sh
```

### 2. Monitor Service Health
```bash
# Check container status
docker-compose ps

# Monitor resource usage
docker stats robustty redis

# Check logs for errors
docker-compose logs --tail=100 robustty | grep -i error
```

### 3. Test All Features
- [x] Search functionality on all platforms
- [x] Audio playback
- [x] Queue management
- [x] Voice connections (join/leave)
- [x] Skip, pause, resume commands

## Troubleshooting Common Issues

### DNS Resolution Failures
```bash
# If DNS still fails, check Docker daemon DNS
sudo cat /etc/docker/daemon.json
# Should contain: {"dns": ["8.8.8.8", "8.8.4.4"]}

# Restart Docker if needed
sudo systemctl restart docker
docker-compose up -d
```

### Platform Connection Issues
```bash
# Test specific platform connectivity
docker-compose exec robustty python -m pytest tests/test_platforms/test_odysee.py::test_dns_resolution -v

# Check network utilities
docker-compose exec robustty python -c "
from src.utils.network_utils import test_connectivity
test_connectivity()
"
```

### Voice Connection Problems
```bash
# Force VPS environment
!voiceenv vps

# Check voice diagnostics
!voicediag

# Reset voice connections
docker-compose restart robustty
```

### Cookie Issues
```bash
# Manual cookie sync from macOS
./scripts/sync-cookies-to-vps.sh

# Verify cookies in container
docker-compose exec robustty python -c "
from src.extractors.cookie_manager import CookieManager
cm = CookieManager()
print(cm.get_cookies_for_platform('youtube'))
"
```

### Container Build Failures
```bash
# Clean Docker system
docker system prune -a --volumes
docker-compose build --no-cache
docker-compose up -d
```

## Rollback Procedure

If issues occur after deployment:

```bash
# Stop new deployment
docker-compose down

# Restore backup
tar -xzf robustty-backup-[timestamp].tar.gz
cp .env.backup .env

# Rebuild with old code
docker-compose up -d --build
```

## Success Indicators

Your deployment is successful when:
- [x] All platforms return search results
- [x] Audio streams play without interruption
- [x] Voice connections are stable (check with !voicehealth)
- [x] No DNS resolution errors in logs
- [x] Container logs show "Platform initialized successfully" for all platforms
- [x] Network connectivity checks pass in container

## Additional Notes

1. **Environment Detection**: The bot automatically detects VPS environment, but you can force it with `!voiceenv vps`

2. **DNS Fallback**: If primary DNS fails, the system will try:
   - 8.8.8.8 (Google Primary)
   - 8.8.4.4 (Google Secondary)
   - 1.1.1.1 (Cloudflare)

3. **Platform Health**: The bot monitors platform health and will disable problematic platforms after repeated failures

4. **Cookie Sync**: If using cookies, set up automatic sync:
   ```bash
   # On macOS development machine
   ./setup-mac-cookie-cron.sh
   ```

5. **Monitoring**: Keep logs open during initial deployment:
   ```bash
   docker-compose logs -f robustty | grep -E "(ERROR|WARNING|DNS|Platform|Voice)"
   ```

## Quick Reference Commands

```bash
# Full deployment from local
./deploy-vps-with-validation.sh <vps-ip> ubuntu full auto

# Quick health check
ssh ubuntu@<vps-ip> 'cd ~/robustty-bot && docker-compose ps'

# View recent errors
ssh ubuntu@<vps-ip> 'cd ~/robustty-bot && docker-compose logs --tail=50 robustty | grep ERROR'

# Restart bot only
ssh ubuntu@<vps-ip> 'cd ~/robustty-bot && docker-compose restart robustty'

# Full restart
ssh ubuntu@<vps-ip> 'cd ~/robustty-bot && docker-compose down && docker-compose up -d'
```

---

Last Updated: 2025-01-28
Deployment Version: DNS & Network Fixes + Platform Improvements