# Discord Voice Connection Testing

This directory contains comprehensive tools to diagnose and test Discord voice connection and audio playback issues.

## Test Files Overview

### 1. `test_ffmpeg_setup.py` - Setup Verification
**Run this first** to verify your basic setup.

```bash
python test_ffmpeg_setup.py
```

**What it tests:**
- FFmpeg installation and version
- FFmpeg audio processing capabilities  
- Discord.py installation and audio classes
- FFmpeg compatibility with Discord.py options

### 2. `test_audio_simple.py` - Interactive Bot Test
Simple Discord bot that mimics your exact audio implementation.

```bash
python test_audio_simple.py
```

**Commands in Discord:**
- `!testjoin` - Join your voice channel
- `!testplay` - Play test audio using exact same setup as main bot
- `!teststatus` - Check voice client status
- `!teststop` - Stop audio playback  
- `!testleave` - Leave voice channel

### 3. `test_discord_voice_diagnostics.py` - Comprehensive Diagnostics
Full automated testing suite.

```bash
# Interactive mode (recommended)
python test_discord_voice_diagnostics.py --interactive

# Full automated mode (requires TEST_GUILD_ID and TEST_VOICE_CHANNEL_ID)
python test_discord_voice_diagnostics.py
```

### 4. `run_voice_test.sh` - Easy Runner Script
Convenience script that sets up environment and runs appropriate tests.

```bash
./run_voice_test.sh
```

## Setup Requirements

### Environment Variables
Create a `.env` file or export these variables:

```bash
# Required
DISCORD_TOKEN=your_discord_bot_token_here

# Optional (for automated testing)
TEST_GUILD_ID=your_server_id_here
TEST_VOICE_CHANNEL_ID=your_voice_channel_id_here
```

### Dependencies
```bash
pip install discord.py[voice]
```

### System Requirements
- **FFmpeg**: Must be installed and accessible in PATH
  - macOS: `brew install ffmpeg`
  - Ubuntu: `sudo apt install ffmpeg`
  - Windows: Download from https://ffmpeg.org/

## Testing Strategy

### Step 1: Basic Setup Verification
```bash
python test_ffmpeg_setup.py
```
This will verify FFmpeg and Discord.py are properly installed.

### Step 2: Interactive Testing
```bash
python test_audio_simple.py
```
1. Start the bot
2. Join a voice channel in Discord
3. Use `!testjoin` to connect the bot
4. Use `!testplay` to test audio playback
5. Listen for audio and check logs

### Step 3: Comprehensive Diagnostics
```bash
python test_discord_voice_diagnostics.py --interactive
```
Use `!diagtest` command in Discord for full automated testing.

## Common Issues and Solutions

### ❌ "FFmpeg not found"
**Solution:** Install FFmpeg and ensure it's in your PATH
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian  
sudo apt install ffmpeg

# Verify installation
ffmpeg -version
```

### ❌ "Cannot connect to voice channel"
**Solution:** Check bot permissions
- Bot needs "Connect" and "Speak" permissions in voice channel
- Bot must be in the same server as the voice channel
- Voice channel must not be full or restricted

### ❌ "Audio starts but no sound"
**Solution:** Check audio routing
- Verify Discord audio settings (User Settings > Voice & Video)
- Check system audio output device
- Try different voice channel or server
- Verify bot has "Speak" permission

### ❌ "Playback fails immediately"
**Solution:** Check stream URL and FFmpeg options
- Test with local audio file first
- Verify YouTube/platform URL accessibility
- Check network connectivity
- Review FFmpeg error messages in logs

### ❌ "Discord.py audio imports fail"
**Solution:** Install voice dependencies
```bash
pip install discord.py[voice]
# or
pip install PyNaCl
```

## Interpreting Results

### ✅ All Tests Pass
Your setup is working correctly. If you still have issues:
- Check Discord client audio settings
- Try different voice channels/servers
- Verify network connectivity

### ❌ FFmpeg Tests Fail
Focus on FFmpeg installation:
1. Reinstall FFmpeg
2. Check PATH environment variable
3. Test FFmpeg manually: `ffmpeg -version`

### ❌ Discord Connection Fails
Focus on Discord setup:
1. Verify bot token is correct
2. Check bot permissions in Discord Developer Portal
3. Ensure bot is invited to your server with correct permissions

### ❌ Voice Connection Fails
Focus on Discord voice permissions:
1. Check bot permissions in voice channel
2. Try different voice channels
3. Check Discord server settings

### ❌ Audio Playback Fails
Focus on audio pipeline:
1. Test with local audio files
2. Check stream URL accessibility
3. Review FFmpeg error messages
4. Test with different audio sources

## Log Files

Tests generate detailed logs:
- `voice_diagnostics.log` - Comprehensive diagnostics log
- Console output - Real-time test results

## Getting Help

If tests reveal issues:
1. Check the logs for detailed error messages
2. Verify all dependencies are installed correctly
3. Test with a minimal setup (local audio file)
4. Check Discord.py and FFmpeg documentation

## Advanced Debugging

For deeper investigation:
```bash
# Enable verbose Discord.py logging
export PYTHONPATH="."
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Run your test here
"

# Test FFmpeg directly with your URLs
ffmpeg -i "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -vn -f null -

# Test Discord.py audio source creation
python -c "
import discord
source = discord.FFmpegPCMAudio('test.wav')
print('Audio source created successfully')
"
```