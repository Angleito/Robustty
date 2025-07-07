# VPS DNS Resolution Fix for Discord Bot

## Problem Summary

When deploying the Robustty Discord bot to Ubuntu VPS servers, you may encounter DNS resolution failures with errors like:
```
Cannot connect to host gateway.discord.gg:443 ssl:default [No address associated with hostname]
```

This occurs because:
1. Ubuntu VPS systems often use `systemd-resolved` for DNS management
2. `/etc/resolv.conf` is symlinked to `/run/systemd/resolve/stub-resolv.conf` which points to `127.0.0.53`
3. Docker containers inherit this configuration, but `127.0.0.53` is not accessible from inside containers
4. This causes all external DNS lookups to fail, preventing Discord connections

## Solution

### Automatic Fix (Recommended)

The deployment scripts now automatically run the DNS fix during deployment:

```bash
# Using the validation deployment script (recommended)
./deploy-vps-with-validation.sh <vps-ip> ubuntu

# The script will automatically:
# 1. Fix the systemd-resolved symlink issue
# 2. Configure Docker daemon with proper DNS
# 3. Test DNS resolution
# 4. Start services with working DNS
```

### Manual Fix (If Needed)

If you need to fix DNS manually on an already deployed VPS:

```bash
# SSH into your VPS
ssh ubuntu@<your-vps-ip>

# Navigate to the bot directory
cd ~/robustty-bot

# Run the DNS fix script
sudo bash scripts/fix-vps-dns.sh

# The script will:
# 1. Fix /etc/resolv.conf to use real DNS servers
# 2. Configure Docker daemon with fallback DNS
# 3. Update systemd-resolved configuration
# 4. Restart necessary services
# 5. Test DNS resolution
```

### What the Fix Does

1. **Fixes systemd-resolved symlink**:
   - Changes `/etc/resolv.conf` from pointing to stub resolver to real resolver
   - From: `/etc/resolv.conf -> /run/systemd/resolve/stub-resolv.conf` (127.0.0.53)
   - To: `/etc/resolv.conf -> /run/systemd/resolve/resolv.conf` (real DNS servers)

2. **Configures Docker daemon**:
   - Adds explicit DNS servers to `/etc/docker/daemon.json`
   - Uses reliable public DNS: Google (8.8.8.8), Cloudflare (1.1.1.1)
   - Disables DNS search domains to prevent lookup delays

3. **Updates systemd-resolved**:
   - Disables the DNS stub listener
   - Configures upstream DNS servers
   - Ensures proper service restart order

## Verification

After running the fix, verify DNS is working:

```bash
# Test host DNS
nslookup gateway.discord.gg

# Test Docker container DNS
docker run --rm alpine nslookup gateway.discord.gg

# Check bot logs
docker-compose logs robustty | grep -i dns
```

## Troubleshooting

If DNS still fails after the fix:

1. **Check firewall rules**:
   ```bash
   # Ensure outbound DNS (UDP port 53) is allowed
   sudo ufw status
   sudo ufw allow out 53/udp
   ```

2. **Check VPS provider restrictions**:
   - Some VPS providers block external DNS servers
   - Use provider's DNS servers if needed:
   ```bash
   cat /run/systemd/resolve/resolv.conf
   # Add provider's nameservers to /etc/docker/daemon.json
   ```

3. **Restart all services**:
   ```bash
   sudo systemctl restart systemd-resolved
   sudo systemctl restart docker
   cd ~/robustty-bot && docker-compose restart
   ```

4. **Check container DNS configuration**:
   ```bash
   docker-compose exec robustty cat /etc/resolv.conf
   # Should show real DNS servers, not 127.0.0.x
   ```

## Prevention

To prevent DNS issues on new deployments:

1. Always use the deployment script with validation:
   ```bash
   ./deploy-vps-with-validation.sh <vps-ip> ubuntu
   ```

2. The script automatically runs the DNS fix before starting services

3. For custom deployments, run the DNS fix immediately after Docker installation:
   ```bash
   sudo bash scripts/fix-vps-dns.sh
   ```

## Additional Notes

- This issue is specific to Ubuntu VPS systems using systemd-resolved
- Other distributions or cloud providers may not require this fix
- The fix is idempotent - safe to run multiple times
- DNS configuration persists across reboots