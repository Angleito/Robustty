#!/bin/bash

# Robustty Deployment Script

echo "=== Deploying Robustty ==="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Run setup.sh first."
    exit 1
fi

# Pull latest changes (if in git repo)
if [ -d .git ]; then
    echo "Pulling latest changes..."
    git pull
fi

# Stop existing containers
echo "Stopping existing containers..."
docker-compose down

# Build and start containers
echo "Starting services..."
docker-compose up -d --build

# Show logs
echo "Showing logs (press Ctrl+C to exit)..."
docker-compose logs -f