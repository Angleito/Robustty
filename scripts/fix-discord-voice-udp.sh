#!/bin/bash

# Fix Discord Voice UDP Ports for VPS
# This script configures the firewall to allow Discord voice UDP traffic

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================="
echo "🎤 Discord Voice UDP Port Configuration"
echo "========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[ERROR]${NC} This script must be run as root (use sudo)"
   exit 1
fi

echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} Checking current firewall status..."

# Check if ufw is installed
if ! command -v ufw &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} UFW not installed. Installing..."
    apt-get update && apt-get install -y ufw
fi

# Enable UFW if not already enabled
if ! ufw status | grep -q "Status: active"; then
    echo -e "${YELLOW}[WARNING]${NC} UFW is not active. Enabling..."
    ufw --force enable
fi

echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} Current UDP rules:"
ufw status | grep udp || echo "No UDP rules configured"

echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} Adding Discord voice UDP port range..."

# Allow Discord voice UDP ports (50000-65535)
# Note: This is a large range but required for Discord voice
ufw allow 50000:65535/udp comment "Discord voice RTP"

# Allow DNS UDP (required for domain resolution)
ufw allow out 53/udp comment "DNS queries"

# Allow NTP UDP (time synchronization)
ufw allow out 123/udp comment "NTP time sync"

# Allow HTTPS (Discord API)
ufw allow out 443/tcp comment "HTTPS/Discord API"

# Allow HTTP (for some CDN redirects)
ufw allow out 80/tcp comment "HTTP"

# Reload firewall
echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} Reloading firewall..."
ufw reload

echo -e "${GREEN}[SUCCESS]${NC} Discord voice UDP ports configured!"

echo -e "\n${BLUE}Current firewall status:${NC}"
ufw status numbered | grep -E "(Discord|udp|UDP)" || echo "Run 'sudo ufw status' to see all rules"

# Check Docker iptables
echo -e "\n${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} Checking Docker iptables rules..."
if iptables -L DOCKER-USER -n 2>/dev/null | grep -q "DOCKER-USER"; then
    echo -e "${YELLOW}[INFO]${NC} Docker iptables chain exists"
    
    # Ensure Docker doesn't block UDP traffic
    if ! iptables -L DOCKER-USER -n | grep -q "udp.*50000:65535"; then
        echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} Adding Docker UDP rule..."
        iptables -I DOCKER-USER -p udp --dport 50000:65535 -j ACCEPT -m comment --comment "Discord voice UDP"
    fi
fi

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}✅ Discord Voice UDP Configuration Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Restart your Discord bot:"
echo "   cd ~/Robustty && docker-compose down && docker-compose up -d"
echo "2. Test voice connection in Discord"
echo "3. Check logs: docker-compose logs -f robustty"

echo -e "\n${BLUE}Port Test Commands:${NC}"
echo "# Check if UDP ports are open:"
echo "sudo netstat -tuln | grep udp"
echo "# Test specific port:"
echo "nc -u -l 50000  # In one terminal"
echo "nc -u localhost 50000  # In another terminal"