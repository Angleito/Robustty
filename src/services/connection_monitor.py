"""
Connection monitoring and automatic reconnection service for Discord voice connections.
Helps handle the WebSocket connection drops and HLS streaming issues.
"""

import asyncio
import logging
from typing import Dict, Optional
import discord
from discord.ext import tasks

logger = logging.getLogger(__name__)


class ConnectionMonitor:
    """Monitors Discord voice connections and automatically handles reconnections"""
    
    def __init__(self, bot):
        self.bot = bot
        self.monitoring = False
        self.reconnection_attempts = {}
        self.max_reconnection_attempts = 5
        
    async def start_monitoring(self):
        """Start connection monitoring"""
        if not self.monitoring:
            self.monitoring = True
            self.connection_check_loop.start()
            logger.info("Connection monitoring started")
    
    async def stop_monitoring(self):
        """Stop connection monitoring"""
        if self.monitoring:
            self.monitoring = False
            self.connection_check_loop.cancel()
            logger.info("Connection monitoring stopped")
    
    @tasks.loop(seconds=30)
    async def connection_check_loop(self):
        """Periodically check voice connections and reconnect if needed"""
        try:
            for guild_id, voice_client in list(self.bot.voice_clients_by_guild.items()):
                if voice_client and not voice_client.is_connected():
                    logger.warning(f"Detected disconnected voice client for guild {guild_id}")
                    await self._handle_disconnected_voice_client(guild_id, voice_client)
                    
        except Exception as e:
            logger.error(f"Error in connection check loop: {e}")
    
    async def _handle_disconnected_voice_client(self, guild_id: int, voice_client: discord.VoiceClient):
        """Handle a disconnected voice client"""
        try:
            # Get the guild and find the bot's current voice channel
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.error(f"Could not find guild {guild_id}")
                return
            
            # Find the last voice channel the bot was in
            last_channel = getattr(voice_client, 'channel', None)
            if not last_channel:
                logger.warning(f"No last channel found for guild {guild_id}")
                return
            
            # Check reconnection attempts
            attempts = self.reconnection_attempts.get(guild_id, 0)
            if attempts >= self.max_reconnection_attempts:
                logger.error(f"Max reconnection attempts reached for guild {guild_id}")
                return
            
            # Attempt reconnection
            logger.info(f"Attempting to reconnect to {last_channel.name} in guild {guild_id} (attempt {attempts + 1})")
            
            try:
                # Disconnect the old client
                await voice_client.disconnect(force=True)
                
                # Wait a moment
                await asyncio.sleep(2)
                
                # Reconnect
                new_voice_client = await last_channel.connect(timeout=30.0, reconnect=True)
                
                # Update the bot's voice client tracking
                if hasattr(self.bot, 'voice_clients_by_guild'):
                    self.bot.voice_clients_by_guild[guild_id] = new_voice_client
                
                # Update audio player
                if hasattr(self.bot, 'audio_players'):
                    audio_player = self.bot.audio_players.get(guild_id)
                    if audio_player:
                        audio_player.voice_client = new_voice_client
                        logger.info(f"Updated audio player voice client for guild {guild_id}")
                
                # Reset reconnection attempts on success
                self.reconnection_attempts[guild_id] = 0
                logger.info(f"Successfully reconnected to {last_channel.name} in guild {guild_id}")
                
            except Exception as e:
                # Increment reconnection attempts
                self.reconnection_attempts[guild_id] = attempts + 1
                logger.error(f"Reconnection attempt {attempts + 1} failed for guild {guild_id}: {e}")
                
                # Exponential backoff
                backoff_delay = min(60, 2 ** attempts)
                logger.info(f"Will retry reconnection in {backoff_delay} seconds")
                await asyncio.sleep(backoff_delay)
                
        except Exception as e:
            logger.error(f"Error handling disconnected voice client for guild {guild_id}: {e}")
    
    @connection_check_loop.before_loop
    async def before_connection_check(self):
        """Wait for bot to be ready before starting monitoring"""
        await self.bot.wait_until_ready()


class StreamHealthMonitor:
    """Monitors stream health and provides fallback mechanisms"""
    
    def __init__(self):
        self.failed_urls = set()
        self.url_failure_counts = {}
        self.max_failures_per_url = 3
        
    def mark_url_failed(self, url: str):
        """Mark a URL as failed"""
        if url in self.url_failure_counts:
            self.url_failure_counts[url] += 1
        else:
            self.url_failure_counts[url] = 1
            
        if self.url_failure_counts[url] >= self.max_failures_per_url:
            self.failed_urls.add(url)
            logger.warning(f"URL marked as persistently failing: {url[:100]}...")
    
    def is_url_healthy(self, url: str) -> bool:
        """Check if a URL is considered healthy"""
        return url not in self.failed_urls
    
    def reset_url_health(self, url: str):
        """Reset health status for a URL"""
        self.failed_urls.discard(url)
        self.url_failure_counts.pop(url, None)
    
    def get_health_stats(self) -> Dict:
        """Get health monitoring statistics"""
        return {
            "failed_urls_count": len(self.failed_urls),
            "total_monitored_urls": len(self.url_failure_counts),
            "failure_rate": len(self.failed_urls) / max(1, len(self.url_failure_counts))
        }


# Global instances
_stream_health_monitor = None

def get_stream_health_monitor() -> StreamHealthMonitor:
    """Get the global stream health monitor instance"""
    global _stream_health_monitor
    if _stream_health_monitor is None:
        _stream_health_monitor = StreamHealthMonitor()
    return _stream_health_monitor