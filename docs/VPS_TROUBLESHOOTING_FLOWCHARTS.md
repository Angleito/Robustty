# VPS Troubleshooting Flowcharts & Checklists

This document provides step-by-step troubleshooting flowcharts and checklists for common VPS networking and deployment issues with the Robustty Discord Bot.

## Table of Contents

1. [Quick Troubleshooting Checklist](#quick-troubleshooting-checklist)
2. [Bot Won't Start Flowchart](#bot-wont-start-flowchart)
3. [Discord Connection Issues](#discord-connection-issues)
4. [DNS Resolution Problems](#dns-resolution-problems)
5. [Container Networking Issues](#container-networking-issues)
6. [Performance Issues](#performance-issues)
7. [Emergency Recovery Procedures](#emergency-recovery-procedures)

## Quick Troubleshooting Checklist

### Pre-Deployment Checklist
- [ ] SSH access to VPS working
- [ ] VPS has sufficient resources (2GB+ RAM, 1GB+ disk space)
- [ ] DNS resolution working (`nslookup discord.com`)
- [ ] Outbound HTTPS allowed (port 443)
- [ ] Port 8080 available for health checks
- [ ] Docker and Docker Compose installed
- [ ] Environment variables configured in `.env`
- [ ] Cookies synced from local machine

### Post-Deployment Checklist
- [ ] Containers started successfully (`docker ps`)
- [ ] Health check endpoint responding (`curl localhost:8080/health`)
- [ ] Bot logged into Discord (check logs)
- [ ] Redis connection working
- [ ] Voice connections functional (if using voice features)

## Bot Won't Start Flowchart

```
🤖 Bot Won't Start
       |
       v
   Check Logs
   `docker logs robustty-bot`
       |
       |-- API Key Issues? -----> Verify .env file
       |                         Check DISCORD_TOKEN
       |                         Check API keys
       |
       |-- Import Errors? ------> Check Docker build
       |                         Verify requirements.txt
       |                         Rebuild container
       |
       |-- Network Errors? -----> Go to Discord Connection Issues
       |
       |-- Redis Errors? -------> Check Redis container
       |                         `docker logs robustty-redis`
       |                         Test Redis connection
       |
       |-- Permission Errors? --> Check file permissions
       |                         Check Docker socket access
       |                         Verify user groups
       |
       v
   Still failing?
       |
       v
   Emergency Recovery
   `/opt/robustty-emergency-recovery.sh`
```

## Discord Connection Issues

```
🎮 Discord Connection Problems
       |
       v
   Test Discord API Access
   `curl https://discord.com/api/v10/gateway`
       |
       |-- Success? -----------> Check Bot Token
       |                         Verify token in .env
       |                         Test token validity
       |
       |-- Timeout/Failed? -----> DNS Resolution Issues
                                 |
                                 v
                             Test DNS Resolution
                             `nslookup discord.com`
                                 |
                                 |-- DNS OK? -------> Firewall Blocking
                                 |                    Check outbound 443
                                 |                    Check UFW rules
                                 |                    Check cloud firewall
                                 |
                                 |-- DNS Failed? ---> Fix DNS Configuration
                                                     Update /etc/resolv.conf
                                                     Restart systemd-resolved
                                                     Check DNS servers
```

### Discord Connection Troubleshooting Steps

1. **Verify Discord API Access**
   ```bash
   curl -v https://discord.com/api/v10/gateway
   ```

2. **Check DNS Resolution**
   ```bash
   nslookup discord.com
   nslookup gateway.discord.gg
   ```

3. **Test SSL/TLS Connection**
   ```bash
   openssl s_client -connect discord.com:443 -verify_return_error
   ```

4. **Verify Bot Token**
   ```bash
   curl -H "Authorization: Bot YOUR_TOKEN" https://discord.com/api/v10/users/@me
   ```

5. **Check Container DNS**
   ```bash
   docker exec robustty-bot nslookup discord.com
   ```

## DNS Resolution Problems

```
🌐 DNS Resolution Failed
       |
       v
   Check System DNS
   `cat /etc/resolv.conf`
       |
       |-- No nameservers? -----> Add DNS Servers
       |                         echo "nameserver 8.8.8.8" >> /etc/resolv.conf
       |                         echo "nameserver 1.1.1.1" >> /etc/resolv.conf
       |
       |-- DNS servers exist? --> Test DNS Servers
       |                         `nslookup discord.com 8.8.8.8`
       |                         `nslookup discord.com 1.1.1.1`
       |
       v
   DNS servers working?
       |
       |-- Yes -----------------> Check systemd-resolved
       |                         `systemctl status systemd-resolved`
       |                         Restart if needed
       |
       |-- No ------------------> Network/Firewall Issue
                                 Check port 53 access
                                 Check VPS provider DNS
                                 Contact provider support
```

### DNS Troubleshooting Commands

```bash
# Quick DNS fix
sudo bash -c 'cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
EOF'

# Restart DNS services
sudo systemctl restart systemd-resolved

# Test DNS resolution
for domain in discord.com googleapis.com; do
    echo "Testing $domain:"
    nslookup $domain
done

# Check DNS from container
docker exec robustty-bot nslookup discord.com
```

## Container Networking Issues

```
🐳 Container Networking Problems
       |
       v
   Containers Running?
   `docker ps`
       |
       |-- No containers? ------> Start Services
       |                         `docker-compose up -d`
       |
       |-- Containers exist? ---> Test Inter-container Communication
       |                         `docker exec robustty-bot ping redis`
       |
       v
   Inter-container communication OK?
       |
       |-- Yes -----------------> Check External Access
       |                         Test health endpoint
       |                         Check port mappings
       |
       |-- No ------------------> Docker Network Issues
                                 |
                                 v
                             Check Docker Networks
                             `docker network ls`
                             `docker network inspect robustty-network`
                                 |
                                 v
                             Recreate Network
                             `docker-compose down`
                             `docker network prune`
                             `docker-compose up -d`
```

### Container Networking Diagnostics

```bash
# Check container status
docker ps -a

# Test inter-container connectivity
docker exec robustty-bot ping redis
docker exec robustty-bot nc -zv redis 6379

# Check Docker networks
docker network ls
docker network inspect robustty-network

# Check container logs
docker logs robustty-bot --tail 50
docker logs robustty-redis --tail 50

# Test health endpoint
curl -v http://localhost:8080/health
```

## Performance Issues

```
⚡ Performance Problems
       |
       v
   Check Resource Usage
   `docker stats`
       |
       |-- High CPU/Memory? ----> Scale Resources
       |                         Upgrade VPS plan
       |                         Optimize bot code
       |                         Adjust Docker limits
       |
       |-- Network Latency? ----> Test Network Performance
       |                         `ping discord.com`
       |                         `traceroute discord.com`
       |                         Check VPS location
       |
       |-- Slow Responses? -----> Check Redis Performance
                                 `docker exec robustty-redis redis-cli info`
                                 Check Redis memory usage
                                 Clear cache if needed
```

### Performance Diagnostics

```bash
# Check system resources
htop
df -h
free -h

# Check Docker resource usage
docker stats

# Test network performance
ping -c 10 discord.com
traceroute discord.com

# Check Redis performance
docker exec robustty-redis redis-cli info stats
docker exec robustty-redis redis-cli info memory

# Monitor bot performance
curl http://localhost:8080/network | jq .
```

## Emergency Recovery Procedures

### 1. Complete System Recovery

```bash
#!/bin/bash
# Emergency recovery script - run as root

echo "🚨 Starting emergency recovery..."

# Stop all services
docker-compose down || true

# Reset Docker
systemctl stop docker
rm -rf /var/lib/docker/containers/*
rm -rf /var/lib/docker/networks/*
systemctl start docker

# Reset networking
systemctl restart systemd-networkd
systemctl restart systemd-resolved

# Flush DNS
systemctl flush-dns || true
systemd-resolve --flush-caches || true

# Fix DNS
cat > /etc/resolv.conf << 'EOF'
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
EOF

# Restart services
docker-compose up -d --build

echo "✅ Emergency recovery completed"
```

### 2. Network-Only Recovery

```bash
#!/bin/bash
# Network recovery script

echo "🔧 Network recovery starting..."

# Restart network services
sudo systemctl restart systemd-networkd
sudo systemctl restart systemd-resolved

# Reset DNS
sudo systemd-resolve --flush-caches
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf

# Test connectivity
if curl -s --max-time 10 https://discord.com/api/v10/gateway > /dev/null; then
    echo "✅ Network recovery successful"
else
    echo "❌ Network issues persist"
fi
```

### 3. Service-Only Recovery

```bash
#!/bin/bash
# Service recovery script

echo "🔄 Service recovery starting..."

# Stop services gracefully
docker-compose down

# Clean up
docker system prune -f

# Restart services
docker-compose up -d

# Wait for services to start
sleep 30

# Test health
if curl -s http://localhost:8080/health > /dev/null; then
    echo "✅ Services recovered successfully"
else
    echo "❌ Service recovery failed"
fi
```

## Step-by-Step Troubleshooting Guide

### Issue: Bot Disconnects Frequently

**Step 1: Check Logs**
```bash
docker logs robustty-bot --tail 100 | grep -i "disconnect\|error\|timeout"
```

**Step 2: Test Network Stability**
```bash
ping -c 100 discord.com | tail -5
```

**Step 3: Check DNS Stability**
```bash
for i in {1..10}; do
    echo "Test $i:"
    nslookup discord.com
    sleep 5
done
```

**Step 4: Monitor Resource Usage**
```bash
docker stats robustty-bot
```

**Step 5: Check Bot Configuration**
```bash
docker exec robustty-bot cat /app/.env | grep -v TOKEN
```

### Issue: Voice Connections Fail

**Step 1: Check Voice Permissions**
- Verify bot has voice permissions in Discord server
- Check if bot is in a voice channel

**Step 2: Test UDP Connectivity**
```bash
# Test UDP connectivity (Discord voice uses UDP)
nc -u -z discord.gg 50000-65535
```

**Step 3: Check FFmpeg Installation**
```bash
docker exec robustty-bot ffmpeg -version
```

**Step 4: Monitor Voice Connection Logs**
```bash
docker logs robustty-bot | grep -i "voice\|audio\|ffmpeg"
```

### Issue: Slow Response Times

**Step 1: Check Redis Performance**
```bash
docker exec robustty-redis redis-cli --latency-history -i 1
```

**Step 2: Monitor Network Latency**
```bash
ping -c 20 discord.com | tail -1
```

**Step 3: Check System Load**
```bash
uptime
iostat 1 5
```

**Step 4: Optimize Cache**
```bash
# Clear Redis cache if needed
docker exec robustty-redis redis-cli FLUSHALL
```

## Automated Diagnostics Script

Create `/opt/robustty-full-diagnostics.sh`:

```bash
#!/bin/bash

echo "🔍 Robustty Full System Diagnostics"
echo "==================================="
date
echo ""

# System Health
echo "💻 System Health:"
echo "Uptime: $(uptime)"
echo "Memory: $(free -h | grep Mem)"
echo "Disk: $(df -h / | tail -1)"
echo ""

# Network Connectivity
echo "🌐 Network Connectivity:"
ping -c 3 discord.com > /dev/null && echo "✅ Discord reachable" || echo "❌ Discord unreachable"
ping -c 3 8.8.8.8 > /dev/null && echo "✅ Internet connectivity OK" || echo "❌ No internet"
echo "DNS servers: $(cat /etc/resolv.conf | grep nameserver)"
echo ""

# Docker Status
echo "🐳 Docker Status:"
docker --version
docker-compose --version
echo "Running containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Bot Health
echo "🤖 Bot Health:"
if curl -s http://localhost:8080/health > /dev/null; then
    echo "✅ Health check passed"
    curl -s http://localhost:8080/health | jq . 2>/dev/null || echo "Health data unavailable"
else
    echo "❌ Health check failed"
fi
echo ""

# Redis Status
echo "📊 Redis Status:"
if docker exec robustty-redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis responding"
    docker exec robustty-redis redis-cli info stats | grep -E "total_commands_processed|keyspace_hits|keyspace_misses"
else
    echo "❌ Redis not responding"
fi
echo ""

# Recent Logs
echo "📋 Recent Bot Logs (last 20 lines):"
docker logs robustty-bot --tail 20 2>&1 | head -20
echo ""

echo "Diagnostics complete. For detailed logs:"
echo "  Bot logs: docker logs robustty-bot"
echo "  Redis logs: docker logs robustty-redis"
echo "  System logs: journalctl -u docker"
```

Make it executable:
```bash
chmod +x /opt/robustty-full-diagnostics.sh
```

## Common Error Patterns and Solutions

### Error Pattern: "DNS resolution failed"
**Solution:**
```bash
# Add reliable DNS servers
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf
sudo systemctl restart systemd-resolved
```

### Error Pattern: "Connection timeout"
**Solution:**
```bash
# Check firewall rules
sudo ufw status
# Allow required ports
sudo ufw allow out 443
sudo ufw allow out 80
```

### Error Pattern: "Redis connection refused"
**Solution:**
```bash
# Restart Redis container
docker-compose restart redis
# Check Redis logs
docker logs robustty-redis
```

### Error Pattern: "Import error" or "Module not found"
**Solution:**
```bash
# Rebuild container
docker-compose build --no-cache robustty
docker-compose up -d
```

## Monitoring and Alerting Setup

### Basic Monitoring Script
```bash
#!/bin/bash
# /opt/robustty-monitor.sh

LOG_FILE="/var/log/robustty-monitor.log"
WEBHOOK_URL="YOUR_DISCORD_WEBHOOK_URL"  # Optional

check_service() {
    if ! curl -s --max-time 10 http://localhost:8080/health > /dev/null; then
        echo "$(date): Bot health check failed" | tee -a "$LOG_FILE"
        
        # Optional: Send Discord webhook alert
        if [[ -n "$WEBHOOK_URL" ]]; then
            curl -X POST "$WEBHOOK_URL" \
                -H "Content-Type: application/json" \
                -d '{"content":"🚨 Robustty bot health check failed!"}'
        fi
        
        # Attempt automatic recovery
        docker-compose -f /home/ubuntu/robustty-bot/docker-compose.yml restart robustty
        
        return 1
    fi
    return 0
}

# Run check
check_service
```

### Cron Job Setup
```bash
# Add to crontab: crontab -e
*/5 * * * * /opt/robustty-monitor.sh
```

This comprehensive troubleshooting guide provides flowcharts, checklists, and step-by-step procedures for resolving common VPS networking and deployment issues with the Robustty Discord Bot.