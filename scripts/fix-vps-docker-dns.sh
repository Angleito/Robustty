#!/bin/bash

# Fix Docker DNS issues on VPS by bypassing Docker's internal resolver
# This script configures containers to use external DNS directly

set -e

echo "=== Docker DNS Fix for VPS ==="
echo
echo "This script will fix DNS resolution in Docker containers"
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
docker-compose down 2>/dev/null || docker compose down 2>/dev/null || true

# 2. Check current DNS setup
echo
echo "=== Step 2: Checking current DNS setup ==="
echo -n "Host DNS: "
cat /etc/resolv.conf | grep nameserver | head -1

echo -n "Docker daemon DNS: "
if [ -f /etc/docker/daemon.json ]; then
    cat /etc/docker/daemon.json | grep -o '"dns".*' | head -1 || echo "Not configured"
else
    echo "Not configured"
fi

# 3. Create a custom Docker network with proper DNS
echo
echo "=== Step 3: Creating custom Docker network ==="
docker network rm robustty-dns-net 2>/dev/null || true
docker network create \
    --driver bridge \
    --opt "com.docker.network.bridge.name=robustty-br0" \
    --opt "com.docker.network.driver.mtu=1450" \
    robustty-dns-net

# 4. Update docker-compose to use custom network and DNS
echo
echo "=== Step 4: Creating docker-compose override ==="
cat > docker-compose.override.yml << 'EOF'
version: '3.8'

networks:
  default:
    external:
      name: robustty-dns-net

services:
  robustty:
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
    dns_search: []
    dns_opt:
      - use-vc
      - edns0
      - ndots:0
    environment:
      - PYTHONDNS=8.8.8.8
      - RES_OPTIONS=ndots:0
    sysctls:
      - net.ipv4.ip_unprivileged_port_start=0
    cap_add:
      - NET_ADMIN
      - SYS_ADMIN
  
  redis:
    dns:
      - 8.8.8.8
      - 8.8.4.4
EOF

# 5. Create a resolv.conf override for containers
echo
echo "=== Step 5: Creating resolv.conf override ==="
mkdir -p "$ROBUSTTY_DIR/config/dns"
cat > "$ROBUSTTY_DIR/config/dns/resolv.conf" << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
options ndots:0 timeout:2 attempts:3
EOF

# 6. Patch docker-compose.yml to mount custom resolv.conf
echo
echo "=== Step 6: Patching docker-compose.yml ==="
if ! grep -q "resolv.conf:ro" docker-compose.yml; then
    # Backup original
    cp docker-compose.yml docker-compose.yml.backup
    
    # Add volume mount for resolv.conf
    sed -i '/volumes:/a\      - ./config/dns/resolv.conf:/etc/resolv.conf:ro' docker-compose.yml
fi

# 7. Configure iptables for DNS
echo
echo "=== Step 7: Configuring iptables for DNS ==="
# Allow DNS traffic
iptables -I DOCKER-USER -p udp --dport 53 -j ACCEPT 2>/dev/null || true
iptables -I DOCKER-USER -p tcp --dport 53 -j ACCEPT 2>/dev/null || true

# 8. Start containers
echo
echo "=== Step 8: Starting containers ==="
docker-compose up -d

# 9. Wait for startup
echo
echo "=== Step 9: Waiting for services ==="
sleep 10

# 10. Test DNS resolution
echo
echo "=== Step 10: Testing DNS resolution ==="

echo -n "Testing container DNS resolution... "
if docker-compose exec -T robustty nslookup discord.com 8.8.8.8 2>&1 | grep -q "Address"; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
    
    # Alternative test
    echo -n "Testing with Python resolver... "
    if docker-compose exec -T robustty python -c "
import socket
try:
    print(socket.gethostbyname('discord.com'))
    print('SUCCESS')
except:
    print('FAILED')
" 2>&1 | grep -q "SUCCESS"; then
        echo "✓ SUCCESS"
    else
        echo "✗ FAILED"
    fi
fi

echo -n "Testing Discord gateway resolution... "
if docker-compose exec -T robustty python -c "
import socket
try:
    socket.gethostbyname('gateway-us-west-1.discord.gg')
    print('SUCCESS')
except Exception as e:
    print(f'FAILED: {e}')
" 2>&1 | grep -q "SUCCESS"; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED - checking alternative solution..."
    
    # Force resolution using external DNS
    docker-compose exec -T robustty sh -c "echo '8.8.8.8' > /etc/resolv.conf && echo 'nameserver 8.8.8.8' >> /etc/resolv.conf"
fi

# 11. Show logs
echo
echo "=== Step 11: Current status ==="
echo "Recent logs:"
echo "----------------------------------------"
docker-compose logs --tail=20 robustty 2>/dev/null || echo "Could not fetch logs"

echo
echo "=== Docker DNS Fix Complete ==="
echo
echo "The bot should now be able to resolve DNS properly."
echo
echo "To monitor: docker-compose logs -f robustty"
echo
echo "If DNS still fails:"
echo "  1. Try: docker-compose exec robustty cat /etc/resolv.conf"
echo "  2. Test: docker-compose exec robustty nslookup discord.com"
echo "  3. Check: docker network inspect robustty-dns-net"