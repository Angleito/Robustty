#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Robustty VPS Search & API Error Fix Script            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print colored status
print_status() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓${NC} $1"
}

print_error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠${NC} $1"
}

# Check if running on VPS
if [[ ! -f /root/Robustty/docker-compose.yml ]]; then
    print_warning "This script should be run on the VPS in /root/Robustty"
    exit 1
fi

cd /root/Robustty

print_status "Starting comprehensive fix for search and API errors..."

# Step 1: Stop all containers
print_status "Stopping all containers..."
docker-compose down
print_success "Containers stopped"

# Step 2: Clean Docker system
print_status "Cleaning Docker system..."
docker system prune -f
docker volume prune -f
print_success "Docker system cleaned"

# Step 3: Update yt-dlp (critical for YouTube issues)
print_status "Creating yt-dlp update script..."
cat > update-ytdlp.sh << 'EOF'
#!/bin/bash
# Update yt-dlp in all containers
pip install --upgrade yt-dlp
yt-dlp --version
EOF
chmod +x update-ytdlp.sh

# Step 4: Fix DNS and network issues
print_status "Fixing DNS configuration..."
cat > /etc/docker/daemon.json << 'EOF'
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-opts": ["ndots:0"],
  "dns-search": []
}
EOF

# Restart Docker daemon
print_status "Restarting Docker daemon..."
systemctl restart docker
sleep 5
print_success "Docker daemon restarted with fixed DNS"

# Step 5: Create network if it doesn't exist
print_status "Creating Docker network..."
docker network create robustty-network 2>/dev/null || true

# Step 6: Pull latest images
print_status "Pulling latest base images..."
docker pull python:3.11-slim
docker pull redis:7-alpine

# Step 7: Rebuild containers with no cache
print_status "Rebuilding all containers (this may take a few minutes)..."
docker-compose build --no-cache

# Step 8: Start Redis first
print_status "Starting Redis..."
docker-compose up -d redis
sleep 5

# Step 9: Start YouTube Music headless
print_status "Starting YouTube Music headless service..."
docker-compose up -d youtube-music-headless
sleep 10

# Step 10: Check YouTube Music health
print_status "Checking YouTube Music service health..."
for i in {1..10}; do
    if curl -s http://localhost:9863/api/health > /dev/null 2>&1; then
        print_success "YouTube Music service is healthy"
        break
    else
        print_warning "Waiting for YouTube Music service... (attempt $i/10)"
        sleep 5
    fi
done

# Step 11: Start main bot
print_status "Starting Robustty bot..."
docker-compose up -d robustty

# Step 12: Update yt-dlp in containers
print_status "Updating yt-dlp in all containers..."
docker-compose exec -T robustty pip install --upgrade yt-dlp
docker-compose exec -T youtube-music-headless npm update ytmusic-api 2>/dev/null || true

# Step 13: Test connectivity
print_status "Testing external connectivity..."
docker-compose exec -T robustty ping -c 1 google.com > /dev/null 2>&1 && \
    print_success "External connectivity OK" || \
    print_error "External connectivity failed"

# Step 14: Check container health
print_status "Checking container health..."
docker-compose ps

# Step 15: Test API endpoints
print_status "Testing API endpoints..."
echo ""
echo "YouTube Music API:"
curl -s http://localhost:9863/api/health | jq '.' 2>/dev/null || echo "API not responding"
echo ""

# Step 16: Show recent logs
print_status "Recent bot logs:"
docker-compose logs --tail=20 robustty

echo ""
print_success "Fix script completed!"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "1. Test the bot with: !play <song name>"
echo "2. Monitor logs: docker-compose logs -f robustty"
echo "3. If issues persist, try different search queries"
echo ""
echo -e "${YELLOW}If YouTube Music still fails:${NC}"
echo "- The bot will automatically fall back to regular YouTube"
echo "- You can disable YouTube Music in .env: YOUTUBE_MUSIC_ENABLED=false"
echo ""