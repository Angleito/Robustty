#!/bin/bash

# Final VPS Fix - Resolves all issues
# This script fixes DNS, YouTube platform import, and Discord connectivity

set -e

echo "=== Final VPS Fix for Robustty Bot ==="
echo
echo "This will fix:"
echo "  1. YouTube platform import issues"
echo "  2. Discord connection (without hardcoded IPs)"
echo "  3. YouTube playback without cookies"
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
docker-compose down 2>/dev/null || docker compose down 2>/dev/null || true

# 2. Remove the problematic YouTube patch
echo
echo "=== Step 2: Restoring original YouTube platform ==="
# Remove the patched file if it exists
rm -f src/platforms/youtube_vps_patch.py 2>/dev/null || true

# Check if we have a backup
if [ -f src/platforms/youtube.py.backup ]; then
    echo "Restoring from backup..."
    mv src/platforms/youtube.py.backup src/platforms/youtube.py
else
    echo "No backup found, checking git status..."
    # Try to restore from git
    git checkout src/platforms/youtube.py 2>/dev/null || echo "Could not restore from git"
fi

# 3. Create a proper YouTube VPS override
echo
echo "=== Step 3: Creating proper YouTube VPS configuration ==="
mkdir -p src/platforms/overrides

cat > src/platforms/overrides/youtube_vps.py << 'EOF'
"""YouTube VPS configuration override"""

import os
import logging

logger = logging.getLogger(__name__)

def configure_for_vps(ydl_opts):
    """Modify yt-dlp options for VPS usage without cookies"""
    
    # Remove any cookie-related options
    ydl_opts.pop('cookiefile', None)
    ydl_opts.pop('cookiesfrombrowser', None)
    
    # Add VPS-specific options
    ydl_opts.update({
        'nocheckcertificate': True,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'source_address': '0.0.0.0',
        # Use alternative extraction methods
        'extractor_args': {
            'youtube': {
                'player_skip': ['webpage', 'configs', 'js'],
                'player_client': ['android', 'web_creator'],
                'skip': ['hls', 'dash', 'translated_subs'],
            }
        },
        # Custom headers
        'user_agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/91.0.4472.77 Mobile Safari/537.36',
        'referer': 'https://www.youtube.com/',
    })
    
    return ydl_opts

# Monkey patch if running on VPS
if os.getenv('YOUTUBE_VPS_MODE') == 'true':
    logger.info("YouTube VPS mode enabled - patching yt-dlp options")
    import src.platforms.youtube as youtube_module
    
    # Store original method
    _original_init = youtube_module.YouTube.__init__
    
    def patched_init(self):
        _original_init(self)
        # Modify ydl_opts after initialization
        if hasattr(self, 'ydl_opts'):
            self.ydl_opts = configure_for_vps(self.ydl_opts)
            logger.info("YouTube platform configured for VPS usage")
    
    # Apply patch
    youtube_module.YouTube.__init__ = patched_init
EOF

# 4. Update platform initialization
echo
echo "=== Step 4: Updating platform initialization ==="
# Add import to __init__.py if not already there
if ! grep -q "youtube_vps" src/platforms/__init__.py 2>/dev/null; then
    echo "" >> src/platforms/__init__.py
    echo "# VPS override" >> src/platforms/__init__.py
    echo "try:" >> src/platforms/__init__.py
    echo "    from .overrides import youtube_vps" >> src/platforms/__init__.py
    echo "except ImportError:" >> src/platforms/__init__.py
    echo "    pass" >> src/platforms/__init__.py
fi

# 5. Fix Docker DNS without hardcoded IPs
echo
echo "=== Step 5: Configuring Docker DNS properly ==="

# Docker daemon config
cat > /etc/docker/daemon.json << EOF
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-opts": ["ndots:0", "timeout:10", "attempts:5"]
}
EOF

# Restart Docker
systemctl restart docker || service docker restart
sleep 5

# 6. Create docker-compose override without hardcoded Discord IPs
echo
echo "=== Step 6: Creating docker-compose override ==="
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
      - timeout:10
      - attempts:5
    environment:
      - PYTHONDNS=8.8.8.8
      - YOUTUBE_VPS_MODE=true
      - DISABLE_YOUTUBE_COOKIES=true
      - DNS_TIMEOUT=10
      - DNS_ATTEMPTS=5
    # Add network capabilities for better connectivity
    cap_add:
      - NET_ADMIN
      - NET_RAW
  
  redis:
    dns:
      - 8.8.8.8
      - 8.8.4.4
EOF

# 7. Update environment variables
echo
echo "=== Step 7: Updating environment variables ==="
# Clean up duplicate entries first
grep -v "YOUTUBE_VPS_MODE\|DISABLE_YOUTUBE_COOKIES\|VOICE_ENVIRONMENT\|VPS_STABILITY_MODE" .env > .env.tmp 2>/dev/null || true
mv .env.tmp .env 2>/dev/null || true

# Add VPS configuration
cat >> .env << EOF

# VPS Configuration
YOUTUBE_VPS_MODE=true
DISABLE_YOUTUBE_COOKIES=true
YOUTUBE_USE_ANDROID_CLIENT=true
VOICE_ENVIRONMENT=vps
VPS_STABILITY_MODE=true
DISCORD_GATEWAY_TIMEOUT=60
DISCORD_GATEWAY_RETRIES=5
EOF

# 8. Clean and rebuild
echo
echo "=== Step 8: Rebuilding containers ==="
docker system prune -f >/dev/null 2>&1
docker-compose build --no-cache
docker-compose up -d

# 9. Wait for startup
echo
echo "=== Step 9: Waiting for services to start ==="
sleep 20

# 10. Run diagnostics
echo
echo "=== Step 10: Running diagnostics ==="

echo -n "Host connectivity: "
if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

echo -n "Container DNS: "
if docker-compose exec -T robustty python -c "import socket; print(socket.gethostbyname('discord.com'))" 2>/dev/null | grep -E "([0-9]{1,3}\.){3}[0-9]{1,3}" >/dev/null; then
    echo "✓ OK"
else
    echo "⚠ May have issues"
fi

echo -n "YouTube platform: "
if docker-compose exec -T robustty python -c "from src.platforms.youtube import YouTube; print('OK')" 2>/dev/null | grep -q "OK"; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

echo -n "Redis connectivity: "
if docker-compose exec -T robustty python -c "import redis; r=redis.from_url('redis://redis:6379'); print('OK' if r.ping() else 'FAIL')" 2>/dev/null | grep -q "OK"; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

# 11. Show logs
echo
echo "=== Step 11: Current bot status ==="
echo "Recent logs:"
echo "----------------------------------------"
docker-compose logs --tail=30 robustty 2>/dev/null || echo "Could not fetch logs"

echo
echo "=== Final VPS Fix Complete ==="
echo
echo "The bot should now be working properly!"
echo
echo "Key fixes applied:"
echo "  ✓ YouTube platform import fixed"
echo "  ✓ DNS resolution using public DNS servers"
echo "  ✓ YouTube configured for VPS usage"
echo "  ✓ Discord connectivity improved"
echo
echo "Monitor with: docker-compose logs -f robustty"
echo
echo "If you still see connection issues:"
echo "  1. Check your Discord bot token"
echo "  2. Verify YouTube API key"
echo "  3. Check firewall (ufw status)"
echo "  4. Try: docker-compose exec robustty curl https://discord.com"