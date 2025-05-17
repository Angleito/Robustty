#!/bin/bash
set -e

# Find an available port
echo "Finding available port..."
AVAILABLE_PORT=$(./scripts/find-available-port.sh 5000)

if [ $? -ne 0 ]; then
    echo "Error: Could not find available port"
    exit 1
fi

echo "Using port $AVAILABLE_PORT for stream service"

# Set the port in environment
export STREAM_PORT=$AVAILABLE_PORT

# Add the port to .env if not already there
if ! grep -q "STREAM_PORT=" .env 2>/dev/null; then
    echo "STREAM_PORT=$AVAILABLE_PORT" >> .env
else
    # Update existing port
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/STREAM_PORT=.*/STREAM_PORT=$AVAILABLE_PORT/" .env
    else
        sed -i "s/STREAM_PORT=.*/STREAM_PORT=$AVAILABLE_PORT/" .env
    fi
fi

# Use the appropriate docker-compose file
if [ -f docker-compose.minimal.yml ]; then
    echo "Starting with minimal configuration..."
    docker-compose -f docker-compose.minimal.yml up -d
else
    echo "Starting with standard configuration..."
    docker-compose up -d
fi

echo ""
echo "Services started successfully!"
echo "Stream service is running on port: $AVAILABLE_PORT"
echo ""
echo "View logs with:"
echo "  docker logs -f robustty-bot"
echo ""
echo "Access stream service at:"
echo "  http://localhost:$AVAILABLE_PORT/health"