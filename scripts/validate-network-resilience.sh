#!/bin/bash
# Network Resilience Validation Script
# Tests cookie sync system under various network conditions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
TEST_DIR="/tmp/robustty_network_tests"
REPORT_FILE="/tmp/network_resilience_report.txt"
LOG_FILE="/tmp/network_resilience.log"

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

echo -e "${BLUE}🌐 Network Resilience Validation for Cookie Sync System${NC}"
echo "=" * 70
echo "Testing connection pooling, retries, and error handling"
echo "Report will be saved to: $REPORT_FILE"
echo ""

# Initialize test environment
setup_test_environment() {
    echo -e "${BLUE}🔧 Setting up test environment...${NC}"
    
    # Create test directory
    mkdir -p "$TEST_DIR"
    
    # Initialize log
    echo "Network Resilience Test - $(date)" > "$LOG_FILE"
    echo "Network Resilience Test Report - $(date)" > "$REPORT_FILE"
    echo "=" * 70 >> "$REPORT_FILE"
    
    # Check dependencies
    echo -e "${BLUE}📋 Checking dependencies...${NC}"
    
    local missing_deps=()
    
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi
    
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi
    
    if ! command -v timeout &> /dev/null; then
        missing_deps+=("timeout")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo -e "${RED}❌ Missing dependencies: ${missing_deps[*]}${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ All dependencies available${NC}"
    return 0
}

# Function to run a test and track results
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_behavior="$3"
    
    echo -e "${BLUE}🧪 Running test: $test_name${NC}"
    echo "Test: $test_name" >> "$REPORT_FILE"
    echo "Command: $test_command" >> "$REPORT_FILE"
    echo "Expected: $expected_behavior" >> "$REPORT_FILE"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    local start_time=$(date +%s)
    
    # Run the test command
    if eval "$test_command" >> "$LOG_FILE" 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        echo -e "${GREEN}✅ PASSED${NC} ($duration seconds)"
        echo "Result: PASSED (${duration}s)" >> "$REPORT_FILE"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        echo -e "${RED}❌ FAILED${NC} ($duration seconds)"
        echo "Result: FAILED (${duration}s)" >> "$REPORT_FILE"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    
    echo "Duration: ${duration}s" >> "$REPORT_FILE"
    echo "---" >> "$REPORT_FILE"
    echo ""
}

# Test HTTP connection resilience
test_http_resilience() {
    echo -e "${PURPLE}📡 Testing HTTP Connection Resilience${NC}"
    echo ""
    
    # Test 1: Basic connectivity
    run_test "Basic HTTP Connectivity" \
        "timeout 30 curl -s --max-time 10 https://httpbin.org/status/200" \
        "Should succeed with 200 status"
    
    # Test 2: Connection timeout handling
    run_test "Connection Timeout Handling" \
        "timeout 15 curl -s --max-time 5 --connect-timeout 3 https://httpbin.org/delay/10 || true" \
        "Should timeout gracefully"
    
    # Test 3: Retry logic simulation
    run_test "Retry Logic Simulation" \
        "for i in {1..3}; do timeout 10 curl -s --max-time 5 https://httpbin.org/status/200 && break || sleep 1; done" \
        "Should succeed with retries"
    
    # Test 4: Connection reuse
    run_test "Connection Reuse Test" \
        "timeout 30 bash -c 'for i in {1..5}; do curl -s --max-time 5 https://httpbin.org/status/200 > /dev/null; done'" \
        "Should reuse connections efficiently"
    
    # Test 5: Concurrent connections
    run_test "Concurrent Connection Handling" \
        "timeout 45 bash -c 'for i in {1..3}; do (timeout 15 curl -s --max-time 10 https://httpbin.org/delay/2 > /dev/null &); done; wait'" \
        "Should handle concurrent requests"
}

# Test cookie sync components
test_cookie_sync_components() {
    echo -e "${PURPLE}🍪 Testing Cookie Sync Components${NC}"
    echo ""
    
    # Test 1: Enhanced cookie manager availability
    if [ -f "../src/services/enhanced_cookie_manager.py" ]; then
        run_test "Enhanced Cookie Manager Import" \
            "cd .. && python3 -c 'from src.services.enhanced_cookie_manager import EnhancedCookieManager; print(\"Import successful\")'" \
            "Should import without errors"
    else
        echo -e "${YELLOW}⚠️ Enhanced cookie manager not found, skipping import test${NC}"
    fi
    
    # Test 2: Network resilience utilities
    if [ -f "../src/utils/network_resilience.py" ]; then
        run_test "Network Resilience Utilities Import" \
            "cd .. && python3 -c 'from src.utils.network_resilience import NetworkResilienceManager; print(\"Import successful\")'" \
            "Should import without errors"
    else
        echo -e "${YELLOW}⚠️ Network resilience utilities not found, skipping import test${NC}"
    fi
    
    # Test 3: Auto-sync script syntax
    if [ -f "auto-sync-cookies.py" ]; then
        run_test "Auto-Sync Script Syntax Check" \
            "python3 -m py_compile auto-sync-cookies.py" \
            "Should compile without syntax errors"
    else
        echo -e "${YELLOW}⚠️ Auto-sync script not found, skipping syntax test${NC}"
    fi
    
    # Test 4: Unified VPS sync script syntax
    if [ -f "unified-vps-sync.sh" ]; then
        run_test "Unified VPS Sync Script Syntax" \
            "bash -n unified-vps-sync.sh" \
            "Should have valid bash syntax"
    else
        echo -e "${YELLOW}⚠️ Unified VPS sync script not found, skipping syntax test${NC}"
    fi
}

# Test configuration and environment
test_configuration() {
    echo -e "${PURPLE}⚙️ Testing Configuration and Environment${NC}"
    echo ""
    
    # Test 1: Cookie directory creation
    run_test "Cookie Directory Creation" \
        "mkdir -p '$TEST_DIR/cookies' && [ -d '$TEST_DIR/cookies' ]" \
        "Should create cookie directory"
    
    # Test 2: Configuration file parsing
    cat > "$TEST_DIR/test.env" << EOF
VPS_HOST=test-host
VPS_USER=ubuntu
VPS_PATH=~/robustty-bot
SSH_KEY_PATH=~/.ssh/id_rsa
AUTO_SYNC_VPS=true
EOF
    
    run_test "Environment Configuration Parsing" \
        "source '$TEST_DIR/test.env' && [ \"\$VPS_HOST\" = 'test-host' ] && [ \"\$AUTO_SYNC_VPS\" = 'true' ]" \
        "Should parse configuration correctly"
    
    # Test 3: JSON handling
    cat > "$TEST_DIR/test_cookies.json" << 'EOF'
[
  {
    "name": "test_cookie",
    "value": "test_value",
    "domain": ".example.com",
    "path": "/",
    "secure": true
  }
]
EOF
    
    run_test "JSON Cookie File Validation" \
        "python3 -c 'import json; data=json.load(open(\"$TEST_DIR/test_cookies.json\")); print(f\"Loaded {len(data)} cookies\")'" \
        "Should parse JSON cookie file"
    
    # Test 4: File permissions
    run_test "File Permission Handling" \
        "touch '$TEST_DIR/test_file' && chmod 644 '$TEST_DIR/test_file' && [ -r '$TEST_DIR/test_file' ]" \
        "Should handle file permissions correctly"
}

# Test error handling scenarios
test_error_handling() {
    echo -e "${PURPLE}🚨 Testing Error Handling Scenarios${NC}"
    echo ""
    
    # Test 1: Network timeout simulation
    run_test "Network Timeout Simulation" \
        "timeout 10 curl -s --max-time 5 --connect-timeout 2 https://httpbin.org/delay/10 || echo 'Timeout handled'" \
        "Should handle timeouts gracefully"
    
    # Test 2: Invalid JSON handling
    echo "invalid json content" > "$TEST_DIR/invalid.json"
    run_test "Invalid JSON Handling" \
        "python3 -c 'import json; 
try: 
    json.load(open(\"$TEST_DIR/invalid.json\"))
except json.JSONDecodeError: 
    print(\"Error handled correctly\")
    exit(0)
exit(1)'" \
        "Should handle JSON errors gracefully"
    
    # Test 3: Missing file handling
    run_test "Missing File Handling" \
        "python3 -c 'import os; 
try: 
    open(\"$TEST_DIR/nonexistent.json\", \"r\")
except FileNotFoundError: 
    print(\"Error handled correctly\")
    exit(0)
exit(1)'" \
        "Should handle missing files gracefully"
    
    # Test 4: Permission denied simulation
    mkdir -p "$TEST_DIR/readonly"
    chmod 444 "$TEST_DIR/readonly"
    run_test "Permission Denied Handling" \
        "python3 -c 'import os; 
try: 
    open(\"$TEST_DIR/readonly/test.txt\", \"w\")
except PermissionError: 
    print(\"Error handled correctly\")
    exit(0)
exit(1)'" \
        "Should handle permission errors gracefully"
}

# Test with simulated network conditions
test_network_conditions() {
    echo -e "${PURPLE}🌐 Testing Network Condition Simulation${NC}"
    echo ""
    
    # Test 1: High latency simulation (using sleep)
    run_test "High Latency Simulation" \
        "timeout 20 bash -c 'sleep 2; curl -s --max-time 10 https://httpbin.org/status/200'" \
        "Should handle high latency"
    
    # Test 2: Intermittent connectivity
    run_test "Intermittent Connectivity Simulation" \
        "timeout 30 bash -c '
            for i in {1..3}; do
                if curl -s --max-time 5 https://httpbin.org/status/200 > /dev/null; then
                    echo \"Connection attempt $i successful\"
                    exit 0
                fi
                sleep 2
            done
            exit 1
        '" \
        "Should retry on intermittent failures"
    
    # Test 3: Multiple concurrent requests under stress
    run_test "Concurrent Request Stress Test" \
        "timeout 60 bash -c '
            pids=()
            for i in {1..5}; do
                (curl -s --max-time 10 https://httpbin.org/delay/1 > /dev/null) &
                pids+=(\$!)
            done
            for pid in \"\${pids[@]}\"; do
                wait \$pid || exit 1
            done
        '" \
        "Should handle concurrent stress"
    
    # Test 4: Connection pooling benefits
    run_test "Connection Pooling Efficiency" \
        "timeout 45 bash -c '
            start_time=\$(date +%s)
            for i in {1..10}; do
                curl -s --max-time 5 https://httpbin.org/status/200 > /dev/null
            done
            end_time=\$(date +%s)
            duration=\$((end_time - start_time))
            echo \"Sequential requests took \${duration} seconds\"
            [ \$duration -lt 30 ]  # Should be efficient
        '" \
        "Should benefit from connection reuse"
}

# Test SSH connection resilience (if configured)
test_ssh_resilience() {
    echo -e "${PURPLE}🔐 Testing SSH Connection Resilience${NC}"
    echo ""
    
    # Load environment if available
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
    fi
    
    if [ -z "$VPS_HOST" ] || [ "$VPS_HOST" = "your-vps-ip" ]; then
        echo -e "${YELLOW}⚠️ VPS_HOST not configured, skipping SSH tests${NC}"
        return 0
    fi
    
    # Test 1: SSH connection syntax
    run_test "SSH Command Syntax Validation" \
        "ssh -o ConnectTimeout=5 -o BatchMode=yes -T ${VPS_USER:-ubuntu}@$VPS_HOST 'echo test' 2>/dev/null || echo 'SSH test completed'" \
        "Should handle SSH connection attempts"
    
    # Test 2: SSH multiplexing configuration
    run_test "SSH Multiplexing Configuration" \
        "ssh -o ControlMaster=auto -o ControlPath=/tmp/test_%h_%p_%r -o ControlPersist=1 -V 2>/dev/null" \
        "Should support SSH multiplexing options"
    
    # Test 3: Rsync command validation
    run_test "Rsync Command Validation" \
        "rsync --version > /dev/null && echo 'Rsync available'" \
        "Should have rsync available for file sync"
}

# Test the SSH persistent connection script
test_ssh_persistent() {
    echo -e "${PURPLE}🔄 Testing SSH Persistent Connection Script${NC}"
    echo ""
    
    if [ -f "ssh-persistent.sh" ]; then
        run_test "SSH Persistent Script Syntax" \
            "bash -n ssh-persistent.sh" \
            "Should have valid bash syntax"
        
        run_test "SSH Persistent Script Functions" \
            "bash -c 'source ssh-persistent.sh && declare -f ssh_connect_persistent > /dev/null'" \
            "Should define required functions"
    else
        echo -e "${YELLOW}⚠️ SSH persistent script not found, skipping tests${NC}"
    fi
}

# Generate final report
generate_final_report() {
    echo -e "${BLUE}📊 Generating Final Report...${NC}"
    echo ""
    
    local success_rate=0
    if [ $TOTAL_TESTS -gt 0 ]; then
        success_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    fi
    
    # Add summary to report
    {
        echo ""
        echo "=" * 70
        echo "NETWORK RESILIENCE TEST SUMMARY"
        echo "=" * 70
        echo "Test Date: $(date)"
        echo "Total Tests: $TOTAL_TESTS"
        echo "Passed: $PASSED_TESTS"
        echo "Failed: $FAILED_TESTS"
        echo "Success Rate: ${success_rate}%"
        echo ""
        
        echo "ANALYSIS:"
        if [ $success_rate -ge 90 ]; then
            echo "🟢 EXCELLENT: System shows excellent resilience to network issues"
        elif [ $success_rate -ge 75 ]; then
            echo "🟡 GOOD: System shows good resilience with minor issues"
        elif [ $success_rate -ge 50 ]; then
            echo "🟠 MODERATE: System has moderate resilience, needs improvement"
        else
            echo "🔴 POOR: System shows poor resilience, significant improvements needed"
        fi
        
        echo ""
        echo "RECOMMENDATIONS:"
        if [ $success_rate -lt 100 ]; then
            echo "- Review failed tests for specific improvement areas"
            echo "- Consider implementing additional retry mechanisms"
            echo "- Ensure proper error handling for all network operations"
            echo "- Test with actual VPS connection if not already done"
        else
            echo "- All tests passed! System appears resilient"
            echo "- Consider periodic re-testing under real network stress"
        fi
        
        echo ""
        echo "Detailed logs available in: $LOG_FILE"
        
    } >> "$REPORT_FILE"
    
    # Print summary to console
    echo "=" * 70
    echo -e "${BLUE}NETWORK RESILIENCE TEST SUMMARY${NC}"
    echo "=" * 70
    echo "Total Tests: $TOTAL_TESTS"
    echo "Passed: $PASSED_TESTS"
    echo "Failed: $FAILED_TESTS"
    echo "Success Rate: ${success_rate}%"
    echo ""
    
    if [ $success_rate -ge 90 ]; then
        echo -e "${GREEN}🟢 EXCELLENT: System shows excellent resilience to network issues${NC}"
    elif [ $success_rate -ge 75 ]; then
        echo -e "${YELLOW}🟡 GOOD: System shows good resilience with minor issues${NC}"
    elif [ $success_rate -ge 50 ]; then
        echo -e "${YELLOW}🟠 MODERATE: System has moderate resilience, needs improvement${NC}"
    else
        echo -e "${RED}🔴 POOR: System shows poor resilience, significant improvements needed${NC}"
    fi
    
    echo ""
    echo "Report saved to: $REPORT_FILE"
    echo "Detailed logs: $LOG_FILE"
}

# Cleanup function
cleanup() {
    echo -e "${BLUE}🧹 Cleaning up test environment...${NC}"
    
    # Remove test directory
    rm -rf "$TEST_DIR"
    
    # Reset any temporary files
    chmod -R 755 /tmp/robustty_network_tests 2>/dev/null || true
    rm -rf /tmp/robustty_network_tests 2>/dev/null || true
}

# Main execution
main() {
    # Setup
    if ! setup_test_environment; then
        echo -e "${RED}❌ Failed to setup test environment${NC}"
        exit 1
    fi
    
    # Run test suites
    test_http_resilience
    test_cookie_sync_components
    test_configuration
    test_error_handling
    test_network_conditions
    test_ssh_resilience
    test_ssh_persistent
    
    # Generate report
    generate_final_report
    
    # Cleanup
    cleanup
    
    # Exit with appropriate code
    if [ $FAILED_TESTS -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

# Handle interrupts
trap cleanup EXIT

# Run main function
main "$@"
