"""
Discord client integration with network routing.

This module demonstrates how to integrate the network routing system
with Discord.py to route Discord traffic through specific interfaces.
"""

import logging
from typing import Any, Dict, Optional

import aiohttp
import discord

from .network_routing import get_http_client, ServiceType, discord_session

logger = logging.getLogger(__name__)


class NetworkRoutedDiscordClient(discord.Client):
    """Discord client that uses network routing for connections"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._network_client = None

    async def setup_hook(self):
        """Setup hook called when client is ready"""
        try:
            # Initialize network routing
            self._network_client = get_http_client()
            await self._network_client.initialize()
            
            logger.info("Discord client initialized with network routing")
            
        except Exception as e:
            logger.error(f"Failed to initialize network routing for Discord: {e}")
            raise

    async def close(self):
        """Close client and cleanup network resources"""
        await super().close()
        
        if self._network_client:
            await self._network_client.cleanup()
            logger.info("Discord client network resources cleaned up")

    async def make_discord_api_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make Discord API request using network routing"""
        if not self._network_client:
            raise RuntimeError("Discord client not properly initialized")

        url = f"https://discord.com/api/v10{endpoint}"
        
        # Get Discord token from the client
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bot {self.http.token}'
        headers['User-Agent'] = 'Robustty Bot (Discord Music Bot)'
        kwargs['headers'] = headers

        async with discord_session() as session:
            async with session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()


class NetworkRoutedDiscordHTTP:
    """Custom Discord HTTP client with network routing"""

    def __init__(self, token: str, session: Optional[aiohttp.ClientSession] = None):
        self.token = token
        self._session = session
        self._network_client = None

    async def initialize(self):
        """Initialize network routing"""
        if not self._network_client:
            self._network_client = get_http_client()
            await self._network_client.initialize()

    async def request(self, method: str, endpoint: str, **kwargs) -> aiohttp.ClientResponse:
        """Make HTTP request using network routing"""
        if not self._network_client:
            await self.initialize()

        url = f"https://discord.com/api/v10{endpoint}"
        
        # Add Discord authentication headers
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bot {self.token}'
        headers['User-Agent'] = 'Robustty Bot (Discord Music Bot)'
        kwargs['headers'] = headers

        async with self._network_client.get_session(ServiceType.DISCORD) as session:
            return await session.request(method, url, **kwargs)

    async def get_json(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Get JSON response from Discord API"""
        async with await self.request('GET', endpoint, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def post_json(self, endpoint: str, json_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Post JSON data to Discord API"""
        kwargs['json'] = json_data
        async with await self.request('POST', endpoint, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def close(self):
        """Close HTTP client"""
        if self._network_client:
            await self._network_client.cleanup()


class DiscordAPIHelper:
    """Helper class for making Discord API calls with network routing"""

    def __init__(self, token: str):
        self.token = token
        self.http = NetworkRoutedDiscordHTTP(token)

    async def initialize(self):
        """Initialize the API helper"""
        await self.http.initialize()

    async def get_gateway_info(self) -> Dict[str, Any]:
        """Get Discord gateway information"""
        return await self.http.get_json('/gateway')

    async def get_gateway_bot_info(self) -> Dict[str, Any]:
        """Get Discord gateway bot information"""
        return await self.http.get_json('/gateway/bot')

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information"""
        return await self.http.get_json(f'/users/{user_id}')

    async def get_guild_info(self, guild_id: str) -> Dict[str, Any]:
        """Get guild information"""
        return await self.http.get_json(f'/guilds/{guild_id}')

    async def send_message(self, channel_id: str, content: str) -> Dict[str, Any]:
        """Send message to channel"""
        return await self.http.post_json(f'/channels/{channel_id}/messages', {
            'content': content
        })

    async def close(self):
        """Close API helper"""
        await self.http.close()


async def create_discord_client_with_routing(token: str, **kwargs) -> NetworkRoutedDiscordClient:
    """Create Discord client with network routing"""
    intents = kwargs.get('intents', discord.Intents.default())
    intents.message_content = True
    
    client = NetworkRoutedDiscordClient(intents=intents, **kwargs)
    return client


async def test_discord_routing():
    """Test Discord routing functionality"""
    import os
    
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("No Discord token found in environment")
        return

    try:
        # Test API helper
        api_helper = DiscordAPIHelper(token)
        await api_helper.initialize()
        
        # Test gateway info
        gateway_info = await api_helper.get_gateway_info()
        logger.info(f"Gateway URL: {gateway_info.get('url')}")
        
        # Test bot gateway info
        bot_gateway_info = await api_helper.get_gateway_bot_info()
        logger.info(f"Bot gateway sessions: {bot_gateway_info.get('session_start_limit', {}).get('remaining', 'unknown')}")
        
        await api_helper.close()
        
        logger.info("Discord routing test completed successfully")
        
    except Exception as e:
        logger.error(f"Discord routing test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_discord_routing())