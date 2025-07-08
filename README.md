# Robustty

A modular Discord music bot that searches and plays audio from multiple video platforms.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Discord.py](https://img.shields.io/badge/discord.py-2.3.2-blue.svg)

## Features

- 🎵 **Multi-platform search** - YouTube Music (headless), YouTube, PeerTube, Odysee, Rumble
- 🎧 **YouTube Music Integration** - Headless desktop app with API for premium features
- 🔍 **Smart search** - Automatic URL detection and cross-platform search
- 🍪 **Cookie management** - Automatic cookie extraction for authenticated access
- 🐳 **Docker deployment** - Easy deployment with Docker Compose
- 🔌 **Modular architecture** - Easily add new platforms
- 🚀 **High performance** - Caching and concurrent operations
- 🔒 **Privacy-focused** - Support for decentralized platforms

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- (Optional) YouTube API Key for enhanced search

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/robustty.git
cd robustty
```

2. Run setup:
```bash
./scripts/setup.sh
```

3. Configure your `.env` file:
```env
DISCORD_TOKEN=your_discord_bot_token_here
YOUTUBE_API_KEY=your_youtube_api_key_here
```

4. Deploy:
```bash
./scripts/deploy.sh
```

5. Invite the bot to your server using the OAuth2 URL generator in Discord Developer Portal.

## Commands

### Music Commands

- `!play <query/url>` - Play a song from any supported platform
- `!skip` - Skip the current song
- `!stop` - Stop playback and clear queue
- `!pause` - Pause the current song
- `!resume` - Resume playback
- `!queue` - Display the current queue
- `!volume <0-100>` - Set or show volume
- `!leave` - Leave the voice channel

### Info Commands

- `!help [command]` - Show help information
- `!ping` - Check bot latency
- `!uptime` - Show bot uptime
- `!about` - Information about the bot
- `!invite` - Get bot invite link

### Admin Commands

- `!reload [cog]` - Reload bot extensions
- `!shutdown` - Shut down the bot
- `!status` - Show bot status
- `!setprefix <prefix>` - Change command prefix

## Platform Support

Currently supported platforms:
- YouTube (with API)
- PeerTube (federated)
- Odysee (LBRY)
- Rumble

See [docs/PLATFORMS.md](docs/PLATFORMS.md) for adding new platforms.

## Configuration

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for detailed configuration options.

## Development

### Project Structure

```
robustty/
├── src/
│   ├── bot/         # Discord bot implementation
│   ├── platforms/   # Platform implementations
│   ├── services/    # Core services
│   └── models/      # Data models
├── docker/          # Docker configurations
├── config/          # Configuration files
├── tests/           # Test suites
└── docs/            # Documentation
```

### Adding a New Platform

1. Create a platform class in `src/platforms/`
2. Implement required methods from `VideoPlatform` base class
3. Register in the platform registry
4. Add configuration options

See [docs/PLATFORMS.md](docs/PLATFORMS.md) for detailed instructions.

### Running Tests

```bash
# Unit tests
pytest

# Integration tests (requires API keys)
pytest tests/integration

# All tests with coverage
pytest --cov=src --cov-report=html
```

See [docs/INTEGRATION_TESTING.md](docs/INTEGRATION_TESTING.md) for integration test details.

## Deployment

### Docker Deployment

```bash
docker-compose up -d
```

### VPS Deployment

For VPS deployments, use the provided diagnostic and fix tools:

```bash
# Diagnose network issues
python3 scripts/diagnose-vps-network.py

# Automatically fix common VPS networking problems
sudo ./scripts/fix-vps-network.sh
```

See [VPS_TROUBLESHOOTING.md](VPS_TROUBLESHOOTING.md) for detailed VPS deployment guidance.

### Manual Deployment

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the bot:
```bash
python -m src.main
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Troubleshooting

Common issues and solutions:

### Discord 530 Errors (WebSocket Authentication Failures)

If your bot is getting 530 errors even with a valid token:

**🚨 Emergency Response (2 minutes):**
```bash
# Stop all instances and run quick diagnosis
pkill -f python.*main.py && docker-compose down
python scripts/discord-530-master.py --quick
```

**🔍 Complete Investigation (10 minutes):**
```bash
# Systematic troubleshooting with automated fixes
python scripts/discord-530-master.py --all
```

**🌳 Interactive Troubleshooting:**
```bash
# Guided step-by-step diagnosis  
python scripts/discord-530-decision-tree.py --tree
```

**Common causes**: Session exhaustion (40%), multiple instances (25%), network issues (15%), verification required (10%). See [DISCORD_530_QUICK_START.md](DISCORD_530_QUICK_START.md) for detailed guidance.

### Bot won't connect
- Verify Discord token
- Check bot permissions
- Review logs: `docker-compose logs bot`

### No audio playback
- Ensure FFmpeg is installed
- Check voice permissions
- Check bot logs for stream extraction errors: `docker-compose logs robustty`

### Search not working
- Verify API keys
- Check platform status
- Review search service logs

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Discord.py community
- yt-dlp developers
- All platform API providers

## Support

- [GitHub Issues](https://github.com/yourusername/robustty/issues)
- [Discord Server](https://discord.gg/yoursupportserver)
- [Documentation](docs/)

---

Made with ❤️ by the Robustty team