#!/bin/bash

# Fix Docker DNS Issues for Robustty Bot
# This script fixes DNS resolution issues inside Docker containers

set -e

echo "=== Fixing Docker DNS Issues ==="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# 1. Fix host DNS first
echo "1. Updating host DNS configuration..."
cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
nameserver 208.67.222.222
EOF
echo "✓ Host DNS updated"

# 2. Fix Docker daemon DNS
echo
echo "2. Configuring Docker daemon DNS..."
mkdir -p /etc/docker

# Create or update daemon.json
if [ -f /etc/docker/daemon.json ]; then
    cp /etc/docker/daemon.json /etc/docker/daemon.json.backup.$(date +%Y%m%d_%H%M%S)
fi

cat > /etc/docker/daemon.json << EOF
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-opts": ["ndots:0"],
  "dns-search": [],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
echo "✓ Docker daemon DNS configured"

# 3. Restart Docker daemon
echo
echo "3. Restarting Docker daemon..."
systemctl restart docker || service docker restart
sleep 5
echo "✓ Docker daemon restarted"

# 4. Test DNS resolution
echo
echo "4. Testing DNS resolution..."
echo -n "Testing host DNS: "
if nslookup google.com >/dev/null 2>&1; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
fi

echo -n "Testing Docker DNS: "
if docker run --rm alpine nslookup google.com >/dev/null 2>&1; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
fi

# 5. Clean up Docker networks (optional)
echo
echo "5. Cleaning up Docker networks..."
# Remove unused networks
docker network prune -f >/dev/null 2>&1 || true
echo "✓ Docker networks cleaned"

# 6. Update iptables rules for Docker
echo
echo "6. Updating iptables rules..."
# Ensure Docker can access DNS
iptables -I DOCKER-USER -p udp --dport 53 -j ACCEPT 2>/dev/null || true
iptables -I DOCKER-USER -p tcp --dport 53 -j ACCEPT 2>/dev/null || true
echo "✓ iptables rules updated"

# 7. Fix systemd-resolved if present
echo
echo "7. Checking systemd-resolved..."
if systemctl is-active systemd-resolved &>/dev/null; then
    echo "Disabling systemd-resolved DNS stub..."
    sed -i 's/#DNSStubListener=yes/DNSStubListener=no/g' /etc/systemd/resolved.conf
    systemctl restart systemd-resolved
    echo "✓ systemd-resolved updated"
else
    echo "✓ systemd-resolved not active"
fi

# 8. Final verification
echo
echo "=== DNS Fix Complete ==="
echo
echo "Please run these commands to restart your bot:"
echo "  cd ~/Robustty"
echo "  docker-compose down"
echo "  docker-compose up -d --build"
echo
echo "Then check logs with:"
echo "  docker-compose logs -f robustty"
echo
echo "If DNS issues persist, try:"
echo "  docker-compose exec robustty nslookup discord.com"
echo "  docker-compose exec robustty ping -c 3 8.8.8.8"