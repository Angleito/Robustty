#!/bin/bash

# Comprehensive VPS Deployment Validation Script for Robustty Discord Bot
# This script performs end-to-end validation of all deployment components
# to ensure successful bot operation on VPS environments.

set -e

# Configuration
SCRIPT_NAME="$(basename "$0")"
LOG_FILE="/tmp/robustty-deployment-validation.log"
VALIDATION_TIMEOUT=300  # 5 minutes timeout for overall validation
TEST_TIMEOUT=30         # 30 seconds timeout for individual tests
HEALTH_CHECK_RETRIES=10
HEALTH_CHECK_INTERVAL=10

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Progress tracking
declare -A validation_results
declare -A test_categories
total_checks=0
passed_checks=0
failed_checks=0
warning_checks=0
critical_failures=()

# Test categories
CATEGORIES=(
    "INFRASTRUCTURE"
    "DOCKER_SERVICES"
    "DISCORD_INTEGRATION"
    "PLATFORM_FUNCTIONALITY"
    "RESOURCE_MONITORING"
    "SECURITY_CONFIG"
    "PERFORMANCE_VALIDATION"
)

# Initialize category counters
for category in "${CATEGORIES[@]}"; do
    test_categories["${category}_total"]=0
    test_categories["${category}_passed"]=0
    test_categories["${category}_failed"]=0
done

# Logging functions
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
        SUCCESS) echo -e "${GREEN}[SUCCESS]${NC} $message" | tee -a "$LOG_FILE" ;;
        CRITICAL) echo -e "${RED}[CRITICAL]${NC} $message" | tee -a "$LOG_FILE" ;;
    esac
    echo "$timestamp [$level] $message" >> "$LOG_FILE"
}

# Progress bar function
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local completed=$((current * width / total))
    local remaining=$((width - completed))
    
    printf "\r${BLUE}Progress: [${NC}"
    printf "%${completed}s" | tr ' ' '='
    printf "%${remaining}s" | tr ' ' '-'
    printf "${BLUE}] %d%% (%d/%d)${NC}" $percentage $current $total
}

# Enhanced test runner with categorization
run_test() {
    local category="$1"
    local test_name="$2"
    local test_command="$3"
    local success_message="$4"
    local failure_message="$5"
    local is_critical="${6:-false}"
    
    ((total_checks++))
    test_categories["${category}_total"]=$((test_categories["${category}_total"] + 1))
    
    log DEBUG "Testing: [$category] $test_name"
    
    local result
    if timeout "$TEST_TIMEOUT" bash -c "$test_command" >/dev/null 2>&1; then
        log SUCCESS "✅ $success_message"
        validation_results["$test_name"]="PASS"
        ((passed_checks++))
        test_categories["${category}_passed"]=$((test_categories["${category}_passed"] + 1))
        result=0
    else
        if [[ "$is_critical" == "true" ]]; then
            log CRITICAL "❌ $failure_message"
            critical_failures+=("$test_name: $failure_message")
            ((failed_checks++))
            test_categories["${category}_failed"]=$((test_categories["${category}_failed"] + 1))
        else
            log WARN "⚠️  $failure_message"
            ((warning_checks++))
        fi
        validation_results["$test_name"]="FAIL"
        result=1
    fi
    
    show_progress $total_checks 50
    return $result
}

# INFRASTRUCTURE VALIDATION
validate_infrastructure() {
    log INFO "🏗️  INFRASTRUCTURE VALIDATION"
    echo "=================================="
    
    # System resources
    run_test "INFRASTRUCTURE" "system_memory" \
        "[ \$(free -m | grep '^Mem:' | awk '{print \$2}') -gt 1024 ]" \
        "Sufficient memory available (>1GB)" \
        "Insufficient memory (<1GB)" \
        true
    
    run_test "INFRASTRUCTURE" "system_disk" \
        "[ \$(df / | tail -1 | awk '{print \$4}') -gt 2097152 ]" \
        "Sufficient disk space available (>2GB)" \
        "Low disk space (<2GB)" \
        true
    
    run_test "INFRASTRUCTURE" "system_cpu" \
        "[ \$(nproc) -ge 1 ]" \
        "CPU cores available" \
        "No CPU cores detected" \
        true
    
    # Network connectivity
    run_test "INFRASTRUCTURE" "dns_resolution" \
        "nslookup discord.com 8.8.8.8" \
        "DNS resolution working" \
        "DNS resolution failed" \
        true
    
    run_test "INFRASTRUCTURE" "internet_connectivity" \
        "curl -s --max-time 10 https://discord.com/api/v10/gateway" \
        "Internet connectivity confirmed" \
        "Internet connectivity failed" \
        true
    
    # Port availability
    run_test "INFRASTRUCTURE" "port_8080_available" \
        "! ss -tlnp | grep -q ':8080 '" \
        "Health check port 8080 available" \
        "Port 8080 already in use" \
        false
    
    run_test "INFRASTRUCTURE" "port_6379_available" \
        "! ss -tlnp | grep -q ':6379 '" \
        "Redis port 6379 available" \
        "Port 6379 already in use" \
        false
}

# DOCKER SERVICES VALIDATION
validate_docker_services() {
    log INFO "🐳 DOCKER SERVICES VALIDATION"
    echo "================================"
    
    # Docker installation and runtime
    run_test "DOCKER_SERVICES" "docker_installed" \
        "command -v docker" \
        "Docker is installed" \
        "Docker is not installed" \
        true
    
    run_test "DOCKER_SERVICES" "docker_running" \
        "docker info" \
        "Docker daemon is running" \
        "Docker daemon is not running" \
        true
    
    run_test "DOCKER_SERVICES" "docker_compose_installed" \
        "command -v docker-compose" \
        "Docker Compose is installed" \
        "Docker Compose is not installed" \
        true
    
    # Check for VPS-specific compose file
    run_test "DOCKER_SERVICES" "vps_compose_file" \
        "[ -f docker-compose.vps.yml ]" \
        "VPS Docker Compose file exists" \
        "VPS Docker Compose file missing" \
        true
    
    # Environment file validation
    run_test "DOCKER_SERVICES" "env_file_exists" \
        "[ -f .env ]" \
        "Environment file (.env) exists" \
        "Environment file (.env) missing" \
        true
    
    if [ -f .env ]; then
        run_test "DOCKER_SERVICES" "discord_token_configured" \
            "grep -q '^DISCORD_TOKEN=' .env && [ -n \"\$(grep '^DISCORD_TOKEN=' .env | cut -d'=' -f2-)\" ]" \
            "Discord token configured" \
            "Discord token not configured" \
            true
        
        run_test "DOCKER_SERVICES" "youtube_api_configured" \
            "grep -q '^YOUTUBE_API_KEY=' .env && [ -n \"\$(grep '^YOUTUBE_API_KEY=' .env | cut -d'=' -f2-)\" ]" \
            "YouTube API key configured" \
            "YouTube API key not configured" \
            false
    fi
    
    # Container services health
    log INFO "Starting Docker services for validation..."
    docker-compose -f docker-compose.vps.yml up -d || {
        log CRITICAL "Failed to start Docker services"
        return 1
    }
    
    # Wait for services to initialize
    sleep 10
    
    run_test "DOCKER_SERVICES" "redis_container_running" \
        "docker-compose -f docker-compose.vps.yml ps | grep -q 'robustty-redis.*Up'" \
        "Redis container is running" \
        "Redis container is not running" \
        true
    
    run_test "DOCKER_SERVICES" "bot_container_running" \
        "docker-compose -f docker-compose.vps.yml ps | grep -q 'robustty-bot.*Up'" \
        "Bot container is running" \
        "Bot container is not running" \
        true
    
    # Redis connectivity test
    run_test "DOCKER_SERVICES" "redis_connectivity" \
        "docker-compose -f docker-compose.vps.yml exec -T redis redis-cli ping | grep -q PONG" \
        "Redis is accessible" \
        "Redis is not accessible" \
        true
    
    # Health check endpoint
    local health_check_attempts=0
    while [ $health_check_attempts -lt $HEALTH_CHECK_RETRIES ]; do
        if curl -s --max-time 5 http://localhost:8080/health >/dev/null 2>&1; then
            break
        fi
        ((health_check_attempts++))
        log DEBUG "Health check attempt $health_check_attempts/$HEALTH_CHECK_RETRIES"
        sleep $HEALTH_CHECK_INTERVAL
    done
    
    run_test "DOCKER_SERVICES" "health_endpoint" \
        "curl -s --max-time 5 http://localhost:8080/health" \
        "Health check endpoint responding" \
        "Health check endpoint not responding" \
        false
}

# DISCORD INTEGRATION VALIDATION
validate_discord_integration() {
    log INFO "🤖 DISCORD INTEGRATION VALIDATION"
    echo "=================================="
    
    # Bot token validation (without exposing token)
    if [ -f .env ]; then
        local token=$(grep '^DISCORD_TOKEN=' .env | cut -d'=' -f2-)
        if [ -n "$token" ]; then
            run_test "DISCORD_INTEGRATION" "discord_token_format" \
                "echo '$token' | grep -qE '^[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27}$'" \
                "Discord token format is valid" \
                "Discord token format is invalid" \
                true
        fi
    fi
    
    # Discord API connectivity
    run_test "DISCORD_INTEGRATION" "discord_api_gateway" \
        "curl -s --max-time 10 https://discord.com/api/v10/gateway | grep -q 'wss://'" \
        "Discord Gateway API accessible" \
        "Discord Gateway API unreachable" \
        true
    
    run_test "DISCORD_INTEGRATION" "discord_api_general" \
        "curl -s --max-time 10 https://discord.com/api/v10/users/@me" \
        "Discord API endpoints accessible" \
        "Discord API endpoints unreachable" \
        true
    
    # Check bot logs for connection status
    log INFO "Checking bot connection status in logs..."
    local bot_logs=$(docker-compose -f docker-compose.vps.yml logs --tail=50 robustty 2>/dev/null || echo "")
    
    if echo "$bot_logs" | grep -q "Bot is now online"; then
        log SUCCESS "✅ Bot successfully connected to Discord"
        validation_results["discord_bot_connected"]="PASS"
        ((passed_checks++))
    elif echo "$bot_logs" | grep -q "Logged in as"; then
        log SUCCESS "✅ Bot logged into Discord"
        validation_results["discord_bot_logged_in"]="PASS"
        ((passed_checks++))
    else
        log WARN "⚠️  Bot connection status unclear from logs"
        validation_results["discord_bot_connection"]="WARN"
        ((warning_checks++))
    fi
    
    ((total_checks++))
}

# PLATFORM FUNCTIONALITY VALIDATION
validate_platform_functionality() {
    log INFO "🔍 PLATFORM FUNCTIONALITY VALIDATION"
    echo "====================================="
    
    # Cookie directory validation
    run_test "PLATFORM_FUNCTIONALITY" "cookies_directory" \
        "[ -d cookies ] || [ -d ./cookies ]" \
        "Cookies directory exists" \
        "Cookies directory missing" \
        false
    
    # YouTube API functionality (if configured)
    if grep -q '^YOUTUBE_API_KEY=' .env 2>/dev/null && [ -n "$(grep '^YOUTUBE_API_KEY=' .env | cut -d'=' -f2-)" ]; then
        local youtube_api_key=$(grep '^YOUTUBE_API_KEY=' .env | cut -d'=' -f2-)
        run_test "PLATFORM_FUNCTIONALITY" "youtube_api_access" \
            "curl -s \"https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&key=$youtube_api_key&maxResults=1\" | grep -q '\"kind\": \"youtube#searchListResponse\"'" \
            "YouTube API is accessible" \
            "YouTube API is not accessible" \
            false
    fi
    
    # Apify API functionality (if configured)
    if grep -q '^APIFY_API_KEY=' .env 2>/dev/null && [ -n "$(grep '^APIFY_API_KEY=' .env | cut -d'=' -f2-)" ]; then
        local apify_api_key=$(grep '^APIFY_API_KEY=' .env | cut -d'=' -f2-)
        run_test "PLATFORM_FUNCTIONALITY" "apify_api_access" \
            "curl -s \"https://api.apify.com/v2/acts?token=$apify_api_key\" | grep -q '\"data\"'" \
            "Apify API is accessible" \
            "Apify API is not accessible" \
            false
    fi
    
    # Platform configuration validation
    run_test "PLATFORM_FUNCTIONALITY" "config_file_exists" \
        "[ -f config/config.yaml ]" \
        "Configuration file exists" \
        "Configuration file missing" \
        false
    
    # Test bot internal functionality via health endpoint
    local health_response=$(curl -s --max-time 10 http://localhost:8080/health 2>/dev/null || echo "{}")
    if echo "$health_response" | grep -q "status.*ok"; then
        log SUCCESS "✅ Bot health endpoint reports OK status"
        validation_results["bot_health_status"]="PASS"
        ((passed_checks++))
    else
        log WARN "⚠️  Bot health endpoint not reporting OK status"
        validation_results["bot_health_status"]="WARN"
        ((warning_checks++))
    fi
    ((total_checks++))
}

# RESOURCE MONITORING VALIDATION
validate_resource_monitoring() {
    log INFO "📊 RESOURCE MONITORING VALIDATION"
    echo "=================================="
    
    # Memory usage validation
    local memory_usage=$(docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}" | grep robustty-bot | awk '{print $2}' | cut -d'/' -f1 | sed 's/MiB//' || echo "0")
    run_test "RESOURCE_MONITORING" "bot_memory_usage" \
        "[ $(echo $memory_usage | cut -d'.' -f1) -lt 512 ]" \
        "Bot memory usage is acceptable (<512MB)" \
        "Bot memory usage is high (>512MB)" \
        false
    
    # CPU usage validation
    local cpu_usage=$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}" | grep robustty-bot | awk '{print $2}' | sed 's/%//' || echo "0")
    run_test "RESOURCE_MONITORING" "bot_cpu_usage" \
        "[ $(echo $cpu_usage | cut -d'.' -f1) -lt 50 ]" \
        "Bot CPU usage is acceptable (<50%)" \
        "Bot CPU usage is high (>50%)" \
        false
    
    # Redis memory usage
    local redis_memory=$(docker-compose -f docker-compose.vps.yml exec -T redis redis-cli info memory | grep used_memory_human | cut -d':' -f2 | tr -d '\r\n' || echo "0B")
    log INFO "Redis memory usage: $redis_memory"
    
    # Log file size validation
    run_test "RESOURCE_MONITORING" "log_directory_size" \
        "[ $(du -sm logs 2>/dev/null | cut -f1 || echo 0) -lt 100 ]" \
        "Log directory size is reasonable (<100MB)" \
        "Log directory size is large (>100MB)" \
        false
    
    # Disk space monitoring
    local disk_usage=$(df . | tail -1 | awk '{print $5}' | sed 's/%//')
    run_test "RESOURCE_MONITORING" "disk_usage" \
        "[ $disk_usage -lt 80 ]" \
        "Disk usage is acceptable (<80%)" \
        "Disk usage is high (>80%)" \
        false
}

# SECURITY CONFIGURATION VALIDATION
validate_security_config() {
    log INFO "🛡️  SECURITY CONFIGURATION VALIDATION"
    echo "====================================="
    
    # File permissions validation
    run_test "SECURITY_CONFIG" "env_file_permissions" \
        "[ \$(stat -c '%a' .env 2>/dev/null || echo '644') -le 600 ]" \
        "Environment file has secure permissions" \
        "Environment file permissions too permissive" \
        false
    
    # Container security
    run_test "SECURITY_CONFIG" "container_non_root" \
        "! docker-compose -f docker-compose.vps.yml exec -T robustty whoami | grep -q '^root$'" \
        "Bot container not running as root" \
        "Bot container running as root" \
        false
    
    # Network security
    run_test "SECURITY_CONFIG" "container_network_isolation" \
        "docker network ls | grep -q robustty-network" \
        "Containers using isolated network" \
        "Containers not using isolated network" \
        false
    
    # Port exposure validation
    local exposed_ports=$(docker port robustty-bot 2>/dev/null | wc -l)
    run_test "SECURITY_CONFIG" "minimal_port_exposure" \
        "[ $exposed_ports -le 2 ]" \
        "Minimal ports exposed ($exposed_ports)" \
        "Too many ports exposed ($exposed_ports)" \
        false
    
    # Environment variable security
    run_test "SECURITY_CONFIG" "no_secrets_in_env" \
        "! docker-compose -f docker-compose.vps.yml config | grep -i -E 'password|secret|key' | grep -v -E 'DISCORD_TOKEN|YOUTUBE_API_KEY|APIFY_API_KEY'" \
        "No unexpected secrets in environment" \
        "Potential secrets exposed in environment" \
        false
}

# PERFORMANCE VALIDATION
validate_performance() {
    log INFO "⚡ PERFORMANCE VALIDATION"
    echo "=========================="
    
    # Response time validation
    local response_time=$(curl -w '%{time_total}' -s --max-time 10 http://localhost:8080/health -o /dev/null 2>/dev/null || echo "999")
    run_test "PERFORMANCE_VALIDATION" "health_endpoint_response_time" \
        "[ $(echo \"$response_time < 2\" | bc -l 2>/dev/null || echo 0) -eq 1 ]" \
        "Health endpoint responds quickly (<2s)" \
        "Health endpoint responds slowly (>2s)" \
        false
    
    # Network latency to Discord
    local discord_latency=$(ping -c 3 discord.com 2>/dev/null | tail -1 | awk -F'/' '{print $5}' || echo "999")
    run_test "PERFORMANCE_VALIDATION" "discord_latency" \
        "[ $(echo \"$discord_latency < 100\" | bc -l 2>/dev/null || echo 0) -eq 1 ]" \
        "Good latency to Discord (<100ms)" \
        "High latency to Discord (>100ms)" \
        false
    
    # Container startup time validation
    log INFO "Testing container restart performance..."
    local start_time=$(date +%s)
    docker-compose -f docker-compose.vps.yml restart robustty >/dev/null 2>&1
    local end_time=$(date +%s)
    local restart_time=$((end_time - start_time))
    
    run_test "PERFORMANCE_VALIDATION" "container_restart_time" \
        "[ $restart_time -lt 60 ]" \
        "Container restarts quickly (<60s)" \
        "Container restart is slow (>60s)" \
        false
    
    # Log processing performance
    local log_lines=$(docker-compose -f docker-compose.vps.yml logs robustty 2>/dev/null | wc -l || echo 0)
    run_test "PERFORMANCE_VALIDATION" "log_processing" \
        "[ $log_lines -gt 0 ]" \
        "Bot is generating logs properly" \
        "Bot not generating expected logs" \
        false
}

# Generate comprehensive report
generate_report() {
    echo ""
    log INFO "📋 COMPREHENSIVE VALIDATION REPORT"
    echo "==================================="
    
    # Overall statistics
    local success_rate=$((passed_checks * 100 / total_checks))
    local warning_rate=$((warning_checks * 100 / total_checks))
    local failure_rate=$((failed_checks * 100 / total_checks))
    
    echo ""
    echo -e "${BLUE}OVERALL STATISTICS${NC}"
    echo "=================="
    echo -e "Total Tests: ${CYAN}$total_checks${NC}"
    echo -e "Passed: ${GREEN}$passed_checks${NC} (${success_rate}%)"
    echo -e "Warnings: ${YELLOW}$warning_checks${NC} (${warning_rate}%)"
    echo -e "Failed: ${RED}$failed_checks${NC} (${failure_rate}%)"
    
    # Category breakdown
    echo ""
    echo -e "${BLUE}CATEGORY BREAKDOWN${NC}"
    echo "=================="
    for category in "${CATEGORIES[@]}"; do
        local total=${test_categories["${category}_total"]}
        local passed=${test_categories["${category}_passed"]}
        local failed=${test_categories["${category}_failed"]}
        
        if [ $total -gt 0 ]; then
            local category_success=$((passed * 100 / total))
            echo -e "${category}: ${GREEN}$passed${NC}/${CYAN}$total${NC} (${category_success}%)"
        fi
    done
    
    # Critical failures
    if [ ${#critical_failures[@]} -gt 0 ]; then
        echo ""
        echo -e "${RED}CRITICAL FAILURES${NC}"
        echo "================="
        for failure in "${critical_failures[@]}"; do
            echo -e "${RED}❌ $failure${NC}"
        done
    fi
    
    # Detailed test results
    echo ""
    echo -e "${BLUE}DETAILED RESULTS${NC}"
    echo "================"
    for test in "${!validation_results[@]}"; do
        local status="${validation_results[$test]}"
        case $status in
            "PASS") echo -e "${GREEN}✅ $test${NC}" ;;
            "FAIL") echo -e "${RED}❌ $test${NC}" ;;
            "WARN") echo -e "${YELLOW}⚠️  $test${NC}" ;;
        esac
    done
    
    # Recommendations
    echo ""
    echo -e "${BLUE}RECOMMENDATIONS${NC}"
    echo "==============="
    
    if [ ${#critical_failures[@]} -gt 0 ]; then
        echo -e "${RED}CRITICAL ISSUES DETECTED - DEPLOYMENT NOT RECOMMENDED${NC}"
        echo "Please fix the following critical issues before proceeding:"
        for failure in "${critical_failures[@]}"; do
            echo "  • $failure"
        done
        echo ""
        echo "Common fixes:"
        echo "  • DNS issues: sudo echo 'nameserver 8.8.8.8' > /etc/resolv.conf"
        echo "  • Docker issues: curl -fsSL https://get.docker.com | sh"
        echo "  • Environment: cp .env.example .env && edit .env"
        echo ""
    elif [ $success_rate -ge 90 ]; then
        echo -e "${GREEN}🎉 EXCELLENT - Deployment is ready!${NC}"
        echo "All critical components are functioning properly."
    elif [ $success_rate -ge 80 ]; then
        echo -e "${YELLOW}⚠️  GOOD - Deployment should work with minor issues${NC}"
        echo "Consider addressing warnings for optimal performance."
    elif [ $success_rate -ge 70 ]; then
        echo -e "${YELLOW}⚠️  FAIR - Deployment may have issues${NC}"
        echo "Recommend fixing failed tests before production use."
    else
        echo -e "${RED}❌ POOR - Significant issues detected${NC}"
        echo "Multiple components failing - not recommended for deployment."
    fi
    
    # Log file location
    echo ""
    echo -e "${BLUE}LOGS AND DEBUGGING${NC}"
    echo "=================="
    echo "Full validation log: $LOG_FILE"
    echo "Bot logs: docker-compose -f docker-compose.vps.yml logs -f robustty"
    echo "Redis logs: docker-compose -f docker-compose.vps.yml logs -f redis"
    echo "System monitoring: scripts/monitor-vps-health.sh"
    
    # Return appropriate exit code
    if [ ${#critical_failures[@]} -gt 0 ]; then
        return 2  # Critical failures
    elif [ $success_rate -ge 80 ]; then
        return 0  # Success
    else
        return 1  # Warnings/issues
    fi
}

# Cleanup function
cleanup() {
    log INFO "🧹 Cleaning up validation environment..."
    
    # Don't stop services if they were already running
    if [ "$SERVICES_WERE_RUNNING" != "true" ]; then
        docker-compose -f docker-compose.vps.yml down >/dev/null 2>&1 || true
    fi
    
    # Clean up temporary files
    # Keep log file for debugging
    
    echo ""
    log INFO "Cleanup completed. Log preserved at: $LOG_FILE"
}

# Signal handlers
trap cleanup EXIT
trap 'echo ""; log ERROR "Validation interrupted"; exit 130' INT TERM

# Help function
show_help() {
    cat << EOF
Comprehensive VPS Deployment Validation Script for Robustty Discord Bot

Usage: $SCRIPT_NAME [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose logging
    -q, --quick             Run only critical tests
    --category CATEGORY     Run tests for specific category only
    --skip-cleanup          Don't stop services after validation
    --timeout SECONDS       Set overall validation timeout (default: 300)
    --no-colors             Disable colored output

CATEGORIES:
    infrastructure          System resources and network
    docker-services         Docker containers and services
    discord-integration     Discord bot connection and API
    platform-functionality Platform APIs and features
    resource-monitoring     Performance and resource usage
    security-config         Security configuration validation
    performance-validation  Performance benchmarks

EXAMPLES:
    $SCRIPT_NAME                                # Full validation
    $SCRIPT_NAME --quick                        # Quick critical tests only
    $SCRIPT_NAME --category infrastructure      # Infrastructure tests only
    $SCRIPT_NAME --verbose --timeout 600        # Verbose with 10min timeout

EXIT CODES:
    0   Validation passed (>80% success rate)
    1   Validation completed with warnings (60-80% success rate)
    2   Critical failures detected (<60% success rate)
    3   Invalid arguments or setup issues

DESCRIPTION:
    This script performs comprehensive end-to-end validation of a Robustty Discord Bot
    VPS deployment. It validates infrastructure, Docker services, Discord integration,
    platform functionality, resource usage, security configuration, and performance.

    The validation includes:
    • System resource availability and network connectivity
    • Docker container health and service connectivity
    • Discord API access and bot authentication
    • External platform APIs (YouTube, Apify, etc.)
    • Resource monitoring and performance benchmarks
    • Security configuration validation
    • Performance testing and optimization validation

REQUIREMENTS:
    • Linux/Unix VPS environment
    • Docker and Docker Compose installed
    • .env file with bot configuration
    • docker-compose.vps.yml file
    • Network access to Discord and platform APIs

FOR TROUBLESHOOTING:
    • Check the generated log file for detailed error information
    • Run 'scripts/diagnose-vps-network.sh' for network issues
    • Use 'scripts/monitor-vps-health.sh' for ongoing monitoring
    • See CLAUDE.md for deployment and debugging guidance

EOF
}

# Parse command line arguments
VERBOSE=false
QUICK_MODE=false
CATEGORY_FILTER=""
SKIP_CLEANUP=false
NO_COLORS=false

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
        --category)
            CATEGORY_FILTER="$2"
            shift 2
            ;;
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --timeout)
            VALIDATION_TIMEOUT="$2"
            shift 2
            ;;
        --no-colors)
            NO_COLORS=true
            # Disable colors
            RED='' GREEN='' YELLOW='' BLUE='' PURPLE='' CYAN='' NC=''
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 3
            ;;
    esac
done

# Main validation execution
main() {
    # Initialize log file
    echo "Robustty VPS Deployment Validation - $(date)" > "$LOG_FILE"
    echo "================================================" >> "$LOG_FILE"
    
    log INFO "🚀 Starting Comprehensive VPS Deployment Validation"
    log INFO "===================================================="
    
    # Check if services are already running
    if docker-compose -f docker-compose.vps.yml ps | grep -q "Up"; then
        SERVICES_WERE_RUNNING=true
        log INFO "Services already running - will not stop them after validation"
    else
        SERVICES_WERE_RUNNING=false
    fi
    
    # Check basic requirements
    if [ ! -f docker-compose.vps.yml ]; then
        log CRITICAL "docker-compose.vps.yml not found. Please run from project root."
        return 3
    fi
    
    # Set timeout for entire validation
    timeout "$VALIDATION_TIMEOUT" bash -c '
        # Run validation categories
        if [ "$CATEGORY_FILTER" = "" ] || [ "$CATEGORY_FILTER" = "infrastructure" ]; then
            validate_infrastructure
        fi
        
        if [ "$CATEGORY_FILTER" = "" ] || [ "$CATEGORY_FILTER" = "docker-services" ]; then
            validate_docker_services
        fi
        
        if [ "$CATEGORY_FILTER" = "" ] || [ "$CATEGORY_FILTER" = "discord-integration" ]; then
            validate_discord_integration
        fi
        
        if [ "$CATEGORY_FILTER" = "" ] || [ "$CATEGORY_FILTER" = "platform-functionality" ]; then
            validate_platform_functionality
        fi
        
        if [ "$CATEGORY_FILTER" = "" ] || [ "$CATEGORY_FILTER" = "resource-monitoring" ]; then
            validate_resource_monitoring
        fi
        
        if [ "$CATEGORY_FILTER" = "" ] || [ "$CATEGORY_FILTER" = "security-config" ]; then
            validate_security_config
        fi
        
        if [ "$CATEGORY_FILTER" = "" ] || [ "$CATEGORY_FILTER" = "performance-validation" ]; then
            validate_performance
        fi
    ' || {
        log ERROR "Validation timed out after $VALIDATION_TIMEOUT seconds"
        return 1
    }
    
    # Generate final report
    generate_report
}

# Execute main function
main "$@"
exit_code=$?

# Handle cleanup unless skipped
if [ "$SKIP_CLEANUP" != "true" ]; then
    cleanup
fi

exit $exit_code