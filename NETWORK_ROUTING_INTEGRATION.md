# Network Routing Integration Guide

This guide explains how to integrate the network-aware HTTP client module (`src/utils/network_routing.py`) with the Robustty bot for service-specific network routing.

## Overview

The network routing module provides intelligent HTTP client management that can route different services through different network interfaces. This is particularly useful for:

- Routing Discord traffic through a VPN while keeping API calls on the direct connection
- Implementing split-tunneling in containerized environments
- Optimizing network paths for different service types
- Handling multi-network setups with redundancy

## Key Components

### 1. NetworkAwareHTTPClient

The main client that manages HTTP sessions with network interface binding:

```python
from src.utils.network_routing import get_http_client, ServiceType

# Get the global HTTP client
client = get_http_client()
await client.initialize()

# Get session for specific service
async with client.get_session(ServiceType.DISCORD) as session:
    async with session.get('https://discord.com/api/v10/gateway') as response:
        data = await response.json()
```

### 2. Service-Specific Sessions

Convenient context managers for different services:

```python
from src.utils.network_routing import discord_session, youtube_session, platform_session

# Discord session (may use VPN)
async with discord_session() as session:
    async with session.get('https://discord.com/api/v10/gateway') as response:
        gateway_info = await response.json()

# YouTube session (typically direct)
async with youtube_session() as session:
    async with session.get('https://www.googleapis.com/youtube/v3/search') as response:
        search_results = await response.json()

# Platform-specific session
async with platform_session('rumble') as session:
    async with session.get('https://rumble.com/api/search') as response:
        data = await response.json()
```

### 3. URL-Based Routing

Automatic service detection from URLs:

```python
from src.utils.network_routing import url_session

# Automatically routes based on URL domain
async with url_session('https://discord.com/api/v10/gateway') as session:
    async with session.get(url) as response:
        data = await response.json()
```

## Configuration

### Environment Variables

Configure routing behavior through environment variables:

```bash
# Network strategy
NETWORK_STRATEGY=split_tunnel  # auto, vpn_only, direct_only, split_tunnel

# Service-specific VPN routing
DISCORD_USE_VPN=true
YOUTUBE_USE_VPN=false
RUMBLE_USE_VPN=false
ODYSEE_USE_VPN=false
PEERTUBE_USE_VPN=false

# Interface configuration
VPN_INTERFACE=auto  # or specific interface name
DEFAULT_INTERFACE=auto  # or specific interface name

# Network subnets (for Docker)
VPN_NETWORK_SUBNET=172.28.0.0/16
DIRECT_NETWORK_SUBNET=172.29.0.0/16

# Route marking
VPN_ROUTE_MARK=100
DIRECT_ROUTE_MARK=200
```

### Docker Configuration

For Docker deployments, configure multiple networks:

```yaml
# docker-compose.yml
version: '3.8'

services:
  robustty:
    build: .
    networks:
      - vpn-network
      - direct-network
    environment:
      - DISCORD_USE_VPN=true
      - YOUTUBE_USE_VPN=false
      - VPN_NETWORK_SUBNET=172.28.0.0/16
      - DIRECT_NETWORK_SUBNET=172.29.0.0/16

networks:
  vpn-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
  
  direct-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.29.0.0/16
```

## Integration Examples

### 1. Platform Integration

Update platform classes to use network routing:

```python
# src/platforms/youtube.py
from ..utils.network_routing import youtube_session

class YouTubePlatform(VideoPlatform):
    async def search_videos(self, query: str, max_results: int = 10):
        api_key = self.config.get('api_key')
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'maxResults': max_results,
            'key': api_key
        }
        
        # Use network routing for YouTube API calls
        async with youtube_session() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
```

### 2. Discord Integration

Route Discord traffic through VPN:

```python
# src/utils/discord_with_routing.py
from .network_routing import discord_session

class NetworkRoutedDiscordClient(discord.Client):
    async def make_api_request(self, endpoint: str):
        url = f"https://discord.com/api/v10{endpoint}"
        
        async with discord_session() as session:
            headers = {'Authorization': f'Bot {self.http.token}'}
            async with session.get(url, headers=headers) as response:
                return await response.json()
```

### 3. Bot Integration

Initialize network routing in bot startup:

```python
# src/bot/bot.py
from ..utils.network_routing import initialize_http_client, cleanup_http_client

class RobusttyBot(commands.Bot):
    async def setup_hook(self):
        # Initialize network routing
        await initialize_http_client()
        
        # Initialize platforms with routing
        await self.initialize_platforms()
        
        logger.info("Bot initialized with network routing")
    
    async def close(self):
        # Cleanup network resources
        await cleanup_http_client()
        await super().close()
```

## Network Interface Detection

The module automatically detects network interfaces:

1. **Docker Networks**: Detects based on subnet configuration
2. **VPN Interfaces**: Identifies VPN connections (WireGuard, OpenVPN, etc.)
3. **System Interfaces**: Falls back to system network interfaces
4. **Default Routing**: Provides fallback when detection fails

### Manual Interface Configuration

Override automatic detection:

```python
from src.utils.network_routing import RoutingConfig, NetworkAwareHTTPClient

config = RoutingConfig()
config.vpn_interface = "wg0"  # Specific WireGuard interface
config.direct_interface = "eth0"  # Specific Ethernet interface

client = NetworkAwareHTTPClient(config)
```

## Monitoring and Debugging

### Get Routing Information

```python
from src.utils.network_routing import get_routing_info

# Get current routing configuration
routing_info = await get_routing_info()
print(f"Strategy: {routing_info['strategy']}")
print(f"Interfaces: {routing_info['interfaces']}")
print(f"Routing table: {routing_info['routing_table']}")
```

### Logging

Enable debug logging to see routing decisions:

```python
import logging

logging.getLogger('src.utils.network_routing').setLevel(logging.DEBUG)
```

## Best Practices

### 1. Error Handling

Always handle network failures gracefully:

```python
async with youtube_session() as session:
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"Network request failed: {e}")
        # Implement fallback logic
        return await fallback_method()
```

### 2. Resource Management

Use context managers and proper cleanup:

```python
# Good: Use context managers
async with discord_session() as session:
    async with session.get(url) as response:
        return await response.json()

# Good: Initialize and cleanup properly
client = get_http_client()
await client.initialize()
try:
    # Use client
    pass
finally:
    await client.cleanup()
```

### 3. Configuration

Use environment variables for configuration:

```python
# Good: Environment-based configuration
DISCORD_USE_VPN = os.getenv('DISCORD_USE_VPN', 'false').lower() == 'true'

# Good: Provide defaults
VPN_INTERFACE = os.getenv('VPN_INTERFACE', 'auto')
```

## Troubleshooting

### Common Issues

1. **Interface Not Found**: Check network configuration and interface names
2. **Binding Failed**: Verify IP addresses and network permissions
3. **Routing Loops**: Ensure correct subnet configuration
4. **DNS Issues**: Configure DNS servers for each network

### Debug Commands

```python
# Check detected interfaces
client = get_http_client()
await client.initialize()
routing_info = client.get_routing_info()

# Test specific service routing
async with discord_session() as session:
    print(f"Discord session local address: {session.connector._local_addr}")
```

## Performance Considerations

1. **Session Reuse**: The module reuses sessions for the same service type
2. **Connection Pooling**: Configured per-host connection limits
3. **DNS Caching**: Enabled with configurable TTL
4. **Interface Binding**: Minimal overhead from local address binding

## Security Considerations

1. **VPN Routing**: Ensure VPN traffic is properly isolated
2. **API Keys**: Keep API keys secure and use appropriate headers
3. **DNS Leaks**: Configure DNS servers for each network interface
4. **Traffic Analysis**: Monitor routing decisions in production

## Migration Guide

To migrate existing code to use network routing:

1. Replace direct `aiohttp.ClientSession` usage with routing sessions
2. Update platform classes to use service-specific sessions
3. Configure environment variables for routing behavior
4. Test routing decisions with debug logging enabled
5. Update Docker configuration for multi-network support

This integration provides a robust foundation for intelligent network routing in the Robustty bot, enabling optimal network paths for different services while maintaining security and performance.