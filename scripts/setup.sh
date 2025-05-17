#!/bin/bash

# Robustty Setup Script

echo "=== Robustty Setup ==="

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create environment file
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env file with your configuration"
    exit 1
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p logs data/cookies data/cache

# Set permissions
chmod 755 scripts/*.sh

# Build Docker images
echo "Building Docker images..."
docker-compose build

echo "Setup complete! Run './scripts/deploy.sh' to start the bot."