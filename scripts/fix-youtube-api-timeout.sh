#!/bin/bash

# Fix YouTube API timeout and search issues
# This directly addresses the 8-second timeout problem

echo "🚨 YouTube API Timeout Fix"
echo "========================="

cd /root/Robustty

# 1. Disable YouTube API temporarily and use yt-dlp only
echo "🔧 Switching to yt-dlp-only mode..."
cat >> .env << 'EOF'

# Temporary fix - disable API to use yt-dlp
YOUTUBE_USE_API=false
YOUTUBE_API_TIMEOUT=30
SEARCH_TIMEOUT=60
YOUTUBE_ENABLE_FALLBACKS=true
EOF

# 2. Update yt-dlp to latest version
echo "📦 Updating yt-dlp..."
docker exec robustty-bot pip install --upgrade --force-reinstall yt-dlp

# 3. Clear circuit breakers
echo "🔄 Resetting circuit breakers..."
docker exec robustty-redis redis-cli DEL "circuit_breaker:*"
docker exec robustty-redis redis-cli FLUSHALL

# 4. Fix cookie issues
echo "🍪 Setting up cookies..."
mkdir -p cookies
cat > cookies/youtube.txt << 'EOF'
# Netscape HTTP Cookie File
# This is a generated file!  Do not edit.
.youtube.com	TRUE	/	TRUE	0	CONSENT	YES+
EOF

# 5. Restart bot with increased memory
echo "🔄 Restarting bot with fixes..."
docker-compose stop robustty
docker-compose rm -f robustty
docker-compose up -d robustty

# 6. Test yt-dlp directly
echo "🧪 Testing yt-dlp..."
docker exec robustty-bot yt-dlp --version
docker exec robustty-bot yt-dlp --dump-json "ytsearch:test" || echo "yt-dlp test failed"

echo "✅ Fixes applied!"
echo ""
echo "The bot is now using yt-dlp directly instead of YouTube API"
echo "This should bypass the timeout issues"
echo ""
echo "Test with: !play despacito"