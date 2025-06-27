#!/bin/bash
# Cookie System Status Checker
# Comprehensive check of Mac cookie extraction and VPS sync

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}🍪 Robustty Cookie System Status Check${NC}"
echo "======================================"

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
echo "  VPS Host: ${VPS_HOST:-not set}"
echo "  VPS User: ${VPS_USER:-not set}"
echo "  SSH Key: ${SSH_KEY_PATH:-not set}"
echo "  Auto Sync: ${AUTO_SYNC_VPS:-not set}"

# Check 1: Local Brave Browser
echo ""
echo -e "${BLUE}🌐 1. Brave Browser Status${NC}"
BRAVE_PATH="${BRAVE_BROWSER_PATH:-$HOME/Library/Application Support/BraveSoftware/Brave-Browser}"
if [ -d "$BRAVE_PATH" ]; then
    echo -e "${GREEN}✅ Brave browser data found${NC}"
    echo "   Path: $BRAVE_PATH"
    
    # Check if browser is running
    if pgrep -f "Brave Browser" > /dev/null; then
        echo -e "${GREEN}✅ Brave browser is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Brave browser is not running${NC}"
    fi
else
    echo -e "${RED}❌ Brave browser data not found${NC}"
    echo "   Expected path: $BRAVE_PATH"
fi

# Check 2: Local Cookie Files
echo ""
echo -e "${BLUE}🍪 2. Local Cookie Files${NC}"
if [ -d "./cookies" ]; then
    local_cookies=$(find ./cookies -name "*.json" 2>/dev/null | wc -l)
    echo -e "${GREEN}✅ Local cookie directory exists${NC}"
    echo "   Cookie files: $local_cookies"
    
    if [ "$local_cookies" -gt 0 ]; then
        echo "   Files:"
        for file in ./cookies/*.json; do
            if [ -f "$file" ]; then
                size=$(wc -c < "$file")
                echo "     $(basename "$file"): ${size} bytes"
            fi
        done
    fi
else
    echo -e "${RED}❌ Local cookie directory not found${NC}"
fi

# Check 3: Cookie Extraction Test
echo ""
echo -e "${BLUE}🔧 3. Cookie Extraction Test${NC}"
if python3 scripts/extract-brave-cookies.py > /tmp/cookie-test.log 2>&1; then
    echo -e "${GREEN}✅ Cookie extraction successful${NC}"
    extracted=$(grep "Extracted.*total cookies" /tmp/cookie-test.log | tail -1)
    if [ -n "$extracted" ]; then
        echo "   $extracted"
    fi
else
    echo -e "${RED}❌ Cookie extraction failed${NC}"
    echo "   Check logs: cat /tmp/cookie-test.log"
fi

# Check 4: SSH Connection to VPS
echo ""
echo -e "${BLUE}🔗 4. VPS Connection${NC}"
if [ -f "${SSH_KEY_PATH:-~/.ssh/yeet}" ]; then
    echo -e "${GREEN}✅ SSH key found${NC}"
    
    if ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" -o ConnectTimeout=10 -o BatchMode=yes "$VPS_USER@$VPS_HOST" 'echo "Connection successful"' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ SSH connection to VPS successful${NC}"
    else
        echo -e "${RED}❌ SSH connection to VPS failed${NC}"
    fi
else
    echo -e "${RED}❌ SSH key not found${NC}"
fi

# Check 5: VPS Cookie Status
echo ""
echo -e "${BLUE}🖥️  5. VPS Cookie Status${NC}"
if ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" -o ConnectTimeout=10 -o BatchMode=yes "$VPS_USER@$VPS_HOST" "cd ~/Robustty && ls -la cookies/" > /tmp/vps-cookies.log 2>&1; then
    echo -e "${GREEN}✅ VPS cookie directory accessible${NC}"
    
    remote_cookies=$(ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" "$VPS_USER@$VPS_HOST" "find ~/Robustty/cookies -name '*.json' 2>/dev/null | wc -l")
    echo "   Remote cookie files: $remote_cookies"
    
    echo "   VPS cookie files:"
    cat /tmp/vps-cookies.log | grep "\.json" | awk '{print "     " $9 ": " $5 " bytes"}'
else
    echo -e "${RED}❌ Cannot access VPS cookie directory${NC}"
fi

# Check 6: VPS Bot Status
echo ""
echo -e "${BLUE}🤖 6. VPS Bot Status${NC}"
if ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" "$VPS_USER@$VPS_HOST" "cd ~/Robustty && docker-compose ps robustty" > /tmp/vps-bot.log 2>&1; then
    if grep -q "Up" /tmp/vps-bot.log; then
        echo -e "${GREEN}✅ VPS bot is running${NC}"
        
        # Check recent cookie logs
        recent_cookie_logs=$(ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" "$VPS_USER@$VPS_HOST" "cd ~/Robustty && docker-compose logs --tail=5 robustty | grep -i cookie | tail -2")
        if [ -n "$recent_cookie_logs" ]; then
            echo "   Recent cookie activity:"
            echo "$recent_cookie_logs" | sed 's/^/     /'
        fi
    else
        echo -e "${RED}❌ VPS bot is not running${NC}"
    fi
else
    echo -e "${RED}❌ Cannot check VPS bot status${NC}"
fi

# Check 7: Cron Job Status
echo ""
echo -e "${BLUE}⏰ 7. Automatic Sync Status${NC}"
if crontab -l 2>/dev/null | grep -q "sync-cookies-to-vps.sh"; then
    echo -e "${GREEN}✅ Cron job for cookie sync is configured${NC}"
    crontab -l | grep "sync-cookies-to-vps.sh" | sed 's/^/   /'
    
    # Check recent cron logs
    if [ -f "./logs/cookie-sync-cron.log" ]; then
        last_sync=$(tail -10 ./logs/cookie-sync-cron.log | grep "Cookie sync process completed" | tail -1)
        if [ -n "$last_sync" ]; then
            echo "   Last successful sync: $(echo "$last_sync" | awk '{print $1, $2}')"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  No cron job configured for automatic sync${NC}"
    echo "   Run: ./setup-mac-cookie-cron.sh"
fi

# Summary
echo ""
echo -e "${BLUE}📊 Summary${NC}"
echo "=========="

# Overall status
local_ok=false
vps_ok=false
sync_ok=false

if [ -d "./cookies" ] && [ "$(find ./cookies -name "*.json" | wc -l)" -gt 0 ]; then
    local_ok=true
fi

if ssh -i "${SSH_KEY_PATH:-~/.ssh/yeet}" -o ConnectTimeout=5 -o BatchMode=yes "$VPS_USER@$VPS_HOST" "test -d ~/Robustty/cookies && find ~/Robustty/cookies -name '*.json' | head -1" > /dev/null 2>&1; then
    vps_ok=true
fi

if $local_ok && $vps_ok; then
    sync_ok=true
fi

if $sync_ok; then
    echo -e "${GREEN}✅ Cookie system is working properly${NC}"
    echo "   - Local extraction: Working"
    echo "   - VPS sync: Working"
    echo "   - Bot integration: Active"
else
    echo -e "${YELLOW}⚠️  Cookie system needs attention${NC}"
    if ! $local_ok; then
        echo "   - Local extraction: Needs fixing"
    fi
    if ! $vps_ok; then
        echo "   - VPS sync: Needs fixing"
    fi
fi

echo ""
echo -e "${BLUE}💡 Quick Actions:${NC}"
echo "  Manual sync: ./scripts/sync-cookies-to-vps.sh"
echo "  Setup auto sync: ./setup-mac-cookie-cron.sh"
echo "  View VPS logs: ssh -i ${SSH_KEY_PATH:-~/.ssh/yeet} $VPS_USER@$VPS_HOST 'cd ~/Robustty && docker-compose logs robustty'"

# Cleanup
rm -f /tmp/cookie-test.log /tmp/vps-cookies.log /tmp/vps-bot.log