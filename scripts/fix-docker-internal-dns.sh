#!/bin/bash

# Fix Docker Internal DNS Issues on VPS
# This script fixes the 127.0.0.11 DNS resolver issues

set -e

echo "=== Fixing Docker Internal DNS Issues ==="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# 1. Stop existing containers
echo "1. Stopping containers..."
cd $(find /root /home -name "Robustty" -type d 2>/dev/null | head -1)
docker-compose down || docker compose down

# 2. Disable Docker's embedded DNS resolver
echo
echo "2. Updating Docker daemon configuration..."
cat > /etc/docker/daemon.json << EOF
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-opts": ["ndots:0"],
  "dns-search": [],
  "bip": "172.26.0.1/24",
  "fixed-cidr": "172.26.0.0/25",
  "default-address-pools": [
    {
      "base": "172.27.0.0/16",
      "size": 24
    }
  ],
  "userland-proxy": false,
  "experimental": true,
  "max-concurrent-downloads": 10,
  "max-concurrent-uploads": 5,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# 3. Update host DNS to ensure it's correct
echo
echo "3. Updating host DNS..."
cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
EOF

# Make resolv.conf immutable to prevent overwrites
chattr +i /etc/resolv.conf 2>/dev/null || true

# 4. Restart Docker with clean state
echo
echo "4. Restarting Docker daemon..."
systemctl stop docker
rm -rf /var/lib/docker/network/files/local-kv.db
systemctl start docker
sleep 5

# 5. Update docker-compose.yml to use host networking for DNS
echo
echo "5. Creating docker-compose override..."
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
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - DISABLE_YOUTUBE_COOKIES=true
      - YT_DLP_NO_WARNINGS=true
      - YOUTUBE_FALLBACK_TO_SEARCH=true
EOF

# 6. Clear any cached DNS
echo
echo "6. Clearing DNS cache..."
if command -v systemd-resolve &> /dev/null; then
    systemd-resolve --flush-caches 2>/dev/null || true
fi

# 7. Start containers with new config
echo
echo "7. Starting containers with fixed DNS..."
docker-compose up -d --build

# 8. Wait and test
echo
echo "8. Waiting for services to start..."
sleep 10

# 9. Test DNS resolution
echo
echo "9. Testing DNS resolution..."
echo -n "Container DNS test: "
if docker-compose exec robustty python -c "import socket; print(socket.gethostbyname('discord.com'))" 2>/dev/null; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
    echo
    echo "Trying alternative fix..."
    
    # Alternative: Add iptables rules
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    iptables -A FORWARD -i docker0 -o eth0 -j ACCEPT
    iptables -A FORWARD -i eth0 -o docker0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    # Restart containers
    docker-compose restart
fi

echo
echo "=== DNS Fix Complete ==="
echo
echo "Check logs with:"
echo "  docker-compose logs -f robustty"
echo
echo "The bot should now connect properly to Discord!"