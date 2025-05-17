#!/bin/bash
set -e

echo "Running Robustty in minimal mode (without browser automation)..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.example to .env and add your bot token"
    exit 1
fi

# Create necessary directories
mkdir -p logs data cookies

# Create manual cookie template if it doesn't exist
if [ ! -f cookies/manual_cookies.json ]; then
    echo "[]" > cookies/manual_cookies.json
    echo "Created empty cookies/manual_cookies.json"
fi

# Use the minimal docker-compose
if [ -f docker-compose.minimal.yml ]; then
    echo "Starting with minimal configuration..."
    docker-compose -f docker-compose.minimal.yml up -d
else
    echo "Warning: docker-compose.minimal.yml not found, using standard configuration"
    # Comment out cookie-extractor in standard compose
    sed 's/cookie-extractor:/#cookie-extractor:/g' docker-compose.yml > docker-compose.tmp.yml
    docker-compose -f docker-compose.tmp.yml up -d
    rm docker-compose.tmp.yml
fi

echo "Bot is starting..."
echo "Check logs with: docker logs robustty-bot"
echo ""
echo "If you need cookies for YouTube:"
echo "1. Extract cookies from your browser"
echo "2. Save them to cookies/manual_cookies.json"
echo "3. Restart the bot"