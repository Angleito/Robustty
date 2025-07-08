#!/bin/bash
# Verify Discord 530 diagnostic tools are ready for VPS deployment

echo "🚀 Verifying Discord 530 Tools for VPS Deployment"
echo "=================================================="

# Check if we're in the right directory
if [[ ! -f "scripts/discord-530-master.py" ]]; then
    echo "❌ Must run from project root directory"
    exit 1
fi

echo "📁 Checking required files..."
REQUIRED_FILES=(
    "scripts/diagnose-discord-530-comprehensive.py"
    "scripts/discord-530-decision-tree.py"
    "scripts/discord-530-master.py"
    "scripts/test-discord-530-tools.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "✅ $file"
    else
        echo "❌ Missing: $file"
        exit 1
    fi
done

echo ""
echo "🔧 Testing help commands..."
python scripts/discord-530-master.py --help > /dev/null 2>&1
if [[ $? -eq 0 ]]; then
    echo "✅ Master controller help works"
else
    echo "❌ Master controller help failed"
    exit 1
fi

echo ""
echo "🧪 Running test suite..."
python scripts/test-discord-530-tools.py > /dev/null 2>&1
if [[ $? -eq 0 ]]; then
    echo "✅ Test suite passed"
else
    echo "❌ Test suite failed"
    exit 1
fi

echo ""
echo "🐳 Checking Docker requirements..."
if [[ -f "Dockerfile" ]] && grep -q "requirements.txt" Dockerfile; then
    echo "✅ Dockerfile includes requirements.txt"
else
    echo "❌ Dockerfile missing or doesn't install requirements"
    exit 1
fi

if [[ -f "requirements.txt" ]] && grep -q "discord.py\|aiohttp\|psutil" requirements.txt; then
    echo "✅ Required dependencies in requirements.txt"
else
    echo "❌ Missing required dependencies"
    exit 1
fi

echo ""
echo "=================================================="
echo "✅ All checks passed! Tools are ready for VPS."
echo ""
echo "To deploy to VPS:"
echo "  ./deploy-vps.sh <vps-ip> ubuntu"
echo ""
echo "To test on VPS after deployment:"
echo "  ssh user@vps 'cd ~/robustty-bot && python scripts/discord-530-master.py --help'"
echo "  ssh user@vps 'cd ~/robustty-bot && python scripts/discord-530-master.py --mode quick'"