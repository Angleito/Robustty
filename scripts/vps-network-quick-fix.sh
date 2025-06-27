#!/bin/bash

# Quick VPS Network Fix Guide
# This script provides a quick reference for fixing VPS Docker networking issues

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== VPS Docker Network Quick Fix Guide ===${NC}\n"

echo -e "${YELLOW}Common symptoms of network issues:${NC}"
echo "- 'Connection closed' errors on all platforms"
echo "- Containers can't reach external services"
echo "- DNS resolution failures inside containers"
echo "- YouTube/Rumble/Odysee searches all fail"
echo

echo -e "${GREEN}Quick Fix Steps:${NC}\n"

echo -e "${BLUE}1. Run Network Diagnostics:${NC}"
echo "   sudo ./scripts/diagnose-vps-network.sh"
echo "   This will identify specific issues with your setup"
echo

echo -e "${BLUE}2. Apply Automatic Fixes:${NC}"
echo "   sudo ./scripts/fix-vps-network.sh"
echo "   This will fix most common Docker networking issues"
echo

echo -e "${BLUE}3. Restart Docker Services:${NC}"
echo "   docker-compose down"
echo "   docker-compose up -d --build"
echo

echo -e "${BLUE}4. Test the Fix:${NC}"
echo "   # Check if containers can reach the internet"
echo "   docker-compose exec robustty ping -c 1 google.com"
echo "   docker-compose exec robustty curl -s https://www.google.com"
echo

echo -e "${BLUE}5. Check Bot Logs:${NC}"
echo "   docker-compose logs -f robustty"
echo

echo -e "${YELLOW}Manual Fixes (if automatic fix doesn't work):${NC}\n"

echo -e "${BLUE}Enable IP Forwarding:${NC}"
echo "   sudo sysctl -w net.ipv4.ip_forward=1"
echo "   echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf"
echo

echo -e "${BLUE}Fix iptables Masquerading:${NC}"
echo "   sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE"
echo "   sudo iptables -A DOCKER-USER -j RETURN"
echo

echo -e "${BLUE}Fix DNS in Docker:${NC}"
echo "   # Edit /etc/docker/daemon.json and add:"
echo '   {
     "dns": ["8.8.8.8", "8.8.4.4"]
   }'
echo "   sudo systemctl restart docker"
echo

echo -e "${YELLOW}Common VPS Provider Issues:${NC}\n"

echo -e "${BLUE}DigitalOcean:${NC}"
echo "   - Private networking may interfere with Docker"
echo "   - Use floating IPs for outbound traffic"
echo

echo -e "${BLUE}AWS EC2:${NC}"
echo "   - Security groups must allow outbound HTTPS (443)"
echo "   - Check VPC subnet routing tables"
echo

echo -e "${BLUE}Google Cloud:${NC}"
echo "   - Firewall rules may block Docker traffic"
echo "   - Check VPC firewall settings"
echo

echo -e "${YELLOW}Still having issues?${NC}"
echo "1. Check firewall: sudo ufw status"
echo "2. Check iptables: sudo iptables -L -n"
echo "3. Check Docker networks: docker network ls"
echo "4. Test from host: curl -s https://www.google.com"
echo "5. Review full diagnostics output"
echo

echo -e "${GREEN}For detailed help, see:${NC}"
echo "- CLAUDE.md - VPS Deployment Issues section"
echo "- README.md - Troubleshooting section"
echo "- Discord support channel"