#!/bin/bash

# Robustty Cookie Sync Script
# Syncs cookies from macOS Docker container to Ubuntu VPS
# This script should be run on the macOS host machine

# Configuration - Update these values
VPS_HOST="${VPS_HOST:-your.vps.ip.address}"
VPS_USER="${VPS_USER:-your-vps-username}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/robustty_vps}"
VPS_COOKIE_DIR="${VPS_COOKIE_DIR:-/opt/robustty/cookies}"

# Docker configuration
CONTAINER_NAME="robustty-bot"
LOCAL_COOKIE_DIR="./data/cookies"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to log with timestamp
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Check if required tools are available
check_requirements() {
    local missing_tools=()
    
    for tool in docker rsync ssh; do
        if ! command -v $tool &> /dev/null; then
            missing_tools+=($tool)
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
}

# Main sync process
main() {
    log "Starting cookie sync process..."
    
    # Check requirements
    check_requirements
    
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        error "Docker container '${CONTAINER_NAME}' is not running"
        exit 1
    fi
    
    # Step 1: Extract cookies from Brave on macOS
    log "Extracting cookies from Brave browser..."
    if docker exec $CONTAINER_NAME python scripts/extract-brave-cookies.py; then
        log "Cookie extraction completed successfully"
    else
        error "Failed to extract cookies from Brave browser"
        exit 1
    fi
    
    # Step 2: Create local directory if it doesn't exist
    mkdir -p "$LOCAL_COOKIE_DIR"
    
    # Step 3: Copy cookies from container to host
    log "Copying cookies from Docker container to host..."
    if docker cp "$CONTAINER_NAME:/app/cookies/." "$LOCAL_COOKIE_DIR/"; then
        log "Cookies copied to host successfully"
    else
        error "Failed to copy cookies from Docker container"
        exit 1
    fi
    
    # Step 4: Check if we have any cookie files
    cookie_count=$(find "$LOCAL_COOKIE_DIR" -name "*.json" -type f | wc -l)
    if [ "$cookie_count" -eq 0 ]; then
        warning "No cookie files found to sync"
        exit 0
    fi
    log "Found $cookie_count cookie file(s) to sync"
    
    # Step 5: Test SSH connection
    log "Testing SSH connection to VPS..."
    if ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
        "$VPS_USER@$VPS_HOST" "echo 'SSH connection successful'" &>/dev/null; then
        log "SSH connection verified"
    else
        error "Failed to connect to VPS via SSH. Check your SSH key and connection settings."
        exit 1
    fi
    
    # Step 6: Create remote directory if it doesn't exist
    log "Ensuring remote cookie directory exists..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" \
        "sudo mkdir -p $VPS_COOKIE_DIR"
    
    # Step 7: Sync to VPS using rsync
    log "Syncing cookies to VPS..."
    if rsync -avz --delete \
        -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
        "$LOCAL_COOKIE_DIR/" \
        "$VPS_USER@$VPS_HOST:$VPS_COOKIE_DIR/"; then
        log "Cookie sync completed successfully"
    else
        error "Failed to sync cookies to VPS"
        exit 1
    fi
    
    # Step 8: Fix permissions on VPS
    log "Setting permissions on VPS..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" \
        "sudo chown -R \$(id -u):\$(id -g) $VPS_COOKIE_DIR && \
         sudo chmod -R 644 $VPS_COOKIE_DIR/*.json 2>/dev/null || true"
    
    # Step 9: Verify sync
    remote_count=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" \
        "find $VPS_COOKIE_DIR -name '*.json' -type f | wc -l")
    
    if [ "$remote_count" -eq "$cookie_count" ]; then
        log "Verification successful: $remote_count cookie file(s) on VPS"
    else
        warning "Cookie count mismatch: Local=$cookie_count, Remote=$remote_count"
    fi
    
    log "Cookie sync process completed!"
}

# Run main function
main "$@"