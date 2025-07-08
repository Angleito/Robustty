#!/bin/bash

# Detect network interfaces and generate configuration for multi-network Docker setup
# This script auto-detects VPN and default interfaces without hardcoding values

set -euo pipefail

echo "🔍 Network Configuration Auto-Detection"
echo "======================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to detect VPN interface
detect_vpn_interface() {
    local vpn_iface=""
    
    # Check for common VPN interface patterns
    for pattern in "tun" "proton" "ppp" "wg" "vpn"; do
        vpn_iface=$(ip link show | grep -E "^[0-9]+: ${pattern}" | awk -F': ' '{print $2}' | head -1)
        if [ -n "$vpn_iface" ]; then
            echo "$vpn_iface"
            return 0
        fi
    done
    
    # Check routing table for VPN routes
    vpn_iface=$(ip route | grep -E 'dev (tun|proton|ppp|wg)' | awk '{print $3}' | head -1)
    if [ -n "$vpn_iface" ]; then
        echo "$vpn_iface"
        return 0
    fi
    
    return 1
}

# Function to detect default interface
detect_default_interface() {
    local default_iface=""
    
    # Get default route interface
    default_iface=$(ip route | grep "^default" | awk '{print $5}' | grep -v -E "(tun|proton|ppp|wg|vpn)" | head -1)
    
    if [ -z "$default_iface" ]; then
        # Fallback to any ethernet/wifi interface
        default_iface=$(ip link show | grep -E "^[0-9]+: (eth|ens|enp|wlan|wlp)" | awk -F': ' '{print $2}' | head -1)
    fi
    
    echo "$default_iface"
}

# Function to get interface IP
get_interface_ip() {
    local iface=$1
    ip addr show "$iface" 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d'/' -f1 | head -1
}

# Function to test connectivity
test_connectivity() {
    local iface=$1
    local target=${2:-"8.8.8.8"}
    
    if [ -n "$iface" ]; then
        ping -c 1 -W 2 -I "$iface" "$target" &>/dev/null
        return $?
    fi
    return 1
}

# Function to suggest network subnets
suggest_subnets() {
    # Check existing Docker networks to avoid conflicts
    local used_subnets=$(docker network ls -q | xargs -I {} docker network inspect {} 2>/dev/null | grep -E '"Subnet"' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+' | sort -u)
    
    # Common private subnet ranges
    local suggested_subnets=(
        "172.28.0.0/16"
        "172.29.0.0/16"
        "172.30.0.0/16"
        "10.28.0.0/16"
        "10.29.0.0/16"
        "10.30.0.0/16"
        "192.168.228.0/24"
        "192.168.229.0/24"
        "192.168.230.0/24"
    )
    
    local vpn_subnet=""
    local direct_subnet=""
    local internal_subnet=""
    
    for subnet in "${suggested_subnets[@]}"; do
        if ! echo "$used_subnets" | grep -q "$subnet"; then
            if [ -z "$vpn_subnet" ]; then
                vpn_subnet="$subnet"
            elif [ -z "$direct_subnet" ]; then
                direct_subnet="$subnet"
            elif [ -z "$internal_subnet" ]; then
                internal_subnet="$subnet"
                break
            fi
        fi
    done
    
    echo "$vpn_subnet|$direct_subnet|$internal_subnet"
}

# Main detection
echo -e "\n${YELLOW}Detecting network interfaces...${NC}"

# Detect interfaces
VPN_INTERFACE=$(detect_vpn_interface || echo "")
DEFAULT_INTERFACE=$(detect_default_interface)

# Get IPs
VPN_IP=$(get_interface_ip "$VPN_INTERFACE" || echo "N/A")
DEFAULT_IP=$(get_interface_ip "$DEFAULT_INTERFACE" || echo "N/A")

# Test connectivity
echo -e "\n${YELLOW}Testing connectivity...${NC}"

if [ -n "$VPN_INTERFACE" ]; then
    if test_connectivity "$VPN_INTERFACE"; then
        echo -e "${GREEN}✓${NC} VPN interface ($VPN_INTERFACE) is active"
        VPN_STATUS="active"
    else
        echo -e "${RED}✗${NC} VPN interface ($VPN_INTERFACE) is not active"
        VPN_STATUS="inactive"
    fi
else
    echo -e "${YELLOW}!${NC} No VPN interface detected"
    VPN_STATUS="none"
fi

if test_connectivity "$DEFAULT_INTERFACE"; then
    echo -e "${GREEN}✓${NC} Default interface ($DEFAULT_INTERFACE) is active"
else
    echo -e "${RED}✗${NC} Default interface ($DEFAULT_INTERFACE) is not active"
fi

# Suggest subnets
SUBNET_SUGGESTION=$(suggest_subnets)
IFS='|' read -r VPN_SUBNET DIRECT_SUBNET INTERNAL_SUBNET <<< "$SUBNET_SUGGESTION"

# Generate configuration
echo -e "\n${YELLOW}Generating configuration...${NC}"

ENV_FILE=".env"
ENV_EXAMPLE=".env.example"

# Create network configuration section
cat << EOF

# Network Configuration (auto-detected)
# =====================================

# Network Interfaces
VPN_INTERFACE=${VPN_INTERFACE:-auto}
DEFAULT_INTERFACE=${DEFAULT_INTERFACE}

# Network Subnets (modify if conflicts exist)
VPN_NETWORK_SUBNET=${VPN_SUBNET}
DIRECT_NETWORK_SUBNET=${DIRECT_SUBNET}
INTERNAL_NETWORK_SUBNET=${INTERNAL_SUBNET}

# Routing Configuration
VPN_ROUTE_MARK=100
DIRECT_ROUTE_MARK=200
NETWORK_MTU=1450

# Network Selection Strategy
# Options: auto, force_vpn, force_direct, split
NETWORK_STRATEGY=auto

# Service-specific network preferences
DISCORD_USE_VPN=true
YOUTUBE_USE_VPN=false
RUMBLE_USE_VPN=false
ODYSEE_USE_VPN=false

EOF

# Summary
echo -e "\n${GREEN}Configuration Summary:${NC}"
echo "========================"
echo "VPN Interface:      ${VPN_INTERFACE:-Not detected} (${VPN_IP})"
echo "Default Interface:  ${DEFAULT_INTERFACE} (${DEFAULT_IP})"
echo "VPN Status:         ${VPN_STATUS}"
echo ""
echo "Suggested Subnets:"
echo "  VPN Network:      ${VPN_SUBNET}"
echo "  Direct Network:   ${DIRECT_SUBNET}"
echo "  Internal Network: ${INTERNAL_SUBNET}"

# Save configuration
echo -e "\n${YELLOW}Would you like to:${NC}"
echo "1) Append configuration to ${ENV_FILE}"
echo "2) Save as ${ENV_FILE}.network"
echo "3) Display only (no save)"
echo -n "Choose option [1-3]: "
read -r option

case $option in
    1)
        # Backup existing file
        if [ -f "$ENV_FILE" ]; then
            cp "$ENV_FILE" "${ENV_FILE}.backup"
            echo -e "${GREEN}✓${NC} Backed up existing ${ENV_FILE}"
        fi
        
        # Append configuration
        cat << EOF >> "$ENV_FILE"

# Network Configuration (auto-detected on $(date))
# =====================================
VPN_INTERFACE=${VPN_INTERFACE:-auto}
DEFAULT_INTERFACE=${DEFAULT_INTERFACE}
VPN_NETWORK_SUBNET=${VPN_SUBNET}
DIRECT_NETWORK_SUBNET=${DIRECT_SUBNET}
INTERNAL_NETWORK_SUBNET=${INTERNAL_SUBNET}
VPN_ROUTE_MARK=100
DIRECT_ROUTE_MARK=200
NETWORK_MTU=1450
NETWORK_STRATEGY=auto
DISCORD_USE_VPN=true
YOUTUBE_USE_VPN=false
RUMBLE_USE_VPN=false
ODYSEE_USE_VPN=false
EOF
        echo -e "${GREEN}✓${NC} Configuration appended to ${ENV_FILE}"
        ;;
    2)
        cat << EOF > "${ENV_FILE}.network"
# Network Configuration (auto-detected on $(date))
# =====================================
VPN_INTERFACE=${VPN_INTERFACE:-auto}
DEFAULT_INTERFACE=${DEFAULT_INTERFACE}
VPN_NETWORK_SUBNET=${VPN_SUBNET}
DIRECT_NETWORK_SUBNET=${DIRECT_SUBNET}
INTERNAL_NETWORK_SUBNET=${INTERNAL_SUBNET}
VPN_ROUTE_MARK=100
DIRECT_ROUTE_MARK=200
NETWORK_MTU=1450
NETWORK_STRATEGY=auto
DISCORD_USE_VPN=true
YOUTUBE_USE_VPN=false
RUMBLE_USE_VPN=false
ODYSEE_USE_VPN=false
EOF
        echo -e "${GREEN}✓${NC} Configuration saved to ${ENV_FILE}.network"
        ;;
    3)
        echo -e "${YELLOW}!${NC} Configuration displayed only (not saved)"
        ;;
esac

echo -e "\n${GREEN}Detection complete!${NC}"
echo "Next steps:"
echo "1. Review the configuration above"
echo "2. Run: docker-compose -f docker-compose.yml -f docker-compose.networks.yml up -d"
echo "3. Monitor with: ./scripts/monitor-network-health.sh"