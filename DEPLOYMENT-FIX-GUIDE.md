# 🚀 Robustty Fix Deployment Guide

This guide provides step-by-step instructions to apply all the fixes for the issues identified in your VPS logs.

## 📋 Issues Fixed

✅ **YouTube API Parameter Error** - Removed invalid `hl` parameter  
✅ **Network Connectivity Issues** - DNS and Discord access fixes  
✅ **Cookie File Missing Warnings** - Ensure all platform cookie files exist  
✅ **Platform Fallback Problems** - Circuit breaker and prioritization fixes  

## 🔧 Apply Fixes to VPS

### Step 1: Update the Repository

```bash
# SSH to your VPS
ssh root@164.92.93.19

# Navigate to your project directory
cd ~/Robustty

# Pull the latest changes (make sure your local changes are pushed first)
git pull origin main

# Or if you need to update manually, copy the key files:
# - Updated: src/platforms/youtube.py (fixed hl parameter)
# - Added: scripts/ensure-cookie-files.py (cookie file management)  
# - Updated: Dockerfile.cookies (includes new cookie script)
# - Updated: cookie-service.sh (runs cookie file check on startup)
# - Added: debug-vps-network.sh (network diagnostics)
# - Added: fix-vps-network-issues.sh (network fixes)
```

### Step 2: Diagnose Network Issues

```bash
# Run network diagnostics
./debug-vps-network.sh

# This will show you:
# - DNS resolution status for Discord domains
# - HTTPS connectivity to Discord endpoints  
# - Current DNS configuration
# - VPS IP and location information
# - Specific error types (403, connection timeout, etc.)
```

### Step 3: Apply Network Fixes

```bash
# Apply comprehensive network fixes (requires root)
sudo ./fix-vps-network-issues.sh

# Or apply specific fixes:
sudo ./fix-vps-network-issues.sh --dns-only          # DNS only
sudo ./fix-vps-network-issues.sh --firewall-only     # Firewall only
sudo ./fix-vps-network-issues.sh --test-only         # Test without changes
```

### Step 4: Rebuild and Restart the Bot

```bash
# Stop current containers
docker-compose down

# Rebuild with all fixes applied
docker-compose up -d --build

# Monitor the logs to see if issues are resolved
docker-compose logs -f robustty
```

## 🧪 Test the Fixes

### Monitor Logs for Improvements

```bash
# Watch bot logs in real-time
docker-compose logs -f robustty

# Look for these improvements:
# ✅ No more "unexpected keyword argument hl" errors
# ✅ YouTube circuit breaker should reset and work again
# ✅ No more "cookie file not found" warnings  
# ✅ Improved Discord connectivity (fewer 403/timeout errors)
```

### Test Platform Functionality

```bash
# Test YouTube search directly (if you have the environment set up)
python3 -c "
import asyncio
from src.platforms.youtube import YouTubePlatform
async def test():
    yt = YouTubePlatform({})
    results = await yt.search_videos('test music', 1)
    print(f'Found {len(results)} results')
    if results:
        print(f'First result: {results[0].title}')
asyncio.run(test())
"
```

### Check Cookie Files

```bash
# Verify all platform cookie files exist
ls -la /path/to/cookies/
# Should show: youtube_cookies.json, rumble_cookies.json, odysee_cookies.json, peertube_cookies.json

# Check cookie file contents (should be valid JSON, may be empty arrays)
cat /path/to/cookies/odysee_cookies.json
cat /path/to/cookies/peertube_cookies.json
```

## 🔍 Expected Improvements

### 1. YouTube Platform Recovery
- **Before**: `ERROR: YouTube search error: Got an unexpected keyword argument hl`
- **After**: YouTube searches work normally, circuit breaker resets

### 2. Network Connectivity  
- **Before**: `Discord CDN: HTTP 403`, `No working Discord gateways found`
- **After**: Improved Discord connectivity (may still have some restrictions based on VPS IP)

### 3. Platform Search Behavior
- **Before**: PeerTube used first due to YouTube circuit breaker being open
- **After**: YouTube prioritized again (proper platform ordering restored)

### 4. Cookie Warnings
- **Before**: `No cookie file found for odysee/peertube` 
- **After**: All platforms have cookie files (empty if no cookies extracted)

## 🚨 If Issues Persist

### YouTube Still Failing
```bash
# Check if the fix was applied correctly
grep -n "hl.*interface_language" src/platforms/youtube.py
# Should return no results (the line was removed)

# Test YouTube API manually
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&regionCode=US&relevanceLanguage=en"
```

### Network Issues Continue
```bash
# Check if VPS IP is blocked by Discord
curl -v https://discord.com/api/v10/gateway
# Look for HTTP response codes:
# - 200: OK (connectivity working)
# - 403: Forbidden (IP likely blocked)
# - Timeout: DNS/firewall issue

# Consider these solutions:
# 1. Try different VPS provider/location
# 2. Contact VPS provider about Discord restrictions
# 3. Use residential proxy or VPN
# 4. Check with Discord about IP restrictions
```

### Cookie Issues Continue
```bash
# Manual cookie file creation
mkdir -p /app/cookies
echo '[]' > /app/cookies/odysee_cookies.json
echo '[]' > /app/cookies/peertube_cookies.json

# Check if Brave browser data is properly mounted
ls -la /host-brave/Default/Cookies
# Should show the Brave cookies database file
```

## 📊 Monitoring Success

### Key Log Indicators of Success

✅ **YouTube Working**:
```
INFO:src.platforms.youtube:Found 5 videos for query 'music'
INFO:src.services.searcher:Search completed: youtube(5), rumble(3), odysee(2)
```

✅ **Circuit Breaker Reset**:
```  
INFO:src.utils.network_resilience:Circuit breaker youtube_search reset to CLOSED
```

✅ **Network Connectivity**:
```
INFO:src.utils.network_connectivity:✓ Discord API: HTTP 200
INFO:src.utils.network_connectivity:✓ Discord CDN: HTTP 200
```

✅ **Cookie Files**:
```
INFO:src.services.cookie_health_monitor:All cookie files healthy
```

### Performance Metrics
- YouTube search latency should improve (< 2 seconds typical)
- Circuit breaker failures should drop to 0
- Platform search should prefer YouTube again
- Discord connectivity should be more stable

## 🎯 Summary

1. **Applied Fix**: Remove invalid `hl` parameter from YouTube API calls
2. **Network Fixes**: DNS, firewall, and Docker networking improvements  
3. **Cookie Management**: Ensure all platform cookie files exist
4. **Monitoring**: Comprehensive diagnostic and fix scripts provided

The bot should now work much more reliably with proper YouTube functionality and improved network connectivity. Monitor the logs after applying these fixes to confirm the improvements.