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

# Run network diagnostics before setup
echo "🔍 Running network diagnostics..."
if [[ -f scripts/diagnose-vps-network.sh ]]; then
    echo "📊 Running comprehensive network diagnostics..."
    # Run with timeout to prevent hanging
    timeout 60 bash scripts/diagnose-vps-network.sh || {
        echo "⚠️  Diagnostics timed out or failed, continuing with setup..."
    }
else
    echo "📋 Running basic DNS checks..."
    # Basic DNS resolution test
    DISCORD_ENDPOINTS=("gateway-us-east1-d.discord.gg" "discord.com")
    DNS_ISSUES=false
    
    for endpoint in "${DISCORD_ENDPOINTS[@]}"; do
        if ! nslookup "$endpoint" >/dev/null 2>&1; then
            echo "❌ DNS resolution failed for $endpoint"
            DNS_ISSUES=true
        else
            echo "✅ DNS resolution OK for $endpoint"
        fi
    done
    
    # Test HTTPS connectivity
    if command -v nc >/dev/null 2>&1; then
        if ! timeout 10 nc -z gateway-us-east1-d.discord.gg 443 >/dev/null 2>&1; then
            echo "❌ Cannot connect to Discord gateway on port 443"
            DNS_ISSUES=true
        else
            echo "✅ Discord gateway HTTPS is accessible"
        fi
    fi
    
    if [[ "$DNS_ISSUES" = true ]]; then
        echo ""
        echo "⚠️  NETWORK CONNECTIVITY ISSUES DETECTED!"
        echo "The Discord bot may fail to connect due to DNS/network problems."
        echo ""
        echo "Common fixes:"
        echo "1. Add public DNS servers to /etc/resolv.conf:"
        echo "   echo 'nameserver 8.8.8.8' | sudo tee -a /etc/resolv.conf"
        echo "2. Check firewall settings (allow outbound ports 53, 443)"
        echo "3. Verify VPS security groups allow outbound internet access"
        echo ""
        read -p "Continue with setup despite network issues? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Setup cancelled. Please fix network issues first."
            exit 1
        fi
    fi
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs data cookies

# Set permissions
chown -R $(whoami):$(whoami) logs data cookies
chmod 755 logs data cookies

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down 2>/dev/null || true

# Pull latest images and build
echo "🔨 Building containers..."
docker-compose build --no-cache

# Start services
echo "🚀 Starting services..."
docker-compose up -d

# Show status
echo "📊 Service status:"
docker-compose ps

echo "✅ VPS setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Sync cookies from your local machine using sync-cookies-vps.sh"
echo "   2. Monitor logs: docker-compose logs -f"
echo "   3. Check health: docker-compose exec robustty python -c 'print(\"Bot is running\")'"