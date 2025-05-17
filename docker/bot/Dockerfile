FROM python:3.11-slim

# Install system dependencies including build tools
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Upgrade pip and set timeout
RUN pip install --upgrade pip setuptools wheel

# Copy requirements first for better caching
COPY requirements.txt .

# Install requirements with increased timeout and retries
RUN pip install --no-cache-dir --timeout=300 --retries=5 -r requirements.txt || \
    (echo "First attempt failed, retrying with increased timeout..." && \
     pip install --no-cache-dir --timeout=600 --retries=10 -r requirements.txt)

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create necessary directories
RUN mkdir -p logs data cookies

# Set Python path
ENV PYTHONPATH=/app/src

# Run the bot
CMD ["python", "-m", "src.main"]