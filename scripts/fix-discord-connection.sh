#!/bin/bash

# Fix Discord connection - remove hardcoded IPs that are being blocked
# This lets Discord resolve naturally through DNS

set -e

echo "=== Discord Connection Fix ==="
echo
echo "Removing hardcoded IPs and using natural DNS resolution"
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

# 2. Create clean override without extra_hosts
echo
echo "=== Step 2: Creating clean docker-compose override ==="
cat > docker-compose.override.yml << 'EOF'
version: '3.8'

services:
  robustty:
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
      - 1.0.0.1
    dns_search: []
    dns_opt:
      - ndots:0
      - timeout:5
      - attempts:3
    environment:
      - PYTHONUNBUFFERED=1
      - VOICE_ENVIRONMENT=vps
      - VPS_STABILITY_MODE=true
      - DISCORD_GATEWAY_TIMEOUT=90
      - DISCORD_WS_HEARTBEAT_TIMEOUT=60
  
  redis:
    dns:
      - 8.8.8.8
      - 8.8.4.4
EOF

# 3. Remove hardcoded Discord entries from hosts file
echo
echo "=== Step 3: Cleaning hosts file ==="
# Remove Discord entries we added earlier
sed -i '/Discord hosts/,/discord\.gg/d' /etc/hosts 2>/dev/null || true
sed -i '/gateway.*discord\.gg/d' /etc/hosts 2>/dev/null || true
sed -i '/discord\.com/d' /etc/hosts 2>/dev/null || true
sed -i '/discordapp/d' /etc/hosts 2>/dev/null || true

# 4. Start services
echo
echo "=== Step 4: Starting services ==="
docker-compose up -d

# 5. Wait for startup
echo
echo "=== Step 5: Waiting for services ==="
sleep 10

# 6. Test connectivity
echo
echo "=== Step 6: Testing connectivity ==="

echo -n "Discord.com DNS: "
if docker-compose exec -T robustty python -c "
import socket
try:
    ip = socket.gethostbyname('discord.com')
    print(f'✓ Resolved to {ip}')
except:
    print('✗ Failed')
" 2>&1 | grep -q "✓"; then
    echo "SUCCESS"
else
    echo "FAILED"
fi

echo -n "Gateway DNS: "
if docker-compose exec -T robustty python -c "
import socket
try:
    ip = socket.gethostbyname('gateway.discord.gg')
    print(f'✓ Resolved to {ip}')
except:
    print('✗ Failed')
" 2>&1 | grep -q "✓"; then
    echo "SUCCESS"
else
    echo "FAILED"
fi

echo -n "HTTPS connectivity: "
if docker-compose exec -T robustty python -c "
import urllib.request
try:
    urllib.request.urlopen('https://discord.com', timeout=5)
    print('✓ Connected')
except:
    print('✗ Failed')
" 2>&1 | grep -q "✓"; then
    echo "SUCCESS"
else
    echo "FAILED"
fi

# 7. Show current logs
echo
echo "=== Step 7: Current status ==="
docker-compose logs --tail=20 robustty

echo
echo "=== Discord Connection Fix Complete ==="
echo
echo "The bot should now connect to Discord using natural DNS resolution."
echo "Monitor with: docker-compose logs -f robustty"
echo
echo "If you still see 530 errors, it might be due to:"
echo "  1. Rate limiting from your VPS IP"
echo "  2. Invalid Discord bot token"
echo "  3. VPS provider blocking Discord"
echo
echo "To check token: grep DISCORD_TOKEN .env"