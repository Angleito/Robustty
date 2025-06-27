#!/bin/bash
# Enhanced VPS Deployment Script with Integrated Validation
# Robustty Discord Bot - VPS Deployment with validation checkpoints

set -e

# Source the SSH retry wrapper for network resilience
SSH_RETRY_SCRIPT="$(dirname "$0")/scripts/ssh-retry-wrapper.sh"
if [[ -f "$SSH_RETRY_SCRIPT" ]]; then
    source "$SSH_RETRY_SCRIPT"
    echo "✅ SSH retry wrapper loaded for network resilience"
else
    echo "⚠️  SSH retry wrapper not found - SSH commands will run without retry logic"
fi

# Configuration
VPS_HOST="${1:-your-vps-ip}"
VPS_USER="${2:-ubuntu}"
VALIDATION_MODE="${3:-full}"  # full, quick, skip
NETWORKING_SETUP="${4:-auto}"  # auto, manual, skip

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Progress tracking
DEPLOYMENT_STAGE="pre-deployment"
VALIDATION_RESULTS=()

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%H:%M:%S')
    
    case $level in
        INFO)  echo -e "${BLUE}[$timestamp]${NC} $message" ;;
        PASS)  echo -e "${GREEN}[$timestamp] ✅${NC} $message" ;;
        FAIL)  echo -e "${RED}[$timestamp] ❌${NC} $message" ;;
        WARN)  echo -e "${YELLOW}[$timestamp] ⚠️${NC} $message" ;;
        ERROR) echo -e "${RED}[$timestamp] 🚨${NC} $message" ;;
        STAGE) echo -e "${CYAN}[$timestamp] 🚀${NC} $message" ;;
    esac
}

# Progress indicator
show_stage() {
    local stage="$1"
    DEPLOYMENT_STAGE="$stage"
    echo ""
    log STAGE "DEPLOYMENT STAGE: $stage"
    echo "$(printf '=%.0s' {1..50})"
}

# Validation checkpoint runner
run_validation_checkpoint() {
    local checkpoint_name="$1"
    local script_path="$2"
    local is_critical="${3:-true}"
    local script_args="${4:-}"
    
    log INFO "Running validation checkpoint: $checkpoint_name"
    
    if [[ "$VALIDATION_MODE" == "skip" ]]; then
        log WARN "Validation skipped by user request"
        return 0
    fi
    
    local validation_args=""
    if [[ "$VALIDATION_MODE" == "quick" ]]; then
        validation_args="--quick"
    fi
    
    if [[ -n "$script_args" ]]; then
        validation_args="$validation_args $script_args"
    fi
    
    if [[ -f "$script_path" ]]; then
        if bash "$script_path" $validation_args; then
            log PASS "$checkpoint_name validation passed"
            VALIDATION_RESULTS+=("$checkpoint_name: PASSED")
            return 0
        else
            local exit_code=$?
            if [[ "$is_critical" == "true" && $exit_code -eq 2 ]]; then
                log FAIL "$checkpoint_name validation failed critically"
                VALIDATION_RESULTS+=("$checkpoint_name: CRITICAL FAILURE")
                echo ""
                log ERROR "Critical validation failure. Deployment aborted."
                echo "Fix the issues above and retry deployment."
                exit 1
            else
                log WARN "$checkpoint_name validation completed with warnings"
                VALIDATION_RESULTS+=("$checkpoint_name: WARNINGS")
                
                echo ""
                read -p "Continue deployment despite validation warnings? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    log INFO "Deployment cancelled by user"
                    exit 1
                fi
            fi
        fi
    else
        log WARN "Validation script not found: $script_path"
        VALIDATION_RESULTS+=("$checkpoint_name: SCRIPT NOT FOUND")
    fi
}

# Show help
show_help() {
    cat << EOF
Enhanced VPS Deployment Script with Validation for Robustty Discord Bot

Usage: $0 <vps-host> [vps-user] [validation-mode] [networking-setup]

PARAMETERS:
    vps-host            VPS IP address or hostname (required)
    vps-user            SSH username (default: ubuntu)
    validation-mode     Validation level: full, quick, skip (default: full)
    networking-setup    Network config: auto, manual, skip (default: auto)

VALIDATION MODES:
    full               Complete validation with all checks
    quick             Essential checks only for faster deployment
    skip              Skip all validation (not recommended)

NETWORKING SETUP:
    auto              Automatically configure VPS networking if needed
    manual            Manual network configuration prompts
    skip              Skip network configuration

EXAMPLES:
    $0 192.168.1.100                           # Full deployment with validation
    $0 192.168.1.100 ubuntu quick              # Quick validation deployment
    $0 192.168.1.100 root skip auto            # Skip validation, auto networking

VALIDATION CHECKPOINTS:
    1. Pre-deployment: System requirements and prerequisites
    2. Remote validation: VPS environment validation
    3. Post-deployment: Service health and functionality validation

EXIT CODES:
    0   Deployment successful
    1   Deployment failed or cancelled
    2   Critical validation failures
EOF
}

# Pre-deployment validation
pre_deployment_validation() {
    show_stage "PRE-DEPLOYMENT VALIDATION"
    
    log INFO "Validating local environment and prerequisites..."
    
    # Run pre-deployment validation
    run_validation_checkpoint "pre-deployment" "./scripts/validate-pre-deployment.sh" true
    
    # Validate inputs
    if [[ "$VPS_HOST" == "your-vps-ip" ]]; then
        log ERROR "Please provide a valid VPS IP address or hostname"
        echo ""
        show_help
        exit 1
    fi
    
    # Test SSH connectivity with retry
    log INFO "Testing SSH connectivity to $VPS_USER@$VPS_HOST..."
    if ! ssh_retry -o ConnectTimeout=10 -o BatchMode=yes "$VPS_USER@$VPS_HOST" "echo 'SSH connection successful'" 2>/dev/null; then
        log ERROR "Cannot connect to VPS via SSH after multiple retries. Please check:"
        echo "  - VPS IP/hostname: $VPS_HOST"
        echo "  - Username: $VPS_USER"
        echo "  - SSH key authentication is set up"
        echo "  - VPS firewall allows SSH on port 22"
        echo "  - Network connectivity and potential rate limiting"
        exit 1
    fi
    log PASS "SSH connectivity confirmed"
}

# VPS environment validation
vps_environment_validation() {
    show_stage "VPS ENVIRONMENT VALIDATION"
    
    log INFO "Validating VPS environment..."
    
    # Copy validation scripts to VPS
    log INFO "Copying validation scripts to VPS..."
    scp_retry scripts/validate-vps-core.sh "$VPS_USER@$VPS_HOST:/tmp/"
    ssh_retry "$VPS_USER@$VPS_HOST" "chmod +x /tmp/validate-vps-core.sh"
    
    # Run remote validation
    log INFO "Running VPS environment validation..."
    local validation_args=""
    if [[ "$VALIDATION_MODE" == "quick" ]]; then
        validation_args="--quick"
    fi
    
    if ssh "$VPS_USER@$VPS_HOST" "cd /tmp && ./validate-vps-core.sh $validation_args --no-docker"; then
        log PASS "VPS environment validation passed"
    else
        local exit_code=$?
        if [[ $exit_code -eq 2 ]]; then
            log FAIL "Critical VPS environment issues detected"
            echo ""
            log ERROR "VPS environment not suitable for deployment."
            echo "Common fixes:"
            echo "• DNS: ssh $VPS_USER@$VPS_HOST 'echo nameserver 8.8.8.8 | sudo tee /etc/resolv.conf'"
            echo "• Docker: ssh $VPS_USER@$VPS_HOST 'curl -fsSL https://get.docker.com | sh'"
            echo "• Memory: Upgrade VPS to at least 1GB RAM"
            exit 1
        else
            log WARN "VPS environment validation completed with warnings"
            echo ""
            read -p "Continue deployment despite VPS warnings? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log INFO "Deployment cancelled by user"
                exit 1
            fi
        fi
    fi
}

# Project deployment
deploy_project() {
    show_stage "PROJECT DEPLOYMENT"
    
    # Create deployment directory on VPS
    log INFO "Creating deployment directory..."
    ssh "$VPS_USER@$VPS_HOST" "mkdir -p ~/robustty-bot"
    
    # Copy project files to VPS
    log INFO "Copying project files..."
    rsync -av --exclude='venv' --exclude='__pycache__' --exclude='.git' \
        --exclude='logs' --exclude='data' --exclude='cookies' \
        ./ "$VPS_USER@$VPS_HOST:~/robustty-bot/"
    
    # Copy VPS-specific configuration
    log INFO "Setting up VPS configuration..."
    scp docker-compose.vps.yml "$VPS_USER@$VPS_HOST:~/robustty-bot/docker-compose.yml"
    
    # Copy environment file
    if [ -f .env ]; then
        scp .env "$VPS_USER@$VPS_HOST:~/robustty-bot/"
        log PASS "Environment file copied"
    else
        log WARN "No .env file found locally"
        echo ""
        log INFO "You'll need to create .env on the VPS:"
        echo "ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && cp .env.example .env && nano .env'"
    fi
    
    # Create necessary directories
    ssh "$VPS_USER@$VPS_HOST" "cd ~/robustty-bot && mkdir -p logs data cookies"
    log PASS "Project deployment completed"
}

# Docker setup and installation
setup_docker() {
    show_stage "DOCKER SETUP"
    
    log INFO "Setting up Docker environment..."
    
    # Install Docker if not present
    ssh "$VPS_USER@$VPS_HOST" "
        if ! command -v docker &> /dev/null; then
            echo 'Installing Docker...'
            curl -fsSL https://get.docker.com | sh
            sudo usermod -aG docker \$USER
            echo 'Docker installed successfully'
        else
            echo 'Docker already installed'
        fi
        
        if ! command -v docker-compose &> /dev/null; then
            echo 'Installing Docker Compose...'
            sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            echo 'Docker Compose installed successfully'
        else
            echo 'Docker Compose already installed'
        fi
    "
    
    log PASS "Docker setup completed"
}

# Service deployment
deploy_services() {
    show_stage "SERVICE DEPLOYMENT"
    
    log INFO "Starting Docker services..."
    
    # Start services on VPS
    ssh "$VPS_USER@$VPS_HOST" "
        cd ~/robustty-bot
        echo 'Pulling Docker images...'
        docker-compose pull
        echo 'Starting services...'
        docker-compose up -d
        echo 'Services started successfully'
    "
    
    log PASS "Services deployed and started"
}

# Post-deployment validation
post_deployment_validation() {
    show_stage "POST-DEPLOYMENT VALIDATION"
    
    log INFO "Validating deployed services..."
    
    # Run post-deployment validation on VPS
    ssh "$VPS_USER@$VPS_HOST" "
        cd ~/robustty-bot
        if [ -f scripts/validate-vps-core.sh ]; then
            echo 'Running post-deployment validation...'
            ./scripts/validate-vps-core.sh
        else
            echo 'Post-deployment validation script not found'
        fi
    "
    
    log PASS "Post-deployment validation completed"
}

# Cookie sync setup guidance
setup_cookie_sync() {
    show_stage "COOKIE SYNCHRONIZATION SETUP"
    
    cat << 'EOF'

🍪 COOKIE SYNC SETUP REQUIRED:

Your bot is deployed but needs cookies for optimal platform functionality.
Choose one of these methods to sync cookies:

1. Manual Sync (Quick start):
   rsync -av ./cookies/ $VPS_USER@$VPS_HOST:~/robustty-bot/cookies/

2. Automated Sync Script:
   ./sync-cookies-vps.sh

3. Scheduled Sync (Recommended):
   Set up a cron job to sync cookies regularly:
   */30 * * * * rsync -av ./cookies/ $VPS_USER@$VPS_HOST:~/robustty-bot/cookies/

4. Network File System:
   Mount shared storage between local and VPS environments

EOF

    echo -e "${YELLOW}Choose your cookie sync method:${NC}"
    echo "1) Manual sync now"
    echo "2) Setup automated sync"
    echo "3) Skip for now"
    
    read -p "Enter choice (1-3): " -n 1 -r
    echo
    
    case $REPLY in
        1)
            if [ -d ./cookies ]; then
                log INFO "Syncing cookies to VPS..."
                rsync -av ./cookies/ "$VPS_USER@$VPS_HOST:~/robustty-bot/cookies/"
                log PASS "Cookies synced successfully"
            else
                log WARN "No local cookies directory found"
            fi
            ;;
        2)
            log INFO "Setting up automated cookie sync..."
            echo "Add this to your crontab (crontab -e):"
            echo "*/30 * * * * rsync -av $(pwd)/cookies/ $VPS_USER@$VPS_HOST:~/robustty-bot/cookies/"
            ;;
        3)
            log INFO "Cookie sync skipped - remember to set up later"
            ;;
    esac
}

# Final deployment report
generate_deployment_report() {
    show_stage "DEPLOYMENT SUMMARY"
    
    echo ""
    log INFO "📋 DEPLOYMENT COMPLETED SUCCESSFULLY!"
    echo "===================================="
    
    echo ""
    echo -e "${GREEN}✅ Deployment Details:${NC}"
    echo "  • VPS: $VPS_USER@$VPS_HOST"
    echo "  • Project Path: ~/robustty-bot"
    echo "  • Validation Mode: $VALIDATION_MODE"
    echo "  • Networking: $NETWORKING_SETUP"
    
    echo ""
    echo -e "${BLUE}📊 Validation Results:${NC}"
    for result in "${VALIDATION_RESULTS[@]}"; do
        echo "  • $result"
    done
    
    echo ""
    echo -e "${CYAN}🔧 Management Commands:${NC}"
    echo "  • Check status: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && docker-compose ps'"
    echo "  • View logs: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && docker-compose logs -f'"
    echo "  • Restart: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && docker-compose restart'"
    echo "  • Stop: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && docker-compose down'"
    
    echo ""
    echo -e "${YELLOW}📚 Useful Resources:${NC}"
    echo "  • Monitor health: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && ./scripts/monitor-vps-health.sh'"
    echo "  • Network diagnostics: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && ./scripts/diagnose-vps-network.sh'"
    echo "  • Documentation: docs/VPS_TROUBLESHOOTING.md"
    
    echo ""
    log PASS "Deployment completed successfully! 🎉"
}

# Parse arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
esac

# Main deployment execution
main() {
    log INFO "🚀 Starting Enhanced VPS Deployment with Validation"
    echo "=================================================="
    echo "VPS: $VPS_USER@$VPS_HOST"
    echo "Validation: $VALIDATION_MODE"
    echo "Networking: $NETWORKING_SETUP"
    echo ""
    
    # Execute deployment stages
    pre_deployment_validation
    vps_environment_validation
    deploy_project
    setup_docker
    deploy_services
    post_deployment_validation
    setup_cookie_sync
    generate_deployment_report
}

# Execute main function
main "$@"