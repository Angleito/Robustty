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

# Make cookie extraction script executable
RUN chmod +x /app/scripts/extract-brave-cookies.py

# Create cron job for Brave cookie extraction (every 2 hours)
RUN echo "0 */2 * * * cd /app && /usr/local/bin/python scripts/extract-brave-cookies.py >> /var/log/cron.log 2>&1" > /etc/cron.d/brave-cookie-extraction && \
    echo "# Extract cookies immediately on startup" >> /etc/cron.d/brave-cookie-extraction && \
    echo "@reboot cd /app && /usr/local/bin/python scripts/extract-brave-cookies.py >> /var/log/cron.log 2>&1" >> /etc/cron.d/brave-cookie-extraction

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/brave-cookie-extraction

# Apply cron job
RUN crontab /etc/cron.d/brave-cookie-extraction

# Create startup script
RUN echo '#!/bin/bash\n\
echo "Starting Robustty Discord Bot with Brave cookie extraction..."\n\
# Create log file for cron\n\
touch /var/log/cron.log\n\
# Extract cookies immediately on startup\n\
echo "Running initial cookie extraction..."\n\
cd /app && /usr/local/bin/python scripts/extract-brave-cookies.py\n\
# Start cron daemon for scheduled extractions\n\
echo "Starting cron daemon for scheduled cookie extraction..."\n\
cron\n\
# Start the bot\n\
echo "Starting Discord bot..."\n\
/usr/local/bin/python -m src.main' > /app/start.sh && chmod +x /app/start.sh

# Expose no ports (Discord bot doesn't need external access)
# Use host network for OrbStack optimization

# Start both cron and the bot
CMD ["/app/start.sh"]