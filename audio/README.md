# Audio Capture Service

This service captures audio from Neko browser instances using PulseAudio virtual sinks and streams it via FFmpeg for Discord voice channel playback.

## Architecture

1. **PulseAudio Virtual Sinks**: Creates virtual audio sinks for each Neko instance
2. **FFmpeg Streaming**: Captures audio from virtual sinks and encodes to Opus format
3. **HTTP API**: RESTful endpoints for managing audio capture and routing

## Features

- Multiple concurrent audio capture streams
- Real-time Opus encoding optimized for Discord
- Health monitoring with detailed service status
- Audio routing from Neko instances to virtual sinks
- Graceful shutdown with cleanup
- Docker containerization with proper PulseAudio configuration

## API Endpoints

### Health Check
```
GET /health
```
Returns detailed health status including PulseAudio state, available sinks, and active captures.

### Start Audio Capture
```
GET /capture/:instanceId
```
Starts capturing audio from the specified instance and streams it as Opus audio.

### Stop Audio Capture
```
DELETE /capture/:instanceId
```
Stops an active audio capture and returns statistics.

### List Active Streams
```
GET /streams
```
Returns information about all active audio capture streams.

### Route Audio
```
POST /route/:instanceId
Content-Type: application/json
{
  "sourceApp": "sink-input-id"
}
```
Routes audio from a specific application to the virtual sink for the instance.

## Environment Variables

- `PORT`: HTTP server port (default: 3000)
- `NODE_ENV`: Node environment (production/development)
- `LOG_LEVEL`: Logging level (info/debug/error)
- `MAX_NEKO_INSTANCES`: Maximum number of virtual sinks to create (default: 5)

## Docker Configuration

The service runs in a Docker container with:
- PulseAudio configured for container environment
- Virtual sinks for audio routing
- FFmpeg for audio encoding
- Health checks for monitoring

## Testing

Use the included `test-audio-capture.sh` script to verify functionality:

```bash
./test-audio-capture.sh
```

This will test health checks, stream listing, audio capture, and routing endpoints.