#!/bin/bash

# VPS Network Diagnostic Script for Robustty Discord Bot
# Diagnoses common VPS Docker networking issues that cause "Connection closed" errors

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Test results storage
ISSUES_FOUND=0
RECOMMENDATIONS=()

add_recommendation() {
    RECOMMENDATIONS+=("$1")
    ((ISSUES_FOUND++))
}

echo "========================================"
echo "🔍 VPS Network Diagnostic Tool for Robustty"
echo "========================================"

# 1. Check if running on VPS
log "Checking VPS environment..."
if [[ -f /.dockerenv ]] || [[ -n "$DOCKER_CONTAINER" ]] || [[ -n "$VPS_MODE" ]]; then
    success "Running in containerized/VPS environment"
else
    log "Environment: Standard Linux server"
fi

# 2. Check Docker installation
log "Checking Docker installation..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    success "Docker installed: $DOCKER_VERSION"
    
    # Check Docker service status
    if systemctl is-active --quiet docker; then
        success "Docker service is running"
    else
        error "Docker service is not running"
        add_recommendation "Start Docker service: sudo systemctl start docker"
    fi
else
    error "Docker is not installed"
    add_recommendation "Install Docker: curl -fsSL https://get.docker.com | sh"
fi

# 3. Check Docker daemon configuration
log "Checking Docker daemon configuration..."
if [[ -f /etc/docker/daemon.json ]]; then
    log "Docker daemon.json exists"
    if grep -q "dns" /etc/docker/daemon.json; then
        success "DNS configuration found in daemon.json"
    else
        warning "No DNS configuration in daemon.json"
        add_recommendation "Add DNS config to /etc/docker/daemon.json: {\"dns\": [\"8.8.8.8\", \"1.1.1.1\"]}"
    fi
else
    warning "No Docker daemon.json configuration file"
    add_recommendation "Create /etc/docker/daemon.json with DNS settings"
fi

# 4. Check iptables rules
log "Checking iptables configuration..."

# Check if iptables is available
if command -v iptables &> /dev/null; then
    # Check DOCKER chain
    if iptables -t nat -L DOCKER &> /dev/null; then
        success "Docker iptables chains exist"
    else
        error "Docker iptables chains missing"
        add_recommendation "Restart Docker to recreate iptables chains: sudo systemctl restart docker"
    fi
    
    # Check DOCKER-USER chain
    if iptables -L DOCKER-USER &> /dev/null; then
        log "DOCKER-USER chain exists"
        USER_RULES=$(iptables -L DOCKER-USER --line-numbers | wc -l)
        if [[ $USER_RULES -gt 3 ]]; then
            log "DOCKER-USER has custom rules"
        else
            warning "DOCKER-USER chain is empty (may block container traffic)"
            add_recommendation "Configure DOCKER-USER chain for container connectivity"
        fi
    else
        error "DOCKER-USER chain missing"
        add_recommendation "Create DOCKER-USER chain and add connectivity rules"
    fi
    
    # Check IP forwarding
    if [[ $(cat /proc/sys/net/ipv4/ip_forward) -eq 1 ]]; then
        success "IP forwarding is enabled"
    else
        error "IP forwarding is disabled"
        add_recommendation "Enable IP forwarding: echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf"
    fi
    
    # Check masquerading
    MASQ_RULES=$(iptables -t nat -L POSTROUTING | grep -c MASQUERADE || true)
    if [[ $MASQ_RULES -gt 0 ]]; then
        success "NAT masquerading rules found ($MASQ_RULES rules)"
    else
        error "No NAT masquerading rules found"
        add_recommendation "Add masquerading rule: iptables -t nat -A POSTROUTING -s 172.17.0.0/16 -j MASQUERADE"
    fi
else
    error "iptables not available"
    add_recommendation "Install iptables: apt-get install iptables"
fi

# 5. Check network interfaces
log "Checking network interfaces..."
if ip link show docker0 &> /dev/null; then
    success "Docker bridge interface exists"
    
    # Check MTU
    DOCKER_MTU=$(ip link show docker0 | grep -o 'mtu [0-9]*' | cut -d' ' -f2)
    log "Docker bridge MTU: $DOCKER_MTU"
    if [[ $DOCKER_MTU -gt 1500 ]]; then
        warning "Docker MTU ($DOCKER_MTU) may be too high for VPS"
        add_recommendation "Lower Docker MTU to 1450 in daemon.json: \"mtu\": 1450"
    fi
else
    warning "Docker bridge interface not found"
    add_recommendation "Create Docker bridge: docker network create --driver bridge test-bridge"
fi

# 6. Test DNS resolution
log "Testing DNS resolution..."

# Test from host
if nslookup discord.com &> /dev/null; then
    success "Host DNS resolution working"
else
    error "Host DNS resolution failed"
    add_recommendation "Fix host DNS: echo 'nameserver 8.8.8.8' > /etc/resolv.conf"
fi

# Test from container (if Docker is available)
if command -v docker &> /dev/null && systemctl is-active --quiet docker; then
    log "Testing container DNS resolution..."
    if docker run --rm alpine nslookup discord.com &> /dev/null; then
        success "Container DNS resolution working"
    else
        error "Container DNS resolution failed"
        add_recommendation "Fix container DNS in daemon.json or add --dns flags"
    fi
fi

# 7. Test connectivity to key services
log "Testing connectivity to key services..."

# Discord API
if curl -s --connect-timeout 10 https://discord.com/api/v10/gateway &> /dev/null; then
    success "Discord API reachable"
else
    error "Discord API unreachable"
    add_recommendation "Check firewall rules for outbound HTTPS traffic"
fi

# YouTube API  
if curl -s --connect-timeout 10 https://www.googleapis.com/youtube/v3/ &> /dev/null; then
    success "YouTube API reachable"
else
    warning "YouTube API unreachable"
    add_recommendation "Check outbound connectivity to googleapis.com"
fi

# PeerTube instance
if curl -s --connect-timeout 10 https://tube.tchncs.de &> /dev/null; then
    success "PeerTube instance reachable"
else
    warning "PeerTube instance unreachable"
    add_recommendation "PeerTube connectivity issues may be expected on some VPS"
fi

# Odysee API
if curl -s --connect-timeout 10 https://api.lbry.tv/api/v1/proxy &> /dev/null; then
    success "Odysee API reachable"
else
    warning "Odysee API unreachable"
    add_recommendation "Odysee connectivity issues may be expected on some VPS"
fi

# 8. Check for common VPS restrictions
log "Checking for common VPS restrictions..."

# Check UFW
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(ufw status | head -1)
    log "UFW status: $UFW_STATUS"
    if echo "$UFW_STATUS" | grep -q "active"; then
        warning "UFW firewall is active - may interfere with Docker"
        add_recommendation "Configure UFW to allow Docker: ufw allow out 53 && ufw allow out 80 && ufw allow out 443"
    fi
fi

# Check firewalld
if command -v firewalld &> /dev/null; then
    if systemctl is-active --quiet firewalld; then
        warning "firewalld is active - may interfere with Docker"
        add_recommendation "Configure firewalld for Docker or disable: systemctl disable firewalld"
    fi
fi

# 9. Summary and recommendations
echo ""
echo "========================================"
echo "📊 DIAGNOSTIC SUMMARY"
echo "========================================"

if [[ $ISSUES_FOUND -eq 0 ]]; then
    success "No major issues found! 🎉"
    log "Your VPS networking appears to be configured correctly."
else
    warning "Found $ISSUES_FOUND potential issues"
    echo ""
    echo "🔧 RECOMMENDATIONS:"
    for i in "${!RECOMMENDATIONS[@]}"; do
        echo "  $((i+1)). ${RECOMMENDATIONS[$i]}"
    done
fi

echo ""
echo "🚀 Next Steps:"
echo "1. Run the fix script: sudo ./scripts/fix-vps-network.sh"
echo "2. Restart Docker: sudo systemctl restart docker"
echo "3. Restart your bot: docker-compose down && docker-compose up -d"
echo "4. Check bot logs: docker-compose logs -f robustty"

exit $ISSUES_FOUND