#!/bin/bash
set -e

echo "Building Robustty without browser automation packages..."

# Use the requirements without browser packages
docker build -f - -t robustty-bot . << 'EOF'
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

# Copy requirements without browser automation
COPY requirements-no-browser.txt requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

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

echo "Build complete! Run with: docker run --env-file .env robustty-bot"