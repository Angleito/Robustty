# VPS Music Bot Diagnostic Quick Start

## 🚀 Quick Diagnosis

Run this single command on your VPS to diagnose all issues:

```bash
cd ~/Robustty  # or your bot directory
sudo python3 scripts/diagnose-vps-music-bot.py
```

For automatic fixes:
```bash
sudo python3 scripts/diagnose-vps-music-bot.py --fix
```

## 📋 What It Tests

### 1. **Discord Connection**
- ✅ Token validation
- ✅ API authentication
- ✅ Gateway connectivity
- ✅ WebSocket handshake

### 2. **VPS Network**
- ✅ DNS resolution (Discord, YouTube, etc.)
- ✅ Outbound ports (443, 80)
- ✅ Firewall rules
- ✅ MTU size
- ✅ IPv6 connectivity

### 3. **Voice Connection**
- ✅ UDP ports 50000-50010
- ✅ Docker port mappings
- ✅ Voice server connectivity

### 4. **Audio Streaming**
- ✅ FFmpeg installation
- ✅ yt-dlp/youtube-dl
- ✅ API keys (YouTube, Rumble)
- ✅ Cookie files

### 5. **System Health**
- ✅ Time synchronization
- ✅ Memory usage
- ✅ Disk space
- ✅ Docker status
- ✅ Redis connectivity

### 6. **VPS-Specific**
- ✅ Provider detection
- ✅ IP reputation
- ✅ Known provider issues

## 🔧 Common Fixes

### Discord Token Issues
```bash
# Update your .env file
nano .env
# Set: DISCORD_TOKEN=your_actual_token_here
```

### Network Issues
```bash
# Fix DNS
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf

# Open firewall ports
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp
sudo ufw allow 50000:50010/udp
```

### Missing Dependencies
```bash
# Install FFmpeg
sudo apt-get update && sudo apt-get install -y ffmpeg

# Install yt-dlp
pip install -U yt-dlp
```

### Time Sync Issues
```bash
sudo timedatectl set-ntp true
```

## 📊 Understanding Results

### ✅ Green = Good
No action needed

### ⚠️ Yellow = Warning
May work but could cause issues

### ❌ Red = Critical
Must fix for bot to work

## 📄 Report

After running, check `vps-diagnostic-report.txt` for a full report you can share when asking for help.

## 🆘 Still Having Issues?

1. Run the diagnostic tool
2. Apply automatic fixes
3. Share the diagnostic report
4. Check Docker logs: `docker-compose logs --tail=100 robustty`