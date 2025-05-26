#!/usr/bin/env python3
"""
Simple Audio Test - Mimics exact audio_player.py implementation

This test replicates the exact audio setup used in your bot to identify issues.
"""

import asyncio
import logging
import os
import sys
from typing import Optional

import discord
from discord.ext import commands

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleAudioTest(commands.Bot):
    """Simple bot that mimics the exact audio implementation"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix='!test',
            intents=intents,
            description="Simple audio test bot"
        )
    
    async def on_ready(self):
        logger.info(f"Audio test bot ready: {self.user}")
        print(f"✅ Bot connected as {self.user}")
        print("Use '!testjoin' to join a voice channel")
        print("Use '!testplay' to play test audio")
        print("Use '!testleave' to leave voice channel")
    
    @commands.command(name='join')
    async def join_voice(self, ctx):
        """Join voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel!")
            return
        
        channel = ctx.author.voice.channel
        
        try:
            if not ctx.voice_client:
                voice_client = await channel.connect()
                await ctx.send(f"✅ Joined {channel.name}")
                logger.info(f"Connected to voice channel: {channel.name}")
            else:
                await ctx.send(f"✅ Already connected to {ctx.voice_client.channel.name}")
        except Exception as e:
            await ctx.send(f"❌ Failed to join: {e}")
            logger.error(f"Voice connection error: {e}")
    
    @commands.command(name='play')
    async def play_test_audio(self, ctx):
        """Play test audio using exact same setup as audio_player.py"""
        if not ctx.voice_client:
            await ctx.send("❌ Not connected to voice channel! Use `!testjoin` first.")
            return
        
        if not ctx.voice_client.is_connected():
            await ctx.send("❌ Voice client not connected!")
            return
        
        # Test with the exact same video as the bot's test command
        test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        await ctx.send("🎵 Testing audio with Rick Astley - Never Gonna Give You Up")
        await ctx.send("🔧 Using exact same FFmpeg options as audio_player.py...")
        
        try:
            # Use exact same FFmpeg options from audio_player.py
            ffmpeg_options = {
                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                "options": "-vn",
            }
            
            logger.info(f"Creating FFmpeg source with URL: {test_video_url}")
            logger.info(f"FFmpeg options: {ffmpeg_options}")
            
            # Create audio source exactly like audio_player.py
            source = discord.FFmpegPCMAudio(test_video_url, **ffmpeg_options)
            transformed_source = discord.PCMVolumeTransformer(source, volume=1.0)  # 100% volume
            
            await ctx.send("✅ Audio source created successfully")
            
            # Track playback state
            playback_finished = asyncio.Event()
            playback_error = None
            
            def after_play(error):
                nonlocal playback_error
                playback_error = error
                playback_finished.set()
                if error:
                    logger.error(f"Playback error: {error}")
                else:
                    logger.info("Playback completed successfully")
            
            # Start playback exactly like audio_player.py
            ctx.voice_client.play(transformed_source, after=after_play)
            
            if ctx.voice_client.is_playing():
                await ctx.send("✅ Audio playback started!")
                logger.info("Audio playback started successfully")
                
                # Monitor playback
                await ctx.send("⏱️ Monitoring playback... (will report status in 10 seconds)")
                
                try:
                    await asyncio.wait_for(playback_finished.wait(), timeout=10)
                    
                    if playback_error:
                        await ctx.send(f"❌ Playback failed: {playback_error}")
                        logger.error(f"Playback error: {playback_error}")
                    else:
                        await ctx.send("✅ Playback completed successfully!")
                        logger.info("Playback completed without errors")
                        
                except asyncio.TimeoutError:
                    # Still playing after 10 seconds - this is good!
                    if ctx.voice_client.is_playing():
                        await ctx.send("✅ Audio is still playing after 10 seconds - SUCCESS!")
                        logger.info("Audio confirmed playing after 10 seconds")
                    else:
                        await ctx.send("⚠️ Audio stopped playing within 10 seconds")
                        logger.warning("Audio stopped playing within 10 seconds")
                    
            else:
                await ctx.send("❌ Failed to start audio playback!")
                logger.error("Failed to start audio playback")
                
        except Exception as e:
            await ctx.send(f"❌ Audio test failed: {e}")
            logger.error(f"Audio test exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    @commands.command(name='stop')
    async def stop_audio(self, ctx):
        """Stop audio playback"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏹️ Stopped audio")
        else:
            await ctx.send("❌ Nothing is playing")
    
    @commands.command(name='status')
    async def voice_status(self, ctx):
        """Check voice client status"""
        if not ctx.voice_client:
            await ctx.send("❌ Not connected to voice")
            return
        
        status_info = []
        status_info.append(f"Connected: {ctx.voice_client.is_connected()}")
        status_info.append(f"Playing: {ctx.voice_client.is_playing()}")
        status_info.append(f"Paused: {ctx.voice_client.is_paused()}")
        
        if hasattr(ctx.voice_client, 'latency') and ctx.voice_client.latency:
            status_info.append(f"Latency: {ctx.voice_client.latency:.2f}ms")
        
        if hasattr(ctx.voice_client, 'channel'):
            status_info.append(f"Channel: {ctx.voice_client.channel.name}")
        
        await ctx.send(f"**Voice Status:**\n```\n" + "\n".join(status_info) + "\n```")
    
    @commands.command(name='leave')
    async def leave_voice(self, ctx):
        """Leave voice channel"""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Left voice channel")
        else:
            await ctx.send("❌ Not in a voice channel")

async def main():
    """Run the simple audio test bot"""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN environment variable not set!")
        print("Please set your Discord bot token:")
        print("export DISCORD_TOKEN='your-bot-token-here'")
        return
    
    bot = SimpleAudioTest()
    
    print("🎵 Simple Audio Test Bot")
    print("========================")
    print("This bot uses the exact same audio setup as your main bot.")
    print("Commands:")
    print("  !testjoin  - Join your voice channel")
    print("  !testplay  - Play test audio")
    print("  !teststop  - Stop audio")
    print("  !teststatus - Check voice status")
    print("  !testleave - Leave voice channel")
    print("\nPress Ctrl+C to stop the bot")
    print("========================")
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        print("\n👋 Stopping audio test bot...")
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())