#!/bin/bash

# Robustty Update Script

echo "=== Updating Robustty ==="

# Check if git repo
if [ ! -d .git ]; then
    echo "Error: Not a git repository"
    exit 1
fi

# Backup current configuration
echo "Backing up configuration..."
cp .env .env.backup
cp -r data data.backup

# Pull latest changes
echo "Pulling latest changes..."
git pull

# Rebuild containers
echo "Rebuilding containers..."
docker-compose build

# Restart services
echo "Restarting services..."
docker-compose down
docker-compose up -d

echo "Update complete!"
echo "Your configuration backup is in .env.backup and data.backup"