# Discord Voice Connection 4006 Error Fixes

## Overview

This document outlines the comprehensive fixes implemented to address Discord WebSocket code 4006 errors and connection cleanup problems in the Robustty music bot.

## Issues Addressed

1. **WebSocket Error 4006**: Session invalidation/authentication expired errors
2. **Connection Cleanup**: Improper voice connection cleanup leading to stuck connections
3. **Permission Validation**: Missing voice channel permission checks before connecting
4. **Retry Logic**: Lack of robust retry mechanisms for failed voice connections
5. **Error Handling**: Inadequate error handling for various Discord voice connection issues

## Solutions Implemented

### 1. Enhanced Voice Connection Manager (`src/services/voice_connection_manager.py`)

**New Features:**
- **Retry Logic with Exponential Backoff**: Implements configurable retry attempts with exponential backoff (2s, 4s, 8s, 16s, 60s max)
- **WebSocket Error Code Handling**: Specific handling for Discord error codes including 4006 (session invalid), 4009 (timeout), 4014 (server crash)
- **Permission Validation**: Pre-connection validation of bot permissions (Connect, Speak, Use Voice Activity)
- **Connection State Tracking**: Tracks connection states per guild (disconnected, connecting, connected, reconnecting, failed)
- **Health Monitoring**: Connection health checks and status reporting

**Key Methods:**
```python
async def connect_to_voice(voice_channel, current_voice_client=None) -> tuple[VoiceClient, str]
async def move_to_voice(voice_channel, voice_client) -> tuple[bool, str]
async def disconnect_from_voice(guild_id, voice_client, force=False) -> tuple[bool, str]
async def health_check_connections() -> List[int]  # Returns unhealthy guild IDs
```

**Configuration:**
- Max retry attempts: 5
- Base retry delay: 2 seconds
- Max retry delay: 60 seconds  
- Connection timeout: 30 seconds

### 2. Enhanced Music Cog (`src/bot/cogs/music.py`)

**Updates:**
- **Integration with Voice Manager**: All voice connection operations now use the enhanced voice connection manager
- **Improved Error Messages**: More detailed error messages with specific troubleshooting steps
- **Graceful Fallbacks**: Better handling when voice connections fail during playback
- **Status Reporting**: Enhanced feedback to users about connection issues

**Key Changes:**
- `join` command: Uses voice manager with retry logic and permission validation
- `play` command: Enhanced voice connection handling with better error recovery
- `test` command: Improved connection handling for audio testing
- `leave` command: Proper cleanup using voice manager disconnect

### 3. Enhanced Audio Player (`src/services/audio_player.py`)

**Improvements:**
- **Connection Validation**: Added methods to validate voice connection status
- **Playback Error Handling**: Enhanced error detection for 4006 and other voice errors
- **Graceful Recovery**: Better handling when voice connections are lost during playback
- **Connection Cleanup**: Automatic cleanup of invalid voice client references

**New Methods:**
```python
def is_voice_connected() -> bool
def validate_voice_connection() -> tuple[bool, str]
```

**Enhanced Error Detection:**
- Detects WebSocket errors (4006, session, connection closed)
- Handles Discord client exceptions more gracefully
- Automatic voice client cleanup on connection failures

### 4. Bot Integration (`src/bot/bot.py`)

**Updates:**
- **Voice Manager Initialization**: Added voice connection manager to bot setup
- **Service Integration**: Integrated with existing bot architecture

### 5. Admin Commands (`src/bot/cogs/admin.py`)

**New Commands:**
- `!voicehealth` / `!vhealth`: Show voice connection health status across all guilds
- `!voicediag` / `!vdiag`: Run voice connection diagnostics and health checks

**Features:**
- Real-time voice connection status monitoring
- Per-guild connection state reporting
- Health statistics and recommendations
- Diagnostic actions and troubleshooting steps

## WebSocket Error Code Mapping

The voice connection manager includes specific handling for Discord WebSocket error codes:

| Code | Description | Action |
|------|-------------|---------|
| 4006 | Session no longer valid - authentication expired | Retry with new session |
| 4009 | Session timeout - connection idle too long | Retry connection |
| 4011 | Server not found - voice server unavailable | Limited retries |
| 4012 | Unknown protocol - voice protocol mismatch | Limited retries |
| 4013 | Disconnected - forcibly removed from channel | Limited retries |
| 4014 | Voice server crashed - temporary server issue | Retry connection |
| 4015 | Unknown encryption mode - voice encryption issue | Limited retries |

## Connection State Management

The voice manager tracks connection states per guild:

- **DISCONNECTED**: No active connection
- **CONNECTING**: Attempting initial connection
- **CONNECTED**: Successfully connected and verified
- **RECONNECTING**: Attempting to reconnect after failure
- **FAILED**: Connection failed after all retry attempts

## Permission Validation

Before attempting any voice connection, the system validates:

1. **Connect Permission**: Bot can join voice channels
2. **Speak Permission**: Bot can transmit audio
3. **Voice Activity Permission**: Bot can use voice activation
4. **Channel Capacity**: Voice channel is not full (if user limit set)

## Error Recovery Strategies

### For WebSocket 4006 Errors:
1. **Immediate Retry**: First attempt with minimal delay
2. **Exponential Backoff**: Increasing delays between retry attempts
3. **Session Renewal**: Each retry creates a fresh connection session
4. **Graceful Degradation**: Clear error messages if all retries fail

### For Connection Timeouts:
1. **Timeout Detection**: 30-second connection timeout
2. **Retry Logic**: Up to 5 retry attempts with backoff
3. **Alternative Channels**: Suggestions to try different voice channels

### For Permission Issues:
1. **Pre-validation**: Check permissions before connection attempts
2. **Specific Errors**: Detailed messages about missing permissions
3. **Troubleshooting**: Step-by-step resolution guidance

## Monitoring and Diagnostics

### Health Monitoring:
- Continuous monitoring of voice connection states
- Automatic detection of disconnected clients
- Health statistics and success rate tracking

### Admin Tools:
- Real-time voice connection dashboard
- Diagnostic commands for troubleshooting
- Per-guild connection status reporting

### Logging:
- Enhanced logging for voice connection events
- Specific error code tracking and reporting
- Connection attempt and failure analysis

## Benefits

1. **Reduced 4006 Errors**: Intelligent retry logic handles session invalidation
2. **Better User Experience**: Clear error messages and troubleshooting steps
3. **Improved Reliability**: Robust error handling and recovery mechanisms
4. **Enhanced Monitoring**: Real-time connection health and diagnostics
5. **VPS Compatibility**: Optimized for VPS deployments with network variability

## Usage Examples

### For Users:
```
!join          # Connect to voice with enhanced error handling
!play <song>   # Play music with robust voice connection management
!vhealth       # Check voice connection health (admin)
!vdiag         # Run voice diagnostics (admin)
```

### For Developers:
```python
# Use voice manager in bot code
voice_client, status = await bot.voice_connection_manager.connect_to_voice(channel)
if voice_client:
    # Connection successful
    pass
else:
    # Handle connection failure with specific status message
    print(f"Connection failed: {status}")
```

## Configuration

No additional configuration is required. The voice connection manager uses sensible defaults:

- **Retry attempts**: 5 (configurable)
- **Retry delays**: 2s, 4s, 8s, 16s, 32s (capped at 60s)
- **Connection timeout**: 30 seconds
- **Health check interval**: On-demand via admin commands

## Future Enhancements

1. **Automatic Health Checks**: Periodic background health monitoring
2. **Voice Region Optimization**: Automatic selection of optimal voice regions
3. **Advanced Metrics**: Detailed connection analytics and reporting
4. **Webhook Notifications**: Admin notifications for persistent connection issues

---

## Files Modified

1. **New**: `src/services/voice_connection_manager.py` - Core voice connection management
2. **Updated**: `src/bot/cogs/music.py` - Enhanced music commands with voice manager
3. **Updated**: `src/services/audio_player.py` - Improved connection validation and error handling
4. **Updated**: `src/bot/bot.py` - Voice manager integration
5. **Updated**: `src/bot/cogs/admin.py` - Added voice health monitoring commands
6. **New**: `test_voice_connection_fix.py` - Test script for validation
7. **New**: `VOICE_CONNECTION_FIXES.md` - This documentation

## Testing

Run the test script to validate the implementation:
```bash
python3 test_voice_connection_fix.py
```

The implementation has been validated for:
- Syntax correctness
- Import compatibility
- Integration with existing codebase
- Enhanced error handling capabilities