#!/bin/bash

# update-discord-and-rebuild.sh
# Update discord.py to latest version and rebuild with fixes
# Usage: ./scripts/update-discord-and-rebuild.sh [--discord-version VERSION]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Parse command line arguments
DISCORD_VERSION=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --discord-version)
            DISCORD_VERSION="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Usage: $0 [--discord-version VERSION]"
            exit 1
            ;;
    esac
done

# Check if running from correct directory
if [ ! -f "requirements.txt" ]; then
    log_error "requirements.txt not found. Please run this script from the project root directory."
    exit 1
fi

log_info "Updating discord.py and rebuilding with voice connection fixes..."

# Step 1: Create backup of current requirements.txt
log_info "Creating backup of current requirements.txt..."
cp requirements.txt requirements.txt.backup
log_success "Backup created: requirements.txt.backup"

# Step 2: Update discord.py version
if [ -n "$DISCORD_VERSION" ]; then
    log_info "Updating discord.py to version $DISCORD_VERSION..."
    sed -i.tmp "s/discord\.py==.*/discord.py==$DISCORD_VERSION/" requirements.txt
    rm requirements.txt.tmp 2>/dev/null || true
else
    log_info "Checking for latest discord.py version..."
    # Try to get the latest version from PyPI (fallback to current if this fails)
    LATEST_VERSION=$(curl -s https://pypi.org/pypi/discord.py/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])" 2>/dev/null || echo "")
    
    if [ -n "$LATEST_VERSION" ]; then
        CURRENT_VERSION=$(grep "discord.py==" requirements.txt | cut -d'=' -f3)
        log_info "Current version: $CURRENT_VERSION"
        log_info "Latest version: $LATEST_VERSION"
        
        if [ "$CURRENT_VERSION" != "$LATEST_VERSION" ]; then
            log_info "Updating discord.py to latest version: $LATEST_VERSION"
            sed -i.tmp "s/discord\.py==.*/discord.py==$LATEST_VERSION/" requirements.txt
            rm requirements.txt.tmp 2>/dev/null || true
        else
            log_info "Already using latest version"
        fi
    else
        log_warning "Could not check for latest version, keeping current version"
    fi
fi

# Step 3: Ensure compatible PyNaCl version for voice
log_info "Ensuring compatible PyNaCl version for voice support..."
if grep -q "PyNaCl==" requirements.txt; then
    # Update to a known good version
    sed -i.tmp "s/PyNaCl==.*/PyNaCl==1.5.0/" requirements.txt
    rm requirements.txt.tmp 2>/dev/null || true
else
    log_warning "PyNaCl not found in requirements.txt"
fi

# Step 4: Update yt-dlp to latest version for better stream support
log_info "Updating yt-dlp to latest version..."
LATEST_YTDLP=$(curl -s https://pypi.org/pypi/yt-dlp/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])" 2>/dev/null || echo "2025.4.30")
if [ -n "$LATEST_YTDLP" ]; then
    sed -i.tmp "s/yt-dlp==.*/yt-dlp==$LATEST_YTDLP/" requirements.txt
    rm requirements.txt.tmp 2>/dev/null || true
    log_info "Updated yt-dlp to: $LATEST_YTDLP"
fi

# Step 5: Show what changed
log_info "Requirements changes:"
if [ -f "requirements.txt.backup" ]; then
    diff requirements.txt.backup requirements.txt || true
fi

# Step 6: Run the rebuild script
log_info "Running rebuild with fixes..."
if [ -f "scripts/rebuild-with-fixes.sh" ]; then
    ./scripts/rebuild-with-fixes.sh
else
    log_error "rebuild-with-fixes.sh not found"
    exit 1
fi

# Step 7: Run voice connection tests
log_info "Running voice connection tests..."
if [ -f "scripts/test-voice-fixes.sh" ]; then
    ./scripts/test-voice-fixes.sh
else
    log_warning "test-voice-fixes.sh not found, skipping voice tests"
fi

# Step 8: Final verification
log_info "Final verification of updates..."
NEW_DISCORD_VERSION=$(docker-compose exec -T robustty python -c "import discord; print(discord.__version__)" 2>/dev/null || echo "UNKNOWN")
NEW_NACL_VERSION=$(docker-compose exec -T robustty python -c "import nacl; print(nacl.__version__)" 2>/dev/null || echo "UNKNOWN")

log_success "=== UPDATE SUMMARY ==="
echo "Discord.py version: $NEW_DISCORD_VERSION"
echo "PyNaCl version: $NEW_NACL_VERSION"
echo "Backup saved as: requirements.txt.backup"

log_info "=== TESTING RECOMMENDATIONS ==="
echo "1. Test voice connection: Join a voice channel and use !join command"
echo "2. Test audio playback: Use !play command with a song"
echo "3. Monitor logs: docker-compose logs -f robustty"
echo "4. Check for any connection errors or audio issues"

log_info "=== ROLLBACK INSTRUCTIONS ==="
echo "If issues arise, you can rollback:"
echo "1. cp requirements.txt.backup requirements.txt"
echo "2. ./scripts/rebuild-with-fixes.sh"

log_success "Discord.py update and rebuild completed successfully!"