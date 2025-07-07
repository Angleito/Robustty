#!/bin/bash

# Quick YouTube Music VPS Deployment Script
# Run this on your VPS to deploy the YouTube Music integration

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🎵 YouTube Music Headless VPS Deployment${NC}"
echo "========================================"
echo ""

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Error: docker-compose.yml not found!${NC}"
    echo "Please run this script from your Robustty bot directory"
    exit 1
fi

# Step 1: Pull latest changes
echo -e "${YELLOW}📥 Pulling latest changes...${NC}"
git pull origin main || {
    echo -e "${RED}❌ Failed to pull changes. Please commit or stash local changes first.${NC}"
    exit 1
}

# Step 2: Check environment variables
echo -e "${YELLOW}🔧 Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found! Creating from example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Please edit .env file with your credentials${NC}"
    exit 1
fi

# Add YouTube Music variables if not present
if ! grep -q "YOUTUBE_MUSIC_ENABLED" .env; then
    echo -e "${YELLOW}➕ Adding YouTube Music configuration to .env...${NC}"
    cat >> .env << 'EOF'

# YouTube Music Headless Configuration
YOUTUBE_MUSIC_ENABLED=true
YOUTUBE_MUSIC_API_URL=http://youtube-music-headless:9863
YOUTUBE_MUSIC_TIMEOUT=30
YOUTUBE_MUSIC_RETRY_ATTEMPTS=3
YOUTUBE_MUSIC_RETRY_DELAY=1
YOUTUBE_MUSIC_MAX_RESULTS=10
EOF
fi

# Step 3: Stop existing services
echo -e "${YELLOW}🛑 Stopping existing services...${NC}"
docker-compose down

# Step 4: Clean up old images (optional)
echo -e "${YELLOW}🧹 Cleaning up old images...${NC}"
docker image prune -f

# Step 5: Build services
echo -e "${YELLOW}🔨 Building services (this may take a few minutes)...${NC}"
docker-compose build --no-cache youtube-music-headless || {
    echo -e "${RED}❌ Build failed! Check error messages above.${NC}"
    exit 1
}

# Step 6: Start services
echo -e "${YELLOW}🚀 Starting all services...${NC}"
docker-compose up -d

# Step 7: Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to start (60 seconds)...${NC}"
for i in {1..60}; do
    echo -n "."
    sleep 1
done
echo ""

# Step 8: Health checks
echo -e "${YELLOW}🏥 Running health checks...${NC}"

# Check container status
echo "Container Status:"
docker-compose ps

# Check YouTube Music health
echo ""
echo "YouTube Music Service Health:"
if docker-compose exec youtube-music-headless curl -s http://localhost:9863/api/health 2>/dev/null | grep -q "status"; then
    echo -e "${GREEN}✅ YouTube Music API is responding${NC}"
else
    echo -e "${RED}❌ YouTube Music API is not responding${NC}"
    echo "Checking logs..."
    docker-compose logs --tail=20 youtube-music-headless
fi

# Check bot health
echo ""
echo "Bot Health Check:"
if curl -s http://localhost:8080/health 2>/dev/null | grep -q "healthy"; then
    echo -e "${GREEN}✅ Bot health endpoint is responding${NC}"
else
    echo -e "${YELLOW}⚠️  Bot health endpoint not ready yet${NC}"
fi

# Check YouTube Music integration
echo ""
echo "YouTube Music Integration Status:"
YTM_HEALTH=$(curl -s http://localhost:8080/health/youtube-music 2>/dev/null || echo "{}")
if echo "$YTM_HEALTH" | grep -q "overall_status"; then
    echo -e "${GREEN}✅ YouTube Music integration is active${NC}"
    echo "$YTM_HEALTH" | jq -r '.overall_status' 2>/dev/null || echo "$YTM_HEALTH"
else
    echo -e "${YELLOW}⚠️  YouTube Music integration not ready yet${NC}"
    echo "This is normal on first start. Check again in a minute."
fi

# Step 9: Show useful commands
echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Useful commands:"
echo "  View logs:         docker-compose logs -f"
echo "  YouTube Music:     docker-compose logs -f youtube-music-headless"
echo "  Bot logs:          docker-compose logs -f robustty"
echo "  Restart services:  docker-compose restart"
echo "  Check health:      curl http://localhost:8080/health/youtube-music | jq"
echo "  Run tests:         ./scripts/test-youtube-music-deployment.sh"
echo ""
echo -e "${YELLOW}💡 Tip: For authenticated access, sync cookies from your local machine:${NC}"
echo "  scp cookies/youtube_music_cookies.json user@vps:~/robustty-bot/cookies/"
echo ""