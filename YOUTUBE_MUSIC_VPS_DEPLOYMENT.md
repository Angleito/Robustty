# YouTube Music Headless VPS Deployment Guide

This guide will help you deploy the YouTube Music headless integration on your Digital Ocean VPS.

## Prerequisites

- VPS with Docker and Docker Compose installed
- Your Discord bot already deployed on the VPS
- SSH access to your VPS

## Step 1: Pull Latest Changes

SSH into your VPS and navigate to your bot directory:

```bash
ssh user@your-vps-ip
cd ~/robustty-bot  # or wherever your bot is deployed
```

Pull the latest changes:

```bash
git pull origin main
```

## Step 2: Update Environment Variables

Edit your `.env` file to enable YouTube Music:

```bash
nano .env
```

Add or update these variables:

```env
# YouTube Music Configuration
YOUTUBE_MUSIC_ENABLED=true
YOUTUBE_MUSIC_API_URL=http://youtube-music-headless:9863
YOUTUBE_MUSIC_TIMEOUT=30
YOUTUBE_MUSIC_RETRY_ATTEMPTS=3
YOUTUBE_MUSIC_RETRY_DELAY=1
YOUTUBE_MUSIC_MAX_RESULTS=10
```

## Step 3: Stop Current Services

Stop the running containers:

```bash
docker-compose down
```

## Step 4: Build and Start Services

Build the new YouTube Music container and start all services:

```bash
# Build images (required for YouTube Music container)
docker-compose build

# Start all services
docker-compose up -d
```

## Step 5: Verify Deployment

Wait about 60 seconds for services to start, then verify:

```bash
# Check if all containers are running
docker-compose ps

# Check YouTube Music container health
docker-compose exec youtube-music-headless curl http://localhost:9863/api/health

# Check bot health with YouTube Music integration
curl http://localhost:8080/health/youtube-music

# View logs
docker-compose logs -f youtube-music-headless
```

## Step 6: Cookie Synchronization (Optional but Recommended)

For authenticated YouTube Music access, sync cookies from your local machine:

### On your local macOS machine:

```bash
# Extract cookies
cd ~/Projects/Robustty
python scripts/extract-brave-cookies.py

# Sync to VPS (replace with your VPS details)
scp cookies/youtube_music_cookies.json user@your-vps-ip:~/robustty-bot/cookies/
```

### On your VPS:

```bash
# Restart YouTube Music container to load cookies
docker-compose restart youtube-music-headless

# Check if authenticated
curl http://localhost:8080/health/youtube-music | jq '.authentication'
```

## Step 7: Run Integration Tests

Test the complete deployment:

```bash
# Make test script executable
chmod +x scripts/test-youtube-music-deployment.sh

# Run deployment tests
./scripts/test-youtube-music-deployment.sh

# Run Python integration tests
python3 tests/test_youtube_music_integration.py
```

## Step 8: Monitor Services

Monitor the services to ensure everything is working:

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f youtube-music-headless
docker-compose logs -f robustty

# Check resource usage
docker stats
```

## Troubleshooting

### YouTube Music container won't start

```bash
# Check container logs
docker-compose logs youtube-music-headless

# Check if port 9863 is available
sudo netstat -tlnp | grep 9863

# Rebuild container
docker-compose build --no-cache youtube-music-headless
docker-compose up -d
```

### API not responding

```bash
# Check if Xvfb is running inside container
docker-compose exec youtube-music-headless ps aux | grep Xvfb

# Check YouTube Music process
docker-compose exec youtube-music-headless ps aux | grep youtube-music

# Restart container
docker-compose restart youtube-music-headless
```

### Authentication issues

```bash
# Check cookie files
ls -la cookies/

# Re-extract and sync cookies from local machine
# Then restart YouTube Music container
docker-compose restart youtube-music-headless
```

### Memory issues on VPS

If your VPS has limited memory, you can optimize:

```bash
# Add memory limits to docker-compose.yml
nano docker-compose.yml
```

Add under youtube-music-headless service:
```yaml
    mem_limit: 512m
    memswap_limit: 1g
```

## Quick Deployment Script

Create a quick deployment script on your VPS:

```bash
cat > deploy-youtube-music.sh << 'EOF'
#!/bin/bash
set -e

echo "🎵 Deploying YouTube Music Headless Integration..."

# Pull latest changes
git pull origin main

# Stop services
docker-compose down

# Build and start services
docker-compose build
docker-compose up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 60

# Check health
echo "🔍 Checking service health..."
docker-compose ps
curl -s http://localhost:8080/health/youtube-music | jq '.'

echo "✅ Deployment complete!"
echo "📊 View logs: docker-compose logs -f"
EOF

chmod +x deploy-youtube-music.sh
```

Then run:
```bash
./deploy-youtube-music.sh
```

## Monitoring Commands

```bash
# Check YouTube Music health endpoint
curl http://localhost:8080/health/youtube-music | jq '.'

# Check platform priorities
curl http://localhost:8080/health/platforms | jq '.platforms | keys'

# Check if YouTube Music is being used for searches
docker-compose logs robustty | grep -i "youtube_music_headless"

# Monitor resource usage
docker stats robustty-youtube-music
```

## Success Indicators

You'll know the deployment is successful when:

1. ✅ All containers show as "Up" in `docker-compose ps`
2. ✅ YouTube Music container passes health checks
3. ✅ `/health/youtube-music` endpoint shows `"overall_status": "healthy_authenticated"` (or at least "healthy_unauthenticated")
4. ✅ Bot logs show "YouTube Music headless service is ready"
5. ✅ Platform list shows `youtube_music_headless` as first priority

## Next Steps

1. Test in Discord by playing music - it should prioritize YouTube Music
2. Monitor logs to see YouTube Music being used for searches
3. Set up automatic cookie sync if needed (using cron job)
4. Configure monitoring alerts for service health

## Need Help?

- Check logs: `docker-compose logs -f`
- Run diagnostics: `./scripts/test-youtube-music-deployment.sh`
- Check VPS network: `python3 scripts/diagnose-vps-network.py`