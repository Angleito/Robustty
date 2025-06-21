#!/usr/bin/env python3
"""
Discord Bot Permissions and Configuration Checker
Checks for common issues that cause voice connection problems
"""

import asyncio
import os
import sys
import logging
from typing import List, Dict, Any

# Suppress discord.py logs for cleaner output
logging.getLogger('discord').setLevel(logging.CRITICAL)
logging.getLogger('discord.gateway').setLevel(logging.CRITICAL)
logging.getLogger('discord.voice_client').setLevel(logging.CRITICAL)

try:
    import discord
    from discord.ext import commands
except ImportError:
    print("❌ Discord.py not installed")
    sys.exit(1)

class PermissionChecker:
    def __init__(self):
        self.token = os.getenv('DISCORD_TOKEN')
        self.issues = []
        self.warnings = []
        
    async def check_bot_permissions(self):
        """Check Discord bot permissions and configuration"""
        if not self.token:
            self.issues.append("No Discord token found in environment")
            return
            
        # Set up minimal bot for testing
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
                print(f"✅ Bot logged in as {bot.user}")
                print(f"✅ Bot ID: {bot.user.id}")
                print(f"✅ Connected to {len(bot.guilds)} server(s)")
                
                # Check each guild
                for guild in bot.guilds:
                    await self.check_guild_permissions(guild)
                    
            except Exception as e:
                self.issues.append(f"Error during permission check: {e}")
            finally:
                await bot.close()
        
        try:
            await bot.start(self.token)
        except discord.LoginFailure:
            self.issues.append("Invalid Discord token")
        except Exception as e:
            self.issues.append(f"Bot connection error: {e}")
            
    async def check_guild_permissions(self, guild: discord.Guild):
        """Check permissions in a specific guild"""
        print(f"\n🔍 Checking guild: {guild.name} (ID: {guild.id})")
        
        # Check bot permissions
        bot_member = guild.me
        if not bot_member:
            self.issues.append(f"Bot not found in guild {guild.name}")
            return
            
        # Required permissions for voice functionality
        required_perms = [
            'connect',
            'speak',
            'use_voice_activation',
            'view_channel',
            'send_messages',
            'embed_links'
        ]
        
        # Check general permissions
        bot_perms = bot_member.guild_permissions
        missing_perms = []
        
        for perm in required_perms:
            if not getattr(bot_perms, perm, False):
                missing_perms.append(perm)
                
        if missing_perms:
            self.issues.append(f"Missing permissions in {guild.name}: {', '.join(missing_perms)}")
        else:
            print(f"✅ All required permissions granted in {guild.name}")
            
        # Check voice channels
        voice_channels = [ch for ch in guild.channels if isinstance(ch, discord.VoiceChannel)]
        accessible_voice = 0
        
        for vc in voice_channels:
            perms = vc.permissions_for(bot_member)
            if perms.connect and perms.speak:
                accessible_voice += 1
            else:
                self.warnings.append(f"Limited access to voice channel '{vc.name}' in {guild.name}")
                
        print(f"✅ Can access {accessible_voice}/{len(voice_channels)} voice channels")
        
        # Check for voice region issues
        if hasattr(guild, 'region') and guild.region:
            print(f"🌍 Server region: {guild.region}")
        
        # Check for verification level
        if guild.verification_level.value > 2:  # High verification
            self.warnings.append(f"High verification level in {guild.name} may cause connection issues")
            
        # Check for 2FA requirement
        if guild.mfa_level == 1:
            print("🔒 2FA required for this server")
            
    def print_results(self):
        """Print the results of the permission check"""
        print("\n" + "="*50)
        print("📋 DISCORD PERMISSIONS REPORT")
        print("="*50)
        
        if not self.issues and not self.warnings:
            print("✅ No permission issues detected!")
            print("✅ Bot should be able to connect to voice channels")
        else:
            if self.issues:
                print(f"\n❌ CRITICAL ISSUES ({len(self.issues)}):")
                for i, issue in enumerate(self.issues, 1):
                    print(f"   {i}. {issue}")
                    
            if self.warnings:
                print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
                for i, warning in enumerate(self.warnings, 1):
                    print(f"   {i}. {warning}")
                    
        print("\n💡 RECOMMENDATIONS:")
        print("   • Ensure bot has 'Connect' and 'Speak' permissions in voice channels")
        print("   • Check that voice channels aren't user-limited or restricted")
        print("   • Try using voice channels in different Discord regions")
        print("   • Verify bot has proper server permissions (not just channel)")
        print("   • Consider lowering server verification level if very high")
        
        if self.issues:
            print(f"\n🔧 Fix these {len(self.issues)} critical issues first!")
            return False
        return True

async def main():
    """Main function to run the permission checker"""
    print("🔧 Discord Bot Permission Checker")
    print("=" * 40)
    
    checker = PermissionChecker()
    
    if not checker.token:
        print("❌ DISCORD_TOKEN environment variable not set")
        print("💡 Make sure to run this from the Docker container or set the token")
        return False
        
    await checker.check_bot_permissions()
    return checker.print_results()

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Permission check cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)