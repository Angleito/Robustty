#!/bin/bash

# VPS Deployment Test Runner
# Runs all tests for VPS deployment and cookie sync functionality

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
PASSED=0
FAILED=0
SKIPPED=0

# Function to log test results
log_test() {
    local test_name=$1
    local status=$2
    local message=$3
    
    case $status in
        "PASS")
            echo -e "${GREEN}✓${NC} $test_name"
            ((PASSED++))
            ;;
        "FAIL")
            echo -e "${RED}✗${NC} $test_name"
            echo -e "  ${RED}→${NC} $message"
            ((FAILED++))
            ;;
        "SKIP")
            echo -e "${YELLOW}○${NC} $test_name (skipped)"
            echo -e "  ${YELLOW}→${NC} $message"
            ((SKIPPED++))
            ;;
    esac
}

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"
    
    # Check Python
    if command -v python3 &> /dev/null; then
        log_test "Python 3 installed" "PASS"
    else
        log_test "Python 3 installed" "FAIL" "Python 3 is required"
        return 1
    fi
    
    # Check required Python packages
    local missing_packages=()
    for package in pytest hypothesis pyyaml; do
        if ! python3 -c "import $package" 2>/dev/null; then
            missing_packages+=($package)
        fi
    done
    
    if [ ${#missing_packages[@]} -eq 0 ]; then
        log_test "Python packages available" "PASS"
    else
        log_test "Python packages available" "FAIL" "Missing: ${missing_packages[*]}"
        echo -e "  Install with: pip install ${missing_packages[*]}"
        return 1
    fi
    
    # Check bash version
    if [ "${BASH_VERSION%%.*}" -ge 4 ]; then
        log_test "Bash version >= 4" "PASS"
    else
        log_test "Bash version >= 4" "FAIL" "Bash 4+ required, found $BASH_VERSION"
    fi
    
    return 0
}

# Test 1: Script syntax validation
test_script_syntax() {
    echo -e "\n${BLUE}Testing script syntax...${NC}"
    
    local scripts=(
        "scripts/sync-cookies-to-vps.sh"
        "scripts/check-cookie-sync.sh"
    )
    
    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            if bash -n "$script" 2>/dev/null; then
                log_test "Syntax check: $script" "PASS"
            else
                log_test "Syntax check: $script" "FAIL" "Syntax errors found"
            fi
        else
            log_test "Syntax check: $script" "SKIP" "File not found"
        fi
    done
}

# Test 2: Configuration file validation
test_configuration_files() {
    echo -e "\n${BLUE}Testing configuration files...${NC}"
    
    # Test docker-compose.vps.yml
    if [ -f "docker-compose.vps.yml" ]; then
        if python3 -c "import yaml; yaml.safe_load(open('docker-compose.vps.yml'))" 2>/dev/null; then
            log_test "docker-compose.vps.yml valid YAML" "PASS"
            
            # Check required services
            if python3 -c "
import yaml
config = yaml.safe_load(open('docker-compose.vps.yml'))
assert 'services' in config
assert 'robustty' in config['services']
assert 'redis' in config['services']
" 2>/dev/null; then
                log_test "Required services defined" "PASS"
            else
                log_test "Required services defined" "FAIL" "Missing required services"
            fi
        else
            log_test "docker-compose.vps.yml valid YAML" "FAIL" "Invalid YAML syntax"
        fi
    else
        log_test "docker-compose.vps.yml exists" "SKIP" "File not found"
    fi
    
    # Test .env.example
    if [ -f ".env.example" ]; then
        if grep -q "VPS_HOST=" ".env.example" && \
           grep -q "VPS_USER=" ".env.example" && \
           grep -q "SSH_KEY=" ".env.example"; then
            log_test ".env.example has VPS variables" "PASS"
        else
            log_test ".env.example has VPS variables" "FAIL" "Missing VPS configuration variables"
        fi
    else
        log_test ".env.example exists" "SKIP" "File not found"
    fi
}

# Test 3: Script functionality (mock environment)
test_script_functionality() {
    echo -e "\n${BLUE}Testing script functionality...${NC}"
    
    # Create temporary test environment
    TEST_DIR=$(mktemp -d)
    trap "rm -rf $TEST_DIR" EXIT
    
    # Test cookie directory creation
    mkdir -p "$TEST_DIR/cookies"
    echo '[]' > "$TEST_DIR/cookies/youtube_cookies.json"
    echo '[]' > "$TEST_DIR/cookies/rumble_cookies.json"
    
    if [ -d "$TEST_DIR/cookies" ] && [ -f "$TEST_DIR/cookies/youtube_cookies.json" ]; then
        log_test "Cookie directory structure" "PASS"
    else
        log_test "Cookie directory structure" "FAIL" "Failed to create test structure"
    fi
    
    # Test file age detection
    touch -t $(date -d '3 hours ago' +%Y%m%d%H%M 2>/dev/null || date -v-3H +%Y%m%d%H%M) "$TEST_DIR/cookies/old_cookies.json"
    
    if [ -f "$TEST_DIR/cookies/old_cookies.json" ]; then
        age_minutes=$(( ($(date +%s) - $(stat -f %m "$TEST_DIR/cookies/old_cookies.json" 2>/dev/null || stat -c %Y "$TEST_DIR/cookies/old_cookies.json")) / 60 ))
        if [ $age_minutes -gt 150 ]; then
            log_test "File age detection" "PASS"
        else
            log_test "File age detection" "FAIL" "Age calculation incorrect: $age_minutes minutes"
        fi
    else
        log_test "File age detection" "SKIP" "Could not create test file"
    fi
}

# Test 4: Run Python tests
test_python_tests() {
    echo -e "\n${BLUE}Running Python tests...${NC}"
    
    # Check if test files exist
    if [ -f "tests/test_vps_deployment.py" ]; then
        # Run property-based tests
        if python3 -m pytest tests/test_vps_deployment.py -v --tb=short -k "not integration" 2>/dev/null; then
            log_test "Property-based tests" "PASS"
        else
            log_test "Property-based tests" "FAIL" "Some tests failed"
        fi
    else
        log_test "Property-based tests" "SKIP" "Test file not found"
    fi
    
    if [ -f "tests/test_cookie_sync_integration.py" ]; then
        # Run integration tests
        if python3 -m pytest tests/test_cookie_sync_integration.py -v --tb=short 2>/dev/null; then
            log_test "Integration tests" "PASS"
        else
            log_test "Integration tests" "FAIL" "Some tests failed"
        fi
    else
        log_test "Integration tests" "SKIP" "Test file not found"
    fi
}

# Test 5: Security checks
test_security() {
    echo -e "\n${BLUE}Testing security configurations...${NC}"
    
    # Check for sensitive data in scripts
    local scripts=(
        "scripts/sync-cookies-to-vps.sh"
        "scripts/check-cookie-sync.sh"
    )
    
    local found_secrets=0
    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            if grep -E "(password|token|secret|api_key)=" "$script" | grep -v "^\s*#" | grep -v "DISCORD_WEBHOOK_URL" &>/dev/null; then
                found_secrets=1
            fi
        fi
    done
    
    if [ $found_secrets -eq 0 ]; then
        log_test "No hardcoded secrets" "PASS"
    else
        log_test "No hardcoded secrets" "FAIL" "Found potential hardcoded secrets"
    fi
    
    # Check SSH key permissions in documentation
    if grep -q "chmod 600" docs/VPS_DEPLOYMENT.md 2>/dev/null; then
        log_test "SSH key permissions documented" "PASS"
    else
        log_test "SSH key permissions documented" "SKIP" "Not found in documentation"
    fi
}

# Test 6: Documentation completeness
test_documentation() {
    echo -e "\n${BLUE}Testing documentation...${NC}"
    
    if [ -f "docs/VPS_DEPLOYMENT.md" ]; then
        # Check for required sections
        local required_sections=(
            "Prerequisites"
            "VPS Initial Setup"
            "SSH Key"
            "Cookie Sync"
            "Troubleshooting"
        )
        
        local missing=0
        for section in "${required_sections[@]}"; do
            if ! grep -q "$section" docs/VPS_DEPLOYMENT.md; then
                missing=1
                break
            fi
        done
        
        if [ $missing -eq 0 ]; then
            log_test "Documentation complete" "PASS"
        else
            log_test "Documentation complete" "FAIL" "Missing required sections"
        fi
    else
        log_test "VPS deployment documentation" "SKIP" "File not found"
    fi
}

# Main test execution
main() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}VPS Deployment Test Suite${NC}"
    echo -e "${BLUE}================================${NC}"
    
    # Run all test suites
    check_prerequisites || exit 1
    test_script_syntax
    test_configuration_files
    test_script_functionality
    test_python_tests
    test_security
    test_documentation
    
    # Summary
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}Test Summary${NC}"
    echo -e "${BLUE}================================${NC}"
    echo -e "${GREEN}Passed:${NC} $PASSED"
    echo -e "${RED}Failed:${NC} $FAILED"
    echo -e "${YELLOW}Skipped:${NC} $SKIPPED"
    
    if [ $FAILED -eq 0 ]; then
        echo -e "\n${GREEN}All tests passed! ✨${NC}"
        exit 0
    else
        echo -e "\n${RED}Some tests failed. Please review the output above.${NC}"
        exit 1
    fi
}

# Run main function
main "$@"