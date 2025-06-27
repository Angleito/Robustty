#!/bin/bash
"""
Test the network diagnostic script within Docker environment where dependencies are available.
This demonstrates how the script would work on a VPS with proper dependencies installed.
"""

echo "Testing network diagnostic script in Docker environment..."
echo "This shows how it would work on a VPS with dependencies installed."
echo ""

# Check if we have docker-compose.yml
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml not found. Please run from project root."
    exit 1
fi

# Build container with diagnostic dependencies
echo "Building test container with network diagnostic dependencies..."
cat > Dockerfile.network-test << EOF
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    dnsutils \\
    netcat-traditional \\
    redis-tools \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install aiohttp dnspython redis

# Copy diagnostic script
WORKDIR /app
COPY scripts/network-diagnostic.py /app/
COPY scripts/install-network-diagnostic-deps.sh /app/

# Make scripts executable
RUN chmod +x /app/network-diagnostic.py /app/install-network-diagnostic-deps.sh

# Set environment variables for testing
ENV REDIS_URL=redis://host.docker.internal:6379

CMD ["python3", "network-diagnostic.py"]
EOF

# Build test image
echo "Building Docker image for network diagnostic test..."
docker build -f Dockerfile.network-test -t robustty-network-test .

# Run diagnostic in container
echo ""
echo "Running network diagnostic in Docker container..."
echo "================================================"
docker run --rm --network host robustty-network-test

# Clean up
echo ""
echo "Cleaning up test files..."
rm -f Dockerfile.network-test

echo ""
echo "✅ Docker network diagnostic test completed!"
echo ""
echo "💡 On your VPS, you can:"
echo "   1. Install dependencies: pip3 install aiohttp dnspython redis"
echo "   2. Run diagnostic: python3 scripts/network-diagnostic.py"
echo "   3. Or run in Docker: docker run --rm --network host robustty-network-test"