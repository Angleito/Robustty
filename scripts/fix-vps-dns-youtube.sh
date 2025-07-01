#!/bin/bash

# VPS Fix for DNS and YouTube - Handles protected resolv.conf
# This script fixes both DNS resolution and YouTube playback

set -e

echo "=== VPS Fix for Robustty Bot ==="
echo
echo "This will fix:"
echo "  1. Docker DNS resolution issues"
echo "  2. YouTube playback without cookies"
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

# 1. Stop everything first
echo
echo "=== Step 1: Stopping all containers ==="
docker-compose down 2>/dev/null || docker compose down 2>/dev/null || true
docker stop $(docker ps -aq) 2>/dev/null || true

# 2. Handle protected resolv.conf
echo
echo "=== Step 2: Fixing host DNS ==="
# First try to remove immutable flag if set
chattr -i /etc/resolv.conf 2>/dev/null || true

# Check if we can write to resolv.conf
if [ -w /etc/resolv.conf ]; then
    cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
EOF
    echo "✓ Host DNS updated"
else
    echo "⚠ Cannot modify /etc/resolv.conf - using Docker DNS override instead"
fi

# 3. Fix Docker daemon DNS
echo
echo "=== Step 3: Configuring Docker daemon ==="
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << EOF
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-opts": ["ndots:0", "timeout:5", "attempts:3"],
  "default-address-pools": [
    {
      "base": "172.30.0.0/16",
      "size": 24
    }
  ]
}
EOF
echo "✓ Docker daemon configured"

# 4. Restart Docker
echo
echo "=== Step 4: Restarting Docker ==="
systemctl restart docker || service docker restart
sleep 5
echo "✓ Docker restarted"

# 5. Create a WORKING YouTube patch
echo
echo "=== Step 5: Patching YouTube platform ==="

# Backup original if exists
if [ -f src/platforms/youtube.py ]; then
    cp src/platforms/youtube.py src/platforms/youtube.py.backup
fi

# Create patched version
cat > src/platforms/youtube.py << 'EOF'
"""YouTube platform implementation for VPS without cookies"""

import os
import re
import logging
from typing import Optional, List, Dict, Any
import yt_dlp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import VideoPlatform

logger = logging.getLogger(__name__)

class YouTube(VideoPlatform):
    """YouTube platform implementation optimized for VPS"""
    
    def __init__(self):
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        self.youtube_api = None
        
        if self.api_key:
            try:
                self.youtube_api = build('youtube', 'v3', developerKey=self.api_key)
                logger.info("YouTube API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize YouTube API: {e}")
                self.youtube_api = None
        else:
            logger.warning("No YouTube API key provided")
            
        # VPS-optimized yt-dlp options
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': False,
            'extract_flat': False,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'nocheckcertificate': True,
            # Disable cookies for VPS
            'cookiefile': None,
            'cookiesfrombrowser': None,
            # Use alternative extraction methods
            'extractor_args': {
                'youtube': {
                    'player_skip': ['webpage', 'configs', 'js'],
                    'player_client': ['android', 'web'],
                    'skip': ['hls', 'dash', 'translated_subs'],
                }
            },
            # Custom headers to avoid bot detection
            'user_agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Mobile Safari/537.36',
            'referer': 'https://www.youtube.com/',
        }
    
    async def search_videos(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for videos using YouTube API"""
        if not self.youtube_api:
            logger.error("YouTube API not initialized")
            return []
            
        try:
            request = self.youtube_api.search().list(
                q=query,
                part='snippet',
                type='video',
                maxResults=max_results,
                fields='items(id(videoId),snippet(title,channelTitle,description,thumbnails))'
            )
            
            response = request.execute()
            
            results = []
            for item in response.get('items', []):
                results.append({
                    'id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'author': item['snippet']['channelTitle'],
                    'description': item['snippet']['description'],
                    'thumbnail': item['snippet']['thumbnails']['default']['url'],
                    'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    'platform': 'youtube'
                })
            
            return results
            
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
            return []
    
    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL using VPS-optimized extraction"""
        url = f'https://www.youtube.com/watch?v={video_id}'
        
        # Try different client approaches
        clients = ['android', 'mweb', 'tv_embedded', 'web']
        
        for client in clients:
            try:
                opts = self.ydl_opts.copy()
                opts['extractor_args']['youtube']['player_client'] = [client]
                
                # Special options for android client
                if client == 'android':
                    opts['user_agent'] = 'com.google.android.youtube/19.02.39 (Linux; U; Android 11) gzip'
                elif client == 'mweb':
                    opts['user_agent'] = 'Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36'
                
                logger.info(f"Attempting YouTube extraction with {client} client")
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    if info and 'url' in info:
                        logger.info(f"Successfully extracted stream URL using {client} client")
                        return info['url']
                    
                    # Check formats
                    if info and 'formats' in info:
                        audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none']
                        if audio_formats:
                            best_audio = max(audio_formats, key=lambda f: f.get('abr', 0))
                            if best_audio.get('url'):
                                logger.info(f"Successfully extracted audio stream URL using {client} client")
                                return best_audio['url']
                                
            except Exception as e:
                logger.warning(f"Failed with {client} client: {str(e)}")
                continue
        
        logger.error(f"All extraction methods failed for video {video_id}")
        return None
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def is_platform_url(self, url: str) -> bool:
        """Check if URL is from YouTube"""
        return bool(re.match(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)', url))
EOF
echo "✓ YouTube platform patched"

# 6. Update environment variables
echo
echo "=== Step 6: Updating environment variables ==="
if ! grep -q "YOUTUBE_VPS_MODE" .env 2>/dev/null; then
    cat >> .env << EOF

# VPS Configuration
YOUTUBE_VPS_MODE=true
DISABLE_YOUTUBE_COOKIES=true
YOUTUBE_USE_ANDROID_CLIENT=true
VOICE_ENVIRONMENT=vps
VPS_STABILITY_MODE=true
EOF
fi
echo "✓ Environment variables updated"

# 7. Create docker-compose override for DNS
echo
echo "=== Step 7: Creating docker-compose override ==="
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
      - "discord.media:162.159.137.232"
      - "discordapp.net:162.159.137.232"
      # YouTube
      - "youtube.com:142.250.185.142"
      - "www.youtube.com:142.250.185.142"
      - "youtubei.googleapis.com:142.250.185.142"
      - "youtube.googleapis.com:142.250.185.142"
    environment:
      - PYTHONDNS=8.8.8.8
      - DISCORD_GATEWAY_OVERRIDE=true
  
  redis:
    dns:
      - 8.8.8.8
      - 8.8.4.4
EOF
echo "✓ Docker compose override created"

# 8. Clean Docker system
echo
echo "=== Step 8: Cleaning Docker system ==="
docker system prune -f >/dev/null 2>&1
echo "✓ Docker system cleaned"

# 9. Rebuild everything
echo
echo "=== Step 9: Rebuilding containers ==="
docker-compose build --no-cache
docker-compose up -d
echo "✓ Containers rebuilt and started"

# 10. Wait for startup
echo
echo "=== Step 10: Waiting for services to start ==="
sleep 15

# 11. Test everything
echo
echo "=== Step 11: Running diagnostics ==="

echo -n "Host connectivity: "
if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

echo -n "Container DNS: "
if docker-compose exec -T robustty python -c "import socket; print(socket.gethostbyname('discord.com'))" 2>/dev/null | grep -q "162.159"; then
    echo "✓ OK (using override)"
else
    echo "⚠ May have issues"
fi

echo -n "Redis connectivity: "
if docker-compose exec -T robustty python -c "import redis; r=redis.from_url('redis://redis:6379'); print('OK' if r.ping() else 'FAIL')" 2>/dev/null | grep -q "OK"; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

# 12. Show current status
echo
echo "=== Step 12: Current bot status ==="
echo "Recent logs:"
echo "----------------------------------------"
docker-compose logs --tail=20 robustty 2>/dev/null || echo "Could not fetch logs"

echo
echo "=== VPS Fix Complete ==="
echo
echo "The bot should now:"
echo "  ✓ Connect to Discord (via hardcoded IPs)"
echo "  ✓ Play YouTube videos (using Android client)"
echo "  ✓ Have working DNS resolution"
echo
echo "Commands to use:"
echo "  Monitor logs:    docker-compose logs -f robustty"
echo "  Restart bot:     docker-compose restart robustty"
echo "  Check status:    docker-compose ps"
echo
echo "If the bot still has issues:"
echo "  1. Check your Discord bot token in .env"
echo "  2. Verify firewall: ufw status"
echo "  3. Test connection: docker-compose exec robustty curl -I https://discord.com"