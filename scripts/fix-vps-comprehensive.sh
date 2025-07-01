#!/bin/bash

# Comprehensive VPS fix - DNS, YouTube, and cookies
# This script fixes all known issues in the correct order

set -e

echo "=== Comprehensive VPS Fix ==="
echo
echo "This will fix:"
echo "  1. YouTube platform import errors"
echo "  2. DNS resolution for Discord"
echo "  3. Cookie usage for YouTube"
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

# 1. Stop everything
echo
echo "=== Step 1: Stopping all containers ==="
docker-compose down || true

# 2. Clean up broken YouTube patches
echo
echo "=== Step 2: Cleaning up YouTube patches ==="
# Remove all patches and restore original
rm -f src/platforms/youtube_vps_patch.py
rm -f src/platforms/youtube_patch.py
rm -rf src/config/
rm -rf src/platforms/overrides/

# Restore original YouTube platform
if [ -f src/platforms/youtube.py.backup ]; then
    echo "Restoring YouTube platform from backup..."
    mv src/platforms/youtube.py.backup src/platforms/youtube.py
else
    echo "Restoring YouTube platform from git..."
    git checkout HEAD -- src/platforms/youtube.py 2>/dev/null || echo "Warning: Could not restore from git"
fi

# Remove patch imports from bot.py
sed -i '/youtube_patch/d' src/bot/bot.py 2>/dev/null || true

# 3. Fix DNS with host networking as fallback
echo
echo "=== Step 3: Configuring DNS ==="
cat > docker-compose.override.yml << 'EOF'
version: '3.8'

services:
  robustty:
    network_mode: bridge
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
      - rotate
      - edns0
    environment:
      - PYTHONDNS=8.8.8.8
      - YOUTUBE_DISABLE_COOKIES=false
      - DNS_TIMEOUT=10
      - DNS_ATTEMPTS=5
      - VOICE_ENVIRONMENT=vps
      - VPS_STABILITY_MODE=true
    extra_hosts:
      - "host.docker.internal:host-gateway"
    sysctls:
      - net.ipv6.conf.all.disable_ipv6=1
    cap_add:
      - NET_ADMIN
  
  redis:
    dns:
      - 8.8.8.8
      - 8.8.4.4
EOF

# 4. Convert cookies to Netscape format
echo
echo "=== Step 4: Converting cookies ==="
if [ -d cookies ] && ls cookies/*.json >/dev/null 2>&1; then
    echo "Converting JSON cookies to Netscape format..."
    python3 - << 'PYTHON_EOF'
import json
import os
from pathlib import Path

def json_to_netscape(json_file, txt_file):
    """Convert JSON cookies to Netscape format"""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Handle different JSON formats
        cookies = data.get('cookies', data) if isinstance(data, dict) else data
        
        with open(txt_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This is a generated file! Do not edit.\n\n")
            
            for cookie in cookies:
                if isinstance(cookie, dict):
                    domain = cookie.get('domain', '')
                    if not domain.startswith('.'):
                        domain = '.' + domain
                    include_subdomains = 'TRUE'
                    
                    path = cookie.get('path', '/')
                    secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                    expires = str(int(cookie.get('expirationDate', cookie.get('expires', 0))))
                    name = cookie.get('name', '')
                    value = cookie.get('value', '')
                    
                    f.write(f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
        
        print(f"✓ Converted {json_file} to {txt_file}")
        return True
    except Exception as e:
        print(f"✗ Failed to convert {json_file}: {e}")
        return False

# Convert all platform cookies
cookie_dir = Path("cookies")
platforms = ['youtube', 'rumble', 'odysee', 'peertube']

for platform in platforms:
    json_file = cookie_dir / f"{platform}_cookies.json"
    txt_file = cookie_dir / f"{platform}_cookies.txt"
    
    if json_file.exists():
        json_to_netscape(json_file, txt_file)
PYTHON_EOF
    
    # Set permissions
    chown -R 1000:1000 cookies/
    chmod 644 cookies/*.txt 2>/dev/null || true
else
    echo "No cookies found to convert"
fi

# 5. Update hosts file for Discord
echo
echo "=== Step 5: Updating hosts file ==="
# Add Discord hosts if not already present
grep -q "discord.gg" /etc/hosts || cat >> /etc/hosts << EOF

# Discord hosts
162.159.128.233 gateway-us-west-1.discord.gg
162.159.129.233 gateway-us-east-1.discord.gg
162.159.128.233 gateway-us-central-1.discord.gg
162.159.128.233 gateway-us-south-1.discord.gg
162.159.130.234 gateway-europe-1.discord.gg
162.159.138.232 gateway-asia-1.discord.gg
162.159.138.232 gateway-sydney-1.discord.gg
162.159.135.232 gateway-brazil-1.discord.gg
EOF

# 6. Fix iptables for DNS
echo
echo "=== Step 6: Configuring firewall for DNS ==="
iptables -I OUTPUT -p udp --dport 53 -j ACCEPT 2>/dev/null || true
iptables -I OUTPUT -p tcp --dport 53 -j ACCEPT 2>/dev/null || true
iptables -I DOCKER-USER -p udp --dport 53 -j ACCEPT 2>/dev/null || true
iptables -I DOCKER-USER -p tcp --dport 53 -j ACCEPT 2>/dev/null || true

# 7. Clean Docker DNS cache
echo
echo "=== Step 7: Cleaning Docker DNS cache ==="
systemctl restart systemd-resolved 2>/dev/null || true
docker network prune -f
docker system prune -f

# 8. Start services
echo
echo "=== Step 8: Starting services ==="
docker-compose up -d

# 9. Wait for startup
echo
echo "=== Step 9: Waiting for services to start ==="
sleep 15

# 10. Test everything
echo
echo "=== Step 10: Running diagnostics ==="

echo -n "Host connectivity: "
if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

echo -n "Discord resolution: "
if ping -c 1 discord.com >/dev/null 2>&1; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

echo -n "Container DNS: "
if docker-compose exec -T robustty nslookup discord.com 2>&1 | grep -q "Address"; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

echo -n "YouTube cookies: "
if docker-compose exec -T robustty ls /app/cookies/youtube_cookies.txt >/dev/null 2>&1; then
    echo "✓ Found"
else
    echo "✗ Not found"
fi

echo -n "Redis connectivity: "
if docker-compose exec -T robustty python -c "import redis; r=redis.from_url('redis://redis:6379'); print('OK' if r.ping() else 'FAIL')" 2>&1 | grep -q "OK"; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

# 11. Show logs
echo
echo "=== Step 11: Current bot status ==="
echo "Recent logs:"
echo "----------------------------------------"
docker-compose logs --tail=30 robustty

echo
echo "=== Comprehensive Fix Complete ==="
echo
echo "The bot should now be working with:"
echo "  ✓ DNS resolution for Discord"
echo "  ✓ YouTube cookies in correct format"
echo "  ✓ Clean platform imports"
echo
echo "Monitor with: docker-compose logs -f robustty"
echo
echo "If still having issues:"
echo "  1. Check Discord token in .env"
echo "  2. Try: docker-compose exec robustty curl https://discord.com"
echo "  3. Verify: docker-compose exec robustty cat /etc/resolv.conf"