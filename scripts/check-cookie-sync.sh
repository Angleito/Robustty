#!/bin/bash

# Cookie Sync Monitoring Script for VPS
# Checks if cookie files are fresh and sends alerts if they're stale
# This script should be run on the Ubuntu VPS

# Configuration
COOKIE_DIR="${COOKIE_DIR:-/opt/robustty/cookies}"
MAX_AGE_MINUTES="${MAX_AGE_MINUTES:-150}"  # 2.5 hours
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"  # Optional Discord webhook for alerts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to send Discord alert
send_discord_alert() {
    local message=$1
    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        curl -H "Content-Type: application/json" \
             -X POST \
             -d "{\"content\": \"🚨 **Cookie Sync Alert**\n$message\"}" \
             "$DISCORD_WEBHOOK_URL" 2>/dev/null
    fi
}

# Function to check file age in minutes
get_file_age_minutes() {
    local file=$1
    local current_time=$(date +%s)
    local file_time=$(stat -c %Y "$file" 2>/dev/null || echo 0)
    echo $(( (current_time - file_time) / 60 ))
}

# Main monitoring function
main() {
    local stale_files=()
    local missing_platforms=()
    local all_good=true
    
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} Checking cookie freshness..."
    
    # Check if cookie directory exists
    if [ ! -d "$COOKIE_DIR" ]; then
        echo -e "${RED}ERROR:${NC} Cookie directory does not exist: $COOKIE_DIR"
        send_discord_alert "Cookie directory missing: $COOKIE_DIR"
        exit 1
    fi
    
    # Expected cookie files
    expected_files=("youtube_cookies.json" "rumble_cookies.json" "odysee_cookies.json" "peertube_cookies.json")
    
    # Check each expected cookie file
    for expected_file in "${expected_files[@]}"; do
        file_path="$COOKIE_DIR/$expected_file"
        
        if [ ! -f "$file_path" ]; then
            echo -e "${YELLOW}WARNING:${NC} Missing cookie file: $expected_file"
            missing_platforms+=("$expected_file")
            all_good=false
            continue
        fi
        
        # Check file age
        age_minutes=$(get_file_age_minutes "$file_path")
        
        if [ "$age_minutes" -gt "$MAX_AGE_MINUTES" ]; then
            echo -e "${RED}STALE:${NC} $expected_file is $age_minutes minutes old (threshold: $MAX_AGE_MINUTES)"
            stale_files+=("$expected_file (${age_minutes}m old)")
            all_good=false
        else
            echo -e "${GREEN}OK:${NC} $expected_file is $age_minutes minutes old"
        fi
    done
    
    # Check for any .json files in the directory
    json_count=$(find "$COOKIE_DIR" -name "*.json" -type f | wc -l)
    echo -e "\nTotal cookie files found: $json_count"
    
    # Prepare alert message if needed
    if [ ${#stale_files[@]} -gt 0 ] || [ ${#missing_platforms[@]} -gt 0 ]; then
        alert_message="Cookie sync issues detected!\n"
        
        if [ ${#stale_files[@]} -gt 0 ]; then
            alert_message+="\n**Stale files:**\n"
            for file in "${stale_files[@]}"; do
                alert_message+="• $file\n"
            done
        fi
        
        if [ ${#missing_platforms[@]} -gt 0 ]; then
            alert_message+="\n**Missing files:**\n"
            for file in "${missing_platforms[@]}"; do
                alert_message+="• $file\n"
            done
        fi
        
        alert_message+="\nLast sync may have failed. Check the sync script on macOS."
        
        echo -e "\n${RED}ALERT:${NC} Issues detected with cookie sync"
        send_discord_alert "$alert_message"
        
        exit 1
    else
        echo -e "\n${GREEN}SUCCESS:${NC} All cookie files are fresh and present"
    fi
    
    # Additional health checks
    echo -e "\n${GREEN}Additional Checks:${NC}"
    
    # Check if bot container is running
    if docker ps --format '{{.Names}}' | grep -q "robustty-bot"; then
        echo -e "${GREEN}✓${NC} Bot container is running"
    else
        echo -e "${RED}✗${NC} Bot container is not running"
        send_discord_alert "Bot container is not running!"
    fi
    
    # Check Redis connectivity
    if docker exec robustty-redis redis-cli ping &>/dev/null; then
        echo -e "${GREEN}✓${NC} Redis is responsive"
    else
        echo -e "${YELLOW}⚠${NC} Redis is not responsive"
    fi
    
    # Show disk usage
    cookie_size=$(du -sh "$COOKIE_DIR" 2>/dev/null | cut -f1)
    echo -e "\nCookie directory size: $cookie_size"
    
    exit 0
}

# Run main function
main "$@"