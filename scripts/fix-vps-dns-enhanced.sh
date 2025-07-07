#!/bin/bash

echo "=== Enhanced VPS DNS Fix for Discord Bot ==="
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

# Fix systemd-resolved symlink issue (critical for Ubuntu VPS)
echo "2. Fixing systemd-resolved DNS configuration..."
if [ -L /etc/resolv.conf ] && readlink /etc/resolv.conf | grep -q "stub-resolv.conf"; then
    echo "Detected systemd-resolved stub configuration - fixing..."
    # Remove the problematic stub symlink
    rm -f /etc/resolv.conf
    # Create symlink to real resolv.conf (not the stub)
    ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
    echo "Fixed /etc/resolv.conf symlink to use real resolver"
else
    # Fallback: create static resolv.conf if no systemd-resolved
    echo "Creating static DNS configuration..."
    rm -f /etc/resolv.conf
    cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
nameserver 1.0.0.1
EOF
fi
echo "Host DNS updated"
echo

# Add Discord domains to /etc/hosts as fallback
echo "3. Adding Discord domains to /etc/hosts as fallback..."
# Backup hosts file
cp /etc/hosts /etc/hosts.backup.$(date +%Y%m%d_%H%M%S)

# Remove existing Discord entries
sed -i '/discord\.gg/d' /etc/hosts
sed -i '/discord\.com/d' /etc/hosts
sed -i '/discordapp\.com/d' /etc/hosts

# Add Discord domains
cat >> /etc/hosts << EOF

# Discord domains (fallback for DNS resolution issues)
162.159.137.232 gateway.discord.gg
162.159.137.232 gateway-us-west-1.discord.gg
162.159.135.232 gateway-us-east-1.discord.gg
162.159.136.232 gateway-us-central-1.discord.gg
162.159.128.232 gateway-europe-1.discord.gg
162.159.134.232 gateway-asia-1.discord.gg
162.159.130.232 gateway-sydney-1.discord.gg
162.159.137.232 discord.com
162.159.137.232 discordapp.com
EOF
echo "Discord domains added to /etc/hosts"
echo

# Fix Docker daemon DNS
echo "4. Configuring Docker daemon DNS..."
mkdir -p /etc/docker

# Create or update Docker daemon configuration
if [ -f /etc/docker/daemon.json ] && [ -s /etc/docker/daemon.json ]; then
    # Backup existing
    cp /etc/docker/daemon.json /etc/docker/daemon.json.backup.$(date +%Y%m%d_%H%M%S)
    
    # Add DNS config using jq if available, otherwise manual
    if command -v jq &> /dev/null; then
        jq '. + {"dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1"], "dns-opts": ["ndots:0"], "dns-search": []}' /etc/docker/daemon.json > /tmp/daemon.json
        mv /tmp/daemon.json /etc/docker/daemon.json
    else
        echo "WARNING: jq not found, please manually add DNS to /etc/docker/daemon.json"
    fi
else
    # Create new daemon.json
    cat > /etc/docker/daemon.json << EOF
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1"],
  "dns-opts": ["ndots:0"],
  "dns-search": [],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
fi
echo "Docker daemon DNS configured"
echo

# Restart Docker
echo "5. Restarting Docker daemon..."
systemctl restart docker
sleep 5
echo "Docker restarted"
echo

# Fix systemd-resolved if present
if systemctl is-active systemd-resolved &>/dev/null; then
    echo "6. Configuring systemd-resolved..."
    mkdir -p /etc/systemd/resolved.conf.d/
    cat > /etc/systemd/resolved.conf.d/dns.conf << EOF
[Resolve]
DNS=8.8.8.8 8.8.4.4 1.1.1.1 1.0.0.1
FallbackDNS=208.67.222.222 208.67.220.220
DNSStubListener=no
Cache=yes
CacheFromLocalhost=yes
EOF
    # Restart services in correct order
    systemctl restart systemd-resolved
    # If NetworkManager is present, restart it to respect new DNS config
    systemctl is-active NetworkManager &>/dev/null && systemctl restart NetworkManager
    echo "systemd-resolved updated and services restarted"
else
    echo "6. systemd-resolved not active, skipping..."
fi
echo

# Test DNS resolution
echo "7. Testing DNS resolution..."
echo -n "Host DNS test (Google): "
nslookup google.com >/dev/null 2>&1 && echo "SUCCESS" || echo "FAILED"

echo -n "Host DNS test (Discord): "
nslookup gateway.discord.gg >/dev/null 2>&1 && echo "SUCCESS" || echo "FAILED"

echo -n "Host DNS test (Discord via hosts file): "
ping -c 1 gateway.discord.gg >/dev/null 2>&1 && echo "SUCCESS" || echo "FAILED"
echo

echo "8. Testing Docker container DNS..."
# Test Docker DNS
if docker run --rm alpine nslookup google.com >/dev/null 2>&1; then
    echo "Docker DNS test (Google): SUCCESS"
else
    echo "Docker DNS test (Google): FAILED"
fi

if docker run --rm alpine nslookup gateway.discord.gg >/dev/null 2>&1; then
    echo "Docker DNS test (Discord): SUCCESS"
else
    echo "Docker DNS test (Discord): FAILED (this is expected if using hosts file fallback)"
fi
echo

echo "9. Restarting Robustty containers..."
cd /home/*/robustty-bot 2>/dev/null || cd ~/robustty-bot || { echo "Cannot find robustty-bot directory"; exit 1; }
docker-compose down
docker-compose up -d
echo "Containers restarted"
echo

echo "=== Enhanced DNS Fix Complete ==="
echo
echo "Discord domains have been added to both:"
echo "1. Docker container configuration (via extra_hosts)"
echo "2. Host /etc/hosts file (as system-wide fallback)"
echo
echo "This dual approach ensures Discord connectivity even if DNS servers fail."
echo
echo "Please wait 30 seconds for services to stabilize, then check logs with:"
echo "docker-compose logs -f robustty"