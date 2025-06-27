#!/bin/bash

# Script to test PeerTube instance connectivity
# Usage: ./scripts/test-peertube-instances.sh [timeout]

set -e

TIMEOUT=${1:-10}
SEARCH_QUERY="music"
MAX_RESULTS=1

echo "Testing PeerTube instance connectivity..."
echo "Timeout: ${TIMEOUT}s"
echo "Search query: ${SEARCH_QUERY}"
echo "=========================================="

# List of instances from config.yaml
INSTANCES=(
    "https://tube.tchncs.de"
    "https://peertube.tv"
    "https://framatube.org"
    "https://video.ploud.fr"
    "https://tilvids.com"
    "https://makertube.net"
    "https://diode.zone"
    "https://tube.shanti.cafe"
    "https://video.infosec.exchange"
    "https://videos.spacefun.ch"
    "https://videos.elenarossini.com"
    "https://peertube.heise.de"
)

SUCCESS_COUNT=0
TOTAL_COUNT=${#INSTANCES[@]}

for instance in "${INSTANCES[@]}"; do
    echo -n "Testing ${instance}... "
    
    # Extract domain for display
    DOMAIN=$(echo "$instance" | sed 's|https://||')
    
    # Test the instance
    RESPONSE=$(curl -s --max-time "$TIMEOUT" "${instance}/api/v1/search/videos?search=${SEARCH_QUERY}&count=${MAX_RESULTS}" 2>/dev/null || echo "FAILED")
    
    if echo "$RESPONSE" | jq -e '.total' >/dev/null 2>&1; then
        TOTAL_VIDEOS=$(echo "$RESPONSE" | jq -r '.total')
        echo "✅ SUCCESS (${TOTAL_VIDEOS} results)"
        ((SUCCESS_COUNT++))
    else
        echo "❌ FAILED"
        echo "   Response: ${RESPONSE:0:100}..."
    fi
done

echo "=========================================="
echo "Results: ${SUCCESS_COUNT}/${TOTAL_COUNT} instances working"

if [ "$SUCCESS_COUNT" -ge 4 ]; then
    echo "✅ PeerTube configuration is healthy (minimum 4 instances working)"
    exit 0
else
    echo "⚠️  PeerTube configuration needs attention (less than 4 instances working)"
    exit 1
fi