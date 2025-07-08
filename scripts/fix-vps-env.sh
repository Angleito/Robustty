#!/bin/bash
# Fix VPS environment variable loading issues

echo "=== VPS Environment Fix Script ==="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Creating .env from example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env from .env.example"
        echo "⚠️  Please edit .env and add your Discord token"
    else
        echo "❌ No .env.example found either!"
    fi
    exit 1
fi

# Check current token
echo "Checking current Discord token..."
CURRENT_TOKEN=$(grep "^DISCORD_TOKEN=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")

if [ -z "$CURRENT_TOKEN" ]; then
    echo "❌ No DISCORD_TOKEN found in .env"
elif [[ "$CURRENT_TOKEN" == *"your"* ]] || [[ "$CURRENT_TOKEN" == *"YOUR"* ]]; then
    echo "❌ Token is still a placeholder: $CURRENT_TOKEN"
    echo ""
    echo "Please edit .env and set your actual Discord token:"
    echo "  nano .env"
    echo ""
    echo "Format: DISCORD_TOKEN=MTEyMzQ1Njc4OTAxMjM0NTY3OA.GAbcde.1234567890abcdefghijklmnop"
    exit 1
else
    TOKEN_LENGTH=${#CURRENT_TOKEN}
    echo "✅ Token found (length: $TOKEN_LENGTH)"
fi

# Export for docker-compose
echo ""
echo "Exporting environment variables..."
export $(grep -v '^#' .env | xargs)

# Verify export
if [ -z "$DISCORD_TOKEN" ]; then
    echo "❌ Failed to export DISCORD_TOKEN"
    echo "Trying alternative method..."
    
    # Alternative: Create a temporary env file
    echo "Creating docker-compose override..."
    cat > docker-compose.override.yml << EOF
version: '3.8'
services:
  robustty:
    environment:
      - DISCORD_TOKEN=$CURRENT_TOKEN
EOF
    echo "✅ Created docker-compose.override.yml"
else
    echo "✅ DISCORD_TOKEN exported successfully"
fi

# Test token in container
echo ""
echo "Testing token in Docker container..."
docker-compose run --rm robustty python /app/scripts/debug-docker-env.py

echo ""
echo "=== Fix Summary ==="
echo "1. Token is loaded from .env file"
echo "2. Environment variables are exported"
echo "3. Docker should now receive the token"
echo ""
echo "To start the bot:"
echo "  docker-compose up -d"
echo ""
echo "To check logs:"
echo "  docker-compose logs -f robustty"