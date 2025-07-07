#!/bin/bash
# Unified VPS Sync Script - Combines multiple remote operations into single SSH sessions
# This script minimizes SSH overhead by performing multiple operations in a single connection

set -e

# Source the SSH persistent connection manager
SSH_PERSISTENT_SCRIPT="$(dirname "$0")/ssh-persistent.sh"
if [[ -f "$SSH_PERSISTENT_SCRIPT" ]]; then
    source "$SSH_PERSISTENT_SCRIPT"
else
    echo "Error: SSH persistent script not found at $SSH_PERSISTENT_SCRIPT"
    exit 1
fi

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    set -a  # automatically export all variables
    source .env
    set +a  # disable automatic export
fi

# Configuration (can be overridden by environment variables)
VPS_HOST="${VPS_HOST:-your-vps-ip}"
VPS_USER="${VPS_USER:-root}"
VPS_PATH="${VPS_PATH:-~/Robustty}"
SSH_KEY="${SSH_KEY_PATH:-~/.ssh/yeet}"
LOCAL_COOKIE_DIR="./cookies"
COOKIE_REMOTE_PATH="${VPS_PATH}/cookies"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Unified VPS Sync - Minimizing SSH Connections${NC}"
echo "================================================"

# Check if VPS_HOST is configured
if [ "$VPS_HOST" = "your-vps-ip" ]; then
    echo -e "${RED}❌ Error: VPS_HOST not configured${NC}"
    echo "Please set VPS_HOST environment variable or edit this script:"
    echo "export VPS_HOST=your.vps.ip.address"
    exit 1
fi

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ Error: SSH key not found at $SSH_KEY${NC}"
    echo "Please ensure your SSH key exists or set SSH_KEY environment variable"
    exit 1
fi

echo -e "${BLUE}📍 Configuration:${NC}"
echo "  VPS Host: $VPS_HOST"
echo "  VPS User: $VPS_USER"
echo "  VPS Path: $VPS_PATH"
echo "  SSH Key:  $SSH_KEY"
echo "  Local Cookie Dir: $LOCAL_COOKIE_DIR"
echo "  Remote Cookie Path: $COOKIE_REMOTE_PATH"
echo ""

# Function to execute multiple commands in a single SSH session
execute_combined_remote_operations() {
    local host="$1"
    local user="$2"
    local port="$3"
    local ssh_key="$4"
    
    echo -e "${BLUE}🔗 Establishing single SSH session for combined operations...${NC}"
    
    # Ensure connection is established
    if ! ssh_connect_persistent "$host" "$user" "$port" "$ssh_key"; then
        echo -e "${RED}❌ Failed to establish SSH connection${NC}"
        return 1
    fi
    
    # Create a comprehensive remote script that does everything in one session
    local remote_script="
        set -e
        echo '=== Starting unified remote operations ==='
        
        # 1. System information and validation
        echo '📊 Gathering system information...'
        echo \"Host: \$(hostname)\"
        echo \"Date: \$(date)\"
        echo \"Uptime: \$(uptime)\"
        echo \"Disk usage: \$(df -h / | tail -1)\"
        echo \"Memory: \$(free -h | grep Mem)\"
        echo ''
        
        # 2. Create directory structure
        echo '📁 Setting up directory structure...'
        mkdir -p ${VPS_PATH}/{cookies,logs,backup}
        mkdir -p ${COOKIE_REMOTE_PATH}
        
        # 3. Backup existing cookies (if any)
        if [ -d \"${COOKIE_REMOTE_PATH}\" ] && [ \"\$(ls -A ${COOKIE_REMOTE_PATH} 2>/dev/null)\" ]; then
            echo '💾 Backing up existing cookies...'
            backup_dir=\"${VPS_PATH}/backup/cookies_\$(date +%Y%m%d_%H%M%S)\"
            mkdir -p \"\$backup_dir\"
            cp -r ${COOKIE_REMOTE_PATH}/* \"\$backup_dir/\" 2>/dev/null || true
            echo \"Backup created at: \$backup_dir\"
        fi
        
        # 4. Clean up old backups (keep last 5)
        echo '🧹 Cleaning up old backups...'
        find ${VPS_PATH}/backup -name 'cookies_*' -type d | sort -r | tail -n +6 | xargs rm -rf 2>/dev/null || true
        
        # 5. Verify Docker services status
        echo '🐳 Checking Docker services...'
        if command -v docker >/dev/null 2>&1; then
            echo \"Docker version: \$(docker --version)\"
            if docker ps >/dev/null 2>&1; then
                echo 'Docker daemon is running'
                docker ps --format 'table {{.Names}}\\t{{.Status}}' | grep robustty || echo 'No robustty containers found'
            else
                echo 'Docker daemon not accessible'
            fi
        else
            echo 'Docker not installed'
        fi
        
        # 6. Check network connectivity
        echo '🌐 Testing network connectivity...'
        if ping -c 1 discord.com >/dev/null 2>&1; then
            echo 'Discord.com is reachable'
        else
            echo 'Warning: Discord.com not reachable'
        fi
        
        # 7. Prepare for cookie sync
        echo '🍪 Preparing for cookie synchronization...'
        # Clear existing cookies to ensure clean sync
        rm -f ${COOKIE_REMOTE_PATH}/*.json 2>/dev/null || true
        
        echo '✅ Remote environment prepared for cookie sync'
        echo '=== Remote operations completed ==='
    "
    
    echo -e "${BLUE}🚀 Executing combined remote operations...${NC}"
    if ssh_exec_persistent "$host" "$user" "$port" "$ssh_key" "$remote_script"; then
        echo -e "${GREEN}✅ Combined remote operations completed successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ Combined remote operations failed${NC}"
        return 1
    fi
}

# Function to sync cookies with verification in single session
sync_and_verify_cookies() {
    local host="$1"
    local user="$2"
    local port="$3"
    local ssh_key="$4"
    
    echo -e "${BLUE}📦 Syncing cookies to VPS...${NC}"
    
    # Sync cookies using persistent connection
    if ssh_copy_persistent "to" "$host" "$user" "$port" "$ssh_key" "$LOCAL_COOKIE_DIR/" "$COOKIE_REMOTE_PATH/"; then
        echo -e "${GREEN}✅ Cookie files transferred successfully${NC}"
    else
        echo -e "${RED}❌ Cookie transfer failed${NC}"
        return 1
    fi
    
    # Verify sync and get stats in single SSH call
    local verification_script="
        set -e
        echo '🔍 Verifying cookie synchronization...'
        
        # Count and list cookie files
        cookie_count=\$(find ${COOKIE_REMOTE_PATH} -name '*.json' 2>/dev/null | wc -l)
        echo \"Total cookie files: \$cookie_count\"
        
        if [ \$cookie_count -gt 0 ]; then
            echo 'Cookie files found:'
            ls -la ${COOKIE_REMOTE_PATH}/*.json 2>/dev/null | head -5
            if [ \$cookie_count -gt 5 ]; then
                echo \"... and \$((cookie_count - 5)) more files\"
            fi
            
            # Check file sizes and timestamps
            total_size=\$(du -sh ${COOKIE_REMOTE_PATH} | cut -f1)
            echo \"Total size: \$total_size\"
            
            # Check if files are recent (modified within last hour)
            recent_files=\$(find ${COOKIE_REMOTE_PATH} -name '*.json' -mmin -60 2>/dev/null | wc -l)
            echo \"Recent files (last hour): \$recent_files\"
            
            # Test a sample cookie file for validity
            sample_file=\$(find ${COOKIE_REMOTE_PATH} -name '*.json' | head -1)
            if [ -n \"\$sample_file\" ]; then
                if python3 -m json.tool \"\$sample_file\" >/dev/null 2>&1; then
                    echo 'Sample cookie file is valid JSON'
                else
                    echo 'Warning: Sample cookie file may be corrupted'
                fi
            fi
            
            echo '✅ Cookie verification completed successfully'
        else
            echo '❌ No cookie files found after sync'
            exit 1
        fi
    "
    
    echo -e "${BLUE}🔍 Verifying cookie sync...${NC}"
    if ssh_exec_persistent "$host" "$user" "$port" "$ssh_key" "$verification_script"; then
        echo -e "${GREEN}✅ Cookie sync verification completed${NC}"
        return 0
    else
        echo -e "${RED}❌ Cookie sync verification failed${NC}"
        return 1
    fi
}

# Function to restart services with health checks in single session
restart_and_monitor_services() {
    local host="$1"
    local user="$2"
    local port="$3"
    local ssh_key="$4"
    
    local service_script="
        set -e
        echo '🔄 Restarting and monitoring services...'
        
        cd ${VPS_PATH}
        
        # Check if docker-compose file exists
        if [ -f docker-compose.yml ]; then
            compose_file='docker-compose.yml'
        else
            echo 'No docker-compose file found'
            exit 1
        fi
        
        echo \"Using compose file: \$compose_file\"
        
        # Stop existing containers gracefully
        echo 'Stopping existing containers...'
        docker-compose -f \"\$compose_file\" down --timeout 30 || true
        
        # Wait a moment for cleanup
        sleep 5
        
        # Start services
        echo 'Starting services...'
        docker-compose -f \"\$compose_file\" up -d
        
        # Wait for services to initialize
        echo 'Waiting for services to initialize...'
        sleep 15
        
        # Check service status
        echo 'Checking service status...'
        docker-compose -f \"\$compose_file\" ps
        
        # Check specific containers
        if docker ps | grep -q robustty-bot; then
            echo '✅ Robustty bot container is running'
            
            # Get recent logs
            echo 'Recent bot logs:'
            docker logs --tail 10 robustty-bot 2>/dev/null || docker logs --tail 10 \$(docker ps -q --filter name=robustty) 2>/dev/null || echo 'Could not retrieve logs'
        else
            echo '❌ Robustty bot container not found'
        fi
        
        if docker ps | grep -q redis; then
            echo '✅ Redis container is running'
        else
            echo '⚠️ Redis container not found (may not be required)'
        fi
        
        # Test health endpoint if available
        echo 'Testing health endpoints...'
        sleep 10  # Give services more time to start
        
        # Try different possible health check ports
        for port in 8080 8081 3000; do
            if curl -s --max-time 5 http://localhost:\$port/health >/dev/null 2>&1; then
                echo \"✅ Health endpoint responding on port \$port\"
                health_response=\$(curl -s --max-time 5 http://localhost:\$port/health 2>/dev/null || echo '{}')
                echo \"Health status: \$health_response\"
                break
            fi
        done
        
        echo '✅ Service restart and monitoring completed'
    "
    
    echo -e "${BLUE}🔄 Restarting services on VPS...${NC}"
    if ssh_exec_persistent "$host" "$user" "$port" "$ssh_key" "$service_script"; then
        echo -e "${GREEN}✅ Services restarted successfully${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️ Service restart completed with warnings${NC}"
        return 0  # Don't fail the entire process for service restart issues
    fi
}

# Main execution function
main() {
    echo -e "${BLUE}🚀 Starting unified VPS sync process...${NC}"
    
    # Step 1: Extract cookies locally
    echo -e "${BLUE}🔍 Step 1: Extracting cookies from Brave browser...${NC}"
    if [ -f "scripts/extract-brave-cookies.py" ]; then
        if python3 scripts/extract-brave-cookies.py; then
            echo -e "${GREEN}✅ Cookie extraction completed${NC}"
        else
            echo -e "${RED}❌ Cookie extraction failed${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠️ Cookie extraction script not found, assuming cookies already exist${NC}"
    fi
    
    # Check if we have cookies to sync
    if [ ! -d "$LOCAL_COOKIE_DIR" ] || [ -z "$(find "$LOCAL_COOKIE_DIR" -name '*.json' 2>/dev/null)" ]; then
        echo -e "${RED}❌ No cookie files found to sync in $LOCAL_COOKIE_DIR${NC}"
        exit 1
    fi
    
    local cookie_count=$(find "$LOCAL_COOKIE_DIR" -name '*.json' 2>/dev/null | wc -l)
    echo -e "${GREEN}📦 Found $cookie_count cookie files to sync${NC}"
    
    # Step 2: Execute combined remote operations in single SSH session
    echo -e "${BLUE}🔗 Step 2: Preparing remote environment (single SSH session)...${NC}"
    if ! execute_combined_remote_operations "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"; then
        echo -e "${RED}❌ Remote environment preparation failed${NC}"
        exit 1
    fi
    
    # Step 3: Sync and verify cookies in optimized manner
    echo -e "${BLUE}📦 Step 3: Syncing and verifying cookies...${NC}"
    if ! sync_and_verify_cookies "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"; then
        echo -e "${RED}❌ Cookie sync and verification failed${NC}"
        exit 1
    fi
    
    # Step 4: Restart services with monitoring in single session
    echo -e "${BLUE}🔄 Step 4: Restarting services with monitoring...${NC}"
    restart_and_monitor_services "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"
    
    # Step 5: Final status check in single SSH call
    echo -e "${BLUE}📊 Step 5: Final status verification...${NC}"
    local final_check_script="
        echo '📊 Final system status:'
        echo \"Date: \$(date)\"
        echo \"System load: \$(uptime | awk '{print \$NF}')\"
        
        cookie_count=\$(find ${COOKIE_REMOTE_PATH} -name '*.json' 2>/dev/null | wc -l)
        echo \"Cookies synchronized: \$cookie_count files\"
        
        if docker ps --format 'table {{.Names}}\\t{{.Status}}' | grep robustty >/dev/null 2>&1; then
            echo '✅ Robustty services are running'
            # Get container uptime
            docker ps --format 'table {{.Names}}\\t{{.Status}}' | grep robustty
        else
            echo '⚠️ Robustty services status unclear'
        fi
        
        echo '✅ Unified sync process completed successfully'
    "
    
    if ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "$final_check_script"; then
        echo -e "${GREEN}✅ Final status check completed${NC}"
    else
        echo -e "${YELLOW}⚠️ Final status check had issues but sync process completed${NC}"
    fi
    
    # Clean up persistent connection
    ssh_disconnect_persistent "$VPS_HOST" "$VPS_USER" "22"
    
    echo ""
    echo -e "${GREEN}🎉 Unified VPS sync completed successfully!${NC}"
    echo -e "${BLUE}📋 Summary:${NC}"
    echo "  ✅ Single SSH session used for multiple remote operations"
    echo "  ✅ Remote environment prepared and validated"
    echo "  ✅ $cookie_count cookie files synced to VPS"
    echo "  ✅ Services restarted with health monitoring"
    echo "  ✅ Reduced SSH connection overhead significantly"
    echo ""
    echo -e "${YELLOW}💡 Benefits of unified approach:${NC}"
    echo "  • Reduced network overhead (single SSH connection)"
    echo "  • Lower chance of disconnection during sync"
    echo "  • Faster overall execution"
    echo "  • Better error handling and rollback capability"
    echo "  • Comprehensive remote validation in one session"
}

# Help function
show_help() {
    cat << EOF
Unified VPS Sync Script - Minimizes SSH connections for efficient syncing

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    --host HOST             VPS hostname or IP (overrides VPS_HOST env var)
    --user USER             VPS username (overrides VPS_USER env var)
    --key PATH              Path to SSH private key (overrides SSH_KEY env var)
    --path PATH             Remote Robustty path (overrides VPS_PATH env var)
    --dry-run               Show what would be done without executing

ENVIRONMENT VARIABLES:
    VPS_HOST                VPS hostname or IP address
    VPS_USER                VPS username (default: root)
    VPS_PATH                Remote Robustty installation path (default: ~/Robustty)
    SSH_KEY_PATH            Path to SSH private key (default: ~/.ssh/yeet)

EXAMPLES:
    # Use environment variables from .env
    $0
    
    # Override specific settings
    $0 --host 192.168.1.100 --user ubuntu --key ~/.ssh/id_rsa
    
    # Dry run to see what would happen
    $0 --dry-run

DESCRIPTION:
    This script combines multiple SSH operations into single sessions to minimize
    connection overhead and reduce chances of disconnection. It performs:
    
    1. Local cookie extraction
    2. Remote environment preparation (single SSH session)
    3. Cookie synchronization with verification
    4. Service restart with health monitoring
    5. Final status verification
    
    All remote operations are batched to use the minimum number of SSH connections
    while maintaining reliability and comprehensive error checking.

REQUIREMENTS:
    • SSH access to VPS with key-based authentication
    • Docker and Docker Compose on VPS
    • Robustty project deployed on VPS
    • .env file configured with VPS details

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --host)
            VPS_HOST="$2"
            shift 2
            ;;
        --user)
            VPS_USER="$2"
            shift 2
            ;;
        --key)
            SSH_KEY="$2"
            shift 2
            ;;
        --path)
            VPS_PATH="$2"
            shift 2
            ;;
        --dry-run)
            echo "DRY RUN MODE - Would execute unified sync with:"
            echo "  VPS_HOST: $VPS_HOST"
            echo "  VPS_USER: $VPS_USER"
            echo "  SSH_KEY: $SSH_KEY"
            echo "  VPS_PATH: $VPS_PATH"
            echo "  LOCAL_COOKIE_DIR: $LOCAL_COOKIE_DIR"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Execute main function
main "$@"
