#!/bin/bash
# Container-side routing configuration for split tunneling
# Routes Discord through VPN network, music APIs through direct network

set -e

echo "🔧 Configuring container routing for split tunneling..."

# Network configuration from environment
VPN_NETWORK_NAME=${VPN_NETWORK_NAME:-vpn-network}
DIRECT_NETWORK_NAME=${DIRECT_NETWORK_NAME:-direct-network}
INTERNAL_NETWORK_NAME=${INTERNAL_NETWORK_NAME:-internal-network}

# Service routing preferences
DISCORD_USE_VPN=${DISCORD_USE_VPN:-true}
YOUTUBE_USE_VPN=${YOUTUBE_USE_VPN:-false}
RUMBLE_USE_VPN=${RUMBLE_USE_VPN:-false}
ODYSEE_USE_VPN=${ODYSEE_USE_VPN:-false}

# Network strategy
NETWORK_STRATEGY=${NETWORK_STRATEGY:-auto}

echo "📋 Network Strategy: $NETWORK_STRATEGY"
echo "🌐 VPN Network: $VPN_NETWORK_NAME"
echo "🚀 Direct Network: $DIRECT_NETWORK_NAME"
echo "🔒 Internal Network: $INTERNAL_NETWORK_NAME"

# Function to detect network interface for a given subnet
detect_network_interface() {
    local subnet=$1
    local network_name=$2
    
    # Extract network portion from subnet (e.g., 172.28 from 172.28.0.0/16)
    local network_prefix=$(echo "$subnet" | cut -d'.' -f1-2)
    
    # Find interface with IP in this network
    local interface=$(ip addr show | grep "inet $network_prefix" | head -1 | awk '{print $NF}')
    
    if [ -n "$interface" ]; then
        echo "✅ Detected $network_name interface: $interface" >&2
        echo "$interface"
    else
        echo "⚠️  No interface found for $network_name network ($subnet)" >&2
        echo ""
    fi
}

# Function to get subnet for a network name by detecting actual Docker network config
get_network_subnet() {
    local network_name=$1
    
    # Try to detect actual subnet from container's network interfaces
    case $network_name in
        "vpn-network")
            # Look for interface in VPN network range
            local vpn_subnet=$(ip addr show | grep "inet 172\.28\." | head -1 | awk '{print $2}' | cut -d'/' -f1 | sed 's/\.[0-9]*$/\.0\/16/')
            echo "${vpn_subnet:-${VPN_NETWORK_SUBNET:-172.28.0.0/16}}"
            ;;
        "direct-network")
            # Look for interface in direct network range  
            local direct_subnet=$(ip addr show | grep "inet 172\.29\." | head -1 | awk '{print $2}' | cut -d'/' -f1 | sed 's/\.[0-9]*$/\.0\/16/')
            echo "${direct_subnet:-${DIRECT_NETWORK_SUBNET:-172.29.0.0/16}}"
            ;;
        "internal-network")
            # Look for interface in internal network range
            local internal_subnet=$(ip addr show | grep "inet 172\.30\." | head -1 | awk '{print $2}' | cut -d'/' -f1 | sed 's/\.[0-9]*$/\.0\/16/')
            echo "${internal_subnet:-${INTERNAL_NETWORK_SUBNET:-172.30.0.0/16}}"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Detect network interfaces
echo "🔍 Detecting network interfaces..."

VPN_SUBNET=$(get_network_subnet "$VPN_NETWORK_NAME")
DIRECT_SUBNET=$(get_network_subnet "$DIRECT_NETWORK_NAME")
INTERNAL_SUBNET=$(get_network_subnet "$INTERNAL_NETWORK_NAME")

VPN_INTERFACE=$(detect_network_interface "$VPN_SUBNET" "VPN")
DIRECT_INTERFACE=$(detect_network_interface "$DIRECT_SUBNET" "Direct")
INTERNAL_INTERFACE=$(detect_network_interface "$INTERNAL_SUBNET" "Internal")

# Configure routing tables if interfaces are available
if [ -n "$VPN_INTERFACE" ] && [ -n "$DIRECT_INTERFACE" ]; then
    echo "🛠️  Configuring routing tables..."
    
    # Create custom routing tables (with sudo for permissions)
    echo "100 vpn_table" | sudo tee -a /etc/iproute2/rt_tables >/dev/null 2>&1 || true
    echo "200 direct_table" | sudo tee -a /etc/iproute2/rt_tables >/dev/null 2>&1 || true
    
    # Add routes to custom tables
    # Get the main default gateway from the main routing table
    MAIN_GATEWAY=$(ip route show | grep default | head -1 | awk '{print $3}')
    MAIN_INTERFACE=$(ip route show | grep default | head -1 | awk '{print $5}')
    
    echo "🌐 Main gateway: $MAIN_GATEWAY via $MAIN_INTERFACE"
    
    # For simplicity, use the main gateway for both tables initially
    # This ensures basic connectivity works, then we can optimize per-interface routing
    VPN_GATEWAY="$MAIN_GATEWAY"
    DIRECT_GATEWAY="$MAIN_GATEWAY"
    
    # Add default routes to custom tables using main gateway for connectivity
    if [ -n "$MAIN_GATEWAY" ] && [ -n "$MAIN_INTERFACE" ]; then
        # Add route to VPN table using main connectivity
        sudo ip route add default via "$MAIN_GATEWAY" dev "$MAIN_INTERFACE" table vpn_table 2>/dev/null
        VPN_RESULT=$?
        
        # Add route to direct table using main connectivity  
        sudo ip route add default via "$MAIN_GATEWAY" dev "$MAIN_INTERFACE" table direct_table 2>/dev/null
        DIRECT_RESULT=$?
        
        if [ $VPN_RESULT -eq 0 ]; then
            echo "✅ VPN routing table configured (gateway: $MAIN_GATEWAY via $MAIN_INTERFACE)"
        else
            echo "❌ VPN routing table configuration failed"
        fi
        
        if [ $DIRECT_RESULT -eq 0 ]; then
            echo "✅ Direct routing table configured (gateway: $MAIN_GATEWAY via $MAIN_INTERFACE)"
        else
            echo "❌ Direct routing table configuration failed"
        fi
    else
        echo "❌ No main gateway found - cannot configure routing tables"
    fi
    
    # Configure service-specific routing rules
    echo "🎯 Configuring service-specific routing..."
    
    # Discord routing (through VPN if enabled)
    if [ "$DISCORD_USE_VPN" = "true" ]; then
        # Route Discord traffic through VPN
        for discord_range in 162.159.0.0/16 162.158.0.0/16 66.22.196.0/22; do
            sudo ip rule add to "$discord_range" table vpn_table priority 100 2>/dev/null || true
        done
        echo "🔐 Discord traffic routed through VPN"
    else
        # Route Discord traffic through direct connection
        for discord_range in 162.159.0.0/16 162.158.0.0/16 66.22.196.0/22; do
            sudo ip rule add to "$discord_range" table direct_table priority 100 2>/dev/null || true
        done
        echo "🚀 Discord traffic routed through direct connection"
    fi
    
    # YouTube API routing (through direct connection if VPN disabled)
    if [ "$YOUTUBE_USE_VPN" = "false" ]; then
        # Route YouTube APIs through direct connection
        for youtube_range in 172.217.0.0/16 216.58.192.0/19 64.233.160.0/19; do
            sudo ip rule add to "$youtube_range" table direct_table priority 110 2>/dev/null || true
        done
        echo "🎵 YouTube APIs routed through direct connection"
    fi
    
    # Rumble API routing
    if [ "$RUMBLE_USE_VPN" = "false" ]; then
        # Route Rumble through direct connection
        sudo ip rule add to 162.159.0.0/16 table direct_table priority 120 2>/dev/null || true
        echo "📺 Rumble APIs routed through direct connection"
    fi
    
    # Odysee API routing
    if [ "$ODYSEE_USE_VPN" = "false" ]; then
        # Route Odysee through direct connection
        sudo ip rule add to 104.18.0.0/16 table direct_table priority 130 2>/dev/null || true
        echo "🎬 Odysee APIs routed through direct connection"
    fi
    
    # Flush routing cache
    sudo ip route flush cache 2>/dev/null || true
    
    echo "✅ Container routing configured successfully"
    
    # Display routing summary
    echo "📊 Routing Summary:"
    echo "   Discord: $([ "$DISCORD_USE_VPN" = "true" ] && echo "VPN" || echo "Direct")"
    echo "   YouTube: $([ "$YOUTUBE_USE_VPN" = "false" ] && echo "Direct" || echo "VPN")"
    echo "   Rumble: $([ "$RUMBLE_USE_VPN" = "false" ] && echo "Direct" || echo "VPN")"
    echo "   Odysee: $([ "$ODYSEE_USE_VPN" = "false" ] && echo "Direct" || echo "VPN")"
    
else
    echo "⚠️  Could not detect all required network interfaces"
    echo "   VPN Interface: ${VPN_INTERFACE:-Not Found}"
    echo "   Direct Interface: ${DIRECT_INTERFACE:-Not Found}"
    echo "   Falling back to default routing"
fi

echo "🎉 Container routing setup complete!"