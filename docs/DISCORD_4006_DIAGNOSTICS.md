# Discord Error 4006 Diagnostics Guide

## Overview

Discord Error 4006 ("Session Timed Out") is one of the most common voice connection issues that can affect Discord bots. This guide explains how to use the enhanced diagnostic script to troubleshoot and resolve these issues.

## Quick Start

### Running the Diagnostic Script

```bash
# From Docker container (recommended)
docker-compose exec robustty python scripts/diagnose-discord-4006.py

# Or locally (requires DISCORD_TOKEN environment variable)
export DISCORD_TOKEN=your_bot_token
python scripts/diagnose-discord-4006.py
```

### What the Script Does

The enhanced diagnostic script performs comprehensive testing including:

1. **System Environment Checks** - Python version, Docker environment, Discord.py version
2. **Discord API Connectivity** - Tests Discord gateway, voice regions, API latency
3. **Voice Dependencies** - Validates PyNaCl, Opus codec, FFmpeg installation
4. **Network Configuration** - Tests internet connectivity, DNS resolution, port accessibility
5. **Voice Server Health** - Tests connectivity to Discord voice servers across regions
6. **Bot Permissions** - Analyzes guild access and voice channel permissions
7. **Real Voice Connection** - Performs actual voice connection tests with retry logic
8. **Configuration Analysis** - Reviews environment variables and bot configuration
9. **Error 4006 Simulation** - Analyzes potential causes and scenarios

## Understanding Error 4006

### What is Error 4006?

Error 4006 indicates "Session Timed Out" during voice connection establishment. This occurs when the voice WebSocket connection fails to complete the handshake within Discord's timeout period.

### Common Causes

1. **Discord Infrastructure Issues**
   - Voice servers experiencing high load
   - Planned maintenance or outages
   - Regional server problems

2. **Network Connectivity Problems**
   - UDP packet loss or blocking
   - Firewall restrictions on ports 50000-65535
   - VPN/proxy interference
   - NAT/router configuration issues

3. **Rate Limiting**
   - Too many rapid connection attempts
   - Discord's anti-abuse measures triggered

4. **Configuration Issues**
   - Missing bot permissions
   - Outdated Discord.py version
   - Improper retry logic

## Solution Priority

### 🔥 IMMEDIATE Actions

1. **Check Discord Status**: Visit [status.discord.com](https://status.discord.com)
2. **Wait and Retry**: Error 4006 is often temporary (wait 5-10 minutes)
3. **Change Voice Region**: Try different Discord server regions
4. **Restart Bot**: Clean restart clears connection state issues

### 🌐 NETWORK Actions

1. **Check Firewall**: Ensure UDP ports 50000-65535 are not blocked
2. **Test Without VPN**: Temporarily disable VPN
3. **Try Different Network**: Test from different internet connection
4. **Port Forward Check**: Ensure no aggressive NAT blocking

### ⚙️ CONFIGURATION Actions

1. **Update Discord.py**: Use latest version (2.3.0+)
2. **Implement Proper Backoff**: Use exponential backoff with jitter
3. **Monitor Connection Frequency**: Avoid rapid connection attempts
4. **Enable Host Networking**: For Docker, consider host networking mode

### 🔧 ADVANCED Actions

1. **Check Bot Permissions**: Verify Connect and Speak permissions
2. **Monitor Voice Server Health**: Track stable regions
3. **Implement Circuit Breaker**: Stop attempts after repeated failures
4. **Use Connection Pooling**: Reuse stable connections

## Diagnostic Script Output Interpretation

### ✅ Success Indicators
- All tests pass with green checkmarks
- Low latency to Discord APIs
- Stable voice connections
- Proper permissions detected

### ⚠️ Warning Signs
- High latency to voice servers
- Some voice servers unreachable
- Missing optional dependencies
- Configuration warnings

### ❌ Critical Issues
- Invalid Discord token
- Missing required dependencies (PyNaCl, Opus)
- No voice channel permissions
- Complete network connectivity failure

## Current Bot Implementation

The Robustty bot already includes enhanced 4006 error handling:

- ✅ Exponential backoff retry logic
- ✅ Specific 4006 error detection
- ✅ Extended cooling-off periods for 4006 errors
- ✅ Connection stability validation
- ✅ Proper cleanup of failed connections
- ✅ Multiple timeout strategies
- ✅ Force disconnect before retries

## Monitoring and Prevention

### Recommended Monitoring

```python
# Log 4006 errors with context
logger.error(f"Discord 4006 error in {guild.name}: {error}")

# Track success rates
voice_connection_success_rate = successful_connections / total_attempts

# Monitor by region
region_health = {region: success_rate for region, success_rate in region_stats.items()}
```

### Prevention Strategies

1. **Implement Health Checks**
   ```python
   async def check_voice_connection_health():
       if voice_client and not voice_client.is_connected():
           await reconnect_with_backoff()
   ```

2. **Use Circuit Breaker Pattern**
   ```python
   if consecutive_4006_errors > 5:
       await asyncio.sleep(300)  # 5-minute break
       consecutive_4006_errors = 0
   ```

3. **Regional Failover**
   ```python
   # Try different voice regions if available
   for region in preferred_regions:
       try:
           await connect_to_region(region)
           break
       except Error4006:
           continue
   ```

## Troubleshooting Common Scenarios

### Scenario 1: Persistent 4006 Errors
```
Problem: Bot consistently gets 4006 errors
Diagnosis: Run diagnostic script to check voice server health
Solution: Implement regional failover or increase backoff delays
```

### Scenario 2: Intermittent 4006 Errors
```
Problem: Random 4006 errors during peak hours
Diagnosis: Check Discord status and network stability
Solution: Implement adaptive retry logic based on time of day
```

### Scenario 3: 4006 Errors After Deployment
```
Problem: Errors started after Docker deployment
Diagnosis: Check network mode and port accessibility
Solution: Use host networking or configure port forwarding
```

## Support Resources

- **Discord Status**: https://status.discord.com
- **Discord Developer Portal**: https://discord.com/developers/applications
- **Discord.py Documentation**: https://discordpy.readthedocs.io
- **Discord API Server**: https://discord.gg/discord-api

## Script Maintenance

The diagnostic script should be run:
- After deployment changes
- When experiencing voice connection issues
- Weekly for proactive monitoring
- Before major Discord.py updates

Regular diagnostics help identify patterns and prevent issues before they affect users.