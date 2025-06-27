#!/bin/bash
# Fix VPS Cookie Issues - Complete Solution

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Robustty VPS Cookie Fix${NC}"
echo "=========================="

# Load environment variables
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo -e "${GREEN}✅ Environment variables loaded${NC}"
else
    echo -e "${RED}❌ .env file not found${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}📍 Configuration:${NC}"
echo "  VPS Host: ${VPS_HOST}"
echo "  VPS User: ${VPS_USER:-root}"
echo "  SSH Key: ${SSH_KEY_PATH:-~/.ssh/yeet}"

# Step 1: Setup VPS environment
echo ""
echo -e "${BLUE}🖥️  Step 1: Setting up VPS environment...${NC}"
if scp -i "${SSH_KEY_PATH:-~/.ssh/yeet}" scripts/vps-setup.sh "${VPS_USER:-root}@${VPS_HOST}:/tmp/"; then
    if ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" "${VPS_USER:-root}@${VPS_HOST}" "chmod +x /tmp/vps-setup.sh && /tmp/vps-setup.sh"; then
        echo -e "${GREEN}✅ VPS environment setup completed${NC}"
    else
        echo -e "${RED}❌ VPS setup failed${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Failed to copy setup script to VPS${NC}"
    exit 1
fi

# Step 2: Stop VPS bot to fix volume mounting
echo ""
echo -e "${BLUE}🛑 Step 2: Stopping VPS bot to fix volume mounting...${NC}"
ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" "${VPS_USER:-root}@${VPS_HOST}" "cd ~/Robustty && docker-compose down" || true

# Step 3: Copy updated docker-compose.yml to VPS
echo ""
echo -e "${BLUE}📋 Step 3: Updating VPS configuration...${NC}"
scp -i "${SSH_KEY_PATH:-~/.ssh/yeet}" docker-compose.yml "${VPS_USER:-root}@${VPS_HOST}:~/Robustty/"
scp -i "${SSH_KEY_PATH:-~/.ssh/yeet}" .env "${VPS_USER:-root}@${VPS_HOST}:~/Robustty/"

# Step 4: Sync fresh cookies
echo ""
echo -e "${BLUE}🍪 Step 4: Syncing fresh cookies...${NC}"
./scripts/sync-cookies-to-vps.sh

# Step 5: Start VPS bot with new configuration
echo ""
echo -e "${BLUE}🚀 Step 5: Starting VPS bot with new configuration...${NC}"
ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" "${VPS_USER:-root}@${VPS_HOST}" "cd ~/Robustty && docker-compose up -d --build"

# Step 6: Wait and check status
echo ""
echo -e "${BLUE}⏳ Step 6: Waiting for services to start...${NC}"
sleep 10

echo ""
echo -e "${BLUE}📊 Step 7: Checking VPS status...${NC}"
ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" "${VPS_USER:-root}@${VPS_HOST}" "cd ~/Robustty && docker-compose ps"

echo ""
echo -e "${BLUE}🍪 Step 8: Verifying cookie files...${NC}"
ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" "${VPS_USER:-root}@${VPS_HOST}" "ls -la ~/Robustty/cookies/"

echo ""
echo -e "${GREEN}🎉 VPS cookie fix completed!${NC}"
echo -e "${BLUE}📋 Summary:${NC}"
echo "  - Fixed Docker volume mounting issue"
echo "  - Improved DNS configuration"
echo "  - Synced fresh cookies to VPS"
echo "  - Restarted bot with new configuration"
echo ""
echo -e "${BLUE}💡 Monitor with:${NC}"
echo "  ssh -i ${SSH_KEY_PATH:-~/.ssh/yeet} ${VPS_USER:-root}@${VPS_HOST} 'cd ~/Robustty && docker-compose logs -f robustty'"