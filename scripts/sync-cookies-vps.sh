#!/bin/bash

# Cookie Sync Script - Local to VPS
# Run this script to sync cookies from local machine to VPS

# Source the SSH retry wrapper for network resilience
SSH_RETRY_SCRIPT="$(dirname "$0")/ssh-retry-wrapper.sh"
if [[ -f "$SSH_RETRY_SCRIPT" ]]; then
    source "$SSH_RETRY_SCRIPT"
    echo "✅ SSH retry wrapper loaded for network resilience"
else
    echo "⚠️  SSH retry wrapper not found - using standard commands"
    # Fallback functions if retry wrapper is not available
    ssh_retry() { ssh "$@"; }
    scp_retry() { scp "$@"; }
fi

VPS_HOST="${1:-your-vps-ip}"
VPS_USER="${2:-ubuntu}"
SYNC_INTERVAL="${3:-3600}"  # 1 hour default

if [ "$1" == "--help" ] || [ -z "$VPS_HOST" ]; then
    echo "Usage: $0 <vps-ip> [vps-user] [sync-interval-seconds]"
    echo ""
    echo "Examples:"
    echo "  $0 192.168.1.100                    # Sync once to VPS"
    echo "  $0 192.168.1.100 ubuntu 1800        # Sync every 30 minutes"
    echo "  $0 192.168.1.100 root 3600          # Sync every hour as root"
    echo ""
    echo "This script syncs cookies from the local Docker volume to your VPS"
    exit 1
fi

echo "🍪 Cookie Sync: Local Machine → VPS ($VPS_USER@$VPS_HOST)"

# Function to sync cookies
sync_cookies() {
    echo "⏰ $(date): Starting cookie sync..."
    
    # Get cookies from local Docker volume
    docker-compose -f docker-compose.cookies.yml exec -T cookie-extractor tar -czf /tmp/cookies.tar.gz -C /app cookies/
    docker-compose -f docker-compose.cookies.yml exec -T cookie-extractor cat /tmp/cookies.tar.gz > /tmp/local-cookies.tar.gz
    
    if [ $? -eq 0 ]; then
        # Upload to VPS with retry
        scp_retry /tmp/local-cookies.tar.gz $VPS_USER@$VPS_HOST:~/robustty-cookies.tar.gz
        
        # Extract on VPS with retry
        ssh_retry $VPS_USER@$VPS_HOST "
            cd ~/robustty-bot
            tar -xzf ~/robustty-cookies.tar.gz
            rm ~/robustty-cookies.tar.gz
            echo 'Cookies synced: \$(ls -la cookies/)'
        "
        
        # Cleanup
        rm -f /tmp/local-cookies.tar.gz
        
        echo "✅ Cookie sync completed successfully"
    else
        echo "❌ Failed to extract cookies from local container"
        return 1
    fi
}

# Sync once
sync_cookies

# If interval specified, run continuously
if [ "$SYNC_INTERVAL" != "0" ] && [ "$SYNC_INTERVAL" -gt 0 ]; then
    echo "🔄 Starting continuous sync every $SYNC_INTERVAL seconds"
    echo "Press Ctrl+C to stop"
    
    while true; do
        sleep $SYNC_INTERVAL
        sync_cookies
    done
else
    echo "✅ One-time sync completed"
fi