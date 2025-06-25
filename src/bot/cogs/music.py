import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import discord
from discord.ext import commands

from ..utils.checks import is_in_voice_channel, is_same_voice_channel
from ..utils.embeds import create_embed, create_error_embed, create_warning_embed  # type: ignore
from ...platforms.errors import (
    PlatformError,
    PlatformNotAvailableError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
)
from ...utils.network_resilience import (
    CircuitBreakerOpenError,
    MaxRetriesExceededError,
    NetworkTimeoutError,
)

if TYPE_CHECKING:
    from discord import Message

    from ..bot import RobusttyBot

logger = logging.getLogger(__name__)


class Music(commands.Cog):
    """Music commands for the bot"""

    def __init__(self, bot: "RobusttyBot") -> None:
        self.bot: "RobusttyBot" = bot

        # Expose command callbacks for direct invocation in tests
        for cmd_name in [
            "join",
            "play",
            "skip",
            "stop",
            "queue",
            "leave",
            "pause",
            "resume",
            "volume",
            "test",
        ]:
            cmd_obj = getattr(type(self), cmd_name)
            if hasattr(cmd_obj, "callback"):
                func = cmd_obj.callback.__get__(self, type(self))
                setattr(self, cmd_name, func)

    @commands.command(name="join", aliases=["j", "connect"])
    @is_in_voice_channel()
    async def join(self, ctx: commands.Context[commands.Bot]) -> None:
        """Join the voice channel"""
        # Get voice channel
        if (
            isinstance(ctx.author, discord.User)
            or not hasattr(ctx.author, "voice")
            or not ctx.author.voice
            or not ctx.author.voice.channel
        ):
            embed = create_error_embed(
                "Error", "You must be in a voice channel to use this command!"
            )
            await ctx.send(embed=embed)
            return

        voice_channel = ctx.author.voice.channel

        # Connect to voice if not already connected
        try:
            if not ctx.voice_client:
                await voice_channel.connect()
                embed = create_embed("Connected", f"Joined {voice_channel.name}")
                await ctx.send(embed=embed)
            elif (
                hasattr(ctx.voice_client, "channel")
                and ctx.voice_client.channel != voice_channel
            ):
                if hasattr(ctx.voice_client, "move_to"):
                    voice_client: Any = ctx.voice_client
                    await voice_client.move_to(voice_channel)
                    embed = create_embed("Moved", f"Moved to {voice_channel.name}")
                    await ctx.send(embed=embed)
                else:
                    await ctx.voice_client.disconnect(force=True)
                    await voice_channel.connect()
                    embed = create_embed("Connected", f"Joined {voice_channel.name}")
                    await ctx.send(embed=embed)
            else:
                embed = create_embed(
                    "Already connected", f"Already in {voice_channel.name}"
                )
                await ctx.send(embed=embed)
        except discord.ClientException as e:
            if "already connected" in str(e).lower():
                embed = create_warning_embed(
                    "Already Connected", "I'm already connected to a voice channel."
                )
            else:
                embed = create_error_embed(
                    "Discord Connection Error",
                    f"Discord reported an issue: {str(e)[:100]}...\n\n"
                    "💡 **Try this:**\n"
                    "• Check bot permissions in voice channel\n"
                    "• Try the `leave` command first, then `join` again",
                )
            await ctx.send(embed=embed)
        except asyncio.TimeoutError:
            embed = create_error_embed(
                "Connection Timeout",
                "Connection to voice channel timed out.\n\n"
                "💡 **This might help:**\n"
                "• Check your internet connection\n"
                "• Try a different voice channel\n"
                "• Wait a moment and try again",
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Unexpected voice connection error: {e}")
            embed = create_error_embed(
                "Connection Failed",
                f"Unexpected error connecting to voice channel.\n\n"
                f"**Error:** {str(e)[:100]}...\n\n"
                "💡 **Try this:**\n"
                "• Check bot permissions\n"
                "• Try again in a few moments\n"
                "• Contact support if this persists",
            )
            await ctx.send(embed=embed)

    @commands.command(name="test")
    @is_in_voice_channel()
    async def test(self, ctx: commands.Context[commands.Bot]) -> None:
        """Test audio playback with a known working video"""
        # Get voice channel
        if (
            isinstance(ctx.author, discord.User)
            or not hasattr(ctx.author, "voice")
            or not ctx.author.voice
            or not ctx.author.voice.channel
        ):
            embed = create_error_embed("Error", "You must be in a voice channel!")
            await ctx.send(embed=embed)
            return

        voice_channel = ctx.author.voice.channel

        # Connect to voice if not already connected
        try:
            if not ctx.voice_client:
                await voice_channel.connect()
            elif (
                hasattr(ctx.voice_client, "channel")
                and ctx.voice_client.channel != voice_channel
            ):
                if hasattr(ctx.voice_client, "move_to"):
                    voice_client: Any = ctx.voice_client
                    await voice_client.move_to(voice_channel)
        except Exception as e:
            embed = create_error_embed("Connection failed", f"Could not connect: {e}")
            await ctx.send(embed=embed)
            return

        # Test with "Never Gonna Give You Up" - a well-known working video
        test_video = {
            "id": "dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up (Audio Test)",
            "channel": "RickAstleyVEVO",
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "platform": "youtube",
            "description": "Audio test video",
        }

        # Get audio player and set high volume
        if not ctx.guild:
            return
        player = self.bot.get_audio_player(ctx.guild.id)
        if isinstance(ctx.voice_client, discord.VoiceClient):
            player.voice_client = ctx.voice_client

        # Set volume to 100% for test
        player.set_volume(100)

        # Add to queue and play
        await player.add_to_queue(test_video)

        embed = create_embed(
            "🧪 Audio Test Started",
            f"Playing audio test video at 100% volume\n"
            f"**Video**: {test_video['title']}\n"
            f"**Channel**: {voice_channel.name}\n"
            f"**Volume**: 100%\n\n"
            f"If you can't hear this, check:\n"
            f"• Discord audio settings\n"
            f"• Bot permissions in voice channel\n"
            f"• Your device audio output",
        )
        await ctx.send(embed=embed)

        await player.play_next()

    @commands.command(name="play", aliases=["p"])
    @is_in_voice_channel()
    async def play(self, ctx: commands.Context[commands.Bot], *, query: str) -> None:
        """Play a song from any supported platform"""
        # Type checking for trigger_typing
        try:
            await ctx.trigger_typing()  # type: ignore
        except AttributeError:
            async with ctx.typing():
                pass

        # Perform the search early to satisfy tests and avoid connection errors
        if self.bot.searcher is None:
            embed = create_error_embed(
                "Service Unavailable",
                "Music search service is not available right now.\n\n"
                "💡 **Try this:**\n"
                "• Wait a moment and try again\n"
                "• Check if the bot is still starting up",
            )
            await ctx.send(embed=embed)
            return

        # Search with comprehensive error handling
        try:
            results: Dict[str, List[Dict[str, Any]]] = (
                await self.bot.searcher.search_all_platforms(query)
            )
        except CircuitBreakerOpenError:
            embed = create_error_embed(
                "Service Temporarily Unavailable",
                "Music search services are experiencing issues and are temporarily disabled.\n\n"
                "💡 **What you can do:**\n"
                "• Try again in a few minutes\n"
                "• Search services will automatically recover\n"
                "• Check service status with admin commands",
            )
            await ctx.send(embed=embed)
            return
        except MaxRetriesExceededError:
            embed = create_error_embed(
                "Search Failed",
                "Unable to search for music after multiple attempts.\n\n"
                "💡 **This might help:**\n"
                "• Check your internet connection\n"
                "• Try a simpler search term\n"
                "• Wait a moment and try again",
            )
            await ctx.send(embed=embed)
            return
        except NetworkTimeoutError:
            embed = create_error_embed(
                "Search Timeout",
                "Music search took too long and timed out.\n\n"
                "💡 **Try this:**\n"
                "• Use more specific search terms\n"
                "• Check your internet connection\n"
                "• Try again in a moment",
            )
            await ctx.send(embed=embed)
            return
        except Exception as e:
            logger.error(f"Unexpected search error: {e}")
            embed = create_error_embed(
                "Search Error",
                "An unexpected error occurred while searching for music.\n\n"
                f"**Error:** {str(e)[:100]}...\n\n"
                "💡 **Try this:**\n"
                "• Try a different search term\n"
                "• Wait a moment and try again\n"
                "• Contact support if this persists",
            )
            await ctx.send(embed=embed)
            return

        # Get voice channel
        if (
            isinstance(ctx.author, discord.User)
            or not hasattr(ctx.author, "voice")
            or not ctx.author.voice
            or not ctx.author.voice.channel
        ):
            await ctx.send("You must be in a voice channel to use this command!")
            return
        voice_channel = ctx.author.voice.channel

        # Connect to voice if not already connected with better error handling
        try:
            if not ctx.voice_client:
                await voice_channel.connect()
            elif (
                hasattr(ctx.voice_client, "channel")
                and ctx.voice_client.channel != voice_channel
            ):
                if hasattr(ctx.voice_client, "move_to"):
                    voice_client: Any = ctx.voice_client
                    await voice_client.move_to(voice_channel)
                else:
                    await ctx.voice_client.disconnect(force=True)
                    await voice_channel.connect()
        except discord.ClientException as e:
            logger.warning(f"Voice connection issue during play: {e}")
            # Continue with playback attempt - voice client might still work
        except Exception as e:
            logger.error(f"Failed to connect to voice for playback: {e}")
            embed = create_error_embed(
                "Voice Connection Failed",
                "Could not connect to voice channel for playback.\n\n"
                "💡 **Try this:**\n"
                "• Use the `join` command first\n"
                "• Check bot permissions in voice channel\n"
                "• Make sure you're in a voice channel",
            )
            await ctx.send(embed=embed)
            return

        # Search for the song
        # search already performed above

        if not any(results.values()):
            # Check if all platforms failed or just no results
            search_status = self.bot.searcher.get_search_health_status()
            platform_count = search_status.get("total_platforms", 0)

            if platform_count == 0:
                embed = create_error_embed(
                    "No Search Services",
                    "No music platforms are currently available.\n\n"
                    "💡 **This might mean:**\n"
                    "• Bot is still starting up\n"
                    "• All platforms are temporarily down\n"
                    "• Configuration issue",
                )
            else:
                # Check for common issues
                description = f"Could not find any results for: **{query}**\n\n"
                description += "💡 **Try this:**\n"
                description += "• Use different search terms\n"
                description += "• Try searching for the artist name\n"
                description += "• Use exact song titles\n"
                description += "• Try again in a few moments\n\n"

                # Add platform status if available
                if hasattr(self.bot.searcher, "get_search_health_status"):
                    status = self.bot.searcher.get_search_health_status()
                    enabled_platforms = status.get("enabled_platforms", [])
                    if enabled_platforms:
                        description += (
                            f"**Searched platforms:** {', '.join(enabled_platforms)}"
                        )

                embed = create_error_embed("No Results Found", description)

            await ctx.send(embed=embed)
            return

        # Create search results embed
        embed = create_embed(
            title="Search Results", description=f"Results for: **{query}**"
        )

        all_results: List[Dict[str, Any]] = []
        for platform, platform_results in results.items():
            if platform_results:
                # Add platform field
                platform_text = "\n".join(
                    [
                        f"{i+1}. [{r['title']}]({r['url']})"
                        for i, r in enumerate(platform_results[:3])
                    ]
                )
                embed.add_field(
                    name=f"{platform.title()} Results",
                    value=platform_text,
                    inline=False,
                )
                all_results.extend(platform_results[:3])

        # Send search results and wait for user selection
        embed.set_footer(text="Type the number of the song you want to play (1-9)")
        search_msg = await ctx.send(embed=embed)

        def check(m: "Message") -> bool:
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.isdigit()
                and 1 <= int(m.content) <= len(all_results)
            )

        try:
            msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            selected = all_results[int(msg.content) - 1]
        except asyncio.TimeoutError:
            embed = create_error_embed(
                "Selection timeout", "No selection made within 30 seconds"
            )
            await search_msg.edit(embed=embed)
            return

        # Get audio player
        if not ctx.guild:
            return
        player = self.bot.get_audio_player(ctx.guild.id)
        if isinstance(ctx.voice_client, discord.VoiceClient):
            player.voice_client = ctx.voice_client

        # Add to queue with error handling
        logger.info(f"Adding to queue: {selected}")
        logger.info(
            f"Selected {selected.get('platform', 'unknown')} ID: {selected.get('id')} (length: {len(selected.get('id', ''))})"
        )

        try:
            await player.add_to_queue(selected)  # type: ignore
        except ValueError as e:
            if "queue is full" in str(e).lower():
                embed = create_error_embed(
                    "Queue Full",
                    "The music queue is full. Please wait for some songs to finish or use the `stop` command to clear it.",
                )
            else:
                embed = create_error_embed(
                    "Queue Error", f"Could not add song to queue: {e}"
                )
            await ctx.send(embed=embed)
            return
        except Exception as e:
            logger.error(f"Unexpected error adding to queue: {e}")
            embed = create_error_embed(
                "Queue Error",
                "An unexpected error occurred while adding the song to queue.\n\n"
                "💡 **Try this:**\n"
                "• Try a different song\n"
                "• Use the `stop` command to reset the queue\n"
                "• Try again in a moment",
            )
            await ctx.send(embed=embed)
            return

        # Update embed
        embed = create_embed(
            title="Added to Queue",
            description=f"[{selected['title']}]({selected['url']})",
            color=discord.Color.green(),
        )
        embed.add_field(name="Platform", value=selected["platform"].title())
        embed.add_field(name="Channel", value=selected.get("channel", "Unknown"))

        await search_msg.edit(embed=embed)

        # Start playing if not already with error handling
        if not player.is_playing():  # type: ignore
            try:
                await player.play_next()  # type: ignore
            except Exception as e:
                logger.error(f"Error starting playback: {e}")
                embed = create_error_embed(
                    "Playback Error",
                    "Could not start playing the music.\n\n"
                    "💡 **Try this:**\n"
                    "• Make sure I'm connected to voice\n"
                    "• Check if the song URL is still valid\n"
                    "• Try the `join` command first",
                )
                await ctx.send(embed=embed)

    @commands.command(name="skip", aliases=["s"])
    @is_same_voice_channel()
    async def skip(self, ctx: commands.Context[commands.Bot]) -> None:
        """Skip the current song"""
        if not ctx.guild:
            return
        player = self.bot.get_audio_player(ctx.guild.id)

        if not player.is_playing():
            await ctx.send("Nothing is playing!")
            return

        # Get current song title before skipping
        current_title = (
            player.current.get("title", "Unknown") if player.current else "Unknown"
        )

        player.skip()

        embed = create_embed(
            title="Skipped",
            description=f"Skipped: {current_title}",
            color=discord.Color.blue(),
        )

        await ctx.send(embed=embed)

    @commands.command(name="stop")
    @is_same_voice_channel()
    async def stop(self, ctx: commands.Context[commands.Bot]) -> None:
        """Stop playback and clear the queue"""
        if not ctx.guild:
            return
        player = self.bot.get_audio_player(ctx.guild.id)
        player.stop()
        await ctx.send("⏹️ Stopped playback and cleared queue.")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context[commands.Bot]) -> None:
        """Display the current queue"""
        if not ctx.guild:
            return
        player = self.bot.get_audio_player(ctx.guild.id)
        queue: List[Dict[str, Any]] = player.get_queue()  # type: ignore

        if not queue and not player.current:  # type: ignore
            await ctx.send("The queue is empty.")
            return

        embed = create_embed(title="Music Queue", color=discord.Color.blue())

        # Add current song
        if player.current:  # type: ignore
            embed.add_field(
                name="Now Playing",
                value=(
                    f"[{player.current['title']}]"  # type: ignore
                    f"({player.current['url']})"  # type: ignore
                ),
                inline=False,
            )

        # Add queue items
        if queue:
            queue_text = "\n".join(
                [
                    f"{i+1}. [{item['title']}]({item['url']})"
                    for i, item in enumerate(queue[:10])
                ]
            )

            if len(queue) > 10:
                queue_text += f"\n\n... and {len(queue) - 10} more"

            embed.add_field(
                name=f"Up Next ({len(queue)} songs)", value=queue_text, inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="leave", aliases=["l", "disconnect", "dc"])
    @is_same_voice_channel()
    async def leave(self, ctx: commands.Context[commands.Bot]) -> None:
        """Leave the voice channel"""
        if ctx.voice_client and ctx.guild:
            player = self.bot.get_audio_player(ctx.guild.id)
            player.stop()
            await ctx.voice_client.disconnect(force=True)
            await ctx.send("👋 Left the voice channel.")
        else:
            await ctx.send("I'm not in a voice channel.")

    @commands.command(name="pause")
    @is_same_voice_channel()
    async def pause(self, ctx: commands.Context[commands.Bot]) -> None:
        """Pause the current song"""
        if not ctx.guild:
            return
        player = self.bot.get_audio_player(ctx.guild.id)

        if player.pause():
            await ctx.send("⏸️ Paused playback.")
        else:
            await ctx.send("Nothing is playing!")

    @commands.command(name="resume")
    @is_same_voice_channel()
    async def resume(self, ctx: commands.Context[commands.Bot]) -> None:
        """Resume playback"""
        if not ctx.guild:
            return
        player = self.bot.get_audio_player(ctx.guild.id)

        if player.resume():
            await ctx.send("▶️ Resumed playback.")
        else:
            await ctx.send("Nothing to resume!")

    @commands.command(name="volume", aliases=["v"])
    @is_same_voice_channel()
    async def volume(
        self, ctx: commands.Context[commands.Bot], volume: Optional[int] = None
    ) -> None:
        """Set or show the volume (0-100)"""
        if not ctx.guild:
            return
        player = self.bot.get_audio_player(ctx.guild.id)

        if volume is None:
            current = player.get_volume()
            await ctx.send(f"🔊 Current volume: {current}%")
        else:
            if 0 <= volume <= 100:
                player.set_volume(volume)
                await ctx.send(f"🔊 Volume set to {volume}%")
            else:
                await ctx.send("Volume must be between 0 and 100!")


async def setup(bot: "RobusttyBot") -> None:
    await bot.add_cog(Music(bot))
