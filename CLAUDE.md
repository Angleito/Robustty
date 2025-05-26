# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Robustty is a modular Discord music bot for searching and playing audio from multiple video platforms (YouTube, Rumble, Odysee, PeerTube). Uses microservices architecture with Docker and Redis caching.

## Key Commands

### Development
```bash
# Run bot locally
python -m src.main

# Run tests
pytest                                    # All tests
pytest tests/integration -v              # Integration tests only  
pytest tests/test_platforms/ -k rumble   # Specific platform tests
./scripts/run-integration-tests.sh       # Full integration test suite

# Type checking
mypy src/                                 # Full type check
mypy src/platforms/                       # Platform-specific

# Code quality
black src/                                # Format code
flake8 src/                              # Lint code
isort src/                               # Sort imports
```

### Docker (OrbStack Optimized)
```bash
# Setup environment first
cp .env.example .env
# Edit .env with your credentials

# Start services (optimized for OrbStack with host networking)
docker-compose up -d                      # Start bot + Redis
docker-compose logs -f robustty           # View bot logs  
docker-compose logs -f                    # View all logs
docker-compose down && docker-compose up -d --build  # Rebuild and restart

# Cookie extraction logs
docker-compose exec robustty tail -f /var/log/cron.log

# Redis operations (using host network)
redis-cli FLUSHALL                        # Clear cache (direct host access)
docker-compose exec redis redis-cli info # Redis info via container
```

## Architecture

### Platform System (`src/platforms/`)
- **Base Class**: `VideoPlatform` defines required methods (`search_videos`, `get_stream_url`, `extract_video_id`)
- **Registry**: `PlatformRegistry` manages dynamic platform loading
- **Current Platforms**: YouTube (API), Rumble (Apify), Odysee, PeerTube
- **Platform Registration**: Each platform auto-registers via `setup_hook` in bot initialization

### Cookie Management (`src/extractors/`, `src/services/`)
- **Brave Browser Focus**: Optimized for Brave browser cookie extraction from host system
- **Scheduled Extraction**: Cron job extracts cookies every 2 hours automatically
- **Host Mount**: Direct access to `~/Library/Application Support/BraveSoftware/Brave-Browser`
- **Platform-Specific**: Saves cookies per platform (YouTube, Rumble, Odysee, PeerTube) in yt-dlp format
- **Docker Integration**: Built-in cookie extraction using `scripts/extract-brave-cookies.py`

### Service Layer (`src/services/`)
- **Searcher**: Multi-platform search aggregation with fallback handling
- **Audio Player**: Queue management with Redis persistence
- **Cache Manager**: Redis-backed caching for search results and metadata
- **Metrics**: Prometheus metrics collection for monitoring

## Adding New Platform

1. **Create Platform Class**:
```python
# src/platforms/newplatform.py
from .base import VideoPlatform

class NewPlatform(VideoPlatform):
    async def search_videos(self, query: str, max_results: int = 10):
        # Implementation here
        
    async def get_stream_url(self, video_id: str):
        # Implementation here
        
    def extract_video_id(self, url: str):
        # Implementation here
        
    def is_platform_url(self, url: str):
        # Implementation here
```

2. **Register Platform** in `src/bot/bot.py` `setup_hook`:
```python
from ..platforms.newplatform import NewPlatform
self.platform_registry.register_platform('newplatform', NewPlatform)
```

3. **Add Configuration** to `config/config.yaml`:
```yaml
platforms:
  newplatform:
    enabled: true
    # platform-specific config
```

## Testing Strategy

- **Unit Tests**: `pytest tests/test_platforms/test_newplatform.py` 
- **Integration Tests**: `pytest tests/integration/` (requires external APIs)
- **Platform-specific**: Use `pytest -k platform_name` to test specific platforms
- **Markers**: `@pytest.mark.integration` for external API tests, `@pytest.mark.unit` for isolated tests

## Environment Setup

### Required Environment Variables
```bash
# Discord
DISCORD_TOKEN=your_discord_bot_token

# Platform APIs  
YOUTUBE_API_KEY=your_youtube_api_key
APIFY_API_KEY=your_apify_key_for_rumble

# Configuration
LOG_LEVEL=INFO
MAX_QUEUE_SIZE=100
REDIS_URL=redis://localhost:6379
```

### Local Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your credentials

# Run locally (requires Redis running)
redis-server &                            # Start Redis in background
python -m src.main                        # Start bot

# Or use Docker (recommended)
docker-compose up -d
```

## Recent Fixes (2025-01-25)

### YouTube Streaming & Cookie Integration
- **Standardized Cookie Paths**: All components now use `/app/cookies/` as primary path with fallbacks to `data/cookies/` and `./cookies/`
- **Enhanced Cookie Conversion**: Improved JSON to Netscape format conversion with better error handling and validation
- **Better Stream URL Extraction**: Fixed yt-dlp configuration conflicts and added proper format selection for audio streams
- **Async URL Validation**: Added async validation for stream URLs using aiohttp with fallback to sync validation
- **Error Handling**: Enhanced error handling throughout the YouTube platform implementation
- **Multiple Cookie Path Support**: Cookie managers now automatically detect and use the best available cookie directory

### Testing
```bash
# Test YouTube streaming fixes
python test_youtube_streaming_fix.py

# Test cookie extraction
python scripts/extract-brave-cookies.py
```

## Debugging

### Platform Issues
- **Platform Not Loading**: Check registration in `src/bot/bot.py` and config in `config/config.yaml`
- **API Failures**: Verify API keys in environment variables
- **Cookie Issues**: Run `python scripts/extract-brave-cookies.py` manually or check cron logs

### Audio Issues
- **No Audio**: Verify FFmpeg installed and voice channel permissions
- **Stream Failures**: Test stream URLs directly with `yt-dlp`

### Cookie Extraction Issues
- **No Cookies Found**: Ensure Brave browser data is mounted correctly at `/host-brave`
- **Permission Errors**: Check that Docker has access to `~/Library/Application Support/BraveSoftware/Brave-Browser`
- **Cron Not Running**: Check cron logs with `docker-compose exec robustty tail -f /var/log/cron.log`
- **Cookie Path Issues**: Check that `/app/cookies/` directory exists and is writable
- **Cookie Conversion Failures**: Run test script to verify JSON to Netscape conversion works

### Log Analysis
- Bot logs: `docker-compose logs -f robustty`
- Cookie extraction: `docker-compose exec robustty tail -f /var/log/cron.log`
- Redis: `docker-compose logs -f redis`

## Configuration Files

- **`config/config.yaml`**: Platform settings, feature toggles
- **`config/logging.yaml`**: Logging configuration
- **`mypy.ini`**: Type checking configuration with platform-specific settings
- **`pytest.ini`**: Test configuration with markers for integration/unit tests