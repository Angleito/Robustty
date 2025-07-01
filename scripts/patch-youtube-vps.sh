#!/bin/bash

# Patch YouTube Platform for VPS Usage
# This modifies the YouTube platform to work without cookies

set -e

echo "=== Patching YouTube Platform for VPS ==="
echo

# Find Robustty directory
ROBUSTTY_DIR=$(find /root /home -name "Robustty" -type d 2>/dev/null | head -1)
if [ -z "$ROBUSTTY_DIR" ]; then
    echo "Cannot find Robustty directory"
    exit 1
fi

cd "$ROBUSTTY_DIR"

# 1. Create a patched YouTube platform file
echo "1. Creating patched YouTube platform..."
cat > src/platforms/youtube_vps_patch.py << 'EOF'
# Temporary patch for YouTube platform to work on VPS without cookies

import os
import logging
from typing import Optional, Dict, Any, List
import yt_dlp
from .youtube import YouTube

logger = logging.getLogger(__name__)

class YouTubeVPS(YouTube):
    """YouTube platform optimized for VPS without cookies"""
    
    def __init__(self):
        super().__init__()
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': False,
            'extract_flat': False,
            'force_generic_extractor': False,
            'source_address': '0.0.0.0',  # Bind to all interfaces
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'nocheckcertificate': True,
            'prefer_insecure': True,
            # VPS-specific options
            'cookiefile': None,  # Don't use cookies
            'no_check_certificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'add_header': [
                'Accept-Language: en-US,en;q=0.9',
                'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            ],
            # Extractor args to bypass bot detection
            'extractor_args': {
                'youtube': {
                    'player_skip': ['configs', 'webpage'],
                    'player_client': ['android', 'web'],
                    'skip': ['hls', 'dash', 'translated_subs'],
                }
            }
        }
    
    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL with VPS optimizations"""
        url = f'https://www.youtube.com/watch?v={video_id}'
        
        # Try different approaches
        for attempt in range(3):
            try:
                # Modify options for each attempt
                opts = self.ydl_opts.copy()
                
                if attempt == 0:
                    # First try: Android client
                    opts['extractor_args']['youtube']['player_client'] = ['android']
                elif attempt == 1:
                    # Second try: Mobile web
                    opts['user_agent'] = 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
                    opts['extractor_args']['youtube']['player_client'] = ['mweb']
                else:
                    # Third try: TV embedded player
                    opts['extractor_args']['youtube']['player_client'] = ['tv_embedded']
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    if info and 'url' in info:
                        logger.info(f"Successfully extracted stream URL on attempt {attempt + 1}")
                        return info['url']
                    
                    # Look for formats
                    if info and 'formats' in info:
                        audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none']
                        if audio_formats:
                            best_audio = max(audio_formats, key=lambda f: f.get('abr', 0))
                            if best_audio.get('url'):
                                logger.info(f"Successfully extracted audio stream URL on attempt {attempt + 1}")
                                return best_audio['url']
                                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == 2:
                    logger.error(f"All extraction attempts failed for video {video_id}")
                    raise
                continue
        
        return None

# Replace the original YouTube class
YouTube = YouTubeVPS
EOF

# 2. Update the platform import
echo
echo "2. Updating platform imports..."
cat >> src/platforms/__init__.py << 'EOF'

# VPS patch for YouTube
try:
    from .youtube_vps_patch import YouTubeVPS
    YouTube = YouTubeVPS
except ImportError:
    pass
EOF

# 3. Create environment override
echo
echo "3. Creating environment override..."
cat >> .env << EOF

# VPS YouTube Configuration
YOUTUBE_DISABLE_COOKIES=true
YOUTUBE_USE_ANDROID_CLIENT=true
YOUTUBE_GEO_BYPASS=true
YT_DLP_VERBOSE=false
EOF

# 4. Restart containers
echo
echo "4. Restarting containers..."
docker-compose down
docker-compose up -d --build

echo
echo "=== YouTube VPS Patch Complete ==="
echo
echo "The bot should now be able to play YouTube videos without cookies!"
echo "Monitor with: docker-compose logs -f robustty"