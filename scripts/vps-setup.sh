#!/bin/bash
# VPS Setup Script - Prepare VPS environment for cookie sync

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🖥️  Robustty VPS Setup${NC}"
echo "====================="

# Create necessary directories
echo -e "${BLUE}📁 Creating directories...${NC}"
mkdir -p ~/Robustty/cookies ~/Robustty/logs ~/Robustty/data

# Set proper permissions
echo -e "${BLUE}🔒 Setting permissions...${NC}"
chown -R 1000:1000 ~/Robustty/cookies ~/Robustty/logs ~/Robustty/data 2>/dev/null || true
chmod 755 ~/Robustty/cookies ~/Robustty/logs ~/Robustty/data

# Create empty cookie files if they don't exist
echo -e "${BLUE}🍪 Initializing cookie files...${NC}"
for platform in youtube rumble odysee peertube; do
    cookie_file="$HOME/Robustty/cookies/${platform}_cookies.json"
    if [ ! -f "$cookie_file" ]; then
        echo "[]" > "$cookie_file"
        chown 1000:1000 "$cookie_file" 2>/dev/null || true
        echo -e "${GREEN}✅ Created ${platform}_cookies.json${NC}"
    else
        echo -e "${YELLOW}⚠️  ${platform}_cookies.json already exists${NC}"
    fi
done

# Check Docker and Docker Compose
echo -e "${BLUE}🐳 Checking Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker is installed${NC}"
    docker --version
else
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✅ Docker Compose is installed${NC}"
    docker-compose --version
else
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Fix DNS resolution issues
echo -e "${BLUE}🌐 Configuring DNS...${NC}"
if [ -f "/etc/resolv.conf" ]; then
    cp /etc/resolv.conf /etc/resolv.conf.backup
    echo "nameserver 1.1.1.1" > /etc/resolv.conf
    echo "nameserver 1.0.0.1" >> /etc/resolv.conf
    echo "nameserver 8.8.8.8" >> /etc/resolv.conf
    echo "nameserver 8.8.4.4" >> /etc/resolv.conf
    echo -e "${GREEN}✅ DNS configured with Cloudflare and Google${NC}"
fi

# Configure system settings for better Docker performance
echo -e "${BLUE}⚙️  Optimizing system settings...${NC}"

# Memory overcommit for Redis
if ! grep -q "vm.overcommit_memory = 1" /etc/sysctl.conf; then
    echo "vm.overcommit_memory = 1" >> /etc/sysctl.conf
    sysctl vm.overcommit_memory=1
    echo -e "${GREEN}✅ Memory overcommit enabled${NC}"
fi

# Increase max connections
if ! grep -q "net.core.somaxconn = 1024" /etc/sysctl.conf; then
    echo "net.core.somaxconn = 1024" >> /etc/sysctl.conf
    sysctl net.core.somaxconn=1024
    echo -e "${GREEN}✅ Max connections increased${NC}"
fi

echo ""
echo -e "${GREEN}🎉 VPS setup completed!${NC}"
echo -e "${BLUE}📋 What was configured:${NC}"
echo "  - Created cookie, log, and data directories"
echo "  - Set proper permissions (1000:1000)"
echo "  - Initialized empty cookie files"
echo "  - Configured DNS for better connectivity"
echo "  - Optimized system settings for Docker"
echo ""
echo -e "${BLUE}💡 Next steps:${NC}"
echo "  1. Upload your .env file to ~/Robustty/"
echo "  2. Run: cd ~/Robustty && docker-compose up -d"
echo "  3. Sync cookies from Mac with: ./scripts/sync-cookies-to-vps.sh"