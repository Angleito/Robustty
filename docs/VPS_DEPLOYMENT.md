# VPS Deployment Guide for Robustty

This guide covers deploying Robustty on an Ubuntu VPS with automated cookie syncing from your macOS development machine.

## Architecture Overview

- **macOS**: Runs Docker container that extracts cookies from Brave browser
- **Ubuntu VPS**: Runs the Discord bot with synced cookies
- **Sync Method**: SSH/rsync for secure, efficient file transfer

## Prerequisites

- Ubuntu 22.04 LTS VPS (DigitalOcean, Vultr, Linode, etc.)
- Minimum 2 vCPU, 4GB RAM
- Docker and Docker Compose installed on both machines
- SSH access to VPS

## Step 1: VPS Initial Setup

### 1.1 Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install Docker
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose -y
```

### 1.3 Create Project Structure
```bash
# Create directories
sudo mkdir -p /opt/robustty/cookies
sudo chown -R $USER:$USER /opt/robustty

# Clone repository
cd /opt
git clone https://github.com/yourusername/robustty.git
cd robustty
```

### 1.4 Configure Firewall
```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow Discord voice ports (if using bridge network)
sudo ufw allow 50000:65535/udp

# Enable firewall
sudo ufw enable
```

## Step 2: macOS Setup

### 2.1 Generate SSH Key
```bash
# Generate dedicated key for cookie sync
ssh-keygen -t ed25519 -f ~/.ssh/robustty_vps -C "robustty-cookie-sync"

# Copy to VPS
ssh-copy-id -i ~/.ssh/robustty_vps.pub your-username@your-vps-ip

# Test connection
ssh -i ~/.ssh/robustty_vps your-username@your-vps-ip
```

### 2.2 Configure Environment
```bash
# Copy and edit .env file
cp .env.example .env

# Add VPS configuration
echo "VPS_HOST=your-vps-ip" >> .env
echo "VPS_USER=your-username" >> .env
echo "SSH_KEY=$HOME/.ssh/robustty_vps" >> .env
echo "VPS_COOKIE_DIR=/opt/robustty/cookies" >> .env
```

### 2.3 Test Cookie Sync
```bash
# Run sync script manually
./scripts/sync-cookies-to-vps.sh

# Check output for any errors
```

### 2.4 Setup Automated Sync
```bash
# Add to crontab
crontab -e

# Add these lines:
# Sync cookies every 2 hours
0 */2 * * * /path/to/robustty/scripts/sync-cookies-to-vps.sh >> /var/log/robustty-cookie-sync.log 2>&1

# Sync on system startup (2 minute delay)
@reboot sleep 120 && /path/to/robustty/scripts/sync-cookies-to-vps.sh
```

## Step 3: VPS Bot Configuration

### 3.1 Setup Environment
```bash
cd /opt/robustty

# Copy environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

Required variables:
```bash
DISCORD_TOKEN=your_discord_bot_token
YOUTUBE_API_KEY=your_youtube_api_key
APIFY_API_KEY=your_apify_key
```

### 3.2 Deploy with Docker Compose
```bash
# Use VPS-specific compose file
docker-compose -f docker-compose.vps.yml up -d

# Check logs
docker-compose -f docker-compose.vps.yml logs -f
```

### 3.3 Setup Cookie Monitoring
```bash
# Add monitoring to crontab
crontab -e

# Check cookie freshness every hour
0 * * * * /opt/robustty/scripts/check-cookie-sync.sh
```

## Step 4: West Coast Optimization

### 4.1 Choose West Coast VPS Location
- DigitalOcean: San Francisco (SFO3)
- Vultr: Los Angeles, Seattle
- Linode: Fremont (California)

### 4.2 DNS Optimization
```bash
# Use Cloudflare DNS
sudo nano /etc/systemd/resolved.conf

# Add:
[Resolve]
DNS=1.1.1.1
FallbackDNS=1.0.0.1
```

### 4.3 Network Tuning
```bash
# Optimize for Discord voice
sudo nano /etc/sysctl.conf

# Add these lines:
net.core.rmem_max = 26214400
net.core.wmem_max = 26214400
net.ipv4.udp_mem = 102400 873800 16777216
net.ipv4.tcp_fastopen = 3

# Apply changes
sudo sysctl -p
```

## Step 5: Monitoring & Maintenance

### 5.1 Setup Monitoring Stack (Optional)
```bash
# Create monitoring compose file
cat > docker-compose.monitoring.yml << 'EOF'
version: '3.8'

services:
  prometheus:
    image: prom/prometheus
    container_name: prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    ports:
      - "127.0.0.1:9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana
    container_name: grafana
    ports:
      - "127.0.0.1:3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    restart: unless-stopped

volumes:
  prometheus-data:
  grafana-data:
EOF

# Start monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

### 5.2 Setup Nginx Reverse Proxy
```bash
# Install Nginx
sudo apt install nginx -y

# Create config
sudo nano /etc/nginx/sites-available/robustty

# Add configuration for metrics access
server {
    listen 80;
    server_name metrics.your-domain.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/robustty /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5.3 Log Rotation
```bash
# Create logrotate config
sudo nano /etc/logrotate.d/robustty

/opt/robustty/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    notifempty
    create 0640 $USER $USER
}
```

## Step 6: Troubleshooting

### Cookie Sync Issues
```bash
# Check sync logs on macOS
tail -f /var/log/robustty-cookie-sync.log

# Verify SSH connection
ssh -i ~/.ssh/robustty_vps -v your-username@your-vps-ip

# Check cookie freshness on VPS
/opt/robustty/scripts/check-cookie-sync.sh
```

### Bot Connection Issues
```bash
# Check bot logs
docker-compose -f docker-compose.vps.yml logs -f robustty

# Test Discord connectivity
docker exec robustty-bot python -c "import discord; print(discord.__version__)"

# Run 4006 diagnostics
docker exec robustty-bot python scripts/diagnose-discord-4006.py
```

### Performance Issues
```bash
# Check resource usage
docker stats

# Monitor network
sudo iftop

# Check disk space
df -h
```

## Security Best Practices

1. **SSH Hardening**
   - Use key-based authentication only
   - Disable root login
   - Change default SSH port
   - Use fail2ban

2. **Docker Security**
   - Run containers as non-root user
   - Use read-only mounts where possible
   - Limit container resources
   - Regular image updates

3. **Cookie Protection**
   - Encrypted transfer (SSH)
   - Read-only mount in container
   - Regular rotation (2-hour sync)
   - Monitoring for freshness

## Backup Strategy

```bash
# Backup script
cat > /opt/robustty/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backup/robustty"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/robustty_$DATE.tar.gz \
  --exclude='logs/*' \
  --exclude='data/cookies/*' \
  /opt/robustty/

# Keep only last 7 days
find $BACKUP_DIR -name "robustty_*.tar.gz" -mtime +7 -delete
EOF

chmod +x /opt/robustty/backup.sh

# Add to crontab (daily at 3 AM)
echo "0 3 * * * /opt/robustty/backup.sh" | crontab -
```

## Quick Reference

### Essential Commands
```bash
# Start bot (VPS)
cd /opt/robustty && docker-compose -f docker-compose.vps.yml up -d

# Stop bot (VPS)
docker-compose -f docker-compose.vps.yml down

# View logs
docker-compose -f docker-compose.vps.yml logs -f

# Sync cookies (macOS)
./scripts/sync-cookies-to-vps.sh

# Check cookie freshness (VPS)
./scripts/check-cookie-sync.sh

# Update bot
git pull && docker-compose -f docker-compose.vps.yml up -d --build
```

### File Locations
- **VPS Cookies**: `/opt/robustty/cookies/`
- **Bot Config**: `/opt/robustty/.env`
- **Logs**: `/opt/robustty/logs/`
- **macOS Sync Key**: `~/.ssh/robustty_vps`

## Support

For issues or questions:
1. Check bot logs: `docker-compose logs -f`
2. Run diagnostics: `./scripts/check-cookie-sync.sh`
3. Review this guide
4. Open an issue on GitHub