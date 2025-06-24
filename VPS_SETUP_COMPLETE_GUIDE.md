# 🚀 Complete VPS Setup Guide for Robustty with Automated Cookie Sync

This guide will walk you through setting up Robustty on a DigitalOcean VPS (or similar) with automated cookie syncing from your macOS machine.

## 📋 Prerequisites

- A VPS with Ubuntu 22.04 LTS (I recommend DigitalOcean, Vultr, or Linode)
- Your macOS machine with Robustty already running in Docker
- Basic familiarity with SSH and terminal commands

## 🎯 Overview

Your setup will work like this:
1. **macOS (Local)**: Extracts cookies from Brave browser every 2 hours
2. **Automated Sync**: SSH/rsync transfers cookies to VPS
3. **VPS (Remote)**: Runs the Discord bot with fresh cookies

---

## 📍 Step 1: Choose Your VPS

### Recommended West Coast Locations:
- **DigitalOcean**: San Francisco (SFO3)
- **Vultr**: Los Angeles or Seattle
- **Linode**: Fremont, CA

### VPS Specifications:
- **Minimum**: 2 vCPU, 4GB RAM, 50GB SSD
- **Recommended**: 4 vCPU, 8GB RAM, 80GB SSD
- **OS**: Ubuntu 22.04 LTS

---

## 🔧 Step 2: Initial VPS Setup

### 2.1 Connect to Your VPS
```bash
ssh root@your-vps-ip
```

### 2.2 Update System & Create User
```bash
# Update packages
apt update && apt upgrade -y

# Create a new user (replace 'robustty' with your preferred username)
adduser robustty

# Add to sudo group
usermod -aG sudo robustty

# Switch to new user
su - robustty
```

### 2.3 Install Docker
```bash
# Install dependencies
sudo apt-get install ca-certificates curl gnupg lsb-release

# Add Docker's GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y

# Add user to docker group
sudo usermod -aG docker $USER

# Install docker-compose
sudo apt install docker-compose -y

# Logout and login again for group changes
exit
```

Log back in as your user:
```bash
ssh robustty@your-vps-ip
```

### 2.4 Setup Project Directory
```bash
# Create directory structure
sudo mkdir -p /opt/robustty/cookies
sudo chown -R $USER:$USER /opt/robustty

# Clone your repository
cd /opt
git clone https://github.com/yourusername/robustty.git
cd robustty
```

### 2.5 Configure Firewall
```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS (optional, for metrics)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw --force enable
```

---

## 🔑 Step 3: Setup SSH Key for Cookie Sync

### On Your macOS Machine:

```bash
# Generate a dedicated SSH key for cookie sync
ssh-keygen -t ed25519 -f ~/.ssh/robustty_vps -N ""

# Display the public key (you'll need this)
cat ~/.ssh/robustty_vps.pub
```

### On Your VPS:

```bash
# Add the public key to authorized_keys
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys

# Paste your public key from above, save and exit

# Set correct permissions
chmod 600 ~/.ssh/authorized_keys
```

### Test SSH Connection (from macOS):

```bash
ssh -i ~/.ssh/robustty_vps robustty@your-vps-ip
```

If this works without asking for a password, you're good!

---

## 🍪 Step 4: Setup Cookie Sync

### 4.1 Configure Environment on macOS

Edit your local `.env` file:
```bash
cd ~/Documents/Projects/Robustty
nano .env
```

Add these lines:
```bash
# VPS Cookie Sync Configuration
VPS_HOST=your-vps-ip
VPS_USER=robustty
SSH_KEY=/Users/yourusername/.ssh/robustty_vps
VPS_COOKIE_DIR=/opt/robustty/cookies
```

### 4.2 Test Cookie Sync Manually

```bash
# Run the sync script
./scripts/sync-cookies-to-vps.sh
```

You should see output like:
```
[2025-01-24 12:00:00] Starting cookie sync process...
[2025-01-24 12:00:00] Extracting cookies from Brave browser...
[2025-01-24 12:00:01] Cookie extraction completed successfully
[2025-01-24 12:00:01] Copying cookies from Docker container to host...
[2025-01-24 12:00:01] Found 4 cookie file(s) to sync
[2025-01-24 12:00:01] Syncing cookies to VPS...
[2025-01-24 12:00:02] Cookie sync completed successfully!
```

### 4.3 Setup Automated Sync on macOS

```bash
# Edit crontab
crontab -e
```

Add these lines:
```cron
# Sync cookies to VPS every 2 hours
0 */2 * * * /Users/yourusername/Documents/Projects/Robustty/scripts/sync-cookies-to-vps.sh >> /var/log/robustty-sync.log 2>&1

# Also sync on reboot (after 2 minute delay)
@reboot sleep 120 && /Users/yourusername/Documents/Projects/Robustty/scripts/sync-cookies-to-vps.sh
```

---

## 🤖 Step 5: Setup Bot on VPS

### 5.1 Configure Environment

```bash
cd /opt/robustty
cp .env.example .env
nano .env
```

Edit with your values:
```bash
# Required
DISCORD_TOKEN=your_discord_bot_token_here
YOUTUBE_API_KEY=your_youtube_api_key_here
APIFY_API_KEY=your_apify_api_key_here

# Performance
SEARCH_TIMEOUT=30
STREAM_TIMEOUT=300
MAX_QUEUE_SIZE=100

# Keep other defaults
```

### 5.2 Start the Bot

```bash
# Use the VPS-specific docker-compose file
docker-compose -f docker-compose.vps.yml up -d

# Check logs
docker-compose -f docker-compose.vps.yml logs -f
```

You should see the bot starting up and connecting to Discord!

---

## 📊 Step 6: Setup Monitoring

### 6.1 Cookie Freshness Monitoring

Add to VPS crontab:
```bash
crontab -e
```

Add:
```cron
# Check cookie freshness every hour
0 * * * * /opt/robustty/scripts/check-cookie-sync.sh
```

### 6.2 Discord Webhook Alerts (Optional)

1. Create a webhook in your Discord server:
   - Server Settings → Integrations → Webhooks → New Webhook

2. Add to `.env` on VPS:
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
```

### 6.3 View Metrics (Optional)

The bot exposes metrics on port 8080:
```bash
# Check metrics
curl http://localhost:8080/metrics
```

---

## 🧪 Step 7: Verify Everything Works

### 7.1 Check Cookie Files on VPS
```bash
ls -la /opt/robustty/cookies/
```

You should see:
```
-rw-r--r-- 1 robustty robustty  3585 Jun 24 12:00 youtube_cookies.json
-rw-r--r-- 1 robustty robustty   323 Jun 24 12:00 rumble_cookies.json
-rw-r--r-- 1 robustty robustty   456 Jun 24 12:00 odysee_cookies.json
-rw-r--r-- 1 robustty robustty   234 Jun 24 12:00 peertube_cookies.json
```

### 7.2 Check Bot Status
```bash
docker-compose -f docker-compose.vps.yml ps
```

Should show:
```
NAME                COMMAND             SERVICE    STATUS    PORTS
robustty-bot        "/app/start.sh"     robustty   Up        
robustty-redis      "redis-server..."   redis      Up        
```

### 7.3 Test Bot in Discord
- Type `!play https://youtube.com/watch?v=dQw4w9WgXcQ` in a voice channel
- Bot should join and start playing

---

## 🔧 Troubleshooting

### Bot Can't Connect to Discord
```bash
# Check DNS resolution
docker exec robustty-bot ping -c 3 discord.com

# Restart containers
docker-compose -f docker-compose.vps.yml restart
```

### Cookies Not Syncing
```bash
# On macOS, test sync manually
./scripts/sync-cookies-to-vps.sh

# Check SSH connection
ssh -i ~/.ssh/robustty_vps robustty@your-vps-ip "echo 'Connection OK'"

# Check cron logs on macOS
tail -f /var/log/robustty-sync.log
```

### Old/Stale Cookies
```bash
# On VPS, check cookie age
./scripts/check-cookie-sync.sh

# Force manual sync from macOS
./scripts/sync-cookies-to-vps.sh
```

---

## 🔒 Security Best Practices

1. **SSH Security**:
   ```bash
   # Disable password authentication
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart sshd
   ```

2. **Fail2ban** (recommended):
   ```bash
   sudo apt install fail2ban -y
   sudo systemctl enable fail2ban
   ```

3. **Regular Updates**:
   ```bash
   # Create update script
   cat > /opt/robustty/update.sh << 'EOF'
   #!/bin/bash
   cd /opt/robustty
   git pull
   docker-compose -f docker-compose.vps.yml up -d --build
   EOF
   
   chmod +x /opt/robustty/update.sh
   ```

---

## 📈 Performance Optimization

### For West Coast Latency:
```bash
# Use Cloudflare DNS
sudo nano /etc/systemd/resolved.conf

# Add:
[Resolve]
DNS=1.1.1.1
FallbackDNS=1.0.0.1

# Restart
sudo systemctl restart systemd-resolved
```

### Docker Resource Limits:
The `docker-compose.vps.yml` already includes resource limits:
- Bot: 2 CPU, 2GB RAM
- Redis: 0.5 CPU, 512MB RAM

---

## 🎉 Success Checklist

- [ ] VPS is running Ubuntu 22.04
- [ ] Docker and Docker Compose installed
- [ ] SSH key authentication working
- [ ] Cookies syncing every 2 hours
- [ ] Bot running and connected to Discord
- [ ] Monitoring scripts in place
- [ ] Firewall configured
- [ ] Bot responding to commands

---

## 📝 Quick Reference

### Essential Commands

**On macOS:**
```bash
# Manual cookie sync
./scripts/sync-cookies-to-vps.sh

# Check sync logs
tail -f /var/log/robustty-sync.log
```

**On VPS:**
```bash
# View bot logs
docker-compose -f docker-compose.vps.yml logs -f

# Restart bot
docker-compose -f docker-compose.vps.yml restart

# Check cookie freshness
./scripts/check-cookie-sync.sh

# Update bot
cd /opt/robustty && git pull && docker-compose -f docker-compose.vps.yml up -d --build
```

### Important Paths

**macOS:**
- Sync script: `~/Documents/Projects/Robustty/scripts/sync-cookies-to-vps.sh`
- SSH key: `~/.ssh/robustty_vps`

**VPS:**
- Bot directory: `/opt/robustty/`
- Cookies: `/opt/robustty/cookies/`
- Logs: `/opt/robustty/logs/`

---

## 💡 Tips

1. **First Time Setup**: Allow 5-10 minutes for initial setup
2. **Cookie Sync**: First sync might take longer, subsequent syncs are instant
3. **Monitoring**: Check bot logs regularly for the first 24 hours
4. **Timezone**: Ensure VPS and macOS have correct timezones for cron jobs

Need help? Check the logs first, then refer to the troubleshooting section!