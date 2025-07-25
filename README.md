# Discord Music Bot with YouTube Integration

A robust Discord music bot featuring YouTube playback, voice commands, advanced search capabilities, and automatic fallback systems. Built with TypeScript and Docker for enterprise-grade reliability.

## Features

### 🎵 Music Playback
- YouTube music playback with search and playlist support
- Automatic fallback to browser-based playback when bot detection occurs
- Interactive search results with button selection interface
- Queue management with pagination and loop modes
- Real-time playback controls (play/pause/skip/stop/shuffle)

### 🎙️ Voice Commands (Optional Feature - Disabled by Default)
- **Opt-in feature**: Set `ENABLE_VOICE_COMMANDS=true` and provide `OPENAI_API_KEY` to enable
- **Two-stage processing**: Local wake word detection → Whisper API only when "Kanye" detected
- **Cost tracking**: Real-time monitoring of OpenAI API usage and costs
- **Intelligent filtering**: Multiple early-exit conditions to minimize processing
- **Wake word detection**: Lightweight local pattern matching for "Kanye"
- **Natural language parsing**: OpenAI Whisper API used only after wake word confirmation

### 🔍 Enhanced Search & Selection
- Multi-result search interface with thumbnail previews
- Interactive button selection for search results
- Session-based search with automatic cleanup
- Search result caching and optimization

### 🛠️ Advanced Error Handling & Recovery
- Comprehensive error classification and tracking
- Automatic retry mechanisms with exponential backoff
- Stream timeout protection and recovery
- Discord interaction error prevention
- Voice connection stability improvements

### 📊 Monitoring & Analytics
- Real-time metrics collection and reporting
- Performance monitoring dashboard
- Error tracking with detailed classification
- Admin notifications for critical issues
- Public stats command access

### 🔐 Security & Administration
- Enhanced admin command system with role-based access
- Optional admin configuration for flexible deployment
- Secure session management with Redis encryption
- Rate limiting and abuse prevention
- Comprehensive logging with adjustable levels

## Architecture

The bot is built with a modern microservices architecture using 4 main containers:

### Core Services

1. **Discord Bot Container** - Main application with multiple specialized services:
   - `MusicBot` - Core orchestration and command handling
   - `SearchResultHandler` - Interactive search session management
   - `VoiceCommandHandler` - Voice recognition and command processing
   - `AudioProcessingService` - Audio normalization and noise reduction
   - `SpeechRecognitionService` - OpenAI Whisper integration
   - `WakeWordDetectionService` - "Kanye" wake word detection
   - `VoiceListenerService` - Discord voice channel monitoring
   - `ErrorHandler` - Comprehensive error classification and recovery
   - `MonitoringService` - Real-time metrics and performance tracking

2. **Neko Browser** - Headless Firefox instances for YouTube fallback
   - Automated browser session management
   - Cookie persistence and authentication
   - Anti-bot detection mechanisms

3. **Redis** - High-performance data layer:
   - Queue persistence and state management
   - Search session caching
   - Voice session tracking
   - Metrics and analytics storage
   - Encrypted cookie storage

4. **Audio Router** - Audio processing pipeline:
   - PulseAudio capture from browser instances
   - FFmpeg conversion to Discord-compatible format
   - Real-time audio streaming optimization

### Key Design Patterns

- **Repository Pattern** - Clean data access abstraction
- **Strategy Pattern** - Pluggable playback methods (direct/neko)
- **Observer Pattern** - Event-driven voice command handling
- **Circuit Breaker** - Automatic fallback and recovery systems
- **Session Management** - Stateful voice and search interactions

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Discord Bot Token
- YouTube Data API v3 Key
- OpenAI API Key (optional, for voice commands)
- Railway account (for deployment)

### Environment Variables

Copy `.env.example` to `.env` and configure your values:

```bash
cp .env.example .env
```

**Required Configuration:**
```bash
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token
DISCORD_CLIENT_ID=your_discord_client_id

# YouTube API
YOUTUBE_API_KEY=your_youtube_api_key

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Neko Configuration
NEKO_INTERNAL_URL=http://localhost:8080
NEKO_PASSWORD=your_neko_password
```

**Optional Configuration:**
```bash
# Voice Commands (disabled by default)
ENABLE_VOICE_COMMANDS=false  # Set to true to enable voice commands
OPENAI_API_KEY=your_openai_api_key  # Required only if voice commands are enabled

# Admin Configuration (optional)
ADMIN_ROLE_ID=your_admin_role_id
ADMIN_NOTIFICATION_WEBHOOK=your_discord_webhook_url

# Environment Settings
NODE_ENV=production
LOG_LEVEL=info
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
- `/play <query>` - Search and play music with interactive selection
- `/skip` - Skip current song
- `/stop` - Stop playback and clear queue
- `/queue` - Show current queue with pagination
- `/nowplaying` - Show currently playing song with controls
- `/voice` - Enable voice commands in your current voice channel
- `/novoice` - Disable voice commands for the server
- `/stats` - View public playback statistics

**Voice Commands (say "Kanye" to activate):**
- **"Kanye play [song name]"** - Search and play music
- **"Kanye skip"** or **"Kanye next"** - Skip current song
- **"Kanye stop"** - Stop playback completely
- **"Kanye pause"** - Pause current song
- **"Kanye resume"** - Resume playback
- **"Kanye queue"** - Get queue information

**Admin Commands:**
- `/admin auth <instance>` - Authenticate a neko instance
- `/admin status` - Show neko instance health
- `/admin restart <instance>` - Restart a neko instance
- `/admin stats` - Show detailed playback statistics
- `/admin metrics` - Show system metrics and performance data
- `/admin errors` - Show error metrics and classifications
- `/admin voice` - Manage voice command settings

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

## Monitoring & Analytics

The bot includes enterprise-grade monitoring and analytics:

### Real-time Metrics
- Performance monitoring with detailed breakdowns
- Voice command usage analytics
- Search pattern analysis
- Error rate tracking and classification
- Memory and CPU usage monitoring

### Health Monitoring
- Container health checks for all services
- Redis connection monitoring
- Voice session state tracking
- Automatic failover and recovery systems

### Admin Features
- Comprehensive admin command suite
- Real-time notifications via Discord webhooks
- Detailed error logs with context
- Performance dashboard access
- Public statistics for transparency

## Security

- All cookies and sessions are encrypted
- Admin commands require proper permissions
- Rate limiting on all commands
- Secure Redis configuration
- Docker security best practices

## Recent Improvements & Bug Fixes

### Version 2.0 - Major Update
- **Enhanced Search System**: Interactive search results with button selection
- **Voice Commands**: Full voice control with wake word detection
- **Improved Error Handling**: Comprehensive error recovery and classification
- **Performance Optimizations**: Better memory usage and connection stability
- **Security Enhancements**: Role-based admin access and secure session management

### Critical Bug Fixes
- ✅ Fixed Discord audio player abort errors
- ✅ Fixed interaction "already replied" errors  
- ✅ Enhanced voice connection stability
- ✅ Stream timeout protection
- ✅ Automatic fallback systems
- ✅ Memory leak prevention
- ✅ Docker configuration improvements

## Troubleshooting

### Common Issues

**Bot not responding to commands:**
```bash
# Check bot permissions in Discord server
# Verify DISCORD_TOKEN and DISCORD_CLIENT_ID
# Check logs: docker logs -f robusttyv2-bot-1
```

**YouTube playback errors:**
```bash
# Verify YOUTUBE_API_KEY is valid
# Check if Neko fallback is working
# Monitor logs for rate limiting issues
```

**Voice commands not working:**
```bash
# First, ensure voice commands are enabled:
# - Set ENABLE_VOICE_COMMANDS=true in your .env file
# - Provide a valid OPENAI_API_KEY in your .env file
# - Restart the bot after configuration changes

# If enabled but still not working:
# - Check microphone permissions in Discord
# - Verify the wake word "Kanye" is being detected
# - Monitor voice processing logs
```

**Redis connection issues:**
```bash
# Verify Redis container is running
# Check REDIS_URL configuration
# Restart Redis container if needed: docker restart robusttyv2-redis-1
```

**Docker deployment issues:**
```bash
# Ensure all environment variables are set
# Check container logs: docker-compose logs
# Verify network connectivity between containers
# Try clean rebuild: docker-compose down && docker-compose up --build
```

### Performance Optimization

**Memory Usage:**
- Monitor container memory with `docker stats`
- Adjust `LOG_LEVEL` to reduce log verbosity
- Clean old sessions regularly (automatic)

**Network Performance:**
- Use Redis clustering for high-traffic deployments
- Configure Railway/cloud provider regions appropriately
- Monitor bandwidth usage for audio streaming

### Development

**Local Testing:**
```bash
# Run tests
cd bot && npm test

# Lint code
npm run lint

# Type checking
npm run typecheck

# Watch mode for development
npm run dev
```

**Docker Health Checks:**
```bash
# Check all services
docker-compose ps

# View logs
docker-compose logs -f bot
docker-compose logs -f neko
docker-compose logs -f redis

# Restart specific service
docker-compose restart bot
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the code standards
4. Test thoroughly with Docker
5. Run linting and type checks
6. Submit a pull request with detailed description

### Code Standards
- TypeScript with strict type checking
- ESLint configuration enforced
- Comprehensive error handling
- Unit tests for new features
- Docker-based testing required

## License

MIT License - see LICENSE file for details