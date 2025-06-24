#!/bin/bash

# VPS Networking Setup Automation Script
# This script automates the complete networking configuration for VPS deployment

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/var/log/robustty-network-setup.log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" | tee -a "$LOG_FILE" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" | tee -a "$LOG_FILE" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" | tee -a "$LOG_FILE" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" | tee -a "$LOG_FILE" ;;
    esac
    echo "$timestamp [$level] $message" >> "$LOG_FILE"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log ERROR "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Detect OS and distribution
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
        log INFO "Detected OS: $OS $OS_VERSION"
    else
        log ERROR "Cannot detect OS. /etc/os-release not found."
        exit 1
    fi
}

# Install required packages
install_packages() {
    log INFO "Installing required networking packages..."
    
    case $OS in
        ubuntu|debian)
            apt-get update
            apt-get install -y curl wget net-tools dnsutils iptables-persistent ufw jq
            ;;
        centos|rhel|fedora)
            if command -v dnf &> /dev/null; then
                dnf install -y curl wget net-tools bind-utils iptables jq
            else
                yum install -y curl wget net-tools bind-utils iptables jq
            fi
            ;;
        *)
            log WARN "Unsupported OS: $OS. Manual package installation may be required."
            ;;
    esac
}

# Configure system DNS
configure_dns() {
    log INFO "Configuring system DNS resolution..."
    
    # Backup existing configuration
    if [[ -f /etc/systemd/resolved.conf ]]; then
        cp /etc/systemd/resolved.conf /etc/systemd/resolved.conf.backup
    fi
    
    # Configure systemd-resolved
    cat > /etc/systemd/resolved.conf << 'EOF'
[Resolve]
DNS=8.8.8.8 8.8.4.4 1.1.1.1 1.0.0.1
FallbackDNS=208.67.222.222 208.67.220.220
Domains=~.
DNSSEC=no
DNSOverTLS=opportunistic
Cache=yes
DNSStubListener=yes
EOF
    
    # Restart systemd-resolved
    systemctl restart systemd-resolved
    
    # Verify DNS configuration
    log INFO "Testing DNS resolution..."
    local test_domains=("discord.com" "googleapis.com" "apify.com")
    
    for domain in "${test_domains[@]}"; do
        if nslookup "$domain" > /dev/null 2>&1; then
            log INFO "✅ DNS resolution working for $domain"
        else
            log WARN "⚠️ DNS resolution failed for $domain"
        fi
    done
}

# Configure Docker daemon
configure_docker() {
    log INFO "Configuring Docker daemon for optimal networking..."
    
    # Create Docker daemon configuration
    mkdir -p /etc/docker
    
    cat > /etc/docker/daemon.json << 'EOF'
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-search": ["."],
  "mtu": 1500,
  "bip": "172.17.0.1/16",
  "default-address-pools": [
    {
      "base": "172.20.0.0/16",
      "size": 24
    }
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}
EOF
    
    # Restart Docker if it's running
    if systemctl is-active --quiet docker; then
        log INFO "Restarting Docker daemon..."
        systemctl restart docker
    fi
}

# Optimize kernel network parameters
optimize_kernel() {
    log INFO "Optimizing kernel network parameters..."
    
    # Backup existing sysctl configuration
    cp /etc/sysctl.conf /etc/sysctl.conf.backup 2>/dev/null || true
    
    # Add network optimizations
    cat >> /etc/sysctl.conf << 'EOF'

# Robustty Discord Bot Network Optimizations
# Network performance optimization
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.rmem_default = 262144
net.core.wmem_default = 262144
net.core.netdev_max_backlog = 5000
net.core.somaxconn = 65535

# TCP optimization
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_probes = 3
net.ipv4.tcp_keepalive_intvl = 15

# IP optimization
net.ipv4.ip_local_port_range = 16384 65535
net.ipv4.tcp_no_metrics_save = 1
net.ipv4.tcp_moderate_rcvbuf = 1
EOF
    
    # Apply the changes
    sysctl -p
    
    log INFO "Kernel network parameters optimized"
}

# Configure firewall
configure_firewall() {
    log INFO "Configuring firewall rules..."
    
    # Get the current user's IP for SSH access
    local current_ip
    current_ip=$(who am i | awk '{print $5}' | sed 's/[()]//g' | cut -d: -f1)
    
    if [[ -z "$current_ip" ]]; then
        log WARN "Could not detect current IP. Using SSH_CLIENT if available."
        current_ip=$(echo $SSH_CLIENT | cut -d' ' -f1)
    fi
    
    if [[ -z "$current_ip" ]]; then
        log ERROR "Could not detect current IP. Please configure SSH access manually."
        current_ip="0.0.0.0/0"
    fi
    
    log INFO "Configuring firewall for IP: $current_ip"
    
    # Configure UFW
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH access
    if [[ "$current_ip" != "0.0.0.0/0" ]]; then
        ufw allow from "$current_ip" to any port 22
    else
        log WARN "Allowing SSH from all IPs - SECURITY RISK!"
        ufw allow 22
    fi
    
    # Allow health check port (internal networks only)
    ufw allow from 10.0.0.0/8 to any port 8080
    ufw allow from 172.16.0.0/12 to any port 8080
    ufw allow from 192.168.0.0/16 to any port 8080
    
    # Allow Docker bridge networks
    ufw allow from 172.17.0.0/16
    ufw allow from 172.20.0.0/16
    
    # Allow essential outbound connections
    ufw allow out 443  # HTTPS
    ufw allow out 80   # HTTP
    ufw allow out 53   # DNS
    
    # Enable firewall
    ufw --force enable
    
    log INFO "Firewall configured successfully"
}

# Create network monitoring service
create_monitoring_service() {
    log INFO "Creating network monitoring service..."
    
    # Create monitoring script
    cat > /opt/robustty-network-monitor.sh << 'EOF'
#!/bin/bash

LOG_FILE="/var/log/robustty-network-monitor.log"

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check Discord connectivity
check_discord() {
    if curl -s --max-time 10 https://discord.com/api/v10/gateway > /dev/null; then
        log_message "✅ Discord API accessible"
        return 0
    else
        log_message "❌ Discord API unreachable"
        return 1
    fi
}

# Check DNS resolution
check_dns() {
    local failed=0
    for domain in discord.com googleapis.com; do
        if ! nslookup "$domain" > /dev/null 2>&1; then
            log_message "❌ DNS resolution failed for $domain"
            failed=1
        fi
    done
    
    if [ $failed -eq 0 ]; then
        log_message "✅ DNS resolution working"
    fi
    return $failed
}

# Main monitoring function
monitor_network() {
    log_message "🔍 Network monitoring check started"
    
    local discord_ok=0
    local dns_ok=0
    
    check_discord && discord_ok=1
    check_dns && dns_ok=1
    
    if [[ $discord_ok -eq 0 || $dns_ok -eq 0 ]]; then
        log_message "⚠️ Network issues detected"
        return 1
    else
        log_message "✅ All network checks passed"
        return 0
    fi
}

# Run monitoring
monitor_network
EOF
    
    chmod +x /opt/robustty-network-monitor.sh
    
    # Create systemd service
    cat > /etc/systemd/system/robustty-network-monitor.service << 'EOF'
[Unit]
Description=Robustty Network Monitor
After=network.target

[Service]
Type=oneshot
ExecStart=/opt/robustty-network-monitor.sh
User=root

[Install]
WantedBy=multi-user.target
EOF
    
    # Create timer for regular monitoring
    cat > /etc/systemd/system/robustty-network-monitor.timer << 'EOF'
[Unit]
Description=Run Robustty Network Monitor every 5 minutes
Requires=robustty-network-monitor.service

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    # Enable and start the timer
    systemctl daemon-reload
    systemctl enable robustty-network-monitor.timer
    systemctl start robustty-network-monitor.timer
    
    log INFO "Network monitoring service created and started"
}

# Create network diagnostic script
create_diagnostic_script() {
    log INFO "Creating network diagnostic script..."
    
    cat > /opt/robustty-network-diagnostics.sh << 'EOF'
#!/bin/bash

echo "🔍 Robustty Network Diagnostics"
echo "================================="

# System information
echo "📋 System Information:"
echo "OS: $(uname -a)"
echo "Network interfaces:"
ip addr show
echo ""

# DNS Configuration
echo "🌐 DNS Configuration:"
echo "System DNS:"
cat /etc/resolv.conf
echo "systemd-resolved status:"
systemd-resolve --status 2>/dev/null || resolvectl status 2>/dev/null || echo "systemd-resolved not available"
echo ""

# Port Status
echo "🔌 Port Status:"
echo "Listening ports:"
netstat -tulpn | grep LISTEN
echo ""
if command -v docker &> /dev/null; then
    echo "Docker port mappings:"
    docker ps --format "table {{.Names}}\t{{.Ports}}" 2>/dev/null || echo "Docker not running or no containers"
fi
echo ""

# Container Networking (if Docker is available)
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo "🐳 Container Networking:"
    echo "Docker networks:"
    docker network ls
    
    if docker ps --format "{{.Names}}" | grep -q robustty-bot; then
        echo "Container connectivity tests:"
        if docker exec robustty-bot ping -c 3 redis &> /dev/null; then
            echo "✅ Bot can reach Redis"
        else
            echo "❌ Bot cannot reach Redis"
        fi
    fi
    echo ""
fi

# External Connectivity
echo "🌍 External Connectivity:"
services=("discord.com" "googleapis.com" "apify.com")
for service in "${services[@]}"; do
    if curl -s --max-time 10 "https://$service" > /dev/null; then
        echo "✅ $service accessible"
    else
        echo "❌ $service unreachable"
    fi
done
echo ""

# Performance Metrics
echo "📊 Network Performance:"
echo "Network interface statistics:"
cat /proc/net/dev | head -3
echo ""

# Bot Health (if running)
echo "🤖 Bot Status:"
if curl -s --max-time 5 http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Bot health check passed"
    echo "Network status:"
    curl -s http://localhost:8080/network 2>/dev/null | jq . 2>/dev/null || echo "Network status unavailable"
else
    echo "❌ Bot health check failed or bot not running"
fi
echo ""

echo "Diagnostics complete. Full logs available at /var/log/robustty-network-monitor.log"
EOF
    
    chmod +x /opt/robustty-network-diagnostics.sh
    
    log INFO "Network diagnostic script created at /opt/robustty-network-diagnostics.sh"
}

# Validate network configuration
validate_configuration() {
    log INFO "Validating network configuration..."
    
    local validation_errors=0
    
    # Check DNS resolution
    log INFO "Testing DNS resolution..."
    local test_domains=("discord.com" "googleapis.com" "google.com")
    for domain in "${test_domains[@]}"; do
        if ! nslookup "$domain" > /dev/null 2>&1; then
            log ERROR "DNS resolution failed for $domain"
            ((validation_errors++))
        fi
    done
    
    # Check firewall rules
    log INFO "Checking firewall rules..."
    if command -v ufw &> /dev/null; then
        if ! ufw status | grep -q "Status: active"; then
            log ERROR "UFW firewall is not active"
            ((validation_errors++))
        fi
    fi
    
    # Check kernel parameters
    log INFO "Checking kernel parameters..."
    local bbr_enabled=$(sysctl net.ipv4.tcp_congestion_control | cut -d' ' -f3)
    if [[ "$bbr_enabled" != "bbr" ]]; then
        log WARN "BBR congestion control not enabled (current: $bbr_enabled)"
    fi
    
    # Check Docker configuration
    if command -v docker &> /dev/null; then
        log INFO "Checking Docker configuration..."
        if [[ -f /etc/docker/daemon.json ]]; then
            if ! jq . /etc/docker/daemon.json > /dev/null 2>&1; then
                log ERROR "Invalid Docker daemon.json configuration"
                ((validation_errors++))
            fi
        fi
    fi
    
    if [[ $validation_errors -eq 0 ]]; then
        log INFO "✅ All network configuration validation checks passed"
        return 0
    else
        log ERROR "❌ $validation_errors validation errors found"
        return 1
    fi
}

# Create emergency recovery script
create_recovery_script() {
    log INFO "Creating emergency recovery script..."
    
    cat > /opt/robustty-emergency-recovery.sh << 'EOF'
#!/bin/bash

echo "🚨 Emergency Network Recovery for Robustty Discord Bot"
echo "======================================================"

# Stop all services
echo "🛑 Stopping services..."
if command -v docker-compose &> /dev/null && [[ -f docker-compose.vps.yml ]]; then
    docker-compose -f docker-compose.vps.yml down 2>/dev/null || true
fi

# Reset Docker networking
echo "🔄 Resetting Docker networking..."
if command -v docker &> /dev/null; then
    docker network prune -f
    docker system prune -f --volumes
fi

# Reset system networking
echo "🌐 Resetting system networking..."
systemctl restart systemd-networkd 2>/dev/null || true
systemctl restart systemd-resolved

# Restart Docker
echo "🐳 Restarting Docker..."
if systemctl is-enabled docker &> /dev/null; then
    systemctl restart docker
fi

# Flush DNS cache
echo "🗑️ Flushing DNS cache..."
systemctl flush-dns 2>/dev/null || true
systemd-resolve --flush-caches 2>/dev/null || resolvectl flush-caches 2>/dev/null || true

# Wait for services to stabilize
echo "⏳ Waiting for services to stabilize..."
sleep 10

# Test connectivity
echo "🔍 Testing connectivity..."
if curl -s --max-time 10 https://discord.com/api/v10/gateway > /dev/null; then
    echo "✅ Discord API accessible"
else
    echo "❌ Discord API still unreachable"
fi

# Restart bot if compose file exists
if [[ -f docker-compose.vps.yml ]]; then
    echo "🚀 Restarting bot services..."
    docker-compose -f docker-compose.vps.yml up -d
else
    echo "⚠️ docker-compose.vps.yml not found in current directory"
fi

echo "✅ Emergency recovery completed"
echo "Check logs with: journalctl -u docker -f"
EOF
    
    chmod +x /opt/robustty-emergency-recovery.sh
    
    log INFO "Emergency recovery script created at /opt/robustty-emergency-recovery.sh"
}

# Main execution
main() {
    log INFO "Starting VPS network configuration for Robustty Discord Bot..."
    
    # Check requirements
    check_root
    detect_os
    
    # Perform configuration steps
    install_packages
    configure_dns
    configure_docker
    optimize_kernel
    configure_firewall
    create_monitoring_service
    create_diagnostic_script
    create_recovery_script
    
    # Validate configuration
    if validate_configuration; then
        log INFO "🎉 VPS networking setup completed successfully!"
        echo ""
        echo "Next steps:"
        echo "1. Test network connectivity: /opt/robustty-network-diagnostics.sh"
        echo "2. Deploy the bot: cd $PROJECT_ROOT && ./deploy-vps.sh"
        echo "3. Monitor network: tail -f /var/log/robustty-network-monitor.log"
        echo "4. Emergency recovery: /opt/robustty-emergency-recovery.sh"
        echo ""
        echo "Important files created:"
        echo "- Network monitor: /opt/robustty-network-monitor.sh"
        echo "- Diagnostics: /opt/robustty-network-diagnostics.sh"
        echo "- Emergency recovery: /opt/robustty-emergency-recovery.sh"
        echo "- Logs: /var/log/robustty-network-*.log"
    else
        log ERROR "Network setup completed with errors. Please review the logs."
        exit 1
    fi
}

# Handle script interruption
trap 'log ERROR "Script interrupted by user"; exit 1' INT TERM

# Run main function
main "$@"