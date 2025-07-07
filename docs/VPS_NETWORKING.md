# VPS Networking Configuration & Troubleshooting Guide

This guide provides comprehensive networking configuration and troubleshooting for deploying Robustty Discord Bot on VPS environments.

## Table of Contents

1. [Overview](#overview)
2. [VPS Provider-Specific Setup](#vps-provider-specific-setup)
3. [Docker Networking Configuration](#docker-networking-configuration)
4. [DNS Configuration](#dns-configuration)
5. [Firewall & Security Groups](#firewall--security-groups)
6. [Network Performance Optimization](#network-performance-optimization)
7. [Monitoring & Health Checks](#monitoring--health-checks)
8. [Troubleshooting](#troubleshooting)
9. [Emergency Recovery](#emergency-recovery)

## Overview

VPS networking for Discord bots requires careful configuration to ensure:
- Stable Discord gateway connections
- Reliable Redis connectivity
- Proper HTTP health check exposure
- DNS resolution reliability
- Network resilience and failover

### Key Network Components

- **Discord Gateway**: WSS connections on ports 443/80
- **Redis**: Internal container networking on port 6379
- **Health Checks**: HTTP server on port 8080
- **Voice Connections**: UDP connections on various ports
- **Platform APIs**: HTTPS connections to YouTube, Rumble, etc.

## VPS Provider-Specific Setup

### AWS EC2

#### Security Group Configuration
```bash
# Allow SSH (replace with your IP)
aws ec2 authorize-security-group-ingress --group-id sg-xxxxxxxx \
    --protocol tcp --port 22 --cidr YOUR_IP/32

# Allow health check port (internal monitoring)
aws ec2 authorize-security-group-ingress --group-id sg-xxxxxxxx \
    --protocol tcp --port 8080 --cidr 10.0.0.0/8

# Allow all outbound (for Discord/API connections)
aws ec2 authorize-security-group-egress --group-id sg-xxxxxxxx \
    --protocol all --port all --cidr 0.0.0.0/0
```

#### EC2 Instance Configuration
```bash
# Optimize network settings
echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_congestion_control = bbr' >> /etc/sysctl.conf
sysctl -p
```

### DigitalOcean Droplet

#### Firewall Setup
```bash
# Create firewall
doctl compute firewall create \
    --name robustty-firewall \
    --inbound-rules "protocol:tcp,ports:22,address:YOUR_IP" \
    --inbound-rules "protocol:tcp,ports:8080,address:10.0.0.0/8" \
    --outbound-rules "protocol:tcp,ports:all,address:0.0.0.0/0" \
    --outbound-rules "protocol:udp,ports:all,address:0.0.0.0/0"

# Apply to droplet
doctl compute firewall add-droplets FIREWALL_ID --droplet-ids DROPLET_ID
```

#### Network Optimization
```bash
# Enable BBR congestion control
echo 'net.core.default_qdisc=fq' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_congestion_control=bbr' >> /etc/sysctl.conf
sysctl -p
```

### Linode VPS

#### Cloud Firewall
```bash
# Create firewall rules
linode-cli firewalls rules-create FIREWALL_ID \
    --protocol TCP --ports 22 --addresses YOUR_IP/32 --action ACCEPT
linode-cli firewalls rules-create FIREWALL_ID \
    --protocol TCP --ports 8080 --addresses 192.168.0.0/16 --action ACCEPT
```

### Vultr VPS

#### Firewall Configuration
```bash
# Allow SSH and health checks
ufw allow from YOUR_IP to any port 22
ufw allow from 10.0.0.0/8 to any port 8080
ufw allow out 443
ufw allow out 80
ufw --force enable
```

### General VPS Setup

#### Network Interface Optimization
```bash
#!/bin/bash
# /etc/systemd/system/network-optimize.service

cat > /etc/systemd/system/network-optimize.service << 'EOF'
[Unit]
Description=Network Optimization for Discord Bot
After=network.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'echo 1 > /proc/sys/net/ipv4/tcp_tw_reuse'
ExecStart=/bin/bash -c 'echo 1 > /proc/sys/net/ipv4/tcp_fin_timeout'
ExecStart=/bin/bash -c 'echo 16384 65536 > /proc/sys/net/ipv4/ip_local_port_range'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl enable network-optimize
systemctl start network-optimize
```

## Docker Networking Configuration

### Bridge Network Optimization

Update `docker-compose.yml` with optimized networking (already configured for VPS):

```yaml
version: '3.8'

services:
  robustty:
    build:
      context: .
      dockerfile: Dockerfile.vps
    container_name: robustty-bot
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - REDIS_URL=redis://redis:6379
    networks:
      - robustty-network
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
    dns_search:
      - .
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  redis:
    image: redis:7-alpine
    container_name: robustty-redis
    restart: unless-stopped
    networks:
      - robustty-network
    sysctls:
      - net.core.somaxconn=65535
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 5s
      retries: 3

networks:
  robustty-network:
    driver: bridge
    driver_opts:
      com.docker.network.driver.mtu: 1500
    ipam:
      config:
        - subnet: 172.20.0.0/16
          gateway: 172.20.0.1

volumes:
  robustty-redis-data:
    driver: local
```

### Docker Daemon Configuration

Create `/etc/docker/daemon.json`:

```json
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-search": ["."],
  "mtu": 1500,
  "bip": "172.17.0.1/16",
  "default-address-pools": [
    {
      "base": "172.20.0.0/16",
      "size": 24
    }
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}
```

## DNS Configuration

### System DNS Resolution

Configure `/etc/systemd/resolved.conf`:

```ini
[Resolve]
DNS=8.8.8.8 8.8.4.4 1.1.1.1 1.0.0.1
FallbackDNS=208.67.222.222 208.67.220.220
Domains=~.
DNSSEC=no
DNSOverTLS=opportunistic
Cache=yes
DNSStubListener=yes
```

Restart systemd-resolved:
```bash
systemctl restart systemd-resolved
```

### Container DNS Configuration

Add to `docker-compose.yml`:

```yaml
services:
  robustty:
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
    dns_opt:
      - ndots:1
      - timeout:5
      - attempts:3
```

### DNS Validation Script

```bash
#!/bin/bash
# scripts/validate-dns.sh

echo "🔍 Validating DNS configuration..."

# Test system DNS
echo "Testing system DNS resolution..."
for domain in discord.com googleapis.com redis.io; do
    if nslookup $domain > /dev/null 2>&1; then
        echo "✅ $domain resolves"
    else
        echo "❌ $domain failed to resolve"
    fi
done

# Test container DNS
echo "Testing container DNS resolution..."
docker run --rm --dns=8.8.8.8 alpine nslookup discord.com

echo "DNS validation complete."
```

## Firewall & Security Groups

### UFW Configuration (Ubuntu/Debian)

```bash
#!/bin/bash
# scripts/setup-firewall.sh

# Reset UFW
ufw --force reset

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (replace YOUR_IP with your actual IP)
ufw allow from YOUR_IP to any port 22

# Allow health check port (internal only)
ufw allow from 10.0.0.0/8 to any port 8080
ufw allow from 172.16.0.0/12 to any port 8080
ufw allow from 192.168.0.0/16 to any port 8080

# Allow Docker bridge network
ufw allow from 172.17.0.0/16
ufw allow from 172.20.0.0/16

# Discord and API connections (outbound)
ufw allow out 443
ufw allow out 80
ufw allow out 53

# Enable firewall
ufw --force enable

echo "Firewall configured successfully"
```

### iptables Configuration

```bash
#!/bin/bash
# scripts/setup-iptables.sh

# Flush existing rules
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X

# Default policies
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow SSH (replace YOUR_IP)
iptables -A INPUT -p tcp --dport 22 -s YOUR_IP -j ACCEPT

# Allow health check port (internal)
iptables -A INPUT -p tcp --dport 8080 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -s 172.16.0.0/12 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -s 192.168.0.0/16 -j ACCEPT

# Allow Docker networks
iptables -A INPUT -s 172.17.0.0/16 -j ACCEPT
iptables -A INPUT -s 172.20.0.0/16 -j ACCEPT

# Save rules
iptables-save > /etc/iptables/rules.v4
```

## Network Performance Optimization

### Kernel Parameters

Add to `/etc/sysctl.conf`:

```ini
# Network performance optimization
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.rmem_default = 262144
net.core.wmem_default = 262144
net.core.netdev_max_backlog = 5000
net.core.somaxconn = 65535

# TCP optimization
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_probes = 3
net.ipv4.tcp_keepalive_intvl = 15

# IP optimization
net.ipv4.ip_local_port_range = 16384 65535
net.ipv4.tcp_no_metrics_save = 1
net.ipv4.tcp_moderate_rcvbuf = 1

# Apply settings
sysctl -p
```

### Docker Container Limits

Update `docker-compose.yml`:

```yaml
services:
  robustty:
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
      nproc:
        soft: 65536
        hard: 65536
    sysctls:
      - net.core.somaxconn=65535
      - net.ipv4.tcp_keepalive_time=600
```

## Monitoring & Health Checks

### Network Monitoring Script

```bash
#!/bin/bash
# scripts/monitor-network.sh

LOG_FILE="/var/log/robustty-network.log"

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check Discord connectivity
check_discord() {
    if curl -s --max-time 10 https://discord.com/api/v10/gateway > /dev/null; then
        log_message "✅ Discord API accessible"
        return 0
    else
        log_message "❌ Discord API unreachable"
        return 1
    fi
}

# Check Redis connectivity
check_redis() {
    if docker exec robustty-redis redis-cli ping > /dev/null 2>&1; then
        log_message "✅ Redis accessible"
        return 0
    else
        log_message "❌ Redis unreachable"
        return 1
    fi
}

# Check bot health
check_bot_health() {
    if curl -s --max-time 5 http://localhost:8080/health > /dev/null; then
        log_message "✅ Bot health check passed"
        return 0
    else
        log_message "❌ Bot health check failed"
        return 1
    fi
}

# Check DNS resolution
check_dns() {
    local failed=0
    for domain in discord.com googleapis.com; do
        if ! nslookup "$domain" > /dev/null 2>&1; then
            log_message "❌ DNS resolution failed for $domain"
            failed=1
        fi
    done
    
    if [ $failed -eq 0 ]; then
        log_message "✅ DNS resolution working"
    fi
    return $failed
}

# Main monitoring loop
log_message "🔍 Starting network monitoring..."

while true; do
    check_discord
    check_redis
    check_bot_health
    check_dns
    
    # Check if any service is failing
    if ! check_discord || ! check_redis || ! check_bot_health; then
        log_message "⚠️  Service degradation detected, checking recovery..."
        
        # Wait and recheck
        sleep 30
        if ! check_bot_health; then
            log_message "🔄 Attempting service restart..."
            docker-compose restart robustty
        fi
    fi
    
    sleep 60
done
```

### Health Check Endpoint

Add to bot code (`src/services/health_monitor.py`):

```python
from aiohttp import web
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/network', self.network_status)
    
    async def health_check(self, request):
        """Basic health check endpoint"""
        status = {
            'status': 'healthy',
            'timestamp': asyncio.get_event_loop().time(),
            'bot_ready': self.bot.is_ready() if self.bot else False,
        }
        
        return web.json_response(status)
    
    async def network_status(self, request):
        """Detailed network status endpoint"""
        from ..utils.network_resilience import get_resilience_manager
        
        manager = get_resilience_manager()
        status = manager.get_all_status()
        
        return web.json_response(status)
    
    async def start_server(self, host='0.0.0.0', port=8080):
        """Start the health check server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        logger.info(f"Health check server started on {host}:{port}")
```

## Troubleshooting

### Common Network Issues

#### 1. Discord Gateway Connection Failures

**Symptoms:**
- Bot frequently disconnects
- "Gateway connection error" messages
- Intermittent voice connection issues

**Diagnosis:**
```bash
# Check Discord API connectivity
curl -v https://discord.com/api/v10/gateway

# Check DNS resolution
nslookup discord.com
nslookup gateway.discord.gg

# Check SSL/TLS
openssl s_client -connect discord.com:443 -verify_return_error
```

**Solutions:**
1. **DNS Issues:**
   ```bash
   # Update DNS servers
   echo "nameserver 8.8.8.8" > /etc/resolv.conf
   echo "nameserver 8.8.4.4" >> /etc/resolv.conf
   systemctl restart systemd-resolved
   ```

2. **Firewall Blocking:**
   ```bash
   # Allow HTTPS outbound
   ufw allow out 443
   ufw allow out 80
   ```

3. **MTU Issues:**
   ```bash
   # Test MTU size
   ping -M do -s 1472 discord.com
   
   # Adjust if needed
   ip link set dev eth0 mtu 1450
   ```

#### 2. Redis Connection Failures

**Symptoms:**
- Cache misses
- "Redis connection refused" errors
- Bot restart required frequently

**Diagnosis:**
```bash
# Check Redis container
docker exec robustty-redis redis-cli ping

# Check network connectivity
docker exec robustty-bot ping redis

# Check Redis logs
docker logs robustty-redis
```

**Solutions:**
1. **Container Networking:**
   ```bash
   # Recreate network
   docker-compose down
   docker network prune
   docker-compose up -d
   ```

2. **Redis Configuration:**
   ```bash
   # Check Redis config
   docker exec robustty-redis redis-cli config get "*"
   
   # Restart Redis
   docker-compose restart redis
   ```

#### 3. DNS Resolution Problems

**Symptoms:**
- Platform API failures
- Intermittent connection issues
- Slow response times

**Diagnosis:**
```bash
# Test DNS from container
docker exec robustty-bot nslookup discord.com

# Check DNS servers
cat /etc/resolv.conf

# Test different DNS servers
nslookup discord.com 8.8.8.8
nslookup discord.com 1.1.1.1
```

**Solutions:**
1. **Update DNS Configuration:**
   ```bash
   # System DNS
   echo "DNS=8.8.8.8 8.8.4.4 1.1.1.1" >> /etc/systemd/resolved.conf
   systemctl restart systemd-resolved
   ```

2. **Container DNS:**
   ```yaml
   # docker-compose.yml
   services:
     robustty:
       dns:
         - 8.8.8.8
         - 8.8.4.4
   ```

#### 4. Port Conflicts

**Symptoms:**
- "Port already in use" errors
- Health check failures
- Cannot start containers

**Diagnosis:**
```bash
# Check port usage
netstat -tulpn | grep :8080
lsof -i :8080

# Check Docker port mappings
docker ps
```

**Solutions:**
```bash
# Kill process using port
sudo fuser -k 8080/tcp

# Use different port
# Update docker-compose.yml port mapping
```

### Network Performance Issues

#### 1. High Latency

**Diagnosis:**
```bash
# Test latency to Discord
ping discord.com
traceroute discord.com

# Test from container
docker exec robustty-bot ping discord.com
```

**Solutions:**
```bash
# Optimize kernel parameters
echo 'net.ipv4.tcp_congestion_control = bbr' >> /etc/sysctl.conf
sysctl -p

# Optimize Docker networking
docker network create --driver bridge --opt com.docker.network.driver.mtu=1500 robustty-network
```

#### 2. Connection Timeouts

**Diagnosis:**
```bash
# Check timeout settings
curl -w "@curl-format.txt" -o /dev/null -s https://discord.com/api/v10/gateway

# Monitor connections
ss -tuln
```

**Solutions:**
```bash
# Increase timeout values in bot configuration
# Update network_resilience.py timeout settings
# Optimize TCP keep-alive
echo 'net.ipv4.tcp_keepalive_time = 600' >> /etc/sysctl.conf
```

### Advanced Diagnostics

#### Network Diagnostic Script

```bash
#!/bin/bash
# scripts/network-diagnostics.sh

echo "🔍 Robustty Network Diagnostics"
echo "================================="

# System information
echo "📋 System Information:"
echo "OS: $(uname -a)"
echo "Network interfaces:"
ip addr show
echo ""

# DNS Configuration
echo "🌐 DNS Configuration:"
echo "System DNS:"
cat /etc/resolv.conf
echo "systemd-resolved status:"
systemd-resolve --status
echo ""

# Port Status
echo "🔌 Port Status:"
echo "Listening ports:"
netstat -tulpn | grep LISTEN
echo "Docker port mappings:"
docker ps --format "table {{.Names}}\t{{.Ports}}"
echo ""

# Container Networking
echo "🐳 Container Networking:"
echo "Docker networks:"
docker network ls
echo "Container connectivity:"
if docker exec robustty-bot ping -c 3 redis; then
    echo "✅ Bot can reach Redis"
else
    echo "❌ Bot cannot reach Redis"
fi
echo ""

# External Connectivity
echo "🌍 External Connectivity:"
services=("discord.com" "googleapis.com" "apify.com")
for service in "${services[@]}"; do
    if curl -s --max-time 10 "https://$service" > /dev/null; then
        echo "✅ $service accessible"
    else
        echo "❌ $service unreachable"
    fi
done
echo ""

# Performance Metrics
echo "📊 Performance Metrics:"
echo "Network statistics:"
cat /proc/net/dev
echo "TCP statistics:"
cat /proc/net/snmp | grep Tcp
echo ""

# Bot Health
echo "🤖 Bot Health:"
if curl -s --max-time 5 http://localhost:8080/health > /dev/null; then
    echo "✅ Bot health check passed"
    curl -s http://localhost:8080/network | jq . 2>/dev/null || echo "Network status unavailable"
else
    echo "❌ Bot health check failed"
fi
echo ""

echo "Diagnostics complete. Check logs at /var/log/robustty-network.log"
```

## Emergency Recovery

### Service Recovery Procedures

#### 1. Complete Network Failure

```bash
#!/bin/bash
# Emergency network recovery

echo "🚨 Emergency Network Recovery"

# Stop all services
docker-compose down

# Reset Docker networking
docker network prune -f
docker system prune -f

# Reset system networking
systemctl restart systemd-networkd
systemctl restart systemd-resolved

# Restart Docker
systemctl restart docker

# Restart services
docker-compose up -d

echo "✅ Network recovery attempted"
```

#### 2. DNS Recovery

```bash
#!/bin/bash
# DNS recovery script

echo "🔧 DNS Recovery"

# Flush DNS cache
systemctl flush-dns
systemd-resolve --flush-caches

# Reset DNS configuration
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf

# Restart DNS services
systemctl restart systemd-resolved

# Test DNS
nslookup discord.com

echo "DNS recovery complete"
```

#### 3. Container Recovery

```bash
#!/bin/bash
# Container recovery script

echo "🔄 Container Recovery"

# Stop containers
docker-compose down

# Remove containers and volumes
docker-compose rm -f
docker volume prune -f

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

echo "Container recovery complete"
```

### Monitoring and Alerting

#### Log Monitoring

```bash
#!/bin/bash
# Log monitoring for network issues

tail -f /var/log/robustty-network.log | while read line; do
    if echo "$line" | grep -q "❌"; then
        echo "ALERT: Network issue detected - $line"
        # Send alert (webhook, email, etc.)
        curl -X POST "$WEBHOOK_URL" -d "{\"text\":\"Robustty Network Alert: $line\"}"
    fi
done
```

#### Automated Recovery

```bash
#!/bin/bash
# Automated recovery service

while true; do
    # Check bot health
    if ! curl -s --max-time 10 http://localhost:8080/health > /dev/null; then
        echo "$(date) - Health check failed, attempting recovery"
        
        # Try simple restart first
        docker-compose restart robustty
        sleep 30
        
        # If still failing, full recovery
        if ! curl -s --max-time 10 http://localhost:8080/health > /dev/null; then
            echo "$(date) - Full recovery needed"
            /opt/robustty/scripts/emergency-recovery.sh
        fi
    fi
    
    sleep 60
done
```

## Quick Start Guide

### For First-Time VPS Setup

1. **Run Network Validation**
   ```bash
   # On your VPS, run the network validation script
   ./scripts/validate-network.sh
   ```

2. **Setup VPS Networking (if validation fails)**
   ```bash
   # Automatic setup (recommended)
   sudo ./scripts/setup-vps-networking.sh
   
   # Manual setup (see provider-specific sections above)
   ```

3. **Deploy the Bot**
   ```bash
   # From your local machine
   ./deploy-vps.sh your-vps-ip ubuntu auto
   ```

4. **Monitor and Troubleshoot**
   ```bash
   # Run diagnostics if issues occur
   /opt/robustty-network-diagnostics.sh
   
   # Emergency recovery if needed
   /opt/robustty-emergency-recovery.sh
   ```

### Key Scripts and Tools

- **`scripts/validate-network.sh`** - Comprehensive network validation
- **`scripts/setup-vps-networking.sh`** - Automated VPS network setup
- **`deploy-vps.sh`** - Enhanced deployment with network validation
- **`/opt/robustty-network-diagnostics.sh`** - System diagnostics (created during setup)
- **`/opt/robustty-emergency-recovery.sh`** - Emergency recovery (created during setup)

### Documentation References

- **[VPS Troubleshooting Flowcharts](VPS_TROUBLESHOOTING_FLOWCHARTS.md)** - Step-by-step troubleshooting
- **[Main Documentation](VPS_NETWORKING.md)** - This comprehensive guide
- **[Installation Guide](INSTALLATION.md)** - General installation instructions

## Summary

This guide provides comprehensive networking configuration for VPS deployment of Robustty Discord Bot, including:

- **Provider-specific setup instructions** for AWS, DigitalOcean, Linode, Vultr
- **Docker networking optimization** with custom bridge networks
- **DNS configuration and troubleshooting** with multiple fallback servers
- **Firewall and security configuration** for UFW and iptables
- **Performance optimization techniques** for kernel and Docker
- **Monitoring and health checking** with automated scripts
- **Troubleshooting procedures** with flowcharts and checklists
- **Emergency recovery scripts** for critical situations
- **Automated setup and validation tools** for streamlined deployment

### Support and Troubleshooting

1. **First, run diagnostics:**
   ```bash
   /opt/robustty-network-diagnostics.sh
   ```

2. **Check logs:**
   ```bash
   # Network monitoring logs
   tail -f /var/log/robustty-network-monitor.log
   
   # Bot logs
   docker logs robustty-bot --tail 50
   
   # Redis logs
   docker logs robustty-redis --tail 50
   ```

3. **Use troubleshooting guides:**
   - See [VPS_TROUBLESHOOTING_FLOWCHARTS.md](VPS_TROUBLESHOOTING_FLOWCHARTS.md) for step-by-step procedures
   - Follow the flowcharts for specific error patterns
   - Use the automated recovery scripts when needed

4. **Get help:**
   - Check the comprehensive troubleshooting documentation
   - Review common error patterns and solutions
   - Use the emergency recovery procedures if needed

For additional support, check the logs at `/var/log/robustty-network*.log` and use the diagnostic scripts provided in this guide.