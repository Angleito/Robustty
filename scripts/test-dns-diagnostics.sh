#!/bin/bash

# Test script for DNS diagnostics functionality
# Usage: ./scripts/test-dns-diagnostics.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

echo -e "${BLUE}🧪 Testing DNS Diagnostics Scripts${NC}"
echo -e "${BLUE}===================================${NC}"
echo ""

# Test 1: Check if diagnostic scripts exist and are executable
print_info "Test 1: Checking diagnostic script files..."

if [ -f "scripts/diagnose-vps-network.sh" ] && [ -x "scripts/diagnose-vps-network.sh" ]; then
    print_success "diagnose-vps-network.sh exists and is executable"
else
    print_error "diagnose-vps-network.sh is missing or not executable"
fi

if [ -f "scripts/fix-vps-dns.sh" ] && [ -x "scripts/fix-vps-dns.sh" ]; then
    print_success "fix-vps-dns.sh exists and is executable"
else
    print_error "fix-vps-dns.sh is missing or not executable"
fi

if [ -f "docs/VPS-DNS-TROUBLESHOOTING.md" ]; then
    print_success "VPS-DNS-TROUBLESHOOTING.md documentation exists"
else
    print_error "VPS-DNS-TROUBLESHOOTING.md documentation is missing"
fi

echo ""

# Test 2: Basic DNS resolution test
print_info "Test 2: Testing basic DNS resolution..."

DISCORD_ENDPOINTS=("gateway-us-east1-d.discord.gg" "discord.com" "google.com")
for endpoint in "${DISCORD_ENDPOINTS[@]}"; do
    if nslookup "$endpoint" >/dev/null 2>&1; then
        print_success "DNS resolution OK for $endpoint"
    else
        print_warning "DNS resolution failed for $endpoint"
    fi
done

echo ""

# Test 3: Test connectivity to Discord HTTPS port
print_info "Test 3: Testing HTTPS connectivity..."

if command -v nc >/dev/null 2>&1; then
    if timeout 10 nc -z gateway-us-east1-d.discord.gg 443 >/dev/null 2>&1; then
        print_success "HTTPS connectivity to Discord gateway is working"
    else
        print_warning "HTTPS connectivity to Discord gateway failed"
    fi
else
    print_warning "netcat (nc) not available for connectivity testing"
fi

echo ""

# Test 4: Test diagnostic script functionality (dry run)
print_info "Test 4: Testing diagnostic script functions..."

# Test that the diagnostic script can be parsed without errors
if bash -n scripts/diagnose-vps-network.sh; then
    print_success "diagnose-vps-network.sh syntax is valid"
else
    print_error "diagnose-vps-network.sh has syntax errors"
fi

if bash -n scripts/fix-vps-dns.sh; then
    print_success "fix-vps-dns.sh syntax is valid"
else
    print_error "fix-vps-dns.sh has syntax errors"
fi

echo ""

# Test 5: Check Docker Compose DNS configuration
print_info "Test 5: Checking Docker Compose DNS configuration..."

if [ -f "docker-compose.vps.yml" ]; then
    if grep -q "dns:" docker-compose.vps.yml; then
        print_success "Docker Compose has DNS configuration"
    else
        print_warning "Docker Compose missing DNS configuration"
    fi
    
    if grep -q "healthcheck:" docker-compose.vps.yml; then
        print_success "Docker Compose has health checks configured"
    else
        print_warning "Docker Compose missing health checks"
    fi
else
    print_error "docker-compose.vps.yml not found"
fi

echo ""

# Test 6: Check deployment script integration
print_info "Test 6: Checking deployment script DNS integration..."

if grep -q "diagnose-vps-network.sh" deploy-vps.sh; then
    print_success "deploy-vps.sh references DNS diagnostics"
else
    print_warning "deploy-vps.sh missing DNS diagnostic references"
fi

if grep -q "DNS resolution" deploy-vps.sh; then
    print_success "deploy-vps.sh includes DNS resolution checks"
else
    print_warning "deploy-vps.sh missing DNS resolution checks"
fi

echo ""

# Test 7: Environment validation
print_info "Test 7: Environment validation..."

# Check if we have the tools needed for diagnostics
TOOLS=("nslookup" "dig" "ping" "curl")
for tool in "${TOOLS[@]}"; do
    if command -v "$tool" >/dev/null 2>&1; then
        print_success "$tool is available"
    else
        print_warning "$tool is not available (may be needed for full diagnostics)"
    fi
done

echo ""

# Summary
print_info "Test Summary:"
echo "The DNS diagnostics system includes:"
echo "  • Comprehensive network diagnostic script (diagnose-vps-network.sh)"
echo "  • Automated DNS fix script (fix-vps-dns.sh)"
echo "  • Integration with deployment scripts"
echo "  • Docker Compose DNS configuration"
echo "  • Detailed troubleshooting documentation"
echo ""
print_info "To test on a VPS:"
echo "  1. Deploy using ./deploy-vps.sh <vps-ip> <username>"
echo "  2. If DNS issues occur, run: ./scripts/diagnose-vps-network.sh"
echo "  3. Apply fixes with: sudo ./scripts/fix-vps-dns.sh"
echo "  4. Check documentation: docs/VPS-DNS-TROUBLESHOOTING.md"

echo ""
print_success "DNS diagnostics test completed!"