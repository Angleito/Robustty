#!/bin/bash

# Robustty Backup Script

echo "=== Backing up Robustty ==="

# Create backup directory
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup configuration
echo "Backing up configuration..."
cp .env "$BACKUP_DIR/"
cp -r config "$BACKUP_DIR/"

# Backup data
echo "Backing up data..."
cp -r data "$BACKUP_DIR/"

# Backup logs (optional)
if [ -d logs ]; then
    echo "Backing up logs..."
    cp -r logs "$BACKUP_DIR/"
fi

# Create archive
echo "Creating archive..."
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo "Backup complete: $BACKUP_DIR.tar.gz"