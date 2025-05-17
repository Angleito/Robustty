#!/usr/bin/env python3
"""Test the queue system to ensure skip functionality works correctly"""

import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from src.services.audio_player import AudioPlayer

class TestQueueSystem(unittest.TestCase):
    def setUp(self):
        self.config = {"max_queue_size": 100}
        self.player = AudioPlayer(self.config)
        self.player.voice_client = Mock()
        self.player.bot = Mock()
        self.player.bot.loop = Mock()
        
        # Mock voice client
        self.player.voice_client.is_connected = Mock(return_value=True)
        self.player.voice_client.is_playing = Mock(return_value=True)
        self.player.voice_client.stop = Mock()
        
        # Use mock audio source
        self.player.voice_client.play = Mock()
        
    async def test_skip_advances_queue(self):
        """Test that skip properly advances to the next song in queue"""
        # Add songs to queue
        song1 = {"id": "test1", "title": "Song 1", "platform": "youtube", "url": "http://test1"}
        song2 = {"id": "test2", "title": "Song 2", "platform": "youtube", "url": "http://test2"}
        
        await self.player.add_to_queue(song1)
        await self.player.add_to_queue(song2)
        
        # Start playing first song
        self.player._is_playing = False
        await self.player.play_next()
        
        # Verify first song is playing
        self.assertEqual(self.player.current["title"], "Song 1")
        self.assertEqual(len(self.player.queue), 1)
        
        # Now skip the current song
        self.player.skip()
        
        # Simulate ffmpeg process ending (what happens when stop() is called)
        # Get the callback that was registered
        play_call = self.player.voice_client.play.call_args
        after_callback = play_call[1]['after']
        
        # Simulate playback finished
        self.player._is_playing = False
        await self.player._playback_finished(None)
        
        # Verify that the queue advanced
        self.assertEqual(self.player.current["title"], "Song 2")
        self.assertEqual(len(self.player.queue), 0)
        
        print("Test passed: Skip properly advances queue")

async def main():
    """Run the test"""
    test = TestQueueSystem()
    test.setUp()
    
    # Mock the stream URL fetching
    test.player._get_stream_url = AsyncMock(return_value="http://stream.url")
    
    # Run the test
    await test.test_skip_advances_queue()
    
    print("\nAll tests passed! The queue system should properly advance after skip.")

if __name__ == "__main__":
    asyncio.run(main())