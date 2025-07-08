#!/bin/bash
# Fix YouTube Music Headless Connection Issues on VPS

set -e

echo "🔧 YouTube Music Connection Fix Script"
echo "====================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check container status
check_container() {
    local container_name="$1"
    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        local status=$(docker inspect -f '{{.Status}}' "$container_name" 2>/dev/null || echo "unknown")
        echo "$status"
    else
        echo "not found"
    fi
}

# Function to check container health
check_container_health() {
    local container_name="$1"
    local health=$(docker inspect -f '{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "no health check")
    echo "$health"
}

echo -e "\n📊 Checking current status..."

# Check Docker
if ! command_exists docker; then
    echo "❌ Docker is not installed!"
    exit 1
fi

# Check docker-compose
if ! command_exists docker-compose; then
    echo "❌ docker-compose is not installed!"
    exit 1
fi

# Check YouTube Music container
YT_MUSIC_STATUS=$(check_container "robustty-youtube-music")
YT_MUSIC_HEALTH=$(check_container_health "robustty-youtube-music")
echo "YouTube Music Container: $YT_MUSIC_STATUS (Health: $YT_MUSIC_HEALTH)"

# Check bot container
BOT_STATUS=$(check_container "robustty-bot")
BOT_HEALTH=$(check_container_health "robustty-bot")
echo "Bot Container: $BOT_STATUS (Health: $BOT_HEALTH)"

# Check Redis container
REDIS_STATUS=$(check_container "robustty-redis")
REDIS_HEALTH=$(check_container_health "robustty-redis")
echo "Redis Container: $REDIS_STATUS (Health: $REDIS_HEALTH)"

echo -e "\n🔍 Checking Docker network..."
if docker network ls | grep -q "robustty_robustty-network"; then
    echo "✅ Docker network exists"
    # Show network details
    docker network inspect robustty_robustty-network --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}}{{println}}{{end}}' 2>/dev/null || true
else
    echo "❌ Docker network not found"
fi

echo -e "\n🛠️ Applying fixes..."

# 1. Fix DNS resolution issues
echo -e "\n1. Fixing DNS resolution..."
if [ -f /etc/docker/daemon.json ]; then
    if ! grep -q '"dns"' /etc/docker/daemon.json; then
        echo "Adding DNS servers to Docker daemon config..."
        # Backup existing config
        sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.bak
        # Add DNS config
        sudo jq '. + {"dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"]}' /etc/docker/daemon.json > /tmp/daemon.json
        sudo mv /tmp/daemon.json /etc/docker/daemon.json
        DOCKER_RESTART_NEEDED=true
    fi
else
    echo "Creating Docker daemon config with DNS..."
    echo '{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}' | sudo tee /etc/docker/daemon.json > /dev/null
    DOCKER_RESTART_NEEDED=true
fi

# 2. Fix container communication
echo -e "\n2. Checking container communication..."

# Recreate network if needed
if ! docker network ls | grep -q "robustty_robustty-network"; then
    echo "Creating Docker network..."
    docker network create --driver bridge \
        --opt com.docker.network.driver.mtu=1450 \
        --subnet=172.28.0.0/16 \
        robustty_robustty-network
fi

# 3. Restart containers in correct order
echo -e "\n3. Restarting containers..."

# Stop all containers
echo "Stopping containers..."
docker-compose stop

# Remove containers (but keep volumes)
echo "Removing containers..."
docker-compose rm -f

# Restart Docker daemon if needed
if [ "$DOCKER_RESTART_NEEDED" = "true" ]; then
    echo "Restarting Docker daemon..."
    sudo systemctl restart docker
    sleep 5
fi

# Start containers in correct order
echo "Starting containers in order..."
docker-compose up -d redis
sleep 5

docker-compose up -d youtube-music-headless
echo "Waiting for YouTube Music to initialize..."
sleep 10

docker-compose up -d robustty
sleep 5

echo -e "\n📋 Checking container logs..."

# Check YouTube Music logs
echo -e "\n--- YouTube Music Logs (last 20 lines) ---"
docker logs robustty-youtube-music --tail 20 2>&1 || echo "Could not fetch logs"

# Check bot logs for YouTube Music errors
echo -e "\n--- Bot Logs (YouTube Music related) ---"
docker logs robustty-bot --tail 50 2>&1 | grep -i "youtube.*music" || echo "No YouTube Music entries in bot logs"

echo -e "\n🧪 Running connectivity test..."

# Test from inside bot container
echo "Testing connection from bot container..."
docker exec robustty-bot python3 -c "
import socket
import sys

try:
    # Test DNS resolution
    ip = socket.gethostbyname('youtube-music-headless')
    print(f'✅ DNS Resolution: youtube-music-headless -> {ip}')
    
    # Test TCP connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((ip, 9863))
    sock.close()
    
    if result == 0:
        print('✅ TCP Connection: Port 9863 is open')
    else:
        print(f'❌ TCP Connection: Port 9863 connection failed (code: {result})')
        sys.exit(1)
        
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
" || echo "Connection test failed"

# Test HTTP endpoint
echo -e "\nTesting HTTP endpoint..."
docker exec robustty-bot curl -s -f -m 5 http://youtube-music-headless:9863/api/health | jq '.' || echo "❌ HTTP health check failed"

echo -e "\n📊 Final Status Check..."

# Final status
YT_MUSIC_STATUS=$(check_container "robustty-youtube-music")
YT_MUSIC_HEALTH=$(check_container_health "robustty-youtube-music")
BOT_STATUS=$(check_container "robustty-bot")

echo "YouTube Music: $YT_MUSIC_STATUS (Health: $YT_MUSIC_HEALTH)"
echo "Bot: $BOT_STATUS"

if [[ "$YT_MUSIC_HEALTH" == "healthy" ]] && [[ "$BOT_STATUS" == *"Up"* ]]; then
    echo -e "\n✅ YouTube Music connection should be working now!"
    echo "Run the test script to verify: python3 scripts/test-youtube-music-vps.py"
else
    echo -e "\n⚠️ Issues remain. Check the logs above for details."
    echo "You may need to:"
    echo "  1. Check firewall rules: sudo ufw status"
    echo "  2. Check Docker daemon: sudo systemctl status docker"
    echo "  3. Rebuild containers: docker-compose up -d --build"
    echo "  4. Check disk space: df -h"
fi

echo -e "\n🔍 Additional Diagnostics Commands:"
echo "  - Full test: docker exec robustty-bot python3 scripts/test-youtube-music-vps.py"
echo "  - Container IPs: docker network inspect robustty_robustty-network"
echo "  - Service logs: docker-compose logs -f youtube-music-headless"
echo "  - Bot logs: docker-compose logs -f robustty"