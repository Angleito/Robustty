#!/bin/bash

# VPS Network Fix Script for Robustty Discord Bot
# Automatically fixes common VPS Docker networking issues

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

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root (use sudo)"
   exit 1
fi

# Parse command line arguments
DRY_RUN=false
FORCE_INSTALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE_INSTALL=true
            shift
            ;;
        *)
            echo "Usage: $0 [--dry-run] [--force]"
            echo "  --dry-run: Show what would be done without making changes"
            echo "  --force: Force installation of Docker if missing"
            exit 1
            ;;
    esac
done

if [[ "$DRY_RUN" == true ]]; then
    warning "DRY RUN MODE - No changes will be made"
fi

echo "========================================"
echo "🔧 VPS Network Fix Tool for Robustty"
echo "========================================"

# Backup current iptables rules
log "Backing up current iptables rules..."
if [[ "$DRY_RUN" == false ]]; then
    iptables-save > /tmp/iptables-backup-$(date +%Y%m%d-%H%M%S).txt
    success "Iptables rules backed up"
else
    log "[DRY RUN] Would backup iptables rules"
fi

# 1. Check and install Docker if needed
log "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    if [[ "$FORCE_INSTALL" == true ]]; then
        log "Installing Docker..."
        if [[ "$DRY_RUN" == false ]]; then
            curl -fsSL https://get.docker.com | sh
            systemctl enable docker
            systemctl start docker
            success "Docker installed and started"
        else
            log "[DRY RUN] Would install Docker"
        fi
    else
        error "Docker is not installed. Use --force to install automatically"
        exit 1
    fi
else
    success "Docker is already installed"
fi

# 2. Configure Docker daemon
log "Configuring Docker daemon..."
DAEMON_CONFIG='{
  "dns": ["8.8.8.8", "1.1.1.1"],
  "mtu": 1450,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}'

if [[ "$DRY_RUN" == false ]]; then
    mkdir -p /etc/docker
    echo "$DAEMON_CONFIG" > /etc/docker/daemon.json
    success "Docker daemon configuration updated"
else
    log "[DRY RUN] Would create /etc/docker/daemon.json with DNS and MTU settings"
fi

# 3. Enable IP forwarding
log "Enabling IP forwarding..."
if [[ "$DRY_RUN" == false ]]; then
    echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
    echo 'net.bridge.bridge-nf-call-iptables=1' >> /etc/sysctl.conf
    echo 'net.bridge.bridge-nf-call-ip6tables=1' >> /etc/sysctl.conf
    sysctl -p
    success "IP forwarding enabled"
else
    log "[DRY RUN] Would enable IP forwarding and bridge netfilter"
fi

# 4. Load bridge netfilter module
log "Loading bridge netfilter module..."
if [[ "$DRY_RUN" == false ]]; then
    modprobe br_netfilter
    echo 'br_netfilter' >> /etc/modules-load.d/docker.conf
    success "Bridge netfilter module loaded"
else
    log "[DRY RUN] Would load br_netfilter module"
fi

# 5. Restart Docker to apply daemon configuration
log "Restarting Docker service..."
if [[ "$DRY_RUN" == false ]]; then
    systemctl restart docker
    sleep 5
    success "Docker service restarted"
else
    log "[DRY RUN] Would restart Docker service"
fi

# 6. Configure iptables rules for Docker
log "Configuring iptables rules..."

if [[ "$DRY_RUN" == false ]]; then
    # Create DOCKER-USER chain if it doesn't exist
    if ! iptables -L DOCKER-USER &> /dev/null; then
        iptables -N DOCKER-USER
        log "Created DOCKER-USER chain"
    fi
    
    # Allow all traffic from Docker containers to anywhere
    iptables -I DOCKER-USER -i docker0 -j ACCEPT
    iptables -I DOCKER-USER -o docker0 -j ACCEPT
    
    # Allow containers to communicate with host
    iptables -I INPUT -i docker0 -j ACCEPT
    
    # Ensure NAT masquerading for Docker containers
    iptables -t nat -A POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE
    
    success "Iptables rules configured for Docker connectivity"
else
    log "[DRY RUN] Would configure iptables rules:"
    log "  - Create/update DOCKER-USER chain"
    log "  - Allow traffic from docker0 interface"
    log "  - Add NAT masquerading for container outbound traffic"
fi

# 7. Configure UFW if present
if command -v ufw &> /dev/null; then
    log "Configuring UFW for Docker compatibility..."
    if [[ "$DRY_RUN" == false ]]; then
        # Allow Docker to manage its own rules
        ufw --force reload
        # Allow essential outbound ports
        ufw allow out 53 comment 'DNS'
        ufw allow out 80 comment 'HTTP'
        ufw allow out 443 comment 'HTTPS'
        success "UFW configured for Docker"
    else
        log "[DRY RUN] Would configure UFW to allow DNS, HTTP, and HTTPS outbound"
    fi
fi

# 8. Save iptables rules
log "Saving iptables rules..."
if [[ "$DRY_RUN" == false ]]; then
    # Install iptables-persistent if not present
    if ! command -v iptables-save &> /dev/null; then
        apt-get update && apt-get install -y iptables-persistent
    fi
    
    # Save rules
    iptables-save > /etc/iptables/rules.v4
    if command -v ip6tables-save &> /dev/null; then
        ip6tables-save > /etc/iptables/rules.v6
    fi
    success "Iptables rules saved"
else
    log "[DRY RUN] Would save iptables rules to /etc/iptables/"
fi

# 9. Create network optimization script
log "Creating network optimization script..."
OPTIMIZATION_SCRIPT='#!/bin/bash
# Network optimization for Discord bot VPS deployment
echo "Applying network optimizations..."

# TCP buffer sizes
echo "net.core.rmem_max = 16777216" >> /etc/sysctl.conf
echo "net.core.wmem_max = 16777216" >> /etc/sysctl.conf
echo "net.ipv4.tcp_rmem = 4096 16384 16777216" >> /etc/sysctl.conf
echo "net.ipv4.tcp_wmem = 4096 16384 16777216" >> /etc/sysctl.conf

# Connection tracking
echo "net.netfilter.nf_conntrack_max = 65536" >> /etc/sysctl.conf

# Apply settings
sysctl -p

echo "Network optimizations applied"
'

if [[ "$DRY_RUN" == false ]]; then
    echo "$OPTIMIZATION_SCRIPT" > /usr/local/bin/optimize-network.sh
    chmod +x /usr/local/bin/optimize-network.sh
    /usr/local/bin/optimize-network.sh
    success "Network optimizations applied"
else
    log "[DRY RUN] Would create and run network optimization script"
fi

# 10. Test Docker networking
log "Testing Docker networking..."
if [[ "$DRY_RUN" == false ]]; then
    if docker run --rm alpine ping -c 1 8.8.8.8 &> /dev/null; then
        success "Docker container can reach external IPs"
    else
        error "Docker container cannot reach external IPs"
    fi
    
    if docker run --rm alpine nslookup discord.com &> /dev/null; then
        success "Docker container DNS resolution working"
    else
        error "Docker container DNS resolution failed"
    fi
else
    log "[DRY RUN] Would test Docker container networking"
fi

# 11. Create systemd service for persistent rules
log "Creating systemd service for network rules..."
SERVICE_CONTENT='[Unit]
Description=Robustty VPS Network Configuration
After=docker.service
Wants=docker.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c "iptables -I DOCKER-USER -i docker0 -j ACCEPT; iptables -I DOCKER-USER -o docker0 -j ACCEPT"
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target'

if [[ "$DRY_RUN" == false ]]; then
    echo "$SERVICE_CONTENT" > /etc/systemd/system/robustty-network.service
    systemctl daemon-reload
    systemctl enable robustty-network.service
    success "Systemd service created for persistent network rules"
else
    log "[DRY RUN] Would create systemd service for persistent network rules"
fi

echo ""
echo "========================================"
echo "✅ VPS NETWORK FIX COMPLETE"
echo "========================================"

if [[ "$DRY_RUN" == false ]]; then
    success "All network fixes have been applied!"
    echo ""
    echo "🚀 Next Steps:"
    echo "1. Restart your Discord bot: docker-compose down && docker-compose up -d"
    echo "2. Check bot logs: docker-compose logs -f robustty"
    echo "3. Test voice connections and platform connectivity"
    echo ""
    echo "📋 What was fixed:"
    echo "• Docker daemon configured with reliable DNS servers"
    echo "• MTU set to 1450 for VPS compatibility"
    echo "• IP forwarding enabled"
    echo "• Iptables rules configured for container connectivity"
    echo "• NAT masquerading enabled for outbound traffic"
    echo "• Network optimizations applied"
    echo "• Persistent configuration created"
else
    warning "DRY RUN completed - no changes were made"
    echo "Run without --dry-run to apply the fixes"
fi

echo ""
echo "📞 If you still experience issues:"
echo "• Run the diagnostic script: ./scripts/diagnose-vps-network.sh"
echo "• Check the troubleshooting guide: cat VPS_TROUBLESHOOTING.md"
echo "• Verify your VPS provider doesn't block specific ports"

exit 0