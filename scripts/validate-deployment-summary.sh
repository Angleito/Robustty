#!/bin/bash
# VPS Deployment Validation Summary
# Quick overview of validation scripts and their usage

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

show_validation_summary() {
    cat << EOF
$(echo -e "${CYAN}🔍 ROBUSTTY VPS DEPLOYMENT VALIDATION SUMMARY${NC}")
========================================================

$(echo -e "${BLUE}📋 AVAILABLE VALIDATION SCRIPTS${NC}")
──────────────────────────────────

$(echo -e "${GREEN}1. Pre-Deployment Validation${NC}")
   Script: ./scripts/validate-pre-deployment.sh
   Purpose: Validates local environment and prerequisites before deployment
   Usage: ./scripts/validate-pre-deployment.sh [--skip-api] [--quick]
   
   Checks:
   • System resources (RAM, disk, CPU)
   • Network connectivity (DNS, Discord API, HTTPS)
   • Docker installation and configuration
   • Environment files and API keys
   • Basic security configuration

$(echo -e "${GREEN}2. Core VPS Validation${NC}")
   Script: ./scripts/validate-vps-core.sh
   Purpose: Essential VPS deployment validation with focused checks
   Usage: ./scripts/validate-vps-core.sh [--quick] [--no-docker]
   
   Checks:
   • Infrastructure (memory, disk, DNS, connectivity)
   • Docker services (containers, Redis, health endpoints)
   • Discord bot connection and functionality
   • Resource usage validation

$(echo -e "${GREEN}3. Comprehensive VPS Validation${NC}")
   Script: ./scripts/validate-vps-deployment.sh
   Purpose: Complete end-to-end validation (existing comprehensive script)
   Usage: ./scripts/validate-vps-deployment.sh [--category CATEGORY] [--quick]
   
   Categories: infrastructure, docker-services, discord-integration,
              platform-functionality, resource-monitoring, security-config

$(echo -e "${GREEN}4. Enhanced Deployment Script${NC}")
   Script: ./deploy-vps-with-validation.sh
   Purpose: VPS deployment with integrated validation checkpoints
   Usage: ./deploy-vps-with-validation.sh <vps-ip> [user] [validation-mode] [network]
   
   Validation Modes: full, quick, skip

$(echo -e "${BLUE}🚀 DEPLOYMENT WORKFLOW${NC}")
────────────────────────

$(echo -e "${YELLOW}Local Pre-Check:${NC}")
./scripts/validate-pre-deployment.sh

$(echo -e "${YELLOW}Deploy to VPS:${NC}")
./deploy-vps-with-validation.sh <vps-ip> ubuntu full auto

$(echo -e "${YELLOW}Or use standard deployment with validation:${NC}")
./deploy-vps.sh <vps-ip> ubuntu

$(echo -e "${YELLOW}Post-Deployment Validation (on VPS):${NC}")
ssh user@vps 'cd ~/robustty-bot && ./scripts/validate-vps-core.sh'

$(echo -e "${BLUE}📊 VALIDATION EXIT CODES${NC}")
──────────────────────────

0   All checks passed / Ready for deployment
1   Warnings present / Deployment possible with caution
2   Critical failures / Deployment not recommended
3   Script errors / Invalid arguments

$(echo -e "${BLUE}🔧 COMMON VALIDATION ISSUES & FIXES${NC}")
──────────────────────────────────────────

$(echo -e "${RED}DNS Resolution Failed:${NC}")
sudo echo 'nameserver 8.8.8.8' > /etc/resolv.conf
sudo echo 'nameserver 1.1.1.1' >> /etc/resolv.conf

$(echo -e "${RED}Docker Not Installed:${NC}")
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker \$USER

$(echo -e "${RED}Discord Token Issues:${NC}")
• Check token format in .env file
• Verify token in Discord Developer Portal
• Ensure bot has proper permissions

$(echo -e "${RED}Insufficient Resources:${NC}")
• Upgrade VPS to at least 1GB RAM
• Free up disk space (need 2GB+ free)
• Check for memory leaks in running containers

$(echo -e "${RED}Port Conflicts:${NC}")
• Port 8080: Health check endpoint
• Port 6379: Redis (internal Docker network)
• Use 'ss -tlnp | grep :PORT' to check usage

$(echo -e "${BLUE}📚 TROUBLESHOOTING RESOURCES${NC}")
──────────────────────────────────

• Network Issues: ./scripts/diagnose-vps-network.sh
• DNS Fixes: ./scripts/fix-vps-dns.sh
• Health Monitoring: ./scripts/monitor-vps-health.sh
• Documentation: docs/VPS_TROUBLESHOOTING.md

$(echo -e "${BLUE}🎯 VALIDATION BEST PRACTICES${NC}")
────────────────────────────────────

1. Always run pre-deployment validation locally first
2. Use 'quick' mode for faster deployment in trusted environments
3. Address critical failures before proceeding with deployment
4. Run post-deployment validation to confirm successful setup
5. Keep validation logs for troubleshooting
6. Regularly validate production deployments

$(echo -e "${GREEN}✅ VALIDATION CHECKLIST${NC}")
─────────────────────────

□ Pre-deployment validation passed locally
□ VPS environment meets requirements
□ Environment variables configured correctly
□ API keys valid and working
□ Docker services healthy
□ Discord bot connected successfully
□ Health endpoints responding
□ Resource usage within acceptable limits
□ Security configuration validated

EOF
}

# Show help
show_help() {
    cat << EOF
VPS Deployment Validation Summary

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help      Show this help
    --check         Run quick validation status check
    --list          List all validation scripts
    --examples      Show usage examples

DESCRIPTION:
    Displays summary of all available validation scripts and best practices
    for Robustty VPS deployment validation.
EOF
}

# Quick validation check
quick_validation_check() {
    echo -e "${CYAN}🔍 Quick Validation Status Check${NC}"
    echo "=================================="
    
    local scripts=("validate-pre-deployment.sh" "validate-vps-core.sh" "validate-vps-deployment.sh")
    local found=0
    
    for script in "${scripts[@]}"; do
        if [[ -f "scripts/$script" ]]; then
            echo -e "${GREEN}✅ scripts/$script${NC}"
            ((found++))
        else
            echo -e "${RED}❌ scripts/$script${NC}"
        fi
    done
    
    echo ""
    echo "Found $found/$(echo ${#scripts[@]}) validation scripts"
    
    if [[ -f .env ]]; then
        echo -e "${GREEN}✅ .env file exists${NC}"
    else
        echo -e "${YELLOW}⚠️  .env file missing${NC}"
    fi
    
    if [[ -f docker-compose.vps.yml ]]; then
        echo -e "${GREEN}✅ docker-compose.vps.yml exists${NC}"
    else
        echo -e "${RED}❌ docker-compose.vps.yml missing${NC}"
    fi
}

# List validation scripts
list_scripts() {
    echo -e "${BLUE}📋 Available Validation Scripts${NC}"
    echo "==============================="
    
    find scripts/ -name "*validate*" -type f -executable 2>/dev/null | while read script; do
        echo -e "${GREEN}• $script${NC}"
    done
    
    echo ""
    echo -e "${BLUE}📋 Deployment Scripts${NC}"
    echo "===================="
    
    local deploy_scripts=("deploy-vps.sh" "deploy-vps-with-validation.sh")
    for script in "${deploy_scripts[@]}"; do
        if [[ -f "$script" ]]; then
            echo -e "${GREEN}• $script${NC}"
        fi
    done
}

# Show examples
show_examples() {
    cat << EOF
$(echo -e "${CYAN}🎯 VALIDATION USAGE EXAMPLES${NC}")
================================

$(echo -e "${YELLOW}Example 1: Complete Validation Workflow${NC}")
# 1. Pre-deployment validation
./scripts/validate-pre-deployment.sh

# 2. Deploy with validation
./deploy-vps-with-validation.sh 192.168.1.100 ubuntu full auto

# 3. Post-deployment check (on VPS)
ssh ubuntu@192.168.1.100 'cd ~/robustty-bot && ./scripts/validate-vps-core.sh'

$(echo -e "${YELLOW}Example 2: Quick Deployment${NC}")
# Pre-check only critical items
./scripts/validate-pre-deployment.sh --quick

# Deploy with quick validation
./deploy-vps-with-validation.sh 192.168.1.100 ubuntu quick auto

$(echo -e "${YELLOW}Example 3: Troubleshooting Failed Deployment${NC}")
# Run comprehensive validation
./scripts/validate-vps-deployment.sh --verbose

# Check specific category
./scripts/validate-vps-deployment.sh --category infrastructure

# Network diagnostics
./scripts/diagnose-vps-network.sh

$(echo -e "${YELLOW}Example 4: Production Deployment${NC}")
# Full validation locally
./scripts/validate-pre-deployment.sh

# Manual deployment with validation checkpoints
./deploy-vps.sh 192.168.1.100 ubuntu

# Comprehensive post-deployment validation
ssh ubuntu@192.168.1.100 'cd ~/robustty-bot && ./scripts/validate-vps-deployment.sh'
EOF
}

# Parse arguments
case "${1:-summary}" in
    -h|--help)
        show_help
        exit 0
        ;;
    --check)
        quick_validation_check
        exit 0
        ;;
    --list)
        list_scripts
        exit 0
        ;;
    --examples)
        show_examples
        exit 0
        ;;
    summary|*)
        show_validation_summary
        exit 0
        ;;
esac