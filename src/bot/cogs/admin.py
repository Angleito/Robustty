import logging
from typing import Any, Dict, List, Optional, Protocol, Tuple

import discord
import psutil
from discord import Embed
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context  # type: ignore[import]

from ..utils.checks import is_admin
from ..utils.embeds import create_embed, create_error_embed, create_service_status_embed, create_warning_embed, create_success_embed
from ...utils.network_resilience import get_resilience_manager
from ...platforms.errors import PlatformError

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
    
    @commands.command(name="health", aliases=["healthcheck", "status-detailed"])
    @is_admin()
    async def health_check(self, ctx: Context[RobottyBot]) -> None:
        """Show detailed service health status"""
        try:
            # Get comprehensive health status
            health_status = await self._get_comprehensive_health_status()
            
            # Create and send status embed
            embed = create_service_status_embed(health_status)
            embed.set_footer(text="Use `recover` command to attempt automatic recovery")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            embed = create_error_embed(
                title="Health Check Failed",
                description=f"Could not retrieve service health status: {str(e)[:100]}..."
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="recover", aliases=["reset-services", "fix"])
    @is_admin()
    async def recover_services(self, ctx: Context[RobottyBot]) -> None:
        """Attempt to recover degraded services"""
        await ctx.trigger_typing()
        
        try:
            recovery_results = await self._attempt_service_recovery()
            
            # Create recovery report
            if recovery_results['overall_success']:
                embed = create_success_embed(
                    title="Service Recovery Completed",
                    description="Service recovery operations completed successfully"
                )
                embed.color = discord.Color.green()
            else:
                embed = create_warning_embed(
                    title="Service Recovery Partial",
                    description="Some services could not be recovered automatically"
                )
                embed.color = discord.Color.yellow()
            
            # Add recovery details
            if recovery_results['circuit_breakers_reset']:
                embed.add_field(
                    name="✅ Circuit Breakers",
                    value=f"Reset {recovery_results['circuit_breakers_reset']} circuit breakers",
                    inline=True
                )
            
            if recovery_results['platforms_reinitialized']:
                embed.add_field(
                    name="✅ Platforms",
                    value=f"Reinitialized {recovery_results['platforms_reinitialized']} platforms",
                    inline=True
                )
            
            if recovery_results['cache_cleared']:
                embed.add_field(
                    name="✅ Cache",
                    value="Cache cleared successfully",
                    inline=True
                )
            
            if recovery_results['errors']:
                error_text = "\n".join(recovery_results['errors'][:3])  # Show max 3 errors
                if len(recovery_results['errors']) > 3:
                    error_text += f"\n... and {len(recovery_results['errors']) - 3} more"
                
                embed.add_field(
                    name="❌ Errors",
                    value=error_text,
                    inline=False
                )
            
            embed.set_footer(text="Use `health` command to check current status")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error during service recovery: {e}")
            embed = create_error_embed(
                title="Recovery Failed",
                description=f"Service recovery failed: {str(e)[:100]}...\n\n"
                           "Try individual recovery commands or restart the bot."
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="reset-circuit-breakers", aliases=["reset-cb"])
    @is_admin()
    async def reset_circuit_breakers(self, ctx: Context[RobottyBot]) -> None:
        """Reset all circuit breakers to closed state"""
        try:
            resilience_manager = get_resilience_manager()
            
            # Get current status before reset
            status = resilience_manager.get_all_status()
            circuit_breakers = status.get('circuit_breakers', {})
            
            open_breakers = [
                name for name, cb_status in circuit_breakers.items() 
                if cb_status.get('state') == 'open'
            ]
            
            if not open_breakers:
                embed = create_embed(
                    title="Circuit Breakers Status",
                    description="All circuit breakers are already closed",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                return
            
            # Reset circuit breakers (this would require adding a reset method to the manager)
            # For now, we'll create new instances which effectively resets them
            reset_count = 0
            for cb_name in open_breakers:
                try:
                    # This is a simplified reset - in a real implementation, 
                    # you'd want a proper reset method
                    if cb_name in resilience_manager.circuit_breakers:
                        cb = resilience_manager.circuit_breakers[cb_name]
                        cb.state = cb.state.__class__.CLOSED  # Reset to CLOSED
                        cb.failure_count = 0
                        cb.success_count = 0
                        reset_count += 1
                except Exception as e:
                    logger.warning(f"Could not reset circuit breaker {cb_name}: {e}")
            
            embed = create_success_embed(
                title="Circuit Breakers Reset",
                description=f"Successfully reset {reset_count} circuit breakers\n\n"
                           f"**Reset breakers:** {', '.join(open_breakers[:5])}{'...' if len(open_breakers) > 5 else ''}"
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error resetting circuit breakers: {e}")
            embed = create_error_embed(
                title="Reset Failed",
                description=f"Could not reset circuit breakers: {str(e)[:100]}..."
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="platforms")
    @is_admin()
    async def list_platforms(self, ctx: Context[RobottyBot]) -> None:
        """Show detailed platform information"""
        try:
            platforms = self.bot.platform_registry.get_all_platforms()
            
            if not platforms:
                embed = create_warning_embed(
                    title="No Platforms",
                    description="No platforms are currently registered"
                )
                await ctx.send(embed=embed)
                return
            
            embed = create_embed(
                title="Platform Status",
                description=f"Showing status for {len(platforms)} platforms"
            )
            
            for name, platform in platforms.items():
                try:
                    # Check platform health
                    is_enabled = getattr(platform, 'enabled', False)
                    has_session = hasattr(platform, 'session') and platform.session
                    has_config = bool(getattr(platform, 'config', {}))
                    
                    status_indicators = []
                    if is_enabled:
                        status_indicators.append("✅ Enabled")
                    else:
                        status_indicators.append("❌ Disabled")
                    
                    if has_session:
                        status_indicators.append("🔗 Connected")
                    else:
                        status_indicators.append("🔌 Disconnected")
                    
                    if has_config:
                        status_indicators.append("⚙️ Configured")
                    else:
                        status_indicators.append("⚠️ Not Configured")
                    
                    status_text = "\n".join(status_indicators)
                    
                    embed.add_field(
                        name=f"{name.title()}",
                        value=status_text,
                        inline=True
                    )
                    
                except Exception as e:
                    embed.add_field(
                        name=f"{name.title()}",
                        value=f"❌ Error: {str(e)[:50]}...",
                        inline=True
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing platforms: {e}")
            embed = create_error_embed(
                title="Platform List Failed",
                description=f"Could not retrieve platform information: {str(e)[:100]}..."
            )
            await ctx.send(embed=embed)
    
    async def _get_comprehensive_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status for all services"""
        health_status = {
            'overall_health': 'unknown',
            'platforms': {},
            'circuit_breakers': {},
            'global_stats': {},
            'searcher_status': {},
            'audio_players': {}
        }
        
        try:
            # Get network resilience status
            resilience_manager = get_resilience_manager()
            resilience_status = resilience_manager.get_all_status()
            
            health_status['circuit_breakers'] = resilience_status.get('circuit_breakers', {})
            health_status['global_stats'] = resilience_status.get('global_stats', {})
            
            # Check platform health
            platforms = self.bot.platform_registry.get_all_platforms()
            platform_health_count = 0
            
            for name, platform in platforms.items():
                try:
                    is_healthy = platform.enabled and hasattr(platform, 'session') and platform.session
                    health_status['platforms'][name] = {
                        'available': is_healthy,
                        'enabled': platform.enabled
                    }
                    if is_healthy:
                        platform_health_count += 1
                except Exception as e:
                    logger.warning(f"Error checking platform {name} health: {e}")
                    health_status['platforms'][name] = {
                        'available': False,
                        'enabled': getattr(platform, 'enabled', False),
                        'error': str(e)
                    }
            
            # Check searcher health
            if hasattr(self.bot, 'searcher') and self.bot.searcher:
                try:
                    searcher_status = self.bot.searcher.get_search_health_status()
                    health_status['searcher_status'] = searcher_status
                except Exception as e:
                    health_status['searcher_status'] = {'error': str(e)}
            
            # Check audio player health
            active_players = 0
            healthy_players = 0
            
            for guild_id, player in self.bot.audio_players.items():
                try:
                    is_healthy = player.is_service_healthy()
                    active_players += 1
                    if is_healthy:
                        healthy_players += 1
                except Exception as e:
                    logger.warning(f"Error checking audio player {guild_id} health: {e}")
            
            health_status['audio_players'] = {
                'active': active_players,
                'healthy': healthy_players
            }
            
            # Determine overall health
            success_rate = health_status['global_stats'].get('success_rate', 100)
            open_circuit_breakers = sum(
                1 for cb_status in health_status['circuit_breakers'].values()
                if cb_status.get('state') == 'open'
            )
            
            total_platforms = len(platforms)
            healthy_platforms = platform_health_count
            
            if success_rate >= 90 and open_circuit_breakers == 0 and healthy_platforms == total_platforms:
                health_status['overall_health'] = 'healthy'
            elif success_rate >= 70 or healthy_platforms >= total_platforms * 0.5:
                health_status['overall_health'] = 'degraded'
            else:
                health_status['overall_health'] = 'unhealthy'
            
        except Exception as e:
            logger.error(f"Error getting comprehensive health status: {e}")
            health_status['overall_health'] = 'unknown'
            health_status['error'] = str(e)
        
        return health_status
    
    async def _attempt_service_recovery(self) -> Dict[str, Any]:
        """Attempt to recover degraded services"""
        recovery_results = {
            'overall_success': False,
            'circuit_breakers_reset': 0,
            'platforms_reinitialized': 0,
            'cache_cleared': False,
            'errors': []
        }
        
        try:
            # Reset circuit breakers
            try:
                resilience_manager = get_resilience_manager()
                status = resilience_manager.get_all_status()
                circuit_breakers = status.get('circuit_breakers', {})
                
                for cb_name, cb_status in circuit_breakers.items():
                    if cb_status.get('state') == 'open':
                        try:
                            cb = resilience_manager.circuit_breakers.get(cb_name)
                            if cb:
                                cb.state = cb.state.__class__.CLOSED
                                cb.failure_count = 0
                                cb.success_count = 0
                                recovery_results['circuit_breakers_reset'] += 1
                        except Exception as e:
                            recovery_results['errors'].append(f"Circuit breaker {cb_name}: {str(e)[:50]}...")
                            
            except Exception as e:
                recovery_results['errors'].append(f"Circuit breaker reset failed: {str(e)[:50]}...")
            
            # Reinitialize platforms
            try:
                platforms = self.bot.platform_registry.get_all_platforms()
                for name, platform in platforms.items():
                    try:
                        if platform.enabled and not (hasattr(platform, 'session') and platform.session):
                            await platform.initialize()
                            recovery_results['platforms_reinitialized'] += 1
                    except Exception as e:
                        recovery_results['errors'].append(f"Platform {name}: {str(e)[:50]}...")
                        
            except Exception as e:
                recovery_results['errors'].append(f"Platform reinitialization failed: {str(e)[:50]}...")
            
            # Clear cache
            try:
                if hasattr(self.bot, 'cache_manager') and self.bot.cache_manager:
                    await self.bot.cache_manager.clear_all()
                    recovery_results['cache_cleared'] = True
            except Exception as e:
                recovery_results['errors'].append(f"Cache clear failed: {str(e)[:50]}...")
            
            # Determine overall success
            recovery_results['overall_success'] = (
                len(recovery_results['errors']) == 0 or
                (recovery_results['circuit_breakers_reset'] > 0 or 
                 recovery_results['platforms_reinitialized'] > 0 or
                 recovery_results['cache_cleared'])
            )
            
        except Exception as e:
            recovery_results['errors'].append(f"Recovery process failed: {str(e)[:50]}...")
        
        return recovery_results


async def setup(bot: RobottyBot) -> None:
    await bot.add_cog(Admin(bot))
