FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install required packages
RUN apt-get update && apt-get install -y \
  pulseaudio \
  pulseaudio-utils \
  ffmpeg \
  nodejs \
  npm \
  curl \
  dbus \
  alsa-utils \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./

# Install Node.js dependencies
RUN npm ci --only=production

# Copy application code
COPY index.js ./

# Copy start script separately to ensure it's properly copied
COPY start.sh ./

# Copy PulseAudio configuration
COPY pulse-default.pa /etc/pulse/default.pa
COPY daemon.conf /etc/pulse/daemon.conf

# Create pulse audio directories and configure
RUN mkdir -p /run/pulse /var/lib/pulse /home/audiouser/.config/pulse && \
    chmod +x /app/start.sh && \
    chmod 755 /app/start.sh

# Create non-root user with audio group
RUN useradd -m -u 1001 -G audio audiouser && \
    chown -R audiouser:audiouser /app /run/pulse /var/lib/pulse /home/audiouser/.config/pulse && \
    chmod 777 /run/pulse

# Configure PulseAudio for container environment
RUN echo "default-server = unix:/run/pulse/native" > /etc/pulse/client.conf && \
    echo "autospawn = no" >> /etc/pulse/client.conf && \
    echo "daemon-binary = /bin/true" >> /etc/pulse/client.conf && \
    echo "enable-shm = false" >> /etc/pulse/client.conf

# Switch to non-root user
USER audiouser

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

# Start services
CMD ["/app/start.sh"]