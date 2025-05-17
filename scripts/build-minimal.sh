#!/bin/bash
set -e

echo "Building Robustty with minimal requirements..."

# Copy minimal requirements to requirements.txt temporarily
cp requirements-minimal.txt requirements.txt

# Build with Docker
DOCKER_BUILDKIT=1 docker-compose build --no-cache bot

# Restore original requirements
git checkout requirements.txt

echo "Build complete! You can now run: docker-compose up -d"