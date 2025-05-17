FROM python:3.11-slim

# Install system dependencies for browser automation
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    xvfb \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python packages
RUN pip install --no-cache-dir \
    selenium \
    browser-cookie3 \
    requests \
    pyyaml

# Copy extraction script
COPY src/extractors/ ./extractors/

# Set up virtual display
ENV DISPLAY=:99

# Create cookie directory
RUN mkdir -p /app/cookies

# Run the cookie extraction service
CMD ["python", "-m", "extractors.cookie_extractor"]