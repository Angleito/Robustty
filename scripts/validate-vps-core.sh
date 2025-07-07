#!/bin/bash
# Core VPS Deployment Validation Script - Essential checks only
# Focused on critical deployment validation with clear pass/fail results

set -e

# Configuration
SCRIPT_NAME="$(basename "$0")"
TIMEOUT=120  # 2 minutes for entire validation
HEALTH_TIMEOUT=60  # 1 minute for health check
MAX_RETRIES=10
RETRY_INTERVAL=6

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Progress tracking
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
CRITICAL_FAILURES=()

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%H:%M:%S')
    
    case $level in
        INFO)  echo -e "${BLUE}[$timestamp]${NC} $message" ;;
        PASS)  echo -e "${GREEN}[$timestamp] ✅${NC} $message" ;;
        FAIL)  echo -e "${RED}[$timestamp] ❌${NC} $message" ;;
        WARN)  echo -e "${YELLOW}[$timestamp] ⚠️${NC} $message" ;;
        ERROR) echo -e "${RED}[$timestamp] 🚨${NC} $message" ;;
    esac
}

# Test runner with critical failure tracking
run_test() {
    local test_name="$1"
    local test_command="$2"
    local success_msg="$3"
    local failure_msg="$4"
    local is_critical="${5:-true}"
    
    ((TOTAL_CHECKS++))
    log INFO "Testing: $test_name"
    
    if timeout 30 bash -c "$test_command" >/dev/null 2>&1; then
        log PASS "$success_msg"
        ((PASSED_CHECKS++))
        return 0
    else
        if [[ "$is_critical" == "true" ]]; then
            log FAIL "$failure_msg"
            CRITICAL_FAILURES+=("$test_name: $failure_msg")
            ((FAILED_CHECKS++))
        else
            log WARN "$failure_msg"
        fi
        return 1
    fi
}

# Infrastructure validation (critical basics)
validate_infrastructure() {
    log INFO "🏗️  INFRASTRUCTURE VALIDATION"
    echo "=============================="
    
    # System resources
    run_test "memory_check" \
        "[ \$(free -m | awk '/^Mem:/{print \$2}') -gt 1024 ]" \
        "Sufficient memory available (>1GB)" \
        "Insufficient memory (<1GB) - bot may fail" \
        true
    
    run_test "disk_space" \
        "[ \$(df / | tail -1 | awk '{print \$4}') -gt 1048576 ]" \
        "Sufficient disk space (>1GB)" \
        "Low disk space (<1GB) - deployment may fail" \
        true
    
    run_test "dns_resolution" \
        "nslookup discord.com 8.8.8.8" \
        "DNS resolution working" \
        "DNS resolution failed - bot cannot connect" \
        true
    
    run_test "discord_connectivity" \
        "curl -s --max-time 10 https://discord.com/api/v10/gateway" \
        "Discord API accessible" \
        "Discord API unreachable - bot cannot connect" \
        true
}

# Docker services validation
validate_docker() {
    log INFO "🐳 DOCKER SERVICES VALIDATION"
    echo "============================="
    
    # Docker basics
    run_test "docker_installed" \
        "command -v docker" \
        "Docker is installed" \
        "Docker not installed - deployment impossible" \
        true
    
    run_test "docker_running" \
        "docker info" \
        "Docker daemon running" \
        "Docker daemon not running" \
        true
    
    run_test "compose_available" \
        "command -v docker-compose" \
        "Docker Compose available" \
        "Docker Compose not installed" \
        true
    
    run_test "compose_file_exists" \
        "[ -f docker-compose.yml ]" \
        "Docker compose file exists" \
        "docker-compose.yml missing" \
        true
    
    run_test "env_file_exists" \
        "[ -f .env ]" \
        "Environment file exists" \
        ".env file missing - bot cannot start" \
        true
    
    # Environment validation
    if [ -f .env ]; then
        run_test "discord_token_configured" \
            "grep -q '^DISCORD_TOKEN=' .env && [ -n \"\$(grep '^DISCORD_TOKEN=' .env | cut -d'=' -f2-)\" ]" \
            "Discord token configured" \
            "Discord token missing - bot cannot authenticate" \
            true
    fi
}

# Service health validation
validate_services() {
    log INFO "🔧 SERVICE HEALTH VALIDATION"
    echo "============================"
    
    # Start services for validation
    log INFO "Starting services for validation..."
    if ! docker-compose -f docker-compose.yml up -d; then
        log FAIL "Failed to start Docker services"
        CRITICAL_FAILURES+=("docker_services: Failed to start containers")
        return 1
    fi
    
    # Wait for services to initialize
    log INFO "Waiting for services to initialize..."
    sleep 15
    
    # Redis health
    run_test "redis_running" \
        "docker-compose -f docker-compose.yml ps | grep -q 'redis.*Up'" \
        "Redis container running" \
        "Redis container not running" \
        true
    
    run_test "redis_accessible" \
        "docker-compose -f docker-compose.yml exec -T redis redis-cli ping | grep -q PONG" \
        "Redis accessible" \
        "Redis not responding" \
        true
    
    # Bot container health
    run_test "bot_container_running" \
        "docker-compose -f docker-compose.yml ps | grep -q 'robustty.*Up'" \
        "Bot container running" \
        "Bot container not running" \
        true
    
    # Health endpoint validation
    local health_attempts=0
    log INFO "Waiting for health endpoint..."
    while [ $health_attempts -lt $MAX_RETRIES ]; do
        if curl -s --max-time 5 http://localhost:8080/health >/dev/null 2>&1; then
            break
        fi
        ((health_attempts++))
        log INFO "Health check attempt $health_attempts/$MAX_RETRIES"
        sleep $RETRY_INTERVAL
    done
    
    run_test "health_endpoint" \
        "curl -s --max-time 5 http://localhost:8080/health" \
        "Health endpoint responding" \
        "Health endpoint not responding - check bot logs" \
        false
}

# Discord bot validation
validate_bot() {
    log INFO "🤖 DISCORD BOT VALIDATION"
    echo "========================="
    
    # Check bot logs for connection
    log INFO "Checking bot connection status..."
    local bot_logs=$(docker-compose -f docker-compose.yml logs --tail=20 robustty 2>/dev/null || echo "")
    
    if echo "$bot_logs" | grep -q -E "(Bot is now online|Logged in as|Successfully connected)"; then
        log PASS "Bot successfully connected to Discord"
        ((PASSED_CHECKS++))
        ((TOTAL_CHECKS++))
    elif echo "$bot_logs" | grep -q -E "(ConnectionError|Unauthorized|Invalid token)"; then
        log FAIL "Bot connection failed - check token and network"
        CRITICAL_FAILURES+=("bot_connection: Authentication or network error")
        ((FAILED_CHECKS++))
        ((TOTAL_CHECKS++))
    else
        log WARN "Bot connection status unclear - check logs manually"
        ((TOTAL_CHECKS++))
    fi
    
    # Basic functionality test (if health endpoint works)
    if curl -s --max-time 5 http://localhost:8080/health | grep -q "ok\|healthy"; then
        log PASS "Bot health check passed"
        ((PASSED_CHECKS++))
    else
        log WARN "Bot health check failed or not available"
    fi
    ((TOTAL_CHECKS++))
}

# Resource validation
validate_resources() {
    log INFO "📊 RESOURCE VALIDATION"
    echo "====================="
    
    # Memory usage
    local memory_usage=$(docker stats --no-stream --format "{{.MemUsage}}" 2>/dev/null | head -1 | cut -d'/' -f1 | sed 's/[^0-9.]//g' || echo "0")
    if [ $(echo "$memory_usage < 400" | bc -l 2>/dev/null || echo 1) -eq 1 ]; then
        log PASS "Memory usage acceptable (<400MB)"
        ((PASSED_CHECKS++))
    else
        log WARN "Memory usage high (${memory_usage}MB)"
    fi
    ((TOTAL_CHECKS++))
    
    # Disk usage
    local disk_usage=$(df . | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_usage" -lt 80 ]; then
        log PASS "Disk usage acceptable (${disk_usage}%)"
        ((PASSED_CHECKS++))
    else
        log WARN "Disk usage high (${disk_usage}%)"
    fi
    ((TOTAL_CHECKS++))
}

# Generate final report
generate_report() {
    echo ""
    log INFO "📋 VALIDATION SUMMARY"
    echo "===================="
    
    local success_rate=0
    if [ $TOTAL_CHECKS -gt 0 ]; then
        success_rate=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
    fi
    
    echo -e "Total Checks: ${BLUE}$TOTAL_CHECKS${NC}"
    echo -e "Passed: ${GREEN}$PASSED_CHECKS${NC}"
    echo -e "Failed: ${RED}$FAILED_CHECKS${NC}"
    echo -e "Success Rate: ${BLUE}${success_rate}%${NC}"
    
    # Critical failures
    if [ ${#CRITICAL_FAILURES[@]} -gt 0 ]; then
        echo ""
        echo -e "${RED}CRITICAL FAILURES:${NC}"
        for failure in "${CRITICAL_FAILURES[@]}"; do
            echo -e "${RED}❌ $failure${NC}"
        done
        echo ""
        echo -e "${RED}🚨 DEPLOYMENT NOT RECOMMENDED${NC}"
        echo "Fix critical issues before proceeding."
        echo ""
        echo "Common fixes:"
        echo "• DNS: sudo echo 'nameserver 8.8.8.8' > /etc/resolv.conf"
        echo "• Docker: curl -fsSL https://get.docker.com | sh"
        echo "• Environment: cp .env.example .env && nano .env"
        return 2
    elif [ $success_rate -ge 85 ]; then
        echo ""
        echo -e "${GREEN}🎉 DEPLOYMENT READY!${NC}"
        echo "All critical checks passed."
        return 0
    elif [ $success_rate -ge 70 ]; then
        echo ""
        echo -e "${YELLOW}⚠️  DEPLOYMENT POSSIBLE WITH WARNINGS${NC}"
        echo "Consider fixing warnings for optimal performance."
        return 1
    else
        echo ""
        echo -e "${RED}❌ DEPLOYMENT NOT RECOMMENDED${NC}"
        echo "Too many issues detected."
        return 1
    fi
}

# Cleanup
cleanup() {
    log INFO "🧹 Cleaning up..."
    # Keep services running if they were started successfully
    # Don't auto-stop as they might be needed for deployment
}

# Signal handlers
trap cleanup EXIT
trap 'echo ""; log ERROR "Validation interrupted"; exit 130' INT TERM

# Help function
show_help() {
    cat << EOF
Core VPS Deployment Validation Script for Robustty

Usage: $SCRIPT_NAME [OPTIONS]

OPTIONS:
    -h, --help          Show this help
    --quick            Skip non-critical checks
    --no-docker        Skip Docker service validation

DESCRIPTION:
    Performs essential validation checks for VPS deployment:
    • Infrastructure (memory, disk, DNS, connectivity)
    • Docker (installation, compose, environment)
    • Services (Redis, bot container, health checks)
    • Bot (Discord connection, basic functionality)
    • Resources (memory/disk usage validation)

EXIT CODES:
    0   All critical checks passed (ready for deployment)
    1   Some warnings but deployment possible
    2   Critical failures (deployment not recommended)

EXAMPLES:
    $SCRIPT_NAME                    # Full validation
    $SCRIPT_NAME --quick           # Skip optional checks
EOF
}

# Parse arguments
QUICK_MODE=false
SKIP_DOCKER=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --no-docker)
            SKIP_DOCKER=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main execution
main() {
    log INFO "🚀 Starting Core VPS Deployment Validation"
    echo "==========================================="
    
    # Check basic requirements
    if [ ! -f docker-compose.yml ]; then
        log ERROR "docker-compose.yml not found. Run from project root."
        exit 3
    fi
    
    # Run validations with timeout
    timeout $TIMEOUT bash -c '
        validate_infrastructure
        
        if [ "$SKIP_DOCKER" != "true" ]; then
            validate_docker
            validate_services
            validate_bot
        fi
        
        if [ "$QUICK_MODE" != "true" ]; then
            validate_resources
        fi
    ' || {
        log ERROR "Validation timed out after $TIMEOUT seconds"
        exit 1
    }
    
    # Generate report and exit with appropriate code
    generate_report
}

# Execute main function
main "$@"