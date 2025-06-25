#!/bin/bash

echo "Starting Robustty Cookie Extraction Service..."
echo "Cookie refresh interval: ${COOKIE_REFRESH_INTERVAL:-7200} seconds"

# Setup SSH configuration if VPS sync is enabled
if [ "$AUTO_SYNC_VPS" = "true" ]; then
    echo "Setting up SSH configuration for VPS sync..."
    /app/scripts/setup-ssh-config.sh
    echo "VPS sync enabled to $VPS_USER@$VPS_HOST"
fi

# Start cron daemon
service cron start

# Ensure all cookie files exist
echo "Ensuring all platform cookie files exist..."
cd /app && python3 scripts/ensure-cookie-files.py

# Run initial cookie extraction
echo "Running initial cookie extraction..."
cd /app && python3 scripts/extract-brave-cookies.py

# Keep container running and monitor cron log
echo "Cookie service started. Monitoring extraction logs..."
tail -f /var/log/cron.log