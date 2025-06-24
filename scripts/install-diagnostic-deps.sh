#!/bin/bash

# Install dependencies for Discord 4006 diagnostics

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Installing Discord 4006 Diagnostics Dependencies${NC}"
echo "================================================="

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}Error: pip3 not found. Please install Python 3 and pip first.${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "\n${GREEN}Installing Python packages...${NC}"
pip3 install requests aiohttp discord.py

# Check if jq is available (for JSON parsing)
if ! command -v jq &> /dev/null; then
    echo -e "\n${YELLOW}jq not found. Installing...${NC}"
    
    # Detect OS and install jq
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install jq
        else
            echo -e "${YELLOW}Homebrew not found. Please install jq manually: https://stedolan.github.io/jq/download/${NC}"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y jq
        elif command -v yum &> /dev/null; then
            sudo yum install -y jq
        elif command -v pacman &> /dev/null; then
            sudo pacman -S jq
        else
            echo -e "${YELLOW}Package manager not detected. Please install jq manually.${NC}"
        fi
    else
        echo -e "${YELLOW}OS not detected. Please install jq manually: https://stedolan.github.io/jq/download/${NC}"
    fi
fi

# Verify installations
echo -e "\n${GREEN}Verifying installations...${NC}"

# Check Python modules
for module in requests aiohttp discord; do
    if python3 -c "import $module" 2>/dev/null; then
        echo -e "✅ Python module $module: Available"
    else
        echo -e "❌ Python module $module: Failed to install"
    fi
done

# Check command line tools
for cmd in jq curl ping nslookup; do
    if command -v "$cmd" &> /dev/null; then
        echo -e "✅ Command $cmd: Available"
    else
        echo -e "❌ Command $cmd: Not available"
    fi
done

echo -e "\n${GREEN}Installation complete!${NC}"
echo -e "You can now run: ${YELLOW}./scripts/run-4006-diagnostics.sh${NC}"