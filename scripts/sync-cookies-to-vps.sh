#!/bin/bash
# Cookie Sync Script - Mac to VPS
# Extracts cookies on Mac and syncs them to VPS

set -e

# Configuration (can be overridden by environment variables)
VPS_HOST="${VPS_HOST:-your-vps-ip}"
VPS_USER="${VPS_USER:-root}"
VPS_PATH="${VPS_PATH:-~/Robustty/cookies}"
SSH_KEY="${SSH_KEY:-~/.ssh/id_rsa}"
LOCAL_COOKIE_DIR="./cookies"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🍪 Robustty Cookie Sync to VPS${NC}"
echo "=================================="

# Check if VPS_HOST is configured
if [ "$VPS_HOST" = "your-vps-ip" ]; then
    echo -e "${RED}❌ Error: VPS_HOST not configured${NC}"
    echo "Please set VPS_HOST environment variable or edit this script:"
    echo "export VPS_HOST=your.vps.ip.address"
    exit 1
fi

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ Error: SSH key not found at $SSH_KEY${NC}"
    echo "Please ensure your SSH key exists or set SSH_KEY environment variable"
    exit 1
fi

# Check if local cookie directory exists
if [ ! -d "$LOCAL_COOKIE_DIR" ]; then
    echo -e "${YELLOW}⚠️  Creating local cookie directory...${NC}"
    mkdir -p "$LOCAL_COOKIE_DIR"
fi

echo -e "${BLUE}📍 Configuration:${NC}"
echo "  VPS Host: $VPS_HOST"
echo "  VPS User: $VPS_USER"
echo "  VPS Path: $VPS_PATH"
echo "  SSH Key:  $SSH_KEY"
echo "  Local:    $LOCAL_COOKIE_DIR"
echo ""

# Step 1: Extract cookies locally
echo -e "${BLUE}🔍 Step 1: Extracting cookies from Brave browser...${NC}"
if python3 scripts/extract-brave-cookies.py; then
    echo -e "${GREEN}✅ Cookie extraction completed${NC}"
else
    echo -e "${RED}❌ Cookie extraction failed${NC}"
    exit 1
fi

# Step 2: Check if we have cookies to sync
cookie_files=$(find "$LOCAL_COOKIE_DIR" -name "*.json" 2>/dev/null | wc -l)
if [ "$cookie_files" -eq 0 ]; then
    echo -e "${RED}❌ No cookie files found to sync${NC}"
    exit 1
fi

echo -e "${GREEN}📦 Found $cookie_files cookie files to sync${NC}"

# Step 3: Test SSH connection
echo -e "${BLUE}🔗 Step 2: Testing SSH connection to VPS...${NC}"
if ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o BatchMode=yes "$VPS_USER@$VPS_HOST" 'echo "SSH connection successful"'; then
    echo -e "${GREEN}✅ SSH connection successful${NC}"
else
    echo -e "${RED}❌ SSH connection failed${NC}"
    echo "Please check:"
    echo "  - VPS is running and accessible"
    echo "  - SSH key is correct and added to VPS"
    echo "  - VPS_HOST and VPS_USER are correct"
    exit 1
fi

# Step 4: Create remote directory if it doesn't exist
echo -e "${BLUE}📁 Step 3: Ensuring remote directory exists...${NC}"
ssh -i "$SSH_KEY" "$VPS_USER@$VPS_HOST" "mkdir -p $VPS_PATH"

# Step 5: Sync cookies to VPS
echo -e "${BLUE}🚀 Step 4: Syncing cookies to VPS...${NC}"
if rsync -avz --progress -e "ssh -i $SSH_KEY" "$LOCAL_COOKIE_DIR/" "$VPS_USER@$VPS_HOST:$VPS_PATH/"; then
    echo -e "${GREEN}✅ Cookie sync completed successfully${NC}"
else
    echo -e "${RED}❌ Cookie sync failed${NC}"
    exit 1
fi

# Step 6: Verify sync
echo -e "${BLUE}🔍 Step 5: Verifying sync...${NC}"
remote_files=$(ssh -i "$SSH_KEY" "$VPS_USER@$VPS_HOST" "find $VPS_PATH -name '*.json' 2>/dev/null | wc -l")
echo -e "${GREEN}📊 Remote VPS now has $remote_files cookie files${NC}"

# Step 7: Restart VPS bot to pick up new cookies
echo -e "${BLUE}🔄 Step 6: Restarting bot on VPS to pick up new cookies...${NC}"
if ssh -i "$SSH_KEY" "$VPS_USER@$VPS_HOST" "cd ~/Robustty && docker-compose restart robustty"; then
    echo -e "${GREEN}✅ VPS bot restarted successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Failed to restart VPS bot (cookies synced but bot may need manual restart)${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Cookie sync process completed!${NC}"
echo -e "${BLUE}📋 Summary:${NC}"
echo "  - Extracted cookies from local Brave browser"
echo "  - Synced $cookie_files cookie files to VPS"
echo "  - VPS bot restarted to use new cookies"
echo ""
echo -e "${YELLOW}💡 To automate this process, you can:${NC}"
echo "  1. Add this script to a cron job on your Mac"
echo "  2. Run it manually when you want to update VPS cookies"
echo "  3. Set up the cookie service to run automatically"