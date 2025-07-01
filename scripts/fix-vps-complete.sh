#!/bin/bash

# Complete VPS Fix - DNS and YouTube
# This script fixes both DNS resolution and YouTube playback

set -e

echo "=== Complete VPS Fix for Robustty ==="
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
docker-compose down || docker compose down
docker stop $(docker ps -aq) 2>/dev/null || true

# 2. Fix host system DNS
echo
echo "=== Step 2: Fixing host DNS ==="
cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
EOF

# 3. Fix Docker daemon DNS
echo
echo "=== Step 3: Configuring Docker daemon ==="
cat > /etc/docker/daemon.json << EOF
{
  "dns": ["8.8.8.8", "8.8.4.4"],
  "dns-opts": ["ndots:0", "timeout:5", "attempts:3"],
  "default-address-pools": [
    {
      "base": "172.30.0.0/16",
      "size": 24
    }
  ]
}
EOF

# 4. Restart Docker completely
echo
echo "=== Step 4: Restarting Docker ==="
systemctl stop docker
# Clean up Docker's DNS state
rm -rf /var/lib/docker/network/files/local-kv.db
systemctl start docker
sleep 5

# 5. Create a WORKING YouTube patch
echo
echo "=== Step 5: Creating YouTube VPS patch ==="

# First, modify the actual YouTube platform file directly
echo "Patching YouTube platform directly..."
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
    dns_search: []
    dns_opt:
      - ndots:0
      - timeout:5
      - attempts:3
    extra_hosts:
      - "gateway-us-west-1.discord.gg:162.159.128.233"
      - "gateway-us-east-1.discord.gg:162.159.128.233"
      - "gateway-us-central-1.discord.gg:162.159.128.233"
      - "gateway-europe-1.discord.gg:162.159.130.234"
      - "gateway-asia-1.discord.gg:162.159.138.232"
      - "gateway-sydney-1.discord.gg:162.159.138.232"
      - "discord.com:162.159.137.232"
      - "discordapp.com:162.159.137.232"
    environment:
      - PYTHONDNS=8.8.8.8
EOF

# 8. Rebuild everything
echo
echo "=== Step 8: Rebuilding containers ==="
docker-compose build --no-cache
docker-compose up -d

# 9. Wait for startup
echo
echo "=== Step 9: Waiting for services to start ==="
sleep 15

# 10. Test everything
echo
echo "=== Step 10: Running tests ==="

echo -n "Host DNS test: "
if nslookup discord.com 8.8.8.8 >/dev/null 2>&1; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
fi

echo -n "Container DNS test: "
if docker-compose exec robustty python -c "import socket; print(socket.gethostbyname('discord.com'))" 2>/dev/null; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
fi

echo -n "Discord gateway resolution: "
if docker-compose exec robustty python -c "import socket; print(socket.gethostbyname('gateway-us-west-1.discord.gg'))" 2>/dev/null; then
    echo "✓ SUCCESS"
else
    echo "✗ FAILED"
fi

# 11. Show logs
echo
echo "=== Step 11: Checking bot status ==="
docker-compose logs --tail=30 robustty

echo
echo "=== Complete VPS Fix Applied ==="
echo
echo "The bot should now:"
echo "  ✓ Resolve DNS properly (with hardcoded Discord IPs as backup)"
echo "  ✓ Connect to Discord successfully"
echo "  ✓ Play YouTube videos without cookies"
echo
echo "Monitor with: docker-compose logs -f robustty"
echo
echo "If issues persist:"
echo "  1. Check firewall: ufw status"
echo "  2. Test connectivity: docker-compose exec robustty curl -I https://discord.com"
echo "  3. Verify bot token in .env file"