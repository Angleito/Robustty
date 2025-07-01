#!/bin/bash

# Setup YouTube Bypass for VPS
# This script configures the bot to work without cookies on VPS

set -e

echo "=== Setting up YouTube Bypass for VPS ==="
echo

# 1. Update environment variables
echo "1. Updating environment variables..."
if ! grep -q "YOUTUBE_USE_API_ONLY" .env 2>/dev/null; then
    echo "" >> .env
    echo "# YouTube Configuration" >> .env
    echo "YOUTUBE_USE_API_ONLY=true" >> .env
    echo "YOUTUBE_FALLBACK_TO_SEARCH=true" >> .env
    echo "DISABLE_YOUTUBE_COOKIES=true" >> .env
fi
echo "✓ Environment variables updated"

# 2. Remove old/invalid cookies
echo
echo "2. Cleaning up old cookies..."
if [ -d "./cookies" ]; then
    find ./cookies -name "youtube_*.txt" -mtime +1 -delete 2>/dev/null || true
    find ./cookies -name "youtube_*.json" -mtime +1 -delete 2>/dev/null || true
fi
echo "✓ Old cookies cleaned"

# 3. Create empty cookie files to prevent errors
echo
echo "3. Creating placeholder cookie files..."
mkdir -p ./cookies
touch ./cookies/youtube_cookies.txt
touch ./cookies/youtube_cookies.json
echo "✓ Placeholder files created"

# 4. Set proper permissions
echo
echo "4. Setting permissions..."
chmod -R 755 ./cookies
echo "✓ Permissions set"

echo
echo "=== YouTube Bypass Setup Complete ==="
echo
echo "The bot will now use:"
echo "  - YouTube Data API for searches"
echo "  - Public yt-dlp access (no cookies)"
echo "  - Fallback search if direct URLs fail"
echo
echo "Note: Some age-restricted or region-locked content may not be accessible"
echo
echo "To apply changes, restart the bot:"
echo "  docker-compose down"
echo "  docker-compose up -d"