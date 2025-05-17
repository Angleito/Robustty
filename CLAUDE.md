# CLAUDE.md - Robustty Project Context

## Project Overview

Robustty is a modular Discord music bot designed to search and play audio from multiple video platforms. It uses a microservices architecture with Docker for easy deployment and extensibility.

## Architecture

### Core Components

1. **Discord Bot** (`src/bot/`)
   - Main bot class handling Discord interactions
   - Cogs for modular command organization
   - Utility functions for embeds and permission checks

2. **Platform System** (`src/platforms/`)
   - Abstract base class for video platforms
   - Platform registry for dynamic loading
   - Individual platform implementations

3. **Services** (`src/services/`)
   - Multi-platform searcher
   - Audio player with queue management
   - Cookie manager for authentication
   - Queue persistence

4. **Docker Services**
   - Main bot container
   - Cookie extraction service
   - Stream extraction service
   - Redis for caching

## Key Design Decisions

### Modular Platform Architecture
- Each platform inherits from `VideoPlatform` base class
- Platforms are dynamically registered and loaded
- Easy to add new platforms without modifying core code

### Service Separation
- Cookie extraction runs as separate service for security
- Stream extraction isolated to handle platform-specific quirks
- Redis used for cross-service caching

### Error Handling
- Graceful degradation when platforms fail
- Comprehensive logging throughout
- User-friendly error messages

## Development Guidelines

### Adding New Features

1. **New Platform**
   - Create class in `src/platforms/`
   - Implement all abstract methods
   - Register in bot's `setup_hook`
   - Add configuration options

2. **New Command**
   - Add to appropriate cog in `src/bot/cogs/`
   - Use utility functions for consistent embeds
   - Implement proper permission checks

3. **New Service**
   - Create in `src/services/`
   - Consider Docker service if needed
   - Update bot initialization

### Code Standards

- Use type hints throughout
- Async/await for all I/O operations
- Comprehensive error handling
- Logging for debugging
- Docstrings for public methods

### Testing

- Unit tests for all platforms
- Integration tests for services
- Mock Discord interactions
- Test error conditions

## Common Tasks

### Running Locally

```bash
# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Install dependencies
pip install -r requirements.txt

# Run bot
python -m src.main
```

### Docker Development

```bash
# Build images
docker-compose build

# Run services
docker-compose up -d

# View logs
docker-compose logs -f bot

# Rebuild specific service
docker-compose build bot
docker-compose up -d bot
```

### Adding Platform

1. Create platform file:
```python
# src/platforms/newplatform.py
from .base import VideoPlatform

class NewPlatform(VideoPlatform):
    # Implement required methods
```

2. Register in bot:
```python
# src/bot/bot.py
from ..platforms.newplatform import NewPlatform
self.platform_registry.register_platform('newplatform', NewPlatform)
```

3. Add config:
```yaml
# config/config.yaml
platforms:
  newplatform:
    enabled: true
```

## Debugging

### Common Issues

1. **Import Errors**
   - Check PYTHONPATH includes src/
   - Verify __init__.py files exist

2. **Platform Not Loading**
   - Check platform is registered
   - Verify config enabled
   - Review logs for errors

3. **No Audio**
   - Verify FFmpeg installed
   - Check voice permissions
   - Test stream URL directly

### Log Locations

- Bot logs: `logs/robustty.log`
- Error logs: `logs/errors.log`
- Docker logs: `docker-compose logs <service>`

## Project Structure

```
robustty/
├── src/
│   ├── bot/           # Discord bot core
│   ├── platforms/     # Platform implementations  
│   ├── services/      # Business logic
│   └── models/        # Data structures
├── docker/            # Dockerfiles
├── config/            # Configuration files
├── tests/             # Test suites
├── scripts/           # Deployment scripts
└── docs/              # Documentation
```

## Environment Variables

Critical variables:
- `DISCORD_TOKEN`: Bot authentication
- `YOUTUBE_API_KEY`: YouTube search
- `LOG_LEVEL`: Debugging verbosity
- `MAX_QUEUE_SIZE`: Performance tuning

## Performance Considerations

- Use caching for repeated searches
- Implement rate limiting per platform
- Batch operations where possible
- Monitor memory usage with large queues

## Security Notes

- Never commit .env file
- Rotate tokens regularly
- Use environment variables for secrets
- Validate user input
- Sanitize error messages

## Future Enhancements

- Playlist support
- Web dashboard
- User preferences
- Advanced queue management
- Spotify integration
- Webhook notifications

## Testing Checklist

Before commits:
- [ ] Run pytest
- [ ] Test new platforms manually
- [ ] Verify Docker builds
- [ ] Check for lint errors
- [ ] Update documentation

## Useful Commands

```bash
# Run tests
pytest

# Format code
black src/

# Check types
mypy src/

# Lint code
flake8 src/

# Build specific service
docker-compose build stream-service

# Enter container shell
docker-compose exec bot bash

# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL
```

## Contact

For questions or issues:
- Create GitHub issue
- Check existing documentation
- Review test cases for examples