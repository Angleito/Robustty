# PeerTube Connection Fix Summary

## Issue Identified
All PeerTube instances were failing with "Connection closed" errors due to:

1. **Response Lifecycle Issue**: The `safe_aiohttp_request` function was returning response objects that were being accessed after their connection context was closed.

2. **Aggressive Circuit Breaker**: Circuit breakers were opening after just 2 failures, preventing retry attempts.

3. **SSL/TLS Certificate Issues**: Some PeerTube instances have self-signed or invalid certificates causing connection failures.

## Changes Made

### 1. Fixed Response Handling in `src/platforms/peertube.py`
- Modified `_search_instance_direct` method to read response data while the connection is still active
- Added proper response cleanup with `response.close()` in a finally block
- This prevents "Connection closed" errors when trying to read response data

### 2. Adjusted Circuit Breaker Configuration
- Increased `failure_threshold` from 2 to 3 failures before opening
- Reduced `recovery_timeout` from 120 to 60 seconds
- Reduced instance timeout from 20 to 15 seconds for faster failure detection

### 3. Enhanced SSL/TLS Handling
- Added custom `initialize()` method for PeerTube platform
- Created SSL context with relaxed certificate verification for self-signed certs
- Added custom User-Agent header for better compatibility
- Enabled connection cleanup and force close options

### 4. Improved Error Handling
- Added specific handling for SSL/TLS errors with clearer error messages
- Enhanced connection error messages to include partial error details

### 5. Added Request Staggering
- Added 50ms delay between instance requests to avoid overwhelming servers
- Helps prevent "thundering herd" problem when searching multiple instances

## Testing
Created `test_peertube_fix.py` to verify:
- Connection handling works correctly
- Multiple instances can be searched successfully
- Health tracking and circuit breakers function properly
- SSL/TLS issues are handled gracefully

## Expected Results
- PeerTube instances should now connect successfully
- SSL certificate issues should be bypassed (with security warning logged)
- Circuit breakers should be less aggressive, allowing more retry attempts
- Connection errors should be properly handled without "Connection closed" messages

## Security Note
The relaxed SSL verification is necessary for some PeerTube instances but reduces security. In production, consider:
- Maintaining a whitelist of instances with known certificate issues
- Implementing certificate pinning for trusted instances
- Logging all SSL verification bypasses for audit purposes