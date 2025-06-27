# VPS Troubleshooting Guide for Robustty Discord Bot

This guide addresses common VPS deployment issues that cause "Connection closed" errors and Discord voice WebSocket 4006 failures.

## 🚨 Quick Fix (TL;DR)

```bash
# On your VPS, run these commands:
sudo ./scripts/diagnose-vps-network.sh
sudo ./scripts/fix-vps-network.sh
docker-compose down && docker-compose up -d
```

## 🔍 Common Issues & Solutions

### 1. Discord Voice WebSocket Error 4006

**Symptoms:**
- `discord.errors.ConnectionClosed: Shard ID None WebSocket closed with 4006`
- Voice connections fail repeatedly
- Bot can connect to Discord but not join voice channels

**Causes:**
- VPS network instability affecting Discord voice servers
- Session invalidation due to connection drops
- Containerized environment networking issues

**Solutions:**
1. **Enable VPS Voice Optimizations:**
   ```bash
   export VPS_MODE=true
   docker-compose restart robustty
   ```

2. **Check Voice Connection Environment:**
   - Use `!voiceenv` command in Discord to see current settings
   - Use `!voicediag` to run diagnostics
   - Use `!voicehealth` to check connection status

3. **Manual Voice Connection Settings:**
   ```bash
   # In your .env file
   VOICE_ENVIRONMENT=vps
   VOICE_RETRY_ATTEMPTS=8
   VOICE_RETRY_DELAY=5
   ```

### 2. "Connection Closed" Errors on All Platforms

**Symptoms:**
- All platforms (PeerTube, Odysee, Rumble) show "Connection closed"
- YouTube might work but others fail
- Network timeouts across the board

**Root Cause:** Docker networking conflicts with VPS firewall rules

**Fix Steps:**
1. **Run Network Diagnostic:**
   ```bash
   sudo ./scripts/diagnose-vps-network.sh
   ```

2. **Apply Automatic Fix:**
   ```bash
   sudo ./scripts/fix-vps-network.sh
   ```

3. **Manual Fix (if automatic fails):**
   ```bash
   # Enable IP forwarding
   echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
   sysctl -p
   
   # Fix Docker iptables rules
   iptables -I DOCKER-USER -i docker0 -j ACCEPT
   iptables -I DOCKER-USER -o docker0 -j ACCEPT
   iptables -t nat -A POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE
   
   # Save rules
   iptables-save > /etc/iptables/rules.v4
   ```

### 3. Platform-Specific Issues

#### PeerTube Connectivity
**Issue:** All PeerTube instances failing
**Temporary Solution:** PeerTube is automatically disabled in VPS stability mode
**Re-enable:** Use `!enable-platform peertube` after fixing network

#### Odysee Timeouts
**Issue:** Consistent Odysee API timeouts
**Automatic Fix:** VPS mode increases timeouts automatically
**Manual Override:**
```bash
export ODYSEE_TIMEOUT_MULTIPLIER=2.0
docker-compose restart robustty
```

### 4. DNS Resolution Problems

**Symptoms:**
- "No answer for domain" errors
- Cannot resolve discord.com, googleapis.com
- DNS timeouts in containers

**Fix:**
1. **Update Docker DNS Configuration:**
   ```bash
   # Create /etc/docker/daemon.json
   sudo tee /etc/docker/daemon.json <<EOF
   {
     "dns": ["8.8.8.8", "1.1.1.1"],
     "mtu": 1450
   }
   EOF
   sudo systemctl restart docker
   ```

2. **Update docker-compose.yml:**
   ```yaml
   services:
     robustty:
       dns:
         - 8.8.8.8
         - 1.1.1.1
   ```

### 5. MTU Configuration Issues

**Symptoms:**
- Large packets dropped
- Intermittent connection failures
- "Connection reset by peer" errors

**Fix:**
```bash
# Set Docker MTU to 1450 (safe for most VPS)
sudo tee /etc/docker/daemon.json <<EOF
{
  "mtu": 1450
}
EOF
sudo systemctl restart docker
```

## 🌐 VPS Provider-Specific Fixes

### DigitalOcean
```bash
# DigitalOcean often requires explicit UFW configuration
sudo ufw allow out 53
sudo ufw allow out 80  
sudo ufw allow out 443
sudo ufw allow out 22/tcp
```

### Vultr
```bash
# Vultr may need bridge netfilter module
sudo modprobe br_netfilter
echo 'br_netfilter' >> /etc/modules-load.d/docker.conf
```

### Linode
```bash
# Linode may require specific iptables configuration
sudo iptables -I INPUT -i docker0 -j ACCEPT
sudo iptables-save > /etc/iptables/rules.v4
```

### AWS EC2
```bash
# AWS requires security group configuration
# Add outbound rules for ports 80, 443, 53
# Also check VPC routing tables
```

### Hetzner
```bash
# Hetzner may need specific network interface configuration
sudo ip route add default via $(ip route | grep default | head -1 | awk '{print $3}')
```

## 🔧 Manual Debugging Steps

### 1. Test Container Networking
```bash
# Test basic connectivity
docker run --rm alpine ping -c 3 8.8.8.8

# Test DNS resolution
docker run --rm alpine nslookup discord.com

# Test HTTPS connectivity
docker run --rm alpine wget -q --timeout=10 https://discord.com/api/v10/gateway -O -
```

### 2. Check iptables Rules
```bash
# View current rules
sudo iptables -L -n -v
sudo iptables -t nat -L -n -v

# Check Docker chains
sudo iptables -L DOCKER-USER -n -v
sudo iptables -t nat -L DOCKER -n -v
```

### 3. Monitor Network Traffic
```bash
# Watch iptables counters
sudo watch -n 1 'iptables -L DOCKER-USER -n -v'

# Monitor container traffic
sudo tcpdump -i docker0

# Check Docker logs
sudo journalctl -u docker.service -f
```

### 4. Test Discord Voice Connectivity
```bash
# Test Discord voice regions
for region in us-west us-east us-central europe asia; do
  echo "Testing ${region}..."
  timeout 5 bash -c "</dev/tcp/gateway-${region}-1.discord.gg/443" 2>/dev/null && echo "✓ ${region} OK" || echo "✗ ${region} FAIL"
done
```

## 🚑 Emergency Recovery

If the bot stops working completely:

1. **Reset Docker Networking:**
   ```bash
   sudo systemctl stop docker
   sudo iptables -t nat -F DOCKER
   sudo iptables -t filter -F DOCKER
   sudo iptables -t filter -F DOCKER-USER
   sudo systemctl start docker
   ```

2. **Use Host Networking (temporary):**
   ```yaml
   # In docker-compose.yml
   services:
     robustty:
       network_mode: host
   ```

3. **Minimal Configuration:**
   ```bash
   # Disable problematic platforms
   export PEERTUBE_ENABLED=false
   export ODYSEE_ENABLED=false
   docker-compose restart robustty
   ```

## 📊 Health Monitoring

### Bot Commands
- `!voicehealth` - Check voice connection status
- `!voicediag` - Run voice diagnostics  
- `!platform-stability` - Check platform health
- `!enable-platform <name>` - Re-enable disabled platforms

### System Monitoring
```bash
# Check Docker service
sudo systemctl status docker

# Monitor bot logs
docker-compose logs -f robustty

# Check network connectivity
./scripts/diagnose-vps-network.sh
```

## 📞 Getting Help

If issues persist after trying these solutions:

1. **Run Full Diagnostic:**
   ```bash
   sudo ./scripts/diagnose-vps-network.sh > diagnostic-report.txt
   ```

2. **Collect System Information:**
   ```bash
   echo "System Info:" > system-info.txt
   uname -a >> system-info.txt
   docker version >> system-info.txt
   docker-compose version >> system-info.txt
   ip addr show >> system-info.txt
   ```

3. **Check Bot Logs:**
   ```bash
   docker-compose logs robustty > bot-logs.txt
   ```

4. **VPS Provider Support:**
   - Check if your VPS provider blocks specific ports
   - Verify no bandwidth restrictions
   - Confirm Docker is allowed on your plan

## 🎯 Prevention

### Regular Maintenance
```bash
# Weekly network health check
sudo ./scripts/diagnose-vps-network.sh

# Monthly iptables rule cleanup
sudo iptables -t nat -F DOCKER
sudo systemctl restart docker

# Keep Docker updated
sudo apt update && sudo apt upgrade docker-ce
```

### Monitoring Setup
```bash
# Add to crontab for automated checks
0 6 * * * /path/to/scripts/diagnose-vps-network.sh
```

This guide should resolve most VPS deployment issues. The key is identifying whether the problem is networking (most common), DNS resolution, or Discord-specific connectivity.