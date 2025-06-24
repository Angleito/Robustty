#!/bin/bash

# VPS Setup Script for Robustty Discord Bot
# This script sets up the VPS environment for running the bot

set -e

echo "🚀 Setting up Robustty Discord Bot on VPS..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)" 
   exit 1
fi

# Check if .env file exists
if [[ ! -f .env ]]; then
    echo "❌ .env file not found. Please create it with your Discord token and API keys."
    echo "   Copy .env.example and edit it with your credentials."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs data cookies

# Set permissions
chown -R $(whoami):$(whoami) logs data cookies
chmod 755 logs data cookies

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.vps.yml down 2>/dev/null || true

# Pull latest images and build
echo "🔨 Building VPS container..."
docker-compose -f docker-compose.vps.yml build --no-cache

# Start services
echo "🚀 Starting services..."
docker-compose -f docker-compose.vps.yml up -d

# Show status
echo "📊 Service status:"
docker-compose -f docker-compose.vps.yml ps

echo "✅ VPS setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Sync cookies from your local machine using sync-cookies-vps.sh"
echo "   2. Monitor logs: docker-compose -f docker-compose.vps.yml logs -f"
echo "   3. Check health: docker-compose -f docker-compose.vps.yml exec robustty python -c 'print(\"Bot is running\")'"