#!/usr/bin/env python3
"""
Test script for VPS voice connection fixes
Tests the enhanced voice connection manager with VPS-specific optimizations
"""

import asyncio
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.services.voice_connection_manager import VoiceConnectionManager, DeploymentEnvironment
import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestBot(commands.Bot):
    """Test bot for voice connection testing"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(command_prefix='!', intents=intents)
        self.voice_connection_manager = None
        
    async def setup_hook(self):
        """Initialize the voice connection manager"""
        self.voice_connection_manager = VoiceConnectionManager(self)
        logger.info(f"Voice Connection Manager initialized with environment: {self.voice_connection_manager.environment.value}")
        
    async def on_ready(self):
        logger.info(f'Bot ready as {self.user}')
        print(f"\n{'='*60}")
        print(f"VPS Voice Connection Test Bot Ready")
        print(f"{'='*60}")
        print(f"Bot: {self.user.name}")
        print(f"Environment: {self.voice_connection_manager.environment.value}")
        print(f"{'='*60}\n")

class VoiceTests(commands.Cog):
    """Voice connection test commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name='test_connect')
    async def test_connect(self, ctx):
        """Test basic voice connection"""
        if not ctx.author.voice:
            await ctx.send("❌ You must be in a voice channel to test connections!")
            return
            
        voice_channel = ctx.author.voice.channel
        voice_manager = self.bot.voice_connection_manager
        
        await ctx.send(f"🔄 Testing voice connection to **{voice_channel.name}**...")
        
        # Test connection
        start_time = datetime.now()
        voice_client, message = await voice_manager.connect_to_voice(voice_channel)
        connection_time = (datetime.now() - start_time).total_seconds()
        
        if voice_client:
            embed = discord.Embed(
                title="✅ Voice Connection Test Successful",
                color=discord.Color.green()
            )
            embed.add_field(name="Channel", value=voice_channel.name, inline=True)
            embed.add_field(name="Connection Time", value=f"{connection_time:.2f}s", inline=True)
            embed.add_field(name="Environment", value=voice_manager.environment.value, inline=True)
            
            # Get connection info
            conn_info = voice_manager.get_connection_info(ctx.guild.id)
            if 'session' in conn_info:
                embed.add_field(
                    name="Session Info",
                    value=f"ID: {conn_info['session']['id']}\nAge: {conn_info['session']['age_seconds']:.0f}s",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
            # Disconnect after a few seconds
            await asyncio.sleep(3)
            await voice_client.disconnect()
            await ctx.send("🔌 Disconnected from voice channel")
        else:
            embed = discord.Embed(
                title="❌ Voice Connection Test Failed",
                color=discord.Color.red(),
                description=message
            )
            embed.add_field(name="Environment", value=voice_manager.environment.value, inline=True)
            await ctx.send(embed=embed)
    
    @commands.command(name='test_reconnect')
    async def test_reconnect(self, ctx):
        """Test reconnection handling"""
        if not ctx.author.voice:
            await ctx.send("❌ You must be in a voice channel to test connections!")
            return
            
        voice_channel = ctx.author.voice.channel
        voice_manager = self.bot.voice_connection_manager
        
        await ctx.send("🔄 Testing reconnection handling...")
        
        # First connection
        voice_client, message = await voice_manager.connect_to_voice(voice_channel)
        if not voice_client:
            await ctx.send(f"❌ Initial connection failed: {message}")
            return
            
        await ctx.send("✅ Initial connection successful")
        
        # Simulate connection loss
        await ctx.send("💥 Simulating connection loss...")
        await voice_client.disconnect(force=True)
        await asyncio.sleep(2)
        
        # Attempt reconnection
        start_time = datetime.now()
        voice_client, message = await voice_manager.connect_to_voice(voice_channel)
        reconnect_time = (datetime.now() - start_time).total_seconds()
        
        if voice_client:
            await ctx.send(f"✅ Reconnection successful in {reconnect_time:.2f}s")
            await asyncio.sleep(2)
            await voice_client.disconnect()
        else:
            await ctx.send(f"❌ Reconnection failed: {message}")
    
    @commands.command(name='test_session')
    async def test_session(self, ctx):
        """Test session management"""
        if not ctx.author.voice:
            await ctx.send("❌ You must be in a voice channel to test connections!")
            return
            
        voice_manager = self.bot.voice_connection_manager
        guild_id = ctx.guild.id
        
        embed = discord.Embed(
            title="🔍 Session Management Test",
            color=discord.Color.blue()
        )
        
        # Check current session
        if guild_id in voice_manager.session_states:
            session = voice_manager.session_states[guild_id]
            embed.add_field(
                name="Current Session",
                value=f"ID: {session['session_id']}\n"
                      f"Created: {session['created_at'].strftime('%H:%M:%S')}\n"
                      f"Age: {(datetime.now() - session['created_at']).total_seconds():.0f}s\n"
                      f"Reconnects: {session.get('reconnect_count', 0)}",
                inline=False
            )
        else:
            embed.add_field(name="Current Session", value="None", inline=False)
        
        # Test session creation
        await voice_manager._create_new_session(guild_id)
        new_session = voice_manager.session_states[guild_id]
        
        embed.add_field(
            name="New Session Created",
            value=f"ID: {new_session['session_id']}\n"
                  f"Environment: {new_session.get('environment', 'unknown')}",
            inline=False
        )
        
        # Test session validation
        is_valid = voice_manager._is_session_valid(guild_id)
        embed.add_field(
            name="Session Validation",
            value=f"Valid: {'✅' if is_valid else '❌'}\n"
                  f"Environment: {voice_manager.environment.value}",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='test_network')
    async def test_network(self, ctx):
        """Test network stability checks"""
        voice_manager = self.bot.voice_connection_manager
        
        await ctx.send("🌐 Testing network stability checks...")
        
        # Force VPS environment for testing
        original_env = voice_manager.environment
        voice_manager.environment = DeploymentEnvironment.VPS
        
        try:
            is_stable = await voice_manager._check_network_stability()
            
            embed = discord.Embed(
                title="🌐 Network Stability Test",
                color=discord.Color.green() if is_stable else discord.Color.red()
            )
            embed.add_field(
                name="Result",
                value="✅ Network is stable" if is_stable else "❌ Network instability detected",
                inline=False
            )
            embed.add_field(name="Environment", value="VPS (forced)", inline=True)
            
            await ctx.send(embed=embed)
        finally:
            # Restore original environment
            voice_manager.environment = original_env
    
    @commands.command(name='test_cleanup')
    async def test_cleanup(self, ctx):
        """Test voice client cleanup"""
        if not ctx.author.voice:
            await ctx.send("❌ You must be in a voice channel to test cleanup!")
            return
            
        voice_channel = ctx.author.voice.channel
        voice_manager = self.bot.voice_connection_manager
        
        await ctx.send("🧹 Testing voice client cleanup...")
        
        # Create connection
        voice_client, message = await voice_manager.connect_to_voice(voice_channel)
        if not voice_client:
            await ctx.send(f"❌ Connection failed: {message}")
            return
        
        initial_clients = len(self.bot.voice_clients)
        await ctx.send(f"✅ Connected. Voice clients count: {initial_clients}")
        
        # Test cleanup
        await voice_manager._cleanup_existing_connection(ctx.guild.id, voice_client)
        
        final_clients = len(self.bot.voice_clients)
        
        embed = discord.Embed(
            title="🧹 Cleanup Test Results",
            color=discord.Color.green() if final_clients < initial_clients else discord.Color.yellow()
        )
        embed.add_field(name="Initial Clients", value=initial_clients, inline=True)
        embed.add_field(name="Final Clients", value=final_clients, inline=True)
        embed.add_field(name="Cleaned", value=initial_clients - final_clients, inline=True)
        
        # Check if guild still has voice client reference
        if ctx.guild.voice_client:
            embed.add_field(name="Guild Voice Client", value="⚠️ Still exists", inline=False)
        else:
            embed.add_field(name="Guild Voice Client", value="✅ Properly cleared", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='test_environment')
    async def test_environment(self, ctx, env: str = None):
        """Test environment detection and configuration"""
        voice_manager = self.bot.voice_connection_manager
        
        if env:
            # Test environment override
            os.environ['VOICE_ENVIRONMENT'] = env
            new_manager = VoiceConnectionManager(self.bot)
            
            embed = discord.Embed(
                title="🌍 Environment Override Test",
                color=discord.Color.blue()
            )
            embed.add_field(name="Original", value=voice_manager.environment.value, inline=True)
            embed.add_field(name="Override", value=new_manager.environment.value, inline=True)
            embed.add_field(name="VOICE_ENVIRONMENT", value=env, inline=True)
            
            # Clean up
            del os.environ['VOICE_ENVIRONMENT']
        else:
            embed = discord.Embed(
                title="🌍 Current Environment Configuration",
                color=discord.Color.blue()
            )
            embed.add_field(name="Environment", value=voice_manager.environment.value, inline=False)
            embed.add_field(name="Max Retries", value=voice_manager.max_retry_attempts, inline=True)
            embed.add_field(name="Base Delay", value=f"{voice_manager.base_retry_delay}s", inline=True)
            embed.add_field(name="Max Delay", value=f"{voice_manager.max_retry_delay}s", inline=True)
            embed.add_field(name="Connection Timeout", value=f"{voice_manager.connection_timeout}s", inline=True)
            embed.add_field(name="Session Timeout", value=f"{voice_manager.session_timeout}s", inline=True)
            embed.add_field(name="Circuit Threshold", value=voice_manager.circuit_breaker_threshold, inline=True)
            embed.add_field(name="Force Session Recreation", value=voice_manager.force_session_recreation, inline=True)
        
        await ctx.send(embed=embed)

async def main():
    """Run the test bot"""
    # Get bot token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN environment variable not set")
        sys.exit(1)
    
    # Test environment override if specified
    test_env = sys.argv[1] if len(sys.argv) > 1 else None
    if test_env:
        os.environ['VOICE_ENVIRONMENT'] = test_env
        print(f"Testing with VOICE_ENVIRONMENT={test_env}")
    
    # Create and run bot
    bot = TestBot()
    
    # Add test cog
    await bot.add_cog(VoiceTests(bot))
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        await bot.close()

if __name__ == '__main__':
    print("Starting VPS Voice Connection Test Bot...")
    print("Usage: python test_vps_voice_fixes.py [vps|local|docker]")
    print("\nAvailable test commands:")
    print("  !test_connect    - Test basic voice connection")
    print("  !test_reconnect  - Test reconnection handling")
    print("  !test_session    - Test session management")
    print("  !test_network    - Test network stability checks")
    print("  !test_cleanup    - Test voice client cleanup")
    print("  !test_environment [env] - Test environment detection")
    print("\nPress Ctrl+C to stop\n")
    
    asyncio.run(main())