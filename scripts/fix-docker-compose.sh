#!/bin/bash

# Fix corrupted docker-compose.yml and restart services

set -e

echo "=== Fixing Docker Compose Configuration ==="
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
echo "Working in: $ROBUSTTY_DIR"

# 1. Restore docker-compose.yml
echo "=== Step 1: Restoring docker-compose.yml ==="
if [ -f docker-compose.yml.backup ]; then
    echo "Restoring from backup..."
    cp docker-compose.yml.backup docker-compose.yml
else
    echo "No backup found, checking git..."
    git checkout docker-compose.yml 2>/dev/null || echo "Could not restore from git"
fi

# 2. Verify docker-compose.yml is valid
echo
echo "=== Step 2: Verifying docker-compose.yml ==="
if docker-compose config >/dev/null 2>&1; then
    echo "✓ docker-compose.yml is valid"
else
    echo "✗ docker-compose.yml is still invalid, restoring from git..."
    git checkout HEAD -- docker-compose.yml
fi

# 3. Create proper override file for DNS
echo
echo "=== Step 3: Creating docker-compose override ==="
cat > docker-compose.override.yml << 'EOF'
version: '3.8'

services:
  robustty:
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
    dns_search: []
    dns_opt:
      - ndots:0
      - timeout:5
      - attempts:3
    environment:
      - PYTHONDNS=8.8.8.8
      - YOUTUBE_VPS_MODE=true
      - DISABLE_YOUTUBE_COOKIES=true
      - DNS_TIMEOUT=10
      - DNS_ATTEMPTS=5
    networks:
      - robustty-network
  
  redis:
    dns:
      - 8.8.8.8
      - 8.8.4.4
    networks:
      - robustty-network

networks:
  robustty-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
EOF

# 4. Start services
echo
echo "=== Step 4: Starting services ==="
docker-compose up -d

# 5. Wait for startup
echo
echo "=== Step 5: Waiting for services ==="
sleep 10

# 6. Test DNS
echo
echo "=== Step 6: Testing DNS resolution ==="
echo -n "Container DNS test: "
if docker-compose exec -T robustty python -c "import socket; print(socket.gethostbyname('discord.com'))" 2>/dev/null | grep -E "([0-9]{1,3}\.){3}[0-9]{1,3}" >/dev/null; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
fi

# 7. Show logs
echo
echo "=== Step 7: Current status ==="
docker-compose logs --tail=20 robustty

echo
echo "=== Fix Complete ==="
echo
echo "To monitor: docker-compose logs -f robustty"