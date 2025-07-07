#!/bin/bash
# Cookie Sync Script - Mac to VPS (with Persistent SSH)
# Extracts cookies on Mac and syncs them to VPS using SSH multiplexing

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
VPS_PATH="${VPS_PATH:-~/Robustty/cookies}"
SSH_KEY="${SSH_KEY_PATH:-~/.ssh/yeet}"
LOCAL_COOKIE_DIR="./cookies"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🍪 Robustty Cookie Sync to VPS${NC}"
echo "=================================="

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

# Check if local cookie directory exists
if [ ! -d "$LOCAL_COOKIE_DIR" ]; then
    echo -e "${YELLOW}⚠️  Creating local cookie directory...${NC}"
    mkdir -p "$LOCAL_COOKIE_DIR"
fi

echo -e "${BLUE}📍 Configuration:${NC}"
echo "  VPS Host: $VPS_HOST"
echo "  VPS User: $VPS_USER"
echo "  VPS Path: $VPS_PATH"
echo "  SSH Key:  $SSH_KEY"
echo "  Local:    $LOCAL_COOKIE_DIR"
echo ""

# Step 1: Extract cookies locally
echo -e "${BLUE}🔍 Step 1: Extracting cookies from Brave browser...${NC}"
if python3 scripts/extract-brave-cookies.py; then
    echo -e "${GREEN}✅ Cookie extraction completed${NC}"
else
    echo -e "${RED}❌ Cookie extraction failed${NC}"
    exit 1
fi

# Step 2: Check if we have cookies to sync
cookie_files=$(find "$LOCAL_COOKIE_DIR" -name "*.json" 2>/dev/null | wc -l)
if [ "$cookie_files" -eq 0 ]; then
    echo -e "${RED}❌ No cookie files found to sync${NC}"
    exit 1
fi

echo -e "${GREEN}📦 Found $cookie_files cookie files to sync${NC}"

# Step 3: Establish persistent SSH connection and execute combined operations
echo -e "${BLUE}🔗 Step 2: Establishing SSH connection and preparing remote environment...${NC}"
if ssh_connect_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"; then
    echo -e "${GREEN}✅ Persistent SSH connection established${NC}"
else
    echo -e "${RED}❌ Failed to establish SSH connection${NC}"
    echo "Please check:"
    echo "  - VPS is running and accessible"
    echo "  - SSH key is correct and added to VPS"
    echo "  - VPS_HOST and VPS_USER are correct"
    exit 1
fi

# Combined remote preparation in single SSH session
echo -e "${BLUE}📁 Step 3: Preparing remote environment (combined operations)...${NC}"
combined_prep_script="
    set -e
    echo 'Starting combined remote preparation...'
    
    # Create directory structure
    mkdir -p $VPS_PATH/{cookies,logs,backup}
    
    # Backup existing cookies if any
    if [ -d '$VPS_PATH/cookies' ] && [ \"\$(ls -A $VPS_PATH/cookies 2>/dev/null)\" ]; then
        backup_dir='$VPS_PATH/backup/cookies_\$(date +%Y%m%d_%H%M%S)'
        mkdir -p \"\$backup_dir\"
        cp -r $VPS_PATH/cookies/* \"\$backup_dir/\" 2>/dev/null || true
        echo \"Backup created: \$backup_dir\"
        
        # Clean old backups (keep last 3)
        find $VPS_PATH/backup -name 'cookies_*' -type d | sort -r | tail -n +4 | xargs rm -rf 2>/dev/null || true
    fi
    
    # Clear existing cookies for clean sync
    rm -f $VPS_PATH/cookies/*.json 2>/dev/null || true
    
    # System check
    echo \"Remote system ready - Host: \$(hostname), Date: \$(date)\"
    echo \"Disk space: \$(df -h $VPS_PATH | tail -1 | awk '{print \$4}') available\"
    
    echo 'Remote environment preparation completed'
"

if ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "$combined_prep_script"; then
    echo -e "${GREEN}✅ Remote environment prepared successfully${NC}"
else
    echo -e "${RED}❌ Remote environment preparation failed${NC}"
    exit 1
fi

# Step 4: Sync cookies to VPS using persistent connection
echo -e "${BLUE}🚀 Step 4: Syncing cookies to VPS using persistent SSH...${NC}"
if ssh_copy_persistent "to" "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "$LOCAL_COOKIE_DIR/" "$VPS_PATH/cookies/"; then
    echo -e "${GREEN}✅ Cookie sync completed successfully${NC}"
else
    echo -e "${RED}❌ Cookie sync failed${NC}"
    exit 1
fi

# Step 5: Verify sync and restart services in combined SSH session
echo -e "${BLUE}🔍 Step 5: Verifying sync and restarting services (combined operations)...${NC}"
combined_verify_restart_script="
    set -e
    echo 'Starting verification and service restart...'
    
    # Verify cookie sync
    cookie_count=\$(find $VPS_PATH/cookies -name '*.json' 2>/dev/null | wc -l)
    echo \"Cookie files synced: \$cookie_count\"
    
    if [ \$cookie_count -eq 0 ]; then
        echo 'ERROR: No cookie files found after sync'
        exit 1
    fi
    
    # List cookie files for verification
    echo 'Cookie files:'
    ls -la $VPS_PATH/cookies/*.json 2>/dev/null | head -3
    if [ \$cookie_count -gt 3 ]; then
        echo \"... and \$((cookie_count - 3)) more files\"
    fi
    
    # Test cookie file validity
    sample_cookie=\$(find $VPS_PATH/cookies -name '*.json' | head -1)
    if [ -n \"\$sample_cookie\" ]; then
        if python3 -m json.tool \"\$sample_cookie\" >/dev/null 2>&1; then
            echo 'Sample cookie file is valid JSON'
        else
            echo 'WARNING: Sample cookie file may be corrupted'
        fi
    fi
    
    # Navigate to project directory
    cd $VPS_PATH
    
    # Determine which docker-compose file to use
    if [ -f docker-compose.yml ]; then
        compose_file='docker-compose.yml'
    else
        echo 'WARNING: No docker-compose file found, skipping service restart'
        exit 0
    fi
    
    echo \"Using compose file: \$compose_file\"
    
    # Restart services
    echo 'Restarting Docker services...'
    docker-compose -f \"\$compose_file\" restart robustty || 
    docker-compose -f \"\$compose_file\" restart || {
        echo 'Service restart failed, trying full restart...'
        docker-compose -f \"\$compose_file\" down
        sleep 5
        docker-compose -f \"\$compose_file\" up -d
    }
    
    # Wait for services to start
    sleep 10
    
    # Check service status
    echo 'Service status:'
    docker-compose -f \"\$compose_file\" ps | grep -E '(robustty|bot)' || echo 'No matching services found'
    
    # Get recent logs
    echo 'Recent bot logs:'
    docker-compose -f \"\$compose_file\" logs --tail 5 robustty 2>/dev/null || 
    docker logs --tail 5 \$(docker ps -q --filter name=robustty) 2>/dev/null || 
    echo 'Could not retrieve recent logs'
    
    echo 'Verification and service restart completed'
"

if ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "$combined_verify_restart_script"; then
    echo -e "${GREEN}✅ Verification and service restart completed successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Verification completed but service restart may have issues${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Cookie sync process completed!${NC}"
echo -e "${BLUE}📋 Summary:${NC}"
echo "  - Extracted cookies from local Brave browser"
echo "  - Synced $cookie_files cookie files to VPS"
echo "  - VPS bot restarted to use new cookies"
echo ""
echo -e "${YELLOW}💡 To automate this process, you can:${NC}"
echo "  1. Add this script to a cron job on your Mac"
echo "  2. Run it manually when you want to update VPS cookies"
echo "  3. Set up the cookie service to run automatically"