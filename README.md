# Discord Music Bot with YouTube Integration

A robust Discord music bot that uses YouTube as its primary source with automatic fallback to virtual browser instances when bot detection occurs.

## Features

- 🎵 YouTube music playback with search and playlist support
- 🔄 Automatic fallback to browser-based playback when detected as bot
- 🎮 Interactive button controls for music playback
- 📊 Queue management with pagination
- 🔐 Admin commands for maintenance and monitoring
- 📈 Real-time metrics and error tracking
- 🐳 Docker-based deployment for easy scaling
- 🚀 Railway-ready configuration

## Architecture

The bot consists of 4 main containers:

1. **Discord Bot** - Main bot logic, command handling, YouTube API integration
2. **Neko Browser** - Virtual browser instances for fallback playback
3. **Audio Router** - Captures audio from browsers and streams to Discord
4. **Redis** - Session persistence and queue management

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Discord Bot Token
- YouTube Data API v3 Key
- Railway account (for deployment)

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### Local Development

```bash
# Install dependencies
cd bot && npm install
cd ../audio && npm install

# Run with Docker Compose
docker-compose up --build
```

### Commands

**Music Commands:**
- `/play <query>` - Play a song or add to queue
- `/skip` - Skip current song
- `/stop` - Stop playback and clear queue
- `/queue` - Show current queue
- `/nowplaying` - Show currently playing song

**Admin Commands:**
- `/admin auth <instance>` - Authenticate a neko instance
- `/admin status` - Show neko instance health
- `/admin restart <instance>` - Restart a neko instance
- `/admin stats` - Show playback statistics
- `/admin metrics` - Show system metrics
- `/admin errors` - Show error metrics

## Deployment on Railway

1. Fork this repository
2. Connect your GitHub account to Railway
3. Create a new project from your forked repository
4. Add the required environment variables
5. Deploy!

Railway will automatically detect the `docker-compose.yml` and deploy all services.

## How It Works

1. **Primary Playback**: The bot first attempts to stream audio directly using ytdl-core or play-dl
2. **Bot Detection**: If YouTube detects bot activity, the system automatically falls back to neko
3. **Browser Playback**: Neko instances run real Firefox browsers that play YouTube videos
4. **Audio Capture**: PulseAudio captures browser audio and FFmpeg converts it to Discord-compatible format
5. **Session Management**: Browser cookies are encrypted and stored in Redis for persistence

## Monitoring

The bot includes comprehensive monitoring:

- Health check endpoints for each service
- Real-time metrics collection
- Error tracking and classification
- Admin notifications for critical issues
- Performance metrics dashboard

## Security

- All cookies and sessions are encrypted
- Admin commands require proper permissions
- Rate limiting on all commands
- Secure Redis configuration
- Docker security best practices

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with Docker
5. Submit a pull request

## License

MIT License - see LICENSE file for details