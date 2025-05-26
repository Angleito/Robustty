#!/bin/bash

# Discord Voice Diagnostics Test Runner
# This script helps run comprehensive voice connection tests

echo "🎵 Discord Voice Connection Diagnostics"
echo "========================================"

# Check if .env file exists
if [ -f .env ]; then
    echo "📁 Loading environment from .env file..."
    export $(cat .env | xargs)
else
    echo "⚠️  No .env file found. Please create one or set environment variables manually."
fi

# Check required environment variables
if [ -z "$DISCORD_TOKEN" ]; then
    echo "❌ DISCORD_TOKEN not set!"
    echo "Please set your Discord bot token:"
    echo "export DISCORD_TOKEN='your-bot-token-here'"
    exit 1
fi

echo "✅ Discord token found"

# Check if guild and channel IDs are set for full test
if [ -z "$TEST_GUILD_ID" ] || [ -z "$TEST_VOICE_CHANNEL_ID" ]; then
    echo "⚠️  TEST_GUILD_ID and/or TEST_VOICE_CHANNEL_ID not set"
    echo "For full testing, please set:"
    echo "export TEST_GUILD_ID='your-server-id'"
    echo "export TEST_VOICE_CHANNEL_ID='your-voice-channel-id'"
    echo ""
    echo "Running in interactive mode instead..."
    python test_discord_voice_diagnostics.py --interactive
else
    echo "✅ Test guild and channel configured"
    echo "Running comprehensive diagnostics..."
    python test_discord_voice_diagnostics.py
fi