# Connection Cleanup Fix for VPS Deployment

## Problem
The Discord bot was showing "Unclosed connection" warnings when running on VPS, indicating that aiohttp ClientSession connections were not being properly closed during shutdown. This could lead to resource leaks and connection exhaustion over time.

## Root Causes
1. **Decentralized Session Management**: Multiple components were creating their own aiohttp ClientSessions without centralized management
2. **Incomplete Cleanup**: Some platforms and services weren't properly closing their sessions during shutdown
3. **Missing Connection Pooling**: No connection pool limits for VPS environments
4. **Improper Shutdown Sequence**: Bot shutdown wasn't ensuring all HTTP connections were closed

## Solution Overview
Implemented a centralized HTTP session manager that:
- Manages all aiohttp ClientSessions globally
- Ensures proper cleanup during shutdown
- Provides connection health monitoring
- Implements VPS-optimized connection pooling

## Changes Made

### 1. Created Global HTTP Session Manager (`src/services/http_session_manager.py`)
- Singleton pattern for centralized session management
- Automatic connection cleanup with proper delays
- Connection leak detection and monitoring
- VPS-optimized connection pool settings:
  - Total connection pool size: 100
  - Connections per host: 10
  - DNS cache TTL: 300 seconds
  - Force close connections on cleanup

### 2. Updated Voice Connection Manager (`src/services/voice_connection_manager.py`)
- Added import for session manager
- Added cleanup method to disconnect all voice connections
- Ensures proper state cleanup during shutdown

### 3. Updated Platform Base Class (`src/platforms/base.py`)
- Modified to use session manager instead of creating own sessions
- Simplified cleanup - session manager handles actual cleanup
- Platform-specific configuration support

### 4. Fixed YouTube Platform (`src/platforms/youtube.py`)
- Updated `_validate_stream_url_async` to use platform's session instead of creating new one
- Prevents connection leaks during URL validation

### 5. Updated Odysee Platform (`src/platforms/odysee.py`)
- Removed direct ClientSession creation
- Uses session manager with custom headers
- Simplified cleanup method

### 6. Updated Cookie Health Monitor (`src/services/cookie_health_monitor.py`)
- Uses session manager for cookie validation requests
- Maintains cookie jar functionality while using managed sessions

### 7. Enhanced Bot Shutdown (`src/bot/bot.py`)
- Added HTTP session manager cleanup at the end of shutdown sequence
- Added voice connection manager cleanup
- Added 1-second delay to ensure connections close properly
- Emergency cleanup in error handler

### 8. Added Health Monitoring (`src/services/health_endpoints.py`)
- New endpoints for HTTP session health:
  - `/health/http-sessions` - Session health status
  - `/health/http-sessions/stats` - Session statistics
- Integrated session health into detailed health report
- Alerts for unhealthy sessions and connection leaks

## Configuration

### Connection Pool Settings (per platform)
```python
{
    'limit': 100,              # Total connections
    'limit_per_host': 10,      # Per-host limit
    'ttl_dns_cache': 300,      # DNS cache TTL
    'use_dns_cache': True,     # Enable DNS caching
    'keepalive_timeout': 30,   # Keep-alive timeout
    'enable_cleanup_closed': True,  # Cleanup closed connections
    'force_close': True        # Force close on cleanup
}
```

### Timeouts
```python
{
    'total': 30,        # Total request timeout
    'connect': 10,      # Connection timeout
    'sock_connect': 10, # Socket connection timeout
    'sock_read': 10     # Socket read timeout
}
```

## Testing

Run the included test script to verify proper connection cleanup:
```bash
python test_connection_cleanup.py
```

The test script:
1. Tests session manager functionality
2. Verifies platform session management
3. Simulates full bot shutdown
4. Checks for any remaining connections

## Monitoring

### Health Check Endpoints
- `GET /health/http-sessions` - Check session health
- `GET /health/http-sessions/stats` - View session statistics
- `GET /health/detailed` - Includes HTTP session info

### Key Metrics to Monitor
- `stats.active` - Number of active sessions
- `stats.created` - Total sessions created
- `stats.closed` - Total sessions properly closed
- `stats.leaked` - Sessions that leaked (weren't properly closed)

### Alerts to Set Up
1. **Connection Leaks**: Alert if `stats.leaked` > 0
2. **Too Many Sessions**: Alert if `stats.active` > 50
3. **Unhealthy Sessions**: Alert if any sessions report as unhealthy

## Best Practices

### For New Components
1. Never create `aiohttp.ClientSession` directly
2. Always use `get_session_manager().get_session(name)`
3. Don't manually close sessions - let the manager handle it
4. Use descriptive session names for debugging

### For Platform Developers
1. Override `initialize()` but always call `await super().initialize()`
2. Use `self.session` for all HTTP requests
3. Don't override `cleanup()` unless necessary - parent handles it

### For Service Developers
1. Import `from src.services.http_session_manager import get_session_manager`
2. Get sessions with appropriate names: `session = await manager.get_session("service_name")`
3. Let the manager handle all cleanup

## Troubleshooting

### Still Seeing Connection Warnings?
1. Check test script output for which component is leaking
2. Look for any direct `ClientSession()` usage: `grep -r "ClientSession(" src/`
3. Verify all components are using the session manager
4. Check health endpoint for leaked connections

### High Connection Count?
1. Review connection pool settings
2. Check if components are creating too many named sessions
3. Consider reducing `limit_per_host` for less critical services
4. Monitor with `/health/http-sessions/stats`

### Connection Timeouts?
1. Increase timeout values in platform config
2. Check VPS network performance
3. Review DNS cache settings
4. Consider regional differences in latency