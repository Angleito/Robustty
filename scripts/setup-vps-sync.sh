#!/bin/bash
# VPS Cookie Sync Setup Script
# Run this on your Mac to configure cookie syncing to VPS

echo "🔧 Robustty VPS Cookie Sync Setup"
echo "================================="

# Get VPS configuration from user
read -p "Enter your VPS IP address: " vps_ip
read -p "Enter VPS username [root]: " vps_user
vps_user=${vps_user:-root}
read -p "Enter path to your SSH private key [~/.ssh/id_rsa]: " ssh_key
ssh_key=${ssh_key:-~/.ssh/id_rsa}

# Expand tilde if present
ssh_key="${ssh_key/#\~/$HOME}"

echo ""
echo "📝 Configuration:"
echo "  VPS IP: $vps_ip"
echo "  VPS User: $vps_user"  
echo "  SSH Key: $ssh_key"
echo ""

# Test SSH connection
echo "🔗 Testing SSH connection..."
if ssh -i "$ssh_key" -o ConnectTimeout=10 "$vps_user@$vps_ip" 'echo "Connection successful"'; then
    echo "✅ SSH connection works!"
else
    echo "❌ SSH connection failed. Please check:"
    echo "  - VPS IP address is correct"
    echo "  - SSH key path is correct"
    echo "  - SSH key is added to VPS authorized_keys"
    exit 1
fi

# Create/update .env file
echo ""
echo "📄 Updating .env configuration..."

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

# Update VPS configuration in .env
if grep -q "VPS_HOST=" .env; then
    sed -i.bak "s/VPS_HOST=.*/VPS_HOST=$vps_ip/" .env
else
    echo "VPS_HOST=$vps_ip" >> .env
fi

if grep -q "VPS_USER=" .env; then
    sed -i.bak "s/VPS_USER=.*/VPS_USER=$vps_user/" .env
else
    echo "VPS_USER=$vps_user" >> .env
fi

if grep -q "SSH_KEY=" .env; then
    sed -i.bak "s|SSH_KEY=.*|SSH_KEY=$ssh_key|" .env
else
    echo "SSH_KEY=$ssh_key" >> .env
fi

# Remove backup file if created
rm -f .env.bak

echo "✅ Updated .env with VPS configuration"

# Make sync script executable
chmod +x scripts/sync-cookies-to-vps.sh
echo "✅ Made sync script executable"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "🚀 To sync cookies to your VPS, run:"
echo "  ./scripts/sync-cookies-to-vps.sh"
echo ""
echo "🤖 To automate cookie syncing every 2 hours, add this to your crontab:"
echo "  0 */2 * * * cd $(pwd) && ./scripts/sync-cookies-to-vps.sh >> logs/cookie-sync.log 2>&1"
echo ""
echo "To add to crontab, run: crontab -e"