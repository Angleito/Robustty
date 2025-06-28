#!/bin/bash
# VPS Cookie Sync Automation Script
# This script should be run as a cron job on the macOS host to keep VPS cookies fresh
# Example cron entry (every 6 hours): 0 */6 * * * /path/to/vps-cookie-sync-cron.sh

set -e

# Configuration - set these in your environment or modify here
VPS_HOST="${VPS_HOST}"
VPS_USER="${VPS_USER:-ubuntu}"
VPS_PATH="${VPS_PATH:-~/robustty-bot}"
LOG_FILE="${HOME}/robustty-cookie-sync.log"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if VPS_HOST is set
if [ -z "$VPS_HOST" ]; then
    log "ERROR: VPS_HOST environment variable not set"
    exit 1
fi

log "Starting VPS cookie sync process"

# Change to project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_DIR"

# Extract fresh cookies from Brave browser
log "Extracting fresh cookies from Brave browser..."
if python3 scripts/extract-brave-cookies.py >> "$LOG_FILE" 2>&1; then
    log "Cookie extraction successful"
else
    log "WARNING: Cookie extraction failed, proceeding with existing cookies"
fi

# Check if cookies exist
if [ ! -d "cookies" ] || [ -z "$(ls -A cookies/*.json 2>/dev/null)" ]; then
    log "ERROR: No cookie files found to sync"
    exit 1
fi

# Count cookies
COOKIE_COUNT=$(ls -1 cookies/*.json 2>/dev/null | wc -l)
log "Found $COOKIE_COUNT cookie files to sync"

# Sync cookies to VPS
log "Syncing cookies to $VPS_USER@$VPS_HOST:$VPS_PATH/cookies/"

# Use rsync with SSH for efficient sync
if rsync -avz --delete \
    -e "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30" \
    cookies/ \
    "$VPS_USER@$VPS_HOST:$VPS_PATH/cookies/" >> "$LOG_FILE" 2>&1; then
    
    log "Cookie sync completed successfully"
    
    # Verify sync and restart bot on VPS
    log "Verifying sync and restarting bot on VPS..."
    
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30 \
        "$VPS_USER@$VPS_HOST" \
        "cd $VPS_PATH && docker-compose restart robustty" >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "Bot restarted successfully on VPS"
    else
        log "WARNING: Failed to restart bot on VPS"
    fi
    
    # Log cookie ages for monitoring
    for cookie_file in cookies/*.json; do
        if [ -f "$cookie_file" ]; then
            platform=$(basename "$cookie_file" | sed 's/_cookies.json//')
            age_hours=$(( ($(date +%s) - $(stat -f %m "$cookie_file")) / 3600 ))
            log "Cookie age: $platform = $age_hours hours"
        fi
    done
    
else
    log "ERROR: Cookie sync failed"
    exit 1
fi

log "VPS cookie sync process completed"
echo "" >> "$LOG_FILE"  # Add blank line for readability