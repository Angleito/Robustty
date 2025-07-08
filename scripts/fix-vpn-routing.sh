#!/bin/bash

# Fix routing so bot traffic bypasses ProtonVPN
# Only Discord traffic goes through VPN

echo "🌐 Configuring Split Tunnel for Robustty"
echo "========================================"

# 1. Check ProtonVPN status
echo "📊 Current VPN status:"
protonvpn-cli status

# 2. Get current network interfaces
echo "🔍 Detecting network interfaces..."
DEFAULT_IFACE=$(ip route | grep default | grep -v proton | awk '{print $5}' | head -1)
VPN_IFACE=$(ip route | grep default | grep proton | awk '{print $5}' | head -1)
REAL_IP=$(curl -s --interface $DEFAULT_IFACE https://ipinfo.io/ip 2>/dev/null || echo "Unknown")

echo "Default interface: $DEFAULT_IFACE (IP: $REAL_IP)"
echo "VPN interface: $VPN_IFACE"

# 3. Create iptables rules for split tunneling
echo "🔧 Setting up split tunnel..."

# Mark packets from Docker containers
iptables -t mangle -A OUTPUT -s 172.28.0.0/16 -j MARK --set-mark 100

# Route marked packets through original interface (bypass VPN)
ip rule add fwmark 100 table 100
ip route add default via $(ip route | grep default | grep -v proton | awk '{print $3}' | head -1) dev $DEFAULT_IFACE table 100

# But keep Discord traffic through VPN
iptables -t mangle -A OUTPUT -d 162.159.0.0/16 -j MARK --set-mark 0  # Discord IPs

# 4. Alternative: Configure Docker to use host networking selectively
echo "🐳 Updating Docker configuration..."
cat > /tmp/docker-compose.override.yml << 'EOF'
version: '3.8'

services:
  robustty:
    # Use host networking to bypass Docker's bridge
    network_mode: "host"
    environment:
      - BYPASS_VPN=true
      
  redis:
    # Keep Redis isolated
    networks:
      - robustty-network
      
  youtube-music-headless:
    # Also use host networking
    network_mode: "host"
EOF

# 5. Save iptables rules
echo "💾 Saving routing rules..."
iptables-save > /etc/iptables/rules.v4

echo "✅ Split tunnel configured!"
echo ""
echo "Bot traffic will now bypass VPN for:"
echo "- YouTube API calls"
echo "- Music streaming"
echo "- Platform searches"
echo ""
echo "Discord traffic still goes through VPN!"
echo ""
echo "Apply with: docker-compose -f docker-compose.yml -f /tmp/docker-compose.override.yml up -d"