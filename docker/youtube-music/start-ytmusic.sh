#!/bin/bash

# Enable error handling
set -e

echo "Starting YouTube Music Headless Container..."

# Clean up any existing X lock files
rm -f /tmp/.X99-lock

# Start virtual display
echo "Starting Xvfb virtual display..."
Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for display to be ready
sleep 3

# Start PulseAudio for audio support
echo "Starting PulseAudio..."
pulseaudio --start --exit-idle-time=-1 || echo "PulseAudio start failed (running as root)"

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
    exit 0
}

# Set trap for cleanup
trap cleanup SIGTERM SIGINT

# Check if youtube-music binary exists
if ! which youtube-music > /dev/null 2>&1; then
    echo "ERROR: youtube-music binary not found!"
    echo "Checking possible locations..."
    ls -la /usr/bin/ | grep -i youtube || true
    ls -la /opt/ | grep -i youtube || true
    find / -name "youtube-music" -type f 2>/dev/null | head -10 || true
    
    # Try alternative locations
    if [ -f "/opt/YouTube Music/youtube-music" ]; then
        echo "Found at /opt/YouTube Music/youtube-music"
        YOUTUBE_MUSIC_BIN="/opt/YouTube Music/youtube-music"
    elif [ -f "/usr/share/youtube-music/youtube-music" ]; then
        echo "Found at /usr/share/youtube-music/youtube-music"
        YOUTUBE_MUSIC_BIN="/usr/share/youtube-music/youtube-music"
    else
        echo "FATAL: Cannot find youtube-music binary anywhere!"
        exit 1
    fi
else
    YOUTUBE_MUSIC_BIN="youtube-music"
fi

# Start YouTube Music with headless settings
echo "Starting YouTube Music from: $YOUTUBE_MUSIC_BIN"
"$YOUTUBE_MUSIC_BIN" \
    --no-sandbox \
    --disable-web-security \
    --disable-features=VizDisplayCompositor \
    --disable-gpu \
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