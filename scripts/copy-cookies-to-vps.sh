#!/bin/bash

# Copy cookies from local machine to VPS
# Run this on your LOCAL machine (not on VPS)

set -e

echo "=== Cookie Transfer to VPS ==="
echo
echo "This script will copy cookies from your local machine to the VPS"
echo

# Configuration
VPS_IP="164.92.93.19"
VPS_USER="root"
SSH_KEY="$HOME/.ssh/yeet"
LOCAL_COOKIE_DIR="./cookies"
VPS_COOKIE_DIR="/root/Robustty/cookies"

# Check if cookies exist locally
if [ ! -d "$LOCAL_COOKIE_DIR" ]; then
    echo "ERROR: No local cookies directory found at $LOCAL_COOKIE_DIR"
    echo
    echo "To create cookies:"
    echo "  1. Run locally: python scripts/extract-brave-cookies.py"
    echo "  2. Or manually create: mkdir -p cookies"
    exit 1
fi

# Check for cookie files
echo "Found local cookies:"
ls -la "$LOCAL_COOKIE_DIR"/*.txt 2>/dev/null || echo "No .txt cookie files found"
ls -la "$LOCAL_COOKIE_DIR"/*.json 2>/dev/null || echo "No .json cookie files found"

# Create cookies directory on VPS
echo
echo "Creating cookies directory on VPS..."
ssh -i "$SSH_KEY" "$VPS_USER@$VPS_IP" "mkdir -p $VPS_COOKIE_DIR"

# Copy cookies to VPS
echo
echo "Copying cookies to VPS..."
if ls "$LOCAL_COOKIE_DIR"/*.txt >/dev/null 2>&1; then
    scp -i "$SSH_KEY" "$LOCAL_COOKIE_DIR"/*.txt "$VPS_USER@$VPS_IP:$VPS_COOKIE_DIR/"
    echo "✓ Copied .txt cookie files"
fi

if ls "$LOCAL_COOKIE_DIR"/*.json >/dev/null 2>&1; then
    scp -i "$SSH_KEY" "$LOCAL_COOKIE_DIR"/*.json "$VPS_USER@$VPS_IP:$VPS_COOKIE_DIR/"
    echo "✓ Copied .json cookie files"
fi

# Set permissions on VPS
echo
echo "Setting permissions on VPS..."
ssh -i "$SSH_KEY" "$VPS_USER@$VPS_IP" "chown -R 1000:1000 $VPS_COOKIE_DIR && chmod -R 644 $VPS_COOKIE_DIR/*"

# Verify cookies on VPS
echo
echo "Verifying cookies on VPS:"
ssh -i "$SSH_KEY" "$VPS_USER@$VPS_IP" "ls -la $VPS_COOKIE_DIR"

# Restart bot to use new cookies
echo
echo "Restarting bot on VPS..."
ssh -i "$SSH_KEY" "$VPS_USER@$VPS_IP" "cd /root/Robustty && docker-compose restart robustty"

echo
echo "=== Cookie Transfer Complete ==="
echo
echo "Cookies have been copied to the VPS!"
echo "The bot should now be able to play YouTube videos."
echo
echo "To check logs on VPS:"
echo "  ssh -i $SSH_KEY $VPS_USER@$VPS_IP 'cd /root/Robustty && docker-compose logs -f robustty'"