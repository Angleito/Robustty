import asyncio
import logging
from collections import deque
from typing import Dict, List, Optional

import discord

from ..services.metrics_collector import get_metrics_collector
from ..utils.network_resilience import (
    with_retry,
    with_circuit_breaker,
    PLATFORM_RETRY_CONFIG,
    PLATFORM_CIRCUIT_BREAKER_CONFIG,
    NetworkResilienceError,
    CircuitBreakerOpenError,
    NetworkTimeoutError,
    MaxRetriesExceededError,
    get_resilience_manager,
)

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
        
        # Task management for proper cleanup
        self._active_tasks: set[asyncio.Task] = set()
        self._cleanup_event = asyncio.Event()
        
        self._update_queue_metrics()

    async def add_to_queue(self, song_info: Dict):
        """Add a song to the queue"""
        if self.queue.maxlen and len(self.queue) >= self.queue.maxlen:
            raise ValueError("Queue is full")
        self.queue.append(song_info)
        logger.info(f"Added to queue: {song_info['title']}")
        logger.info(
            f"Queue song info: ID={song_info.get('id')}, Platform={song_info.get('platform')}, URL={song_info.get('url')}"
        )
        self._update_queue_metrics()

    async def play_next(self):
        """Play the next song in queue"""
        logger.info(
            f"play_next called. Is playing: {self._is_playing}, Queue size: {len(self.queue)}"
        )

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
        if not self.voice_client:
            logger.error("No voice client available")
            self._is_playing = False
            return
        
        # Check if voice client is still connected
        if not self.voice_client.is_connected():
            logger.error("Voice client disconnected - attempting to handle gracefully")
            self._is_playing = False
            # Try to skip to next song if available
            if self.queue:
                logger.info("Attempting to play next song after connection loss")
                await asyncio.sleep(2)  # Brief delay before retry
                await self.play_next()
            return

        self._is_playing = True
        self._skip_flag = False

        logger.info(
            f"Playing song: {song_info.get('title')} (ID: {song_info.get('id')})"
        )

        try:
            # Get stream URL from the platform with enhanced error handling
            try:
                stream_url = song_info.get("stream_url") or await self._get_stream_url(
                    song_info
                )
                logger.info(f"Got stream URL: {stream_url[:100]}...")
            except CircuitBreakerOpenError as e:
                logger.error(f"Circuit breaker open for platform service: {e}")
                # Skip to next song if platform service is unavailable
                self._is_playing = False
                await self.play_next()
                return
            except MaxRetriesExceededError as e:
                logger.error(f"Max retries exceeded getting stream URL: {e}")
                # Skip to next song if we can't get stream URL after retries
                self._is_playing = False
                await self.play_next()
                return
            except NetworkTimeoutError as e:
                logger.error(f"Network timeout getting stream URL: {e}")
                # Skip to next song on timeout
                self._is_playing = False
                await self.play_next()
                return

            # Create FFmpeg source with enhanced Discord compatibility
            ffmpeg_options = {
                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -loglevel info",
                "options": "-vn -ar 48000 -ac 2 -b:a 128k",
            }

            try:
                source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)  # type: ignore[arg-type]
                transformed_source = discord.PCMVolumeTransformer(
                    source, volume=self._volume
                )
            except Exception as e:
                logger.error(
                    f"Error creating audio source for {song_info['title']}: {e}"
                )
                self._is_playing = False
                await self.play_next()
                return

            # Play the audio
            def after_play(error):
                if self.bot:
                    task = self.bot.loop.create_task(self._playback_finished(error))
                    self._active_tasks.add(task)
                    task.add_done_callback(self._active_tasks.discard)
                else:
                    # Fallback if bot is not available
                    try:
                        task = asyncio.create_task(self._playback_finished(error))
                        self._active_tasks.add(task)
                        task.add_done_callback(self._active_tasks.discard)
                    except RuntimeError:
                        # This happens when there's no running event loop
                        logger.warning("No event loop available for playback cleanup")
                        pass

            try:
                # Verify voice client is still connected before playing
                if not self.voice_client.is_connected():
                    logger.error("Voice client disconnected just before playback")
                    self._is_playing = False
                    await self.play_next()
                    return
                
                self.voice_client.play(transformed_source, after=after_play)
                logger.info(f"Now playing: {song_info['title']}")
            except discord.ClientException as e:
                logger.error(f"Discord client error starting playback for {song_info['title']}: {e}")
                # Handle specific Discord connection issues
                if "not connected" in str(e).lower() or "invalid" in str(e).lower():
                    logger.error("Voice connection is no longer valid")
                    self.voice_client = None  # Clear invalid voice client
                self._is_playing = False
                await self.play_next()
                return
            except Exception as e:
                logger.error(f"Error starting playback for {song_info['title']}: {e}")
                self._is_playing = False
                await self.play_next()
                return

        except Exception as e:
            logger.error(
                f"Unexpected error playing song {song_info.get('title', 'Unknown')}: {e}"
            )
            self._is_playing = False
            await self.play_next()

    @with_retry(
        retry_config=PLATFORM_RETRY_CONFIG,
        circuit_breaker_config=PLATFORM_CIRCUIT_BREAKER_CONFIG,
        service_name="platform_stream_url",
        exceptions=(Exception,),
        exclude_exceptions=(CircuitBreakerOpenError, NetworkResilienceError),
    )
    async def _get_stream_url(self, song_info: Dict) -> str:
        """Get stream URL directly from platform with enhanced error handling"""
        platform_name = song_info["platform"]
        video_id = song_info["id"]
        logger.info(f"Song info: {song_info}")
        logger.info(f"Getting stream URL for {platform_name}/{video_id}")

        try:
            # Get the platform from the bot's registry
            if not self.bot or not hasattr(self.bot, "platform_registry"):
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

        except NetworkResilienceError:
            # Re-raise network resilience errors as-is
            raise
        except Exception as e:
            logger.error(f"Error getting stream URL from platform: {e}")
            raise

    async def _playback_finished(self, error):
        """Called when playback finishes"""
        logger.info(f"Playback finished callback triggered. Error: {error}")

        if error:
            logger.error(f"Playback error: {error}")
            logger.error(f"Error type: {type(error)}")
            logger.error(
                f"Current song: {self.current.get('title') if self.current else 'None'}"
            )
            
            # Check for specific Discord voice connection errors
            error_str = str(error).lower()
            if any(keyword in error_str for keyword in ["4006", "session", "websocket", "connection closed"]):
                logger.error("Detected Discord voice connection error - may need reconnection")
                # Clear voice client reference as it's likely invalid
                self.voice_client = None
            
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

        self._is_playing = False

        # Always reset skip flag
        skip_was_requested = self._skip_flag
        self._skip_flag = False

        logger.info(
            f"Skip flag was: {skip_was_requested}, Queue length: {len(self.queue)}"
        )

        # Validate voice connection before attempting to play next
        if self.voice_client and not self.voice_client.is_connected():
            logger.warning("Voice client disconnected - clearing reference")
            self.voice_client = None

        # Always advance to next song when playback finishes (whether by skip or natural end)
        logger.info("Attempting to play next song...")
        try:
            await self.play_next()
        except Exception as e:
            logger.error(f"Error in play_next from callback: {e}")
            # Don't let callback errors crash the bot

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
    
    def is_voice_connected(self) -> bool:
        """Check if voice client is connected"""
        return self.voice_client is not None and self.voice_client.is_connected()
    
    def validate_voice_connection(self) -> tuple[bool, str]:
        """Validate voice connection status"""
        if not self.voice_client:
            return False, "No voice client available"
        
        if not self.voice_client.is_connected():
            return False, "Voice client is disconnected"
        
        return True, "Voice connection is valid"

    def get_queue(self) -> List[Dict]:
        """Get current queue"""
        return list(self.queue)

    async def cleanup(self):
        """Cleanup resources and properly close all async tasks"""
        logger.info("Starting audio player cleanup")
        
        # Set cleanup event to signal shutdown
        self._cleanup_event.set()
        
        # Stop playback first
        self.stop()
        
        # Disconnect voice client properly
        if self.voice_client:
            try:
                if self.voice_client.is_connected():
                    await self.voice_client.disconnect(force=True)
                    logger.info("Voice client disconnected")
                # Clear the voice client reference
                self.voice_client = None
            except Exception as e:
                logger.error(f"Error disconnecting voice client: {e}")
        
        # Cancel and wait for all active tasks to complete
        if self._active_tasks:
            logger.info(f"Cancelling {len(self._active_tasks)} active tasks")
            for task in self._active_tasks.copy():
                if not task.done():
                    task.cancel()
            
            # Wait for all tasks to complete or be cancelled
            if self._active_tasks:
                try:
                    await asyncio.gather(*self._active_tasks, return_exceptions=True)
                    logger.info("All audio player tasks completed")
                except Exception as e:
                    logger.error(f"Error waiting for tasks to complete: {e}")
            
            # Clear the task set
            self._active_tasks.clear()
        
        # Clear queue and current track
        self.queue.clear()
        self.current = None
        self._is_playing = False
        self._skip_flag = False
        
        # Update metrics
        self._update_queue_metrics()
        
        logger.info("Audio player cleanup completed")

    def _update_queue_metrics(self):
        """Update queue size metric"""
        # Count current + queue size
        total_size = len(self.queue)
        if self.current:
            total_size += 1
        self.metrics.set_queue_size(total_size)

    def get_network_status(self) -> Dict:
        """Get network resilience status for debugging"""
        resilience_manager = get_resilience_manager()
        return resilience_manager.get_all_status()

    def is_service_healthy(self) -> bool:
        """Check if audio player and related services are healthy"""
        try:
            resilience_manager = get_resilience_manager()
            status = resilience_manager.get_all_status()

            # Check if any circuit breakers are open
            for cb_name, cb_status in status.get("circuit_breakers", {}).items():
                if cb_status.get("state") == "open":
                    logger.warning(
                        f"Circuit breaker {cb_name} is open - service unhealthy"
                    )
                    return False

            # Check overall success rate
            global_stats = status.get("global_stats", {})
            success_rate = global_stats.get("success_rate", 0)

            # Consider service healthy if success rate > 80%
            return success_rate > 80.0

        except Exception as e:
            logger.error(f"Error checking service health: {e}")
            return False
