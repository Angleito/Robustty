# VPS DNS Troubleshooting Guide

This guide helps diagnose and fix DNS resolution issues that prevent the Robustty Discord bot from connecting to Discord services on VPS deployments.

## Common Symptoms

- `socket.gaierror: [Errno -2] Name or service not known`
- Bot fails to connect to Discord with connection timeouts
- DNS resolution failures for `gateway-us-east1-d.discord.gg`
- Network connectivity issues during deployment

## Quick Diagnosis

Run the comprehensive network diagnostics script:

```bash
./scripts/diagnose-vps-network.sh
```

Or perform basic DNS checks:

```bash
# Test Discord endpoint resolution
nslookup gateway-us-east1-d.discord.gg
nslookup discord.com

# Test connectivity to Discord HTTPS port
nc -z gateway-us-east1-d.discord.gg 443

# Check current DNS configuration
cat /etc/resolv.conf
```

## Automated Fix

For most DNS issues, run our automated fix script:

```bash
sudo ./scripts/fix-vps-dns.sh
```

This script will:
- Backup current DNS configuration
- Add reliable public DNS servers
- Configure firewall rules for DNS/HTTPS traffic
- Test and validate the fixes
- Provide rollback instructions if needed

## Manual Troubleshooting Steps

### 1. Check DNS Configuration

```bash
# View current DNS servers
cat /etc/resolv.conf

# Check systemd-resolved status (if applicable)
systemd-resolve --status

# View name resolution order
grep "^hosts:" /etc/nsswitch.conf
```

### 2. Test Public DNS Servers

```bash
# Test connectivity to public DNS servers
ping -c 1 8.8.8.8
ping -c 1 1.1.1.1

# Test DNS resolution using specific servers
nslookup discord.com 8.8.8.8
dig @1.1.1.1 gateway-us-east1-d.discord.gg
```

### 3. Fix DNS Servers

Add reliable public DNS servers to `/etc/resolv.conf`:

```bash
# Backup current configuration
sudo cp /etc/resolv.conf /etc/resolv.conf.backup

# Add public DNS servers
sudo tee /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 1.1.1.1
nameserver 8.8.4.4
EOF
```

### 4. Configure systemd-resolved (Ubuntu/Debian)

If your system uses systemd-resolved:

```bash
# Edit systemd-resolved configuration
sudo nano /etc/systemd/resolved.conf

# Add these lines:
[Resolve]
DNS=8.8.8.8 1.1.1.1
FallbackDNS=8.8.4.4 1.0.0.1
Domains=~.

# Restart the service
sudo systemctl restart systemd-resolved

# Link resolv.conf to systemd-resolved
sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
```

### 5. Check Firewall Rules

Ensure outbound DNS and HTTPS traffic is allowed:

```bash
# UFW (Ubuntu Firewall)
sudo ufw allow out 53 comment "Allow outbound DNS"
sudo ufw allow out 443 comment "Allow outbound HTTPS"
sudo ufw status

# iptables (generic)
sudo iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
sudo iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT
```

### 6. Network Interface Troubleshooting

```bash
# Check network interfaces
ip addr show
ip link show

# Check routing table
ip route show

# Restart networking (be careful with SSH connections!)
sudo systemctl restart networking
# or
sudo systemctl restart NetworkManager
```

## VPS Provider Specific Issues

### Security Groups / Firewall Rules

Many VPS providers have security groups or firewall rules that need to be configured:

1. **AWS EC2**: Check Security Groups allow outbound HTTPS (443) and DNS (53)
2. **DigitalOcean**: Verify Cloud Firewall allows outbound traffic
3. **Vultr**: Check Firewall rules in the control panel
4. **Linode**: Verify Cloud Firewall settings

### Common Provider DNS Issues

1. **OVH/OVHcloud**: May have restrictive DNS settings
2. **Hetzner**: Sometimes blocks certain DNS queries
3. **Azure**: Check Network Security Groups
4. **Google Cloud**: Verify VPC firewall rules

## Docker-Specific Solutions

### DNS Configuration in Docker Compose

The main `docker-compose.yml` already includes DNS configuration for VPS deployments:

```yaml
dns:
  - 8.8.8.8
  - 8.8.4.4
  - 1.1.1.1
dns_search:
  - .
dns_opt:
  - ndots:1
  - timeout:5
  - attempts:3
```

### Test DNS from Container

```bash
# Enter running container
docker exec -it robustty-bot bash

# Test DNS resolution from inside container
nslookup gateway-us-east1-d.discord.gg
ping -c 1 discord.com

# Test Python socket connection
python -c "import socket; socket.create_connection(('discord.com', 443), timeout=10)"
```

### Host Networking (Last Resort)

If DNS issues persist, try host networking:

```yaml
# Add to robustty service in docker-compose.yml
network_mode: host
```

Note: This bypasses Docker's network isolation and may have security implications.

## Verification Steps

After applying fixes, verify resolution works:

```bash
# Test all Discord endpoints
for endpoint in gateway-us-east1-d.discord.gg discord.com discordapp.com cdn.discordapp.com; do
    echo "Testing $endpoint..."
    nslookup $endpoint
    nc -z $endpoint 443 && echo "✅ $endpoint:443 accessible" || echo "❌ $endpoint:443 failed"
done

# Test from Docker container
docker-compose exec robustty python -c "
import socket
try:
    socket.create_connection(('gateway-us-east1-d.discord.gg', 443), timeout=10)
    print('✅ Discord gateway is accessible from container')
except Exception as e:
    print(f'❌ Connection failed: {e}')
"
```

## Logs and Debugging

### Check Bot Logs

```bash
# View real-time logs
docker-compose logs -f robustty

# Search for DNS errors
docker-compose logs robustty | grep -i "gaierror\|dns\|resolve"
```

### Check System DNS Logs

```bash
# systemd journal for DNS issues
journalctl -u systemd-resolved -f

# General network logs
journalctl -k | grep -i dns
```

## Prevention

### Monitoring

Set up monitoring to detect DNS issues:

```bash
# Add to crontab for regular DNS checks
*/5 * * * * nslookup gateway-us-east1-d.discord.gg >/dev/null 2>&1 || echo "$(date): DNS resolution failed" >> /var/log/dns-monitor.log
```

### Backup DNS Configuration

Always backup working DNS configuration:

```bash
# Create backup
sudo cp /etc/resolv.conf /etc/resolv.conf.working

# Restore if needed
sudo cp /etc/resolv.conf.working /etc/resolv.conf
```

## Contact Support

If DNS issues persist after trying all solutions:

1. Contact your VPS provider's support team
2. Provide the output of `./scripts/diagnose-vps-network.sh`
3. Include relevant logs from `docker-compose logs`
4. Specify your VPS provider and plan details

## Related Files

- `/scripts/diagnose-vps-network.sh` - Comprehensive network diagnostics
- `/scripts/fix-vps-dns.sh` - Automated DNS fix script
- `/deploy-vps.sh` - VPS deployment with DNS pre-checks
- `/scripts/setup-vps.sh` - VPS setup with network validation
- `/docker-compose.yml` - Main Docker configuration with VPS-compatible DNS settings