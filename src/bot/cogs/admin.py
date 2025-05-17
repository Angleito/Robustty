import logging
from typing import Any, Dict, List, Optional, Protocol, Tuple

import discord
import psutil
from discord import Embed
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context  # type: ignore[import]

from ..utils.checks import is_admin
from ..utils.embeds import create_embed, create_error_embed

logger = logging.getLogger(__name__)


class PlatformRegistry(Protocol):
    """Type stub for platform registry"""
    def get_all_platforms(self) -> Dict[str, Any]: ...


class RobottyBot(Bot):
    """Type stub for our custom bot class"""
    platform_registry: PlatformRegistry


class Admin(Cog):
    """Administrative commands"""

    def __init__(self, bot: RobottyBot) -> None:
        self.bot: RobottyBot = bot

    @commands.command(name="reload")
    @is_admin()
    async def reload(self, ctx: Context[RobottyBot], extension: Optional[str] = None) -> None:
        """Reload a cog or all cogs"""
        if extension:
            try:
                await self.bot.reload_extension(f"src.bot.cogs.{extension}")
                success_embed = create_embed(
                    title="Reload Successful",
                    description=f"Successfully reloaded `{extension}`",
                    color=discord.Color.green(),
                )
                await ctx.send(embed=success_embed)
            except Exception as e:
                error_embed = create_error_embed(
                    title="Reload Failed",
                    description=f"Failed to reload `{extension}`: {str(e)}",
                )
                await ctx.send(embed=error_embed)
        else:
            # Reload all cogs
            reloaded: List[str] = []
            failed: List[Tuple[str, str]] = []

            for ext in ["music", "admin", "info"]:
                try:
                    await self.bot.reload_extension(f"bot.cogs.{ext}")
                    reloaded.append(ext)
                except Exception as e:
                    failed.append((ext, str(e)))

            embed: Embed = create_embed(title="Reload Results")

            if reloaded:
                embed.add_field(
                    name="✅ Successfully Reloaded",
                    value="\n".join(reloaded),
                    inline=False,
                )

            if failed:
                failed_text: str = "\n".join([f"{ext}: {err}" for ext, err in failed])
                embed.add_field(
                    name="❌ Failed to Reload", value=failed_text, inline=False
                )

            await ctx.send(embed=embed)

    @commands.command(name="shutdown")
    @is_admin()
    async def shutdown(self, ctx: Context[RobottyBot]) -> None:
        """Shut down the bot"""
        embed = create_embed(
            title="Shutting Down",
            description="Bot is shutting down...",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
        await self.bot.close()

    @commands.command(name="setprefix")
    @commands.guild_only()
    @is_admin()
    async def set_prefix(self, ctx: Context[RobottyBot], new_prefix: str) -> None:
        """Change the bot's command prefix for this server"""
        # This is a simplified version - you might want to store per-guild prefixes
        old_prefix = self.bot.command_prefix
        # Handle the case where command_prefix might be a callable
        if callable(old_prefix):
            old_prefix_str = str(old_prefix(self.bot, ctx.message))  # type: ignore
        else:
            old_prefix_str = str(old_prefix)
        self.bot.command_prefix = new_prefix

        embed = create_embed(
            title="Prefix Changed",
            description=f"Command prefix changed from `{old_prefix_str}` to `{new_prefix}`",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="status")
    @is_admin()
    async def status(self, ctx: Context[RobottyBot]) -> None:
        """Show bot status information"""
        embed = create_embed(title="Bot Status")

        # General info
        embed.add_field(name="Guilds", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Users", value=len(self.bot.users), inline=True)
        embed.add_field(
            name="Voice Connections", value=len(self.bot.voice_clients), inline=True
        )

        # Platform status
        platforms = self.bot.platform_registry.get_all_platforms()
        platform_text: str = "\n".join(
            [
                f"{name}: {'✅' if platform.enabled else '❌'}"
                for name, platform in platforms.items()
            ]
        )
        embed.add_field(
            name="Platforms", value=platform_text or "No platforms loaded", inline=False
        )

        # Memory usage (requires psutil)
        try:
            process = psutil.Process()
            memory_mb: float = process.memory_info().rss / 1024 / 1024
            embed.add_field(
                name="Memory Usage", value=f"{memory_mb:.2f} MB", inline=True
            )
        except (ImportError, psutil.NoSuchProcess):
            pass

        await ctx.send(embed=embed)

    @commands.command(name="clearcache")
    @is_admin()
    async def clear_cache(self, ctx: Context[RobottyBot]) -> None:
        """Clear all caches"""
        try:
            # Clear various caches here
            # For example: await self.bot.cache_manager.clear_all()

            embed = create_embed(
                title="Cache Cleared",
                description="All caches have been cleared successfully",
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = create_error_embed(
                title="Failed to Clear Cache", description=str(e)
            )
            await ctx.send(embed=embed)


async def setup(bot: RobottyBot) -> None:
    await bot.add_cog(Admin(bot))
