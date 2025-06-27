# VPS Troubleshooting Guide for Robustty Bot

This guide documents common VPS networking issues encountered when deploying the Robustty Discord bot and provides comprehensive solutions.

## Table of Contents
- [Common Issues](#common-issues)
- [Diagnostic Tools](#diagnostic-tools)
- [Step-by-Step Fixes](#step-by-step-fixes)
- [VPS Provider Specific Fixes](#vps-provider-specific-fixes)
- [Docker Networking Best Practices](#docker-networking-best-practices)

## Common Issues

### 1. Docker Container Cannot Reach External Services
**Symptoms:**
- Bot connects to Discord but fails to join voice channels
- Platform searches timeout (YouTube, Rumble, Odysee, PeerTube)
- DNS resolution fails inside containers
- `urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`

**Root Causes:**
- Docker bridge network misconfiguration
- IPTables rules blocking outbound traffic
- DNS not properly configured for containers
- MTU mismatch between Docker bridge and host network

### 2. Discord Voice Connection Failures
**Symptoms:**
- Bot joins voice channel but immediately disconnects
- "Failed to connect to voice channel" errors
- WebSocket connection timeouts

**Root Causes:**
- UDP ports blocked by firewall
- NAT/masquerading not configured
- Discord voice server regions blocked

### 3. Platform API Timeouts
**Symptoms:**
- Odysee searches timeout after 30+ seconds
- PeerTube instance unreachable
- YouTube API calls fail intermittently

**Root Causes:**
- High network latency on VPS
- DNS resolution delays
- TCP buffer sizes too small

## Diagnostic Tools

### Running Network Diagnostics

```bash
# Full diagnostic scan
python3 scripts/diagnose-vps-network.py

# Verbose output with detailed information
python3 scripts/diagnose-vps-network.py --verbose

# JSON output for automation
python3 scripts/diagnose-vps-network.py --json > network-report.json
```

### What the Diagnostic Tool Checks:
1. **Docker Installation & Configuration**
   - Docker daemon status
   - Network driver configuration
   - Bridge network subnet

2. **IPTables Rules**
   - DOCKER-USER chain configuration
   - NAT masquerading rules
   - Firewall restrictions

3. **Container Connectivity**
   - DNS resolution from containers
   - Outbound HTTP/HTTPS
   - Discord API accessibility

4. **Network Performance**
   - MTU configuration
   - TCP buffer sizes
   - Connection tracking limits

5. **Platform Connectivity**
   - Discord voice servers
   - PeerTube instances
   - Odysee API endpoints

## Step-by-Step Fixes

### Quick Fix (Automated)

```bash
# Dry run to see what changes will be made
sudo ./scripts/fix-vps-network.sh --dry-run

# Apply all fixes automatically
sudo ./scripts/fix-vps-network.sh

# Force installation of missing components
sudo ./scripts/fix-vps-network.sh --force
```

### Manual Fixes

#### 1. Fix Docker DNS Configuration

```bash
# Create/update Docker daemon configuration
sudo nano /etc/docker/daemon.json
```

Add:
```json
{
  "dns": ["1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4"],
  "dns-opts": ["ndots:0"],
  "dns-search": []
}
```

```bash
# Restart Docker
sudo systemctl restart docker
```

#### 2. Fix IPTables Rules

```bash
# Add DOCKER-USER chain rule to allow all traffic
sudo iptables -I DOCKER-USER -j RETURN

# Ensure NAT masquerading for Docker
sudo iptables -t nat -A POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE

# Allow Docker bridge to external interface
sudo iptables -I FORWARD -i docker0 -o eth0 -j ACCEPT
sudo iptables -I FORWARD -i eth0 -o docker0 -m state --state ESTABLISHED,RELATED -j ACCEPT

# Save rules (Ubuntu/Debian)
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

#### 3. Fix MTU Issues

```bash
# Find Docker bridge interface
ip link show | grep docker

# Set MTU to 1500
sudo ip link set dev docker0 mtu 1500

# Make persistent by adding to Docker daemon.json
"mtu": 1500
```

#### 4. Fix System DNS

```bash
# Backup current configuration
sudo cp /etc/resolv.conf /etc/resolv.conf.backup

# Set reliable DNS servers
echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf
```

#### 5. Optimize Network Performance

```bash
# Increase TCP buffer sizes
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728
sudo sysctl -w net.ipv4.tcp_rmem='4096 87380 134217728'
sudo sysctl -w net.ipv4.tcp_wmem='4096 65536 134217728'

# Enable TCP fast open
sudo sysctl -w net.ipv4.tcp_fastopen=3

# Increase connection tracking
sudo sysctl -w net.netfilter.nf_conntrack_max=131072

# Make permanent
echo "net.core.rmem_max=134217728" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_max=134217728" | sudo tee -a /etc/sysctl.conf
```

## VPS Provider Specific Fixes

### DigitalOcean

```bash
# Disable firewall if causing issues
sudo ufw disable

# Or allow Docker traffic
sudo ufw allow from 172.16.0.0/12
sudo ufw reload
```

### Vultr

```bash
# Check for custom firewall rules
sudo iptables -L -n -v

# Vultr often requires explicit outbound rules
sudo iptables -A OUTPUT -j ACCEPT
```

### Linode

```bash
# Linode's network helper can interfere
# Disable it in Linode Manager under Configuration Profiles

# Fix IPv6 issues
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
```

### AWS EC2

```bash
# Check Security Groups in AWS Console
# Ensure outbound rules allow:
# - All traffic to 0.0.0.0/0
# - Or specific: HTTPS (443), HTTP (80), DNS (53)

# Fix source/destination check for NAT
# Disable in EC2 instance settings
```

### Hetzner Cloud

```bash
# Hetzner has strict DDoS protection
# May need to whitelist Discord IPs

# Add to firewall
sudo iptables -A INPUT -s 162.159.128.0/22 -j ACCEPT  # Discord
sudo iptables -A INPUT -s 66.22.196.0/22 -j ACCEPT    # Discord Voice
```

## Docker Networking Best Practices

### 1. Use Bridge Networks (Not Host)

```yaml
# docker-compose.yml
networks:
  robustty-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### 2. Configure DNS in Compose

```yaml
services:
  robustty:
    dns:
      - 1.1.1.1
      - 1.0.0.1
      - 8.8.8.8
```

### 3. Set Proper Health Checks

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### 4. Resource Limits

```yaml
deploy:
  resources:
    limits:
      memory: 2G
    reservations:
      memory: 512M
```

### 5. Logging Configuration

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

## Troubleshooting Commands

### Check Container Network

```bash
# Inspect network configuration
docker network inspect bridge

# Test DNS from container
docker exec robustty-bot nslookup discord.com

# Test outbound connectivity
docker exec robustty-bot curl -v https://discord.com/api/v10/gateway

# Check container logs
docker-compose logs -f robustty
```

### Monitor Network Traffic

```bash
# Watch network connections
sudo netstat -tuln | grep ESTABLISHED

# Monitor Docker bridge traffic
sudo tcpdump -i docker0 -n

# Check connection tracking
sudo conntrack -L
```

### Debug Voice Connection

```bash
# Test UDP connectivity (Discord voice uses UDP)
docker exec robustty-bot python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(5)
try:
    s.sendto(b'test', ('8.8.8.8', 53))
    print('UDP works')
except:
    print('UDP blocked')
"
```

## Emergency Recovery

If all else fails:

```bash
# 1. Stop all services
docker-compose down

# 2. Reset Docker networking
sudo systemctl stop docker
sudo ip link delete docker0
sudo systemctl start docker

# 3. Clear all iptables rules (CAUTION!)
sudo iptables -F
sudo iptables -X
sudo iptables -t nat -F
sudo iptables -t nat -X

# 4. Reboot VPS
sudo reboot

# 5. After reboot, run fix script
cd ~/robustty-bot
sudo ./scripts/fix-vps-network.sh --force
```

## Getting Help

If issues persist after trying these fixes:

1. Run diagnostics and save output:
   ```bash
   python3 scripts/diagnose-vps-network.py --json > diagnostic-report.json
   ```

2. Check provider-specific documentation for network restrictions

3. Contact VPS support with diagnostic report

4. Common questions for VPS support:
   - Are there any outbound traffic restrictions?
   - Is UDP traffic allowed?
   - Are there DDoS protection rules that might block Discord?
   - Can Docker containers access external DNS servers?

## Prevention

To avoid these issues in future deployments:

1. **Choose VPS carefully**: Some providers have restrictive default firewall rules
2. **Test early**: Run diagnostics immediately after VPS setup
3. **Document changes**: Keep track of any network modifications
4. **Monitor regularly**: Set up alerts for connectivity issues
5. **Keep backups**: Save working iptables rules and Docker configurations

Remember: VPS networking issues are common with Discord bots due to the combination of Docker networking, voice channel requirements (UDP), and various VPS provider restrictions. The diagnostic and fix tools provided should resolve most issues automatically.