#!/bin/bash

# Monitor Docker multi-network and WireGuard health
# Shows routing status, connectivity tests, and troubleshooting info

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🔍 Network Health Monitor"
echo "========================"
echo "Time: $(date)"
echo ""

# Function to check WireGuard status
check_wireguard() {
    echo -e "${BLUE}WireGuard Status:${NC}"
    echo "----------------"
    
    if command -v wg &> /dev/null; then
        if sudo wg show wg0 &> /dev/null; then
            echo -e "${GREEN}✓ WireGuard is running${NC}"
            sudo wg show wg0 | grep -E "(endpoint|latest handshake|transfer)" | sed 's/^/  /'
            
            # Check if interface exists
            if ip link show wg0 &> /dev/null; then
                WG_IP=$(ip addr show wg0 | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
                echo -e "  Interface IP: ${WG_IP}"
            fi
        else
            echo -e "${RED}✗ WireGuard is not running${NC}"
            echo "  Run: sudo wg-quick up wg0"
        fi
    else
        echo -e "${YELLOW}⚠ WireGuard not installed${NC}"
    fi
    echo ""
}

# Function to check Docker networks
check_docker_networks() {
    echo -e "${BLUE}Docker Networks:${NC}"
    echo "---------------"
    
    # Expected networks
    networks=("vpn-network" "direct-network" "internal-network")
    
    for network in "${networks[@]}"; do
        if docker network inspect "$network" &> /dev/null; then
            subnet=$(docker network inspect "$network" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}')
            containers=$(docker network inspect "$network" --format '{{len .Containers}}')
            echo -e "${GREEN}✓ $network${NC}"
            echo "  Subnet: $subnet"
            echo "  Containers: $containers"
        else
            echo -e "${RED}✗ $network not found${NC}"
            echo "  Create with: docker network create $network"
        fi
    done
    echo ""
}

# Function to check container routing
check_container_routing() {
    echo -e "${BLUE}Container Network Assignment:${NC}"
    echo "----------------------------"
    
    # Check robustty container
    if docker ps --format "{{.Names}}" | grep -q "robustty"; then
        echo "robustty-bot:"
        docker inspect robustty-bot --format '{{range $net, $conf := .NetworkSettings.Networks}}  - {{$net}}: {{range $conf.IPAMConfig}}{{.IPv4Address}}{{else}}{{$conf.IPAddress}}{{end}}{{"\n"}}{{end}}' 2>/dev/null || echo "  Not running"
    else
        echo -e "${YELLOW}⚠ robustty-bot not running${NC}"
    fi
    
    # Check other services
    for service in "robustty-redis" "robustty-youtube-music"; do
        if docker ps --format "{{.Names}}" | grep -q "$service"; then
            echo "$service:"
            docker inspect "$service" --format '{{range $net, $conf := .NetworkSettings.Networks}}  - {{$net}}: {{$conf.IPAddress}}{{"\n"}}{{end}}' 2>/dev/null
        fi
    done
    echo ""
}

# Function to test connectivity
test_connectivity() {
    echo -e "${BLUE}Connectivity Tests:${NC}"
    echo "------------------"
    
    # Test Discord connectivity (should go through VPN)
    echo -n "Discord API (via VPN): "
    if curl -s -m 5 https://discord.com/api/v10/gateway &> /dev/null; then
        echo -e "${GREEN}✓ Connected${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
    
    # Test YouTube (should bypass VPN)
    echo -n "YouTube API (direct): "
    if curl -s -m 5 https://www.googleapis.com/youtube/v3/ &> /dev/null; then
        echo -e "${GREEN}✓ Connected${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
    
    # Test from within container if running
    if docker ps --format "{{.Names}}" | grep -q "robustty-bot"; then
        echo ""
        echo "Container connectivity:"
        
        # Test Discord from container
        echo -n "  Discord (from container): "
        docker exec robustty-bot curl -s -m 5 https://discord.com/api/v10/gateway &> /dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}"
        
        # Test YouTube from container
        echo -n "  YouTube (from container): "
        docker exec robustty-bot curl -s -m 5 https://www.youtube.com &> /dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}"
    fi
    echo ""
}

# Function to check routing tables
check_routing() {
    echo -e "${BLUE}Routing Configuration:${NC}"
    echo "--------------------"
    
    # Check if custom routing tables exist
    if ip rule show | grep -q "fwmark 0x51820"; then
        echo -e "${GREEN}✓ WireGuard routing rules active${NC}"
    else
        echo -e "${YELLOW}⚠ WireGuard routing rules not found${NC}"
    fi
    
    # Show routing marks
    echo "Active routing marks:"
    ip rule show | grep -E "fwmark|lookup" | head -5 | sed 's/^/  /'
    echo ""
}

# Function to show troubleshooting tips
show_troubleshooting() {
    echo -e "${BLUE}Quick Troubleshooting:${NC}"
    echo "--------------------"
    
    if ! sudo wg show wg0 &> /dev/null; then
        echo "1. Start WireGuard:"
        echo "   sudo ./scripts/setup-wireguard-routing.sh"
        echo ""
    fi
    
    if ! docker network inspect vpn-network &> /dev/null; then
        echo "2. Create Docker networks:"
        echo "   docker-compose -f docker-compose.yml -f docker-compose.networks.yml up --no-start"
        echo ""
    fi
    
    echo "3. Restart services with multi-network:"
    echo "   docker-compose -f docker-compose.yml -f docker-compose.networks.yml up -d"
    echo ""
    echo "4. Check container logs:"
    echo "   docker-compose logs -f robustty"
    echo ""
}

# Function to test specific service routing
test_service_routing() {
    echo -e "${BLUE}Service-Specific Routing Tests:${NC}"
    echo "------------------------------"
    
    if docker ps --format "{{.Names}}" | grep -q "robustty-bot"; then
        # Get external IPs as seen by services
        echo "External IPs seen by services:"
        
        echo -n "  Discord sees IP: "
        docker exec robustty-bot sh -c 'wget -qO- --timeout=5 https://ipinfo.io/ip 2>/dev/null || echo "Failed"' || echo "N/A"
        
        # Test with direct network
        echo -n "  YouTube sees IP: "
        docker exec robustty-bot sh -c 'wget -qO- --timeout=5 --bind-address=$(ip addr show | grep "172.29" | awk "{print \$2}" | cut -d"/" -f1) https://ipinfo.io/ip 2>/dev/null || echo "Failed"' 2>/dev/null || echo "N/A"
    else
        echo -e "${YELLOW}⚠ Container not running${NC}"
    fi
    echo ""
}

# Main monitoring loop
main() {
    if [ "${1:-}" = "--watch" ]; then
        # Continuous monitoring mode
        while true; do
            clear
            check_wireguard
            check_docker_networks
            check_container_routing
            test_connectivity
            check_routing
            test_service_routing
            
            echo -e "${YELLOW}Refreshing in 30 seconds... (Ctrl+C to exit)${NC}"
            sleep 30
        done
    else
        # Single run
        check_wireguard
        check_docker_networks
        check_container_routing
        test_connectivity
        check_routing
        test_service_routing
        show_troubleshooting
        
        echo -e "${YELLOW}Tip: Run with --watch for continuous monitoring${NC}"
    fi
}

# Run main function
main "$@"