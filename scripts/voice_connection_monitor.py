#!/usr/bin/env python3
"""
Voice Connection Health Monitor
Real-time monitoring and recovery for Discord voice connections
Specifically designed to detect and recover from 4006 errors
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json

try:
    import discord
    from discord.ext import commands, tasks
except ImportError:
    print("discord.py not available - monitor will run in standalone mode")
    discord = None
    commands = None
    tasks = None

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """Voice connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"

@dataclass
class VoiceConnectionEvent:
    """Voice connection event data"""
    timestamp: datetime
    guild_id: int
    channel_id: Optional[int]
    event_type: str
    old_state: Optional[ConnectionState]
    new_state: ConnectionState
    error: Optional[str] = None
    latency: Optional[float] = None
    region: Optional[str] = None

@dataclass
class VoiceConnectionStats:
    """Voice connection statistics"""
    guild_id: int
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    disconnections: int = 0
    error_4006_count: int = 0
    avg_connection_time: float = 0.0
    last_connection: Optional[datetime] = None
    last_disconnection: Optional[datetime] = None
    current_uptime: timedelta = field(default_factory=lambda: timedelta(0))
    events: List[VoiceConnectionEvent] = field(default_factory=list)

class VoiceConnectionMonitor:
    """Monitor and manage voice connection health"""
    
    def __init__(self, bot=None, config: Optional[Dict] = None):
        self.bot = bot
        self.config = config or {}
        self.stats: Dict[int, VoiceConnectionStats] = {}
        self.monitoring_active = False
        self.recovery_callbacks: List[Callable] = []
        
        # Configuration
        self.max_events_per_guild = self.config.get('max_events_per_guild', 100)
        self.recovery_delay = self.config.get('recovery_delay', 5.0)
        self.max_recovery_attempts = self.config.get('max_recovery_attempts', 3)
        self.health_check_interval = self.config.get('health_check_interval', 30)
        self.error_4006_threshold = self.config.get('error_4006_threshold', 3)
        
        # Setup logging
        self.setup_logging()
        
        # Start monitoring task if bot is available
        if self.bot and discord and tasks:
            self.health_check_task.start()
    
    def setup_logging(self):
        """Setup specialized logging for voice connections"""
        # Create voice connection logger
        self.voice_logger = logging.getLogger('voice_connections')
        
        # Add file handler for voice connection logs
        voice_handler = logging.FileHandler('voice_diagnostics.log')
        voice_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        voice_handler.setFormatter(voice_formatter)
        self.voice_logger.addHandler(voice_handler)
        self.voice_logger.setLevel(logging.INFO)
    
    def get_guild_stats(self, guild_id: int) -> VoiceConnectionStats:
        """Get or create stats for a guild"""
        if guild_id not in self.stats:
            self.stats[guild_id] = VoiceConnectionStats(guild_id=guild_id)
        return self.stats[guild_id]
    
    def record_event(self, guild_id: int, event_type: str, channel_id: Optional[int] = None,
                    old_state: Optional[ConnectionState] = None, new_state: ConnectionState = ConnectionState.CONNECTED,
                    error: Optional[str] = None, latency: Optional[float] = None, region: Optional[str] = None):
        """Record a voice connection event"""
        
        stats = self.get_guild_stats(guild_id)
        
        event = VoiceConnectionEvent(
            timestamp=datetime.now(),
            guild_id=guild_id,
            channel_id=channel_id,
            event_type=event_type,
            old_state=old_state,
            new_state=new_state,
            error=error,
            latency=latency,
            region=region
        )
        
        # Add event to stats
        stats.events.append(event)
        
        # Limit events per guild
        if len(stats.events) > self.max_events_per_guild:
            stats.events = stats.events[-self.max_events_per_guild:]
        
        # Update counters
        if event_type == 'connection':
            stats.total_connections += 1
            if new_state == ConnectionState.CONNECTED:
                stats.successful_connections += 1
                stats.last_connection = event.timestamp
            else:
                stats.failed_connections += 1
        
        elif event_type == 'disconnection':
            stats.disconnections += 1
            stats.last_disconnection = event.timestamp
        
        # Track 4006 errors specifically
        if error and '4006' in str(error):
            stats.error_4006_count += 1
            self.voice_logger.error(f"4006 error detected in guild {guild_id}: {error}")
            
            # Trigger recovery if threshold exceeded
            if stats.error_4006_count >= self.error_4006_threshold:
                asyncio.create_task(self.trigger_recovery(guild_id, "4006_threshold_exceeded"))
        
        # Log the event
        self.voice_logger.info(f"Guild {guild_id}: {event_type} - {old_state} -> {new_state}")
        
        if error:
            self.voice_logger.warning(f"Guild {guild_id}: Error - {error}")
    
    async def trigger_recovery(self, guild_id: int, reason: str):
        """Trigger voice connection recovery for a guild"""
        logger.info(f"Triggering voice recovery for guild {guild_id}: {reason}")
        
        # Wait for recovery delay
        await asyncio.sleep(self.recovery_delay)
        
        # Call recovery callbacks
        for callback in self.recovery_callbacks:
            try:
                await callback(guild_id, reason)
            except Exception as e:
                logger.error(f"Recovery callback failed: {e}")
        
        # If bot is available, try to reconnect
        if self.bot and discord:
            await self.attempt_voice_reconnection(guild_id)
    
    async def attempt_voice_reconnection(self, guild_id: int):
        """Attempt to reconnect voice connection for a guild"""
        if not self.bot:
            return
        
        guild = self.bot.get_guild(guild_id)
        if not guild:
            logger.error(f"Guild {guild_id} not found for reconnection")
            return
        
        # Check if bot is currently connected to voice
        voice_client = guild.voice_client
        if voice_client and voice_client.is_connected():
            logger.info(f"Guild {guild_id}: Voice client already connected")
            return
        
        # Find a suitable voice channel to reconnect to
        # Look for a channel where bot members are present
        target_channel = None
        
        for channel in guild.voice_channels:
            # Check if bot has permissions
            if channel.permissions_for(guild.me).connect:
                # Check if there are members in the channel
                if len(channel.members) > 0:
                    target_channel = channel
                    break
        
        if not target_channel:
            logger.warning(f"Guild {guild_id}: No suitable voice channel found for reconnection")
            return
        
        # Attempt reconnection
        try:
            logger.info(f"Guild {guild_id}: Attempting reconnection to {target_channel.name}")
            
            # Disconnect first if partially connected
            if voice_client:
                await voice_client.disconnect(force=True)
                await asyncio.sleep(1)
            
            # Reconnect
            new_voice_client = await target_channel.connect()
            
            self.record_event(
                guild_id=guild_id,
                event_type='reconnection',
                channel_id=target_channel.id,
                old_state=ConnectionState.DISCONNECTED,
                new_state=ConnectionState.CONNECTED,
                region=str(new_voice_client.endpoint) if hasattr(new_voice_client, 'endpoint') else None
            )
            
            logger.info(f"Guild {guild_id}: Successfully reconnected to {target_channel.name}")
            
        except Exception as e:
            self.record_event(
                guild_id=guild_id,
                event_type='reconnection_failed',
                channel_id=target_channel.id,
                old_state=ConnectionState.RECONNECTING,
                new_state=ConnectionState.FAILED,
                error=str(e)
            )
            
            logger.error(f"Guild {guild_id}: Reconnection failed - {e}")
    
    @tasks.loop(seconds=30)
    async def health_check_task(self):
        """Periodic health check for voice connections"""
        if not self.bot:
            return
        
        logger.debug("Running voice connection health check")
        
        for guild in self.bot.guilds:
            if guild.voice_client:
                await self.check_voice_connection_health(guild.id)
    
    async def check_voice_connection_health(self, guild_id: int):
        """Check health of a specific voice connection"""
        if not self.bot:
            return
        
        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            return
        
        voice_client = guild.voice_client
        
        # Check connection status
        if not voice_client.is_connected():
            self.record_event(
                guild_id=guild_id,
                event_type='health_check_failed',
                old_state=ConnectionState.CONNECTED,
                new_state=ConnectionState.DISCONNECTED,
                error='Connection lost during health check'
            )
            
            # Trigger recovery
            await self.trigger_recovery(guild_id, "health_check_failed")
            return
        
        # Check latency if available
        latency = getattr(voice_client, 'latency', None)
        if latency:
            # Convert to milliseconds
            latency_ms = latency * 1000
            
            # Log high latency
            if latency_ms > 500:  # > 500ms is concerning
                self.voice_logger.warning(f"Guild {guild_id}: High voice latency {latency_ms:.1f}ms")
            
            self.record_event(
                guild_id=guild_id,
                event_type='health_check',
                new_state=ConnectionState.CONNECTED,
                latency=latency_ms
            )
    
    def add_recovery_callback(self, callback: Callable):
        """Add a callback function to be called during recovery"""
        self.recovery_callbacks.append(callback)
    
    def get_stats_summary(self, guild_id: Optional[int] = None) -> Dict:
        """Get statistics summary"""
        if guild_id:
            if guild_id in self.stats:
                stats = self.stats[guild_id]
                return {
                    'guild_id': guild_id,
                    'total_connections': stats.total_connections,
                    'successful_connections': stats.successful_connections,
                    'failed_connections': stats.failed_connections,
                    'success_rate': (stats.successful_connections / max(stats.total_connections, 1)) * 100,
                    'error_4006_count': stats.error_4006_count,
                    'last_connection': stats.last_connection.isoformat() if stats.last_connection else None,
                    'event_count': len(stats.events)
                }
            else:
                return {'guild_id': guild_id, 'error': 'No stats available'}
        
        else:
            # Return summary for all guilds
            summary = {
                'total_guilds': len(self.stats),
                'guilds': {}
            }
            
            total_connections = 0
            total_successful = 0
            total_4006_errors = 0
            
            for gid, stats in self.stats.items():
                total_connections += stats.total_connections
                total_successful += stats.successful_connections
                total_4006_errors += stats.error_4006_count
                
                summary['guilds'][gid] = {
                    'connections': stats.total_connections,
                    'success_rate': (stats.successful_connections / max(stats.total_connections, 1)) * 100,
                    'error_4006_count': stats.error_4006_count
                }
            
            summary['totals'] = {
                'connections': total_connections,
                'success_rate': (total_successful / max(total_connections, 1)) * 100,
                'error_4006_count': total_4006_errors
            }
            
            return summary
    
    def export_stats(self, filename: str):
        """Export statistics to JSON file"""
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'guilds': {}
        }
        
        for guild_id, stats in self.stats.items():
            export_data['guilds'][guild_id] = {
                'total_connections': stats.total_connections,
                'successful_connections': stats.successful_connections,
                'failed_connections': stats.failed_connections,
                'disconnections': stats.disconnections,
                'error_4006_count': stats.error_4006_count,
                'last_connection': stats.last_connection.isoformat() if stats.last_connection else None,
                'last_disconnection': stats.last_disconnection.isoformat() if stats.last_disconnection else None,
                'events': [
                    {
                        'timestamp': event.timestamp.isoformat(),
                        'event_type': event.event_type,
                        'old_state': event.old_state.value if event.old_state else None,
                        'new_state': event.new_state.value,
                        'error': event.error,
                        'latency': event.latency,
                        'region': event.region
                    }
                    for event in stats.events[-50:]  # Last 50 events per guild
                ]
            }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Stats exported to {filename}")
    
    async def cleanup(self):
        """Cleanup monitor resources"""
        if hasattr(self, 'health_check_task'):
            self.health_check_task.cancel()
        
        logger.info("Voice connection monitor cleanup completed")

# Example usage as a bot extension
if discord and commands:
    class VoiceMonitorCog(commands.Cog):
        """Discord bot cog for voice connection monitoring"""
        
        def __init__(self, bot):
            self.bot = bot
            self.monitor = VoiceConnectionMonitor(bot)
        
        @commands.Cog.listener()
        async def on_voice_state_update(self, member, before, after):
            """Track voice state changes for the bot"""
            if member.id != self.bot.user.id:
                return
            
            guild_id = member.guild.id
            
            # Bot joined voice channel
            if before.channel is None and after.channel is not None:
                self.monitor.record_event(
                    guild_id=guild_id,
                    event_type='connection',
                    channel_id=after.channel.id,
                    old_state=ConnectionState.DISCONNECTED,
                    new_state=ConnectionState.CONNECTED
                )
            
            # Bot left voice channel
            elif before.channel is not None and after.channel is None:
                self.monitor.record_event(
                    guild_id=guild_id,
                    event_type='disconnection',
                    channel_id=before.channel.id,
                    old_state=ConnectionState.CONNECTED,
                    new_state=ConnectionState.DISCONNECTED
                )
            
            # Bot moved between channels
            elif before.channel != after.channel and after.channel is not None:
                self.monitor.record_event(
                    guild_id=guild_id,
                    event_type='channel_change',
                    channel_id=after.channel.id,
                    old_state=ConnectionState.CONNECTED,
                    new_state=ConnectionState.CONNECTED
                )
        
        @commands.command(name='voice_stats')
        @commands.has_permissions(administrator=True)
        async def voice_stats(self, ctx, guild_id: Optional[int] = None):
            """Display voice connection statistics"""
            target_guild_id = guild_id or ctx.guild.id
            stats = self.monitor.get_stats_summary(target_guild_id)
            
            if 'error' in stats:
                await ctx.send(f"❌ {stats['error']}")
                return
            
            embed = discord.Embed(
                title=f"Voice Connection Stats - Guild {target_guild_id}",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Connections",
                value=f"Total: {stats['total_connections']}\nSuccessful: {stats['successful_connections']}\nFailed: {stats['failed_connections']}",
                inline=True
            )
            
            embed.add_field(
                name="Success Rate",
                value=f"{stats['success_rate']:.1f}%",
                inline=True
            )
            
            embed.add_field(
                name="4006 Errors",
                value=str(stats['error_4006_count']),
                inline=True
            )
            
            if stats['last_connection']:
                embed.add_field(
                    name="Last Connection",
                    value=stats['last_connection'],
                    inline=False
                )
            
            await ctx.send(embed=embed)
        
        def cog_unload(self):
            """Cleanup when cog is unloaded"""
            asyncio.create_task(self.monitor.cleanup())

# Standalone mode
async def main():
    """Run monitor in standalone mode"""
    monitor = VoiceConnectionMonitor()
    
    logger.info("Voice Connection Monitor started in standalone mode")
    logger.info("Monitoring voice connection health...")
    
    try:
        while True:
            await asyncio.sleep(60)  # Keep running
    except KeyboardInterrupt:
        logger.info("Shutting down monitor...")
        await monitor.cleanup()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())