#!/bin/bash
# Pre-Deployment Validation Script for Robustty VPS
# Validates system requirements and prerequisites before deployment

set -e

# Configuration
SCRIPT_NAME="$(basename "$0")"
LOG_FILE="/tmp/robustty-pre-deployment.log"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Validation results
CHECKS_PASSED=0
CHECKS_FAILED=0
TOTAL_CHECKS=0
CRITICAL_ISSUES=()
WARNINGS=()

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%H:%M:%S')
    
    case $level in
        INFO)  echo -e "${BLUE}[$timestamp]${NC} $message" | tee -a "$LOG_FILE" ;;
        PASS)  echo -e "${GREEN}[$timestamp] ✅${NC} $message" | tee -a "$LOG_FILE" ;;
        FAIL)  echo -e "${RED}[$timestamp] ❌${NC} $message" | tee -a "$LOG_FILE" ;;
        WARN)  echo -e "${YELLOW}[$timestamp] ⚠️${NC} $message" | tee -a "$LOG_FILE" ;;
        ERROR) echo -e "${RED}[$timestamp] 🚨${NC} $message" | tee -a "$LOG_FILE" ;;
    esac
}

# Test runner
check_requirement() {
    local name="$1"
    local test_command="$2"
    local success_msg="$3"
    local failure_msg="$4"
    local is_critical="${5:-true}"
    local fix_suggestion="${6:-}"
    
    ((TOTAL_CHECKS++))
    
    if eval "$test_command" >/dev/null 2>&1; then
        log PASS "$success_msg"
        ((CHECKS_PASSED++))
        return 0
    else
        if [[ "$is_critical" == "true" ]]; then
            log FAIL "$failure_msg"
            CRITICAL_ISSUES+=("$name: $failure_msg")
            if [[ -n "$fix_suggestion" ]]; then
                CRITICAL_ISSUES+=("  Fix: $fix_suggestion")
            fi
            ((CHECKS_FAILED++))
        else
            log WARN "$failure_msg"
            WARNINGS+=("$name: $failure_msg")
            if [[ -n "$fix_suggestion" ]]; then
                WARNINGS+=("  Suggestion: $fix_suggestion")
            fi
        fi
        return 1
    fi
}

# System requirements validation
validate_system_requirements() {
    log INFO "🖥️  SYSTEM REQUIREMENTS"
    echo "======================="
    
    # Operating system
    check_requirement "os_support" \
        "uname -s | grep -qE '^(Linux|Darwin)$'" \
        "Operating system supported" \
        "Unsupported operating system" \
        true \
        "Use Linux or macOS"
    
    # Memory requirements
    check_requirement "memory_requirement" \
        "[ \$(free -m 2>/dev/null | awk '/^Mem:/{print \$2}' || echo 0) -ge 1024 ]" \
        "Sufficient RAM (≥1GB)" \
        "Insufficient RAM (<1GB)" \
        true \
        "Upgrade VPS to at least 1GB RAM"
    
    # Disk space requirements
    check_requirement "disk_space" \
        "[ \$(df / 2>/dev/null | tail -1 | awk '{print \$4}' || echo 0) -gt 2097152 ]" \
        "Sufficient disk space (≥2GB free)" \
        "Insufficient disk space (<2GB free)" \
        true \
        "Free up disk space or upgrade storage"
    
    # CPU requirements
    check_requirement "cpu_cores" \
        "[ \$(nproc 2>/dev/null || echo 1) -ge 1 ]" \
        "CPU cores available" \
        "No CPU cores detected" \
        true \
        "Check VPS specifications"
}

# Network prerequisites
validate_network_prerequisites() {
    log INFO "🌐 NETWORK PREREQUISITES"
    echo "========================"
    
    # DNS resolution
    check_requirement "dns_basic" \
        "nslookup google.com >/dev/null 2>&1" \
        "Basic DNS resolution working" \
        "DNS resolution failed" \
        true \
        "Configure DNS servers: echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf"
    
    # Discord API reachability
    check_requirement "discord_api" \
        "curl -s --max-time 10 https://discord.com/api/v10/gateway >/dev/null 2>&1" \
        "Discord API reachable" \
        "Cannot reach Discord API" \
        true \
        "Check firewall and network connectivity"
    
    # HTTPS connectivity
    check_requirement "https_connectivity" \
        "curl -s --max-time 10 https://www.google.com >/dev/null 2>&1" \
        "HTTPS connectivity working" \
        "HTTPS connectivity failed" \
        true \
        "Check firewall settings for outbound HTTPS (port 443)"
    
    # Port availability for health checks
    check_requirement "port_8080" \
        "! ss -tlnp 2>/dev/null | grep -q ':8080 '" \
        "Port 8080 available for health checks" \
        "Port 8080 already in use" \
        false \
        "Stop service using port 8080 or configure alternative port"
    
    # IPv4 connectivity
    check_requirement "ipv4_connectivity" \
        "ping -c 1 8.8.8.8 >/dev/null 2>&1" \
        "IPv4 connectivity working" \
        "IPv4 connectivity failed" \
        true \
        "Check network configuration and routing"
}

# Docker prerequisites
validate_docker_prerequisites() {
    log INFO "🐳 DOCKER PREREQUISITES"
    echo "======================="
    
    # Docker installation
    check_requirement "docker_installed" \
        "command -v docker >/dev/null 2>&1" \
        "Docker is installed" \
        "Docker not installed" \
        true \
        "Install Docker: curl -fsSL https://get.docker.com | sh"
    
    # Docker daemon
    if command -v docker >/dev/null 2>&1; then
        check_requirement "docker_daemon" \
            "docker info >/dev/null 2>&1" \
            "Docker daemon running" \
            "Docker daemon not running" \
            true \
            "Start Docker: sudo systemctl start docker"
        
        # Docker permissions
        check_requirement "docker_permissions" \
            "docker ps >/dev/null 2>&1" \
            "Docker permissions configured" \
            "Docker permission denied" \
            false \
            "Add user to docker group: sudo usermod -aG docker \$USER && newgrp docker"
    fi
    
    # Docker Compose
    check_requirement "docker_compose" \
        "command -v docker-compose >/dev/null 2>&1" \
        "Docker Compose installed" \
        "Docker Compose not installed" \
        true \
        "Install: sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose && sudo chmod +x /usr/local/bin/docker-compose"
}

# Environment validation
validate_environment() {
    log INFO "⚙️  ENVIRONMENT VALIDATION"
    echo "========================="
    
    # Project files
    check_requirement "project_root" \
        "[ -f docker-compose.yml ]" \
        "In correct project directory" \
        "Not in project root or missing docker-compose.yml" \
        true \
        "Navigate to project root directory"
    
    # Environment file
    check_requirement "env_file" \
        "[ -f .env ]" \
        "Environment file exists" \
        "Environment file (.env) missing" \
        true \
        "Create from template: cp .env.example .env && nano .env"
    
    # Discord token in environment
    if [ -f .env ]; then
        check_requirement "discord_token" \
            "grep -q '^DISCORD_TOKEN=' .env && [ -n \"\$(grep '^DISCORD_TOKEN=' .env | cut -d'=' -f2-)\" ]" \
            "Discord token configured" \
            "Discord token not set in .env" \
            true \
            "Add DISCORD_TOKEN=your_token_here to .env file"
        
        # Token format validation
        local token=$(grep '^DISCORD_TOKEN=' .env 2>/dev/null | cut -d'=' -f2- | tr -d '"'"'"' ')
        if [[ -n "$token" ]]; then
            check_requirement "token_format" \
                "echo '$token' | grep -qE '^[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27}$'" \
                "Discord token format valid" \
                "Discord token format appears invalid" \
                false \
                "Verify token from Discord Developer Portal"
        fi
    fi
    
    # API keys (optional)
    if [ -f .env ]; then
        if grep -q '^YOUTUBE_API_KEY=' .env 2>/dev/null; then
            check_requirement "youtube_api_key" \
                "[ -n \"\$(grep '^YOUTUBE_API_KEY=' .env | cut -d'=' -f2-)\" ]" \
                "YouTube API key configured" \
                "YouTube API key empty" \
                false \
                "Get API key from Google Cloud Console"
        fi
        
        if grep -q '^APIFY_API_KEY=' .env 2>/dev/null; then
            check_requirement "apify_api_key" \
                "[ -n \"\$(grep '^APIFY_API_KEY=' .env | cut -d'=' -f2-)\" ]" \
                "Apify API key configured" \
                "Apify API key empty" \
                false \
                "Get API key from Apify Console"
        fi
    fi
}

# API key validation
validate_api_keys() {
    log INFO "🔑 API KEY VALIDATION"
    echo "===================="
    
    if [ ! -f .env ]; then
        log WARN "Skipping API validation - no .env file"
        return
    fi
    
    # YouTube API validation
    local youtube_key=$(grep '^YOUTUBE_API_KEY=' .env 2>/dev/null | cut -d'=' -f2- | tr -d '"'"'"' ')
    if [[ -n "$youtube_key" && "$youtube_key" != "your_youtube_api_key_here" ]]; then
        check_requirement "youtube_api_valid" \
            "curl -s \"https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&key=$youtube_key&maxResults=1\" | grep -q '\"kind\": \"youtube#searchListResponse\"'" \
            "YouTube API key valid" \
            "YouTube API key invalid or quota exceeded" \
            false \
            "Check API key and quota in Google Cloud Console"
    fi
    
    # Discord token validation (test connection without exposing token)
    local discord_token=$(grep '^DISCORD_TOKEN=' .env 2>/dev/null | cut -d'=' -f2- | tr -d '"'"'"' ')
    if [[ -n "$discord_token" && "$discord_token" != "your_discord_bot_token" ]]; then
        check_requirement "discord_token_valid" \
            "curl -s -H \"Authorization: Bot $discord_token\" https://discord.com/api/v10/users/@me | grep -q '\"id\"'" \
            "Discord token valid" \
            "Discord token invalid" \
            true \
            "Check token in Discord Developer Portal"
    fi
}

# Security validation
validate_security() {
    log INFO "🛡️  SECURITY VALIDATION"
    echo "======================"
    
    # Environment file permissions
    if [ -f .env ]; then
        check_requirement "env_permissions" \
            "[ \$(stat -c '%a' .env 2>/dev/null || echo 644) -le 600 ]" \
            "Environment file has secure permissions" \
            "Environment file permissions too open" \
            false \
            "Secure permissions: chmod 600 .env"
    fi
    
    # User is not root
    check_requirement "non_root_user" \
        "[ \"\$(id -u)\" -ne 0 ]" \
        "Running as non-root user" \
        "Running as root user" \
        false \
        "Create and use a non-root user for deployment"
    
    # Check for common security tools
    check_requirement "sudo_available" \
        "command -v sudo >/dev/null 2>&1" \
        "Sudo available for privileged operations" \
        "Sudo not available" \
        false \
        "Install sudo or use root account carefully"
}

# Generate pre-deployment report
generate_report() {
    echo ""
    log INFO "📋 PRE-DEPLOYMENT VALIDATION REPORT"
    echo "==================================="
    
    local success_rate=0
    if [ $TOTAL_CHECKS -gt 0 ]; then
        success_rate=$((CHECKS_PASSED * 100 / TOTAL_CHECKS))
    fi
    
    echo -e "Total Checks: ${CYAN}$TOTAL_CHECKS${NC}"
    echo -e "Passed: ${GREEN}$CHECKS_PASSED${NC}"
    echo -e "Failed: ${RED}$CHECKS_FAILED${NC}"
    echo -e "Success Rate: ${BLUE}${success_rate}%${NC}"
    
    # Critical issues
    if [ ${#CRITICAL_ISSUES[@]} -gt 0 ]; then
        echo ""
        echo -e "${RED}🚨 CRITICAL ISSUES (must fix before deployment):${NC}"
        for issue in "${CRITICAL_ISSUES[@]}"; do
            echo -e "${RED}❌ $issue${NC}"
        done
    fi
    
    # Warnings
    if [ ${#WARNINGS[@]} -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}⚠️  WARNINGS (recommended to fix):${NC}"
        for warning in "${WARNINGS[@]}"; do
            echo -e "${YELLOW}⚠️  $warning${NC}"
        done
    fi
    
    # Final recommendation
    echo ""
    if [ ${#CRITICAL_ISSUES[@]} -eq 0 ]; then
        if [ $success_rate -ge 90 ]; then
            echo -e "${GREEN}🎉 READY FOR DEPLOYMENT!${NC}"
            echo "All critical requirements met."
        elif [ $success_rate -ge 80 ]; then
            echo -e "${YELLOW}✅ DEPLOYMENT POSSIBLE${NC}"
            echo "Consider addressing warnings for optimal setup."
        else
            echo -e "${YELLOW}⚠️  DEPLOYMENT RISKY${NC}"
            echo "Multiple issues detected. Proceed with caution."
        fi
        echo ""
        echo "Next steps:"
        echo "1. Run deployment: ./deploy-vps.sh <vps-ip> <username>"
        echo "2. Monitor with: ./scripts/monitor-vps-health.sh"
    else
        echo -e "${RED}❌ NOT READY FOR DEPLOYMENT${NC}"
        echo "Fix critical issues above before proceeding."
    fi
    
    echo ""
    echo "Full log: $LOG_FILE"
    
    # Return appropriate exit code
    if [ ${#CRITICAL_ISSUES[@]} -gt 0 ]; then
        return 2  # Critical failures
    elif [ $success_rate -ge 80 ]; then
        return 0  # Ready
    else
        return 1  # Warnings
    fi
}

# Help function
show_help() {
    cat << EOF
Pre-Deployment Validation Script for Robustty VPS

Usage: $SCRIPT_NAME [OPTIONS]

OPTIONS:
    -h, --help          Show this help
    --skip-api          Skip API key validation
    --quick             Skip optional validations

DESCRIPTION:
    Validates system requirements and prerequisites before VPS deployment:
    • System resources (RAM, disk, CPU)
    • Network connectivity (DNS, Discord API, HTTPS)
    • Docker installation and configuration
    • Environment files and configuration
    • API key validation (optional)
    • Basic security checks

EXIT CODES:
    0   Ready for deployment
    1   Deployment possible with warnings
    2   Critical issues - not ready for deployment

EXAMPLES:
    $SCRIPT_NAME                    # Full validation
    $SCRIPT_NAME --skip-api         # Skip API key tests
    $SCRIPT_NAME --quick            # Skip optional checks
EOF
}

# Parse arguments
SKIP_API=false
QUICK_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --skip-api)
            SKIP_API=true
            shift
            ;;
        --quick)
            QUICK_MODE=true
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
    echo "Robustty Pre-Deployment Validation - $(date)" > "$LOG_FILE"
    echo "============================================" >> "$LOG_FILE"
    
    log INFO "🚀 Starting Pre-Deployment Validation"
    echo "======================================"
    
    # Run all validations
    validate_system_requirements
    validate_network_prerequisites
    validate_docker_prerequisites
    validate_environment
    
    if [[ "$SKIP_API" != "true" ]]; then
        validate_api_keys
    fi
    
    if [[ "$QUICK_MODE" != "true" ]]; then
        validate_security
    fi
    
    # Generate final report
    generate_report
}

# Execute main function
main "$@"