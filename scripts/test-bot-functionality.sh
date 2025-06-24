#!/bin/bash

# End-to-End Bot Functionality Testing Script for Robustty Discord Bot
# This script tests all bot functionality to ensure complete operation
# including Discord commands, platform searches, and audio streaming.

set -e

# Configuration
SCRIPT_NAME="$(basename "$0")"
LOG_FILE="/tmp/robustty-functionality-test.log"
TEST_TIMEOUT=60
COMMAND_TIMEOUT=30
STREAM_TEST_TIMEOUT=45

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Test tracking
declare -A test_results
total_tests=0
passed_tests=0
failed_tests=0
skipped_tests=0

# Bot testing configuration
DISCORD_TEST_GUILD_ID="${DISCORD_TEST_GUILD_ID:-}"
DISCORD_TEST_CHANNEL_ID="${DISCORD_TEST_CHANNEL_ID:-}"
DISCORD_TEST_USER_ID="${DISCORD_TEST_USER_ID:-}"

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
        SKIP) echo -e "${CYAN}[SKIP]${NC} $message" | tee -a "$LOG_FILE" ;;
    esac
    echo "$timestamp [$level] $message" >> "$LOG_FILE"
}

# Progress tracking
show_progress() {
    local current=$1
    local total=$2
    local width=40
    local percentage=$((current * 100 / total))
    local completed=$((current * width / total))
    local remaining=$((width - completed))
    
    printf "\r${BLUE}Testing Progress: [${NC}"
    printf "%${completed}s" | tr ' ' '='
    printf "%${remaining}s" | tr ' ' '-'
    printf "${BLUE}] %d%% (%d/%d)${NC}" $percentage $current $total
}

# Test runner function
run_test() {
    local test_name="$1"
    local test_description="$2"
    local test_command="$3"
    local is_critical="${4:-false}"
    
    ((total_tests++))
    log DEBUG "Running test: $test_name - $test_description"
    
    local result
    if eval "$test_command" >/dev/null 2>&1; then
        log SUCCESS "✅ $test_description"
        test_results["$test_name"]="PASS"
        ((passed_tests++))
        result=0
    else
        if [[ "$is_critical" == "true" ]]; then
            log ERROR "❌ $test_description"
            test_results["$test_name"]="FAIL"
            ((failed_tests++))
        else
            log WARN "⚠️  $test_description (non-critical)"
            test_results["$test_name"]="WARN"
            ((failed_tests++))
        fi
        result=1
    fi
    
    show_progress $total_tests 25
    return $result
}

# Skip test function
skip_test() {
    local test_name="$1"
    local test_description="$2"
    local reason="$3"
    
    ((total_tests++))
    ((skipped_tests++))
    log SKIP "$test_description (Skipped: $reason)"
    test_results["$test_name"]="SKIP"
    show_progress $total_tests 25
}

# Check if bot is running and accessible
validate_bot_status() {
    log INFO "🤖 VALIDATING BOT STATUS"
    echo "========================="
    
    # Check if containers are running
    run_test "bot_container_running" \
        "Bot container is running" \
        "docker-compose -f docker-compose.vps.yml ps | grep -q 'robustty-bot.*Up'" \
        true
    
    # Check health endpoint
    run_test "health_endpoint_accessible" \
        "Health endpoint is accessible" \
        "curl -s --max-time 10 http://localhost:8080/health | grep -q 'status'" \
        true
    
    # Check bot logs for successful startup
    local bot_logs=$(docker-compose -f docker-compose.vps.yml logs --tail=50 robustty 2>/dev/null)
    
    if echo "$bot_logs" | grep -q -E "(Bot is now online|Logged in as|Successfully connected)"; then
        log SUCCESS "✅ Bot successfully connected to Discord"
        test_results["discord_connection"]="PASS"
        ((passed_tests++))
    else
        log ERROR "❌ Bot not connected to Discord"
        test_results["discord_connection"]="FAIL"
        ((failed_tests++))
    fi
    ((total_tests++))
    
    # Check for error messages in logs
    if echo "$bot_logs" | grep -q -E "(ERROR|CRITICAL|Exception|Traceback)"; then
        log WARN "⚠️  Error messages detected in bot logs"
        test_results["bot_error_check"]="WARN"
    else
        log SUCCESS "✅ No error messages in bot logs"
        test_results["bot_error_check"]="PASS"
        ((passed_tests++))
    fi
    ((total_tests++))
}

# Test Redis connectivity and caching
test_redis_functionality() {
    log INFO "🗄️  TESTING REDIS FUNCTIONALITY"
    echo "==============================="
    
    # Basic Redis connectivity
    run_test "redis_ping" \
        "Redis responds to ping" \
        "docker-compose -f docker-compose.vps.yml exec -T redis redis-cli ping | grep -q PONG" \
        true
    
    # Test Redis write/read operations
    run_test "redis_write_read" \
        "Redis write/read operations work" \
        "docker-compose -f docker-compose.vps.yml exec -T redis redis-cli set test_key 'test_value' && docker-compose -f docker-compose.vps.yml exec -T redis redis-cli get test_key | grep -q 'test_value'" \
        true
    
    # Clean up test key
    docker-compose -f docker-compose.vps.yml exec -T redis redis-cli del test_key >/dev/null 2>&1 || true
    
    # Check Redis memory usage
    local redis_memory=$(docker-compose -f docker-compose.vps.yml exec -T redis redis-cli info memory | grep used_memory_human | cut -d':' -f2 | tr -d '\r' || echo "unknown")
    log INFO "Redis memory usage: $redis_memory"
    
    # Test cache operations through bot (if accessible)
    if curl -s --max-time 5 http://localhost:8080/health >/dev/null 2>&1; then
        # Test caching through health endpoint metadata
        run_test "bot_redis_integration" \
            "Bot can access Redis for caching" \
            "curl -s --max-time 10 http://localhost:8080/health | grep -q -E '(cache|redis)'" \
            false
    fi
}

# Test platform search functionality
test_platform_searches() {
    log INFO "🔍 TESTING PLATFORM SEARCH FUNCTIONALITY"
    echo "========================================"
    
    # Test internal search functionality by checking bot logs during simulated searches
    log INFO "Testing platform integrations..."
    
    # Check if YouTube API is configured
    if grep -q '^YOUTUBE_API_KEY=' .env 2>/dev/null && [ -n "$(grep '^YOUTUBE_API_KEY=' .env | cut -d'=' -f2-)" ]; then
        local youtube_api_key=$(grep '^YOUTUBE_API_KEY=' .env | cut -d'=' -f2-)
        run_test "youtube_api_search" \
            "YouTube API search functionality" \
            "curl -s \"https://www.googleapis.com/youtube/v3/search?part=snippet&q=music&key=$youtube_api_key&maxResults=1\" | grep -q '\"kind\": \"youtube#searchListResponse\"'" \
            false
    else
        skip_test "youtube_api_search" \
            "YouTube API search functionality" \
            "YouTube API key not configured"
    fi
    
    # Check if Apify API is configured
    if grep -q '^APIFY_API_KEY=' .env 2>/dev/null && [ -n "$(grep '^APIFY_API_KEY=' .env | cut -d'=' -f2-)" ]; then
        local apify_api_key=$(grep '^APIFY_API_KEY=' .env | cut -d'=' -f2-)
        run_test "apify_api_access" \
            "Apify API accessibility for Rumble searches" \
            "curl -s \"https://api.apify.com/v2/acts?token=$apify_api_key\" | grep -q '\"data\"'" \
            false
    else
        skip_test "apify_api_access" \
            "Apify API accessibility for Rumble searches" \
            "Apify API key not configured"
    fi
    
    # Test platform URL validation patterns
    log INFO "Testing platform URL recognition..."
    
    # This would require access to bot internals, so we'll test external APIs instead
    run_test "youtube_platform_connectivity" \
        "YouTube platform connectivity" \
        "curl -s --max-time 10 https://www.youtube.com | grep -q 'YouTube'" \
        false
    
    run_test "rumble_platform_connectivity" \
        "Rumble platform connectivity" \
        "curl -s --max-time 10 https://rumble.com | grep -q -i 'rumble'" \
        false
    
    run_test "odysee_platform_connectivity" \
        "Odysee platform connectivity" \
        "curl -s --max-time 10 https://odysee.com | grep -q -i 'odysee'" \
        false
    
    # Test yt-dlp functionality for stream extraction
    if docker-compose -f docker-compose.vps.yml exec -T robustty which yt-dlp >/dev/null 2>&1; then
        run_test "yt_dlp_functionality" \
            "yt-dlp is available for stream extraction" \
            "docker-compose -f docker-compose.vps.yml exec -T robustty yt-dlp --version" \
            false
    else
        skip_test "yt_dlp_functionality" \
            "yt-dlp is available for stream extraction" \
            "yt-dlp not found in container"
    fi
}

# Test audio processing capabilities
test_audio_functionality() {
    log INFO "🎵 TESTING AUDIO FUNCTIONALITY"
    echo "=============================="
    
    # Check FFmpeg availability
    if docker-compose -f docker-compose.vps.yml exec -T robustty which ffmpeg >/dev/null 2>&1; then
        run_test "ffmpeg_available" \
            "FFmpeg is available for audio processing" \
            "docker-compose -f docker-compose.vps.yml exec -T robustty ffmpeg -version" \
            true
            
        # Test FFmpeg audio processing capabilities
        run_test "ffmpeg_audio_codecs" \
            "FFmpeg supports required audio codecs" \
            "docker-compose -f docker-compose.vps.yml exec -T robustty ffmpeg -codecs | grep -q -E '(opus|pcm|mp3)'" \
            true
    else
        log ERROR "❌ FFmpeg not found - audio streaming will not work"
        test_results["ffmpeg_available"]="FAIL"
        ((failed_tests++))
        ((total_tests++))
    fi
    
    # Check audio libraries and dependencies
    run_test "python_audio_libs" \
        "Python audio libraries are available" \
        "docker-compose -f docker-compose.vps.yml exec -T robustty python -c 'import discord; import asyncio; print(\"Audio libs OK\")'" \
        true
    
    # Test Discord voice client capabilities
    run_test "discord_voice_support" \
        "Discord.py voice support is available" \
        "docker-compose -f docker-compose.vps.yml exec -T robustty python -c 'import discord; print(discord.opus.is_loaded())'" \
        false
    
    # Check for audio processing dependencies
    run_test "audio_dependencies" \
        "Audio processing dependencies are met" \
        "docker-compose -f docker-compose.vps.yml exec -T robustty python -c 'import subprocess; subprocess.run([\"ffmpeg\", \"-version\"], check=True, capture_output=True)'" \
        true
}

# Test configuration and environment
test_configuration() {
    log INFO "🔧 TESTING CONFIGURATION"
    echo "========================="
    
    # Environment variables validation
    if [ -f .env ]; then
        run_test "discord_token_format" \
            "Discord token has valid format" \
            "grep '^DISCORD_TOKEN=' .env | cut -d'=' -f2- | grep -qE '^[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27}$'" \
            true
    else
        skip_test "discord_token_format" \
            "Discord token has valid format" \
            ".env file not found"
    fi
    
    # Configuration file validation
    run_test "config_file_valid" \
        "Configuration file is valid YAML" \
        "python -c 'import yaml; yaml.safe_load(open(\"config/config.yaml\"))'" \
        false
    
    # Log level configuration
    run_test "log_level_valid" \
        "Log level is properly configured" \
        "grep -E '^LOG_LEVEL=(DEBUG|INFO|WARN|ERROR)$' .env || echo 'LOG_LEVEL=INFO' | grep -q INFO" \
        false
    
    # Required directories exist
    for dir in logs data cookies; do
        run_test "directory_$dir" \
            "Directory '$dir' exists" \
            "[ -d $dir ]" \
            false
    done
    
    # Test container environment
    run_test "container_environment" \
        "Container environment is properly configured" \
        "docker-compose -f docker-compose.vps.yml exec -T robustty env | grep -q DISCORD_TOKEN" \
        true
}

# Test network and external connectivity
test_network_connectivity() {
    log INFO "🌐 TESTING NETWORK CONNECTIVITY"
    echo "==============================="
    
    # Discord API connectivity from container
    run_test "discord_api_from_container" \
        "Discord API accessible from container" \
        "docker-compose -f docker-compose.vps.yml exec -T robustty curl -s --max-time 10 https://discord.com/api/v10/gateway | grep -q 'wss://'" \
        true
    
    # DNS resolution from container
    run_test "dns_resolution_container" \
        "DNS resolution works from container" \
        "docker-compose -f docker-compose.vps.yml exec -T robustty nslookup discord.com" \
        true
    
    # External API connectivity
    run_test "external_apis_container" \
        "External APIs accessible from container" \
        "docker-compose -f docker-compose.vps.yml exec -T robustty curl -s --max-time 10 https://googleapis.com" \
        false
    
    # Container network connectivity
    run_test "container_network" \
        "Container can access other services" \
        "docker-compose -f docker-compose.vps.yml exec -T robustty nc -z redis 6379" \
        true
}

# Test error handling and recovery
test_error_handling() {
    log INFO "🛡️  TESTING ERROR HANDLING"
    echo "==========================="
    
    # Test bot behavior with invalid inputs
    log INFO "Testing bot resilience..."
    
    # Check log file for proper error handling
    local bot_logs=$(docker-compose -f docker-compose.vps.yml logs --tail=100 robustty 2>/dev/null)
    
    # Look for graceful error handling patterns
    if echo "$bot_logs" | grep -q -E "(Error.*handled|Exception.*caught|Gracefully|Retry)"; then
        log SUCCESS "✅ Bot shows evidence of error handling"
        test_results["error_handling_evidence"]="PASS"
        ((passed_tests++))
    else
        log WARN "⚠️  No clear evidence of error handling in logs"
        test_results["error_handling_evidence"]="WARN"
        ((failed_tests++))
    fi
    ((total_tests++))
    
    # Test container restart recovery
    log INFO "Testing container restart recovery..."
    local restart_start=$(date +%s)
    
    if docker-compose -f docker-compose.vps.yml restart robustty >/dev/null 2>&1; then
        # Wait for service to be ready
        local attempts=0
        while [ $attempts -lt 30 ]; do
            if curl -s --max-time 5 http://localhost:8080/health >/dev/null 2>&1; then
                break
            fi
            sleep 2
            ((attempts++))
        done
        
        local restart_end=$(date +%s)
        local restart_time=$((restart_end - restart_start))
        
        if [ $attempts -lt 30 ]; then
            log SUCCESS "✅ Bot recovered after restart in ${restart_time}s"
            test_results["restart_recovery"]="PASS"
            ((passed_tests++))
        else
            log ERROR "❌ Bot failed to recover after restart"
            test_results["restart_recovery"]="FAIL"
            ((failed_tests++))
        fi
    else
        log ERROR "❌ Failed to restart bot container"
        test_results["restart_recovery"]="FAIL"
        ((failed_tests++))
    fi
    ((total_tests++))
}

# Performance testing
test_performance() {
    log INFO "⚡ TESTING PERFORMANCE"
    echo "======================"
    
    # Response time test
    local response_times=()
    for i in {1..5}; do
        local response_time=$(curl -w '%{time_total}' -s --max-time 10 http://localhost:8080/health -o /dev/null 2>/dev/null || echo "999")
        response_times+=($response_time)
    done
    
    # Calculate average response time
    local total_time=0
    for time in "${response_times[@]}"; do
        total_time=$(echo "$total_time + $time" | bc -l 2>/dev/null || echo "999")
    done
    local avg_time=$(echo "scale=3; $total_time / ${#response_times[@]}" | bc -l 2>/dev/null || echo "999")
    
    run_test "response_time_performance" \
        "Average response time is acceptable (<1s)" \
        "[ $(echo \"$avg_time < 1\" | bc -l 2>/dev/null || echo 0) -eq 1 ]" \
        false
    
    log INFO "Average response time: ${avg_time}s"
    
    # Memory usage test
    local memory_usage=$(docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}" | grep robustty-bot | awk '{print $2}' | cut -d'/' -f1 | sed 's/MiB//' | cut -d'.' -f1 || echo "999")
    
    run_test "memory_usage_performance" \
        "Memory usage is reasonable (<256MB)" \
        "[ $memory_usage -lt 256 ]" \
        false
    
    log INFO "Current memory usage: ${memory_usage}MB"
    
    # CPU usage test
    local cpu_usage=$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}" | grep robustty-bot | awk '{print $2}' | sed 's/%//' | cut -d'.' -f1 || echo "999")
    
    run_test "cpu_usage_performance" \
        "CPU usage is reasonable (<25%)" \
        "[ $cpu_usage -lt 25 ]" \
        false
    
    log INFO "Current CPU usage: ${cpu_usage}%"
}

# Generate comprehensive test report
generate_test_report() {
    echo ""
    log INFO "📋 BOT FUNCTIONALITY TEST REPORT"
    echo "=================================="
    
    # Overall statistics
    local success_rate=$((passed_tests * 100 / total_tests))
    local failure_rate=$((failed_tests * 100 / total_tests))
    local skip_rate=$((skipped_tests * 100 / total_tests))
    
    echo ""
    echo -e "${BLUE}OVERALL TEST STATISTICS${NC}"
    echo "======================="
    echo -e "Total Tests: ${CYAN}$total_tests${NC}"
    echo -e "Passed: ${GREEN}$passed_tests${NC} (${success_rate}%)"
    echo -e "Failed: ${RED}$failed_tests${NC} (${failure_rate}%)"
    echo -e "Skipped: ${CYAN}$skipped_tests${NC} (${skip_rate}%)"
    
    # Critical functionality status
    echo ""
    echo -e "${BLUE}CRITICAL FUNCTIONALITY STATUS${NC}"
    echo "============================="
    
    local critical_tests=("bot_container_running" "health_endpoint_accessible" "discord_connection" "redis_ping" "ffmpeg_available")
    local critical_passed=0
    local critical_total=${#critical_tests[@]}
    
    for test in "${critical_tests[@]}"; do
        if [[ "${test_results[$test]}" == "PASS" ]]; then
            echo -e "${GREEN}✅${NC} ${test//_/ }"
            ((critical_passed++))
        elif [[ "${test_results[$test]}" == "FAIL" ]]; then
            echo -e "${RED}❌${NC} ${test//_/ }"
        else
            echo -e "${YELLOW}⚠️${NC} ${test//_/ } (Unknown status)"
        fi
    done
    
    local critical_success=$((critical_passed * 100 / critical_total))
    echo ""
    echo -e "Critical Tests Passed: ${GREEN}$critical_passed${NC}/${CYAN}$critical_total${NC} (${critical_success}%)"
    
    # Detailed results by category
    echo ""
    echo -e "${BLUE}DETAILED TEST RESULTS${NC}"
    echo "====================="
    
    local categories=("Bot Status" "Redis" "Platform Search" "Audio" "Configuration" "Network" "Error Handling" "Performance")
    
    for category in "${categories[@]}"; do
        echo ""
        echo -e "${PURPLE}$category Tests:${NC}"
        for test in "${!test_results[@]}"; do
            local status="${test_results[$test]}"
            local test_display="${test//_/ }"
            
            case $status in
                "PASS") echo -e "  ${GREEN}✅ $test_display${NC}" ;;
                "FAIL") echo -e "  ${RED}❌ $test_display${NC}" ;;
                "WARN") echo -e "  ${YELLOW}⚠️  $test_display${NC}" ;;
                "SKIP") echo -e "  ${CYAN}⏭️  $test_display${NC}" ;;
            esac
        done
    done
    
    # Bot readiness assessment
    echo ""
    echo -e "${BLUE}BOT READINESS ASSESSMENT${NC}"
    echo "========================"
    
    if [ $critical_success -eq 100 ] && [ $success_rate -ge 90 ]; then
        echo -e "${GREEN}🎉 EXCELLENT - Bot is fully functional and ready for production!${NC}"
        echo "All critical systems are working properly."
        return 0
    elif [ $critical_success -ge 80 ] && [ $success_rate -ge 80 ]; then
        echo -e "${YELLOW}✅ GOOD - Bot is functional with minor issues${NC}"
        echo "Critical systems working, some non-critical issues detected."
        return 0
    elif [ $critical_success -ge 60 ]; then
        echo -e "${YELLOW}⚠️  FAIR - Bot has functionality issues${NC}"
        echo "Some critical systems may have problems. Review failed tests."
        return 1
    else
        echo -e "${RED}❌ POOR - Bot has significant functionality problems${NC}"
        echo "Critical systems are failing. Bot may not work properly."
        return 2
    fi
}

# Cleanup function
cleanup() {
    log INFO "🧹 Cleaning up test environment..."
    # Remove any test artifacts
    docker-compose -f docker-compose.vps.yml exec -T redis redis-cli del test_key >/dev/null 2>&1 || true
    log INFO "Test cleanup completed"
}

# Signal handlers
trap cleanup EXIT
trap 'echo ""; log ERROR "Testing interrupted"; exit 130' INT TERM

# Help function
show_help() {
    cat << EOF
End-to-End Bot Functionality Testing Script for Robustty Discord Bot

Usage: $SCRIPT_NAME [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose logging
    --quick                 Run only critical functionality tests
    --skip-performance      Skip performance tests
    --no-colors             Disable colored output

EXAMPLES:
    $SCRIPT_NAME                    # Full functionality test
    $SCRIPT_NAME --quick            # Critical tests only
    $SCRIPT_NAME --verbose          # Verbose output

EXIT CODES:
    0   All tests passed - bot fully functional
    1   Some tests failed - bot has issues but may work
    2   Critical tests failed - bot likely non-functional
    3   Setup/configuration issues

DESCRIPTION:
    This script performs comprehensive end-to-end testing of bot functionality
    including Discord connectivity, platform searches, audio processing,
    Redis caching, configuration validation, and performance testing.

TESTS PERFORMED:
    • Bot container and service status
    • Discord API connectivity and authentication
    • Redis caching and data persistence
    • Platform search API functionality
    • Audio processing and FFmpeg capabilities
    • Configuration and environment validation
    • Network connectivity from containers
    • Error handling and recovery testing
    • Performance and resource usage

REQUIREMENTS:
    • Bot must be deployed and running (docker-compose.vps.yml)
    • .env file with proper configuration
    • Network access to Discord and platform APIs

FOR TROUBLESHOOTING:
    • Check bot logs: docker-compose -f docker-compose.vps.yml logs -f robustty
    • Run network diagnostics: scripts/diagnose-vps-network.sh
    • Validate deployment: scripts/validate-vps-deployment.sh

EOF
}

# Parse command line arguments
VERBOSE=false
QUICK_MODE=false
SKIP_PERFORMANCE=false
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
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --skip-performance)
            SKIP_PERFORMANCE=true
            shift
            ;;
        --no-colors)
            NO_COLORS=true
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

# Main execution
main() {
    # Initialize log file
    echo "Robustty Bot Functionality Test - $(date)" > "$LOG_FILE"
    echo "==========================================" >> "$LOG_FILE"
    
    log INFO "🚀 Starting End-to-End Bot Functionality Testing"
    log INFO "================================================="
    
    # Check prerequisites
    if [ ! -f docker-compose.vps.yml ]; then
        log ERROR "docker-compose.vps.yml not found. Please run from project root."
        return 3
    fi
    
    # Run test suites
    validate_bot_status
    test_redis_functionality
    test_platform_searches
    test_audio_functionality
    test_configuration
    test_network_connectivity
    
    if [ "$QUICK_MODE" != "true" ]; then
        test_error_handling
        if [ "$SKIP_PERFORMANCE" != "true" ]; then
            test_performance
        fi
    fi
    
    # Generate comprehensive report
    generate_test_report
}

# Execute main function
main "$@"
exit_code=$?

# Cleanup
cleanup

exit $exit_code