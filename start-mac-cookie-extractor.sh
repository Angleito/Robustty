#!/bin/bash
# Start Cookie Extractor on macOS
# This script starts the dedicated cookie extraction and sync service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🍪 Robustty Cookie Extractor for macOS${NC}"
echo "=========================================="

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please ensure your .env file exists with VPS configuration"
    exit 1
fi

# Load environment variables
source .env

# Verify required variables
if [ -z "$VPS_HOST" ] || [ "$VPS_HOST" = "your-vps-ip" ]; then
    echo -e "${RED}❌ Error: VPS_HOST not configured in .env${NC}"
    exit 1
fi

if [ ! -f "${SSH_KEY_PATH:-~/.ssh/yeet}" ]; then
    echo -e "${RED}❌ Error: SSH key not found at ${SSH_KEY_PATH:-~/.ssh/yeet}${NC}"
    exit 1
fi

# Check if Brave browser data exists
BRAVE_PATH="${BRAVE_BROWSER_PATH:-$HOME/Library/Application Support/BraveSoftware/Brave-Browser}"
if [ ! -d "$BRAVE_PATH" ]; then
    echo -e "${YELLOW}⚠️  Warning: Brave browser data not found at $BRAVE_PATH${NC}"
    echo "Cookie extraction may not work properly"
fi

echo -e "${BLUE}📍 Configuration:${NC}"
echo "  VPS Host: $VPS_HOST"
echo "  VPS User: ${VPS_USER:-root}"
echo "  SSH Key: ${SSH_KEY_PATH:-~/.ssh/yeet}"
echo "  Brave Path: $BRAVE_PATH"
echo "  Auto Sync: ${AUTO_SYNC_VPS:-true}"
echo ""

# Create necessary directories
mkdir -p ./cookies ./logs

# Check if service is already running
if docker ps | grep -q "robustty-cookie-extractor"; then
    echo -e "${YELLOW}⚠️  Cookie extractor is already running${NC}"
    echo "Stop it first with: docker-compose -f docker-compose.mac.yml down cookie-extractor"
    exit 1
fi

# Start the cookie extractor service
echo -e "${BLUE}🚀 Starting cookie extractor service...${NC}"
if docker-compose -f docker-compose.mac.yml up -d cookie-extractor; then
    echo -e "${GREEN}✅ Cookie extractor started successfully${NC}"
    echo ""
    echo -e "${BLUE}📋 Service Status:${NC}"
    docker-compose -f docker-compose.mac.yml ps cookie-extractor
    echo ""
    echo -e "${BLUE}📝 View logs with:${NC}"
    echo "  docker-compose -f docker-compose.mac.yml logs -f cookie-extractor"
    echo ""
    echo -e "${BLUE}🛑 Stop service with:${NC}"
    echo "  docker-compose -f docker-compose.mac.yml down cookie-extractor"
else
    echo -e "${RED}❌ Failed to start cookie extractor${NC}"
    exit 1
fi

# Show initial logs
echo -e "${BLUE}📊 Initial service logs:${NC}"
docker-compose -f docker-compose.mac.yml logs --tail=20 cookie-extractor