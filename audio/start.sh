#!/bin/bash

# Clean up any existing PulseAudio files
rm -rf /run/pulse/* /var/lib/pulse/* ~/.config/pulse/cookie

# Ensure PulseAudio socket directory exists with correct permissions
mkdir -p /run/pulse
chmod 755 /run/pulse

# Set the PulseAudio server address
export PULSE_SERVER=unix:/run/pulse/native

# Start PulseAudio in system mode for container
echo "Starting PulseAudio..."
pulseaudio --daemonize=no \
    --log-target=stderr \
    --log-level=info \
    --exit-idle-time=-1 \
    --disable-shm=true \
    --use-pid-file=no \
    --system=false &

PULSE_PID=$!

# Wait for PulseAudio to be ready
echo "Waiting for PulseAudio to initialize..."
sleep 3  # Give PulseAudio time to start and create the socket

for i in {1..10}; do
    if [ -S "/run/pulse/native" ] && pactl info >/dev/null 2>&1; then
        echo "PulseAudio is ready"
        break
    fi
    echo "Waiting for PulseAudio... ($i/10)"
    sleep 1
done

# Verify PulseAudio is running
if ! pactl info >/dev/null 2>&1; then
    echo "ERROR: PulseAudio failed to start properly"
    # Show debug information
    echo "Checking for PulseAudio process:"
    ps aux | grep pulse
    echo "Checking for socket:"
    ls -la /run/pulse/
    echo "Checking PulseAudio logs from stderr above"
    exit 1
fi

# Show PulseAudio info
echo "PulseAudio info:"
pactl info

# Function to handle shutdown
cleanup() {
    echo "Shutting down..."
    if [ -n "$NODE_PID" ]; then
        kill $NODE_PID 2>/dev/null
    fi
    if [ -n "$PULSE_PID" ]; then
        kill $PULSE_PID 2>/dev/null
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Start the Node.js application
echo "Starting audio capture service..."
node index.js &
NODE_PID=$!

# Wait for either process to exit
wait -n $PULSE_PID $NODE_PID

# If we get here, something died
echo "Process exited unexpectedly"
cleanup