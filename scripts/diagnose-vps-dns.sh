#!/bin/bash

echo "=== VPS DNS Diagnostics (Sanitized) ==="
echo

# Check host DNS configuration (sanitized)
echo "1. Host DNS Configuration:"
echo "------------------------"
echo "Nameservers configured: $(grep -c nameserver /etc/resolv.conf 2>/dev/null || echo "0")"
grep nameserver /etc/resolv.conf 2>/dev/null | sed 's/nameserver/DNS Server:/' || echo "Unable to read DNS config"
echo

# Test DNS resolution without exposing IPs
echo "2. Host DNS Resolution Tests:"
echo "----------------------------"
for domain in "gateway-us-west-1.discord.gg" "google.com"; do
    echo -n "Testing $domain: "
    nslookup $domain >/dev/null 2>&1 && echo "SUCCESS" || echo "FAILED"
done
echo

# Check Docker daemon DNS configuration
echo "3. Docker Daemon DNS:"
echo "--------------------"
if [ -f /etc/docker/daemon.json ]; then
    echo "daemon.json exists"
    jq -r '.dns // empty' /etc/docker/daemon.json 2>/dev/null | head -5 || echo "No DNS config in daemon.json"
else
    echo "No daemon.json found"
fi
echo

# Test DNS inside container
echo "4. Container DNS Tests:"
echo "----------------------"
docker-compose exec robustty sh -c '
echo "Container nameservers: $(grep -c nameserver /etc/resolv.conf)"
echo
echo "Testing DNS resolution inside container:"
for domain in "gateway-us-west-1.discord.gg" "google.com" "redis"; do
    echo -n "Testing $domain: "
    nslookup $domain >/dev/null 2>&1 && echo "SUCCESS" || echo "FAILED"
done
' 2>/dev/null || echo "Unable to execute tests inside container"
echo

# Check firewall rules (sanitized)
echo "5. Firewall Status:"
echo "------------------"
echo "Docker rules: $(sudo iptables -L -n 2>/dev/null | grep -c DOCKER || echo "0")"
echo "DNS port (53) rules: $(sudo iptables -L -n 2>/dev/null | grep -c ':53' || echo "0")"
echo

# Check network connectivity
echo "6. Network Connectivity:"
echo "-----------------------"
echo "Testing outbound connections:"
for host in "8.8.8.8" "1.1.1.1"; do
    echo -n "DNS server $host: "
    ping -c 1 -W 2 $host &>/dev/null && echo "OK" || echo "FAILED"
done
echo -n "Discord gateway: "
ping -c 1 -W 2 gateway-us-west-1.discord.gg &>/dev/null && echo "OK" || echo "FAILED"
echo

# Docker network status
echo "7. Docker Network Status:"
echo "------------------------"
docker network ls | grep robustty || echo "No robustty network found"
echo

# Check systemd-resolved if present
echo "8. DNS Service Status:"
echo "---------------------"
if systemctl is-active systemd-resolved &>/dev/null; then
    echo "systemd-resolved: ACTIVE"
else
    echo "systemd-resolved: NOT ACTIVE"
fi
echo

# Provide fix suggestions
echo "9. Suggested Fixes:"
echo "------------------"
echo "If DNS is failing, try these commands on your VPS:"
echo "1. sudo echo 'nameserver 8.8.8.8' > /etc/resolv.conf"
echo "2. sudo echo 'nameserver 8.8.4.4' >> /etc/resolv.conf"
echo "3. docker-compose down && docker-compose up -d"
echo "4. Or add to /etc/docker/daemon.json:"
echo '   {"dns": ["8.8.8.8", "8.8.4.4"]}'
echo

echo "=== Diagnostics Complete ==="