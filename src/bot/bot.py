import logging
from typing import Dict, Optional

import discord
from discord.ext import commands

from src.platforms.registry import PlatformRegistry
from src.services.audio_player import AudioPlayer
from src.services.cookie_manager import CookieManager
from src.services.enhanced_cookie_manager import EnhancedCookieManager
from src.services.cookie_health_monitor import CookieHealthMonitor
from src.services.platform_fallback_manager import PlatformFallbackManager
from src.services.health_endpoints import HealthEndpoints
from src.services.searcher import MultiPlatformSearcher
from src.utils.config_loader import ConfigType
from src.services.metrics_collector import get_metrics_collector
from src.services.health_monitor import HealthMonitor
# from src.utils.resilient_discord_client import add_resilient_connection_to_bot
from src.utils.network_connectivity import get_connectivity_manager

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
        self.enhanced_cookie_manager: Optional[EnhancedCookieManager] = None
        self.cookie_health_monitor: Optional[CookieHealthMonitor] = None
        self.fallback_manager: Optional[PlatformFallbackManager] = None
        self.health_endpoints: Optional[HealthEndpoints] = None
        self.audio_players: Dict[int, AudioPlayer] = {}
        self.metrics = get_metrics_collector()
        self.health_monitor: Optional[HealthMonitor] = None
        self.connectivity_manager = get_connectivity_manager(config)

        # Temporarily disable resilient connection to fix infinite loop
        # self.resilient_client = add_resilient_connection_to_bot(self, config)
        self.resilient_client = None

    async def setup_hook(self) -> None:
        """Initialize bot components"""
        # Load platforms dynamically
        try:
            # Import platform modules
            from src.platforms.peertube import PeerTubePlatform
            from src.platforms.youtube import YouTubePlatform
            from src.platforms.rumble import RumblePlatform
            from src.platforms.odysee import OdyseePlatform

            self.platform_registry.register_platform("youtube", YouTubePlatform)
            self.platform_registry.register_platform("peertube", PeerTubePlatform)
            self.platform_registry.register_platform("rumble", RumblePlatform)
            self.platform_registry.register_platform("odysee", OdyseePlatform)

        except ImportError as e:
            logger.warning(f"Failed to import platform: {e}")

        # Load platforms from config
        await self.platform_registry.load_platforms(self.config["platforms"])

        # Initialize cookie management services
        cookie_config = self.config.get("cookies", {})
        self.cookie_manager = CookieManager(cookie_config)
        self.enhanced_cookie_manager = EnhancedCookieManager(cookie_config)

        # Initialize cookie health monitoring
        self.cookie_health_monitor = CookieHealthMonitor(cookie_config)
        await self.cookie_health_monitor.start()

        # Initialize platform fallback management
        fallback_config = self.config.get("fallbacks", {})
        self.fallback_manager = PlatformFallbackManager(fallback_config)
        await self.fallback_manager.start()

        # Set fallback and health monitors on platforms
        for platform_name in ["youtube", "rumble", "odysee", "peertube"]:
            try:
                platform = self.platform_registry.get_platform(platform_name)
                if platform and hasattr(platform, "set_fallback_manager"):
                    platform.set_fallback_manager(self.fallback_manager)
                if platform and hasattr(platform, "set_cookie_health_monitor"):
                    platform.set_cookie_health_monitor(self.cookie_health_monitor)
            except Exception as e:
                logger.warning(f"Failed to set managers on {platform_name}: {e}")

        # Initialize health endpoints
        health_config = self.config.get("health_endpoints", {})
        self.health_endpoints = HealthEndpoints(health_config)
        self.health_endpoints.set_dependencies(
            self.cookie_health_monitor,
            self.fallback_manager,
            self.enhanced_cookie_manager,
            self.platform_registry,
        )
        await self.health_endpoints.start()

        # Initialize services
        self.searcher = MultiPlatformSearcher(self.platform_registry)

        # Load cookies
        await self.cookie_manager.load_cookies()
        await self.enhanced_cookie_manager.load_cookies()

        # Initialize cache manager if needed
        from src.services.cache_manager import CacheManager

        self.cache_manager = CacheManager(self.config)
        await self.cache_manager.initialize()

        # Initialize health monitor
        self.health_monitor = HealthMonitor(self, self.config)

        # Setup connection monitoring callbacks
        self.add_connection_callback(
            on_lost=self._on_connection_lost, on_restored=self._on_connection_restored
        )

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

        # Start health monitor if enabled
        if self.health_monitor and self.config.get("health_monitor", {}).get(
            "enabled", True
        ):
            await self.health_monitor.start()
            logger.info("Health monitor started")

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

        # Stop health endpoints first
        if self.health_endpoints:
            await self.health_endpoints.stop()

        # Stop health monitor
        if self.health_monitor:
            await self.health_monitor.stop()

        # Stop cookie health monitor
        if self.cookie_health_monitor:
            await self.cookie_health_monitor.stop()

        # Stop fallback manager
        if self.fallback_manager:
            await self.fallback_manager.stop()

        # Cleanup audio players
        for player in self.audio_players.values():
            await player.cleanup()

        # Cleanup platforms
        await self.platform_registry.cleanup_all()

        # Cleanup cache manager
        if hasattr(self, "cache_manager") and self.cache_manager:
            await self.cache_manager.close()

        # Cleanup cookie managers
        if self.cookie_manager:
            await self.cookie_manager.cleanup()
        if self.enhanced_cookie_manager:
            await self.enhanced_cookie_manager.cleanup()

        await super().close()

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Track voice connection changes for metrics"""
        # Only track bot's own voice state
        if member.id == self.user.id if self.user else None:
            self._update_connection_metrics()

    def _update_connection_metrics(self) -> None:
        """Update active voice connections metric"""
        active_connections = sum(
            1
            for player in self.audio_players.values()
            if player.voice_client and player.voice_client.is_connected()
        )
        self.metrics.set_active_connections(active_connections)

    async def _on_connection_lost(self) -> None:
        """Handle Discord connection loss"""
        logger.warning("Discord connection lost - initiating recovery procedures")

        # Pause all audio players
        for player in self.audio_players.values():
            if player.is_playing():
                await player.pause()
                logger.info(f"Paused audio player for guild {player.guild_id}")

        # Update metrics
        self.metrics.increment_connection_losses()

        # Stop health monitor temporarily
        if self.health_monitor:
            await self.health_monitor.pause()

    async def _on_connection_restored(self) -> None:
        """Handle Discord connection restoration"""
        logger.info("Discord connection restored - resuming operations")

        # Resume health monitor
        if self.health_monitor:
            await self.health_monitor.resume()

        # Resume audio players that were paused
        for player in self.audio_players.values():
            if player.is_paused() and player.current_track:
                await player.resume()
                logger.info(f"Resumed audio player for guild {player.guild_id}")

        # Update metrics
        self.metrics.increment_connection_restorations()
        self._update_connection_metrics()
