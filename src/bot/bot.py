import discord
from discord.ext import commands
import logging
from typing import Optional, Dict
from services.searcher import MultiPlatformSearcher
from services.cookie_manager import CookieManager
from services.audio_player import AudioPlayer
from platforms.registry import PlatformRegistry

logger = logging.getLogger(__name__)

class RobusttyBot(commands.Bot):
    def __init__(self, config: dict):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix=config['bot']['command_prefix'],
            intents=intents,
            description=config['bot']['description'],
            help_command=None  # Disable default help command
        )
        
        self.config = config
        self.platform_registry = PlatformRegistry()
        self.searcher: Optional[MultiPlatformSearcher] = None
        self.cookie_manager: Optional[CookieManager] = None
        self.audio_players: Dict[int, AudioPlayer] = {}
    
    async def setup_hook(self):
        """Initialize bot components"""
        # Load platforms dynamically
        try:
            # Import platform modules
            from platforms.youtube import YouTubePlatform
            from platforms.peertube import PeerTubePlatform
            self.platform_registry.register_platform('youtube', YouTubePlatform)
            self.platform_registry.register_platform('peertube', PeerTubePlatform)
            
            # Import other platforms as they're implemented
            # from platforms.odysee import OdyseePlatform
            # from platforms.rumble import RumblePlatform
            # self.platform_registry.register_platform('odysee', OdyseePlatform)
            # self.platform_registry.register_platform('rumble', RumblePlatform)
            
        except ImportError as e:
            logger.warning(f"Failed to import platform: {e}")
        
        # Load platforms from config
        await self.platform_registry.load_platforms(self.config['platforms'])
        
        # Initialize services
        self.searcher = MultiPlatformSearcher(self.platform_registry)
        self.cookie_manager = CookieManager(self.config.get('cookies', {}))
        
        # Load cogs
        await self.load_extension('bot.cogs.music')
        await self.load_extension('bot.cogs.admin')
        await self.load_extension('bot.cogs.info')
        
        logger.info("Bot setup completed")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        
        # Set activity
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=self.config['bot']['activity']
        )
        await self.change_presence(activity=activity)
    
    async def on_guild_join(self, guild):
        """Called when bot joins a guild"""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
    
    async def on_guild_remove(self, guild):
        """Called when bot leaves a guild"""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
        
        # Cleanup audio player
        if guild.id in self.audio_players:
            await self.audio_players[guild.id].cleanup()
            del self.audio_players[guild.id]
    
    def get_audio_player(self, guild_id: int) -> AudioPlayer:
        """Get or create audio player for guild"""
        if guild_id not in self.audio_players:
            self.audio_players[guild_id] = AudioPlayer(self.config['performance'])
        return self.audio_players[guild_id]
    
    async def close(self):
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