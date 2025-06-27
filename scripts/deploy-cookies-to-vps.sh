#!/bin/bash
# Automated cookie deployment and Docker container restart for VPS
# This script handles the complete cookie sync and container restart process

set -e

# Source the SSH retry wrapper for network resilience
SSH_RETRY_SCRIPT="$(dirname "$0")/ssh-retry-wrapper.sh"
if [[ -f "$SSH_RETRY_SCRIPT" ]]; then
    source "$SSH_RETRY_SCRIPT"
    echo "✅ SSH retry wrapper loaded for network resilience"
else
    echo "⚠️  SSH retry wrapper not found - SSH commands will run without retry logic"
    # Fallback functions if retry wrapper is not available
    ssh_retry() { ssh "$@"; }
    scp_retry() { scp "$@"; }
fi

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting automated cookie deployment to VPS...${NC}"

# Check if we're in the right directory
if [ ! -f "docker-compose.vps.yml" ]; then
    echo -e "${RED}❌ Error: Must run from Robustty project root directory${NC}"
    exit 1
fi

# Set environment variables (must be provided via environment)
export VPS_IP="${VPS_IP}"
export SSH_KEY="${SSH_KEY}"
export SSH_PASSPHRASE="${SSH_PASSPHRASE}"

# Check required environment variables
if [ -z "$VPS_IP" ]; then
    echo -e "${RED}❌ Error: VPS_IP environment variable is required${NC}"
    echo -e "${YELLOW}   Example: export VPS_IP=\"your.vps.ip.address\"${NC}"
    exit 1
fi

if [ -z "$SSH_KEY" ]; then
    echo -e "${RED}❌ Error: SSH_KEY environment variable is required${NC}"
    echo -e "${YELLOW}   Example: export SSH_KEY=\"/path/to/your/ssh/key\"${NC}"
    exit 1
fi

if [ -z "$SSH_PASSPHRASE" ]; then
    echo -e "${RED}❌ Error: SSH_PASSPHRASE environment variable is required${NC}"
    echo -e "${YELLOW}   Example: export SSH_PASSPHRASE=\"your_passphrase\"${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Configuration:${NC}"
echo -e "   VPS IP: ${VPS_IP}"
echo -e "   SSH Key: ${SSH_KEY}"
echo -e "   Container: robustty-bot"

# Step 1: Run cookie synchronization
echo -e "${BLUE}🍪 Step 1: Synchronizing cookies...${NC}"
if ./scripts/sync-cookies-to-vps.sh; then
    echo -e "${GREEN}✅ Cookie synchronization completed${NC}"
else
    echo -e "${RED}❌ Cookie synchronization failed${NC}"
    exit 1
fi

# Step 2: Restart and rebuild container
echo -e "${BLUE}🔄 Step 2: Rebuilding and restarting Docker containers...${NC}"
expect -c "
    spawn ssh -i $SSH_KEY root@$VPS_IP
    expect \"Enter passphrase for key\" { send \"$SSH_PASSPHRASE\r\" }
    expect \"#\" { send \"cd ~/Robustty\r\" }
    expect \"#\" { send \"echo 'Stopping containers...'\r\" }
    expect \"#\" { send \"docker-compose -f docker-compose.vps.yml down\r\" }
    expect \"#\" { send \"echo 'Rebuilding and starting containers...'\r\" }
    expect \"#\" { send \"docker-compose -f docker-compose.vps.yml up -d --build\r\" }
    expect \"#\" { send \"echo 'Waiting for containers to start...'\r\" }
    expect \"#\" { send \"sleep 20\r\" }
    expect \"#\" { send \"echo 'Container status:'\r\" }
    expect \"#\" { send \"docker ps\r\" }
    expect \"#\" { send \"echo 'Recent bot logs:'\r\" }
    expect \"#\" { send \"docker logs --tail 10 robustty-bot\r\" }
    expect \"#\" { send \"exit\r\" }
    expect eof
"

echo -e "${BLUE}🔍 Step 3: Verifying deployment...${NC}"
sleep 5

# Check if the deployment was successful
HEALTH_CHECK=$(expect -c "
    spawn ssh -i $SSH_KEY root@$VPS_IP
    expect \"Enter passphrase for key\" { send \"$SSH_PASSPHRASE\r\" }
    expect \"#\" { send \"cd ~/Robustty\r\" }
    expect \"#\" { send \"docker ps --format 'table {{.Names}}\t{{.Status}}' | grep robustty || echo 'Container not found'\r\" }
    expect \"#\" { send \"exit\r\" }
    expect eof
" 2>/dev/null | grep -i "up" || echo "failed")

if [[ "$HEALTH_CHECK" == *"Up"* ]]; then
    echo -e "${GREEN}🎉 Deployment successful! Bot is running on VPS.${NC}"
    echo -e "${GREEN}✅ Cookies synchronized and loaded${NC}"
    echo -e "${GREEN}✅ Docker containers rebuilt and running${NC}"
    echo -e "${GREEN}✅ Bot is operational with fresh authentication${NC}"
    
    echo -e "${BLUE}🔗 Useful commands:${NC}"
    echo -e "   Monitor logs: ssh -i ${SSH_KEY} root@${VPS_IP} 'cd ~/Robustty && docker logs -f robustty-bot'"
    echo -e "   Check status: ssh -i ${SSH_KEY} root@${VPS_IP} 'cd ~/Robustty && docker ps'"
    echo -e "   Health check: ssh -i ${SSH_KEY} root@${VPS_IP} 'curl -s http://localhost:8081/health'"
else
    echo -e "${YELLOW}⚠️  Warning: Container status unclear. Check manually:${NC}"
    echo -e "   ssh -i ${SSH_KEY} root@${VPS_IP} 'cd ~/Robustty && docker ps && docker logs robustty-bot'"
fi

echo -e "${BLUE}🏁 Cookie deployment process completed!${NC}"