#!/bin/bash

# VPS Network Diagnostics Script for Docker Containers
# Diagnoses common Docker networking issues on VPS deployments

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== VPS Docker Network Diagnostics ===${NC}\n"

# Function to check if running on VPS
check_vps_environment() {
    echo -e "${YELLOW}1. Checking Environment...${NC}"
    
    # Check if running in cloud environment
    if [ -f /sys/hypervisor/uuid ] && [ $(head -c 3 /sys/hypervisor/uuid) == "ec2" ]; then
        echo -e "   ${GREEN}✓${NC} Running on AWS EC2"
    elif [ -f /sys/class/dmi/id/product_name ] && grep -q "Google\|GCE" /sys/class/dmi/id/product_name; then
        echo -e "   ${GREEN}✓${NC} Running on Google Cloud"
    elif [ -f /sys/class/dmi/id/sys_vendor ] && grep -q "DigitalOcean" /sys/class/dmi/id/sys_vendor; then
        echo -e "   ${GREEN}✓${NC} Running on DigitalOcean"
    elif systemd-detect-virt -q; then
        VIRT=$(systemd-detect-virt)
        echo -e "   ${GREEN}✓${NC} Running in virtualized environment: $VIRT"
    else
        echo -e "   ${YELLOW}!${NC} Could not detect VPS environment"
    fi
    echo
}

# Function to check Docker installation
check_docker_status() {
    echo -e "${YELLOW}2. Checking Docker Status...${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "   ${RED}✗${NC} Docker is not installed"
        return 1
    fi
    
    echo -e "   ${GREEN}✓${NC} Docker is installed"
    
    if ! systemctl is-active --quiet docker; then
        echo -e "   ${RED}✗${NC} Docker service is not running"
        return 1
    fi
    
    echo -e "   ${GREEN}✓${NC} Docker service is running"
    
    # Check Docker version
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,$//')
    echo -e "   ${BLUE}ℹ${NC} Docker version: $DOCKER_VERSION"
    echo
}

# Function to check Docker networks
check_docker_networks() {
    echo -e "${YELLOW}3. Checking Docker Networks...${NC}"
    
    # List all Docker networks
    echo -e "   ${BLUE}Available networks:${NC}"
    docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" | sed 's/^/   /'
    
    # Check for custom network
    if docker network ls | grep -q "robustty-network"; then
        echo -e "\n   ${GREEN}✓${NC} Custom network 'robustty-network' exists"
        
        # Get network details
        NETWORK_INFO=$(docker network inspect robustty-network 2>/dev/null || echo "")
        if [ -n "$NETWORK_INFO" ]; then
            SUBNET=$(echo "$NETWORK_INFO" | jq -r '.[0].IPAM.Config[0].Subnet' 2>/dev/null || echo "N/A")
            GATEWAY=$(echo "$NETWORK_INFO" | jq -r '.[0].IPAM.Config[0].Gateway' 2>/dev/null || echo "N/A")
            echo -e "   ${BLUE}ℹ${NC} Subnet: $SUBNET"
            echo -e "   ${BLUE}ℹ${NC} Gateway: $GATEWAY"
        fi
    else
        echo -e "\n   ${YELLOW}!${NC} Custom network 'robustty-network' not found"
    fi
    echo
}

# Function to check iptables rules
check_iptables_rules() {
    echo -e "${YELLOW}4. Checking iptables Rules...${NC}"
    
    # Check if iptables is available
    if ! command -v iptables &> /dev/null; then
        echo -e "   ${RED}✗${NC} iptables not found"
        return 1
    fi
    
    # Check Docker chain
    if iptables -L DOCKER -n &> /dev/null; then
        echo -e "   ${GREEN}✓${NC} DOCKER chain exists"
    else
        echo -e "   ${RED}✗${NC} DOCKER chain missing"
    fi
    
    # Check DOCKER-USER chain
    if iptables -L DOCKER-USER -n &> /dev/null; then
        echo -e "   ${GREEN}✓${NC} DOCKER-USER chain exists"
        
        # Count rules in DOCKER-USER
        RULE_COUNT=$(iptables -L DOCKER-USER -n | grep -c "^[A-Z]" || true)
        echo -e "   ${BLUE}ℹ${NC} DOCKER-USER chain has $((RULE_COUNT - 2)) custom rules"
    else
        echo -e "   ${RED}✗${NC} DOCKER-USER chain missing"
    fi
    
    # Check INPUT chain for Docker
    if iptables -L INPUT -n | grep -q "docker0"; then
        echo -e "   ${GREEN}✓${NC} Docker bridge interface allowed in INPUT chain"
    else
        echo -e "   ${YELLOW}!${NC} Docker bridge interface not explicitly allowed in INPUT chain"
    fi
    
    # Check FORWARD chain
    if iptables -L FORWARD -n | grep -q "DOCKER"; then
        echo -e "   ${GREEN}✓${NC} Docker forwarding rules present"
    else
        echo -e "   ${RED}✗${NC} Docker forwarding rules missing"
    fi
    
    # Check NAT masquerading
    if iptables -t nat -L POSTROUTING -n | grep -q "MASQUERADE"; then
        echo -e "   ${GREEN}✓${NC} NAT masquerading enabled"
    else
        echo -e "   ${RED}✗${NC} NAT masquerading not configured"
    fi
    echo
}

# Function to check DNS configuration
check_dns_configuration() {
    echo -e "${YELLOW}5. Checking DNS Configuration...${NC}"
    
    # Check host DNS
    echo -e "   ${BLUE}Host DNS servers:${NC}"
    if [ -f /etc/resolv.conf ]; then
        grep "nameserver" /etc/resolv.conf | head -3 | sed 's/^/   /'
    else
        echo -e "   ${RED}✗${NC} /etc/resolv.conf not found"
    fi
    
    # Test host DNS resolution
    echo -e "\n   ${BLUE}Testing host DNS resolution:${NC}"
    if host google.com &> /dev/null; then
        echo -e "   ${GREEN}✓${NC} Host can resolve google.com"
    else
        echo -e "   ${RED}✗${NC} Host cannot resolve google.com"
    fi
    
    # Check Docker daemon DNS settings
    if [ -f /etc/docker/daemon.json ]; then
        echo -e "\n   ${BLUE}Docker daemon DNS configuration:${NC}"
        DNS_CONFIG=$(jq '.dns // empty' /etc/docker/daemon.json 2>/dev/null || echo "")
        if [ -n "$DNS_CONFIG" ] && [ "$DNS_CONFIG" != "null" ]; then
            echo "   $DNS_CONFIG"
        else
            echo -e "   ${YELLOW}!${NC} No custom DNS configured in daemon.json"
        fi
    fi
    echo
}

# Function to test container networking
test_container_networking() {
    echo -e "${YELLOW}6. Testing Container Networking...${NC}"
    
    # Check if robustty container is running
    if docker ps | grep -q "robustty"; then
        CONTAINER_NAME=$(docker ps --format "{{.Names}}" | grep "robustty" | head -1)
        echo -e "   ${GREEN}✓${NC} Found running container: $CONTAINER_NAME"
        
        # Test DNS inside container
        echo -e "\n   ${BLUE}Testing DNS resolution inside container:${NC}"
        if docker exec "$CONTAINER_NAME" nslookup google.com &> /dev/null; then
            echo -e "   ${GREEN}✓${NC} Container can resolve google.com"
        else
            echo -e "   ${RED}✗${NC} Container cannot resolve google.com"
            
            # Try with explicit DNS
            echo -e "   ${BLUE}Trying with explicit DNS (8.8.8.8):${NC}"
            if docker exec "$CONTAINER_NAME" nslookup google.com 8.8.8.8 &> /dev/null; then
                echo -e "   ${YELLOW}!${NC} Resolution works with explicit DNS server"
            else
                echo -e "   ${RED}✗${NC} DNS resolution failed even with explicit server"
            fi
        fi
        
        # Test outbound connectivity
        echo -e "\n   ${BLUE}Testing outbound connectivity:${NC}"
        if docker exec "$CONTAINER_NAME" ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
            echo -e "   ${GREEN}✓${NC} Container can reach 8.8.8.8"
        else
            echo -e "   ${RED}✗${NC} Container cannot reach 8.8.8.8"
        fi
        
        # Test HTTPS connectivity
        if docker exec "$CONTAINER_NAME" curl -s -m 5 https://www.google.com > /dev/null; then
            echo -e "   ${GREEN}✓${NC} Container can make HTTPS requests"
        else
            echo -e "   ${RED}✗${NC} Container cannot make HTTPS requests"
        fi
        
        # Check container's resolv.conf
        echo -e "\n   ${BLUE}Container DNS configuration:${NC}"
        docker exec "$CONTAINER_NAME" cat /etc/resolv.conf | grep "nameserver" | head -3 | sed 's/^/   /'
        
    else
        echo -e "   ${YELLOW}!${NC} No running robustty container found"
        
        # Create test container
        echo -e "\n   ${BLUE}Creating test container...${NC}"
        if docker run --rm -d --name network-test --network robustty-network alpine:latest sleep 300 &> /dev/null; then
            echo -e "   ${GREEN}✓${NC} Test container created"
            
            # Install necessary tools
            docker exec network-test apk add --no-cache curl bind-tools &> /dev/null
            
            # Test from test container
            echo -e "\n   ${BLUE}Testing from test container:${NC}"
            if docker exec network-test nslookup google.com &> /dev/null; then
                echo -e "   ${GREEN}✓${NC} DNS resolution works"
            else
                echo -e "   ${RED}✗${NC} DNS resolution failed"
            fi
            
            if docker exec network-test ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
                echo -e "   ${GREEN}✓${NC} Can reach 8.8.8.8"
            else
                echo -e "   ${RED}✗${NC} Cannot reach 8.8.8.8"
            fi
            
            # Cleanup
            docker stop network-test &> /dev/null
        else
            echo -e "   ${RED}✗${NC} Failed to create test container"
        fi
    fi
    echo
}

# Function to check MTU settings
check_mtu_settings() {
    echo -e "${YELLOW}7. Checking MTU Settings...${NC}"
    
    # Get host interface MTU
    DEFAULT_IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
    if [ -n "$DEFAULT_IFACE" ]; then
        HOST_MTU=$(ip link show "$DEFAULT_IFACE" | grep -oP 'mtu \K\d+')
        echo -e "   ${BLUE}ℹ${NC} Host interface ($DEFAULT_IFACE) MTU: $HOST_MTU"
    fi
    
    # Check Docker bridge MTU
    if ip link show docker0 &> /dev/null; then
        DOCKER_MTU=$(ip link show docker0 | grep -oP 'mtu \K\d+')
        echo -e "   ${BLUE}ℹ${NC} Docker bridge (docker0) MTU: $DOCKER_MTU"
        
        if [ "$DOCKER_MTU" -gt "${HOST_MTU:-1500}" ]; then
            echo -e "   ${YELLOW}!${NC} Docker MTU is larger than host MTU - may cause issues"
        fi
    fi
    
    # Check custom network MTU
    if docker network ls | grep -q "robustty-network"; then
        NETWORK_MTU=$(docker network inspect robustty-network | jq -r '.[0].Options."com.docker.network.driver.mtu" // empty' 2>/dev/null)
        if [ -n "$NETWORK_MTU" ]; then
            echo -e "   ${BLUE}ℹ${NC} Custom network MTU: $NETWORK_MTU"
        else
            echo -e "   ${YELLOW}!${NC} No custom MTU set for robustty-network"
        fi
    fi
    echo
}

# Function to check for common VPS provider issues
check_vps_specific_issues() {
    echo -e "${YELLOW}8. Checking VPS-Specific Issues...${NC}"
    
    # Check for UFW
    if command -v ufw &> /dev/null; then
        if ufw status | grep -q "Status: active"; then
            echo -e "   ${YELLOW}!${NC} UFW firewall is active - may conflict with Docker"
            
            # Check if Docker rules are allowed
            if ufw status | grep -q "2375\|2376\|2377"; then
                echo -e "   ${GREEN}✓${NC} Docker ports appear to be allowed in UFW"
            else
                echo -e "   ${YELLOW}!${NC} Docker ports not explicitly allowed in UFW"
            fi
        else
            echo -e "   ${GREEN}✓${NC} UFW is inactive"
        fi
    fi
    
    # Check for firewalld
    if command -v firewall-cmd &> /dev/null; then
        if systemctl is-active --quiet firewalld; then
            echo -e "   ${YELLOW}!${NC} firewalld is active - may conflict with Docker"
            
            # Check Docker zone
            if firewall-cmd --get-zones | grep -q docker; then
                echo -e "   ${GREEN}✓${NC} Docker zone exists in firewalld"
            else
                echo -e "   ${YELLOW}!${NC} Docker zone not configured in firewalld"
            fi
        fi
    fi
    
    # Check kernel modules
    echo -e "\n   ${BLUE}Checking required kernel modules:${NC}"
    for module in br_netfilter overlay; do
        if lsmod | grep -q "^$module"; then
            echo -e "   ${GREEN}✓${NC} $module module loaded"
        else
            echo -e "   ${YELLOW}!${NC} $module module not loaded"
        fi
    done
    
    # Check sysctl settings
    echo -e "\n   ${BLUE}Checking sysctl settings:${NC}"
    if [ "$(sysctl -n net.ipv4.ip_forward)" = "1" ]; then
        echo -e "   ${GREEN}✓${NC} IP forwarding enabled"
    else
        echo -e "   ${RED}✗${NC} IP forwarding disabled"
    fi
    
    if [ "$(sysctl -n net.bridge.bridge-nf-call-iptables 2>/dev/null)" = "1" ]; then
        echo -e "   ${GREEN}✓${NC} Bridge netfilter enabled"
    else
        echo -e "   ${YELLOW}!${NC} Bridge netfilter not enabled"
    fi
    echo
}

# Function to generate diagnostic summary
generate_summary() {
    echo -e "${YELLOW}9. Diagnostic Summary${NC}"
    echo -e "${BLUE}${'─' * 50}${NC}"
    
    # Collect all issues
    ISSUES=()
    
    # Check for critical issues
    if ! systemctl is-active --quiet docker; then
        ISSUES+=("Docker service not running")
    fi
    
    if ! iptables -L DOCKER -n &> /dev/null; then
        ISSUES+=("Docker iptables chains missing")
    fi
    
    if ! iptables -t nat -L POSTROUTING -n | grep -q "MASQUERADE"; then
        ISSUES+=("NAT masquerading not configured")
    fi
    
    if [ "$(sysctl -n net.ipv4.ip_forward)" != "1" ]; then
        ISSUES+=("IP forwarding disabled")
    fi
    
    # Print issues
    if [ ${#ISSUES[@]} -gt 0 ]; then
        echo -e "${RED}Critical Issues Found:${NC}"
        for issue in "${ISSUES[@]}"; do
            echo -e "  ${RED}✗${NC} $issue"
        done
        echo
        echo -e "${YELLOW}Run './scripts/fix-vps-network.sh' to attempt automatic fixes${NC}"
    else
        echo -e "${GREEN}No critical issues found!${NC}"
        echo -e "\nIf you're still experiencing issues, check:"
        echo -e "  - Container logs: docker-compose logs robustty"
        echo -e "  - Specific platform errors in the application"
        echo -e "  - VPS provider-specific firewall rules"
    fi
    
    echo -e "${BLUE}${'─' * 50}${NC}"
}

# Main execution
main() {
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Some diagnostics require root access. Run with sudo for complete results.${NC}\n"
    fi
    
    check_vps_environment
    check_docker_status || exit 1
    check_docker_networks
    check_iptables_rules
    check_dns_configuration
    test_container_networking
    check_mtu_settings
    check_vps_specific_issues
    generate_summary
}

# Run main function
main