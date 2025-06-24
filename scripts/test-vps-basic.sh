#!/bin/bash

# Basic VPS Deployment Test Script
# Tests core functionality without requiring Python packages

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0

echo -e "${BLUE}=== Basic VPS Deployment Tests ===${NC}\n"

# Test 1: Check if scripts exist and are executable
echo -e "${BLUE}1. Testing script files...${NC}"

scripts=(
    "scripts/sync-cookies-to-vps.sh"
    "scripts/check-cookie-sync.sh"
    "scripts/extract-brave-cookies.py"
)

for script in "${scripts[@]}"; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            echo -e "${GREEN}✓${NC} $script exists and is executable"
            ((PASSED++))
        else
            echo -e "${YELLOW}!${NC} $script exists but is not executable"
            echo "  Run: chmod +x $script"
            ((FAILED++))
        fi
    else
        echo -e "${RED}✗${NC} $script not found"
        ((FAILED++))
    fi
done

# Test 2: Validate shell script syntax
echo -e "\n${BLUE}2. Testing shell script syntax...${NC}"

for script in "scripts/sync-cookies-to-vps.sh" "scripts/check-cookie-sync.sh"; do
    if [ -f "$script" ]; then
        if bash -n "$script" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} $script has valid syntax"
            ((PASSED++))
        else
            echo -e "${RED}✗${NC} $script has syntax errors:"
            bash -n "$script" 2>&1 | head -5
            ((FAILED++))
        fi
    fi
done

# Test 3: Check configuration files
echo -e "\n${BLUE}3. Testing configuration files...${NC}"

# Check docker-compose.vps.yml
if [ -f "docker-compose.vps.yml" ]; then
    # Basic YAML validation using Python
    if python3 -c "import yaml; yaml.safe_load(open('docker-compose.vps.yml'))" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} docker-compose.vps.yml is valid YAML"
        ((PASSED++))
        
        # Check for required keys
        if grep -q "services:" docker-compose.vps.yml && \
           grep -q "robustty:" docker-compose.vps.yml && \
           grep -q "redis:" docker-compose.vps.yml; then
            echo -e "${GREEN}✓${NC} Required services defined"
            ((PASSED++))
        else
            echo -e "${RED}✗${NC} Missing required services"
            ((FAILED++))
        fi
        
        # Check cookie volume mount
        if grep -q "/opt/robustty/cookies:/app/cookies:ro" docker-compose.vps.yml; then
            echo -e "${GREEN}✓${NC} Cookie volume mount configured"
            ((PASSED++))
        else
            echo -e "${RED}✗${NC} Cookie volume mount not found"
            ((FAILED++))
        fi
    else
        echo -e "${RED}✗${NC} docker-compose.vps.yml has invalid YAML"
        ((FAILED++))
    fi
else
    echo -e "${RED}✗${NC} docker-compose.vps.yml not found"
    ((FAILED++))
fi

# Check .env.example
echo -e "\n${BLUE}4. Testing environment configuration...${NC}"

if [ -f ".env.example" ]; then
    required_vars=(
        "VPS_HOST="
        "VPS_USER="
        "SSH_KEY="
        "VPS_COOKIE_DIR="
        "DISCORD_TOKEN="
        "YOUTUBE_API_KEY="
    )
    
    for var in "${required_vars[@]}"; do
        if grep -q "^$var" ".env.example"; then
            echo -e "${GREEN}✓${NC} $var found in .env.example"
            ((PASSED++))
        else
            echo -e "${RED}✗${NC} $var missing from .env.example"
            ((FAILED++))
        fi
    done
else
    echo -e "${RED}✗${NC} .env.example not found"
    ((FAILED++))
fi

# Test 5: Check documentation
echo -e "\n${BLUE}5. Testing documentation...${NC}"

if [ -f "docs/VPS_DEPLOYMENT.md" ]; then
    echo -e "${GREEN}✓${NC} VPS deployment documentation exists"
    ((PASSED++))
    
    # Check for important sections
    sections=("Prerequisites" "VPS Initial Setup" "Cookie Sync" "Troubleshooting")
    for section in "${sections[@]}"; do
        if grep -q "$section" docs/VPS_DEPLOYMENT.md; then
            echo -e "${GREEN}✓${NC} Documentation includes: $section"
            ((PASSED++))
        else
            echo -e "${YELLOW}!${NC} Documentation missing: $section"
            ((FAILED++))
        fi
    done
else
    echo -e "${RED}✗${NC} docs/VPS_DEPLOYMENT.md not found"
    ((FAILED++))
fi

# Test 6: Security checks
echo -e "\n${BLUE}6. Testing security...${NC}"

# Check for hardcoded secrets
found_secrets=0
for file in scripts/*.sh; do
    if [ -f "$file" ]; then
        # Look for potential secrets (excluding comments and examples)
        if grep -E "(password|token|secret|api_key)=[\"']?[A-Za-z0-9]" "$file" | \
           grep -v "^\s*#" | \
           grep -v "your_" | \
           grep -v "test_" | \
           grep -v "\${" &>/dev/null; then
            echo -e "${RED}✗${NC} Potential hardcoded secret in $file"
            ((FAILED++))
            found_secrets=1
        fi
    fi
done

if [ $found_secrets -eq 0 ]; then
    echo -e "${GREEN}✓${NC} No hardcoded secrets found"
    ((PASSED++))
fi

# Test 7: Cookie sync script validation
echo -e "\n${BLUE}7. Testing cookie sync script features...${NC}"

if [ -f "scripts/sync-cookies-to-vps.sh" ]; then
    # Check for required functions
    if grep -q "check_requirements" scripts/sync-cookies-to-vps.sh; then
        echo -e "${GREEN}✓${NC} Requirements check function present"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} Missing requirements check"
        ((FAILED++))
    fi
    
    # Check for error handling
    if grep -q "set -e\|error\|exit 1" scripts/sync-cookies-to-vps.sh; then
        echo -e "${GREEN}✓${NC} Error handling present"
        ((PASSED++))
    else
        echo -e "${YELLOW}!${NC} Limited error handling"
        ((FAILED++))
    fi
    
    # Check for rsync with proper flags
    if grep -q "rsync.*-avz.*--delete" scripts/sync-cookies-to-vps.sh; then
        echo -e "${GREEN}✓${NC} Rsync configured with proper flags"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} Rsync not properly configured"
        ((FAILED++))
    fi
fi

# Summary
echo -e "\n${BLUE}=== Test Summary ===${NC}"
echo -e "${GREEN}Passed:${NC} $PASSED"
echo -e "${RED}Failed:${NC} $FAILED"
total=$((PASSED + FAILED))
percentage=$((PASSED * 100 / total))

echo -e "\nSuccess rate: ${percentage}%"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed! ✨${NC}"
    echo -e "The VPS deployment scripts are ready to use."
    exit 0
else
    echo -e "\n${YELLOW}Some tests failed.${NC}"
    echo -e "Please review the issues above before deployment."
    exit 1
fi