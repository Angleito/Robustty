#!/bin/bash

# Comprehensive VPS Audio Fix Script
# Fixes DNS issues and YouTube playback problems

set -e

echo "=== Comprehensive VPS Audio Fix ==="
echo "This script will fix DNS and YouTube playback issues"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Get the Robustty directory
ROBUSTTY_DIR=$(find /home -name "Robustty" -type d 2>/dev/null | head -1)
if [ -z "$ROBUSTTY_DIR" ]; then
    ROBUSTTY_DIR=$(find /root -name "Robustty" -type d 2>/dev/null | head -1)
fi
if [ -z "$ROBUSTTY_DIR" ]; then
    echo "Cannot find Robustty directory. Please specify the path."
    exit 1
fi

echo "Found Robustty at: $ROBUSTTY_DIR"
cd "$ROBUSTTY_DIR"

# 1. Fix DNS Issues
echo
echo "=== STEP 1: Fixing DNS Issues ==="
echo "--------------------------------"

# Fix host DNS
echo "Updating host DNS..."
cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
EOF

# Fix Docker daemon DNS
echo "Configuring Docker DNS..."
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << EOF
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-opts": ["ndots:0"],
  "default-address-pools": [
    {
      "base": "172.17.0.0/16",
      "size": 24
    }
  ]
}
EOF

# Restart Docker
echo "Restarting Docker daemon..."
systemctl restart docker || service docker restart
sleep 5

# 2. Fix YouTube Issues
echo
echo "=== STEP 2: Fixing YouTube Playback ==="
echo "--------------------------------------"

# Update environment for YouTube bypass
echo "Configuring YouTube bypass..."
if ! grep -q "YOUTUBE_USE_API_ONLY" .env 2>/dev/null; then
    cat >> .env << EOF

# YouTube VPS Configuration
YOUTUBE_USE_API_ONLY=false
YOUTUBE_FALLBACK_TO_SEARCH=true
DISABLE_YOUTUBE_COOKIES=true
YT_DLP_EXTRACT_FLAT=false
YT_DLP_NO_WARNINGS=true
EOF
fi

# Clean up old cookies
echo "Cleaning up old cookies..."
rm -rf ./cookies/youtube_*.txt ./cookies/youtube_*.json 2>/dev/null || true
mkdir -p ./cookies
touch ./cookies/.gitkeep

# 3. Stop existing containers
echo
echo "=== STEP 3: Stopping Containers ==="
echo "----------------------------------"
docker-compose down || docker compose down

# 4. Rebuild and start
echo
echo "=== STEP 4: Rebuilding Bot ==="
echo "-----------------------------"
docker-compose up -d --build || docker compose up -d --build

# 5. Wait for services to stabilize
echo
echo "Waiting for services to stabilize..."
sleep 10

# 6. Test DNS inside container
echo
echo "=== STEP 5: Testing DNS Resolution ==="
echo "------------------------------------"
echo -n "Testing DNS in container: "
if docker-compose exec robustty nslookup discord.com >/dev/null 2>&1 || docker compose exec robustty nslookup discord.com >/dev/null 2>&1; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED - Manual intervention may be needed"
fi

# 7. Show logs
echo
echo "=== STEP 6: Checking Bot Status ==="
echo "---------------------------------"
echo "Showing last 20 lines of logs..."
docker-compose logs --tail=20 robustty || docker compose logs --tail=20 robustty

echo
echo "=== Fix Complete ==="
echo
echo "The bot should now be able to:"
echo "  ✓ Resolve DNS properly"
echo "  ✓ Connect to Discord"
echo "  ✓ Play YouTube videos without cookies"
echo
echo "To monitor the bot:"
echo "  docker-compose logs -f robustty"
echo
echo "To test playback in Discord:"
echo "  !play <youtube-url>"
echo "  !play <search-query>"
echo
echo "If issues persist, check:"
echo "  - Your YouTube API key is valid"
echo "  - VPS firewall allows outbound HTTPS (port 443)"
echo "  - docker-compose exec robustty ping youtube.com"