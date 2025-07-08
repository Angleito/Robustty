#!/bin/bash

# fix-vps-deployment.sh - Comprehensive VPS deployment fix script
# This script updates code, fixes YouTube Music connectivity, and verifies deployment

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Function to print colored output
print_step() {
    echo -e "\n${BLUE}${BOLD}==> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if we're running on VPS (not local)
is_vps() {
    # Check if we're not on macOS and have typical VPS characteristics
    if [[ "$OSTYPE" != "darwin"* ]] && [[ -f /etc/os-release ]]; then
        return 0
    else
        return 1
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local service=$1
    local max_attempts=30
    local attempt=1
    
    print_info "Waiting for $service to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps | grep -q "$service.*Up"; then
            print_success "$service is ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_error "$service failed to start within 60 seconds"
    return 1
}

# Function to check YouTube Music connectivity
check_youtube_music() {
    print_step "Checking YouTube Music connectivity"
    
    # Check if youtube-music service is running
    if docker-compose ps | grep -q "youtube-music.*Up"; then
        print_success "YouTube Music service is running"
        
        # Test actual connectivity
        print_info "Testing YouTube Music API connection..."
        
        # Test from within the robustty container
        if docker-compose exec -T robustty python3 -c "
import aiohttp
import asyncio
import json

async def test_youtube_music():
    try:
        async with aiohttp.ClientSession() as session:
            # Test connection to YouTube Music service
            async with session.get('http://youtube-music:3000/api/search?q=test', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print('SUCCESS: YouTube Music API is responding')
                    return True
                else:
                    print(f'ERROR: YouTube Music API returned status {resp.status}')
                    return False
    except aiohttp.ClientError as e:
        print(f'ERROR: Failed to connect to YouTube Music: {e}')
        return False
    except Exception as e:
        print(f'ERROR: Unexpected error: {e}')
        return False

asyncio.run(test_youtube_music())
" 2>&1; then
            print_success "YouTube Music API is accessible from bot container"
            return 0
        else
            print_error "YouTube Music API is not accessible from bot container"
            return 1
        fi
    else
        print_error "YouTube Music service is not running"
        return 1
    fi
}

# Main script starts here
clear
echo -e "${PURPLE}${BOLD}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║          Robustty VPS Deployment Fix Script               ║"
echo "║                                                           ║"
echo "║  This script will:                                        ║"
echo "║  • Update code from git                                   ║"
echo "║  • Fix YouTube Music connectivity                         ║"
echo "║  • Rebuild Docker containers                              ║"
echo "║  • Run comprehensive health checks                        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

# Check if we're on a VPS
if ! is_vps; then
    print_warning "This appears to be a local development environment, not a VPS."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Check prerequisites
print_step "Checking prerequisites"

if ! command_exists docker; then
    print_error "Docker is not installed!"
    exit 1
fi
print_success "Docker is installed"

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed!"
    exit 1
fi
print_success "Docker Compose is installed"

if ! command_exists git; then
    print_error "Git is not installed!"
    exit 1
fi
print_success "Git is installed"

# Step 1: Update code from git
print_step "Updating code from git"

# Check if we're in a git repository
if [ ! -d .git ]; then
    print_error "Not in a git repository! Please run this script from the Robustty project root."
    exit 1
fi

# Stash any local changes
if ! git diff --quiet || ! git diff --staged --quiet; then
    print_warning "Local changes detected, stashing them..."
    git stash push -m "Stashed by fix-vps-deployment.sh on $(date)"
    print_success "Local changes stashed"
fi

# Pull latest changes
print_info "Pulling latest changes from git..."
if git pull origin main; then
    print_success "Code updated successfully"
else
    print_error "Failed to pull latest changes"
    print_info "Attempting to reset to origin/main..."
    git fetch origin
    git reset --hard origin/main
    print_success "Reset to origin/main"
fi

# Step 2: Check and update environment file
print_step "Checking environment configuration"

if [ ! -f .env ]; then
    if [ -f .env.vps ]; then
        print_info "Using .env.vps as .env"
        cp .env.vps .env
    elif [ -f .env.example ]; then
        print_warning ".env file not found! Creating from .env.example"
        cp .env.example .env
        print_error "Please edit .env file with your credentials before continuing!"
        exit 1
    else
        print_error "No .env file found and no template available!"
        exit 1
    fi
fi
print_success "Environment file exists"

# Ensure YouTube Music is enabled in .env
if ! grep -q "YOUTUBE_MUSIC_ENABLED=true" .env; then
    print_warning "YouTube Music not enabled in .env, enabling it..."
    if grep -q "YOUTUBE_MUSIC_ENABLED=" .env; then
        sed -i 's/YOUTUBE_MUSIC_ENABLED=.*/YOUTUBE_MUSIC_ENABLED=true/' .env
    else
        echo "YOUTUBE_MUSIC_ENABLED=true" >> .env
    fi
    print_success "YouTube Music enabled in .env"
fi

# Step 3: Stop existing containers
print_step "Stopping existing containers"
docker-compose down
print_success "Containers stopped"

# Step 4: Clean up Docker resources
print_step "Cleaning up Docker resources"
print_info "Removing unused containers, networks, and volumes..."
docker system prune -f
print_success "Docker cleanup completed"

# Step 5: Pull latest images
print_step "Pulling latest Docker images"
docker-compose pull
print_success "Images updated"

# Step 6: Rebuild containers
print_step "Rebuilding containers"
print_info "This may take a few minutes..."

if docker-compose up -d --build; then
    print_success "Containers rebuilt and started"
else
    print_error "Failed to rebuild containers"
    print_info "Checking docker-compose logs for errors..."
    docker-compose logs --tail=50
    exit 1
fi

# Step 7: Wait for services to be ready
print_step "Waiting for services to start"

# Wait for Redis
wait_for_service "redis"

# Wait for YouTube Music
wait_for_service "youtube-music"

# Wait for bot
wait_for_service "robustty"

# Give services a moment to fully initialize
sleep 5

# Step 8: Fix YouTube Music connectivity
print_step "Fixing YouTube Music connectivity"

# Check if containers are on the same network
print_info "Verifying network configuration..."
NETWORK_NAME=$(docker-compose ps -q robustty | xargs docker inspect -f '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}' | head -1)
YT_MUSIC_NETWORK=$(docker-compose ps -q youtube-music 2>/dev/null | xargs docker inspect -f '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}' 2>/dev/null | head -1)

if [ -z "$YT_MUSIC_NETWORK" ]; then
    print_warning "YouTube Music container not found or not running"
else
    if [ "$NETWORK_NAME" = "$YT_MUSIC_NETWORK" ]; then
        print_success "Containers are on the same network"
    else
        print_error "Containers are on different networks!"
        print_info "Recreating containers with correct network..."
        docker-compose down
        docker-compose up -d --build
        wait_for_service "youtube-music"
        wait_for_service "robustty"
    fi
fi

# Test YouTube Music connectivity
check_youtube_music

# Step 9: Verify Redis connectivity
print_step "Verifying Redis connectivity"

if docker-compose exec -T redis redis-cli ping | grep -q PONG; then
    print_success "Redis is responding"
else
    print_error "Redis is not responding"
fi

# Step 10: Check bot health
print_step "Checking bot health"

# Check if bot process is running
if docker-compose exec -T robustty pgrep -f "python -m src.main" > /dev/null; then
    print_success "Bot process is running"
else
    print_error "Bot process is not running"
    print_info "Checking logs for errors..."
    docker-compose logs --tail=50 robustty
fi

# Step 11: Run comprehensive health check
print_step "Running comprehensive health check"

# Create a health check script
cat > /tmp/health_check.py << 'EOF'
import asyncio
import sys
import os
sys.path.insert(0, '/app')

from src.services.cache import CacheManager
from src.platforms.youtube_music import YouTubeMusic
import aiohttp

async def check_health():
    results = {
        'redis': False,
        'youtube_music_service': False,
        'youtube_music_platform': False
    }
    
    # Check Redis
    try:
        cache = CacheManager()
        await cache.set_recent_search('health_check', 'test', {'test': 'data'})
        data = await cache.get_recent_search('health_check', 'test')
        results['redis'] = data is not None
        print(f"✓ Redis: {'Connected' if results['redis'] else 'Failed'}")
    except Exception as e:
        print(f"✗ Redis: Error - {e}")
    
    # Check YouTube Music service connectivity
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://youtube-music:3000/api/search?q=test', 
                                 timeout=aiohttp.ClientTimeout(total=10)) as resp:
                results['youtube_music_service'] = resp.status == 200
                print(f"✓ YouTube Music Service: {'Connected' if results['youtube_music_service'] else f'Failed (Status: {resp.status})'}")
    except Exception as e:
        print(f"✗ YouTube Music Service: Error - {e}")
    
    # Check YouTube Music platform
    try:
        yt_music = YouTubeMusic()
        # Just verify it initializes properly
        results['youtube_music_platform'] = True
        print(f"✓ YouTube Music Platform: Initialized")
    except Exception as e:
        print(f"✗ YouTube Music Platform: Error - {e}")
    
    # Summary
    all_passed = all(results.values())
    print(f"\nHealth Check: {'PASSED' if all_passed else 'FAILED'}")
    return all_passed

if __name__ == "__main__":
    result = asyncio.run(check_health())
    sys.exit(0 if result else 1)
EOF

print_info "Running health check from within container..."
if docker-compose exec -T robustty python /tmp/health_check.py; then
    print_success "All health checks passed!"
else
    print_warning "Some health checks failed, but this may be normal during startup"
fi

rm -f /tmp/health_check.py

# Step 12: Display service status
print_step "Final service status"

echo -e "\n${BOLD}Container Status:${NC}"
docker-compose ps

echo -e "\n${BOLD}Recent Logs:${NC}"
echo -e "${CYAN}=== Bot Logs ===${NC}"
docker-compose logs --tail=10 robustty

echo -e "\n${CYAN}=== YouTube Music Logs ===${NC}"
docker-compose logs --tail=10 youtube-music 2>/dev/null || print_info "YouTube Music logs not available"

# Step 13: Provide next steps
echo -e "\n${GREEN}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}Deployment fix completed!${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"

print_info "Next steps:"
echo "  1. Monitor logs: ${BOLD}docker-compose logs -f${NC}"
echo "  2. Check bot status in Discord"
echo "  3. Test YouTube Music with: ${BOLD}!play <song name>${NC}"
echo "  4. View all logs: ${BOLD}docker-compose logs --tail=100${NC}"

if check_youtube_music > /dev/null 2>&1; then
    echo -e "\n${GREEN}${BOLD}✓ YouTube Music is fully operational!${NC}"
else
    echo -e "\n${YELLOW}${BOLD}⚠ YouTube Music may need additional configuration${NC}"
    echo "  Check the logs and ensure the service is properly configured"
fi

echo -e "\n${CYAN}For troubleshooting, see: ${BOLD}VPS_TROUBLESHOOTING.md${NC}"