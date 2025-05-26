import asyncio
import logging
from collections import deque
from typing import Dict, List, Optional

import discord

from ..services.metrics_collector import get_metrics_collector
from ..services.connection_monitor import get_stream_health_monitor

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
        self.stream_monitor = get_stream_health_monitor()
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
        """Play a specific song with retry logic and enhanced error handling"""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.error("Not connected to voice channel")
            return

        self._is_playing = True
        self._skip_flag = False
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                logger.info(f"Playing song: {song_info.get('title')} (ID: {song_info.get('id')}) - Attempt {attempt + 1}")

                # Get stream URL from the platform
                stream_url = song_info.get("stream_url") or await self._get_stream_url(song_info)
                logger.info(f"Got stream URL: {stream_url[:100]}...")

                # Check if this URL has been marked as unhealthy
                if not self.stream_monitor.is_url_healthy(stream_url):
                    logger.warning(f"Stream URL marked as unhealthy, getting fresh URL")
                    # Remove cached URL and get a fresh one
                    if "stream_url" in song_info:
                        del song_info["stream_url"]
                    stream_url = await self._get_stream_url(song_info)
                    logger.info(f"Got fresh stream URL: {stream_url[:100]}...")

                # Validate stream URL before attempting playback
                if not await self._validate_stream_url(stream_url):
                    logger.warning(f"Stream URL validation failed on attempt {attempt + 1}")
                    self.stream_monitor.mark_url_failed(stream_url)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        # Force getting a new URL on retry
                        if "stream_url" in song_info:
                            del song_info["stream_url"]
                        continue
                    else:
                        raise Exception("Stream URL validation failed after all retries")

                # Create FFmpeg source with enhanced stability for HLS streams
                ffmpeg_options = {
                    "before_options": (
                        "-reconnect 1 "
                        "-reconnect_streamed 1 "
                        "-reconnect_delay_max 5 "
                        "-reconnect_at_eof 1 "
                        "-multiple_requests 1 "
                        "-http_persistent 0 "
                        "-user_agent 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' "
                        "-headers 'Accept: */*' "
                        "-rw_timeout 30000000 "
                        "-loglevel warning"
                    ),
                    "options": "-vn -ar 48000 -ac 2 -b:a 128k -bufsize 512k -maxrate 256k",
                }

                # Ensure voice client is still connected before creating source
                if not self.voice_client or not self.voice_client.is_connected():
                    logger.error("Voice client disconnected during playback attempt")
                    raise Exception("Voice client disconnected")

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
                return  # Success, exit retry loop

            except Exception as e:
                logger.error(f"Error playing song (attempt {attempt + 1}): {e}")
                
                # Mark URL as failed if we have one
                if 'stream_url' in locals():
                    self.stream_monitor.mark_url_failed(stream_url)
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay * (2 ** attempt)} seconds...")
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    # Try to get a fresh stream URL on retry
                    if "stream_url" in song_info:
                        del song_info["stream_url"]
                else:
                    logger.error(f"Failed to play song after {max_retries} attempts")
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

    async def _validate_stream_url(self, url: str) -> bool:
        """Validate that the stream URL is accessible"""
        try:
            import aiohttp
            import asyncio
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.head(url, allow_redirects=True) as response:
                        is_valid = response.status < 400
                        
                        if not is_valid:
                            logger.warning(f"Stream URL validation failed with status {response.status}")
                        
                        return is_valid
                except asyncio.TimeoutError:
                    logger.warning("Stream URL validation timed out")
                    return True  # Assume valid on timeout to avoid blocking valid URLs
                    
        except ImportError:
            # Fallback to sync validation if aiohttp not available
            return self._validate_stream_url_sync(url)
        except Exception as e:
            logger.warning(f"Stream URL validation error: {e}")
            # Return True on validation error to avoid blocking valid URLs
            return True

    def _validate_stream_url_sync(self, url: str) -> bool:
        """Sync fallback for stream URL validation"""
        try:
            import requests
            
            response = requests.head(url, timeout=5, allow_redirects=True)
            is_valid = response.status_code < 400
            
            if not is_valid:
                logger.warning(f"Stream URL validation failed with status {response.status_code}")
            
            return is_valid
            
        except Exception as e:
            logger.warning(f"Stream URL validation error: {e}")
            return True  # Assume valid on error

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
