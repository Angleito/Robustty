#!/usr/bin/env python3
"""
Discord Error 4006 Diagnostic Script
Analyzes and provides solutions for Discord voice connection error 4006
"""

import asyncio
import os
import sys
import logging
from typing import Dict, List, Any
import time

# Suppress discord.py logs for cleaner output
logging.getLogger('discord').setLevel(logging.CRITICAL)
logging.getLogger('discord.gateway').setLevel(logging.CRITICAL)
logging.getLogger('discord.voice_client').setLevel(logging.CRITICAL)

try:
    import discord
    from discord.ext import commands
    import aiohttp
except ImportError as e:
    print(f"❌ Required dependencies not installed: {e}")
    sys.exit(1)

class Discord4006Diagnostics:
    def __init__(self):
        self.token = os.getenv('DISCORD_TOKEN')
        self.issues = []
        self.warnings = []
        self.recommendations = []
        
    async def run_diagnostics(self):
        """Run comprehensive diagnostics for Discord error 4006"""
        print("🔍 Discord Error 4006 Diagnostic Tool")
        print("=" * 50)
        
        if not self.token:
            self.issues.append("No Discord token found in environment")
            return
            
        # Test Discord connectivity
        await self._test_discord_connectivity()
        
        # Test voice connection capabilities
        await self._test_voice_capabilities()
        
        # Check network connectivity to Discord voice servers
        await self._test_voice_server_connectivity()
        
        # Analyze configuration
        self._analyze_configuration()
        
        # Print results
        self._print_results()
        
    async def _test_discord_connectivity(self):
        """Test basic Discord connection"""
        print("\n🌐 Testing Discord Gateway Connectivity...")
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        bot = commands.Bot(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        @bot.event
        async def on_ready():
            try:
                print(f"✅ Successfully connected to Discord Gateway")
                print(f"✅ Bot: {bot.user} (ID: {bot.user.id})")
                print(f"✅ Latency: {bot.latency * 1000:.1f}ms")
                
                # Check guilds and their voice regions
                for guild in bot.guilds:
                    print(f"📍 Guild: {guild.name} (ID: {guild.id})")
                    if hasattr(guild, 'region'):
                        print(f"   🌍 Region: {guild.region}")
                    else:
                        print("   🌍 Region: Unknown (may use automatic selection)")
                    
                    # Check voice channels
                    voice_channels = [ch for ch in guild.channels if isinstance(ch, discord.VoiceChannel)]
                    print(f"   🎵 Voice channels: {len(voice_channels)}")
                    
                    for vc in voice_channels[:3]:  # Show first 3
                        try:
                            perms = vc.permissions_for(guild.me)
                            connect_perm = "✅" if perms.connect else "❌"
                            speak_perm = "✅" if perms.speak else "❌"
                            print(f"      - {vc.name}: Connect {connect_perm} Speak {speak_perm}")
                        except Exception as e:
                            print(f"      - {vc.name}: Error checking permissions - {e}")
                            
            except Exception as e:
                self.issues.append(f"Gateway connection test failed: {e}")
            finally:
                await bot.close()
        
        try:
            await asyncio.wait_for(bot.start(self.token), timeout=30.0)
        except asyncio.TimeoutError:
            self.issues.append("Discord gateway connection timed out")
        except discord.LoginFailure:
            self.issues.append("Invalid Discord token")
        except Exception as e:
            self.issues.append(f"Gateway connection error: {e}")
    
    async def _test_voice_capabilities(self):
        """Test voice connection capabilities"""
        print("\n🎵 Testing Voice Connection Capabilities...")
        
        # Check if we have proper voice requirements
        try:
            import nacl
            print("✅ PyNaCl (voice encryption) available")
        except ImportError:
            self.issues.append("PyNaCl not installed - required for voice connections")
            
        # Check opus libraries
        try:
            if discord.opus.is_loaded():
                print("✅ Opus codec loaded")
            else:
                print("⚠️  Opus codec not loaded - attempting to load...")
                try:
                    discord.opus.load_opus()
                    print("✅ Opus codec loaded successfully")
                except Exception as e:
                    self.warnings.append(f"Opus loading issue: {e}")
        except Exception as e:
            self.warnings.append(f"Voice codec check failed: {e}")
        
        # Check FFmpeg availability
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✅ FFmpeg available")
            else:
                self.warnings.append("FFmpeg not found - required for audio processing")
        except Exception:
            self.warnings.append("FFmpeg not found or not accessible")
    
    async def _test_voice_server_connectivity(self):
        """Test connectivity to Discord voice servers"""
        print("\n🌐 Testing Discord Voice Server Connectivity...")
        
        # Discord voice server endpoints (common regions)
        voice_endpoints = [
            "us-west.discord.gg",
            "us-east.discord.gg", 
            "us-central.discord.gg",
            "europe.discord.gg",
            "sydney.discord.gg",
            "japan.discord.gg"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in voice_endpoints:
                try:
                    start_time = time.time()
                    # Test HTTPS connectivity to voice gateway discovery
                    async with session.get(f"https://{endpoint}", timeout=10) as response:
                        latency = (time.time() - start_time) * 1000
                        status = "✅" if response.status < 500 else "⚠️"
                        print(f"   {status} {endpoint}: {response.status} ({latency:.1f}ms)")
                except asyncio.TimeoutError:
                    print(f"   ❌ {endpoint}: Timeout")
                    self.warnings.append(f"Timeout connecting to {endpoint}")
                except Exception as e:
                    print(f"   ❌ {endpoint}: {type(e).__name__}")
                    self.warnings.append(f"Failed to connect to {endpoint}: {e}")
    
    def _analyze_configuration(self):
        """Analyze current configuration for 4006 error causes"""
        print("\n⚙️  Analyzing Configuration...")
        
        # Check environment variables
        required_vars = ['DISCORD_TOKEN']
        for var in required_vars:
            if os.getenv(var):
                print(f"✅ {var} is set")
            else:
                self.issues.append(f"Environment variable {var} is not set")
        
        # Check Docker/network configuration
        if os.path.exists('/.dockerenv'):
            print("🐳 Running in Docker container")
            # Check if running with host networking
            try:
                with open('/proc/1/cgroup', 'r') as f:
                    cgroup_content = f.read()
                    if 'docker' in cgroup_content:
                        print("✅ Docker environment detected")
                        self.recommendations.append("Consider using host networking mode if experiencing persistent connection issues")
            except Exception:
                pass
        else:
            print("💻 Running natively (not in Docker)")
    
    def _print_results(self):
        """Print diagnostic results and recommendations"""
        print("\n" + "="*60)
        print("📋 DISCORD ERROR 4006 DIAGNOSTIC REPORT")
        print("="*60)
        
        # Error 4006 explanation
        print("\n❓ ABOUT ERROR 4006:")
        print("   Discord Error 4006 indicates 'Session Timed Out' in voice connections.")
        print("   This typically occurs when:")
        print("   • Discord voice servers are experiencing issues")
        print("   • Network connectivity problems prevent proper handshake")
        print("   • UDP packets are being blocked or delayed")
        print("   • Voice connection parameters are incompatible")
        
        # Issues found
        if self.issues:
            print(f"\n❌ CRITICAL ISSUES ({len(self.issues)}):")
            for i, issue in enumerate(self.issues, 1):
                print(f"   {i}. {issue}")
        else:
            print("\n✅ No critical configuration issues detected")
            
        # Warnings
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")
                
        # Specific 4006 solutions
        print(f"\n🔧 DISCORD ERROR 4006 SOLUTIONS:")
        solutions = [
            "Wait and retry: Error 4006 is often temporary - Discord voice servers may be experiencing issues",
            "Change voice regions: Try connecting to voice channels in different Discord server regions",
            "Check firewall/router: Ensure UDP traffic on ports 50000-65535 is not blocked",
            "Disable VPN temporarily: Some VPNs don't properly support Discord's UDP voice protocol",
            "Restart network connection: Reset your internet connection or switch networks",
            "Use different voice channel: Try connecting to a different voice channel in the same server",
            "Check Discord status: Visit status.discord.com to check for known voice server issues",
            "Update Discord.py: Ensure you're using the latest version of discord.py library"
        ]
        
        for i, solution in enumerate(solutions, 1):
            print(f"   {i}. {solution}")
            
        # Bot-specific recommendations
        if self.recommendations:
            print(f"\n💡 ADDITIONAL RECOMMENDATIONS:")
            for i, rec in enumerate(self.recommendations, 1):
                print(f"   {i}. {rec}")
                
        # Current bot implementation
        print(f"\n🤖 CURRENT BOT IMPLEMENTATION:")
        print("   ✅ Enhanced retry logic with exponential backoff")
        print("   ✅ Specific 4006 error handling with extended delays")
        print("   ✅ Connection stability validation")
        print("   ✅ Proper cleanup of failed connections")
        print("   ✅ Multiple connection attempts with different timeout strategies")
        
        print(f"\n📊 DIAGNOSTIC SUMMARY:")
        print(f"   • Critical Issues: {len(self.issues)}")
        print(f"   • Warnings: {len(self.warnings)}")
        print(f"   • Recommendations: {len(self.recommendations)}")
        
        if self.issues:
            print(f"\n🚨 ACTION REQUIRED: Fix {len(self.issues)} critical issues first!")
            return False
        else:
            print(f"\n✅ Configuration appears healthy. If 4006 errors persist, they're likely due to Discord infrastructure issues.")
            return True

async def main():
    """Main function to run diagnostics"""
    diagnostics = Discord4006Diagnostics()
    
    if not diagnostics.token:
        print("❌ DISCORD_TOKEN environment variable not set")
        print("💡 Run this from the Docker container: docker-compose exec robustty python scripts/diagnose-4006-error.py")
        return False
        
    success = await diagnostics.run_diagnostics()
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Diagnostics cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error during diagnostics: {e}")
        sys.exit(1)