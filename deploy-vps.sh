#!/bin/bash

# VPS Deployment Script for Robustty Discord Bot
# This script sets up the bot on a VPS to use cookies from a remote machine

set -e

VPS_HOST="${1:-your-vps-ip}"
VPS_USER="${2:-ubuntu}"

echo "🚀 Deploying Robustty Discord Bot to VPS: $VPS_USER@$VPS_HOST"

# Create deployment directory on VPS
echo "📁 Creating deployment directory..."
ssh $VPS_USER@$VPS_HOST "mkdir -p ~/robustty-bot"

# Copy necessary files to VPS
echo "📤 Copying project files..."
rsync -av --exclude='venv' --exclude='__pycache__' --exclude='.git' --exclude='logs' \
    --exclude='data' --exclude='cookies' \
    ./ $VPS_USER@$VPS_HOST:~/robustty-bot/

# Copy VPS-specific docker-compose
echo "📋 Setting up VPS configuration..."
scp docker-compose.vps.yml $VPS_USER@$VPS_HOST:~/robustty-bot/docker-compose.yml

# Copy environment file
if [ -f .env ]; then
    scp .env $VPS_USER@$VPS_HOST:~/robustty-bot/
else
    echo "⚠️  No .env file found. You'll need to create one on the VPS."
fi

# Create necessary directories on VPS
ssh $VPS_USER@$VPS_HOST "cd ~/robustty-bot && mkdir -p logs data cookies"

# Install Docker if not present
echo "🐳 Checking Docker installation..."
ssh $VPS_USER@$VPS_HOST "
    if ! command -v docker &> /dev/null; then
        echo 'Installing Docker...'
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker \$USER
        echo 'Docker installed. You may need to log out and back in.'
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo 'Installing Docker Compose...'
        sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi
"

# Set up cookie sync (choose one method below)
cat << 'EOF'

🍪 COOKIE SYNC SETUP REQUIRED:

Choose one of these methods to sync cookies from your local machine to the VPS:

1. SCP/Rsync (Manual sync):
   rsync -av ./cookies/ $VPS_USER@$VPS_HOST:~/robustty-bot/cookies/

2. GitHub Actions (Automated):
   - Use the provided GitHub Actions workflow
   - Set repository secrets for VPS access

3. Network File System:
   - Mount a shared NFS/SSHFS between machines
   - Point both cookie directories to the same location

4. Cloud Storage:
   - Use AWS S3, Google Cloud Storage, or similar
   - Sync cookies via cloud bucket

EOF

echo "✅ VPS deployment prepared!"
echo "📝 Next steps:"
echo "1. Set up cookie synchronization (see options above)"
echo "2. Configure .env file on VPS: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && nano .env'"
echo "3. Start the bot: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && docker-compose up -d'"
echo "4. Monitor logs: ssh $VPS_USER@$VPS_HOST 'cd ~/robustty-bot && docker-compose logs -f'"