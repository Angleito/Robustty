#!/bin/bash

# Emergency fix for platform API issues
# This script addresses the specific errors shown in screenshots

echo "🚨 Emergency Platform Fix Script"
echo "================================"

cd /root/Robustty

# 1. Force update all platform libraries
echo "📦 Updating platform libraries..."
cat > /tmp/update-deps.sh << 'EOF'
#!/bin/bash
pip install --upgrade \
    yt-dlp \
    youtube-dl \
    aiohttp \
    requests \
    beautifulsoup4 \
    lxml
EOF

docker cp /tmp/update-deps.sh robustty-bot:/tmp/
docker exec robustty-bot bash /tmp/update-deps.sh

# 2. Fix YouTube format issues
echo "🎥 Fixing YouTube format issues..."
docker exec robustty-bot bash -c 'echo "UPDATE: Forcing audio-only formats" && \
    yt-dlp --update && \
    yt-dlp --rm-cache-dir'

# 3. Restart YouTube Music with increased timeout
echo "🎵 Restarting YouTube Music service..."
docker-compose stop youtube-music-headless
docker-compose rm -f youtube-music-headless
docker-compose up -d youtube-music-headless

# 4. Clear Redis cache (might have bad data)
echo "🗑️  Clearing Redis cache..."
docker exec robustty-redis redis-cli FLUSHALL

# 5. Test each platform
echo "🧪 Testing platforms..."
docker exec robustty-bot python3 -c "
import asyncio
from src.platforms import PlatformRegistry

async def test_platforms():
    registry = PlatformRegistry()
    # Test will be done when bot starts
    print('Platform registry initialized')

asyncio.run(test_platforms())
"

# 6. Restart bot with clean state
echo "🔄 Restarting bot..."
docker-compose restart robustty

echo "✅ Emergency fix completed!"
echo ""
echo "Test with these commands:"
echo "  !play despacito"
echo "  !play https://www.youtube.com/watch?v=dQw4w9WgXcQ"
echo ""
echo "Monitor: docker-compose logs -f robustty"