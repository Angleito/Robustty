# Discord Audio Streaming Fixes for Voice Protocol v8

This document explains the critical fixes applied to resolve Discord audio streaming issues with the new voice protocol v8.

## Issues Identified

### 1. PyNaCl Version Incompatibility
**Problem**: PyNaCl 1.5.0 lacks the `nacl.secret.Aead` module required for Discord voice protocol v8 encryption.
**Error**: `AttributeError: module 'nacl.secret' has no attribute 'Aead'`

### 2. FFmpeg Audio Format Issues
**Problem**: FFmpeg options weren't optimized for Discord's specific PCM requirements.
**Requirements**: Discord requires exactly 16-bit 48kHz stereo PCM with 3,840 bytes per 20ms frame.

### 3. Voice Protocol v8 Compatibility
**Problem**: Using Discord.py PR #10210 for voice v8 support but missing supporting configuration.

## Fixes Applied

### 1. Updated PyNaCl Version
```diff
- PyNaCl==1.5.0
+ PyNaCl>=1.6.0
```

### 2. Optimized FFmpeg Options
**Previous options**:
```python
"options": "-vn -ar 48000 -ac 2 -b:a 128k -bufsize 512k -maxrate 256k"
```

**New optimized options**:
```python
"options": (
    "-vn "                    # No video
    "-f s16le "               # 16-bit signed little-endian PCM
    "-ar 48000 "              # 48kHz sample rate (Discord requirement)
    "-ac 2 "                  # 2 channels (stereo)
    "-frame_duration 20 "     # 20ms frames for Discord
    "-application audio "     # Optimize for audio content
    "-bufsize 3840 "          # Buffer size for 20ms at 48kHz 16-bit stereo
    "-threads 0"              # Use optimal thread count
)
```

### 3. Added Fallback Audio Source Creation
Added error handling with fallback options if primary options fail:
```python
try:
    source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)
except Exception as source_error:
    # Try fallback with simpler options
    fallback_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn -f s16le -ar 48000 -ac 2"
    }
    source = discord.FFmpegPCMAudio(stream_url, **fallback_options)
```

## Technical Details

### Discord v8 Audio Requirements
- **Format**: 16-bit signed little-endian PCM (`s16le`)
- **Sample Rate**: 48,000 Hz
- **Channels**: 2 (stereo)
- **Frame Duration**: 20ms
- **Frame Size**: 3,840 bytes per frame
- **Calculation**: `48000 Hz × 0.02s × 2 channels × 2 bytes/sample = 3840 bytes`

### PyNaCl v1.6.0+ Features
- Added `nacl.secret.Aead` module for AEAD encryption
- Support for XChaCha20-Poly1305 encryption used in Discord v8
- Better compatibility with modern cryptographic requirements

### Connection Retry Logic
The existing connection retry logic in `music.py` is already well-optimized for voice v8:
- Multiple retry attempts with exponential backoff
- Proper cleanup between attempts
- Configurable timeouts via environment variables
- Force disconnect handling

## Environment Variables
Add these to your `.env` file for optimal voice performance:
```bash
# Discord voice timeouts (in seconds)
DISCORD_VOICE_TIMEOUT=30
DISCORD_RECONNECT_TIMEOUT=60
```

## Deployment Instructions

### 1. Update Dependencies
```bash
# Update PyNaCl to compatible version
pip install --upgrade "PyNaCl>=1.6.0"

# Or reinstall all requirements
pip install -r requirements.txt --upgrade
```

### 2. Docker Deployment
```bash
# Rebuild with updated dependencies
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verify logs
docker-compose logs -f robustty
```

### 3. Test Audio Streaming
```bash
# Run compatibility test
python3 test_discord_audio_fixes.py

# Test in Discord
!join    # Join voice channel
!play <song_name>    # Test audio playback
```

## Verification

### 1. Check PyNaCl Version
```python
import nacl.secret
print(hasattr(nacl.secret, 'Aead'))  # Should return True
```

### 2. Test FFmpeg Options
The audio format calculations should yield:
- Sample rate: 48,000 Hz
- Bit depth: 16 bits (2 bytes per sample)
- Channels: 2 (stereo)
- Samples per frame (20ms): 960
- Frame size: 3,840 bytes

### 3. Monitor Audio Quality
- Check for reduced audio dropouts
- Verify stable voice connections
- Monitor for 4006 connection errors (should be reduced)

## Troubleshooting

### If Audio Still Fails
1. **Check FFmpeg Installation**: Ensure FFmpeg is properly installed and accessible
2. **Verify Stream URLs**: Test with different audio sources
3. **Check Network Connectivity**: Voice protocol v8 may have different network requirements
4. **Monitor Logs**: Look for specific error messages in bot logs

### If Connection Issues Persist
1. **Update Discord.py**: Ensure you're using the latest version from PR #10210
2. **Check Bot Permissions**: Verify voice channel permissions
3. **Test Different Servers**: Some Discord servers may have specific requirements

### Common Error Messages
- `AttributeError: module 'nacl.secret' has no attribute 'Aead'` → Update PyNaCl
- `FFmpeg process exited with code 1` → Check FFmpeg options and stream URL
- `4006 error` → Connection timeout, check retry logic and network

## Performance Improvements

These fixes should provide:
- **Better Audio Quality**: Optimized PCM format for Discord
- **Improved Stability**: Proper error handling and fallback options
- **Reduced Connection Errors**: Compatible with voice protocol v8
- **Lower Latency**: Optimized buffer sizes and frame durations

## Files Modified

1. `/requirements.txt` - Updated PyNaCl version
2. `/src/services/audio_player.py` - Optimized FFmpeg options and error handling
3. `/test_discord_audio_fixes.py` - Comprehensive test script
4. `/DISCORD_AUDIO_FIXES.md` - This documentation

## Next Steps

1. Deploy the fixes to your environment
2. Run the test script to verify compatibility
3. Test audio streaming in Discord
4. Monitor logs for any remaining issues
5. Consider updating to stable Discord.py release when voice v8 is merged

## Support

If you continue experiencing issues after applying these fixes:
1. Check Discord.py GitHub issues for voice protocol v8 updates
2. Verify your FFmpeg installation and version
3. Test with different audio sources and platforms
4. Monitor Discord API status for service issues