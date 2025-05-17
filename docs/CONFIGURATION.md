# Configuration Guide

This guide explains all configuration options for Robustty.

## Environment Variables (.env)

### Discord Configuration

```env
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_PREFIX=!
```

- `DISCORD_TOKEN`: Your bot's authentication token
- `DISCORD_PREFIX`: Default command prefix (can be changed per-server)

### Platform Configuration

#### YouTube
```env
YOUTUBE_API_KEY=your_youtube_api_key_here
```

- `YOUTUBE_API_KEY`: YouTube Data API v3 key for search functionality

#### PeerTube
```env
PEERTUBE_INSTANCES=https://framatube.org,https://video.ploud.fr
```

- `PEERTUBE_INSTANCES`: Comma-separated list of PeerTube instances to search

#### Odysee
```env
ODYSEE_ENABLED=true
```

- `ODYSEE_ENABLED`: Enable/disable Odysee platform

#### Rumble
```env
RUMBLE_ENABLED=true
```

- `RUMBLE_ENABLED`: Enable/disable Rumble platform

### Cookie Extraction

```env
COOKIE_REFRESH_INTERVAL=3600
BROWSER_PROFILE_PATH=/home/user/.config/google-chrome
```

- `COOKIE_REFRESH_INTERVAL`: How often to refresh cookies (seconds)
- `BROWSER_PROFILE_PATH`: Path to browser profile for cookie extraction

### Logging

```env
LOG_LEVEL=INFO
LOG_FILE_SIZE=10485760
LOG_BACKUP_COUNT=5
```

- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `LOG_FILE_SIZE`: Maximum log file size in bytes
- `LOG_BACKUP_COUNT`: Number of log backups to keep

### Performance

```env
MAX_QUEUE_SIZE=100
SEARCH_TIMEOUT=10
STREAM_TIMEOUT=30
```

- `MAX_QUEUE_SIZE`: Maximum songs in queue per server
- `SEARCH_TIMEOUT`: Search timeout in seconds
- `STREAM_TIMEOUT`: Stream extraction timeout in seconds

## YAML Configuration (config/config.yaml)

### Bot Settings

```yaml
bot:
  command_prefix: "!"
  description: "Multi-platform music bot"
  activity: "music from everywhere"
```

### Platform Settings

```yaml
platforms:
  youtube:
    enabled: true
    api_key: ${YOUTUBE_API_KEY}
    max_results: 10
```

Each platform can have:
- `enabled`: Whether the platform is active
- `max_results`: Maximum search results to return
- Platform-specific settings

### Performance Settings

```yaml
performance:
  search_timeout: ${SEARCH_TIMEOUT}
  stream_timeout: ${STREAM_TIMEOUT}
  max_queue_size: ${MAX_QUEUE_SIZE}
  cache_ttl: 3600
```

### Features

```yaml
features:
  auto_disconnect: true
  auto_disconnect_timeout: 300
  save_queue: true
  announce_songs: true
```

- `auto_disconnect`: Automatically leave when alone
- `auto_disconnect_timeout`: Seconds before auto-disconnect
- `save_queue`: Persist queues between restarts
- `announce_songs`: Announce when songs start playing

## Logging Configuration (config/logging.yaml)

### Log Formatters

```yaml
formatters:
  default:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
```

### Log Handlers

```yaml
handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: default
  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: detailed
    filename: logs/robustty.log
```

## Docker Configuration

### Resource Limits

In `docker-compose.yml`, you can set resource limits:

```yaml
services:
  bot:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
```

### Network Configuration

```yaml
networks:
  bot-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

## Per-Server Configuration

Some settings can be configured per-server using bot commands:

- Command prefix: `!setprefix <new_prefix>`
- DJ role: Create a role named "DJ"
- Volume default: Set with `!volume <0-100>`

## Security Considerations

1. Never commit your `.env` file to git
2. Use strong, unique tokens
3. Restrict API keys to specific IPs when possible
4. Regularly rotate credentials
5. Monitor resource usage

## Advanced Configuration

### Custom Platform Settings

To add custom platform settings, modify the platform implementation:

```python
class MyPlatform(VideoPlatform):
    def __init__(self, config):
        super().__init__("myplatform", config)
        self.custom_setting = config.get('custom_setting', 'default')
```

### Redis Configuration

For advanced caching:

```yaml
redis:
  host: redis
  port: 6379
  db: 0
  password: your_redis_password
```

### SSL/TLS Configuration

For secure connections:

```yaml
ssl:
  enabled: true
  cert_path: /path/to/cert.pem
  key_path: /path/to/key.pem
```