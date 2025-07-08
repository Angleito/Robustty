# VPS-compatible Dockerfile for Robustty Discord Bot
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    gcc \
    g++ \
    build-essential \
    cron \
    sudo \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security and VPS compatibility
RUN groupadd -g 1000 robustty && \
    useradd -u 1000 -g 1000 -s /bin/bash -m robustty && \
    echo 'robustty ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Create app directory and set ownership
WORKDIR /app
RUN chown -R robustty:robustty /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Create necessary directories with proper ownership
RUN mkdir -p logs data cookies && \
    chown -R robustty:robustty /app logs data cookies

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
if [ -d "/host-brave" ] && [ "$(ls -A /host-brave 2>/dev/null)" ]; then\n\
    echo "Brave browser detected - enabling cookie extraction"\n\
    \n\
    # Create log file for cron (as root first, then fix permissions)\n\
    sudo touch /var/log/cron.log\n\
    sudo chmod 666 /var/log/cron.log\n\
    \n\
    # Setup cron job for cookie extraction (every 2 hours)\n\
    echo "0 */2 * * * cd /app && /usr/local/bin/python scripts/extract-brave-cookies.py >> /app/logs/cookie-extraction.log 2>&1" > /tmp/cookie-cron\n\
    echo "@reboot cd /app && /usr/local/bin/python scripts/extract-brave-cookies.py >> /app/logs/cookie-extraction.log 2>&1" >> /tmp/cookie-cron\n\
    sudo cp /tmp/cookie-cron /etc/cron.d/brave-cookie-extraction\n\
    sudo chmod 0644 /etc/cron.d/brave-cookie-extraction\n\
    sudo crontab /etc/cron.d/brave-cookie-extraction\n\
    \n\
    # Extract cookies immediately on startup\n\
    echo "Running initial cookie extraction..."\n\
    cd /app && /usr/local/bin/python scripts/extract-brave-cookies.py 2>&1 | tee /app/logs/cookie-extraction.log || echo "Cookie extraction failed, continuing without cookies"\n\
    \n\
    # Start cron daemon for scheduled extractions\n\
    echo "Starting cron daemon for scheduled cookie extraction..."\n\
    sudo cron\n\
else\n\
    echo "No Brave browser detected or empty - running in VPS mode without cookie extraction"\n\
    echo "Bot will use API keys and public access for video platforms"\n\
fi\n\
\n\
# Fix cookie directory permissions for VPS compatibility\n\
echo "Fixing cookie directory permissions..."\n\
sudo chown -R robustty:robustty /app/cookies /app/data /app/logs || true\n\
sudo chmod 755 /app/cookies /app/data /app/logs || true\n\
\n\
# Convert any Netscape format cookies to JSON format\n\
echo "Converting Netscape cookies to JSON format..."\n\
cd /app && /usr/local/bin/python scripts/convert-cookies-to-json.py 2>&1 | tee -a /app/logs/cookie-conversion.log || echo "Cookie conversion failed or no cookies to convert"\n\
\n\
# Start the bot\n\
echo "Starting Discord bot..."\n\
exec /usr/local/bin/python -m src.main' > /app/start.sh && chmod +x /app/start.sh

# Create log directory with proper permissions  
RUN mkdir -p /app/logs && chown -R robustty:robustty /app/logs

# Switch to non-root user for security
USER robustty

# Port configuration is handled by docker-compose.yml
# Local dev: host networking for OrbStack optimization
# VPS: bridge networking with exposed ports

# Start both cron and the bot
CMD ["/app/start.sh"]