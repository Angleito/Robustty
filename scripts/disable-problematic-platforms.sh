#!/bin/bash

# Temporarily disable problematic platforms to get music working

echo "🛑 Disabling Problematic Platforms"
echo "=================================="

cd /root/Robustty

# Create a minimal working configuration
echo "📝 Creating minimal configuration..."

# Backup current .env
cp .env .env.backup

# Create new minimal .env focusing on what works
cat > .env << 'EOF'
# Discord Configuration
DISCORD_TOKEN=${DISCORD_TOKEN}
YOUTUBE_API_KEY=${YOUTUBE_API_KEY}

# Disable problematic platforms temporarily
YOUTUBE_MUSIC_ENABLED=false
ODYSEE_ENABLED=false
PEERTUBE_ENABLED=false
RUMBLE_ENABLED=false

# Only use YouTube with yt-dlp
YOUTUBE_ENABLED=true
YOUTUBE_USE_API=false

# Increase all timeouts
SEARCH_TIMEOUT=120
STREAM_TIMEOUT=600
YOUTUBE_API_TIMEOUT=60

# Logging
LOG_LEVEL=WARNING

# Redis
REDIS_URL=redis://redis:6379

# Performance
MAX_QUEUE_SIZE=10
EOF

# Copy Discord token from backup
DISCORD_TOKEN=$(grep "^DISCORD_TOKEN=" .env.backup | cut -d'=' -f2)
YOUTUBE_API_KEY=$(grep "^YOUTUBE_API_KEY=" .env.backup | cut -d'=' -f2)

# Update .env with actual tokens
sed -i "s/\${DISCORD_TOKEN}/$DISCORD_TOKEN/" .env
sed -i "s/\${YOUTUBE_API_KEY}/$YOUTUBE_API_KEY/" .env

# Restart everything fresh
echo "🔄 Restarting with minimal config..."
docker-compose down
docker-compose up -d redis
sleep 5
docker-compose up -d robustty

echo "✅ Minimal configuration applied!"
echo ""
echo "Only YouTube (via yt-dlp) is enabled now"
echo "This should eliminate all the API timeout issues"
echo ""
echo "Monitor: docker-compose logs -f robustty"