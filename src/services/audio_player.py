import discord
import asyncio
import logging
from typing import Optional, List, Dict
from collections import deque

logger = logging.getLogger(__name__)

class AudioPlayer:
    """Manages audio playback for a guild"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.queue = deque(maxlen=config.get('max_queue_size', 100))
        self.current: Optional[Dict] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self._volume = 0.5  # Default 50% volume
        self._is_playing = False
        self._skip_flag = False
    
    async def add_to_queue(self, song_info: Dict):
        """Add a song to the queue"""
        if len(self.queue) >= self.queue.maxlen:
            raise ValueError("Queue is full")
        self.queue.append(song_info)
        logger.info(f"Added to queue: {song_info['title']}")
    
    async def play_next(self):
        """Play the next song in queue"""
        if self._is_playing:
            return
        
        if not self.queue and not self.current:
            return
        
        if not self.queue:
            self.current = None
            self._is_playing = False
            return
        
        self.current = self.queue.popleft()
        await self._play_song(self.current)
    
    async def _play_song(self, song_info: Dict):
        """Play a specific song"""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.error("Not connected to voice channel")
            return
        
        self._is_playing = True
        self._skip_flag = False
        
        try:
            # Get stream URL from the platform
            stream_url = song_info.get('stream_url') or await self._get_stream_url(song_info)
            
            # Create FFmpeg source
            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn'
            }
            
            source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)
            source = discord.PCMVolumeTransformer(source, volume=self._volume)
            
            # Play the audio
            self.voice_client.play(
                source,
                after=lambda e: asyncio.create_task(self._playback_finished(e))
            )
            
            logger.info(f"Now playing: {song_info['title']}")
            
        except Exception as e:
            logger.error(f"Error playing song: {e}")
            self._is_playing = False
            await self.play_next()
    
    async def _get_stream_url(self, song_info: Dict) -> str:
        """Get stream URL from stream service"""
        # This would call the stream extraction service
        platform = song_info['platform']
        video_id = song_info['id']
        return f"http://stream-service:5000/stream/{platform}/{video_id}"
    
    async def _playback_finished(self, error):
        """Called when playback finishes"""
        if error:
            logger.error(f"Playback error: {error}")
        
        self._is_playing = False
        
        if not self._skip_flag:
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
        if self.voice_client and hasattr(self.voice_client.source, 'volume'):
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