#!/usr/bin/env python3
"""
Comprehensive Discord Voice Connection and Audio Test

This script tests:
1. Discord connection and voice client
2. FFmpeg installation and configuration
3. Audio source creation and playback
4. Voice channel connection and permissions
5. Audio sink and routing

Run this independently to diagnose audio issues.
"""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('voice_diagnostics.log')
    ]
)
logger = logging.getLogger(__name__)

class VoiceDiagnostics:
    """Comprehensive voice connection diagnostics"""
    
    def __init__(self):
        self.results = {}
        
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}: {details}")
        self.results[test_name] = {"success": success, "details": details}
        
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("VOICE DIAGNOSTICS SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in self.results.values() if r["success"])
        total = len(self.results)
        
        for test_name, result in self.results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{status} {test_name}")
            if result["details"] and not result["success"]:
                print(f"    Details: {result['details']}")
                
        print(f"\nTotal: {passed}/{total} tests passed")
        print("="*60)

    async def test_ffmpeg_installation(self) -> bool:
        """Test FFmpeg installation and configuration"""
        try:
            # Test FFmpeg executable
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version_info = result.stdout.split('\n')[0]
                self.log_result("FFmpeg Installation", True, f"Found: {version_info}")
                
                # Test FFmpeg with audio processing
                test_result = subprocess.run(
                    ['ffmpeg', '-f', 'lavfi', '-i', 'testsrc2=duration=1:size=320x240:rate=30', 
                     '-f', 'null', '-'],
                    capture_output=True,
                    timeout=5
                )
                
                if test_result.returncode == 0:
                    self.log_result("FFmpeg Audio Processing", True, "Can process audio")
                    return True
                else:
                    self.log_result("FFmpeg Audio Processing", False, f"Error: {test_result.stderr}")
                    return False
            else:
                self.log_result("FFmpeg Installation", False, f"Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_result("FFmpeg Installation", False, "Timeout running FFmpeg")
            return False
        except FileNotFoundError:
            self.log_result("FFmpeg Installation", False, "FFmpeg not found in PATH")
            return False
        except Exception as e:
            self.log_result("FFmpeg Installation", False, f"Exception: {e}")
            return False

    def create_test_audio_file(self) -> Optional[str]:
        """Create a test audio file for playback"""
        try:
            # Create temporary WAV file with sine wave
            temp_dir = tempfile.gettempdir()
            test_file = os.path.join(temp_dir, "discord_voice_test.wav")
            
            # Generate 5-second 440Hz tone
            result = subprocess.run([
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', 'sine=frequency=440:duration=5',
                '-ar', '48000',
                '-ac', '2',
                test_file
            ], capture_output=True, timeout=10)
            
            if result.returncode == 0 and os.path.exists(test_file):
                self.log_result("Test Audio Creation", True, f"Created: {test_file}")
                return test_file
            else:
                self.log_result("Test Audio Creation", False, f"FFmpeg error: {result.stderr}")
                return None
                
        except Exception as e:
            self.log_result("Test Audio Creation", False, f"Exception: {e}")
            return None

    async def test_discord_connection(self, token: str) -> Optional[discord.Client]:
        """Test Discord bot connection"""
        try:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.voice_states = True
            
            client = discord.Client(intents=intents)
            
            @client.event
            async def on_ready():
                logger.info(f"Connected as {client.user}")
                
            # Connect with timeout
            await asyncio.wait_for(client.login(token), timeout=10)
            await asyncio.wait_for(client.connect(), timeout=10)
            
            if client.is_ready():
                self.log_result("Discord Connection", True, f"Connected as {client.user}")
                return client
            else:
                self.log_result("Discord Connection", False, "Client not ready")
                return None
                
        except asyncio.TimeoutError:
            self.log_result("Discord Connection", False, "Connection timeout")
            return None
        except discord.LoginFailure:
            self.log_result("Discord Connection", False, "Invalid token")
            return None
        except Exception as e:
            self.log_result("Discord Connection", False, f"Exception: {e}")
            return None

    async def test_voice_connection(self, client: discord.Client, guild_id: int, channel_id: int) -> Optional[discord.VoiceClient]:
        """Test voice channel connection"""
        try:
            guild = client.get_guild(guild_id)
            if not guild:
                self.log_result("Guild Access", False, f"Guild {guild_id} not found")
                return None
                
            self.log_result("Guild Access", True, f"Found guild: {guild.name}")
            
            channel = guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                self.log_result("Voice Channel Access", False, f"Voice channel {channel_id} not found")
                return None
                
            self.log_result("Voice Channel Access", True, f"Found channel: {channel.name}")
            
            # Test permissions
            permissions = channel.permissions_for(guild.me)
            required_perms = ['connect', 'speak', 'use_voice_activation']
            missing_perms = [perm for perm in required_perms if not getattr(permissions, perm)]
            
            if missing_perms:
                self.log_result("Voice Permissions", False, f"Missing: {missing_perms}")
                return None
            else:
                self.log_result("Voice Permissions", True, "All required permissions available")
            
            # Connect to voice channel
            voice_client = await channel.connect(timeout=10)
            
            if voice_client and voice_client.is_connected():
                self.log_result("Voice Connection", True, f"Connected to {channel.name}")
                return voice_client
            else:
                self.log_result("Voice Connection", False, "Failed to establish voice connection")
                return None
                
        except asyncio.TimeoutError:
            self.log_result("Voice Connection", False, "Connection timeout")
            return None
        except Exception as e:
            self.log_result("Voice Connection", False, f"Exception: {e}")
            return None

    async def test_audio_source_creation(self, test_file: str) -> Optional[discord.AudioSource]:
        """Test Discord audio source creation"""
        try:
            # Test PCM audio source
            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn -f wav'
            }
            
            source = discord.FFmpegPCMAudio(test_file, **ffmpeg_options)
            self.log_result("Audio Source Creation", True, "FFmpegPCMAudio created successfully")
            
            # Test volume transformer
            volume_source = discord.PCMVolumeTransformer(source, volume=0.5)
            self.log_result("Volume Transformer", True, "PCMVolumeTransformer created successfully")
            
            return volume_source
            
        except Exception as e:
            self.log_result("Audio Source Creation", False, f"Exception: {e}")
            return None

    async def test_audio_playback(self, voice_client: discord.VoiceClient, audio_source: discord.AudioSource) -> bool:
        """Test actual audio playback"""
        try:
            playback_finished = asyncio.Event()
            playback_error = None
            
            def after_play(error):
                nonlocal playback_error
                playback_error = error
                playback_finished.set()
            
            # Start playback
            voice_client.play(audio_source, after=after_play)
            
            if voice_client.is_playing():
                self.log_result("Audio Playback Start", True, "Playback started successfully")
                
                # Wait for playback to finish or timeout
                try:
                    await asyncio.wait_for(playback_finished.wait(), timeout=10)
                    
                    if playback_error:
                        self.log_result("Audio Playback Completion", False, f"Playback error: {playback_error}")
                        return False
                    else:
                        self.log_result("Audio Playback Completion", True, "Playback completed successfully")
                        return True
                        
                except asyncio.TimeoutError:
                    self.log_result("Audio Playback Completion", False, "Playback timeout")
                    voice_client.stop()
                    return False
                    
            else:
                self.log_result("Audio Playback Start", False, "Failed to start playback")
                return False
                
        except Exception as e:
            self.log_result("Audio Playback", False, f"Exception: {e}")
            return False

    async def test_voice_client_status(self, voice_client: discord.VoiceClient) -> bool:
        """Test voice client status and capabilities"""
        try:
            # Test connection status
            connected = voice_client.is_connected()
            self.log_result("Voice Client Connected", connected, f"Connection status: {connected}")
            
            # Test latency
            latency = voice_client.latency
            if latency is not None:
                self.log_result("Voice Latency", True, f"Latency: {latency:.2f}ms")
            else:
                self.log_result("Voice Latency", False, "Unable to measure latency")
            
            # Test endpoint info
            endpoint = getattr(voice_client, 'endpoint', None)
            if endpoint:
                self.log_result("Voice Endpoint", True, f"Endpoint: {endpoint}")
            else:
                self.log_result("Voice Endpoint", False, "No endpoint information")
                
            return connected
            
        except Exception as e:
            self.log_result("Voice Client Status", False, f"Exception: {e}")
            return False

async def run_full_diagnostics():
    """Run complete voice diagnostics"""
    print("🎵 Discord Voice Connection Diagnostics")
    print("="*60)
    
    diagnostics = VoiceDiagnostics()
    
    # Check environment variables
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN environment variable not set!")
        print("Please set your Discord bot token:")
        print("export DISCORD_TOKEN='your-bot-token-here'")
        return
    
    guild_id = os.getenv('TEST_GUILD_ID')
    channel_id = os.getenv('TEST_VOICE_CHANNEL_ID')
    
    if not guild_id or not channel_id:
        print("❌ TEST_GUILD_ID and TEST_VOICE_CHANNEL_ID environment variables not set!")
        print("Please set your test guild and voice channel IDs:")
        print("export TEST_GUILD_ID='123456789'")
        print("export TEST_VOICE_CHANNEL_ID='987654321'")
        return
    
    try:
        guild_id = int(guild_id)
        channel_id = int(channel_id)
    except ValueError:
        print("❌ Guild ID and Channel ID must be integers!")
        return
    
    client = None
    voice_client = None
    
    try:
        # Test 1: FFmpeg installation
        await diagnostics.test_ffmpeg_installation()
        
        # Test 2: Create test audio file
        test_file = diagnostics.create_test_audio_file()
        if not test_file:
            print("❌ Cannot proceed without test audio file")
            return
        
        # Test 3: Discord connection
        client = await diagnostics.test_discord_connection(token)
        if not client:
            print("❌ Cannot proceed without Discord connection")
            return
        
        # Test 4: Voice connection
        voice_client = await diagnostics.test_voice_connection(client, guild_id, channel_id)
        if not voice_client:
            print("❌ Cannot proceed without voice connection")
            return
        
        # Test 5: Voice client status
        await diagnostics.test_voice_client_status(voice_client)
        
        # Test 6: Audio source creation
        audio_source = await diagnostics.test_audio_source_creation(test_file)
        if not audio_source:
            print("❌ Cannot proceed without audio source")
            return
        
        # Test 7: Audio playback
        await diagnostics.test_audio_playback(voice_client, audio_source)
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        
    finally:
        # Cleanup
        try:
            if voice_client:
                await voice_client.disconnect()
            if client:
                await client.close()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    # Print summary
    diagnostics.print_summary()

class DiagnosticsBot(commands.Bot):
    """Simple bot for running diagnostics commands"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix='!diag',
            intents=intents,
            description="Voice diagnostics bot"
        )
        
        self.diagnostics = VoiceDiagnostics()
    
    async def on_ready(self):
        logger.info(f"Diagnostics bot ready: {self.user}")
    
    @commands.command(name='test')
    async def test_voice(self, ctx):
        """Run voice diagnostics in Discord"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel to run diagnostics!")
            return
        
        channel = ctx.author.voice.channel
        await ctx.send(f"🎵 Running voice diagnostics in {channel.name}...")
        
        try:
            # Test FFmpeg
            ffmpeg_ok = await self.diagnostics.test_ffmpeg_installation()
            
            # Create test audio
            test_file = self.diagnostics.create_test_audio_file()
            if not test_file:
                await ctx.send("❌ Failed to create test audio file")
                return
            
            # Connect to voice
            voice_client = await channel.connect()
            await ctx.send("✅ Connected to voice channel")
            
            # Test voice client status
            await self.diagnostics.test_voice_client_status(voice_client)
            
            # Create audio source
            audio_source = await self.diagnostics.test_audio_source_creation(test_file)
            if not audio_source:
                await ctx.send("❌ Failed to create audio source")
                return
            
            await ctx.send("🎵 Playing test audio (5-second tone)...")
            
            # Test playback
            success = await self.diagnostics.test_audio_playback(voice_client, audio_source)
            
            if success:
                await ctx.send("✅ Audio test completed successfully!")
            else:
                await ctx.send("❌ Audio test failed - check logs for details")
            
            # Cleanup
            await voice_client.disconnect()
            
            # Send summary
            summary = []
            for test_name, result in self.diagnostics.results.items():
                status = "✅" if result["success"] else "❌"
                summary.append(f"{status} {test_name}")
            
            await ctx.send(f"**Diagnostics Summary:**\n```\n" + "\n".join(summary) + "\n```")
            
        except Exception as e:
            await ctx.send(f"❌ Diagnostics failed: {e}")
            logger.error(f"Diagnostics error: {e}")
            logger.error(traceback.format_exc())

async def run_interactive_bot():
    """Run interactive diagnostics bot"""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN environment variable not set!")
        return
    
    bot = DiagnosticsBot()
    
    print("🤖 Starting interactive diagnostics bot...")
    print("Use '!diagtest' command in a voice channel to run diagnostics")
    print("Press Ctrl+C to stop")
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        print("\n👋 Stopping diagnostics bot...")
        await bot.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(run_interactive_bot())
    else:
        asyncio.run(run_full_diagnostics())