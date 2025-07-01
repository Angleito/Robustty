#!/bin/bash

echo "=== Fixing VPS DNS Issues ==="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Backup current DNS config
echo "1. Backing up current DNS configuration..."
cp /etc/resolv.conf /etc/resolv.conf.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null
echo "Backup created"
echo

# Fix host DNS
echo "2. Fixing host DNS configuration..."
cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
EOF
echo "Host DNS updated"
echo

# Fix Docker daemon DNS
echo "3. Configuring Docker daemon DNS..."
mkdir -p /etc/docker

# Check if daemon.json exists and has content
if [ -f /etc/docker/daemon.json ] && [ -s /etc/docker/daemon.json ]; then
    # Backup existing
    cp /etc/docker/daemon.json /etc/docker/daemon.json.backup.$(date +%Y%m%d_%H%M%S)
    
    # Add DNS config using jq if available, otherwise manual
    if command -v jq &> /dev/null; then
        jq '. + {"dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"]}' /etc/docker/daemon.json > /tmp/daemon.json
        mv /tmp/daemon.json /etc/docker/daemon.json
    else
        echo "WARNING: jq not found, please manually add DNS to /etc/docker/daemon.json"
    fi
else
    # Create new daemon.json
    cat > /etc/docker/daemon.json << EOF
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-opts": ["ndots:0"],
  "dns-search": []
}
EOF
fi
echo "Docker daemon DNS configured"
echo

# Restart Docker
echo "4. Restarting Docker daemon..."
systemctl restart docker
sleep 5
echo "Docker restarted"
echo

# Fix systemd-resolved if present
if systemctl is-active systemd-resolved &>/dev/null; then
    echo "5. Fixing systemd-resolved..."
    mkdir -p /etc/systemd/resolved.conf.d/
    cat > /etc/systemd/resolved.conf.d/dns.conf << EOF
[Resolve]
DNS=8.8.8.8 8.8.4.4 1.1.1.1
FallbackDNS=208.67.222.222 208.67.220.220
DNSStubListener=no
EOF
    systemctl restart systemd-resolved
    echo "systemd-resolved updated"
else
    echo "5. systemd-resolved not active, skipping..."
fi
echo

# Test DNS resolution
echo "6. Testing DNS resolution..."
echo -n "Host DNS test: "
nslookup google.com >/dev/null 2>&1 && echo "SUCCESS" || echo "FAILED"
echo

echo "7. Restarting Robustty containers..."
cd /home/*/robustty-bot 2>/dev/null || cd ~/robustty-bot || { echo "Cannot find robustty-bot directory"; exit 1; }
docker-compose down
docker-compose up -d
echo "Containers restarted"
echo

echo "=== DNS Fix Complete ==="
echo
echo "Please wait 30 seconds for services to stabilize, then check logs with:"
echo "docker-compose logs -f robustty"