# Network Diagnostic Script for Robustty Bot

The `network-diagnostic.py` script provides comprehensive network connectivity testing for the Robustty Discord bot. It validates all critical network requirements needed for the bot to function properly.

## Features

### 🔍 **Comprehensive Testing**
- **DNS Resolution**: Tests multiple DNS servers and all platform domains (Discord, YouTube, Odysee, PeerTube, Rumble)
- **HTTP Connectivity**: Validates API endpoints for all supported platforms
- **Port Connectivity**: Tests TCP connectivity to critical services
- **Redis Connectivity**: Tests Redis connections with multiple configurations
- **YouTube API**: Validates YouTube API key and quota status

### 🛠 **Environment Support**
- **Standalone**: Can run independently without bot dependencies
- **VPS Optimized**: Designed for troubleshooting VPS deployment issues
- **Docker Compatible**: Works in containerized environments
- **Fallback Mode**: Provides basic functionality even without optional dependencies

### 📊 **Detailed Reporting**
- Color-coded status indicators
- Response time measurements
- Specific error messages
- Actionable recommendations
- JSON output for automation

## Installation

### Option 1: Install Dependencies Directly
```bash
# On VPS or systems allowing pip
pip3 install aiohttp dnspython redis

# Then run diagnostic
python3 scripts/network-diagnostic.py
```

### Option 2: Use Installation Helper
```bash
# Run the dependency installer
./scripts/install-network-diagnostic-deps.sh

# Then run diagnostic
python3 scripts/network-diagnostic.py
```

### Option 3: Docker Test Environment
```bash
# Test with all dependencies in Docker
./scripts/test-network-diagnostic-docker.sh
```

## Usage

### Basic Usage
```bash
# Run comprehensive network diagnostic
python3 scripts/network-diagnostic.py
```

### Expected Output
```
Robustty Bot Network Diagnostic Tool
====================================
Checking diagnostic dependencies...
✓ All dependencies available

2025-06-27 14:30:00,000 - INFO - Starting comprehensive network diagnostic for Robustty bot...
2025-06-27 14:30:00,000 - INFO - Running DNS diagnostics...
2025-06-27 14:30:00,000 - INFO - Testing default DNS resolution...
2025-06-27 14:30:00,100 - INFO -   ✓ discord.com: 0.100s -> 162.159.138.232
...

======================================================================
ROBUSTTY BOT NETWORK CONNECTIVITY DIAGNOSTIC SUMMARY
======================================================================

✓ Best DNS performance: Cloudflare Primary - 100.0% success
✓ Discord connectivity: Working
✓ YouTube API: Working correctly
✓ Redis connectivity: Working

📊 DETAILED TEST RESULTS:
   DNS Servers Working: 5/5
   HTTP Endpoints Working: 6/6
   Port Tests Passing: 4/4
   Redis Configurations Working: 1/3
   YouTube API Status: ✓ Working

💡 NEXT STEPS:
   1. Network connectivity looks good!
   2. Start the bot with: docker-compose up -d
   3. Monitor logs with: docker-compose logs -f robustty
======================================================================
```

## What It Tests

### DNS Resolution
- **Services**: Discord, YouTube, Odysee, PeerTube, Rumble
- **DNS Servers**: Cloudflare (1.1.1.1), Google (8.8.8.8), Quad9 (9.9.9.9)
- **Metrics**: Response times, success rates, IP addresses

### HTTP Connectivity
- **Discord API**: Gateway endpoints and API availability
- **YouTube API**: Base URL and search functionality
- **Platform APIs**: Odysee, PeerTube, Rumble endpoints
- **Metrics**: HTTP status codes, response times, error details

### Port Connectivity
- **Discord HTTPS**: Port 443 connectivity
- **Discord Gateway**: WebSocket port accessibility
- **YouTube API**: HTTPS port connectivity
- **Redis**: Local and Docker Redis ports

### Redis Testing
- **Multiple Configurations**: Tests common Redis setups
- **Operations**: Ping, info, set/get operations
- **Environment Variables**: Respects REDIS_URL configuration
- **Metrics**: Connection times, Redis version, memory usage

### YouTube API Validation
- **API Key Detection**: Checks for YOUTUBE_API_KEY environment variable
- **Quota Status**: Reports remaining API quota
- **Search Testing**: Validates actual API functionality
- **Error Analysis**: Provides specific API error messages

## Environment Variables

```bash
# Required for YouTube functionality
YOUTUBE_API_KEY=your_youtube_api_key_here

# Redis configuration (auto-detected)
REDIS_URL=redis://localhost:6379  # or redis://redis:6379 for Docker

# Optional: Custom timeout values
NETWORK_TIMEOUT=10
DNS_TIMEOUT=5
```

## Troubleshooting

### Common Issues

#### 🚨 Critical DNS Issues
```
🚨 CRITICAL: No DNS servers are working properly
```
**Solutions**:
- Check internet connection: `ping 8.8.8.8`
- Restart DNS resolver: `sudo systemctl restart systemd-resolved`
- Set DNS manually: `echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf`

#### 🚨 Discord Connectivity Issues
```
🚨 CRITICAL: Discord connectivity issues detected
```
**Solutions**:
- Check firewall settings
- Try different DNS servers
- Verify Discord isn't blocked by ISP
- Test with: `curl -I https://discord.com/api/v10/gateway`

#### 🚨 Redis Connectivity Issues
```
🚨 CRITICAL: Redis connectivity failed
```
**Solutions**:
- Check Redis status: `docker-compose ps redis`
- View Redis logs: `docker-compose logs redis`
- Restart Redis: `docker-compose restart redis`
- Test manually: `redis-cli ping`

#### ⚠️ YouTube API Issues
```
⚠️ YouTube API: API key issue: Daily Limit Exceeded
```
**Solutions**:
- Check API quota in Google Cloud Console
- Wait for quota reset (daily)
- Create additional API keys for backup

### Exit Codes
- **0**: All tests passed successfully
- **1**: Critical issues detected (bot won't function)
- **2**: Script execution error

## VPS Deployment Workflow

### 1. Pre-Deployment Validation
```bash
# On local machine before VPS deployment
python3 scripts/network-diagnostic.py
```

### 2. VPS Post-Deployment Testing
```bash
# On VPS after deployment
ssh user@your-vps
cd ~/robustty-bot
python3 scripts/network-diagnostic.py
```

### 3. Docker Environment Testing
```bash
# Inside bot container
docker-compose exec robustty python3 scripts/network-diagnostic.py
```

## Integration with Other Scripts

The network diagnostic integrates with other Robustty diagnostic tools:

- **validate-pre-deployment.sh**: Calls network diagnostic as part of validation
- **validate-vps-core.sh**: Uses network tests for VPS validation  
- **diagnose-network-connectivity.py**: Complementary detailed network analysis

## Output Files

### JSON Results
Detailed results are saved to `/tmp/robustty_network_diagnostic.json`:
```json
{
  "dns_results": { ... },
  "http_results": { ... },
  "redis_results": { ... },
  "youtube_results": { ... },
  "recommendations": [ ... ],
  "timestamp": 1703676000.0
}
```

This file can be used for:
- Automated monitoring and alerting
- Historical network performance tracking
- Integration with external monitoring systems
- Debugging complex network issues

## Dependencies

### Required (for full functionality)
- `aiohttp`: HTTP client for async requests
- `dnspython`: DNS resolution testing
- `redis`: Redis connectivity testing

### Optional
- Script provides fallback functionality without these dependencies
- Basic socket-based testing works without any external packages
- Some tests will be limited but core functionality remains

## Contributing

To extend the network diagnostic:

1. **Add New Platform**: Update `test_domains` and `http_endpoints`
2. **Add New Tests**: Create new test methods following existing patterns
3. **Improve Analysis**: Enhance the `analyze_results` method
4. **Add Metrics**: Extend result dictionaries with additional measurements