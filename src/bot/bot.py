import asyncio
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
from src.services.quota_monitor import QuotaMonitor, create_quota_monitor
from src.services.voice_connection_manager import VoiceConnectionManager
from src.utils.config_loader import ConfigType
from src.services.metrics_collector import get_metrics_collector
from src.services.health_monitor import HealthMonitor
from src.services.stability_monitor import StabilityMonitor
# from src.utils.resilient_discord_client import add_resilient_connection_to_bot
from src.utils.network_connectivity import get_connectivity_manager
from src.services.http_session_manager import cleanup_session_manager

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
        self.platform_registry: Optional[PlatformRegistry] = None
        self.searcher: Optional[MultiPlatformSearcher] = None
        self.cookie_manager: Optional[CookieManager] = None
        self.enhanced_cookie_manager: Optional[EnhancedCookieManager] = None
        self.cookie_health_monitor: Optional[CookieHealthMonitor] = None
        self.fallback_manager: Optional[PlatformFallbackManager] = None
        self.health_endpoints: Optional[HealthEndpoints] = None
        self.quota_monitor: Optional[QuotaMonitor] = None
        self.audio_players: Dict[int, AudioPlayer] = {}
        self.voice_connection_manager: Optional[VoiceConnectionManager] = None
        self.metrics = get_metrics_collector()
        self.health_monitor: Optional[HealthMonitor] = None
        self.stability_monitor: Optional[StabilityMonitor] = None
        self.connectivity_manager = get_connectivity_manager(config)

        # Temporarily disable resilient connection to fix infinite loop
        # self.resilient_client = add_resilient_connection_to_bot(self, config)
        self.resilient_client = None

    async def setup_hook(self) -> None:
        """Initialize bot components"""
        # Initialize cache manager first
        from src.services.cache_manager import CacheManager

        self.cache_manager = CacheManager(self.config)
        await self.cache_manager.initialize()
        
        # Initialize quota monitor for YouTube API
        self.quota_monitor = await create_quota_monitor(
            self.config,
            self.cache_manager.redis_client if hasattr(self.cache_manager, 'redis_client') else None
        )

        # Initialize platform registry with cache manager
        self.platform_registry = PlatformRegistry(self.cache_manager)

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
        
        # Initialize stability monitor
        self.stability_monitor = StabilityMonitor(self.platform_registry)
        
        # Log platform status after loading
        if self.stability_monitor.enabled:
            enabled_platforms = list(self.platform_registry.get_enabled_platforms().keys())
            logger.info(f"STABILITY MODE: Active platforms: {enabled_platforms}")
            if self.stability_monitor.problematic_platforms:
                logger.warning(f"STABILITY MODE: Problematic platforms disabled: {self.stability_monitor.problematic_platforms}")

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
                # Set quota monitor for YouTube
                if platform_name == "youtube" and platform and hasattr(platform, "set_quota_monitor"):
                    platform.set_quota_monitor(self.quota_monitor)
            except Exception as e:
                logger.warning(f"Failed to set managers on {platform_name}: {e}")

        # Initialize health endpoints
        health_config = self.config.get("health_endpoints", {})
        self.health_endpoints = HealthEndpoints(
            host=health_config.get("host", "0.0.0.0"),
            port=health_config.get("port", 8081)
        )
        self.health_endpoints.set_services(
            cookie_health_monitor=self.cookie_health_monitor,
            fallback_manager=self.fallback_manager,
            cookie_manager=self.enhanced_cookie_manager,
            platform_registry=self.platform_registry,
            quota_monitor=self.quota_monitor,
            stability_monitor=self.stability_monitor,
        )
        await self.health_endpoints.start()

        # Initialize services
        self.searcher = MultiPlatformSearcher(self.platform_registry, self.config, self.stability_monitor)

        # Load cookies
        await self.cookie_manager.load_cookies()
        await self.enhanced_cookie_manager.load_cookies()

        # Initialize health monitor
        self.health_monitor = HealthMonitor(self, self.config)
        
        # Initialize voice connection manager
        self.voice_connection_manager = VoiceConnectionManager(self)
        logger.info("Voice connection manager initialized")
        
        # Initialize platform prioritization manager
        from src.services.platform_prioritization import initialize_prioritization_manager
        initialize_prioritization_manager(self.config)

        # Setup connection monitoring callbacks (stub implementation since resilient client is disabled)
        # self.add_connection_callback(
        #     on_lost=self._on_connection_lost, on_restored=self._on_connection_restored
        # )

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
            
        # Start stability monitor if enabled
        if self.stability_monitor:
            await self.stability_monitor.start()
            logger.info("Stability monitor started")

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
        """Cleanup on bot shutdown with proper resource management"""
        logger.info("Shutting down bot...")

        try:
            # Stop health endpoints first
            if self.health_endpoints:
                try:
                    await self.health_endpoints.stop()
                    logger.info("Health endpoints stopped")
                except Exception as e:
                    logger.error(f"Error stopping health endpoints: {e}")

            # Stop health monitor
            if self.health_monitor:
                try:
                    await self.health_monitor.stop()
                    logger.info("Health monitor stopped")
                except Exception as e:
                    logger.error(f"Error stopping health monitor: {e}")

            # Stop cookie health monitor
            if self.cookie_health_monitor:
                try:
                    await self.cookie_health_monitor.stop()
                    logger.info("Cookie health monitor stopped")
                except Exception as e:
                    logger.error(f"Error stopping cookie health monitor: {e}")

            # Stop fallback manager
            if self.fallback_manager:
                try:
                    await self.fallback_manager.stop()
                    logger.info("Fallback manager stopped")
                except Exception as e:
                    logger.error(f"Error stopping fallback manager: {e}")

            # Cleanup searcher
            if self.searcher:
                try:
                    await self.searcher.cleanup()
                    logger.info("Searcher cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up searcher: {e}")

            # Cleanup audio players with proper voice disconnection
            logger.info(f"Cleaning up {len(self.audio_players)} audio players")
            for guild_id, player in list(self.audio_players.items()):
                try:
                    await player.cleanup()
                    logger.info(f"Cleaned up audio player for guild {guild_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up audio player for guild {guild_id}: {e}")
            
            # Clear audio players dict
            self.audio_players.clear()

            # Cleanup voice connection manager
            if self.voice_connection_manager:
                try:
                    await self.voice_connection_manager.cleanup()
                    logger.info("Voice connection manager cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up voice connection manager: {e}")

            # Disconnect from all voice channels (backup in case voice manager didn't handle all)
            for guild in self.guilds:
                try:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.is_connected():
                        await voice_client.disconnect(force=True)
                        logger.info(f"Disconnected from voice channel in guild {guild.name}")
                except Exception as e:
                    logger.error(f"Error disconnecting from voice in guild {guild.name}: {e}")

            # Cleanup platforms
            if self.platform_registry:
                try:
                    await self.platform_registry.cleanup_all()
                    logger.info("Platform registry cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up platform registry: {e}")

            # Shutdown prioritization manager
            try:
                from src.services.platform_prioritization import shutdown_prioritization_manager
                shutdown_prioritization_manager()
                logger.info("Prioritization manager shut down")
            except Exception as e:
                logger.error(f"Error shutting down prioritization manager: {e}")

            # Cleanup cache manager
            if hasattr(self, "cache_manager") and self.cache_manager:
                try:
                    await self.cache_manager.close()
                    logger.info("Cache manager closed")
                except Exception as e:
                    logger.error(f"Error closing cache manager: {e}")
            
            # Cleanup quota monitor
            if self.quota_monitor:
                try:
                    await self.quota_monitor.cleanup()
                    logger.info("Quota monitor cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up quota monitor: {e}")

            # Cleanup cookie managers
            if self.cookie_manager:
                try:
                    await self.cookie_manager.cleanup()
                    logger.info("Cookie manager cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up cookie manager: {e}")
            
            if self.enhanced_cookie_manager:
                try:
                    await self.enhanced_cookie_manager.cleanup()
                    logger.info("Enhanced cookie manager cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up enhanced cookie manager: {e}")

            # Clean up global HTTP session manager
            try:
                await cleanup_session_manager()
                logger.info("HTTP session manager cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up HTTP session manager: {e}")
            
            # Add a small delay to ensure all connections are closed
            await asyncio.sleep(1.0)

            # Call parent close
            await super().close()
            logger.info("Bot shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"Error during bot shutdown: {e}")
            # Still try to cleanup session manager if not done
            try:
                await cleanup_session_manager()
            except Exception as cleanup_error:
                logger.error(f"Error in emergency session cleanup: {cleanup_error}")
            
            # Still try to call parent close
            try:
                await super().close()
            except Exception as e2:
                logger.error(f"Error calling parent close: {e2}")
            raise

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
