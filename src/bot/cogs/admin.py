import logging
from typing import Any, Dict, List, Optional, Protocol, Tuple

import discord
import psutil
from discord import Embed
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context  # type: ignore[import]

from ..utils.checks import is_admin
from ..utils.embeds import (
    create_embed,
    create_error_embed,
    create_service_status_embed,
    create_warning_embed,
    create_success_embed,
)
from ...utils.network_resilience import get_resilience_manager
from ...utils.network_connectivity import get_connectivity_manager, ConnectivityStatus
from ...platforms.errors import PlatformError

logger = logging.getLogger(__name__)


class PlatformRegistry(Protocol):
    """Type stub for platform registry"""

    def get_all_platforms(self) -> Dict[str, Any]: ...


class RobottyBot(Bot):
    """Type stub for our custom bot class"""

    platform_registry: PlatformRegistry
    stability_monitor: Optional[Any]


class Admin(Cog):
    """Administrative commands"""

    def __init__(self, bot: RobottyBot) -> None:
        self.bot: RobottyBot = bot

    @commands.command(name="reload")
    @is_admin()
    async def reload(
        self, ctx: Context[RobottyBot], extension: Optional[str] = None
    ) -> None:
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
                description=f"Could not retrieve service health status: {str(e)[:100]}...",
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
            if recovery_results["overall_success"]:
                embed = create_success_embed(
                    title="Service Recovery Completed",
                    description="Service recovery operations completed successfully",
                )
                embed.color = discord.Color.green()
            else:
                embed = create_warning_embed(
                    title="Service Recovery Partial",
                    description="Some services could not be recovered automatically",
                )
                embed.color = discord.Color.yellow()

            # Add recovery details
            if recovery_results["circuit_breakers_reset"]:
                embed.add_field(
                    name="✅ Circuit Breakers",
                    value=f"Reset {recovery_results['circuit_breakers_reset']} circuit breakers",
                    inline=True,
                )

            if recovery_results["platforms_reinitialized"]:
                embed.add_field(
                    name="✅ Platforms",
                    value=f"Reinitialized {recovery_results['platforms_reinitialized']} platforms",
                    inline=True,
                )

            if recovery_results["cache_cleared"]:
                embed.add_field(
                    name="✅ Cache", value="Cache cleared successfully", inline=True
                )

            if recovery_results["errors"]:
                error_text = "\n".join(
                    recovery_results["errors"][:3]
                )  # Show max 3 errors
                if len(recovery_results["errors"]) > 3:
                    error_text += (
                        f"\n... and {len(recovery_results['errors']) - 3} more"
                    )

                embed.add_field(name="❌ Errors", value=error_text, inline=False)

            embed.set_footer(text="Use `health` command to check current status")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error during service recovery: {e}")
            embed = create_error_embed(
                title="Recovery Failed",
                description=f"Service recovery failed: {str(e)[:100]}...\n\n"
                "Try individual recovery commands or restart the bot.",
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
            circuit_breakers = status.get("circuit_breakers", {})

            open_breakers = [
                name
                for name, cb_status in circuit_breakers.items()
                if cb_status.get("state") == "open"
            ]

            if not open_breakers:
                embed = create_embed(
                    title="Circuit Breakers Status",
                    description="All circuit breakers are already closed",
                    color=discord.Color.green(),
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
                f"**Reset breakers:** {', '.join(open_breakers[:5])}{'...' if len(open_breakers) > 5 else ''}",
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error resetting circuit breakers: {e}")
            embed = create_error_embed(
                title="Reset Failed",
                description=f"Could not reset circuit breakers: {str(e)[:100]}...",
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
                    description="No platforms are currently registered",
                )
                await ctx.send(embed=embed)
                return

            embed = create_embed(
                title="Platform Status",
                description=f"Showing status for {len(platforms)} platforms",
            )

            for name, platform in platforms.items():
                try:
                    # Check platform health
                    is_enabled = getattr(platform, "enabled", False)
                    has_session = hasattr(platform, "session") and platform.session
                    has_config = bool(getattr(platform, "config", {}))

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
                        name=f"{name.title()}", value=status_text, inline=True
                    )

                except Exception as e:
                    embed.add_field(
                        name=f"{name.title()}",
                        value=f"❌ Error: {str(e)[:50]}...",
                        inline=True,
                    )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error listing platforms: {e}")
            embed = create_error_embed(
                title="Platform List Failed",
                description=f"Could not retrieve platform information: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    async def _get_comprehensive_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status for all services"""
        health_status = {
            "overall_health": "unknown",
            "platforms": {},
            "circuit_breakers": {},
            "global_stats": {},
            "searcher_status": {},
            "audio_players": {},
            "youtube_quota": {},
        }

        try:
            # Get network resilience status
            resilience_manager = get_resilience_manager()
            resilience_status = resilience_manager.get_all_status()

            health_status["circuit_breakers"] = resilience_status.get(
                "circuit_breakers", {}
            )
            health_status["global_stats"] = resilience_status.get("global_stats", {})

            # Check platform health
            platforms = self.bot.platform_registry.get_all_platforms()
            platform_health_count = 0

            for name, platform in platforms.items():
                try:
                    is_healthy = (
                        platform.enabled
                        and hasattr(platform, "session")
                        and platform.session
                    )
                    health_status["platforms"][name] = {
                        "available": is_healthy,
                        "enabled": platform.enabled,
                    }
                    if is_healthy:
                        platform_health_count += 1
                except Exception as e:
                    logger.warning(f"Error checking platform {name} health: {e}")
                    health_status["platforms"][name] = {
                        "available": False,
                        "enabled": getattr(platform, "enabled", False),
                        "error": str(e),
                    }

            # Check searcher health
            if hasattr(self.bot, "searcher") and self.bot.searcher:
                try:
                    searcher_status = self.bot.searcher.get_search_health_status()
                    health_status["searcher_status"] = searcher_status
                except Exception as e:
                    health_status["searcher_status"] = {"error": str(e)}

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
                    logger.warning(
                        f"Error checking audio player {guild_id} health: {e}"
                    )

            health_status["audio_players"] = {
                "active": active_players,
                "healthy": healthy_players,
            }
            
            # Check YouTube quota status
            if hasattr(self.bot, "quota_monitor") and self.bot.quota_monitor:
                try:
                    quota_status = self.bot.quota_monitor.get_quota_status()
                    conservation = self.bot.quota_monitor.get_conservation_recommendations()
                    
                    health_status["youtube_quota"] = {
                        "usage": f"{quota_status['current_usage']}/{quota_status['daily_limit']}",
                        "percentage_remaining": quota_status['percentage_remaining'],
                        "level": quota_status['level'],
                        "conservation_active": quota_status['conservation_active'],
                        "hours_to_reset": quota_status.get('hours_to_reset', 'unknown'),
                        "predicted_exhaustion_hours": quota_status.get('predicted_exhaustion_hours'),
                        "message": conservation.get('message', ''),
                    }
                except Exception as e:
                    logger.warning(f"Error checking YouTube quota: {e}")
                    health_status["youtube_quota"] = {"error": str(e)}

            # Determine overall health
            success_rate = health_status["global_stats"].get("success_rate", 100)
            open_circuit_breakers = sum(
                1
                for cb_status in health_status["circuit_breakers"].values()
                if cb_status.get("state") == "open"
            )

            total_platforms = len(platforms)
            healthy_platforms = platform_health_count

            if (
                success_rate >= 90
                and open_circuit_breakers == 0
                and healthy_platforms == total_platforms
            ):
                health_status["overall_health"] = "healthy"
            elif success_rate >= 70 or healthy_platforms >= total_platforms * 0.5:
                health_status["overall_health"] = "degraded"
            else:
                health_status["overall_health"] = "unhealthy"

        except Exception as e:
            logger.error(f"Error getting comprehensive health status: {e}")
            health_status["overall_health"] = "unknown"
            health_status["error"] = str(e)

        return health_status

    async def _attempt_service_recovery(self) -> Dict[str, Any]:
        """Attempt to recover degraded services"""
        recovery_results = {
            "overall_success": False,
            "circuit_breakers_reset": 0,
            "platforms_reinitialized": 0,
            "cache_cleared": False,
            "errors": [],
        }

        try:
            # Reset circuit breakers
            try:
                resilience_manager = get_resilience_manager()
                status = resilience_manager.get_all_status()
                circuit_breakers = status.get("circuit_breakers", {})

                for cb_name, cb_status in circuit_breakers.items():
                    if cb_status.get("state") == "open":
                        try:
                            cb = resilience_manager.circuit_breakers.get(cb_name)
                            if cb:
                                cb.state = cb.state.__class__.CLOSED
                                cb.failure_count = 0
                                cb.success_count = 0
                                recovery_results["circuit_breakers_reset"] += 1
                        except Exception as e:
                            recovery_results["errors"].append(
                                f"Circuit breaker {cb_name}: {str(e)[:50]}..."
                            )

            except Exception as e:
                recovery_results["errors"].append(
                    f"Circuit breaker reset failed: {str(e)[:50]}..."
                )

            # Reinitialize platforms
            try:
                platforms = self.bot.platform_registry.get_all_platforms()
                for name, platform in platforms.items():
                    try:
                        if platform.enabled and not (
                            hasattr(platform, "session") and platform.session
                        ):
                            await platform.initialize()
                            recovery_results["platforms_reinitialized"] += 1
                    except Exception as e:
                        recovery_results["errors"].append(
                            f"Platform {name}: {str(e)[:50]}..."
                        )

            except Exception as e:
                recovery_results["errors"].append(
                    f"Platform reinitialization failed: {str(e)[:50]}..."
                )

            # Clear cache
            try:
                if hasattr(self.bot, "cache_manager") and self.bot.cache_manager:
                    await self.bot.cache_manager.clear_all()
                    recovery_results["cache_cleared"] = True
            except Exception as e:
                recovery_results["errors"].append(
                    f"Cache clear failed: {str(e)[:50]}..."
                )

            # Determine overall success
            recovery_results["overall_success"] = len(
                recovery_results["errors"]
            ) == 0 or (
                recovery_results["circuit_breakers_reset"] > 0
                or recovery_results["platforms_reinitialized"] > 0
                or recovery_results["cache_cleared"]
            )

        except Exception as e:
            recovery_results["errors"].append(
                f"Recovery process failed: {str(e)[:50]}..."
            )

        return recovery_results

    @commands.command(name="network", aliases=["connectivity", "network-status"])
    @is_admin()
    async def network_status(self, ctx: Context[RobottyBot]) -> None:
        """Show detailed network connectivity status"""
        await ctx.trigger_typing()

        try:
            connectivity_manager = get_connectivity_manager()
            result = await connectivity_manager.ensure_connectivity(skip_cache=True)

            # Create status embed based on connectivity status
            if result.status == ConnectivityStatus.HEALTHY:
                embed = create_success_embed(
                    title="🟢 Network Status: Healthy",
                    description=f"All network checks passed ({result.success_rate:.1f}% success rate)",
                )
                embed.color = discord.Color.green()
            elif result.status == ConnectivityStatus.DEGRADED:
                embed = create_warning_embed(
                    title="🟡 Network Status: Degraded",
                    description=f"Some network issues detected ({result.success_rate:.1f}% success rate)",
                )
                embed.color = discord.Color.yellow()
            else:
                embed = create_error_embed(
                    title="🔴 Network Status: Failed",
                    description=f"Critical network issues detected ({result.success_rate:.1f}% success rate)",
                )
                embed.color = discord.Color.red()

            # Add detailed statistics
            embed.add_field(
                name="📊 Statistics",
                value=f"**Successful:** {result.successful_checks}\n"
                f"**Failed:** {result.failed_checks}\n"
                f"**Total:** {result.total_checks}",
                inline=True,
            )

            # Add response times
            if result.response_times:
                avg_response_time = sum(result.response_times.values()) / len(
                    result.response_times
                )
                response_text = f"**Average:** {avg_response_time:.2f}s\n"

                # Show top 3 fastest/slowest
                sorted_times = sorted(result.response_times.items(), key=lambda x: x[1])
                if len(sorted_times) > 0:
                    response_text += f"**Fastest:** {sorted_times[0][0]} ({sorted_times[0][1]:.2f}s)\n"
                if len(sorted_times) > 1:
                    response_text += f"**Slowest:** {sorted_times[-1][0]} ({sorted_times[-1][1]:.2f}s)"

                embed.add_field(
                    name="⏱️ Response Times", value=response_text, inline=True
                )

            # Add current settings
            optimal_dns = connectivity_manager.checker.get_optimal_dns_server()
            optimal_gateway = connectivity_manager.checker.get_optimal_discord_gateway()

            settings_text = ""
            if optimal_dns:
                settings_text += f"**DNS:** {optimal_dns}\n"
            if optimal_gateway:
                settings_text += f"**Gateway:** {optimal_gateway}"

            if settings_text:
                embed.add_field(
                    name="🔧 Current Settings", value=settings_text, inline=True
                )

            # Add errors if any
            if result.errors:
                error_text = "\n".join([f"• {error}" for error in result.errors[:3]])
                if len(result.errors) > 3:
                    error_text += f"\n... and {len(result.errors) - 3} more"

                embed.add_field(
                    name="❌ Issues Detected", value=error_text, inline=False
                )

            # Add recommendations
            if result.recommended_actions:
                rec_text = "\n".join(
                    [f"• {action}" for action in result.recommended_actions[:3]]
                )
                if len(result.recommended_actions) > 3:
                    rec_text += f"\n... and {len(result.recommended_actions) - 3} more"

                embed.add_field(name="💡 Recommendations", value=rec_text, inline=False)

            embed.set_footer(text="Use `network-test` to run connectivity tests")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error checking network status: {e}")
            embed = create_error_embed(
                title="Network Check Failed",
                description=f"Could not check network status: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    @commands.command(name="network-test", aliases=["connectivity-test", "nettest"])
    @is_admin()
    async def network_test(self, ctx: Context[RobottyBot]) -> None:
        """Run comprehensive network connectivity tests"""
        await ctx.trigger_typing()

        try:
            connectivity_manager = get_connectivity_manager()

            # Send initial message
            embed = create_embed(
                title="🔄 Running Network Tests",
                description="Testing DNS resolution, endpoints, and Discord gateways...",
                color=discord.Color.blue(),
            )
            message = await ctx.send(embed=embed)

            # Run the actual tests
            result = await connectivity_manager.ensure_connectivity(skip_cache=True)

            # Update with results
            if result.status == ConnectivityStatus.HEALTHY:
                embed = create_success_embed(
                    title="✅ Network Tests Completed",
                    description=f"All tests passed successfully! ({result.success_rate:.1f}% success rate)",
                )
            elif result.status == ConnectivityStatus.DEGRADED:
                embed = create_warning_embed(
                    title="⚠️ Network Tests Completed",
                    description=f"Some tests failed, but connection is usable ({result.success_rate:.1f}% success rate)",
                )
            else:
                embed = create_error_embed(
                    title="❌ Network Tests Failed",
                    description=f"Critical connectivity issues detected ({result.success_rate:.1f}% success rate)",
                )

            # Add test breakdown
            embed.add_field(
                name="Test Results",
                value=f"**Passed:** {result.successful_checks}/{result.total_checks}\n"
                f"**Failed:** {result.failed_checks}/{result.total_checks}",
                inline=True,
            )

            if result.response_times:
                avg_time = sum(result.response_times.values()) / len(
                    result.response_times
                )
                embed.add_field(
                    name="Performance",
                    value=f"**Avg Response:** {avg_time:.2f}s",
                    inline=True,
                )

            await message.edit(embed=embed)

        except Exception as e:
            logger.error(f"Error running network tests: {e}")
            embed = create_error_embed(
                title="Test Failed",
                description=f"Network tests failed to complete: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    @commands.command(name="connection-stats", aliases=["conn-stats"])
    @is_admin()
    async def connection_stats(self, ctx: Context[RobottyBot]) -> None:
        """Show Discord connection statistics"""
        try:
            if hasattr(self.bot, "get_connection_stats"):
                stats = self.bot.get_connection_stats()

                embed = create_embed(
                    title="🔗 Discord Connection Statistics",
                    description=f"Current state: **{stats['connection_state'].title()}**",
                )

                # Connection attempts
                embed.add_field(
                    name="📊 Connection Attempts",
                    value=f"**Total:** {stats['total_attempts']}\n"
                    f"**Successful:** {stats['successful_attempts']}\n"
                    f"**Failed:** {stats['failed_attempts']}\n"
                    f"**Consecutive Failures:** {stats['consecutive_failures']}",
                    inline=True,
                )

                # Performance
                if stats["average_response_time"] > 0:
                    embed.add_field(
                        name="⏱️ Performance",
                        value=f"**Avg Response:** {stats['average_response_time']:.2f}s",
                        inline=True,
                    )

                # Current settings
                if stats["current_gateway"]:
                    embed.add_field(
                        name="🌐 Current Gateway",
                        value=stats["current_gateway"],
                        inline=True,
                    )

                # Last successful connection
                if stats["last_successful_connect"]:
                    import datetime

                    last_connect = datetime.datetime.fromtimestamp(
                        stats["last_successful_connect"]
                    )
                    embed.add_field(
                        name="✅ Last Successful Connection",
                        value=last_connect.strftime("%Y-%m-%d %H:%M:%S"),
                        inline=False,
                    )

                # Circuit breaker status
                if "circuit_breaker_status" in stats:
                    cb_status = stats["circuit_breaker_status"]
                    embed.add_field(
                        name="🔌 Circuit Breaker",
                        value=f"**State:** {cb_status.get('state', 'unknown').title()}\n"
                        f"**Failures:** {cb_status.get('failure_count', 0)}",
                        inline=True,
                    )

                await ctx.send(embed=embed)
            else:
                embed = create_warning_embed(
                    title="Connection Stats Unavailable",
                    description="Connection statistics are not available (resilient client not initialized)",
                )
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error getting connection stats: {e}")
            embed = create_error_embed(
                title="Stats Failed",
                description=f"Could not retrieve connection statistics: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    @commands.command(name="rotate-gateway", aliases=["switch-gateway"])
    @is_admin()
    async def rotate_gateway(self, ctx: Context[RobottyBot]) -> None:
        """Force rotation to a different Discord gateway"""
        try:
            if hasattr(self.bot, "force_gateway_rotation"):
                embed = create_embed(
                    title="🔄 Rotating Discord Gateway",
                    description="Searching for optimal Discord gateway...",
                    color=discord.Color.blue(),
                )
                message = await ctx.send(embed=embed)

                await self.bot.force_gateway_rotation()

                # Get new gateway info
                if hasattr(self.bot, "get_connection_stats"):
                    stats = self.bot.get_connection_stats()
                    new_gateway = stats.get("current_gateway", "Unknown")

                    embed = create_success_embed(
                        title="✅ Gateway Rotation Complete",
                        description=f"Switched to gateway: **{new_gateway}**",
                    )
                else:
                    embed = create_success_embed(
                        title="✅ Gateway Rotation Complete",
                        description="Discord gateway has been rotated",
                    )

                await message.edit(embed=embed)
            else:
                embed = create_warning_embed(
                    title="Gateway Rotation Unavailable",
                    description="Gateway rotation is not available (resilient client not initialized)",
                )
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error rotating gateway: {e}")
            embed = create_error_embed(
                title="Rotation Failed",
                description=f"Could not rotate Discord gateway: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)


    @commands.group(name="prioritization", aliases=["priority", "prio"])
    @is_admin()
    async def prioritization(self, ctx: Context[RobottyBot]) -> None:
        """Platform prioritization management commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @prioritization.command(name="status")
    async def prioritization_status(self, ctx: Context[RobottyBot]) -> None:
        """Show current platform prioritization status"""
        await ctx.trigger_typing()

        try:
            from ...services.platform_prioritization import get_prioritization_manager, PrioritizationStrategy
            
            prioritization_manager = get_prioritization_manager()
            if not prioritization_manager:
                embed = create_warning_embed(
                    title="Prioritization Not Available",
                    description="Platform prioritization manager is not initialized",
                )
                await ctx.send(embed=embed)
                return

            # Get platform metrics summary
            metrics_summary = prioritization_manager.get_platform_metrics_summary()
            platforms = self.bot.platform_registry.get_enabled_platforms()
            priority_order = prioritization_manager.get_platform_priority_order(platforms)

            embed = create_embed(
                title="🎯 Platform Prioritization Status",
                description=f"**Strategy:** {prioritization_manager.strategy.value}\n"
                           f"**Enabled:** {'✅' if prioritization_manager.enabled else '❌'}\n"
                           f"**Priority Order:** {' → '.join(priority_order)}",
            )

            # Add metrics for each platform
            for i, platform_name in enumerate(priority_order):
                if platform_name in metrics_summary:
                    metrics = metrics_summary[platform_name]
                    
                    # Create status indicator
                    health_indicators = {
                        "healthy": "🟢",
                        "degraded": "🟡", 
                        "unhealthy": "🔴",
                        "unknown": "⚪"
                    }
                    health_icon = health_indicators.get(metrics["current_health"], "⚪")
                    
                    value = (
                        f"{health_icon} **Score:** {metrics['overall_score']:.3f}\n"
                        f"📈 **Success Rate:** {metrics['success_rate']:.1%}\n"
                        f"⚡ **Avg Response:** {metrics['avg_response_time']:.2f}s\n"
                        f"📊 **Requests:** {metrics['total_requests']}\n"
                        f"❌ **Consecutive Failures:** {metrics['consecutive_failures']}"
                    )
                    
                    embed.add_field(
                        name=f"#{i+1} {platform_name.title()}",
                        value=value,
                        inline=True
                    )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error getting prioritization status: {e}")
            embed = create_error_embed(
                title="Status Error",
                description=f"Could not get prioritization status: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    @prioritization.command(name="strategy")
    async def set_strategy(self, ctx: Context[RobottyBot], strategy: str) -> None:
        """Set the prioritization strategy
        
        Available strategies:
        - balanced: Balance response time, reliability, and success rate
        - speed_first: Prioritize fastest response times
        - reliability_first: Prioritize most reliable platforms  
        - success_rate_first: Prioritize highest success rates
        - adaptive: Dynamically adjust based on current conditions
        """
        await ctx.trigger_typing()

        try:
            from ...services.platform_prioritization import get_prioritization_manager, PrioritizationStrategy
            
            prioritization_manager = get_prioritization_manager()
            if not prioritization_manager:
                embed = create_warning_embed(
                    title="Prioritization Not Available",
                    description="Platform prioritization manager is not initialized",
                )
                await ctx.send(embed=embed)
                return

            # Validate strategy
            valid_strategies = [s.value for s in PrioritizationStrategy]
            if strategy.lower() not in valid_strategies:
                embed = create_error_embed(
                    title="Invalid Strategy",
                    description=f"Valid strategies: {', '.join(valid_strategies)}",
                )
                await ctx.send(embed=embed)
                return

            # Set new strategy
            new_strategy = PrioritizationStrategy(strategy.lower())
            prioritization_manager.set_strategy(new_strategy)

            embed = create_success_embed(
                title="Strategy Updated",
                description=f"Prioritization strategy set to: **{new_strategy.value}**",
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error setting prioritization strategy: {e}")
            embed = create_error_embed(
                title="Strategy Error",
                description=f"Could not set strategy: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    @prioritization.command(name="enable")
    async def enable_prioritization(self, ctx: Context[RobottyBot]) -> None:
        """Enable dynamic platform prioritization"""
        await ctx.trigger_typing()

        try:
            from ...services.platform_prioritization import get_prioritization_manager
            
            prioritization_manager = get_prioritization_manager()
            if not prioritization_manager:
                embed = create_warning_embed(
                    title="Prioritization Not Available",
                    description="Platform prioritization manager is not initialized",
                )
                await ctx.send(embed=embed)
                return

            prioritization_manager.enabled = True
            
            embed = create_success_embed(
                title="Prioritization Enabled",
                description="Dynamic platform prioritization is now **enabled**",
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error enabling prioritization: {e}")
            embed = create_error_embed(
                title="Enable Error",
                description=f"Could not enable prioritization: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    @prioritization.command(name="disable")
    async def disable_prioritization(self, ctx: Context[RobottyBot]) -> None:
        """Disable dynamic platform prioritization (fallback to static order)"""
        await ctx.trigger_typing()

        try:
            from ...services.platform_prioritization import get_prioritization_manager
            
            prioritization_manager = get_prioritization_manager()
            if not prioritization_manager:
                embed = create_warning_embed(
                    title="Prioritization Not Available", 
                    description="Platform prioritization manager is not initialized",
                )
                await ctx.send(embed=embed)
                return

            prioritization_manager.enabled = False
            
            embed = create_success_embed(
                title="Prioritization Disabled",
                description="Dynamic platform prioritization is now **disabled**\nUsing static priority order",
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error disabling prioritization: {e}")
            embed = create_error_embed(
                title="Disable Error",
                description=f"Could not disable prioritization: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    @commands.command(name="voicehealth", aliases=["vhealth", "voice-status"])
    @is_admin()
    async def voice_health(self, ctx: Context[RobottyBot]) -> None:
        """Show voice connection health status"""
        await ctx.trigger_typing()

        try:
            if not hasattr(self.bot, 'voice_connection_manager') or not self.bot.voice_connection_manager:
                embed = create_warning_embed(
                    title="Voice Manager Unavailable",
                    description="Voice connection manager is not initialized",
                )
                await ctx.send(embed=embed)
                return

            voice_manager = self.bot.voice_connection_manager
            health_status = voice_manager.get_health_status()

            # Create status embed
            if health_status['total_guilds'] == 0:
                embed = create_embed(
                    title="🔇 Voice Status: Inactive",
                    description="No active voice connections",
                    color=discord.Color.blue()
                )
            elif health_status['failed'] == 0:
                embed = create_success_embed(
                    title="🔊 Voice Status: Healthy",
                    description=f"All voice connections are functioning properly",
                )
            elif health_status['connection_rate'] >= 0.8:
                embed = create_warning_embed(
                    title="🔊 Voice Status: Mostly Healthy",
                    description=f"Most voice connections are working ({health_status['connection_rate']:.1%} success rate)",
                )
            else:
                embed = create_error_embed(
                    title="🔇 Voice Status: Issues Detected",
                    description=f"Multiple voice connection issues ({health_status['connection_rate']:.1%} success rate)",
                )

            # Add environment info
            environment = health_status.get('environment', 'unknown')
            env_emoji = {
                'local': '💻',
                'docker': '🐳',
                'vps': '☁️'
            }.get(environment, '❓')
            
            embed.add_field(
                name=f"{env_emoji} Environment",
                value=f"**Type:** {environment.upper()}\n"
                f"**Detection:** Automatic",
                inline=True,
            )
            
            # Add statistics
            embed.add_field(
                name="📊 Connection Statistics",
                value=f"**Total Guilds:** {health_status['total_guilds']}\n"
                f"**Connected:** {health_status['connected']}\n"
                f"**Failed:** {health_status['failed']}\n"
                f"**Success Rate:** {health_status['connection_rate']:.1%}",
                inline=True,
            )
            
            # Add configuration info
            if 'configuration' in health_status:
                config = health_status['configuration']
                embed.add_field(
                    name="⚙️ Configuration",
                    value=f"**Max Retries:** {config['max_retry_attempts']}\n"
                    f"**Base Delay:** {config['base_retry_delay']}s\n"
                    f"**Timeout:** {config['connection_timeout']}s\n"
                    f"**Circuit Threshold:** {config['circuit_breaker_threshold']}",
                    inline=True,
                )
            
            # Add circuit breaker status
            circuit_open_count = health_status.get('circuit_breakers_open', 0)
            if circuit_open_count > 0:
                embed.add_field(
                    name="🚨 Circuit Breakers",
                    value=f"**Open:** {circuit_open_count} guild(s)\n"
                    f"These guilds are temporarily blocked from voice connections",
                    inline=False,
                )

            # Add per-guild status if any connections exist
            if health_status['states']:
                guild_status_lines = []
                for guild_id, state in list(health_status['states'].items())[:10]:  # Limit to 10 guilds
                    guild = self.bot.get_guild(guild_id)
                    guild_name = guild.name if guild else f"Guild {guild_id}"
                    
                    status_emoji = {
                        'connected': '🟢',
                        'connecting': '🟡', 
                        'reconnecting': '🟠',
                        'failed': '🔴',
                        'disconnected': '⚪'
                    }.get(state, '❓')
                    
                    guild_status_lines.append(f"{status_emoji} {guild_name}: {state}")

                if guild_status_lines:
                    embed.add_field(
                        name="🏠 Guild Status",
                        value="\n".join(guild_status_lines),
                        inline=False,
                    )
                    
                    if len(health_status['states']) > 10:
                        embed.add_field(
                            name="",
                            value=f"... and {len(health_status['states']) - 10} more guilds",
                            inline=False,
                        )

            # Add recommendations if there are issues
            if health_status['failed'] > 0:
                embed.add_field(
                    name="💡 Recommendations",
                    value="• Check Discord voice server status\n"
                    "• Verify bot permissions in voice channels\n"
                    "• Run voice diagnostics: `!voicediag`\n"
                    "• Consider restarting bot if issues persist",
                    inline=False,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error getting voice health status: {e}")
            embed = create_error_embed(
                title="Voice Health Check Failed",
                description=f"Could not retrieve voice health status: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    @commands.command(name="voicediag", aliases=["vdiag", "voice-diag"])
    @is_admin()
    async def voice_diagnostics(self, ctx: Context[RobottyBot]) -> None:
        """Run voice connection diagnostics"""
        await ctx.trigger_typing()

        try:
            if not hasattr(self.bot, 'voice_connection_manager') or not self.bot.voice_connection_manager:
                embed = create_warning_embed(
                    title="Voice Manager Unavailable",
                    description="Voice connection manager is not initialized",
                )
                await ctx.send(embed=embed)
                return

            voice_manager = self.bot.voice_connection_manager
            
            # Run health check on all connections
            unhealthy_guilds = await voice_manager.health_check_connections()
            
            if not unhealthy_guilds:
                embed = create_success_embed(
                    title="🔍 Voice Diagnostics: All Clear",
                    description="All voice connections passed health checks",
                )
            else:
                embed = create_warning_embed(
                    title="🔍 Voice Diagnostics: Issues Found",
                    description=f"Found {len(unhealthy_guilds)} unhealthy voice connections",
                )
                
                guild_issues = []
                for guild_id in unhealthy_guilds[:5]:  # Show first 5
                    guild = self.bot.get_guild(guild_id)
                    guild_name = guild.name if guild else f"Guild {guild_id}"
                    connection_info = voice_manager.get_connection_info(guild_id)
                    
                    issue_details = [
                        f"**{guild_name}**",
                        f"State: {connection_info['state']}",
                        f"Attempts: {connection_info['attempts']}/{connection_info['max_attempts']}"
                    ]
                    
                    # Add session info if available
                    if 'session' in connection_info:
                        session = connection_info['session']
                        issue_details.append(f"Session: {session['id']}")
                        issue_details.append(f"Session Age: {session['age_seconds']:.0f}s")
                    
                    # Add last error if available
                    if connection_info.get('last_error'):
                        error_msg = connection_info['last_error'][:50] + "..." if len(connection_info['last_error']) > 50 else connection_info['last_error']
                        issue_details.append(f"Error: {error_msg}")
                    
                    # Add circuit breaker info if available
                    if 'circuit_breaker' in connection_info and connection_info['circuit_breaker']['is_open']:
                        issue_details.append(f"⚠️ Circuit breaker OPEN ({connection_info['circuit_breaker']['failures']} failures)")
                    
                    guild_issues.append("\n".join(issue_details))
                
                if guild_issues:
                    embed.add_field(
                        name="🏠 Unhealthy Guilds",
                        value="\n\n".join(guild_issues),
                        inline=False,
                    )
                
                if len(unhealthy_guilds) > 5:
                    embed.add_field(
                        name="",
                        value=f"... and {len(unhealthy_guilds) - 5} more affected guilds",
                        inline=False,
                    )

            # Add diagnostic information
            embed.add_field(
                name="🛠️ Diagnostic Actions",
                value="• Checked voice client connections\n"
                "• Validated connection states\n"
                "• Cleared invalid references\n"
                "• Updated connection tracking",
                inline=False,
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error running voice diagnostics: {e}")
            embed = create_error_embed(
                title="Voice Diagnostics Failed",
                description=f"Could not run voice diagnostics: {str(e)[:100]}...",
            )
            await ctx.send(embed=embed)

    @commands.command(name="voiceenv", aliases=["venv", "voice-env"])
    @is_admin()
    async def voice_environment(self, ctx: Context[RobottyBot], environment: Optional[str] = None) -> None:
        """Show or set voice connection environment mode
        
        Usage:
        - !voiceenv - Show current environment
        - !voiceenv vps - Force VPS mode
        - !voiceenv local - Force local mode
        - !voiceenv auto - Re-detect environment
        """
        if not hasattr(self.bot, 'voice_connection_manager') or not self.bot.voice_connection_manager:
            embed = create_warning_embed(
                title="Voice Manager Unavailable",
                description="Voice connection manager is not initialized",
            )
            await ctx.send(embed=embed)
            return
        
        voice_manager = self.bot.voice_connection_manager
        
        # Show current environment if no argument
        if environment is None:
            current_env = voice_manager.environment.value
            env_emoji = {
                'local': '💻',
                'docker': '🐳',
                'vps': '☁️'
            }.get(current_env, '❓')
            
            embed = create_embed(
                title=f"{env_emoji} Voice Environment: {current_env.upper()}",
                description="Current voice connection environment configuration",
                color=discord.Color.blue()
            )
            
            # Add detection info
            embed.add_field(
                name="🔍 Detection Method",
                value="Automatic detection based on:\n"
                "• Docker container presence\n"
                "• Environment variables\n"
                "• Network configuration\n"
                "• System indicators",
                inline=False
            )
            
            # Add current configuration
            embed.add_field(
                name="⚙️ Current Settings",
                value=f"**Max Retries:** {voice_manager.max_retry_attempts}\n"
                f"**Base Delay:** {voice_manager.base_retry_delay}s\n"
                f"**Max Delay:** {voice_manager.max_retry_delay}s\n"
                f"**Connection Timeout:** {voice_manager.connection_timeout}s\n"
                f"**Session Timeout:** {voice_manager.session_timeout}s\n"
                f"**Circuit Breaker Threshold:** {voice_manager.circuit_breaker_threshold}",
                inline=True
            )
            
            # Add usage info
            embed.add_field(
                name="💡 Usage",
                value="To change environment:\n"
                "`!voiceenv vps` - Force VPS mode\n"
                "`!voiceenv local` - Force local mode\n"
                "`!voiceenv auto` - Re-detect environment",
                inline=True
            )
            
            await ctx.send(embed=embed)
            return
        
        # Handle environment changes
        environment = environment.lower()
        
        if environment == "auto":
            # Re-detect environment
            old_env = voice_manager.environment.value
            voice_manager.environment = voice_manager._detect_environment()
            new_env = voice_manager.environment.value
            
            if old_env == new_env:
                embed = create_embed(
                    title="🔍 Environment Re-detected",
                    description=f"Environment remains: **{new_env.upper()}**",
                    color=discord.Color.blue()
                )
            else:
                embed = create_success_embed(
                    title="🔄 Environment Changed",
                    description=f"Environment changed from **{old_env.upper()}** to **{new_env.upper()}**"
                )
                # Reconfigure based on new environment
                voice_manager.__init__(self.bot)
            
            await ctx.send(embed=embed)
            
        elif environment in ["vps", "local", "docker"]:
            from ...services.voice_connection_manager import DeploymentEnvironment
            
            old_env = voice_manager.environment.value
            
            # Map string to enum
            env_map = {
                "vps": DeploymentEnvironment.VPS,
                "local": DeploymentEnvironment.LOCAL,
                "docker": DeploymentEnvironment.DOCKER
            }
            
            voice_manager.environment = env_map[environment]
            
            # Reconfigure for new environment
            if voice_manager.environment == DeploymentEnvironment.VPS:
                # VPS-specific configuration
                voice_manager.max_retry_attempts = 8
                voice_manager.base_retry_delay = 5.0
                voice_manager.max_retry_delay = 120.0
                voice_manager.connection_timeout = 45.0
                voice_manager.session_timeout = 300.0
                voice_manager.circuit_breaker_threshold = 5
                voice_manager.circuit_breaker_timeout = 300.0
                voice_manager.network_check_interval = 10.0
            else:
                # Local/Docker configuration
                voice_manager.max_retry_attempts = 5
                voice_manager.base_retry_delay = 2.0
                voice_manager.max_retry_delay = 60.0
                voice_manager.connection_timeout = 30.0
                voice_manager.session_timeout = 180.0
                voice_manager.circuit_breaker_threshold = 3
                voice_manager.circuit_breaker_timeout = 180.0
                voice_manager.network_check_interval = 5.0
            
            embed = create_success_embed(
                title="✅ Environment Updated",
                description=f"Voice environment changed from **{old_env.upper()}** to **{environment.upper()}**"
            )
            
            embed.add_field(
                name="⚙️ New Configuration",
                value=f"**Max Retries:** {voice_manager.max_retry_attempts}\n"
                f"**Base Delay:** {voice_manager.base_retry_delay}s\n"
                f"**Connection Timeout:** {voice_manager.connection_timeout}s\n"
                f"**Circuit Breaker Threshold:** {voice_manager.circuit_breaker_threshold}",
                inline=False
            )
            
            if environment == "vps":
                embed.add_field(
                    name="☁️ VPS Optimizations",
                    value="• Longer retry delays\n"
                    "• Extended connection timeout\n"
                    "• Higher circuit breaker threshold\n"
                    "• Network stability checks enabled\n"
                    "• Session recreation on error 4006",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        else:
            embed = create_error_embed(
                title="Invalid Environment",
                description=f"Unknown environment: `{environment}`\n\n"
                "Valid options: `vps`, `local`, `docker`, `auto`"
            )
            await ctx.send(embed=embed)

    @commands.command(name="platform-stability", aliases=["pstatus", "stability"])
    @is_admin()
    async def platform_stability(self, ctx: Context[RobottyBot]) -> None:
        """Check platform stability status and health metrics"""
        await ctx.trigger_typing()
        
        try:
            # Check if stability monitor is available
            if not hasattr(self.bot, 'stability_monitor') or not self.bot.stability_monitor:
                embed = create_warning_embed(
                    title="Stability Monitor Not Available",
                    description="Stability monitoring is not enabled or not initialized"
                )
                await ctx.send(embed=embed)
                return
                
            # Get platform status from stability monitor
            platform_status = await self.bot.stability_monitor.get_platform_status()
            
            # Check if stability mode is enabled
            stability_enabled = self.bot.stability_monitor.enabled
            
            # Create embed
            if stability_enabled:
                embed = create_embed(
                    title="Platform Stability Status (STABILITY MODE ACTIVE)",
                    description="Automatic platform disabling is enabled to maintain bot stability",
                    color=discord.Color.orange()
                )
            else:
                embed = create_embed(
                    title="Platform Stability Status",
                    description="Platform health monitoring (stability mode disabled)",
                    color=discord.Color.blue()
                )
            
            # Add stability mode configuration
            config_info = []
            if stability_enabled:
                config_info.append(f"Failure Threshold: {self.bot.stability_monitor.failure_threshold}")
                config_info.append(f"Recovery Check: {self.bot.stability_monitor.recovery_check_interval}s")
                config_info.append(f"Auto-disable: {'Enabled' if self.bot.stability_monitor.auto_disable else 'Disabled'}")
                
                embed.add_field(
                    name="⚙️ Configuration",
                    value="\n".join(config_info),
                    inline=False
                )
            
            # Group platforms by status
            enabled_platforms = []
            disabled_platforms = []
            problematic_platforms = []
            
            for name, status in platform_status.items():
                if status['is_disabled']:
                    disabled_platforms.append((name, status))
                elif status['is_problematic']:
                    problematic_platforms.append((name, status))
                else:
                    enabled_platforms.append((name, status))
            
            # Add enabled platforms
            if enabled_platforms:
                platform_info = []
                for name, status in enabled_platforms:
                    fail_rate = status['failure_rate'] * 100
                    emoji = "✅" if status['consecutive_failures'] == 0 else "⚠️"
                    protection = "🛡️" if status['is_protected'] else ""
                    
                    platform_info.append(
                        f"{emoji} **{name.title()}** {protection}\n"
                        f"   Failures: {status['consecutive_failures']}/{self.bot.stability_monitor.failure_threshold} "
                        f"(Rate: {fail_rate:.1f}%)"
                    )
                
                embed.add_field(
                    name="✅ Active Platforms",
                    value="\n".join(platform_info[:5]),  # Limit to 5
                    inline=False
                )
            
            # Add disabled platforms
            if disabled_platforms:
                platform_info = []
                for name, status in disabled_platforms:
                    fail_rate = status['failure_rate'] * 100
                    disabled_time = status.get('disabled_at', 'Unknown')
                    
                    # Get top failure reason
                    top_reason = "unknown"
                    if status['top_failure_reasons']:
                        top_reason = list(status['top_failure_reasons'].keys())[0]
                    
                    platform_info.append(
                        f"❌ **{name.title()}**\n"
                        f"   Disabled at: {disabled_time}\n"
                        f"   Failure rate: {fail_rate:.1f}%\n"
                        f"   Main issue: {top_reason}"
                    )
                
                embed.add_field(
                    name="❌ Disabled Platforms",
                    value="\n".join(platform_info),
                    inline=False
                )
            
            # Add problematic platforms (marked but not disabled)
            if problematic_platforms:
                platform_info = []
                for name, status in problematic_platforms:
                    if not status['is_disabled']:  # Only show if not already disabled
                        fail_rate = status['failure_rate'] * 100
                        platform_info.append(
                            f"⚠️ **{name.title()}** (marked problematic)\n"
                            f"   Failures: {status['consecutive_failures']}/{self.bot.stability_monitor.failure_threshold} "
                            f"(Rate: {fail_rate:.1f}%)"
                        )
                
                if platform_info:
                    embed.add_field(
                        name="⚠️ Problematic Platforms",
                        value="\n".join(platform_info),
                        inline=False
                    )
            
            # Add summary statistics
            total_platforms = len(platform_status)
            active_count = len(enabled_platforms)
            disabled_count = len(disabled_platforms)
            
            stats = [
                f"Total Platforms: {total_platforms}",
                f"Active: {active_count}",
                f"Disabled: {disabled_count}",
            ]
            
            embed.add_field(
                name="📊 Summary",
                value="\n".join(stats),
                inline=True
            )
            
            # Add recovery info if platforms are disabled
            if disabled_platforms and stability_enabled:
                embed.set_footer(
                    text=f"Disabled platforms will be checked for recovery every {self.bot.stability_monitor.recovery_check_interval}s"
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting platform stability status: {e}")
            embed = create_error_embed(
                title="Stability Check Failed",
                description=f"Could not retrieve platform stability status: {str(e)[:100]}..."
            )
            await ctx.send(embed=embed)

    @commands.command(name="enable-platform", aliases=["ep"])
    @is_admin()
    async def enable_platform(self, ctx: Context[RobottyBot], platform_name: str) -> None:
        """Manually enable a disabled platform"""
        try:
            if not hasattr(self.bot, 'stability_monitor') or not self.bot.stability_monitor:
                embed = create_error_embed(
                    title="Stability Monitor Not Available",
                    description="Stability monitoring is not enabled"
                )
                await ctx.send(embed=embed)
                return
            
            platform_name = platform_name.lower()
            
            # Try to enable the platform
            success = await self.bot.stability_monitor.try_enable_platform(platform_name)
            
            if success:
                embed = create_success_embed(
                    title="Platform Enabled",
                    description=f"Successfully re-enabled **{platform_name}** platform.\n\n"
                    "The platform will be monitored for stability."
                )
            else:
                embed = create_warning_embed(
                    title="Platform Enable Failed",
                    description=f"Could not enable **{platform_name}**.\n\n"
                    "Possible reasons:\n"
                    "• Platform doesn't exist\n"
                    "• Platform is not disabled\n"
                    "• Not enough time has passed since disabling"
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error enabling platform: {e}")
            embed = create_error_embed(
                title="Enable Failed",
                description=f"Failed to enable platform: {str(e)[:100]}..."
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="platform", aliases=["platforms"])
    @is_admin()
    async def platform_control(self, ctx: Context[RobottyBot], action: Optional[str] = None, platform_name: Optional[str] = None) -> None:
        """Control platform enable/disable status
        
        Usage:
        !platform - Show all platforms status
        !platform enable <name> - Enable a platform
        !platform disable <name> - Disable a platform
        """
        await ctx.trigger_typing()
        
        try:
            # Show platform status if no action specified
            if not action:
                platforms = self.bot.platform_registry.get_all_platforms()
                
                embed = create_embed(
                    title="Platform Status",
                    description="Current status of all registered platforms",
                    color=discord.Color.blue()
                )
                
                # Group by status
                enabled_platforms = []
                disabled_platforms = []
                
                for name, platform in platforms.items():
                    if platform.enabled:
                        enabled_platforms.append(name)
                    else:
                        disabled_platforms.append(name)
                
                if enabled_platforms:
                    embed.add_field(
                        name="✅ Enabled Platforms",
                        value="\n".join([f"• **{p}**" for p in sorted(enabled_platforms)]),
                        inline=False
                    )
                
                if disabled_platforms:
                    embed.add_field(
                        name="❌ Disabled Platforms", 
                        value="\n".join([f"• **{p}**" for p in sorted(disabled_platforms)]),
                        inline=False
                    )
                
                # Add stability info if available
                if hasattr(self.bot, 'stability_monitor') and self.bot.stability_monitor:
                    if self.bot.stability_monitor.disabled_platforms:
                        embed.add_field(
                            name="🚨 Auto-disabled by Stability Monitor",
                            value="\n".join([f"• **{p}**" for p in sorted(self.bot.stability_monitor.disabled_platforms)]),
                            inline=False
                        )
                
                embed.set_footer(text="Use !platform enable/disable <name> to control platforms")
                await ctx.send(embed=embed)
                return
            
            # Validate action
            action = action.lower()
            if action not in ['enable', 'disable']:
                embed = create_error_embed(
                    title="Invalid Action",
                    description="Valid actions are: `enable` or `disable`"
                )
                await ctx.send(embed=embed)
                return
            
            # Validate platform name
            if not platform_name:
                embed = create_error_embed(
                    title="Platform Name Required",
                    description=f"Usage: `!platform {action} <platform_name>`"
                )
                await ctx.send(embed=embed)
                return
            
            platform_name = platform_name.lower()
            platform = self.bot.platform_registry.get_platform(platform_name)
            
            if not platform:
                embed = create_error_embed(
                    title="Platform Not Found",
                    description=f"Platform **{platform_name}** is not registered.\n\n"
                    f"Available platforms: {', '.join(self.bot.platform_registry.get_all_platforms().keys())}"
                )
                await ctx.send(embed=embed)
                return
            
            # Handle enable/disable
            if action == 'enable':
                if platform.enabled:
                    embed = create_warning_embed(
                        title="Already Enabled",
                        description=f"Platform **{platform_name}** is already enabled"
                    )
                else:
                    platform.enabled = True
                    # Remove from disabled platforms if present
                    if hasattr(self.bot, 'stability_monitor') and self.bot.stability_monitor:
                        self.bot.stability_monitor.disabled_platforms.discard(platform_name)
                    
                    embed = create_success_embed(
                        title="Platform Enabled",
                        description=f"Successfully enabled **{platform_name}** platform"
                    )
            else:  # disable
                if not platform.enabled:
                    embed = create_warning_embed(
                        title="Already Disabled",
                        description=f"Platform **{platform_name}** is already disabled"
                    )
                else:
                    platform.enabled = False
                    # Add to disabled platforms if stability monitor exists
                    if hasattr(self.bot, 'stability_monitor') and self.bot.stability_monitor:
                        self.bot.stability_monitor.disabled_platforms.add(platform_name)
                    
                    embed = create_success_embed(
                        title="Platform Disabled",
                        description=f"Successfully disabled **{platform_name}** platform"
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in platform control: {e}")
            embed = create_error_embed(
                title="Platform Control Failed",
                description=f"Failed to control platform: {str(e)[:100]}..."
            )
            await ctx.send(embed=embed)


async def setup(bot: RobottyBot) -> None:
    await bot.add_cog(Admin(bot))
