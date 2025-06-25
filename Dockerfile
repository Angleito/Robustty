# OrbStack-optimized Dockerfile for Robustty Discord Bot
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    gcc \
    g++ \
    build-essential \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p logs data cookies

# Set Python path
ENV PYTHONPATH=/app

# Make cookie extraction script executable (optional for VPS without Brave)
RUN chmod +x /app/scripts/extract-brave-cookies.py

# Create VPS-compatible startup script with optional cookie extraction
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Starting Robustty Discord Bot..."\n\
\n\
# Check if running in environment with Brave browser support\n\
if [ -d "/host-brave" ] || [ -d "$HOME/Library/Application Support/BraveSoftware/Brave-Browser" ]; then\n\
    echo "Brave browser detected - enabling cookie extraction"\n\
    \n\
    # Create log file for cron\n\
    touch /var/log/cron.log\n\
    \n\
    # Setup cron job for cookie extraction (every 2 hours)\n\
    echo "0 */2 * * * cd /app && /usr/local/bin/python scripts/extract-brave-cookies.py >> /var/log/cron.log 2>&1" > /etc/cron.d/brave-cookie-extraction\n\
    echo "@reboot cd /app && /usr/local/bin/python scripts/extract-brave-cookies.py >> /var/log/cron.log 2>&1" >> /etc/cron.d/brave-cookie-extraction\n\
    chmod 0644 /etc/cron.d/brave-cookie-extraction\n\
    crontab /etc/cron.d/brave-cookie-extraction\n\
    \n\
    # Extract cookies immediately on startup\n\
    echo "Running initial cookie extraction..."\n\
    cd /app && /usr/local/bin/python scripts/extract-brave-cookies.py || echo "Cookie extraction failed, continuing without cookies"\n\
    \n\
    # Start cron daemon for scheduled extractions\n\
    echo "Starting cron daemon for scheduled cookie extraction..."\n\
    cron\n\
else\n\
    echo "No Brave browser detected - running in VPS mode without cookie extraction"\n\
    echo "Bot will use API keys and public access for video platforms"\n\
fi\n\
\n\
# Start the bot\n\
echo "Starting Discord bot..."\n\
exec /usr/local/bin/python -m src.main' > /app/start.sh && chmod +x /app/start.sh

# Port configuration is handled by docker-compose.yml
# Local dev: host networking for OrbStack optimization
# VPS: bridge networking with exposed ports

# Start both cron and the bot
CMD ["/app/start.sh"]