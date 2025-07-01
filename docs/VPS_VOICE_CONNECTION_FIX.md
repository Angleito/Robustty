# VPS Voice Connection Fix Documentation

This document describes the comprehensive fixes implemented to resolve Discord voice connection issues on VPS deployments.

## Problem Summary

Voice connections on VPS deployments were experiencing:
- WebSocket error 4006 (Session no longer valid) 
- Connection timeouts and instability
- Failed reconnection attempts
- Voice clients not being properly cleaned up
- Poor network conditions causing frequent disconnects

## Implemented Fixes

### 1. Enhanced VPS Configuration
- **Increased base retry delay**: From 8s to 10s (Discord recommends 6+ seconds minimum)
- **Extended connection timeout**: From 60s to 90s for VPS environments
- **Higher circuit breaker threshold**: From 3 to 5 failures before disabling
- **Longer session timeout**: 5 minutes for VPS (vs 3 minutes)
- **More retry attempts**: 5 attempts for VPS (vs 3 previously)

### 2. Improved Voice Client Cleanup
- Enhanced `_cleanup_existing_connection` method to:
  - Search and remove all voice clients for a guild
  - Clear guild's internal voice client reference
  - Remove clients from bot's voice_clients list
  - Wait longer (5s) on VPS for network cleanup
- Enhanced `_force_disconnect_guild` method with similar improvements

### 3. Environment Variable Override
- Added `VOICE_ENVIRONMENT` variable to force specific modes:
  ```bash
  export VOICE_ENVIRONMENT=vps    # Force VPS mode
  export VOICE_ENVIRONMENT=local  # Force local mode
  export VOICE_ENVIRONMENT=docker # Force Docker mode
  ```

### 4. Aggressive Session Recreation for VPS
- Force new sessions on timeout errors in VPS environments
- Invalidate sessions with 3+ reconnect attempts
- Create new sessions for WebSocket/session-related errors
- Shorter effective session timeout (75% of configured) for VPS

### 5. Comprehensive Network Stability Checks
- Multiple endpoint checks before connecting:
  - Discord API gateway
  - Discord CDN
  - Voice regions endpoint
- Requires 2/3 checks to pass for stability
- Retry with recovery attempt if initial check fails

## Usage

### Setting VPS Mode

#### Method 1: Environment Variable (Recommended)
```bash
# In your .env file or shell
export VOICE_ENVIRONMENT=vps
```

#### Method 2: Auto-detection
The bot automatically detects VPS environment based on:
- Docker container with specific network configuration
- Environment variables (IS_VPS=true, DEPLOYMENT_TYPE=vps)
- Redis URL pattern (redis://redis:)
- Hostname patterns
- Headless environment indicators

#### Method 3: Admin Command
```bash
!voiceenv vps  # Force VPS mode via Discord command
```

### Admin Commands

- `!voicehealth` - Shows voice connection status and environment
- `!voicediag` - Runs diagnostics and shows detailed connection info
- `!voiceenv [vps|local|auto]` - View or change voice environment settings

### Testing

Run the comprehensive test suite:
```bash
# Test with auto-detected environment
python tests/manual/test_vps_voice_fixes.py

# Test with forced VPS environment
python tests/manual/test_vps_voice_fixes.py vps

# Test commands in Discord:
!test_connect     # Test basic connection
!test_reconnect   # Test reconnection handling
!test_session     # Test session management
!test_network     # Test network stability
!test_cleanup     # Test cleanup mechanisms
!test_environment # Show current configuration
```

## VPS Deployment Recommendations

1. **Set Environment Variable**: Always set `VOICE_ENVIRONMENT=vps` in production
2. **Monitor Logs**: Watch for "Voice Connection Manager initialized in VPS environment"
3. **Network Quality**: Ensure VPS has stable network with low latency to Discord
4. **Resource Allocation**: Voice connections require adequate CPU and memory
5. **Regular Monitoring**: Use `!voicehealth` command to monitor connection status

## Troubleshooting

### Connection Failures
1. Check environment detection: `!voiceenv`
2. Force VPS mode if needed: `!voiceenv vps`
3. Check network stability: `!test_network` 
4. Review voice health: `!voicehealth`

### Session Issues
- Bot automatically creates new sessions for error 4006
- Sessions expire after 5 minutes on VPS
- Check session info with `!voicediag`

### Circuit Breaker Open
- After 5 consecutive failures, connections are temporarily disabled
- Wait 5 minutes or use `!reset-circuit-breakers` command
- Check status with `!voicehealth`

## Technical Details

### Error Code Handling
- **4006**: Session invalid → Force new session and full cleanup
- **4009**: Session timeout → Create new session
- **4011**: Server not found → Retry with backoff
- **4014**: Server crashed → Retry with backoff

### VPS-Specific Optimizations
- Longer wait times between operations
- More aggressive session management
- Enhanced cleanup procedures
- Network stability verification
- Higher tolerance for transient failures