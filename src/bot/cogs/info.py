import discord
from discord.ext import commands
import logging
from datetime import datetime
from ..utils.embeds import create_embed

logger = logging.getLogger(__name__)

class Info(commands.Cog):
    """Information commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()
    
    @commands.command(name='help')
    async def help(self, ctx, command_name: str = None):
        """Show help information"""
        if command_name:
            # Show specific command help
            command = self.bot.get_command(command_name)
            if not command:
                await ctx.send(f"Command `{command_name}` not found.")
                return
            
            embed = create_embed(
                title=f"Help: {command.name}",
                description=command.help or "No description available"
            )
            
            if command.aliases:
                embed.add_field(
                    name="Aliases",
                    value=", ".join(command.aliases),
                    inline=False
                )
            
            embed.add_field(
                name="Usage",
                value=f"{ctx.prefix}{command.name} {command.signature}",
                inline=False
            )
            
            await ctx.send(embed=embed)
        else:
            # Show all commands
            embed = create_embed(
                title="Robustty Commands",
                description="Here are all available commands:"
            )
            
            # Group commands by cog
            for cog_name, cog in self.bot.cogs.items():
                commands_list = [cmd.name for cmd in cog.get_commands() if not cmd.hidden]
                if commands_list:
                    embed.add_field(
                        name=cog_name,
                        value=", ".join(commands_list),
                        inline=False
                    )
            
            embed.set_footer(text=f"Use {ctx.prefix}help <command> for more info on a command")
            await ctx.send(embed=embed)
    
    @commands.command(name='ping')
    async def ping(self, ctx):
        """Check bot latency"""
        embed = create_embed(
            title="🏓 Pong!",
            description=f"Latency: {round(self.bot.latency * 1000)}ms"
        )
        await ctx.send(embed=embed)
    
    @commands.command(name='uptime')
    async def uptime(self, ctx):
        """Show bot uptime"""
        uptime = datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        embed = create_embed(
            title="Bot Uptime",
            description=f"🕐 {uptime_str}"
        )
        await ctx.send(embed=embed)
    
    @commands.command(name='about')
    async def about(self, ctx):
        """Show information about the bot"""
        embed = create_embed(
            title="About Robustty",
            description="A multi-platform Discord music bot that searches and plays audio from various video platforms."
        )
        
        embed.add_field(
            name="Features",
            value="• Multi-platform search\n• High-quality audio playback\n• Queue management\n• Volume control",
            inline=False
        )
        
        embed.add_field(
            name="Supported Platforms",
            value="YouTube, PeerTube, Odysee, Rumble",
            inline=False
        )
        
        embed.add_field(
            name="Version",
            value="1.0.0",
            inline=True
        )
        
        embed.add_field(
            name="Developer",
            value="Your Name",
            inline=True
        )
        
        embed.add_field(
            name="GitHub",
            value="[View on GitHub](https://github.com/yourusername/robustty)",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='invite')
    async def invite(self, ctx):
        """Get bot invite link"""
        permissions = discord.Permissions(
            send_messages=True,
            read_messages=True,
            add_reactions=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            connect=True,
            speak=True,
            use_voice_activation=True
        )
        
        invite_url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissions
        )
        
        embed = create_embed(
            title="Invite Robustty",
            description=f"[Click here to invite Robustty to your server]({invite_url})"
        )
        await ctx.send(embed=embed)
    
    @commands.command(name='support')
    async def support(self, ctx):
        """Get support server link"""
        embed = create_embed(
            title="Support",
            description="Need help? Join our support server!\n\n[Support Server](https://discord.gg/yoursupportserver)"
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))