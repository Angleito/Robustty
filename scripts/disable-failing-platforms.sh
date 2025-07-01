#!/bin/bash

echo "=== Managing Failing Platforms ==="
echo

# Function to update environment variable in .env file
update_env_var() {
    local var_name=$1
    local var_value=$2
    local env_file=".env"
    
    if grep -q "^${var_name}=" "$env_file" 2>/dev/null; then
        # Update existing variable
        sed -i.bak "s/^${var_name}=.*/${var_name}=${var_value}/" "$env_file"
        echo "Updated: ${var_name}=${var_value}"
    else
        # Add new variable
        echo "${var_name}=${var_value}" >> "$env_file"
        echo "Added: ${var_name}=${var_value}"
    fi
}

# Check command line argument
if [ "$1" == "disable-odysee" ]; then
    echo "Disabling Odysee platform due to API issues..."
    update_env_var "ODYSEE_ENABLED" "false"
    echo "✓ Odysee disabled"
    echo
elif [ "$1" == "enable-stability-mode" ]; then
    echo "Enabling VPS stability mode..."
    update_env_var "VPS_STABILITY_MODE" "true"
    update_env_var "AUTO_DISABLE_FAILING_PLATFORMS" "true"
    update_env_var "PLATFORM_FAILURE_THRESHOLD" "5"
    update_env_var "PLATFORM_RECOVERY_CHECK_INTERVAL" "300"
    echo "✓ Stability mode enabled"
    echo "This will automatically disable platforms that fail repeatedly"
    echo
elif [ "$1" == "status" ]; then
    echo "Current platform status:"
    echo "----------------------"
    grep -E "(ODYSEE_ENABLED|YOUTUBE_ENABLED|RUMBLE_ENABLED|PEERTUBE_ENABLED|VPS_STABILITY_MODE)" .env 2>/dev/null || echo "No platform settings found in .env"
    echo
else
    echo "Usage: $0 [disable-odysee|enable-stability-mode|status]"
    echo
    echo "Options:"
    echo "  disable-odysee      - Disable Odysee platform"
    echo "  enable-stability-mode - Enable automatic platform management"
    echo "  status             - Show current platform status"
    echo
    echo "Example:"
    echo "  $0 enable-stability-mode"
    exit 1
fi

# Only restart if we made changes
if [ "$1" != "status" ]; then
    echo "Restarting bot with new configuration..."
    docker-compose down
    docker-compose up -d
    echo
    echo "✓ Bot restarted with updated configuration"
    echo "Check logs with: docker-compose logs -f robustty"
fi