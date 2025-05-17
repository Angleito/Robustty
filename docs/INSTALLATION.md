# Installation Guide

This guide will help you install and set up Robustty on your server.

## Prerequisites

- Docker and Docker Compose installed
- A Discord Bot Token (get one from [Discord Developer Portal](https://discord.com/developers/applications))
- (Optional) YouTube API Key for YouTube search functionality
- A server or computer to host the bot

## Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/robustty.git
cd robustty
```

## Step 2: Initial Setup

Run the setup script:

```bash
./scripts/setup.sh
```

This will:
- Check Docker installation
- Create necessary directories
- Copy the environment template
- Build Docker images

## Step 3: Configure the Bot

Edit the `.env` file with your configurations:

```bash
nano .env
```

Required settings:
- `DISCORD_TOKEN`: Your Discord bot token
- `YOUTUBE_API_KEY`: YouTube Data API v3 key (optional but recommended)

## Step 4: Deploy

Run the deployment script:

```bash
./scripts/deploy.sh
```

This will start all services using Docker Compose.

## Step 5: Invite the Bot

1. Go to the Discord Developer Portal
2. Select your application
3. Go to the OAuth2 section
4. Select "bot" in scopes
5. Select necessary permissions:
   - Send Messages
   - Read Messages
   - Add Reactions
   - Embed Links
   - Connect
   - Speak
   - Use Voice Activity
6. Copy the generated URL and open it in your browser
7. Select a server and authorize the bot

## Troubleshooting

### Bot won't start
- Check logs: `docker-compose logs bot`
- Verify your Discord token is correct
- Ensure all required environment variables are set

### No audio playback
- Check FFmpeg installation in container
- Verify voice permissions
- Check stream service logs: `docker-compose logs stream-service`

### Search not working
- Verify API keys are correct
- Check platform-specific logs
- Ensure internet connectivity

## Next Steps

- Read the [Configuration Guide](CONFIGURATION.md) for advanced settings
- Learn about [Platform Integration](PLATFORMS.md)
- Check the [API Documentation](API.md)