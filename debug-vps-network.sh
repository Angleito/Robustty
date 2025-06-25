#!/bin/bash

# Debug script for VPS network issues
# Run this on the VPS to diagnose Discord connectivity problems

echo "🔍 Robustty VPS Network Diagnostic"
echo "=================================="
echo ""

# Test DNS resolution for Discord domains  
echo "📡 Testing DNS Resolution:"
echo "-------------------------"
for domain in discord.com gateway.discord.gg cdn.discordapp.com gateway-us-west-1.discord.gg; do
    echo -n "$domain: "
    if nslookup "$domain" >/dev/null 2>&1; then
        echo "✅ OK"
    else
        echo "❌ FAILED"
        echo "  Trying with Google DNS..."
        if nslookup "$domain" 8.8.8.8 >/dev/null 2>&1; then
            echo "  ✅ OK with Google DNS - DNS server issue"
        else
            echo "  ❌ Still failed - possible DNS blocking"
        fi
    fi
done
echo ""

# Test HTTPS connectivity to Discord endpoints
echo "🌐 Testing HTTPS Connectivity:"
echo "------------------------------"
declare -A endpoints=(
    ["Discord API"]="https://discord.com/api/v10/gateway"
    ["Discord CDN"]="https://cdn.discordapp.com"
    ["Discord Gateway"]="https://gateway.discord.gg"
)

for name in "${!endpoints[@]}"; do
    url="${endpoints[$name]}"
    echo -n "$name: "
    response=$(curl -s -w "%{http_code}" -o /dev/null --connect-timeout 10 --max-time 15 "$url" 2>/dev/null)
    if [[ "$response" == "200" ]]; then
        echo "✅ OK (HTTP 200)"
    elif [[ "$response" == "403" ]]; then
        echo "❌ HTTP 403 - IP likely blocked by Discord"
    elif [[ "$response" == "" ]]; then
        echo "❌ Connection failed - DNS or firewall issue"
    else
        echo "⚠️  HTTP $response"
    fi
done
echo ""

# Check current DNS configuration
echo "🔧 DNS Configuration:"
echo "--------------------"
echo "Current resolv.conf:"
cat /etc/resolv.conf
echo ""

# Test with different DNS servers
echo "🧪 Testing Alternative DNS Servers:"
echo "-----------------------------------"
for dns in "8.8.8.8" "1.1.1.1" "208.67.222.222"; do
    echo -n "DNS $dns: "
    if nslookup discord.com "$dns" >/dev/null 2>&1; then
        echo "✅ Working"
    else
        echo "❌ Failed"  
    fi
done
echo ""

# Check firewall rules
echo "🛡️  Firewall Status:"
echo "-------------------"
if command -v ufw >/dev/null 2>&1; then
    echo "UFW Status:"
    ufw status
    echo ""
fi

if command -v iptables >/dev/null 2>&1 && [[ $EUID -eq 0 ]]; then
    echo "IPTables OUTPUT chain:"
    iptables -L OUTPUT -n
    echo ""
fi

# Test basic connectivity
echo "🏓 Basic Connectivity Tests:"
echo "----------------------------"
echo -n "Google DNS ping: "
if ping -c 3 8.8.8.8 >/dev/null 2>&1; then
    echo "✅ OK"
else
    echo "❌ Failed - no internet"
fi

echo -n "Discord.com ping: "
if ping -c 3 discord.com >/dev/null 2>&1; then  
    echo "✅ OK"
else
    echo "❌ Failed - DNS or routing issue"
fi
echo ""

# VPS Provider IP Information
echo "📍 VPS Information:"
echo "------------------"
echo "Public IP: $(curl -s ifconfig.me 2>/dev/null || echo 'Unable to detect')"
echo "Hostname: $(hostname)"
echo "Location info:"
curl -s "http://ip-api.com/json/" 2>/dev/null | grep -E '"country"|"regionName"|"city"|"isp"' || echo "Unable to get location info"
echo ""

# Docker network test
echo "🐳 Docker Network Test:"
echo "----------------------"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "Testing container DNS resolution:"
    if docker run --rm alpine nslookup discord.com >/dev/null 2>&1; then
        echo "✅ Container DNS working"
    else
        echo "❌ Container DNS failed"
    fi
    
    echo "Testing container HTTPS:"
    if docker run --rm alpine wget -q --spider https://discord.com 2>/dev/null; then
        echo "✅ Container HTTPS working"  
    else
        echo "❌ Container HTTPS failed"
    fi
else
    echo "Docker not available"
fi
echo ""

echo "🎯 Diagnosis Summary:"
echo "===================="
echo "1. If DNS resolution fails → DNS server issue"
echo "2. If HTTP 403 errors → VPS IP blocked by Discord"  
echo "3. If connection timeouts → Firewall or routing issue"
echo "4. If Docker tests fail → Container networking issue"
echo ""
echo "💡 Quick Fixes to Try:"
echo "====================="
echo "1. Fix DNS: sudo echo 'nameserver 8.8.8.8' > /etc/resolv.conf"
echo "2. Restart systemd-resolved: sudo systemctl restart systemd-resolved"
echo "3. Try different VPS location/provider if IP is blocked"
echo "4. Check with VPS provider about Discord access restrictions"