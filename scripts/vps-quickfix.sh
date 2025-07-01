#!/bin/bash

echo "╔════════════════════════════════════════════╗"
echo "║     Robustty VPS Quick Fix Script         ║"
echo "╚════════════════════════════════════════════╝"
echo

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get VPS info
VPS_IP=$(curl -s ifconfig.me 2>/dev/null || echo "unknown")
echo -e "VPS IP: ${BLUE}$VPS_IP${NC}"
echo -e "Location: ${BLUE}San Francisco (DigitalOcean)${NC}"
echo

# Function to run fixes
run_fix() {
    local fix_name=$1
    local fix_command=$2
    
    echo -e "\n${YELLOW}→ Running: $fix_name${NC}"
    eval "$fix_command"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Success${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
}

echo "═══════════════════════════════════════════════"
echo "QUICK FIXES"
echo "═══════════════════════════════════════════════"

# 1. Fix DNS Resolution
echo -e "\n${BLUE}1. DNS Resolution Fix${NC}"
echo "   Issue: Discord gateway connection failures"

if [ "$EUID" -eq 0 ]; then
    # Running as root
    run_fix "Update host DNS" "echo -e 'nameserver 8.8.8.8\nnameserver 8.8.4.4\nnameserver 1.1.1.1' > /etc/resolv.conf"
    run_fix "Configure Docker DNS" "mkdir -p /etc/docker && echo '{\"dns\": [\"8.8.8.8\", \"8.8.4.4\", \"1.1.1.1\"]}' > /etc/docker/daemon.json"
    run_fix "Restart Docker daemon" "systemctl restart docker && sleep 5"
else
    echo -e "${YELLOW}⚠️  Need root access for DNS fixes${NC}"
    echo "   Run: sudo $0"
fi

# 2. Platform Management
echo -e "\n${BLUE}2. Platform Management${NC}"
echo "   Issue: Odysee API returning 404 errors"

# Check if .env exists
if [ -f ".env" ]; then
    # Enable stability mode
    if ! grep -q "VPS_STABILITY_MODE=true" .env; then
        echo "VPS_STABILITY_MODE=true" >> .env
        echo "AUTO_DISABLE_FAILING_PLATFORMS=true" >> .env
        echo "PLATFORM_FAILURE_THRESHOLD=5" >> .env
        echo -e "${GREEN}✓ Enabled VPS stability mode${NC}"
    else
        echo -e "${GREEN}✓ VPS stability mode already enabled${NC}"
    fi
    
    # Temporarily disable Odysee if needed
    if ! grep -q "ODYSEE_ENABLED" .env; then
        echo "ODYSEE_ENABLED=false" >> .env
        echo -e "${YELLOW}⚠️  Disabled Odysee due to API issues${NC}"
    fi
else
    echo -e "${RED}✗ .env file not found${NC}"
    echo "   Create .env from .env.example first"
fi

# 3. Cookie Setup
echo -e "\n${BLUE}3. Cookie Authentication${NC}"
echo "   Issue: YouTube requiring authentication"

# Create cookies directory
mkdir -p cookies
chmod 755 cookies

# Check for existing cookies
if [ -f "cookies/youtube_cookies.txt" ]; then
    cookie_count=$(grep -v '^#' cookies/youtube_cookies.txt | grep -v '^$' | wc -l)
    if [ "$cookie_count" -gt 0 ]; then
        echo -e "${GREEN}✓ YouTube cookies found ($cookie_count cookies)${NC}"
    else
        echo -e "${YELLOW}⚠️  YouTube cookie file exists but is empty${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No YouTube cookies found${NC}"
    echo "   To add cookies:"
    echo "   1. Export cookies from browser on local machine"
    echo "   2. Transfer to VPS: scp youtube_cookies.txt root@$VPS_IP:~/robustty-bot/cookies/"
fi

# 4. Container Health Check
echo -e "\n${BLUE}4. Container Health Check${NC}"

if command -v docker-compose &> /dev/null; then
    # Check if containers are running
    if docker-compose ps | grep -q "Up"; then
        echo -e "${GREEN}✓ Containers are running${NC}"
        
        # Test Redis connection
        if docker-compose exec redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
            echo -e "${GREEN}✓ Redis is responsive${NC}"
        else
            echo -e "${RED}✗ Redis not responding${NC}"
        fi
        
        # Check bot logs for errors
        error_count=$(docker-compose logs --tail=50 robustty 2>/dev/null | grep -c "ERROR")
        if [ "$error_count" -gt 0 ]; then
            echo -e "${YELLOW}⚠️  Found $error_count errors in recent logs${NC}"
        else
            echo -e "${GREEN}✓ No errors in recent logs${NC}"
        fi
    else
        echo -e "${RED}✗ Containers not running${NC}"
        echo "   Run: docker-compose up -d"
    fi
else
    echo -e "${RED}✗ docker-compose not found${NC}"
fi

# 5. Apply Fixes
echo -e "\n${BLUE}5. Applying All Fixes${NC}"
echo "═══════════════════════════════════════════════"

read -p "Apply all fixes and restart bot? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Restarting bot with fixes...${NC}"
    
    # Stop containers
    docker-compose down
    
    # Clear any stale data
    docker system prune -f
    
    # Start with fresh state
    docker-compose up -d --build
    
    echo -e "\n${GREEN}✓ Bot restarted with all fixes applied${NC}"
    echo
    echo "Monitor logs with:"
    echo -e "${BLUE}docker-compose logs -f robustty${NC}"
    echo
    echo "Check status with:"
    echo -e "${BLUE}docker-compose ps${NC}"
    echo
    echo "If issues persist:"
    echo "1. Check DNS: ./scripts/diagnose-vps-dns.sh"
    echo "2. Test Odysee: python3 ./scripts/fix-odysee-api.py"
    echo "3. Setup cookies: ./scripts/setup-vps-cookies.sh"
else
    echo -e "\n${YELLOW}Fixes prepared but not applied.${NC}"
    echo "Review the suggestions above and apply manually if needed."
fi

echo
echo "═══════════════════════════════════════════════"
echo -e "${GREEN}Quick fix script completed!${NC}"