FROM node:18-bullseye

# Install system dependencies for headless operation
RUN apt-get update && apt-get install -y \
    xvfb \
    pulseaudio \
    libgtk-3-0 \
    libgbm-dev \
    libasound2-dev \
    libxss1 \
    libgconf-2-4 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libxrandr2 \
    libasound2 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libgtk-3-0 \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Download and install YouTube Music Desktop App
RUN wget https://github.com/th-ch/youtube-music/releases/latest/download/youtube-music_3.6.0_amd64.deb -O youtube-music.deb \
    && dpkg -i youtube-music.deb || apt-get install -f -y \
    && rm youtube-music.deb

# Create necessary directories
RUN mkdir -p /app/cookies \
    && mkdir -p /root/.config/YouTube\ Music \
    && mkdir -p /tmp/.X11-unix \
    && chmod 1777 /tmp/.X11-unix

# Set environment variables
ENV DISPLAY=:99
ENV PULSE_SERVER=unix:/tmp/pulse-socket
ENV NODE_ENV=production

# Copy startup script
COPY start-ytmusic.sh /start-ytmusic.sh
RUN chmod +x /start-ytmusic.sh

# Expose API server port
EXPOSE 9863

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9863/api/health || exit 1

# Start the application
CMD ["/start-ytmusic.sh"]