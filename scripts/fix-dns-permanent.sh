#!/bin/bash

# Permanent DNS fix using Docker host networking
# This bypasses Docker's DNS resolver entirely

set -e

echo "=== Permanent DNS Fix ==="
echo
echo "Using host networking to bypass Docker DNS issues"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Find Robustty directory
ROBUSTTY_DIR=$(find /root /home -name "Robustty" -type d 2>/dev/null | head -1)
if [ -z "$ROBUSTTY_DIR" ]; then
    echo "Cannot find Robustty directory"
    exit 1
fi

cd "$ROBUSTTY_DIR"

# 1. Stop containers
echo
echo "=== Step 1: Stopping containers ==="
docker-compose down

# 2. Update docker-compose.yml to use host networking temporarily
echo
echo "=== Step 2: Creating temporary host network configuration ==="
cat > docker-compose.host.yml << 'EOF'
version: '3.8'

services:
  robustty:
    image: robustty_robustty:latest
    build: .
    container_name: robustty-bot
    network_mode: host
    environment:
      - REDIS_URL=redis://localhost:6379
      - PYTHONUNBUFFERED=1
      - VOICE_ENVIRONMENT=vps
      - VPS_STABILITY_MODE=true
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
      - ./data:/app/data
      - ./cookies:/app/cookies
    env_file:
      - .env
    restart: unless-stopped
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    container_name: robustty-redis
    network_mode: host
    command: redis-server --port 6379
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
EOF

# 3. Ensure host DNS is working
echo
echo "=== Step 3: Checking host DNS ==="
cat /etc/resolv.conf
echo
echo -n "Host DNS test: "
if nslookup discord.com 8.8.8.8 >/dev/null 2>&1; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
fi

# 4. Start with host networking
echo
echo "=== Step 4: Starting with host networking ==="
docker-compose -f docker-compose.host.yml up -d

# 5. Wait for startup
echo
echo "=== Step 5: Waiting for services ==="
sleep 10

# 6. Test connectivity
echo
echo "=== Step 6: Testing connectivity ==="
echo -n "Discord connection: "
if docker logs robustty-bot 2>&1 | tail -20 | grep -q "No address associated with hostname"; then
    echo "✗ Still failing"
else
    echo "✓ Should be working"
fi

# 7. Show logs
echo
echo "=== Step 7: Current status ==="
docker logs --tail=30 robustty-bot

echo
echo "=== Permanent DNS Fix Applied ==="
echo
echo "The bot is now using host networking to bypass Docker DNS issues."
echo "This means:"
echo "  - Bot uses port 8080 on host (for metrics)"
echo "  - Redis uses port 6379 on host"
echo "  - DNS resolution uses host's resolv.conf directly"
echo
echo "Monitor with: docker logs -f robustty-bot"
echo
echo "To revert to bridge networking later:"
echo "  docker-compose down"
echo "  docker-compose up -d"