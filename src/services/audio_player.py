import asyncio
import logging
from collections import deque
from typing import Dict, List, Optional

import discord

from ..services.metrics_collector import get_metrics_collector

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Manages audio playback for a guild"""

    def __init__(self, config: Dict, bot=None):
        self.config = config
        self.bot = bot
        max_queue_size = config.get("max_queue_size", 100)
        # Convert to int if it's a string from environment
        if isinstance(max_queue_size, str):
            max_queue_size = int(max_queue_size)
        self.queue: deque[Dict] = deque(maxlen=max_queue_size)
        self.current: Optional[Dict] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self._volume = 0.5  # Default 50% volume
        self._is_playing = False
        self._skip_flag = False
        self.metrics = get_metrics_collector()
        self._update_queue_metrics()

    async def add_to_queue(self, song_info: Dict):
        """Add a song to the queue"""
        if self.queue.maxlen and len(self.queue) >= self.queue.maxlen:
            raise ValueError("Queue is full")
        self.queue.append(song_info)
        logger.info(f"Added to queue: {song_info['title']}")
        logger.info(f"Queue song info: ID={song_info.get('id')}, Platform={song_info.get('platform')}, URL={song_info.get('url')}")
        self._update_queue_metrics()

    async def play_next(self):
        """Play the next song in queue"""
        logger.info(f"play_next called. Is playing: {self._is_playing}, Queue size: {len(self.queue)}")
        
        if self._is_playing:
            logger.info("Already playing, returning")
            return

        if not self.queue and not self.current:
            logger.info("No songs in queue and no current song")
            return

        if not self.queue:
            logger.info("Queue is empty, clearing current")
            self.current = None
            self._is_playing = False
            return

        self.current = self.queue.popleft()
        logger.info(f"Popped next song from queue: {self.current.get('title')}")
        self._update_queue_metrics()
        await self._play_song(self.current)

    async def _play_song(self, song_info: Dict):
        """Play a specific song"""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.error("Not connected to voice channel")
            return

        self._is_playing = True
        self._skip_flag = False

        logger.info(f"Playing song: {song_info.get('title')} (ID: {song_info.get('id')})")

        try:
            # Get stream URL from the platform
            stream_url = song_info.get("stream_url") or await self._get_stream_url(
                song_info
            )
            logger.info(f"Got stream URL: {stream_url[:100]}...")

            # Create FFmpeg source with enhanced Discord compatibility
            ffmpeg_options = {
                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -loglevel info",
                "options": "-vn -ar 48000 -ac 2 -b:a 128k",
            }

            source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)  # type: ignore[arg-type]
            transformed_source = discord.PCMVolumeTransformer(
                source, volume=self._volume
            )

            # Play the audio
            def after_play(error):
                if self.bot:
                    self.bot.loop.create_task(self._playback_finished(error))
                else:
                    # Fallback if bot is not available
                    try:
                        asyncio.create_task(self._playback_finished(error))
                    except RuntimeError:
                        # This happens when there's no running event loop
                        pass

            self.voice_client.play(transformed_source, after=after_play)

            logger.info(f"Now playing: {song_info['title']}")

        except Exception as e:
            logger.error(f"Error playing song: {e}")
            self._is_playing = False
            await self.play_next()

    async def _get_stream_url(self, song_info: Dict) -> str:
        """Get stream URL directly from platform"""
        platform_name = song_info["platform"]
        video_id = song_info["id"]
        logger.info(f"Song info: {song_info}")
        logger.info(f"Getting stream URL for {platform_name}/{video_id}")
        
        try:
            # Get the platform from the bot's registry
            if not self.bot or not hasattr(self.bot, 'platform_registry'):
                raise Exception("Bot or platform registry not available")
            
            platform = self.bot.platform_registry.get_platform(platform_name)
            if not platform:
                raise Exception(f"Platform {platform_name} not found")
            
            # Get stream URL from platform
            stream_url = await platform.get_stream_url(video_id)
            if not stream_url:
                raise Exception(f"No stream URL returned from {platform_name}")
            
            logger.info(f"Got stream URL from {platform_name}: {stream_url[:100]}...")
            return stream_url
            
        except Exception as e:
            logger.error(f"Error getting stream URL from platform: {e}")
            raise

    async def _playback_finished(self, error):
        """Called when playback finishes"""
        logger.info(f"Playback finished callback triggered. Error: {error}")
        
        if error:
            logger.error(f"Playback error: {error}")
            logger.error(f"Error type: {type(error)}")
            logger.error(f"Current song: {self.current.get('title') if self.current else 'None'}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

        self._is_playing = False
        
        # Always reset skip flag
        skip_was_requested = self._skip_flag
        self._skip_flag = False
        
        logger.info(f"Skip flag was: {skip_was_requested}, Queue length: {len(self.queue)}")

        # Always advance to next song when playback finishes (whether by skip or natural end)
        logger.info("Attempting to play next song...")
        await self.play_next()

    def skip(self):
        """Skip the current song"""
        if self.voice_client and self.voice_client.is_playing():
            self._skip_flag = True
            self.voice_client.stop()

    def stop(self):
        """Stop playback and clear queue"""
        self.queue.clear()
        self.current = None
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        self._is_playing = False

    def pause(self) -> bool:
        """Pause playback"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            return True
        return False

    def resume(self) -> bool:
        """Resume playback"""
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            return True
        return False

    def set_volume(self, volume: int):
        """Set volume (0-100)"""
        self._volume = volume / 100
        if (
            self.voice_client
            and self.voice_client.source
            and hasattr(self.voice_client.source, "volume")
        ):
            self.voice_client.source.volume = self._volume

    def get_volume(self) -> int:
        """Get current volume (0-100)"""
        return int(self._volume * 100)

    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self._is_playing

    def get_queue(self) -> List[Dict]:
        """Get current queue"""
        return list(self.queue)

    async def cleanup(self):
        """Cleanup resources"""
        self.stop()
        self.queue.clear()
        self.current = None
        self._update_queue_metrics()
    
    def _update_queue_metrics(self):
        """Update queue size metric"""
        # Count current + queue size
        total_size = len(self.queue)
        if self.current:
            total_size += 1
        self.metrics.set_queue_size(total_size)
