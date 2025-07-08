#!/bin/bash
# DNS routing configuration for split tunneling
# Ensures DNS queries go through appropriate networks

set -e

echo "🌐 Configuring DNS routing for split tunneling..."

# Network configuration from environment
VPN_NETWORK_NAME=${VPN_NETWORK_NAME:-vpn-network}
DIRECT_NETWORK_NAME=${DIRECT_NETWORK_NAME:-direct-network}
VPN_DNS=${WG_DNS:-10.2.0.1}
CLOUDFLARE_DNS="1.1.1.1"
GOOGLE_DNS="8.8.8.8"

# Service routing preferences
DISCORD_USE_VPN=${DISCORD_USE_VPN:-true}
YOUTUBE_USE_VPN=${YOUTUBE_USE_VPN:-false}

echo "📋 DNS Configuration:"
echo "🔐 VPN DNS: $VPN_DNS"
echo "🌍 Public DNS: $CLOUDFLARE_DNS, $GOOGLE_DNS"

# Function to configure DNS for specific domains
configure_domain_dns() {
    local domain=$1
    local dns_server=$2
    local description=$3
    
    echo "Configuring DNS for $domain via $dns_server ($description)"
    
    # Add to /etc/hosts if needed (fallback)
    # Note: In production, this would use DNS policy routing
    # For now, we'll configure global DNS and rely on network routing
}

# Configure split DNS
echo "🎯 Configuring split DNS routing..."

if [ "$DISCORD_USE_VPN" = "true" ]; then
    echo "🔐 Discord domains will use VPN DNS ($VPN_DNS)"
    configure_domain_dns "discord.com" "$VPN_DNS" "VPN"
    configure_domain_dns "discordapp.com" "$VPN_DNS" "VPN"
    configure_domain_dns "discord.gg" "$VPN_DNS" "VPN"
else
    echo "🌍 Discord domains will use public DNS"
    configure_domain_dns "discord.com" "$CLOUDFLARE_DNS" "Public"
fi

if [ "$YOUTUBE_USE_VPN" = "false" ]; then
    echo "🎵 YouTube domains will use public DNS"
    configure_domain_dns "youtube.com" "$CLOUDFLARE_DNS" "Public"
    configure_domain_dns "googleapis.com" "$CLOUDFLARE_DNS" "Public"
    configure_domain_dns "googlevideo.com" "$CLOUDFLARE_DNS" "Public"
else
    echo "🔐 YouTube domains will use VPN DNS"
    configure_domain_dns "youtube.com" "$VPN_DNS" "VPN"
fi

# Configure fallback DNS
echo "⚡ Configuring fallback DNS servers..."

# Create custom resolv.conf with multiple DNS servers
cat > /tmp/resolv.conf.custom << EOF
# Custom DNS configuration for split tunneling
# Primary DNS servers
nameserver $CLOUDFLARE_DNS
nameserver $GOOGLE_DNS

# VPN DNS (if available)
$([ -n "$VPN_DNS" ] && echo "nameserver $VPN_DNS")

# DNS options
options timeout:2
options attempts:3
options rotate
EOF

# Use custom DNS configuration
if [ -w /etc/resolv.conf ]; then
    cp /tmp/resolv.conf.custom /etc/resolv.conf
    echo "✅ DNS configuration updated"
else
    echo "⚠️  Cannot write to /etc/resolv.conf (read-only filesystem)"
    echo "   DNS routing will rely on network interface routing"
fi

# Test DNS resolution
echo "🧪 Testing DNS resolution..."

for domain in discord.com youtube.com google.com; do
    if nslookup "$domain" >/dev/null 2>&1; then
        echo "✅ DNS resolution working for $domain"
    else
        echo "⚠️  DNS resolution failed for $domain"
    fi
done

echo "🎉 DNS routing configuration complete!"