#!/bin/bash

# Configure YouTube to work without cookies on VPS
# This uses alternative extraction methods

set -e

echo "=== YouTube No-Cookie Configuration ==="
echo
echo "This configures YouTube to work without cookies using alternative methods"
echo

# Find Robustty directory
ROBUSTTY_DIR=$(find /root /home -name "Robustty" -type d 2>/dev/null | head -1)
if [ -z "$ROBUSTTY_DIR" ]; then
    echo "Cannot find Robustty directory"
    exit 1
fi

cd "$ROBUSTTY_DIR"

# 1. Create YouTube configuration override
echo
echo "=== Step 1: Creating YouTube configuration ==="
mkdir -p src/config
cat > src/config/youtube_vps.py << 'EOF'
"""YouTube VPS configuration for cookie-less operation"""

# yt-dlp options optimized for VPS without cookies
YOUTUBE_VPS_OPTIONS = {
    'nocheckcertificate': True,
    'geo_bypass': True,
    'geo_bypass_country': 'US',
    'source_address': '0.0.0.0',
    'force_ipv4': True,
    'prefer_insecure': True,
    'legacy_server_connect': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web_creator', 'android_producer'],
            'player_skip': ['webpage', 'configs', 'js'],
            'skip': ['hls', 'dash', 'translated_subs'],
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
        },
        'youtubetab': {
            'skip': ['webpage'],
        }
    },
    'http_headers': {
        'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    }
}

def get_youtube_opts():
    """Get YouTube options for VPS"""
    return YOUTUBE_VPS_OPTIONS.copy()
EOF

# 2. Patch YouTube platform to use VPS config
echo
echo "=== Step 2: Patching YouTube platform ==="
cat > src/platforms/youtube_patch.py << 'EOF'
"""Monkey patch for YouTube platform to work on VPS"""

import os
import logging

logger = logging.getLogger(__name__)

def patch_youtube_platform():
    """Apply VPS patches to YouTube platform"""
    try:
        from src.platforms.youtube import YouTube
        from src.config.youtube_vps import get_youtube_opts
        
        # Store original init
        _original_init = YouTube.__init__
        
        def patched_init(self):
            _original_init(self)
            
            # Override yt-dlp options for VPS
            vps_opts = get_youtube_opts()
            self.ydl_opts.update(vps_opts)
            
            # Remove cookie options
            self.ydl_opts.pop('cookiefile', None)
            self.ydl_opts.pop('cookiesfrombrowser', None)
            
            logger.info("YouTube platform configured for VPS (no cookies)")
        
        # Apply patch
        YouTube.__init__ = patched_init
        logger.info("YouTube VPS patch applied successfully")
        
    except Exception as e:
        logger.error(f"Failed to patch YouTube platform: {e}")

# Auto-patch if running on VPS
if os.getenv('YOUTUBE_VPS_MODE') == 'true':
    patch_youtube_platform()
EOF

# 3. Update bot initialization to load patch
echo
echo "=== Step 3: Updating bot initialization ==="
# Add import to bot.py after other imports
if ! grep -q "youtube_patch" src/bot/bot.py; then
    sed -i '/^import/ a\
try:\
    from ..platforms import youtube_patch\
except ImportError:\
    pass' src/bot/bot.py
fi

# 4. Update environment variables
echo
echo "=== Step 4: Setting environment variables ==="
cat >> .env << EOF

# YouTube VPS Configuration
YOUTUBE_VPS_MODE=true
YOUTUBE_DISABLE_AGE_GATE=true
YOUTUBE_BYPASS_GEO_RESTRICTION=true
EOF

# 5. Restart containers
echo
echo "=== Step 5: Restarting containers ==="
docker-compose down
docker-compose up -d --build

echo
echo "=== YouTube No-Cookie Configuration Complete ==="
echo
echo "YouTube should now work without cookies!"
echo "The bot uses Android client spoofing to bypass restrictions."
echo
echo "Monitor with: docker-compose logs -f robustty"