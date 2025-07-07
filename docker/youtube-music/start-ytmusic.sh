#!/bin/bash

# Enable error handling
set -e

echo "Starting YouTube Music Headless Container..."

# Start virtual display
echo "Starting Xvfb virtual display..."
Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for display to be ready
sleep 3

# Start PulseAudio for audio support
echo "Starting PulseAudio..."
pulseaudio --start --exit-idle-time=-1 &
PULSE_PID=$!

# Wait for audio to be ready
sleep 2

# Import cookies if available
echo "Checking for cookie files..."
if [ -f /app/cookies/youtube_music_cookies.json ]; then
    echo "Importing YouTube Music cookies from extracted cookies..."
    cp /app/cookies/youtube_music_cookies.json /root/.config/YouTube\ Music/cookies.json
elif [ -f /app/cookies/youtube-music.json ]; then
    echo "Importing YouTube Music cookies from legacy path..."
    cp /app/cookies/youtube-music.json /root/.config/YouTube\ Music/cookies.json
elif [ -f /app/cookies/youtube_music_auth.json ]; then
    echo "Importing YouTube Music auth cookies..."
    cp /app/cookies/youtube_music_auth.json /root/.config/YouTube\ Music/cookies.json
elif [ -f /app/cookies/youtube_cookies.json ]; then
    echo "Using YouTube cookies for YouTube Music (fallback)..."
    cp /app/cookies/youtube_cookies.json /root/.config/YouTube\ Music/cookies.json
else
    echo "No cookie files found, YouTube Music will run without authentication"
fi

# Create config directory if it doesn't exist
mkdir -p /root/.config/YouTube\ Music

# Create basic config to enable API server
cat > /root/.config/YouTube\ Music/config.json << EOF
{
  "plugins": {
    "api-server": {
      "enabled": true,
      "port": 9863,
      "host": "0.0.0.0"
    },
    "adblocker": {
      "enabled": true
    },
    "shortcuts": {
      "enabled": false
    }
  },
  "options": {
    "autoUpdater": false,
    "hideMenu": true,
    "startMinimized": true,
    "disableHardwareAcceleration": true
  }
}
EOF

echo "Configuration created. Starting YouTube Music..."

# Function to cleanup on exit
cleanup() {
    echo "Shutting down services..."
    kill $XVFB_PID 2>/dev/null || true
    kill $PULSE_PID 2>/dev/null || true
    exit 0
}

# Set trap for cleanup
trap cleanup SIGTERM SIGINT

# Start YouTube Music with headless settings
youtube-music \
    --no-sandbox \
    --disable-web-security \
    --disable-features=VizDisplayCompositor \
    --disable-gpu \
    --headless=new \
    --disable-dev-shm-usage \
    --remote-debugging-port=9222 \
    --enable-automation \
    --disable-background-timer-throttling \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --disable-ipc-flooding-protection \
    &

YTMUSIC_PID=$!

# Wait for YouTube Music to start
echo "Waiting for YouTube Music to start..."
sleep 10

# Check if API server is responding
for i in {1..30}; do
    if curl -s http://localhost:9863/api/health >/dev/null 2>&1; then
        echo "YouTube Music API server is ready!"
        break
    fi
    echo "Waiting for API server... ($i/30)"
    sleep 2
done

# Keep the container running
echo "YouTube Music Headless is running. API available at port 9863"
wait $YTMUSIC_PID