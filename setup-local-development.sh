#!/bin/bash
# Setup script for local macOS development environment

echo "Setting up Robustty local development environment..."

# Check if Brave browser is installed
BRAVE_PATH="/Users/$(whoami)/Library/Application Support/BraveSoftware/Brave-Browser"
if [ ! -d "$BRAVE_PATH" ]; then
    echo "Warning: Brave browser not found at $BRAVE_PATH"
    echo "Cookie extraction will be disabled."
    BRAVE_PATH="./empty-cookies"
fi

# Export environment variable for Docker Compose
export BRAVE_BROWSER_PATH="$BRAVE_PATH"

echo "Brave browser path: $BRAVE_PATH"

# Update .env file
if [ -f ".env" ]; then
    # Update the BRAVE_BROWSER_PATH line in .env
    sed -i.bak "s|BRAVE_BROWSER_PATH=.*|BRAVE_BROWSER_PATH=$BRAVE_PATH|" .env
    echo "Updated .env file with correct Brave browser path"
else
    echo "Warning: .env file not found. Please create it from .env.example"
fi

# Start containers
echo "Starting Docker containers..."
docker-compose down
docker-compose up -d

echo "Setup complete!"
echo ""
echo "To verify cookie extraction is working:"
echo "  docker-compose logs robustty --tail=20"
echo ""
echo "To manually extract cookies:"
echo "  docker-compose exec robustty python3 scripts/extract-brave-cookies.py"
echo ""
echo "To check container status:"
echo "  docker-compose ps"