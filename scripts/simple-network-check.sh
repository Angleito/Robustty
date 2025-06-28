#!/bin/bash
# Simple network connectivity check for Robustty bot

echo "🔍 ROBUSTTY NETWORK CONNECTIVITY DIAGNOSTIC"
echo "==========================================="
echo

# Function to test DNS resolution
test_dns() {
    local domain=$1
    local description=$2
    local dns_server=$3
    
    echo -n "Testing $description ($domain) with $dns_server... "
    
    if nslookup "$domain" "$dns_server" >/dev/null 2>&1; then
        echo "✅ SUCCESS"
        return 0
    else
        echo "❌ FAILED"
        return 1
    fi
}

# Function to test HTTP connectivity
test_http() {
    local url=$1
    local description=$2
    
    echo -n "Testing $description ($url)... "
    
    if curl -s --head --connect-timeout 10 --max-time 15 "$url" >/dev/null 2>&1; then
        echo "✅ SUCCESS"
        return 0
    else
        echo "❌ FAILED"
        return 1
    fi
}

# Test DNS servers
echo "🌐 DNS RESOLUTION TESTS"
echo "----------------------"

dns_servers=("8.8.8.8:Google" "1.1.1.1:Cloudflare" "9.9.9.9:Quad9")
test_domains=("discord.com:Discord" "gateway.discord.gg:Discord Gateway" "api.odysee.com:Odysee" "tube.tchncs.de:PeerTube")

working_dns=0
total_dns=0

for dns_entry in "${dns_servers[@]}"; do
    IFS=':' read -r dns_server dns_name <<< "$dns_entry"
    echo
    echo "📡 Testing with $dns_name DNS ($dns_server):"
    
    dns_success=0
    dns_total=0
    
    for domain_entry in "${test_domains[@]}"; do
        IFS=':' read -r domain domain_desc <<< "$domain_entry"
        test_dns "$domain" "$domain_desc" "$dns_server"
        if [ $? -eq 0 ]; then
            ((dns_success++))
        fi
        ((dns_total++))
    done
    
    echo "  Results: $dns_success/$dns_total successful"
    
    if [ $dns_success -gt 1 ]; then
        ((working_dns++))
    fi
    ((total_dns++))
done

echo
echo "🌍 HTTP CONNECTIVITY TESTS"
echo "-------------------------"

http_endpoints=(
    "https://discord.com/api/v10/gateway:Discord API"
    "https://api.odysee.com:Odysee API"
    "https://tube.tchncs.de:PeerTube Main"
)

working_http=0
total_http=0

for endpoint in "${http_endpoints[@]}"; do
    IFS=':' read -r url description <<< "$endpoint"
    test_http "$url" "$description"
    if [ $? -eq 0 ]; then
        ((working_http++))
    fi
    ((total_http++))
done

echo
echo "📊 SUMMARY & RECOMMENDATIONS"
echo "============================"
echo "DNS Servers Working: $working_dns/$total_dns"
echo "HTTP Endpoints Working: $working_http/$total_http"
echo

# Provide recommendations
if [ $working_dns -eq 0 ]; then
    echo "🚨 CRITICAL: No DNS servers are working!"
    echo "   ➤ Check your internet connection"
    echo "   ➤ Check firewall settings"
    echo "   ➤ Contact your network administrator"
    exit 1
elif [ $working_dns -lt 2 ]; then
    echo "⚠️  WARNING: Limited DNS connectivity"
    echo "   ➤ Consider using alternative DNS servers"
    echo "   ➤ Configure router DNS settings to use 1.1.1.1, 8.8.8.8"
fi

if [ $working_http -lt 2 ]; then
    echo "⚠️  WARNING: Some platforms may be unavailable"
    echo "   ➤ Bot will use fallback mechanisms"
    echo "   ➤ Some features may be limited"
fi

# Test specific Discord gateway issue
echo
echo "🎮 DISCORD SPECIFIC TESTS"
echo "------------------------"

echo -n "Testing Discord gateway resolution... "
if nslookup gateway-us-west-1.discord.gg 8.8.8.8 >/dev/null 2>&1; then
    echo "✅ Discord gateways resolve"
else
    echo "❌ Discord gateways not resolving"
    echo "   ➤ This is the main issue causing Discord connection failures"
    echo "   ➤ Bot will fallback to gateway.discord.gg"
fi

echo
if [ $working_dns -gt 0 ] && [ $working_http -gt 0 ]; then
    echo "✅ Overall network connectivity: GOOD"
    echo "   ➤ Bot should be able to connect with some limitations"
    exit 0
else
    echo "❌ Overall network connectivity: POOR"
    echo "   ➤ Bot may have significant connection issues"
    exit 1
fi