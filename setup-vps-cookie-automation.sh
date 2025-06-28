#!/bin/bash
# Setup VPS Cookie Automation on macOS Host
# This script sets up automatic cookie extraction and syncing to VPS

set -e

echo "=== Robustty VPS Cookie Automation Setup ==="
echo

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "ERROR: This script is designed for macOS only"
    exit 1
fi

# Get VPS details
read -p "Enter your VPS IP address or hostname: " VPS_HOST
read -p "Enter your VPS username (default: ubuntu): " VPS_USER
VPS_USER=${VPS_USER:-ubuntu}
read -p "Enter path to Robustty on VPS (default: ~/robustty-bot): " VPS_PATH
VPS_PATH=${VPS_PATH:-~/robustty-bot}

# Test SSH connection
echo
echo "Testing SSH connection to VPS..."
if ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" "echo 'SSH connection successful'" 2>/dev/null; then
    echo "✓ SSH connection successful"
else
    echo "✗ Failed to connect to VPS. Please ensure:"
    echo "  1. SSH key is set up (~/.ssh/id_rsa)"
    echo "  2. VPS is accessible"
    echo "  3. Username is correct"
    exit 1
fi

# Create environment file for cron
ENV_FILE="$HOME/.robustty-vps-sync.env"
cat > "$ENV_FILE" << EOF
# Robustty VPS Cookie Sync Configuration
export VPS_HOST="$VPS_HOST"
export VPS_USER="$VPS_USER"
export VPS_PATH="$VPS_PATH"
EOF
chmod 600 "$ENV_FILE"
echo "✓ Created environment configuration at $ENV_FILE"

# Get project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create wrapper script for cron
WRAPPER_SCRIPT="$HOME/robustty-cookie-sync-wrapper.sh"
cat > "$WRAPPER_SCRIPT" << EOF
#!/bin/bash
# Wrapper script for Robustty cookie sync cron job

# Load environment
source $ENV_FILE

# Run the sync script
$PROJECT_DIR/scripts/vps-cookie-sync-cron.sh
EOF
chmod +x "$WRAPPER_SCRIPT"
echo "✓ Created wrapper script at $WRAPPER_SCRIPT"

# Setup cron job
echo
echo "Setting up cron job for automatic cookie sync..."
echo "Choose sync frequency:"
echo "1) Every 6 hours (recommended for VPS)"
echo "2) Every 12 hours"
echo "3) Every 24 hours"
echo "4) Custom"
read -p "Enter choice (1-4): " FREQ_CHOICE

case $FREQ_CHOICE in
    1) CRON_SCHEDULE="0 */6 * * *" ;;
    2) CRON_SCHEDULE="0 */12 * * *" ;;
    3) CRON_SCHEDULE="0 0 * * *" ;;
    4) 
        echo "Enter custom cron schedule (e.g., '0 */4 * * *' for every 4 hours):"
        read CRON_SCHEDULE
        ;;
    *) CRON_SCHEDULE="0 */6 * * *" ;;
esac

# Add to crontab
CRON_CMD="$CRON_SCHEDULE $WRAPPER_SCRIPT"
(crontab -l 2>/dev/null | grep -v "robustty-cookie-sync-wrapper.sh"; echo "$CRON_CMD") | crontab -

echo "✓ Added cron job: $CRON_CMD"

# Run initial sync
echo
echo "Running initial cookie extraction and sync..."
cd "$PROJECT_DIR"

# Extract cookies
python3 scripts/extract-brave-cookies.py

# Initialize missing cookies for optional platforms
python3 scripts/init-missing-cookies.py

# Run sync
if bash scripts/vps-cookie-sync-cron.sh; then
    echo "✓ Initial sync completed successfully"
else
    echo "✗ Initial sync failed - check logs at ~/robustty-cookie-sync.log"
fi

echo
echo "=== Setup Complete ==="
echo
echo "Cookie automation is now configured with the following settings:"
echo "- VPS Host: $VPS_HOST"
echo "- VPS User: $VPS_USER"
echo "- VPS Path: $VPS_PATH"
echo "- Sync Schedule: $CRON_SCHEDULE"
echo
echo "Logs will be written to: ~/robustty-cookie-sync.log"
echo
echo "To check the status:"
echo "  crontab -l | grep robustty"
echo "  tail -f ~/robustty-cookie-sync.log"
echo
echo "To manually sync cookies:"
echo "  $WRAPPER_SCRIPT"