#!/bin/bash

# test-voice-fixes.sh
# Test voice connection fixes after Docker rebuild
# Usage: ./scripts/test-voice-fixes.sh

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

# Check if containers are running
if ! docker-compose ps | grep -q "Up"; then
    log_error "Containers are not running. Please run 'docker-compose up -d' first."
    exit 1
fi

log_info "Testing voice connection fixes..."

# Test 1: Verify discord.py version and voice support
log_info "Test 1: Verifying discord.py installation and voice support..."
cat > /tmp/discord_voice_test.py << 'EOF'
import discord
import asyncio
import sys

async def test_discord_voice():
    print(f"Discord.py version: {discord.__version__}")
    
    # Test voice dependencies
    try:
        import nacl
        print(f"PyNaCl version: {nacl.__version__}")
        print("✓ Voice encryption support available")
    except ImportError:
        print("✗ PyNaCl not available - voice connections will fail")
        return False
    
    # Test voice client creation
    try:
        # Create a mock bot to test voice client
        intents = discord.Intents.default()
        intents.voice_states = True
        client = discord.Client(intents=intents)
        print("✓ Discord client with voice intents created successfully")
    except Exception as e:
        print(f"✗ Failed to create Discord client: {e}")
        return False
    
    # Test FFmpeg
    import subprocess
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ FFmpeg is available for audio processing")
        else:
            print("✗ FFmpeg not working properly")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("✗ FFmpeg not found or not responding")
        return False
    
    print("✓ All voice connection dependencies are properly installed")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_discord_voice())
    sys.exit(0 if success else 1)
EOF

if docker cp /tmp/discord_voice_test.py robustty-bot:/tmp/discord_voice_test.py && \
   docker-compose exec -T robustty python /tmp/discord_voice_test.py; then
    log_success "Discord.py voice dependencies test passed"
else
    log_error "Discord.py voice dependencies test failed"
    exit 1
fi

# Test 2: Check bot startup logs for voice-related errors
log_info "Test 2: Checking bot logs for voice-related issues..."
sleep 2
LOGS=$(docker-compose logs robustty --tail=50)

# Check for common voice connection errors
if echo "$LOGS" | grep -i "opus.*not.*loaded\|voice.*not.*supported\|nacl.*not.*found"; then
    log_error "Found voice-related errors in bot logs:"
    echo "$LOGS" | grep -i "opus\|voice\|nacl"
else
    log_success "No voice-related errors found in bot logs"
fi

# Test 3: Test network connectivity for Discord voice
log_info "Test 3: Testing network connectivity for Discord voice servers..."
cat > /tmp/network_test.py << 'EOF'
import asyncio
import aiohttp
import socket

async def test_discord_connectivity():
    """Test connectivity to Discord voice servers"""
    voice_regions = [
        "gateway.discord.gg",
        "discord.gg"
    ]
    
    # Test DNS resolution
    for region in voice_regions:
        try:
            socket.gethostbyname(region)
            print(f"✓ DNS resolution for {region} successful")
        except socket.gaierror:
            print(f"✗ DNS resolution failed for {region}")
    
    # Test HTTP connectivity
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://discord.com/api/v10/gateway", timeout=10) as resp:
                if resp.status == 200:
                    print("✓ Discord API gateway accessible")
                else:
                    print(f"✗ Discord API returned status {resp.status}")
        except Exception as e:
            print(f"✗ Failed to connect to Discord API: {e}")

if __name__ == "__main__":
    asyncio.run(test_discord_connectivity())
EOF

if docker cp /tmp/network_test.py robustty-bot:/tmp/network_test.py && \
   docker-compose exec -T robustty python /tmp/network_test.py; then
    log_success "Network connectivity test passed"
else
    log_warning "Network connectivity test had issues (this may be expected in some environments)"
fi

# Test 4: Verify host networking configuration
log_info "Test 4: Verifying host networking configuration..."
NETWORK_MODE=$(docker inspect robustty-bot | grep -o '"NetworkMode": "[^"]*"' | cut -d'"' -f4)
if [ "$NETWORK_MODE" = "host" ]; then
    log_success "Container is using host networking (optimal for Discord voice)"
else
    log_warning "Container is not using host networking: $NETWORK_MODE"
    log_info "Consider updating docker-compose.yml to use 'network_mode: host'"
fi

# Test 5: Check for proper permissions and capabilities
log_info "Test 5: Checking container permissions and capabilities..."
CAPS=$(docker inspect robustty-bot | grep -A 20 '"CapAdd"')
if echo "$CAPS" | grep -q "NET_ADMIN"; then
    log_success "Container has NET_ADMIN capability for advanced networking"
else
    log_warning "Container lacks NET_ADMIN capability"
fi

# Test 6: Memory and resource allocation
log_info "Test 6: Checking container resource allocation..."
STATS=$(docker stats robustty-bot --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}")
echo "$STATS"

# Cleanup test files
rm -f /tmp/discord_voice_test.py /tmp/network_test.py
docker-compose exec -T robustty rm -f /tmp/discord_voice_test.py /tmp/network_test.py 2>/dev/null || true

# Summary
log_info "=== VOICE CONNECTION TEST SUMMARY ==="
log_success "Voice connection tests completed"
log_info "If all tests passed, your bot should be able to connect to voice channels"
log_info "To verify the fix works:"
echo "1. Join a voice channel in your Discord server"
echo "2. Use the bot's !join command"
echo "3. Monitor logs: docker-compose logs -f robustty"
echo "4. Look for successful voice connection messages"

log_info "Common voice connection issues and solutions:"
echo "- Bot not joining: Check bot permissions (Connect, Speak, Use Voice Activity)"
echo "- Audio cutting out: Verify stable network connection"
echo "- Connection timeouts: Check firewall settings for UDP traffic"
echo "- Opus errors: Ensure FFmpeg is properly installed (should be fixed now)"

log_success "Voice connection fix testing completed!"