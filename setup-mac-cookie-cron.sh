#!/bin/bash
# Setup cron job for automatic cookie sync on macOS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_SCRIPT="$SCRIPT_DIR/scripts/sync-cookies-to-vps.sh"

echo -e "${BLUE}⏰ Setting up automatic cookie sync for macOS${NC}"
echo "==============================================="

# Check if sync script exists
if [ ! -f "$SYNC_SCRIPT" ]; then
    echo -e "${RED}❌ Error: Sync script not found at $SYNC_SCRIPT${NC}"
    exit 1
fi

# Make sure sync script is executable
chmod +x "$SYNC_SCRIPT"

# Check current cron jobs
echo -e "${BLUE}📋 Current cron jobs:${NC}"
crontab -l 2>/dev/null || echo "No existing cron jobs"
echo ""

# Create cron job entry
CRON_JOB="0 */2 * * * cd $SCRIPT_DIR && $SYNC_SCRIPT >> $SCRIPT_DIR/logs/cookie-sync-cron.log 2>&1"

# Check if job already exists
if crontab -l 2>/dev/null | grep -q "$SYNC_SCRIPT"; then
    echo -e "${YELLOW}⚠️  Cookie sync cron job already exists${NC}"
    echo "Current job:"
    crontab -l | grep "$SYNC_SCRIPT"
    echo ""
    read -p "Do you want to update it? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing cron job"
        exit 0
    fi
    
    # Remove existing job
    crontab -l | grep -v "$SYNC_SCRIPT" | crontab -
    echo -e "${BLUE}📝 Removed existing cron job${NC}"
fi

# Add new cron job
echo -e "${BLUE}📝 Adding new cron job...${NC}"
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"

# Verify cron job was added
echo -e "${GREEN}✅ Cron job added successfully!${NC}"
echo ""
echo -e "${BLUE}📋 Updated cron jobs:${NC}"
crontab -l
echo ""
echo -e "${BLUE}📍 Configuration:${NC}"
echo "  Schedule: Every 2 hours"
echo "  Script: $SYNC_SCRIPT"
echo "  Log: $SCRIPT_DIR/logs/cookie-sync-cron.log"
echo ""
echo -e "${BLUE}💡 Management commands:${NC}"
echo "  View logs: tail -f $SCRIPT_DIR/logs/cookie-sync-cron.log"
echo "  Manual run: $SYNC_SCRIPT"
echo "  Remove job: crontab -e (then delete the line)"
echo ""
echo -e "${BLUE}🔍 Test run:${NC}"
read -p "Do you want to run a test sync now? (Y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo -e "${BLUE}🧪 Running test sync...${NC}"
    "$SYNC_SCRIPT"
fi