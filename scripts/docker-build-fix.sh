#!/bin/bash
set -e

echo "Fixing Docker build timeout issues..."

# Create a Dockerfile with step-by-step package installation
cat > docker/bot/Dockerfile.fixed << 'EOF'
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install build tools
RUN pip install --upgrade pip setuptools wheel

# Install core dependencies first
RUN pip install --no-cache-dir \
    "discord.py==2.3.2" \
    "PyNaCl==1.5.0" \
    "aiohttp==3.9.5" \
    "python-dotenv==1.0.0" \
    "PyYAML==6.0.1" \
    "redis==5.0.1" \
    "psutil>=5.8.0"

# Install media and web scraping tools
RUN pip install --no-cache-dir \
    "beautifulsoup4==4.12.2" \
    "yt-dlp==2023.10.13" \
    "ffmpeg-python==0.2.0" \
    "lxml==4.9.3"

# Install Google API clients
RUN pip install --no-cache-dir \
    "google-api-python-client==2.100.0" \
    "google-auth==2.23.0" \
    "google-auth-oauthlib==1.1.0" \
    "google-auth-httplib2==0.1.0"

# Install remaining utilities
RUN pip install --no-cache-dir \
    "aiofiles==23.2.1" \
    "colorlog==6.7.0" \
    "typing-extensions==4.9.0" \
    "flask==3.0.0" \
    "gunicorn==21.2.0"

# Install performance improvements
RUN pip install --no-cache-dir \
    "aiodns==3.1.1" \
    "charset-normalizer==3.4.2" \
    "brotli==1.1.0"

# Install heavy packages separately with retries
RUN pip install --no-cache-dir --timeout=600 "selenium==4.15.2" || \
    echo "Warning: selenium installation failed"
RUN pip install --no-cache-dir --timeout=600 "browser-cookie3==0.19.1" || \
    echo "Warning: browser-cookie3 installation failed"

# Development tools (optional)
RUN pip install --no-cache-dir \
    "black==23.11.0" \
    "flake8==6.1.0" \
    "isort==5.12.0" \
    "mypy==1.7.0" || echo "Warning: Some dev tools failed to install"

# Testing tools (optional)
RUN pip install --no-cache-dir \
    "pytest==7.4.3" \
    "pytest-asyncio==0.21.1" \
    "pytest-cov==4.1.0" \
    "pytest-mock==3.12.0" || echo "Warning: Some test tools failed to install"

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create necessary directories
RUN mkdir -p logs data cookies

# Set Python path
ENV PYTHONPATH=/app/src

# Run the bot
CMD ["python", "-m", "src.main"]
EOF

echo "Building with fixed Dockerfile..."
docker build -f docker/bot/Dockerfile.fixed -t robustty-bot .

echo "Build complete! To use this image, update docker-compose.yml to use robustty-bot:latest"
echo "Or run directly: docker run --env-file .env robustty-bot"