#!/bin/bash

# Network Validation Script for Robustty Discord Bot
# This script performs comprehensive network validation for VPS deployments

set -e

# Configuration
SCRIPT_NAME="$(basename "$0")"
LOG_FILE="/tmp/robustty-network-validation.log"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" | tee -a "$LOG_FILE" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" | tee -a "$LOG_FILE" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" | tee -a "$LOG_FILE" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" | tee -a "$LOG_FILE" ;;
    esac
    echo "$timestamp [$level] $message" >> "$LOG_FILE"
}

# Initialize validation results
declare -A validation_results
total_checks=0
passed_checks=0

# Test function template
run_test() {
    local test_name="$1"
    local test_command="$2"
    local success_message="$3"
    local failure_message="$4"
    
    ((total_checks++))
    log INFO "Testing: $test_name"
    
    if eval "$test_command" >/dev/null 2>&1; then
        log INFO "✅ $success_message"
        validation_results["$test_name"]="PASS"
        ((passed_checks++))
        return 0
    else
        log WARN "❌ $failure_message"
        validation_results["$test_name"]="FAIL"
        return 1
    fi
}

# DNS Resolution Tests
test_dns_resolution() {
    log INFO "🌐 Testing DNS Resolution..."
    
    local dns_domains=(
        "discord.com"
        "gateway.discord.gg"
        "googleapis.com"
        "apify.com"
        "github.com"
    )
    
    for domain in "${dns_domains[@]}"; do
        run_test "DNS_$domain" \
                 "nslookup $domain" \
                 "$domain resolves correctly" \
                 "$domain failed to resolve"
    done
    
    # Test different DNS servers
    run_test "DNS_Google" \
             "nslookup discord.com 8.8.8.8" \
             "Google DNS (8.8.8.8) working" \
             "Google DNS (8.8.8.8) failed"
    
    run_test "DNS_Cloudflare" \
             "nslookup discord.com 1.1.1.1" \
             "Cloudflare DNS (1.1.1.1) working" \
             "Cloudflare DNS (1.1.1.1) failed"
}

# Connectivity Tests
test_connectivity() {
    log INFO "🔗 Testing Network Connectivity..."
    
    # Test basic internet connectivity
    run_test "Ping_Google" \
             "ping -c 3 8.8.8.8" \
             "Internet connectivity confirmed" \
             "No internet connectivity"
    
    # Test HTTPS connectivity to critical services
    local https_endpoints=(
        "https://discord.com/api/v10/gateway"
        "https://googleapis.com"
        "https://github.com"
    )
    
    for endpoint in "${https_endpoints[@]}"; do
        local service_name=$(echo "$endpoint" | sed 's|https://||' | cut -d'/' -f1)
        run_test "HTTPS_$service_name" \
                 "curl -s --max-time 10 --connect-timeout 5 '$endpoint'" \
                 "$service_name HTTPS accessible" \
                 "$service_name HTTPS unreachable"
    done
    
    # Test specific Discord endpoints
    run_test "Discord_Gateway" \
             "curl -s --max-time 10 'https://discord.com/api/v10/gateway'" \
             "Discord Gateway API accessible" \
             "Discord Gateway API unreachable"
}

# Port Tests
test_ports() {
    log INFO "🔌 Testing Port Availability..."
    
    # Check if required ports are available
    local required_ports=(8080 6379)
    
    for port in "${required_ports[@]}"; do
        run_test "Port_$port" \
                 "! ss -tlnp | grep -q ':$port '" \
                 "Port $port is available" \
                 "Port $port is already in use"
    done
    
    # Test outbound port connectivity
    if command -v nc >/dev/null 2>&1; then
        run_test "Outbound_443" \
                 "timeout 10 nc -z discord.com 443" \
                 "Outbound HTTPS (443) working" \
                 "Outbound HTTPS (443) blocked"
        
        run_test "Outbound_80" \
                 "timeout 10 nc -z google.com 80" \
                 "Outbound HTTP (80) working" \
                 "Outbound HTTP (80) blocked"
    else
        log WARN "netcat (nc) not available, skipping port tests"
    fi
}

# System Requirements Tests
test_system_requirements() {
    log INFO "💻 Testing System Requirements..."
    
    # Check if Docker is installed
    run_test "Docker_Installed" \
             "command -v docker" \
             "Docker is installed" \
             "Docker is not installed"
    
    # Check if Docker is running
    run_test "Docker_Running" \
             "docker info" \
             "Docker daemon is running" \
             "Docker daemon is not running"
    
    # Check if Docker Compose is installed
    run_test "DockerCompose_Installed" \
             "command -v docker-compose" \
             "Docker Compose is installed" \
             "Docker Compose is not installed"
    
    # Check available disk space
    run_test "Disk_Space" \
             "[ $(df / | tail -1 | awk '{print $4}') -gt 1048576 ]" \
             "Sufficient disk space (>1GB available)" \
             "Low disk space (<1GB available)"
    
    # Check available memory
    run_test "Memory" \
             "[ $(free -m | grep '^Mem:' | awk '{print $7}') -gt 512 ]" \
             "Sufficient memory (>512MB available)" \
             "Low memory (<512MB available)"
}

# SSL/TLS Tests
test_ssl_tls() {
    log INFO "🔒 Testing SSL/TLS Connectivity..."
    
    if command -v openssl >/dev/null 2>&1; then
        run_test "SSL_Discord" \
                 "echo | timeout 10 openssl s_client -connect discord.com:443 -verify_return_error" \
                 "SSL connection to Discord working" \
                 "SSL connection to Discord failed"
    else
        log WARN "OpenSSL not available, skipping SSL tests"
    fi
}

# Docker Network Tests (if Docker is available)
test_docker_networking() {
    if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
        log INFO "🐳 Docker not available, skipping Docker network tests"
        return
    fi
    
    log INFO "🐳 Testing Docker Networking..."
    
    # Test Docker network creation
    run_test "Docker_Network_Create" \
             "docker network create test-network-robustty" \
             "Can create Docker networks" \
             "Cannot create Docker networks"
    
    # Clean up test network
    docker network rm test-network-robustty >/dev/null 2>&1 || true
    
    # Test container DNS resolution
    run_test "Docker_DNS" \
             "docker run --rm alpine nslookup discord.com" \
             "Container DNS resolution working" \
             "Container DNS resolution failed"
}

# Firewall Tests
test_firewall() {
    log INFO "🛡️  Testing Firewall Configuration..."
    
    # Check UFW status if available
    if command -v ufw >/dev/null 2>&1; then
        local ufw_status=$(ufw status 2>/dev/null | head -1 || echo "")
        if [[ "$ufw_status" == *"Status: active"* ]]; then
            log INFO "UFW firewall is active"
            
            # Check if outbound connections are allowed
            if ufw status | grep -q "443.*ALLOW.*OUT"; then
                log INFO "✅ UFW allows outbound HTTPS"
            else
                log WARN "❌ UFW may block outbound HTTPS"
            fi
        else
            log INFO "UFW firewall is inactive or not configured"
        fi
    fi
    
    # Check iptables if available
    if command -v iptables >/dev/null 2>&1 && [[ $EUID -eq 0 ]]; then
        local output_policy=$(iptables -L OUTPUT | head -1 | awk '{print $4}' | tr -d '()')
        if [[ "$output_policy" == "ACCEPT" ]]; then
            log INFO "✅ iptables allows outbound connections"
        else
            log WARN "❌ iptables may block outbound connections"
        fi
    fi
}

# Network Performance Tests
test_network_performance() {
    log INFO "⚡ Testing Network Performance..."
    
    # Test latency to Discord
    local discord_latency=$(ping -c 5 discord.com 2>/dev/null | tail -1 | awk -F'/' '{print $5}' || echo "999")
    if (( $(echo "$discord_latency < 200" | bc -l 2>/dev/null || echo "0") )); then
        log INFO "✅ Good latency to Discord (${discord_latency}ms)"
        validation_results["Latency_Discord"]="PASS"
    else
        log WARN "❌ High latency to Discord (${discord_latency}ms)"
        validation_results["Latency_Discord"]="FAIL"
    fi
    ((total_checks++))
    if [[ "${validation_results["Latency_Discord"]}" == "PASS" ]]; then
        ((passed_checks++))
    fi
    
    # Test download speed (simple test)
    local speed_test_url="http://speedtest.ftp.otenet.gr/files/test1Mb.db"
    if curl -s --max-time 30 "$speed_test_url" >/dev/null 2>&1; then
        log INFO "✅ Download speed test passed"
        validation_results["Download_Speed"]="PASS"
        ((passed_checks++))
    else
        log WARN "❌ Download speed test failed"
        validation_results["Download_Speed"]="FAIL"
    fi
    ((total_checks++))
}

# Main validation function
run_validation() {
    log INFO "🔍 Starting Robustty Network Validation"
    log INFO "======================================"
    
    # Initialize log file
    echo "Robustty Network Validation - $(date)" > "$LOG_FILE"
    echo "================================================" >> "$LOG_FILE"
    
    # Run all test suites
    test_dns_resolution
    test_connectivity
    test_ports
    test_system_requirements
    test_ssl_tls
    test_docker_networking
    test_firewall
    test_network_performance
    
    echo ""
    log INFO "🏁 Validation Complete"
    log INFO "===================="
    
    # Calculate success rate
    local success_rate=$((passed_checks * 100 / total_checks))
    
    log INFO "Tests passed: $passed_checks/$total_checks ($success_rate%)"
    
    # Detailed results
    echo ""
    echo "Detailed Results:"
    echo "=================="
    for test in "${!validation_results[@]}"; do
        local status="${validation_results[$test]}"
        if [[ "$status" == "PASS" ]]; then
            echo -e "${GREEN}✅ $test${NC}"
        else
            echo -e "${RED}❌ $test${NC}"
        fi
    done
    
    echo ""
    echo "Log file: $LOG_FILE"
    
    # Return appropriate exit code
    if [[ $success_rate -ge 80 ]]; then
        log INFO "🎉 Network validation PASSED ($success_rate% success rate)"
        echo ""
        echo "Your system is ready for Robustty deployment!"
        return 0
    elif [[ $success_rate -ge 60 ]]; then
        log WARN "⚠️  Network validation PASSED with warnings ($success_rate% success rate)"
        echo ""
        echo "Your system should work but may have some issues. Consider fixing failed tests."
        return 0
    else
        log ERROR "❌ Network validation FAILED ($success_rate% success rate)"
        echo ""
        echo "Critical network issues detected. Please fix the failed tests before deployment."
        echo ""
        echo "Common fixes:"
        echo "1. DNS issues: sudo echo 'nameserver 8.8.8.8' > /etc/resolv.conf"
        echo "2. Firewall issues: sudo ufw allow out 443 && sudo ufw allow out 80"
        echo "3. Docker issues: curl -fsSL https://get.docker.com | sh"
        echo ""
        echo "For detailed troubleshooting, see: docs/VPS_TROUBLESHOOTING_FLOWCHARTS.md"
        return 1
    fi
}

# Help function
show_help() {
    cat << EOF
Robustty Network Validation Script

Usage: $SCRIPT_NAME [OPTIONS]

OPTIONS:
    -h, --help          Show this help message
    -v, --verbose       Enable verbose logging
    -q, --quick         Run only critical tests (faster)
    --dns-only          Test DNS resolution only
    --connectivity-only Test connectivity only
    --docker-only       Test Docker networking only

EXAMPLES:
    $SCRIPT_NAME                    # Run full validation
    $SCRIPT_NAME --quick            # Quick validation
    $SCRIPT_NAME --dns-only         # DNS tests only
    $SCRIPT_NAME --verbose          # Verbose output

EXIT CODES:
    0   Validation passed
    1   Validation failed
    2   Invalid arguments

DESCRIPTION:
    This script performs comprehensive network validation for VPS deployments
    of the Robustty Discord Bot. It tests DNS resolution, connectivity,
    port availability, system requirements, and Docker networking.

REQUIREMENTS:
    - Linux/Unix system
    - Basic networking tools (ping, nslookup, curl)
    - Optional: Docker, netcat, openssl

EOF
}

# Parse command line arguments
QUICK_MODE=false
VERBOSE=false
DNS_ONLY=false
CONNECTIVITY_ONLY=false
DOCKER_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -q|--quick)
            QUICK_MODE=true
            shift
            ;;
        --dns-only)
            DNS_ONLY=true
            shift
            ;;
        --connectivity-only)
            CONNECTIVITY_ONLY=true
            shift
            ;;
        --docker-only)
            DOCKER_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 2
            ;;
    esac
done

# Check for required tools
missing_tools=()
required_tools=("ping" "nslookup" "curl")

for tool in "${required_tools[@]}"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        missing_tools+=("$tool")
    fi
done

if [[ ${#missing_tools[@]} -gt 0 ]]; then
    log ERROR "Missing required tools: ${missing_tools[*]}"
    echo "Please install missing tools and try again."
    exit 1
fi

# Run validation based on mode
if [[ "$DNS_ONLY" == true ]]; then
    test_dns_resolution
elif [[ "$CONNECTIVITY_ONLY" == true ]]; then
    test_connectivity
elif [[ "$DOCKER_ONLY" == true ]]; then
    test_docker_networking
elif [[ "$QUICK_MODE" == true ]]; then
    # Quick mode - only critical tests
    test_dns_resolution
    test_connectivity
    run_test "Quick_Discord_API" \
             "curl -s --max-time 5 https://discord.com/api/v10/gateway" \
             "Discord API accessible" \
             "Discord API unreachable"
    ((total_checks++))
    if [[ $? -eq 0 ]]; then ((passed_checks++)); fi
    
    local success_rate=$((passed_checks * 100 / total_checks))
    if [[ $success_rate -ge 80 ]]; then
        log INFO "🎉 Quick validation PASSED"
        exit 0
    else
        log ERROR "❌ Quick validation FAILED"
        exit 1
    fi
else
    # Full validation
    run_validation
fi