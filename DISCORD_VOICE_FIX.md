# Discord Voice Connection Fix for VPS

## Problem
Discord voice connections fail on VPS deployments because UDP ports 50000-65535 are not configured. This causes:
- WebSocket error 4006 "Session no longer valid"
- Voice connections that immediately disconnect
- YouTube audio that won't play despite everything else working

## Root Cause
Discord voice requires:
- **TCP port 443**: For WebSocket control connection ✅ (already working)
- **UDP ports 50000-65535**: For RTP audio streaming ❌ (was missing)

## Solution

### 1. Docker Configuration (Already Fixed)
The `docker-compose.yml` now includes:
```yaml
ports:
  - "8080:8080"  # Health check and metrics port
  - "50000-65535:50000-65535/udp"  # Discord voice RTP audio streaming
```

### 2. VPS Firewall Configuration
Run the provided script on your VPS:
```bash
sudo ./scripts/fix-discord-voice-udp.sh
```

Or manually configure:
```bash
# Allow Discord voice UDP ports
sudo ufw allow 50000:65535/udp

# Verify the rule was added
sudo ufw status | grep udp
```

### 3. Apply Changes
```bash
# Pull the latest changes
cd ~/Robustty
git pull

# Restart with new port configuration
docker-compose down
docker-compose up -d
```

### 4. Test Voice Connection
1. Join a Discord voice channel
2. Use command: `!play never gonna give you up`
3. Audio should now work!

## Troubleshooting

### Check if UDP ports are accessible:
```bash
# Inside the container
docker-compose exec robustty netstat -tuln | grep udp

# From host
sudo netstat -tuln | grep udp
```

### Monitor voice connections:
```bash
# Check bot logs
docker-compose logs -f robustty | grep -E "(voice|Voice|4006)"

# Use Discord commands
!voicehealth
!voicediag
```

### DigitalOcean Specific
DigitalOcean droplets have strict firewall defaults. Ensure:
1. UFW is configured with the UDP rule
2. No cloud firewall is blocking UDP traffic
3. The droplet's network settings allow UDP

## Why This Works
1. Bot connects to Discord (TCP) ✅
2. Discord assigns voice server ✅
3. Bot opens UDP port for audio ✅ (now fixed)
4. Audio streams over UDP ✅
5. YouTube audio plays in voice channel! 🎉