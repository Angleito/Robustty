#!/bin/bash
set -e

echo "=== Robustty Docker Build Fix ==="
echo "This script will build and run Robustty without browser automation packages"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Creating from template..."
    cp .env.example .env
    echo "Please edit .env and add your Discord bot token"
    exit 1
fi

# Find available port
echo "Finding available port..."
STREAM_PORT=$(./scripts/find-available-port.sh 5000)
if [ $? -ne 0 ]; then
    echo "Error: Could not find available port"
    exit 1
fi
echo "Using port $STREAM_PORT for stream service"

# Export the port for docker-compose
export STREAM_PORT

# Create necessary directories
echo "Creating directories..."
mkdir -p logs data cookies

# Create the fixed Dockerfile
echo "Creating optimized Dockerfile..."
cat > docker/bot/Dockerfile.optimized << 'EOF'
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install core dependencies first
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
        "discord.py==2.3.2" \
        "PyNaCl==1.5.0" \
        "aiohttp==3.9.5" \
        "python-dotenv==1.0.0" \
        "psutil>=5.8.0" \
        "redis==5.0.1"

# Install media and parsing libraries
RUN pip install --no-cache-dir \
        "yt-dlp==2023.10.13" \
        "ffmpeg-python==0.2.0" \
        "beautifulsoup4==4.12.2" \
        "lxml==4.9.3" \
        "PyYAML==6.0.1"

# Install remaining packages
RUN pip install --no-cache-dir \
        "google-api-python-client==2.100.0" \
        "google-auth==2.23.0" \
        "aiofiles==23.2.1" \
        "colorlog==6.7.0" \
        "typing-extensions==4.9.0" \
        "flask==3.0.0" \
        "aiodns==3.1.1" \
        "charset-normalizer==3.4.2"

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create directories and files
RUN mkdir -p logs data cookies && \
    echo '[]' > cookies/manual_cookies.json

ENV PYTHONPATH=/app/src
CMD ["python", "-m", "src.main"]
EOF

# Create minimal docker-compose with dynamic port
echo "Creating minimal docker-compose..."
cat > docker-compose.minimal.yml << EOF
services:
  bot:
    build:
      context: .
      dockerfile: docker/bot/Dockerfile.optimized
    container_name: robustty-bot
    restart: unless-stopped
    environment:
      - DISCORD_TOKEN=\${DISCORD_TOKEN}
      - YOUTUBE_API_KEY=\${YOUTUBE_API_KEY}
      - LOG_LEVEL=\${LOG_LEVEL:-INFO}
      - SEARCH_TIMEOUT=\${SEARCH_TIMEOUT:-30}
      - STREAM_TIMEOUT=\${STREAM_TIMEOUT:-300}
      - MAX_QUEUE_SIZE=\${MAX_QUEUE_SIZE:-100}
      - STREAM_SERVICE_URL=http://stream-service:5000
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
      - ./data:/app/data
      - ./cookies:/app/cookies
    depends_on:
      - redis
      - stream-service
    networks:
      - bot-network

  stream-service:
    build:
      context: .
      dockerfile: docker/stream-service/Dockerfile
    container_name: robustty-stream
    restart: unless-stopped
    ports:
      - "${STREAM_PORT}:5000"
    environment:
      - FLASK_ENV=production
    networks:
      - bot-network

  redis:
    image: redis:alpine
    container_name: robustty-redis
    restart: unless-stopped
    volumes:
      - redis-data:/data
    networks:
      - bot-network

networks:
  bot-network:
    driver: bridge

volumes:
  redis-data:
  cookies:
EOF

# Build and run
echo ""
echo "Building Docker images..."
DOCKER_BUILDKIT=1 docker-compose -f docker-compose.minimal.yml build --progress=plain

echo ""
echo "Starting services..."
docker-compose -f docker-compose.minimal.yml up -d

echo ""
echo "=== Build complete! ==="
echo ""
echo "Bot is running. Stream service is on port $STREAM_PORT"
echo ""
echo "Check status with:"
echo "  docker-compose -f docker-compose.minimal.yml ps"
echo ""
echo "View logs with:"
echo "  docker logs -f robustty-bot"
echo ""
echo "Stop the bot with:"
echo "  docker-compose -f docker-compose.minimal.yml down"
echo ""
echo "Note: Cookie extraction is disabled. If you need cookies:"
echo "1. Extract them from your browser manually"
echo "2. Save them to cookies/manual_cookies.json"
echo "3. Restart the bot"