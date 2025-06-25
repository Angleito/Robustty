#!/bin/bash

# Configuration
VPS_HOST="your-vps-ip"
VPS_USER="your-username"
VPS_PATH="/home/your-username/robustty"
LOCAL_COOKIES="./cookies"

# Sync all cookie files
echo "Syncing cookies to VPS..."
rsync -avz --mkpath ${LOCAL_COOKIES}/*.json ${VPS_USER}@${VPS_HOST}:${VPS_PATH}/data/cookies/

echo "Cookie sync complete!"