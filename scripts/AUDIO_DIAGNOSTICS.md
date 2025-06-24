# Audio Pipeline Diagnostic Tools

This directory contains diagnostic tools to help identify and fix audio pipeline issues in Robustty.

## Scripts

### 1. `test-audio-playback.py` - Comprehensive Diagnostic Tool

Tests the complete audio pipeline from YouTube URL extraction to Discord audio format validation.

**Usage:**
```bash
# Test a specific YouTube URL
python scripts/test-audio-playback.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Run comprehensive tests with multiple URLs
python scripts/test-audio-playback.py --test-all

# Save results to a file
python scripts/test-audio-playback.py --test-all --output audio_test_report.txt

# Enable verbose logging
python scripts/test-audio-playback.py --test-all --verbose
```

**Tests Performed:**
1. **URL Validation** - Validates YouTube URL format and extracts video ID
2. **Platform Initialization** - Tests YouTube platform initialization and API key
3. **Cookie Validation** - Checks for YouTube cookies and validates conversion
4. **Stream Extraction** - Tests yt-dlp stream URL extraction with different formats
5. **FFmpeg Compatibility** - Validates FFmpeg installation and Discord audio options
6. **Discord Audio Format** - Tests Discord.py audio source creation
7. **Network Reliability** - Tests stream URL accessibility and reliability
8. **Error Handling** - Validates error handling for various failure scenarios

### 2. `fix-audio-issues.py` - Automated Issue Fixer

Provides automated fixes for common audio pipeline issues identified by the diagnostic tool.

**Usage:**
```bash
# Check for issues without fixing
python scripts/fix-audio-issues.py --check

# Fix all identified issues automatically
python scripts/fix-audio-issues.py --fix-all

# Fix specific components
python scripts/fix-audio-issues.py --fix-ffmpeg
python scripts/fix-audio-issues.py --fix-cookies
python scripts/fix-audio-issues.py --fix-environment
python scripts/fix-audio-issues.py --fix-dependencies
python scripts/fix-audio-issues.py --fix-permissions
```

**Issues Fixed:**
- **FFmpeg Installation** - Installs FFmpeg using platform-specific package managers
- **Cookie Extraction** - Creates cookie directories and runs extraction scripts
- **Environment Configuration** - Creates .env file from template
- **Missing Dependencies** - Installs Python packages from requirements.txt
- **Directory Permissions** - Fixes file/directory permission issues

## Common Issues and Solutions

### 1. Stream URL Extraction Fails

**Symptoms:**
- yt-dlp returns no stream URL
- "No valid stream URL found" errors
- Platform-specific extraction failures

**Diagnostic Steps:**
```bash
python scripts/test-audio-playback.py "https://www.youtube.com/watch?v=VIDEO_ID" --verbose
```

**Common Fixes:**
- Extract and update YouTube cookies
- Check for yt-dlp updates
- Verify network connectivity
- Test with different video URLs

### 2. FFmpeg Audio Processing Issues

**Symptoms:**
- "FFmpeg not found" errors
- Audio format conversion failures
- Discord audio source creation fails

**Diagnostic Steps:**
```bash
python scripts/fix-audio-issues.py --check
python scripts/test-audio-playback.py --test-all
```

**Common Fixes:**
```bash
# Install FFmpeg
python scripts/fix-audio-issues.py --fix-ffmpeg

# Or manually on macOS:
brew install ffmpeg

# On Ubuntu/Debian:
sudo apt update && sudo apt install ffmpeg
```

### 3. Cookie-Related Issues

**Symptoms:**
- Limited stream quality
- "Sign in to confirm you're not a bot" errors
- Rate limiting from YouTube

**Diagnostic Steps:**
```bash
python scripts/test-audio-playback.py --test-all --verbose
```

**Common Fixes:**
```bash
# Extract cookies from Brave browser
python scripts/extract-brave-cookies.py

# Fix cookie-related issues
python scripts/fix-audio-issues.py --fix-cookies
```

### 4. Discord Voice Connection Issues

**Symptoms:**
- Voice client connection failures
- Audio playback starts but no sound
- "Voice client disconnected" errors

**Diagnostic Steps:**
1. Run comprehensive audio test:
   ```bash
   python scripts/test-audio-playback.py --test-all
   ```

2. Check bot permissions and voice channel access

3. Verify FFmpeg options are Discord-compatible

**Common Fixes:**
- Ensure bot has proper voice permissions
- Update Discord.py to latest version
- Check voice channel region compatibility

### 5. Network and Streaming Issues

**Symptoms:**
- Stream URLs become invalid quickly
- Frequent playback interruptions
- Network timeout errors

**Diagnostic Steps:**
```bash
python scripts/test-audio-playback.py "URL" --verbose
```

**Common Fixes:**
- Check network stability
- Update cookies for better access
- Implement stream URL caching with shorter TTL
- Use HLS streams for better reliability

## Interpreting Test Results

### Test Status Indicators
- **✓ SUCCESS** - Test passed without issues
- **⚠ WARNING** - Test passed but with minor issues
- **✗ FAILED** - Test failed and requires attention
- **○ SKIPPED** - Test was skipped due to missing prerequisites

### Key Metrics to Watch
1. **Stream URL Extraction Success Rate** - Should be close to 100%
2. **FFmpeg Compatibility** - Must pass for audio playback
3. **Network Reliability** - Success rate should be >80%
4. **Cookie Validation** - Important for stream quality

### Performance Benchmarks
- **URL Validation**: < 1 second
- **Stream Extraction**: < 10 seconds
- **FFmpeg Probe**: < 5 seconds
- **Network Tests**: < 15 seconds total

## Integration with CI/CD

These diagnostic tools can be integrated into CI/CD pipelines:

```bash
# Add to your CI script
python scripts/test-audio-playback.py --test-all --output ci_audio_test.txt
if [ $? -ne 0 ]; then
    echo "Audio pipeline tests failed"
    exit 1
fi
```

## Troubleshooting Tips

1. **Always run tests with --verbose for detailed logs**
2. **Check audio_pipeline_test.log for detailed error information**
3. **Test with multiple YouTube URLs to identify pattern issues**
4. **Run diagnostic tests after any major configuration changes**
5. **Keep cookies updated for best results**

## Contributing

When adding new audio pipeline features:
1. Add corresponding tests to `test-audio-playback.py`
2. Add automated fixes to `fix-audio-issues.py` where possible
3. Update this documentation with new diagnostic procedures
4. Test the full pipeline before submitting changes

For questions or issues with these diagnostic tools, please check the main project documentation or create an issue with diagnostic test output.