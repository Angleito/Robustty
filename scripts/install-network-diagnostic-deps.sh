#!/bin/bash
"""
Install dependencies for network diagnostic script.
This script installs the Python packages needed for comprehensive network testing.
"""

echo "Installing network diagnostic dependencies..."

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✓ Virtual environment detected: $VIRTUAL_ENV"
else
    echo "⚠️  No virtual environment detected - installing system-wide"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Install required packages
echo "Installing Python packages..."
pip install aiohttp dnspython redis

# Check installation
echo ""
echo "Verifying installation..."
python3 -c "
import sys
try:
    import aiohttp
    print('✓ aiohttp installed')
except ImportError:
    print('✗ aiohttp not available')
    sys.exit(1)

try:
    import dns.asyncresolver
    print('✓ dnspython installed')
except ImportError:
    print('✗ dnspython not available')
    sys.exit(1)

try:
    import redis
    print('✓ redis installed')
except ImportError:
    print('✗ redis not available')
    sys.exit(1)

print('\\n✓ All dependencies installed successfully!')
"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Installation complete!"
    echo "You can now run: python3 scripts/network-diagnostic.py"
else
    echo ""
    echo "✗ Installation failed. Please check the errors above."
    exit 1
fi