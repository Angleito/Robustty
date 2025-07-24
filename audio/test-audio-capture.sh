#!/bin/bash

# Test script for audio capture service

API_URL="http://localhost:3000"
INSTANCE_ID="neko-0"

echo "Testing Audio Capture Service"
echo "============================"

# Check health
echo -n "1. Checking service health... "
HEALTH=$(curl -s "$API_URL/health")
if [ $? -eq 0 ]; then
    echo "OK"
    echo "   Health Response: $(echo $HEALTH | jq -c .)"
else
    echo "FAILED"
    exit 1
fi

# List streams
echo -n "2. Listing active streams... "
STREAMS=$(curl -s "$API_URL/streams")
if [ $? -eq 0 ]; then
    echo "OK"
    echo "   Active Streams: $(echo $STREAMS | jq -c .)"
else
    echo "FAILED"
fi

# Test audio capture
echo "3. Testing audio capture for $INSTANCE_ID..."
echo "   Starting capture (press Ctrl+C to stop)..."

# Start capture in background and save to file
curl -s "$API_URL/capture/$INSTANCE_ID" > test-capture.opus &
CURL_PID=$!

# Let it run for 5 seconds
sleep 5

# Stop the capture
echo "   Stopping capture..."
kill $CURL_PID 2>/dev/null

# Check if file was created and has content
if [ -f test-capture.opus ] && [ -s test-capture.opus ]; then
    SIZE=$(ls -lh test-capture.opus | awk '{print $5}')
    echo "   Capture successful! File size: $SIZE"
    
    # Try to get file info with ffprobe if available
    if command -v ffprobe &> /dev/null; then
        echo "   File info:"
        ffprobe -v error -show_format -show_streams test-capture.opus 2>&1 | grep -E "(codec_name|duration|bit_rate)"
    fi
    
    rm test-capture.opus
else
    echo "   Capture failed - no data received"
fi

# Test routing endpoint
echo -n "4. Testing audio routing endpoint... "
ROUTE_RESP=$(curl -s -X POST "$API_URL/route/$INSTANCE_ID" -H "Content-Type: application/json" -d '{}')
if [ $? -eq 0 ]; then
    echo "OK"
    echo "   Route Response: $(echo $ROUTE_RESP | jq -c .)"
else
    echo "FAILED"
fi

echo ""
echo "Test completed!"