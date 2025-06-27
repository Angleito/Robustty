#!/bin/bash

# VPS Deployment Script for Robustty Discord Bot (with Persistent SSH)
# This script sets up the bot on a VPS to use cookies from a remote machine
# Uses SSH multiplexing for efficient connection management

set -e

# Source the SSH persistent connection manager
SSH_PERSISTENT_SCRIPT="$(dirname "$0")/scripts/ssh-persistent.sh"
if [[ -f "$SSH_PERSISTENT_SCRIPT" ]]; then
    source "$SSH_PERSISTENT_SCRIPT"
else
    echo "Error: SSH persistent script not found at $SSH_PERSISTENT_SCRIPT"
    exit 1
fi

# Configuration
VPS_HOST="${1:-your-vps-ip}"
VPS_USER="${2:-ubuntu}"
NETWORKING_SETUP="${3:-auto}"  # auto, manual, skip

# Color codes
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
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" ;;
    esac
}

# Validate inputs
validate_inputs() {
    if [[ "$VPS_HOST" == "your-vps-ip" ]]; then
        log ERROR "Please provide a valid VPS IP address or hostname"
        echo "Usage: $0 <vps-host> [vps-user] [networking-setup]"
        echo "Example: $0 192.168.1.100 ubuntu auto"
        exit 1
    fi
    
    # Test SSH connectivity
    log INFO "Testing SSH connectivity to $VPS_USER@$VPS_HOST..."
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$VPS_USER@$VPS_HOST" "echo 'SSH connection successful'" 2>/dev/null; then
        log ERROR "Cannot connect to VPS via SSH. Please check:"
        echo "  - VPS IP/hostname: $VPS_HOST"
        echo "  - Username: $VPS_USER"
        echo "  - SSH key authentication is set up"
        echo "  - VPS firewall allows SSH on port 22"
        exit 1
    fi
    log INFO "✅ SSH connectivity confirmed"
}

# Pre-deployment network validation
validate_vps_network() {
    log INFO "🔍 Validating VPS network configuration..."
    
    # Check basic connectivity
    local network_checks_passed=0
    local total_checks=5
    
    # Test 1: DNS resolution
    log INFO "Testing DNS resolution on VPS..."
    if ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "nslookup discord.com > /dev/null 2>&1"; then
        log INFO "✅ DNS resolution working"
        ((network_checks_passed++))
    else
        log WARN "❌ DNS resolution failed"
    fi
    
    # Test 2: Discord API connectivity
    log INFO "Testing Discord API connectivity..."
    if ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "curl -s --max-time 10 https://discord.com/api/v10/gateway > /dev/null"; then
        log INFO "✅ Discord API accessible"
        ((network_checks_passed++))
    else
        log WARN "❌ Discord API unreachable"
    fi
    
    # Test 3: Required ports availability
    log INFO "Checking required ports..."
    if ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "! ss -tlnp | grep -q ':8080 '"; then
        log INFO "✅ Port 8080 available for health checks"
        ((network_checks_passed++))
    else
        log WARN "❌ Port 8080 is already in use"
    fi
    
    # Test 4: Outbound HTTPS connectivity
    log INFO "Testing outbound HTTPS connectivity..."
    if ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "curl -s --max-time 10 https://googleapis.com > /dev/null"; then
        log INFO "✅ Outbound HTTPS working"
        ((network_checks_passed++))
    else
        log WARN "❌ Outbound HTTPS blocked"
    fi
    
    # Test 5: Check if Docker networking will work
    log INFO "Testing Docker prerequisites..."
    if ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "ip route show | grep -q default"; then
        log INFO "✅ Default route configured"
        ((network_checks_passed++))
    else
        log WARN "❌ No default route found"
    fi
    
    # Summarize results
    log INFO "Network validation: $network_checks_passed/$total_checks checks passed"
    
    if [[ $network_checks_passed -lt 3 ]]; then
        log ERROR "Critical network issues detected. Deployment may fail."
        
        if [[ "$NETWORKING_SETUP" == "auto" ]]; then
            log INFO "Attempting automatic network configuration..."
            setup_vps_networking
        else
            log WARN "Network setup skipped. Consider running: sudo ./scripts/setup-vps-networking.sh"
        fi
    else
        log INFO "✅ Network validation passed"
    fi
}

# Setup VPS networking automatically
setup_vps_networking() {
    log INFO "🔧 Setting up VPS networking automatically..."
    
    # Copy networking setup script to VPS
    scp scripts/setup-vps-networking.sh "$VPS_USER@$VPS_HOST:/tmp/"
    
    # Execute networking setup on VPS
    ssh "$VPS_USER@$VPS_HOST" "
        chmod +x /tmp/setup-vps-networking.sh
        sudo /tmp/setup-vps-networking.sh
    "
    
    log INFO "✅ VPS networking setup completed"
}

log INFO "🚀 Deploying Robustty Discord Bot to VPS: $VPS_USER@$VPS_HOST"

# Run pre-deployment validation if script exists
if [ -f scripts/validate-pre-deployment.sh ]; then
    log INFO "🔍 Running pre-deployment validation..."
    if ! bash scripts/validate-pre-deployment.sh --quick; then
        log WARN "Pre-deployment validation failed. Continue anyway?"
        read -p "Continue deployment? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log ERROR "Deployment cancelled by user"
            exit 1
        fi
    fi
else
    log WARN "Pre-deployment validation script not found, skipping..."
fi

# Validate inputs and connectivity
validate_inputs

# Establish persistent SSH connection
log INFO "🔗 Establishing persistent SSH connection to VPS..."
if ! ssh_connect_persistent "$VPS_HOST" "$VPS_USER" "22"; then
    log ERROR "Failed to establish SSH connection to VPS"
    exit 1
fi

# Perform network validation
validate_vps_network

# Create deployment directory on VPS
echo "📁 Creating deployment directory..."
ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "mkdir -p ~/robustty-bot"

# Copy necessary files to VPS using persistent connection
echo "📤 Copying project files using persistent SSH..."
ssh_copy_persistent "to" "$VPS_HOST" "$VPS_USER" "22" "" "." "~/robustty-bot/" "--exclude='venv' --exclude='__pycache__' --exclude='.git' --exclude='logs' --exclude='data' --exclude='cookies'"

# Copy VPS-specific docker-compose
echo "📋 Setting up VPS configuration..."
ssh_copy_persistent "to" "$VPS_HOST" "$VPS_USER" "22" "" "docker-compose.vps.yml" "~/robustty-bot/docker-compose.yml"

# Copy environment file
if [ -f .env ]; then
    ssh_copy_persistent "to" "$VPS_HOST" "$VPS_USER" "22" "" ".env" "~/robustty-bot/.env"
else
    echo "⚠️  No .env file found. You'll need to create one on the VPS."
fi

# Create necessary directories on VPS
ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "cd ~/robustty-bot && mkdir -p logs data cookies"

# Run network diagnostics using persistent connection
echo "🔍 Running network diagnostics on VPS..."
ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "
    # Test basic connectivity first
    echo '⚡ Testing basic network connectivity...'
    
    # Test DNS resolution of Discord endpoints
    DISCORD_ENDPOINTS=('gateway-us-east1-d.discord.gg' 'discord.com' 'discordapp.com')
    DNS_OK=true
    
    for endpoint in \"\${DISCORD_ENDPOINTS[@]}\"; do
        if ! nslookup \"\$endpoint\" >/dev/null 2>&1; then
            echo \"❌ DNS resolution failed for \$endpoint\"
            DNS_OK=false
        else
            echo \"✅ DNS resolution OK for \$endpoint\"
        fi
    done
    
    # Test connectivity to Discord HTTPS port
    if command -v nc >/dev/null 2>&1; then
        if ! timeout 10 nc -z gateway-us-east1-d.discord.gg 443 >/dev/null 2>&1; then
            echo '❌ Cannot connect to Discord gateway on port 443'
            DNS_OK=false
        else
            echo '✅ Discord gateway port 443 is accessible'
        fi
    fi
    
    # Check DNS configuration
    echo '📋 DNS Configuration:'
    if [ -f /etc/resolv.conf ]; then
        cat /etc/resolv.conf | grep nameserver || echo 'No nameservers found'
    fi
    
    if [ \"\$DNS_OK\" = false ]; then
        echo ''
        echo '⚠️  DNS RESOLUTION ISSUES DETECTED!'
        echo 'This will prevent the Discord bot from connecting.'
        echo ''
        echo 'Potential fixes:'
        echo '1. Add public DNS servers:'
        echo '   echo \"nameserver 8.8.8.8\" | sudo tee -a /etc/resolv.conf'
        echo '   echo \"nameserver 1.1.1.1\" | sudo tee -a /etc/resolv.conf'
        echo '2. Check firewall rules allowing outbound DNS (port 53) and HTTPS (port 443)'
        echo '3. Contact your VPS provider about DNS/network restrictions'
        echo ''
        echo 'Run the full diagnostics script for detailed analysis:'
        echo '   ~/robustty-bot/scripts/diagnose-vps-network.sh'
        echo ''
        read -p 'Continue with deployment anyway? (y/N): ' -n 1 -r
        echo
        if [[ ! \$REPLY =~ ^[Yy]$ ]]; then
            echo 'Deployment cancelled. Fix DNS issues first.'
            exit 1
        fi
    else
        echo '✅ Network connectivity looks good!'
    fi
"

# Install Docker if not present using persistent connection
echo "🐳 Checking Docker installation..."
ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "
    if ! command -v docker &> /dev/null; then
        echo 'Installing Docker...'
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker \$USER
        echo 'Docker installed. You may need to log out and back in.'
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo 'Installing Docker Compose...'
        sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi"

# Set up cookie sync (choose one method below)
# Set up cookie sync (choose one method below)
cat << 'EOF'

🍪 COOKIE SYNC SETUP REQUIRED:

Choose one of these methods to sync cookies from your local machine to the VPS:

1. SCP/Rsync (Manual sync):
   rsync -av ./cookies/ $VPS_USER@$VPS_HOST:~/robustty-bot/cookies/

2. GitHub Actions (Automated):
   - Use the provided GitHub Actions workflow
   - Set repository secrets for VPS access

3. Network File System:
   - Mount a shared NFS/SSHFS between machines
   - Point both cookie directories to the same location

4. Cloud Storage:
   - Use AWS S3, Google Cloud Storage, or similar
   - Sync cookies via cloud bucket

EOF

# Copy validation script to VPS for post-deployment validation
if [ -f scripts/validate-vps-core.sh ]; then
    echo "📋 Copying validation tools to VPS..."
    scp scripts/validate-vps-core.sh $VPS_USER@$VPS_HOST:~/robustty-bot/scripts/
    ssh $VPS_USER@$VPS_HOST "chmod +x ~/robustty-bot/scripts/validate-vps-core.sh"
fi

echo "✅ VPS deployment prepared!"
echo "📝 Next steps:"
echo "1. Set up cookie synchronization (see options above)"
echo "2. Configure .env file on VPS: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && nano .env'"
echo "3. Start the bot: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && docker-compose up -d'"
echo "4. Validate deployment: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && ./scripts/validate-vps-core.sh'"
echo "5. Monitor logs: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && docker-compose logs -f'"
echo ""
echo "🔧 If DNS/connectivity issues occur:"
echo "   • Run diagnostics: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && ./scripts/diagnose-vps-network.sh'"
echo "   • Auto-fix DNS: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && sudo ./scripts/fix-vps-dns.sh'"
echo "   • View troubleshooting guide: docs/VPS-DNS-TROUBLESHOOTING.md"