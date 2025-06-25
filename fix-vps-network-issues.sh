#!/bin/bash

# VPS Network Issue Fix Script for Robustty Discord Bot
# This script applies common fixes for Discord connectivity issues

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    local level=$1
    shift
    local message="$*"
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" ;;
    esac
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log ERROR "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Fix DNS resolution issues
fix_dns() {
    log INFO "🔧 Fixing DNS Configuration..."
    
    # Backup current resolv.conf
    cp /etc/resolv.conf /etc/resolv.conf.backup.$(date +%Y%m%d_%H%M%S)
    
    # Configure reliable DNS servers
    cat > /etc/resolv.conf << EOF
# Fixed DNS configuration for Robustty
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
nameserver 1.0.0.1
options timeout:5 attempts:3
EOF
    
    # Configure systemd-resolved if available
    if systemctl is-active --quiet systemd-resolved; then
        log INFO "Configuring systemd-resolved..."
        
        mkdir -p /etc/systemd/resolved.conf.d
        cat > /etc/systemd/resolved.conf.d/99-robustty.conf << EOF
[Resolve]
DNS=8.8.8.8 8.8.4.4 1.1.1.1 1.0.0.1
FallbackDNS=208.67.222.222 208.67.220.220
DNSSEC=no
DNSOverTLS=opportunistic
Cache=yes
EOF
        
        systemctl restart systemd-resolved
        systemctl enable systemd-resolved
    fi
    
    # Test DNS resolution
    if nslookup discord.com >/dev/null 2>&1; then
        log INFO "✅ DNS resolution fixed"
    else
        log ERROR "❌ DNS resolution still failing"
    fi
}

# Configure Docker networking
fix_docker_networking() {
    log INFO "🐳 Fixing Docker Networking..."
    
    # Backup Docker daemon config
    if [[ -f /etc/docker/daemon.json ]]; then
        cp /etc/docker/daemon.json /etc/docker/daemon.json.backup.$(date +%Y%m%d_%H%M%S)
    fi
    
    # Configure Docker daemon with proper DNS
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << EOF
{
    "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
    "mtu": 1500,
    "bip": "172.17.0.1/16",
    "default-address-pools": [
        {
            "base": "172.20.0.0/16",
            "size": 24
        }
    ],
    "live-restore": true,
    "storage-driver": "overlay2"
}
EOF
    
    # Restart Docker to apply changes
    if systemctl is-active --quiet docker; then
        log INFO "Restarting Docker daemon..."
        systemctl restart docker
        
        # Wait for Docker to be ready
        sleep 5
        
        # Test Docker networking
        if docker run --rm alpine nslookup discord.com >/dev/null 2>&1; then
            log INFO "✅ Docker DNS resolution fixed"
        else
            log ERROR "❌ Docker DNS resolution still failing"
        fi
    else
        log WARN "Docker is not running"
    fi
}

# Configure firewall rules
fix_firewall() {
    log INFO "🛡️  Configuring Firewall Rules..."
    
    # Configure UFW if available
    if command -v ufw >/dev/null 2>&1; then
        log INFO "Configuring UFW firewall..."
        
        # Allow outbound HTTPS and HTTP
        ufw --force allow out 443/tcp comment 'HTTPS outbound for Discord'
        ufw --force allow out 80/tcp comment 'HTTP outbound'
        ufw --force allow out 53 comment 'DNS outbound'
        
        # Allow SSH (important!)
        ufw --force allow ssh
        
        # Allow health check port if specified
        ufw --force allow 8080/tcp comment 'Health check port'
        
        # Enable UFW if not already enabled
        echo "y" | ufw --force enable
        
        log INFO "UFW rules configured"
        ufw status
        
    elif command -v iptables >/dev/null 2>&1; then
        log INFO "Configuring iptables firewall..."
        
        # Allow outbound HTTPS and HTTP
        iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT
        iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT  
        iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
        iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
        
        # Save iptables rules if possible
        if command -v iptables-save >/dev/null 2>&1; then
            iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
        fi
        
        log INFO "iptables rules configured"
    else
        log WARN "No firewall configuration tools found"
    fi
}

# Fix network routing and MTU issues
fix_networking() {
    log INFO "🌐 Fixing Network Configuration..."
    
    # Set appropriate MTU for VPS environments
    for interface in $(ip link show | grep -E '^[0-9]+:' | grep -v lo | cut -d: -f2 | tr -d ' '); do
        if [[ "$interface" != "lo" ]]; then
            log INFO "Setting MTU for interface $interface"
            ip link set dev "$interface" mtu 1500 2>/dev/null || true
        fi
    done
    
    # Enable IP forwarding (helps with Docker networking)
    echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
    echo 'net.ipv4.conf.all.forwarding=1' >> /etc/sysctl.conf
    sysctl -p >/dev/null 2>&1 || true
    
    # Flush DNS cache
    if command -v systemd-resolve >/dev/null 2>&1; then
        systemd-resolve --flush-caches
    elif command -v resolvectl >/dev/null 2>&1; then
        resolvectl flush-caches
    fi
    
    log INFO "Network configuration updated"
}

# Test Discord connectivity after fixes
test_discord_connectivity() {
    log INFO "🧪 Testing Discord Connectivity..."
    
    local endpoints=(
        "https://discord.com/api/v10/gateway"
        "https://cdn.discordapp.com"
        "https://gateway.discord.gg"
    )
    
    local success_count=0
    local total_count=${#endpoints[@]}
    
    for endpoint in "${endpoints[@]}"; do
        log INFO "Testing $endpoint..."
        
        local response=$(curl -s -w "%{http_code}" -o /dev/null --connect-timeout 10 --max-time 15 "$endpoint" 2>/dev/null)
        
        if [[ "$response" == "200" ]]; then
            log INFO "✅ $endpoint - OK"
            ((success_count++))
        elif [[ "$response" == "403" ]]; then
            log WARN "⚠️  $endpoint - HTTP 403 (IP may be restricted)"
        else
            log ERROR "❌ $endpoint - Failed (HTTP $response)"
        fi
    done
    
    log INFO "Discord connectivity test: $success_count/$total_count endpoints working"
    
    if [[ $success_count -eq $total_count ]]; then
        log INFO "🎉 All Discord endpoints accessible!"
        return 0
    elif [[ $success_count -gt 0 ]]; then
        log WARN "⚠️  Partial Discord connectivity - some restrictions may apply"
        return 0
    else
        log ERROR "❌ No Discord endpoints accessible - VPS IP may be blocked"
        return 1
    fi
}

# Restart services after fixes
restart_services() {
    log INFO "🔄 Restarting Services..."
    
    # Restart network services
    systemctl restart systemd-networkd 2>/dev/null || true
    systemctl restart systemd-resolved 2>/dev/null || true
    systemctl restart networking 2>/dev/null || true
    
    # Restart Docker if it's running
    if systemctl is-active --quiet docker; then
        systemctl restart docker
        sleep 5
    fi
    
    log INFO "Services restarted"
}

# Main fix function
apply_fixes() {
    log INFO "🚀 Starting VPS Network Fixes for Robustty..."
    log INFO "=============================================="
    
    check_root
    
    # Apply fixes in sequence
    fix_dns
    fix_docker_networking
    fix_firewall
    fix_networking
    restart_services
    
    # Test connectivity
    echo ""
    test_discord_connectivity
    
    echo ""
    log INFO "🏁 Network fixes completed!"
    log INFO "If Discord is still inaccessible, the VPS IP may be blocked."
    log INFO "Consider trying a different VPS provider or location."
    echo ""
    log INFO "Next steps:"
    log INFO "1. Rebuild and restart the bot: docker-compose down && docker-compose up -d --build"
    log INFO "2. Monitor logs: docker-compose logs -f robustty"
    log INFO "3. If issues persist, try a different VPS provider"
}

# Show help
show_help() {
    cat << EOF
VPS Network Fix Script for Robustty Discord Bot

Usage: sudo $0 [OPTIONS]

OPTIONS:
    --dns-only          Fix DNS configuration only
    --docker-only       Fix Docker networking only
    --firewall-only     Fix firewall configuration only
    --test-only         Test connectivity without applying fixes
    -h, --help          Show this help

DESCRIPTION:
    This script applies common network fixes for VPS deployments where
    Discord connectivity is failing. It addresses DNS resolution,
    Docker networking, firewall rules, and general network configuration.

REQUIREMENTS:
    - Must be run as root (use sudo)
    - Ubuntu/Debian VPS recommended
    - Docker and Docker Compose should be installed

EXAMPLES:
    sudo $0                    # Apply all fixes
    sudo $0 --dns-only         # Fix DNS only
    sudo $0 --test-only        # Test connectivity only

EOF
}

# Parse arguments
DNS_ONLY=false
DOCKER_ONLY=false
FIREWALL_ONLY=false
TEST_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dns-only)
            DNS_ONLY=true
            shift
            ;;
        --docker-only)
            DOCKER_ONLY=true
            shift
            ;;
        --firewall-only)
            FIREWALL_ONLY=true
            shift
            ;;
        --test-only)
            TEST_ONLY=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Execute based on arguments
if [[ "$TEST_ONLY" == true ]]; then
    test_discord_connectivity
elif [[ "$DNS_ONLY" == true ]]; then
    check_root
    fix_dns
    test_discord_connectivity
elif [[ "$DOCKER_ONLY" == true ]]; then
    check_root
    fix_docker_networking
    test_discord_connectivity
elif [[ "$FIREWALL_ONLY" == true ]]; then
    check_root
    fix_firewall
    test_discord_connectivity
else
    # Apply all fixes
    apply_fixes
fi