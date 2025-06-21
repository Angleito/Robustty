#!/bin/bash

# rebuild-help.sh
# Display help for Docker rebuild scripts
# Usage: ./scripts/rebuild-help.sh

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== ROBUSTTY DOCKER REBUILD SCRIPTS ===${NC}\n"

echo -e "${GREEN}Available rebuild scripts:${NC}"

echo -e "\n${BLUE}1. rebuild-with-fixes.sh${NC}"
echo "   Purpose: Complete Docker rebuild with discord.py fixes"
echo "   Features:"
echo "   - Clears Docker build cache completely"
echo "   - Forces rebuild with updated requirements.txt"
echo "   - Tests voice connection capabilities"
echo "   - Verifies all dependencies are properly installed"
echo "   Usage: ./scripts/rebuild-with-fixes.sh"

echo -e "\n${BLUE}2. update-discord-and-rebuild.sh${NC}"
echo "   Purpose: Update discord.py to latest version and rebuild"
echo "   Features:"
echo "   - Updates discord.py to latest or specified version"
echo "   - Updates PyNaCl and yt-dlp to compatible versions"
echo "   - Creates backup of requirements.txt"
echo "   - Runs full rebuild and voice tests"
echo "   Usage: ./scripts/update-discord-and-rebuild.sh [--discord-version VERSION]"
echo "   Example: ./scripts/update-discord-and-rebuild.sh --discord-version 2.3.2"

echo -e "\n${BLUE}3. test-voice-fixes.sh${NC}"
echo "   Purpose: Test voice connection fixes after rebuild"
echo "   Features:"
echo "   - Verifies discord.py voice dependencies"
echo "   - Tests network connectivity to Discord"
echo "   - Checks container networking configuration"
echo "   - Validates FFmpeg and PyNaCl installation"
echo "   Usage: ./scripts/test-voice-fixes.sh"

echo -e "\n${YELLOW}Quick Commands:${NC}"

echo -e "\n${GREEN}Standard rebuild with current requirements:${NC}"
echo "   ./scripts/rebuild-with-fixes.sh"

echo -e "\n${GREEN}Update to latest discord.py and rebuild:${NC}"
echo "   ./scripts/update-discord-and-rebuild.sh"

echo -e "\n${GREEN}Test voice fixes without rebuilding:${NC}"
echo "   ./scripts/test-voice-fixes.sh"

echo -e "\n${GREEN}View current container status:${NC}"
echo "   docker-compose ps"
echo "   docker-compose logs -f robustty"

echo -e "\n${GREEN}Quick restart without rebuild:${NC}"
echo "   docker-compose restart"

echo -e "\n${GREEN}Emergency stop and clean restart:${NC}"
echo "   docker-compose down && ./scripts/rebuild-with-fixes.sh"

echo -e "\n${RED}Troubleshooting:${NC}"

echo -e "\n${YELLOW}If rebuild fails:${NC}"
echo "1. Check Docker daemon is running"
echo "2. Ensure you have sufficient disk space"
echo "3. Verify .env file exists with required tokens"
echo "4. Try: docker system prune -af && ./scripts/rebuild-with-fixes.sh"

echo -e "\n${YELLOW}If voice connections still fail after rebuild:${NC}"
echo "1. Check Discord bot permissions (Connect, Speak, Use Voice Activity)"
echo "2. Verify bot is in the same server as the voice channel"
echo "3. Test with: ./scripts/test-voice-fixes.sh"
echo "4. Check logs: docker-compose logs -f robustty | grep -i voice"

echo -e "\n${YELLOW}If containers won't start:${NC}"
echo "1. Check environment variables in .env"
echo "2. Verify Redis port 6379 is available"
echo "3. Check Docker resource limits"
echo "4. Try: docker-compose down && docker system prune -f && docker-compose up -d"

echo -e "\n${CYAN}=== ADDITIONAL RESOURCES ===${NC}"
echo "- Project documentation: ./docs/"
echo "- Configuration: ./config/config.yaml"
echo "- Environment template: .env.example"
echo "- Integration tests: ./scripts/run-integration-tests.sh"

echo -e "\n${GREEN}For more help, check the CLAUDE.md file or project documentation.${NC}"