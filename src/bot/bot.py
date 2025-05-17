import logging
from typing import Dict, Optional

import discord
from discord.ext import commands

from src.platforms.registry import PlatformRegistry
from src.services.audio_player import AudioPlayer
from src.services.cookie_manager import CookieManager
from src.services.searcher import MultiPlatformSearcher
from src.utils.config_loader import ConfigType
from src.services.metrics_collector import get_metrics_collector

logger = logging.getLogger(__name__)


class RobusttyBot(commands.Bot):
    def __init__(self, config: ConfigType) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=config["bot"]["command_prefix"],
            intents=intents,
            description=config["bot"]["description"],
            help_command=None,  # Disable default help command
        )

        self.config = config
        self.platform_registry = PlatformRegistry()
        self.searcher: Optional[MultiPlatformSearcher] = None
        self.cookie_manager: Optional[CookieManager] = None
        self.audio_players: Dict[int, AudioPlayer] = {}
        self.metrics = get_metrics_collector()

    async def setup_hook(self) -> None:
        """Initialize bot components"""
        # Load platforms dynamically
        try:
            # Import platform modules
            from src.platforms.peertube import PeerTubePlatform
            from src.platforms.youtube import YouTubePlatform
            from src.platforms.rumble import RumblePlatform

            self.platform_registry.register_platform("youtube", YouTubePlatform)
            self.platform_registry.register_platform("peertube", PeerTubePlatform)
            self.platform_registry.register_platform("rumble", RumblePlatform)

            # Import other platforms as they're implemented
            # from platforms.odysee import OdyseePlatform
            # self.platform_registry.register_platform('odysee', OdyseePlatform)

        except ImportError as e:
            logger.warning(f"Failed to import platform: {e}")

        # Load platforms from config
        await self.platform_registry.load_platforms(self.config["platforms"])

        # Initialize services
        self.searcher = MultiPlatformSearcher(self.platform_registry)
        self.cookie_manager = CookieManager(self.config.get("cookies", {}))

        # Load cogs
        await self.load_extension("src.bot.cogs.music")
        await self.load_extension("src.bot.cogs.admin")
        await self.load_extension("src.bot.cogs.info")

        logger.info("Bot setup completed")

    async def on_ready(self) -> None:
        """Called when bot is ready"""
        if self.user is None:
            logger.error("Bot user is None")
            return

        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

        # Set activity
        activity = discord.Activity(
            type=discord.ActivityType.listening, name=self.config["bot"]["activity"]
        )
        await self.change_presence(activity=activity)
        
        # Update metrics with active connections
        self._update_connection_metrics()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Called when bot joins a guild"""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when bot leaves a guild"""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")

        # Cleanup audio player
        if guild.id in self.audio_players:
            await self.audio_players[guild.id].cleanup()
            del self.audio_players[guild.id]
        
        # Update metrics
        self._update_connection_metrics()

    def get_audio_player(self, guild_id: int) -> AudioPlayer:
        """Get or create audio player for guild"""
        if guild_id not in self.audio_players:
            self.audio_players[guild_id] = AudioPlayer(
                dict(self.config["performance"]), bot=self
            )
        return self.audio_players[guild_id]

    async def close(self) -> None:
        """Cleanup on bot shutdown"""
        logger.info("Shutting down bot...")

        # Cleanup audio players
        for player in self.audio_players.values():
            await player.cleanup()

        # Cleanup platforms
        await self.platform_registry.cleanup_all()

        # Cleanup cookie manager
        if self.cookie_manager:
            await self.cookie_manager.cleanup()

        await super().close()
    
    async def on_voice_state_update(
        self, 
        member: discord.Member, 
        before: discord.VoiceState, 
        after: discord.VoiceState
    ) -> None:
        """Track voice connection changes for metrics"""
        # Only track bot's own voice state
        if member.id == self.user.id if self.user else None:
            self._update_connection_metrics()
    
    def _update_connection_metrics(self) -> None:
        """Update active voice connections metric"""
        active_connections = sum(
            1 for player in self.audio_players.values() 
            if player.voice_client and player.voice_client.is_connected()
        )
        self.metrics.set_active_connections(active_connections)
