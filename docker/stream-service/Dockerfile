FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python packages
RUN pip install --no-cache-dir \
    flask \
    yt-dlp \
    redis \
    gunicorn

# Copy stream service and extractors
COPY src/services/stream_service.py ./
COPY src/extractors ./extractors

# Create cache directory
RUN mkdir -p /app/cache /app/cookies

# Set up Flask
ENV FLASK_APP=stream_service.py

# Run the stream service
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "4", "stream_service:app"]