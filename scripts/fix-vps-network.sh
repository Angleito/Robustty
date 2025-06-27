#!/bin/bash
#
# VPS Network Fix Script for Robustty Bot
# 
# This script automatically fixes common VPS networking issues
# that prevent Docker containers from accessing external services.
#
# Usage: sudo ./fix-vps-network.sh [--dry-run] [--force]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
FORCE=false
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        --force)
            FORCE=true
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--dry-run] [--force]"
            exit 1
            ;;
    esac
done

# Check if running as root
if [[ $EUID -ne 0 ]] && [[ "$DRY_RUN" == "false" ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

echo -e "${BLUE}🔧 Robustty VPS Network Fix Tool${NC}"
echo "=================================="

# Function to execute or print commands
execute_cmd() {
    local cmd="$1"
    local description="$2"
    
    echo -e "\n${YELLOW}→ ${description}${NC}"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${BLUE}[DRY RUN] Would execute:${NC} $cmd"
    else
        echo -e "${BLUE}Executing:${NC} $cmd"
        eval "$cmd"
        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}✓ Success${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            return 1
        fi
    fi
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to backup iptables rules
backup_iptables() {
    if [[ "$DRY_RUN" == "false" ]]; then
        local backup_file="/tmp/iptables-backup-$(date +%Y%m%d-%H%M%S).rules"
        iptables-save > "$backup_file" 2>/dev/null || true
        echo -e "${GREEN}Backed up iptables rules to: $backup_file${NC}"
    fi
}

echo -e "\n${BLUE}1. Checking Docker Installation${NC}"
echo "--------------------------------"

if ! command_exists docker; then
    echo -e "${RED}Docker is not installed!${NC}"
    if [[ "$FORCE" == "true" ]] || [[ "$DRY_RUN" == "true" ]]; then
        execute_cmd "curl -fsSL https://get.docker.com | sh" "Installing Docker"
        execute_cmd "systemctl enable docker" "Enabling Docker service"
        execute_cmd "systemctl start docker" "Starting Docker service"
    else
        echo "Run with --force to install Docker automatically"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Docker is installed${NC}"
fi

# Check if Docker is running
if ! systemctl is-active --quiet docker && [[ "$DRY_RUN" == "false" ]]; then
    execute_cmd "systemctl start docker" "Starting Docker service"
fi

echo -e "\n${BLUE}2. Fixing Docker Network Configuration${NC}"
echo "--------------------------------------"

# Ensure Docker's iptables integration is proper
execute_cmd "systemctl restart docker" "Restarting Docker to refresh iptables rules"

# Fix Docker bridge MTU
echo -e "\n${BLUE}3. Fixing MTU Configuration${NC}"
echo "-------------------------------"

# Get Docker bridge interface name
DOCKER_BRIDGE=$(ip link show | grep -E "docker0|br-" | awk -F: '{print $2}' | tr -d ' ' | head -n1)

if [[ -n "$DOCKER_BRIDGE" ]]; then
    execute_cmd "ip link set dev $DOCKER_BRIDGE mtu 1500" "Setting MTU to 1500 for $DOCKER_BRIDGE"
else
    echo -e "${YELLOW}⚠ No Docker bridge interface found${NC}"
fi

echo -e "\n${BLUE}4. Configuring DNS for Docker${NC}"
echo "---------------------------------"

# Create Docker daemon configuration with DNS
DOCKER_CONFIG="/etc/docker/daemon.json"
if [[ "$DRY_RUN" == "false" ]]; then
    # Backup existing config
    if [[ -f "$DOCKER_CONFIG" ]]; then
        cp "$DOCKER_CONFIG" "${DOCKER_CONFIG}.backup-$(date +%Y%m%d-%H%M%S)"
    fi
    
    # Create new config with DNS settings
    cat > "$DOCKER_CONFIG" <<EOF
{
  "dns": ["1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4"],
  "dns-opts": ["ndots:0"],
  "dns-search": [],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-address-pools": [
    {
      "base": "172.17.0.0/16",
      "size": 24
    }
  ]
}
EOF
    echo -e "${GREEN}✓ Updated Docker daemon configuration${NC}"
else
    echo -e "${BLUE}[DRY RUN] Would update Docker daemon configuration${NC}"
fi

execute_cmd "systemctl restart docker" "Restarting Docker with new configuration"

echo -e "\n${BLUE}5. Configuring IPTables Rules${NC}"
echo "---------------------------------"

# Backup current iptables rules
backup_iptables

# Ensure DOCKER-USER chain exists and has proper rules
if iptables -L DOCKER-USER -n >/dev/null 2>&1; then
    # Check if DOCKER-USER chain is empty or blocking
    RULES_COUNT=$(iptables -L DOCKER-USER -n | grep -c "RETURN" || true)
    if [[ $RULES_COUNT -eq 0 ]]; then
        execute_cmd "iptables -I DOCKER-USER -j RETURN" "Adding RETURN rule to DOCKER-USER chain"
    fi
else
    echo -e "${YELLOW}DOCKER-USER chain doesn't exist, Docker will create it${NC}"
fi

# Ensure proper masquerading for Docker networks
execute_cmd "iptables -t nat -C POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE" "Ensuring NAT masquerading for Docker"

# Allow established connections
execute_cmd "iptables -C INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || iptables -I INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT" "Allowing established connections"

# Ensure Docker containers can access external DNS
execute_cmd "iptables -C FORWARD -i docker0 -o eth0 -j ACCEPT 2>/dev/null || iptables -I FORWARD -i docker0 -o eth0 -j ACCEPT" "Allowing Docker bridge to external interface forwarding"
execute_cmd "iptables -C FORWARD -i eth0 -o docker0 -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || iptables -I FORWARD -i eth0 -o docker0 -m state --state ESTABLISHED,RELATED -j ACCEPT" "Allowing return traffic to Docker"

echo -e "\n${BLUE}6. Fixing System DNS Resolution${NC}"
echo "----------------------------------"

# Ensure system DNS is working
if [[ -f /etc/resolv.conf ]]; then
    # Check if resolv.conf has valid nameservers
    if ! grep -q "nameserver" /etc/resolv.conf || grep -q "nameserver 127" /etc/resolv.conf; then
        if [[ "$DRY_RUN" == "false" ]]; then
            # Backup original
            cp /etc/resolv.conf /etc/resolv.conf.backup-$(date +%Y%m%d-%H%M%S)
            
            # Create new resolv.conf
            cat > /etc/resolv.conf <<EOF
nameserver 1.1.1.1
nameserver 1.0.0.1
nameserver 8.8.8.8
nameserver 8.8.4.4
EOF
            echo -e "${GREEN}✓ Updated system DNS configuration${NC}"
        else
            echo -e "${BLUE}[DRY RUN] Would update /etc/resolv.conf${NC}"
        fi
    else
        echo -e "${GREEN}✓ System DNS configuration looks good${NC}"
    fi
fi

echo -e "\n${BLUE}7. Optimizing Network Performance${NC}"
echo "------------------------------------"

# Increase network buffer sizes
execute_cmd "sysctl -w net.core.rmem_max=134217728" "Increasing receive buffer maximum"
execute_cmd "sysctl -w net.core.wmem_max=134217728" "Increasing send buffer maximum"
execute_cmd "sysctl -w net.ipv4.tcp_rmem='4096 87380 134217728'" "Setting TCP receive buffer sizes"
execute_cmd "sysctl -w net.ipv4.tcp_wmem='4096 65536 134217728'" "Setting TCP send buffer sizes"

# Enable TCP fast open
execute_cmd "sysctl -w net.ipv4.tcp_fastopen=3" "Enabling TCP fast open"

# Increase connection tracking limits
execute_cmd "sysctl -w net.netfilter.nf_conntrack_max=131072" "Increasing connection tracking limit"

# Make sysctl changes persistent
if [[ "$DRY_RUN" == "false" ]]; then
    cat >> /etc/sysctl.conf <<EOF

# Robustty VPS Network Optimizations
net.core.rmem_max=134217728
net.core.wmem_max=134217728
net.ipv4.tcp_rmem=4096 87380 134217728
net.ipv4.tcp_wmem=4096 65536 134217728
net.ipv4.tcp_fastopen=3
net.netfilter.nf_conntrack_max=131072
EOF
    echo -e "${GREEN}✓ Made network optimizations persistent${NC}"
fi

echo -e "\n${BLUE}8. Restarting Robustty Services${NC}"
echo "-----------------------------------"

# Check if docker-compose exists in current directory
if [[ -f "docker-compose.yml" ]] || [[ -f "../docker-compose.yml" ]]; then
    COMPOSE_DIR="."
    if [[ -f "../docker-compose.yml" ]]; then
        COMPOSE_DIR=".."
    fi
    
    execute_cmd "cd $COMPOSE_DIR && docker-compose down" "Stopping Robustty services"
    execute_cmd "cd $COMPOSE_DIR && docker-compose up -d" "Starting Robustty services"
    
    # Wait for services to start
    echo -e "${BLUE}Waiting for services to start...${NC}"
    sleep 10
    
    # Check service health
    if [[ "$DRY_RUN" == "false" ]]; then
        cd $COMPOSE_DIR
        if docker-compose ps | grep -q "Up"; then
            echo -e "${GREEN}✓ Robustty services are running${NC}"
        else
            echo -e "${RED}✗ Some services failed to start${NC}"
            docker-compose logs --tail=50
        fi
    fi
else
    echo -e "${YELLOW}⚠ docker-compose.yml not found in current directory${NC}"
    echo "Please run this script from the Robustty project directory"
fi

echo -e "\n${BLUE}9. Verifying Fixes${NC}"
echo "--------------------"

if [[ "$DRY_RUN" == "false" ]]; then
    # Test DNS resolution
    if nslookup discord.com >/dev/null 2>&1; then
        echo -e "${GREEN}✓ DNS resolution working${NC}"
    else
        echo -e "${RED}✗ DNS resolution still failing${NC}"
    fi
    
    # Test outbound connectivity
    if curl -s -m 5 https://discord.com/api/v10/gateway >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Outbound HTTPS working${NC}"
    else
        echo -e "${RED}✗ Outbound HTTPS still failing${NC}"
    fi
    
    # Test from within container if running
    if docker ps --format "{{.Names}}" | grep -q "robustty"; then
        CONTAINER=$(docker ps --format "{{.Names}}" | grep "robustty" | grep -v "redis" | head -n1)
        if docker exec $CONTAINER curl -s -m 5 https://discord.com/api/v10/gateway >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Container outbound connectivity working${NC}"
        else
            echo -e "${RED}✗ Container outbound connectivity still failing${NC}"
        fi
    fi
fi

echo -e "\n${GREEN}✅ Network fix script completed!${NC}"
echo "=================================="

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}This was a dry run. No changes were made.${NC}"
    echo "Run without --dry-run to apply fixes."
else
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Run the diagnostic script to verify fixes:"
    echo "   python3 scripts/diagnose-vps-network.py"
    echo "2. Check Robustty bot logs:"
    echo "   docker-compose logs -f robustty"
    echo "3. If issues persist, check VPS firewall rules with your provider"
fi