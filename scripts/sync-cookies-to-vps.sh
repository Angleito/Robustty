#!/bin/bash
# Cookie synchronization script for VPS deployment
# Usage: ./scripts/sync-cookies-to-vps.sh [VPS_IP]

set -e

VPS_IP=${1:-${VPS_IP}}
VPS_USER=${VPS_USER:-"root"}
SSH_KEY=${SSH_KEY}
SSH_PASSPHRASE=${SSH_PASSPHRASE}

# Check required environment variables
if [ -z "$VPS_IP" ]; then
    echo "❌ VPS_IP environment variable is required"
    exit 1
fi

if [ -z "$SSH_KEY" ]; then
    echo "❌ SSH_KEY environment variable is required"
    exit 1
fi

if [ -z "$SSH_PASSPHRASE" ]; then
    echo "❌ SSH_PASSPHRASE environment variable is required"
    exit 1
fi
CONTAINER_NAME="robustty-bot"
LOCAL_COOKIE_DIR="./cookies"
REMOTE_COOKIE_DIR="~/Robustty/cookies"

# Helper function to run SSH with passphrase
ssh_with_passphrase() {
    local ssh_command="$1"
    expect -c "
        spawn {*}[split {$ssh_command}]
        expect {
            \"Enter passphrase for key\" {
                send \"$SSH_PASSPHRASE\r\"
                exp_continue
            }
            \"assword:\" {
                send \"$SSH_PASSPHRASE\r\"
                exp_continue
            }
            eof
        }
    "
}

# Helper function to run SCP with passphrase
scp_with_passphrase() {
    local scp_command="$1"
    expect -c "
        spawn {*}[split {$scp_command}]
        expect {
            \"Enter passphrase for key\" {
                send \"$SSH_PASSPHRASE\r\"
                exp_continue
            }
            \"assword:\" {
                send \"$SSH_PASSPHRASE\r\"
                exp_continue
            }
            eof
        }
    "
}

echo "🍪 Starting cookie synchronization to VPS..."

# Check SSH key existence
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found: $SSH_KEY"
    echo "   Please set SSH_KEY environment variable or ensure key exists"
    exit 1
fi

# Test SSH connection
echo "🔑 Testing SSH connection..."
if ssh_with_passphrase "ssh -i $SSH_KEY -o ConnectTimeout=10 ${VPS_USER}@${VPS_IP} echo 'SSH test successful'" | grep -q "SSH test successful"; then
    echo "✅ SSH connection successful"
else
    echo "❌ SSH connection failed"
    exit 1
fi

# Step 1: Extract cookies locally
echo "📦 Extracting cookies locally..."
if [ -f "scripts/extract-brave-cookies.py" ]; then
    python3 scripts/extract-brave-cookies.py
    echo "✅ Local cookie extraction completed"
else
    echo "❌ Cookie extraction script not found"
    exit 1
fi

# Step 2: Check if cookies were created
if [ ! -d "$LOCAL_COOKIE_DIR" ] || [ -z "$(ls -A $LOCAL_COOKIE_DIR 2>/dev/null)" ]; then
    echo "❌ No cookies found in $LOCAL_COOKIE_DIR"
    echo "   Make sure you have logged into YouTube, Rumble, etc. in your browser"
    exit 1
fi

echo "📋 Found cookies for platforms:"
ls -la "$LOCAL_COOKIE_DIR"

# Step 3: Transfer cookies to VPS
echo "🚀 Transferring cookies to VPS ($VPS_IP)..."
scp_with_passphrase "scp -i $SSH_KEY -r $LOCAL_COOKIE_DIR ${VPS_USER}@${VPS_IP}:${REMOTE_COOKIE_DIR%/*}/"

# Step 4: Copy cookies into running container
echo "📥 Copying cookies into Docker container..."
ssh_with_passphrase "ssh -i $SSH_KEY ${VPS_USER}@${VPS_IP} 'cd ~/Robustty && docker cp ./cookies/. ${CONTAINER_NAME}:/app/cookies/ && docker exec ${CONTAINER_NAME} chown -R root:root /app/cookies && docker exec ${CONTAINER_NAME} chmod 644 /app/cookies/* && echo \"✅ Cookies copied to container\"'"

# Step 5: Restart container to pick up new cookies
echo "🔄 Restarting bot to load new cookies..."
ssh_with_passphrase "ssh -i $SSH_KEY ${VPS_USER}@${VPS_IP} 'cd ~/Robustty && docker-compose -f docker-compose.vps.yml restart robustty-bot && echo \"✅ Bot restarted\"'"

echo "🎉 Cookie synchronization completed!"
echo "🔍 Check bot logs: ssh -i ${SSH_KEY} ${VPS_USER}@${VPS_IP} 'cd ~/Robustty && docker logs -f robustty-bot'"