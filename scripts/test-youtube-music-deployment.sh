#!/bin/bash

# Test YouTube Music Headless Docker Deployment
# This script verifies that the complete Docker deployment is working correctly

set -e

echo "========================================"
echo "🎵 YouTube Music Docker Deployment Test"
echo "========================================"
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a container is running
check_container() {
    local container_name=$1
    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo -e "${GREEN}✅ Container '${container_name}' is running${NC}"
        return 0
    else
        echo -e "${RED}❌ Container '${container_name}' is not running${NC}"
        return 1
    fi
}

# Function to check container health
check_container_health() {
    local container_name=$1
    local health_status=$(docker inspect --format='{{.State.Health.Status}}' "${container_name}" 2>/dev/null || echo "none")
    
    if [ "$health_status" = "healthy" ]; then
        echo -e "${GREEN}✅ Container '${container_name}' is healthy${NC}"
        return 0
    elif [ "$health_status" = "none" ]; then
        echo -e "${YELLOW}⚠️  Container '${container_name}' has no health check${NC}"
        return 0
    else
        echo -e "${RED}❌ Container '${container_name}' is unhealthy (status: ${health_status})${NC}"
        return 1
    fi
}

# Function to check if a port is accessible
check_port() {
    local port=$1
    local service=$2
    if nc -z localhost "$port" 2>/dev/null; then
        echo -e "${GREEN}✅ Port ${port} (${service}) is accessible${NC}"
        return 0
    else
        echo -e "${RED}❌ Port ${port} (${service}) is not accessible${NC}"
        return 1
    fi
}

# Function to check HTTP endpoint
check_http_endpoint() {
    local url=$1
    local description=$2
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    
    if [ "$response" = "200" ]; then
        echo -e "${GREEN}✅ ${description} is responding (HTTP 200)${NC}"
        return 0
    elif [ "$response" = "000" ]; then
        echo -e "${RED}❌ ${description} is not reachable${NC}"
        return 1
    else
        echo -e "${YELLOW}⚠️  ${description} returned HTTP ${response}${NC}"
        return 1
    fi
}

# Function to check YouTube Music API
check_youtube_music_api() {
    local api_response=$(curl -s "http://localhost:9863/api/health" 2>/dev/null || echo "{}")
    
    if echo "$api_response" | grep -q '"status"'; then
        echo -e "${GREEN}✅ YouTube Music API is responding${NC}"
        echo "   Response: $api_response"
        return 0
    else
        echo -e "${RED}❌ YouTube Music API is not responding properly${NC}"
        return 1
    fi
}

# Function to check Docker network
check_docker_network() {
    if docker network ls --format '{{.Name}}' | grep -q "robustty-network"; then
        echo -e "${GREEN}✅ Docker network 'robustty-network' exists${NC}"
        
        # Check connected containers
        connected_containers=$(docker network inspect robustty-network --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null || echo "")
        if [ -n "$connected_containers" ]; then
            echo "   Connected containers: $connected_containers"
        fi
        return 0
    else
        echo -e "${RED}❌ Docker network 'robustty-network' not found${NC}"
        return 1
    fi
}

# Main test execution
echo "1. Checking Docker containers..."
echo "================================"
check_container "robustty-youtube-music"
check_container "robustty-bot"
check_container "robustty-redis"
echo ""

echo "2. Checking container health..."
echo "==============================="
check_container_health "robustty-youtube-music"
check_container_health "robustty-bot"
check_container_health "robustty-redis"
echo ""

echo "3. Checking network configuration..."
echo "===================================="
check_docker_network
echo ""

echo "4. Checking service ports..."
echo "============================"
check_port 9863 "YouTube Music API"
check_port 8080 "Bot Health Endpoints"
check_port 6379 "Redis" || echo -e "${YELLOW}   Note: Redis port might be internal only${NC}"
echo ""

echo "5. Checking HTTP endpoints..."
echo "============================="
check_http_endpoint "http://localhost:9863/api/health" "YouTube Music Health"
check_http_endpoint "http://localhost:8080/health" "Bot Health"
check_http_endpoint "http://localhost:8080/health/youtube-music" "YouTube Music Integration"
echo ""

echo "6. Checking YouTube Music API..."
echo "================================"
check_youtube_music_api
echo ""

echo "7. Checking container logs for errors..."
echo "========================================"
# Check for recent errors in YouTube Music container
ytm_errors=$(docker logs robustty-youtube-music 2>&1 | tail -20 | grep -i "error" || true)
if [ -z "$ytm_errors" ]; then
    echo -e "${GREEN}✅ No recent errors in YouTube Music container${NC}"
else
    echo -e "${YELLOW}⚠️  Found errors in YouTube Music container:${NC}"
    echo "$ytm_errors"
fi

# Check for recent errors in bot container
bot_errors=$(docker logs robustty-bot 2>&1 | tail -20 | grep -i "error" || true)
if [ -z "$bot_errors" ]; then
    echo -e "${GREEN}✅ No recent errors in bot container${NC}"
else
    echo -e "${YELLOW}⚠️  Found errors in bot container:${NC}"
    echo "$bot_errors"
fi
echo ""

echo "8. Running Python integration tests..."
echo "====================================="
if [ -f "tests/test_youtube_music_integration.py" ]; then
    echo "Running integration test suite..."
    python3 tests/test_youtube_music_integration.py || echo -e "${RED}Integration tests failed${NC}"
else
    echo -e "${YELLOW}⚠️  Integration test file not found${NC}"
fi
echo ""

echo "========================================"
echo "📊 Deployment Test Summary"
echo "========================================"
echo ""
echo "To view live logs:"
echo "  - YouTube Music: docker logs -f robustty-youtube-music"
echo "  - Bot: docker logs -f robustty-bot"
echo "  - All: docker-compose logs -f"
echo ""
echo "To restart services:"
echo "  - docker-compose restart"
echo "  - docker-compose down && docker-compose up -d"
echo ""
echo "Test completed!"