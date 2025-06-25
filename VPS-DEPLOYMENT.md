# VPS Deployment Guide

This guide explains how to deploy Robustty on Ubuntu VPS, highlighting the differences from local development.

## Quick Start for Ubuntu VPS

### 1. Environment Setup
```bash
# Copy VPS-specific environment template
cp .env.vps.example .env

# Edit with your credentials
nano .env
```

### 2. Deploy with VPS-optimized compose file
```bash
# Use the VPS-specific compose file (recommended)
docker-compose -f docker-compose.vps.yml up -d

# OR use the main compose file (now VPS-compatible)
docker-compose up -d
```

## Key Differences: Local vs VPS

### Docker Compose Configuration

| Feature | Local (macOS/OrbStack) | VPS (Ubuntu) |
|---------|------------------------|--------------|
| **Networking** | `network_mode: host` | Bridge network with exposed ports |
| **Cookie Source** | Local Brave browser mount | Remote cookie sync or manual placement |
| **Redis** | External or host network | Containerized Redis service |
| **DNS** | System default | Explicit DNS servers (8.8.8.8, 1.1.1.1) |

### Cookie Management

#### Local Development (macOS)
- Mounts `~/Library/Application Support/BraveSoftware/Brave-Browser`
- Automatic cookie extraction via cron
- Uses `Dockerfile` with cookie extraction setup

#### VPS Deployment (Ubuntu)
- No local browser data available
- Uses `docker-compose.vps.yml` with `Dockerfile.vps`
- Cookies must be synced from external source
- Environment variable `COOKIE_SOURCE=remote`

### Network Configuration

#### Local (OrbStack Optimized)
```yaml
network_mode: host  # Direct host networking
environment:
  - REDIS_URL=redis://localhost:6379
```

#### VPS (Bridge Network)
```yaml
networks:
  - robustty-network
ports:
  - "8080:8080"
  - "6379:6379"
environment:
  - REDIS_URL=redis://redis:6379
```

## Environment Variables

### Core Variables (Both Platforms)
```bash
DISCORD_TOKEN=your_discord_bot_token
YOUTUBE_API_KEY=your_youtube_api_key
APIFY_API_KEY=your_apify_api_key
```

### Platform-Specific Variables

#### Local Development
```bash
BRAVE_BROWSER_PATH="${HOME}/Library/Application Support/BraveSoftware/Brave-Browser"
REDIS_URL=redis://localhost:6379
```

#### VPS Deployment
```bash
BRAVE_BROWSER_PATH=./empty-cookies  # Fallback path
REDIS_URL=redis://redis:6379        # Container network
COOKIE_SOURCE=remote                # Use external cookies
```

## Cookie Synchronization for VPS

Since VPS doesn't have local browser data, cookies must be provided externally:

### Option 1: Manual Cookie Placement
```bash
# Place cookies in the ./cookies/ directory before starting
mkdir -p ./cookies
# Copy your cookie files here
```

### Option 2: Automated Sync (from macOS development machine)
```bash
# Set in .env file
AUTO_SYNC_VPS=true
VPS_HOST=your-vps-ip
VPS_USER=ubuntu
VPS_PATH=~/robustty-bot/cookies
SSH_KEY_PATH=~/.ssh/your-key

# Run cookie extractor with sync
python scripts/extract-brave-cookies.py
```

## Deployment Commands

### VPS-Specific Deployment
```bash
# Use VPS-optimized configuration
docker-compose -f docker-compose.vps.yml up -d

# View logs
docker-compose -f docker-compose.vps.yml logs -f

# Health check
curl http://localhost:8080/health
```

### Universal Deployment (works on both platforms)
```bash
# The main docker-compose.yml now works on both platforms
docker-compose up -d

# Platform detection is automatic via environment variables
```

## Troubleshooting VPS Issues

### Common Problems and Solutions

1. **Redis Connection Errors**
   ```bash
   # Ensure Redis is running
   docker-compose logs redis
   
   # Check network connectivity
   docker-compose exec robustty ping redis
   ```

2. **Missing Cookies**
   ```bash
   # Check cookie directory
   docker-compose exec robustty ls -la /app/cookies/
   
   # Verify cookie format
   docker-compose exec robustty head /app/cookies/youtube.txt
   ```

3. **Network Issues**
   ```bash
   # Check exposed ports
   docker-compose ps
   
   # Test health endpoint
   curl -v http://localhost:8080/health
   ```

4. **DNS Resolution Problems**
   ```bash
   # The VPS compose file includes explicit DNS servers
   # Check if they're working:
   docker-compose exec robustty nslookup google.com
   ```

## Performance Optimization for VPS

The VPS configuration includes several optimizations:

- **Resource Limits**: Increased ulimits for file descriptors and processes
- **Network Tuning**: Optimized TCP settings and connection limits
- **Redis Optimization**: LRU eviction and persistent storage
- **Health Checks**: Comprehensive health monitoring
- **DNS Configuration**: Fast, reliable DNS resolution

## Migration from Local to VPS

1. **Export Cookies** (run on local machine):
   ```bash
   python scripts/extract-brave-cookies.py
   tar -czf cookies.tar.gz cookies/
   ```

2. **Transfer to VPS**:
   ```bash
   scp cookies.tar.gz user@vps:~/robustty-bot/
   ssh user@vps 'cd ~/robustty-bot && tar -xzf cookies.tar.gz'
   ```

3. **Deploy on VPS**:
   ```bash
   # On VPS
   cp .env.vps.example .env
   # Edit .env with your credentials
   docker-compose -f docker-compose.vps.yml up -d
   ```

## Monitoring and Maintenance

### Health Checks
- Bot health: `http://vps-ip:8080/health`
- Redis health: `docker-compose exec redis redis-cli ping`

### Log Monitoring
```bash
# Real-time logs
docker-compose logs -f robustty

# Search for errors
docker-compose logs robustty | grep ERROR
```

### Resource Usage
```bash
# Container stats
docker stats

# Disk usage
docker system df
```