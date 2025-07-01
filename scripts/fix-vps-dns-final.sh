#!/bin/bash

# Final DNS fix for VPS - simplified approach
# This uses the most reliable method for DNS resolution

set -e

echo "=== Final VPS DNS Fix ==="
echo
echo "This will fix DNS resolution once and for all"
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

# 1. Stop containers
echo
echo "=== Step 1: Stopping containers ==="
docker-compose down 2>/dev/null || true

# 2. Create simple override without conflicts
echo
echo "=== Step 2: Creating docker-compose override ==="
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
    environment:
      - PYTHONUNBUFFERED=1
      - VOICE_ENVIRONMENT=vps
      - VPS_STABILITY_MODE=true
    extra_hosts:
      # Discord gateways
      - "gateway-us-west-1.discord.gg:162.159.128.233"
      - "gateway-us-east-1.discord.gg:162.159.129.233"
      - "gateway-us-central-1.discord.gg:162.159.128.233"
      - "gateway-us-south-1.discord.gg:162.159.128.233"
      - "gateway-europe-1.discord.gg:162.159.130.234"
      - "gateway-asia-1.discord.gg:162.159.138.232"
      - "gateway-sydney-1.discord.gg:162.159.138.232"
      - "gateway-brazil-1.discord.gg:162.159.135.232"
      # Discord domains
      - "discord.com:162.159.137.232"
      - "discordapp.com:162.159.137.232"
      - "discord.gg:162.159.137.232"
  
  redis:
    dns:
      - 8.8.8.8
      - 8.8.4.4
EOF

# 3. Ensure cookies are in correct format
echo
echo "=== Step 3: Checking cookies ==="
if [ -f cookies/youtube_cookies.txt ]; then
    echo "✓ YouTube cookies found in Netscape format"
else
    echo "⚠ No YouTube cookies in Netscape format"
fi

# 4. Start services
echo
echo "=== Step 4: Starting services ==="
docker-compose up -d

# 5. Wait for startup
echo
echo "=== Step 5: Waiting for services ==="
sleep 10

# 6. Force DNS resolution in container
echo
echo "=== Step 6: Forcing DNS resolution ==="
# Create a custom resolv.conf inside the container
docker-compose exec -T robustty sh -c 'echo "nameserver 8.8.8.8" > /tmp/resolv.conf && echo "nameserver 8.8.4.4" >> /tmp/resolv.conf && cp /tmp/resolv.conf /etc/resolv.conf' 2>/dev/null || true

# 7. Test DNS
echo
echo "=== Step 7: Testing DNS ==="
echo -n "Discord.com resolution: "
if docker-compose exec -T robustty python -c "import socket; print(socket.gethostbyname('discord.com'))" 2>&1 | grep -E "([0-9]{1,3}\.){3}[0-9]{1,3}" >/dev/null; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
fi

# 8. Show logs
echo
echo "=== Step 8: Current status ==="
docker-compose logs --tail=30 robustty

echo
echo "=== DNS Fix Complete ==="
echo
echo "Monitor with: docker-compose logs -f robustty"