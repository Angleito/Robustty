#!/bin/bash

echo "Starting Robustty Cookie Extraction Service..."
echo "Cookie refresh interval: ${COOKIE_REFRESH_INTERVAL:-7200} seconds"

# Start cron daemon
service cron start

# Run initial cookie extraction
echo "Running initial cookie extraction..."
cd /app && python3 scripts/extract-brave-cookies.py

# Keep container running and monitor cron log
echo "Cookie service started. Monitoring extraction logs..."
tail -f /var/log/cron.log