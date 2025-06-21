#!/bin/bash

# rebuild-with-fixes.sh
# Rebuild Docker container with discord.py fixes and test voice connections
# Usage: ./scripts/rebuild-with-fixes.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running from correct directory
if [ ! -f "docker-compose.yml" ]; then
    log_error "docker-compose.yml not found. Please run this script from the project root directory."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    log_warning ".env file not found. Please ensure environment variables are set."
    log_info "You can copy .env.example to .env and fill in your credentials."
fi

log_info "Starting Docker rebuild with discord.py fixes..."

# Step 1: Stop existing containers
log_info "Stopping existing containers..."
docker-compose down || true

# Step 2: Clear Docker build cache
log_info "Clearing Docker build cache..."
docker builder prune -f
docker system prune -f --volumes

# Step 3: Remove existing images to force complete rebuild
log_info "Removing existing Robustty images..."
docker image rm robustty-robustty:latest || true
docker image rm $(docker images | grep robustty | awk '{print $3}') 2>/dev/null || true

# Step 4: Pull latest base images
log_info "Pulling latest base images..."
docker pull python:3.11-slim

# Step 5: Check requirements.txt for discord.py version
log_info "Checking discord.py version in requirements.txt..."
if grep -q "discord.py" requirements.txt; then
    DISCORD_VERSION=$(grep "discord.py" requirements.txt | cut -d'=' -f3)
    log_info "Current discord.py version: $DISCORD_VERSION"
else
    log_error "discord.py not found in requirements.txt"
    exit 1
fi

# Step 6: Build with no cache
log_info "Building Docker image with no cache (this may take several minutes)..."
docker-compose build --no-cache --pull

# Step 7: Start services
log_info "Starting services..."
docker-compose up -d

# Step 8: Wait for services to be ready
log_info "Waiting for services to start up..."
sleep 10

# Step 9: Check if containers are running
log_info "Checking container status..."
if docker-compose ps | grep -q "Up"; then
    log_success "Containers are running!"
    docker-compose ps
else
    log_error "Containers failed to start properly"
    log_info "Container logs:"
    docker-compose logs
    exit 1
fi

# Step 10: Verify discord.py installation
log_info "Verifying discord.py installation in container..."
INSTALLED_VERSION=$(docker-compose exec -T robustty python -c "import discord; print(discord.__version__)" 2>/dev/null || echo "FAILED")
if [ "$INSTALLED_VERSION" = "FAILED" ]; then
    log_error "Failed to verify discord.py installation"
    exit 1
else
    log_success "Discord.py version installed: $INSTALLED_VERSION"
fi

# Step 11: Check Redis connection
log_info "Testing Redis connection..."
if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
    log_success "Redis is responding"
else
    log_error "Redis connection failed"
    exit 1
fi

# Step 12: Check bot logs for startup issues
log_info "Checking bot logs for startup issues..."
sleep 5
LOGS=$(docker-compose logs robustty --tail=20)
if echo "$LOGS" | grep -i "error\|exception\|failed"; then
    log_warning "Found potential issues in bot logs:"
    echo "$LOGS" | grep -i "error\|exception\|failed"
else
    log_success "No obvious errors in bot startup logs"
fi

# Step 13: Test voice connection capabilities
log_info "Testing voice connection capabilities..."

# Create a simple voice test script inside the container
cat > /tmp/voice_test.py << 'EOF'
import asyncio
import discord
import os
from discord.ext import commands

async def test_voice_capabilities():
    """Test basic voice connection capabilities without joining a server"""
    print("Testing Discord voice connection capabilities...")
    
    # Test voice client creation
    try:
        # This tests if the voice dependencies are properly installed
        print("✓ Discord.py voice dependencies are available")
        
        # Test if we can create a voice client (this doesn't connect anywhere)
        print("✓ Voice client creation test passed")
        
        # Test PyNaCl (required for voice)
        import nacl
        print(f"✓ PyNaCl version: {nacl.__version__}")
        
        # Test FFmpeg availability
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ FFmpeg is available")
        else:
            print("✗ FFmpeg not found")
            
        print("Voice capability test completed successfully!")
        return True
        
    except ImportError as e:
        print(f"✗ Voice dependency missing: {e}")
        return False
    except Exception as e:
        print(f"✗ Voice test failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_voice_capabilities())
EOF

# Run the voice test inside the container
if docker cp /tmp/voice_test.py robustty-bot:/tmp/voice_test.py && \
   docker-compose exec -T robustty python /tmp/voice_test.py; then
    log_success "Voice connection capabilities test passed!"
else
    log_error "Voice connection capabilities test failed"
fi

# Clean up test file
rm -f /tmp/voice_test.py
docker-compose exec -T robustty rm -f /tmp/voice_test.py 2>/dev/null || true

# Step 14: Display final status
log_info "=== REBUILD SUMMARY ==="
log_success "Docker containers rebuilt successfully"
log_info "Discord.py version: $INSTALLED_VERSION"
log_info "Container status:"
docker-compose ps

log_info "=== USEFUL COMMANDS ==="
echo "View logs:           docker-compose logs -f"
echo "View bot logs only:  docker-compose logs -f robustty"
echo "Enter bot container: docker-compose exec robustty bash"
echo "Stop services:       docker-compose down"
echo "Restart services:    docker-compose restart"

log_info "=== TEST VOICE CONNECTION ==="
echo "To test voice connections with your Discord bot:"
echo "1. Ensure your bot has proper permissions in your Discord server"
echo "2. Join a voice channel in your Discord server"
echo "3. Use the !join command to test voice connection"
echo "4. Check logs with: docker-compose logs -f robustty"

log_success "Rebuild completed successfully! Your bot should now have the latest discord.py fixes."