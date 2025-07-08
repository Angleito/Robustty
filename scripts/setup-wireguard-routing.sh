#!/bin/bash

# Setup WireGuard with Docker multi-network routing
# This script configures WireGuard and sets up routing for Docker containers

set -euo pipefail

echo "🔐 WireGuard + Docker Multi-Network Setup"
echo "========================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

# Function to create WireGuard config
create_wireguard_config() {
    local config_file="/etc/wireguard/wg0.conf"
    
    echo -e "${YELLOW}Creating WireGuard configuration...${NC}"
    
    # Check if config already exists
    if [ -f "$config_file" ]; then
        echo -e "${YELLOW}Backing up existing config...${NC}"
        cp "$config_file" "${config_file}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Create WireGuard config from environment variables
    cat > "$config_file" << EOF
[Interface]
PrivateKey = ${WG_PRIVATE_KEY}
Address = ${WG_ADDRESS}
DNS = ${WG_DNS}
# Don't route all traffic through VPN by default
Table = 51820
PostUp = /etc/wireguard/postup.sh
PostDown = /etc/wireguard/postdown.sh

[Peer]
PublicKey = ${WG_PUBLIC_KEY}
AllowedIPs = 0.0.0.0/0
Endpoint = ${WG_ENDPOINT}
PersistentKeepalive = 25
EOF

    chmod 600 "$config_file"
    echo -e "${GREEN}✓ WireGuard config created${NC}"
}

# Function to create PostUp script for routing
create_postup_script() {
    echo -e "${YELLOW}Creating PostUp routing script...${NC}"
    
    cat > /etc/wireguard/postup.sh << 'EOF'
#!/bin/bash
# WireGuard PostUp script for Docker multi-network routing

# Add custom routing table
ip route add default dev wg0 table 51820

# Mark packets from VPN network
iptables -t mangle -A PREROUTING -s ${VPN_NETWORK_SUBNET:-172.28.0.0/16} -j MARK --set-mark 0x51820

# Route marked packets through WireGuard
ip rule add fwmark 0x51820 table 51820 priority 100

# Allow forwarding between Docker networks
iptables -A FORWARD -i br-+ -o br-+ -j ACCEPT
iptables -A FORWARD -i br-+ -o wg0 -j ACCEPT
iptables -A FORWARD -i wg0 -o br-+ -j ACCEPT

# NAT for VPN network
iptables -t nat -A POSTROUTING -s ${VPN_NETWORK_SUBNET:-172.28.0.0/16} -o wg0 -j MASQUERADE

# Don't route direct network through VPN
iptables -t mangle -A PREROUTING -s ${DIRECT_NETWORK_SUBNET:-172.29.0.0/16} -j MARK --set-mark 0x0

echo "✓ WireGuard routing configured"
EOF

    chmod +x /etc/wireguard/postup.sh
}

# Function to create PostDown script
create_postdown_script() {
    echo -e "${YELLOW}Creating PostDown cleanup script...${NC}"
    
    cat > /etc/wireguard/postdown.sh << 'EOF'
#!/bin/bash
# WireGuard PostDown script for cleanup

# Remove routing rules
ip rule del fwmark 0x51820 table 51820 2>/dev/null || true
ip route flush table 51820 2>/dev/null || true

# Remove iptables rules
iptables -t mangle -D PREROUTING -s ${VPN_NETWORK_SUBNET:-172.28.0.0/16} -j MARK --set-mark 0x51820 2>/dev/null || true
iptables -t nat -D POSTROUTING -s ${VPN_NETWORK_SUBNET:-172.28.0.0/16} -o wg0 -j MASQUERADE 2>/dev/null || true

echo "✓ WireGuard routing cleaned up"
EOF

    chmod +x /etc/wireguard/postdown.sh
}

# Function to setup Docker routing
setup_docker_routing() {
    echo -e "${YELLOW}Configuring Docker network routing...${NC}"
    
    # Ensure Docker networks exist
    docker network create vpn-network --subnet="${VPN_NETWORK_SUBNET:-172.28.0.0/16}" 2>/dev/null || true
    docker network create direct-network --subnet="${DIRECT_NETWORK_SUBNET:-172.29.0.0/16}" 2>/dev/null || true
    docker network create internal-network --subnet="${INTERNAL_NETWORK_SUBNET:-172.30.0.0/16}" --internal 2>/dev/null || true
    
    echo -e "${GREEN}✓ Docker networks configured${NC}"
}

# Function to create container routing script
create_container_routing_script() {
    echo -e "${YELLOW}Creating container routing script...${NC}"
    
    cat > ./scripts/container-routing.sh << 'EOF'
#!/bin/sh
# Container-side routing configuration

echo "Configuring container routing..."

# Get container's network interfaces
VPN_IF=$(ip addr | grep "${VPN_NETWORK_SUBNET%/*}" | awk '{print $NF}')
DIRECT_IF=$(ip addr | grep "${DIRECT_NETWORK_SUBNET%/*}" | awk '{print $NF}')

if [ -n "$VPN_IF" ] && [ -n "$DIRECT_IF" ]; then
    # Create routing tables
    echo "100 vpn" >> /etc/iproute2/rt_tables 2>/dev/null || true
    echo "200 direct" >> /etc/iproute2/rt_tables 2>/dev/null || true
    
    # Add routes to tables
    ip route add default dev $VPN_IF table vpn 2>/dev/null || true
    ip route add default dev $DIRECT_IF table direct 2>/dev/null || true
    
    # Route Discord through VPN
    for discord_ip in 162.159.0.0/16 162.158.0.0/16; do
        ip rule add to $discord_ip table vpn 2>/dev/null || true
    done
    
    # Route APIs through direct connection
    for api_domain in youtube.googleapis.com www.youtube.com api.rumble.com api.odysee.tv; do
        # Resolve and add rules (this is a simplified version)
        ip rule add to $(getent hosts $api_domain | awk '{print $1}') table direct 2>/dev/null || true
    done
    
    echo "✓ Container routing configured"
else
    echo "⚠ Could not detect all network interfaces"
fi
EOF

    chmod +x ./scripts/container-routing.sh
}

# Main setup process
main() {
    # Load environment variables
    if [ -f .env ]; then
        export $(grep -E '^(WG_|VPN_|DIRECT_|INTERNAL_)' .env | xargs)
    else
        echo -e "${RED}Error: .env file not found${NC}"
        exit 1
    fi
    
    # Check for required WireGuard variables
    if [ -z "$WG_PRIVATE_KEY" ] || [ -z "$WG_PUBLIC_KEY" ] || [ -z "$WG_ENDPOINT" ]; then
        echo -e "${RED}Error: WireGuard configuration missing in .env${NC}"
        echo "Required variables: WG_PRIVATE_KEY, WG_PUBLIC_KEY, WG_ENDPOINT, WG_ADDRESS, WG_DNS"
        exit 1
    fi
    
    # Install WireGuard if needed
    if ! command -v wg &> /dev/null; then
        echo -e "${YELLOW}Installing WireGuard...${NC}"
        apt-get update && apt-get install -y wireguard
    fi
    
    # Create configurations
    create_wireguard_config
    create_postup_script
    create_postdown_script
    setup_docker_routing
    create_container_routing_script
    
    # Enable IP forwarding
    echo -e "${YELLOW}Enabling IP forwarding...${NC}"
    sysctl -w net.ipv4.ip_forward=1
    echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-wireguard.conf
    
    # Start WireGuard
    echo -e "${YELLOW}Starting WireGuard...${NC}"
    wg-quick down wg0 2>/dev/null || true
    wg-quick up wg0
    
    # Show status
    echo -e "\n${GREEN}Setup complete!${NC}"
    echo "=================="
    wg show
    
    echo -e "\n${YELLOW}Next steps:${NC}"
    echo "1. Start services: docker-compose -f docker-compose.yml -f docker-compose.networks.yml up -d"
    echo "2. Monitor: ./scripts/monitor-network-health.sh"
    echo "3. Test routing: ./scripts/test-network-routing.sh"
}

# Run main function
main "$@"