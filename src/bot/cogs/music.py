import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import discord
from discord.ext import commands

from ..utils.checks import is_in_voice_channel, is_same_voice_channel
from ..utils.embeds import create_embed, create_error_embed  # type: ignore

if TYPE_CHECKING:
    from discord import Message

    from ..bot import RobusttyBot

logger = logging.getLogger(__name__)


class Music(commands.Cog):
    """Music commands for the bot"""

    def __init__(self, bot: "RobusttyBot") -> None:
        self.bot: "RobusttyBot" = bot
        
        # Load Discord voice timeout settings from environment
        self.voice_timeout = float(os.getenv("DISCORD_VOICE_TIMEOUT", "30"))
        self.reconnect_timeout = float(os.getenv("DISCORD_RECONNECT_TIMEOUT", "60"))
        
        logger.info(
            f"Discord voice timeout settings: "
            f"voice={self.voice_timeout}s, reconnect={self.reconnect_timeout}s"
        )

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

        # Connect to voice with enhanced error handling and reconnection
        try:
            if not ctx.voice_client:
                voice_client = await self._connect_with_retry(voice_channel)
                if voice_client:
                    # Set up audio player for this guild
                    guild_id = ctx.guild.id if ctx.guild else None
                    if guild_id and hasattr(self.bot, "audio_players"):
                        audio_player = self.bot.audio_players.get(guild_id)
                        if audio_player:
                            audio_player.voice_client = voice_client
                    embed = create_embed("Connected", f"Joined {voice_channel.name}")
                    await ctx.send(embed=embed)
                else:
                    embed = create_error_embed(
                        "Connection failed",
                        "Unable to connect to voice channel after multiple attempts. "
                "This may be due to Discord voice server issues or network "
                "connectivity problems.",
                    )
                    await ctx.send(embed=embed)
                    return
            elif (
                hasattr(ctx.voice_client, "channel")
                and ctx.voice_client.channel != voice_channel
            ):
                if hasattr(ctx.voice_client, "move_to"):
                    try:
                        current_voice_client: Any = ctx.voice_client
                        await asyncio.wait_for(
                            current_voice_client.move_to(voice_channel),
                            timeout=self.voice_timeout
                        )
                        embed = create_embed("Moved", f"Moved to {voice_channel.name}")
                        await ctx.send(embed=embed)
                    except asyncio.TimeoutError:
                        logger.warning("Move operation timed out, attempting reconnect")
                        await ctx.voice_client.disconnect(force=True)
                        voice_client = await self._connect_with_retry(voice_channel)
                        if voice_client:
                            guild_id = ctx.guild.id if ctx.guild else None
                            if guild_id and hasattr(self.bot, "audio_players"):
                                audio_player = self.bot.audio_players.get(guild_id)
                                if audio_player:
                                    audio_player.voice_client = voice_client
                            embed = create_embed(
                                "Connected", f"Joined {voice_channel.name}"
                            )
                            await ctx.send(embed=embed)
                        else:
                            embed = create_error_embed(
                                "Connection failed",
                                "Failed to move or reconnect to voice channel",
                            )
                            await ctx.send(embed=embed)
                            return
                else:
                    await ctx.voice_client.disconnect(force=True)
                    await asyncio.sleep(1)  # Brief pause after disconnect
                    voice_client = await self._connect_with_retry(voice_channel)
                    if voice_client:
                        # Update audio player
                        guild_id = ctx.guild.id if ctx.guild else None
                        if guild_id and hasattr(self.bot, "audio_players"):
                            audio_player = self.bot.audio_players.get(guild_id)
                            if audio_player:
                                audio_player.voice_client = voice_client
                        embed = create_embed(
                            "Connected", f"Joined {voice_channel.name}"
                        )
                        await ctx.send(embed=embed)
                    else:
                        embed = create_error_embed(
                            "Connection failed", "Failed to reconnect to voice channel"
                        )
                        await ctx.send(embed=embed)
                        return
            else:
                # Check if connection is actually working
                if not ctx.voice_client.is_connected():
                    await ctx.voice_client.disconnect(force=True)
                    await asyncio.sleep(1)  # Brief pause after disconnect
                    voice_client = await self._connect_with_retry(voice_channel)
                    if voice_client:
                        guild_id = ctx.guild.id if ctx.guild else None
                        if guild_id and hasattr(self.bot, "audio_players"):
                            audio_player = self.bot.audio_players.get(guild_id)
                            if audio_player:
                                audio_player.voice_client = voice_client
                        embed = create_embed(
                            "Reconnected", f"Reconnected to {voice_channel.name}"
                        )
                        await ctx.send(embed=embed)
                    else:
                        embed = create_error_embed(
                            "Reconnection failed",
                            "Unable to reconnect to voice channel",
                        )
                        await ctx.send(embed=embed)
                        return
                else:
                    embed = create_embed(
                        "Already connected", f"Already in {voice_channel.name}"
                    )
                    await ctx.send(embed=embed)
        except asyncio.TimeoutError:
            logger.error("Voice connection operation timed out")
            embed = create_error_embed(
                "Connection timeout",
                "Voice connection operation timed out. Please try again.",
            )
            await ctx.send(embed=embed)
        except discord.errors.ConnectionClosed as e:
            logger.error(f"Discord connection closed during voice connection: {e}")
            embed = create_error_embed(
                "Discord connection error",
                "Discord voice connection was closed. This may indicate "
                "server issues or rate limiting. Please wait a moment and "
                "try again.",
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Voice connection error: {type(e).__name__}: {e}")
            embed = create_error_embed(
                "Connection failed",
                f"Could not connect to voice channel: {type(e).__name__}",
            )
            await ctx.send(embed=embed)

    async def _connect_with_retry(
        self, voice_channel, max_retries: int = 5
    ) -> Optional[discord.VoiceClient]:
        """Connect to voice channel with enhanced retry logic and proper cleanup"""
        voice_client = None
        logger.info(
            f"🎵 Starting voice connection to {voice_channel.name} "
            f"(max {max_retries} attempts) with timeouts: "
            f"voice={self.voice_timeout}s, reconnect={self.reconnect_timeout}s"
        )

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Attempting to connect to voice channel {voice_channel.name} "
                    f"(attempt {attempt + 1})"
                )

                # Clean up any existing failed connection
                if voice_client:
                    try:
                        await voice_client.disconnect(force=True)
                        await asyncio.sleep(0.5)  # Brief pause for cleanup
                    except Exception as cleanup_error:
                        logger.debug(
                            f"Error during connection cleanup: {cleanup_error}"
                        )
                    finally:
                        voice_client = None

                # Use configured timeouts to reduce 4006 errors
                # Allow Discord more time to establish stable connections
                try:
                    if attempt == 0:
                        # First attempt: use configured voice timeout
                        voice_client = await asyncio.wait_for(
                            voice_channel.connect(
                                timeout=self.voice_timeout, reconnect=False
                            ),
                            timeout=self.voice_timeout + 5,
                        )
                    elif attempt == 1:
                        # Second attempt: use reconnect timeout for more patience
                        voice_client = await asyncio.wait_for(
                            voice_channel.connect(
                                timeout=self.reconnect_timeout, reconnect=False
                            ),
                            timeout=self.reconnect_timeout + 10,
                        )
                    else:
                        # Later attempts: maximum timeout but ensure reconnect is
                        # disabled
                        # to prevent Discord's built-in retry interference
                        max_timeout = max(
                            self.voice_timeout, self.reconnect_timeout
                        )
                        voice_client = await asyncio.wait_for(
                            voice_channel.connect(
                                timeout=max_timeout, reconnect=False
                            ),
                            timeout=max_timeout + 15,
                        )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Connection attempt {attempt + 1} timed out after "
                        f"configured timeout"
                    )
                    voice_client = None
                    # Don't continue to validation - let our retry logic handle it
                    if attempt < max_retries - 1:
                        continue
                    else:
                        break

                # Validate connection stability
                if voice_client and voice_client.is_connected():
                    # Test connection with a brief wait
                    await asyncio.sleep(1.5)

                    # Double-check connection is still stable
                    if voice_client.is_connected():
                        logger.info(f"Successfully connected to {voice_channel.name}")
                        return voice_client
                    else:
                        logger.warning(
                            f"Connection became unstable immediately after "
                            f"connecting (attempt {attempt + 1})"
                        )
                        continue
                else:
                    logger.warning(
                        f"Connection failed validation on attempt {attempt + 1}"
                    )
                    continue

            except asyncio.TimeoutError:
                logger.warning(f"Voice connection attempt {attempt + 1} timed out")
            except discord.errors.ConnectionClosed as e:
                logger.warning(
                    f"Voice connection attempt {attempt + 1} failed with "
                    f"ConnectionClosed: {e}"
                )
                # For error 4006, implement aggressive backoff
                if hasattr(e, "code") and e.code == 4006:
                    logger.error(
                        f"🚨 Discord Error 4006 detected on attempt {attempt + 1} - "
                        f"voice servers unavailable"
                    )
                    if attempt < max_retries - 1:
                        # Exponentially increasing delays for 4006 errors,
                        # scaled with reconnect timeout
                        base_delay = max(30, self.reconnect_timeout)
                        delay = min(base_delay * (2**attempt), 180)  # Cap at 3 minutes
                        logger.warning(
                            f"⏰ Implementing {delay}s cooling-off period for "
                            f"error 4006..."
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(
                            "❌ All attempts failed with error 4006 - "
                            "Discord voice infrastructure issue"
                        )
            except Exception as e:
                logger.warning(
                    f"Voice connection attempt {attempt + 1} failed: {type(e).__name__}: {e}"
                )

            # Clean up failed connection attempt
            if voice_client:
                try:
                    await voice_client.disconnect(force=True)
                    await asyncio.sleep(0.5)
                except Exception as cleanup_error:
                    logger.debug(
                        f"Error cleaning up failed connection: {cleanup_error}"
                    )
                finally:
                    voice_client = None

            # Exponential backoff with jitter for non-4006 errors,
            # scaled with configured timeouts
            if attempt < max_retries - 1:
                base_delay = min(
                    (2**attempt) * max(3, self.voice_timeout / 10), 
                    max(15, self.voice_timeout / 2)
                )  # Scale with voice timeout, reasonable cap
                jitter = base_delay * 0.1  # Add 10% jitter
                retry_delay = base_delay + jitter
                logger.info(
                    f"⏳ Retrying voice connection in {retry_delay:.1f} seconds..."
                )
                await asyncio.sleep(retry_delay)

        logger.error(f"Failed to connect to voice channel after {max_retries} attempts")
        return None

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

        # Connect to voice if not already connected using retry logic
        try:
            if not ctx.voice_client:
                test_voice_client = await self._connect_with_retry(voice_channel)
                if not test_voice_client:
                    embed = create_error_embed(
                        "Connection failed",
                        "Unable to connect to voice channel after multiple attempts. "
                        "This may be due to Discord voice server issues or network "
                        "connectivity problems."
                    )
                    await ctx.send(embed=embed)
                    return
                # Set up audio player for this guild
                guild_id = ctx.guild.id if ctx.guild else None
                if guild_id and hasattr(self.bot, 'audio_players'):
                    audio_player = self.bot.audio_players.get(guild_id)
                    if audio_player:
                        audio_player.voice_client = test_voice_client
            elif (
                hasattr(ctx.voice_client, "channel")
                and ctx.voice_client.channel != voice_channel
            ):
                if hasattr(ctx.voice_client, "move_to"):
                    try:
                        existing_test_client: Any = ctx.voice_client
                        await asyncio.wait_for(
                            existing_test_client.move_to(voice_channel),
                            timeout=self.voice_timeout
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Move operation timed out, attempting reconnect with "
                            "retry logic"
                        )
                        await ctx.voice_client.disconnect(force=True)
                        reconnected_test_client = await self._connect_with_retry(
                            voice_channel
                        )
                        if not reconnected_test_client:
                            embed = create_error_embed(
                                "Connection failed",
                                "Failed to move or reconnect to voice channel"
                            )
                            await ctx.send(embed=embed)
                            return
                        guild_id = ctx.guild.id if ctx.guild else None
                        if guild_id and hasattr(self.bot, 'audio_players'):
                            audio_player = self.bot.audio_players.get(guild_id)
                            if audio_player:
                                audio_player.voice_client = reconnected_test_client
                else:
                    await ctx.voice_client.disconnect(force=True)
                    await asyncio.sleep(1)  # Brief pause after disconnect
                    fallback_test_client = await self._connect_with_retry(voice_channel)
                    if not fallback_test_client:
                        embed = create_error_embed(
                            "Connection failed", 
                            "Failed to reconnect to voice channel"
                        )
                        await ctx.send(embed=embed)
                        return
                    # Update audio player
                    guild_id = ctx.guild.id if ctx.guild else None
                    if guild_id and hasattr(self.bot, 'audio_players'):
                        audio_player = self.bot.audio_players.get(guild_id)
                        if audio_player:
                            audio_player.voice_client = fallback_test_client
        except Exception as e:
            logger.error(
                f"Voice connection error in test command: "
                f"{type(e).__name__}: {e}"
            )
            embed = create_error_embed(
                "Connection failed", 
                f"Could not connect: {type(e).__name__}"
            )
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
            embed = create_error_embed("Bot error", "Searcher not initialized")
            await ctx.send(embed=embed)
            return
        results: Dict[str, List[Dict[str, Any]]] = (
            await self.bot.searcher.search_all_platforms(query)
        )

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

        # Connect to voice if not already connected using retry logic
        try:
            if not ctx.voice_client:
                play_voice_client = await self._connect_with_retry(voice_channel)
                if not play_voice_client:
                    embed = create_error_embed(
                        "Connection failed",
                        "Unable to connect to voice channel after multiple attempts. "
                        "This may be due to Discord voice server issues or network "
                        "connectivity problems."
                    )
                    await ctx.send(embed=embed)
                    return
                # Set up audio player for this guild
                guild_id = ctx.guild.id if ctx.guild else None
                if guild_id and hasattr(self.bot, 'audio_players'):
                    audio_player = self.bot.audio_players.get(guild_id)
                    if audio_player:
                        audio_player.voice_client = play_voice_client
            elif (
                hasattr(ctx.voice_client, "channel")
                and ctx.voice_client.channel != voice_channel
            ):
                if hasattr(ctx.voice_client, "move_to"):
                    try:
                        existing_play_client: Any = ctx.voice_client
                        await asyncio.wait_for(
                            existing_play_client.move_to(voice_channel),
                            timeout=self.voice_timeout
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Move operation timed out, attempting reconnect with "
                            "retry logic"
                        )
                        await ctx.voice_client.disconnect(force=True)
                        reconnected_play_client = await self._connect_with_retry(
                            voice_channel
                        )
                        if not reconnected_play_client:
                            embed = create_error_embed(
                                "Connection failed",
                                "Failed to move or reconnect to voice channel"
                            )
                            await ctx.send(embed=embed)
                            return
                        guild_id = ctx.guild.id if ctx.guild else None
                        if guild_id and hasattr(self.bot, 'audio_players'):
                            audio_player = self.bot.audio_players.get(guild_id)
                            if audio_player:
                                audio_player.voice_client = reconnected_play_client
                else:
                    await ctx.voice_client.disconnect(force=True)
                    await asyncio.sleep(1)  # Brief pause after disconnect
                    fallback_play_client = await self._connect_with_retry(voice_channel)
                    if not fallback_play_client:
                        embed = create_error_embed(
                            "Connection failed", 
                            "Failed to reconnect to voice channel"
                        )
                        await ctx.send(embed=embed)
                        return
                    # Update audio player
                    guild_id = ctx.guild.id if ctx.guild else None
                    if guild_id and hasattr(self.bot, 'audio_players'):
                        audio_player = self.bot.audio_players.get(guild_id)
                        if audio_player:
                            audio_player.voice_client = fallback_play_client
        except Exception as e:
            logger.error(
                f"Voice connection error in play command: "
                f"{type(e).__name__}: {e}"
            )
            embed = create_error_embed(
                "Connection failed", 
                f"Could not connect to voice channel: {type(e).__name__}"
            )
            await ctx.send(embed=embed)
            return

        # Search for the song
        # search already performed above

        if not any(results.values()):
            embed = create_error_embed(
                "No results found", f"Could not find any results for: {query}"
            )
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

        # Send search results
        search_msg = await ctx.send(embed=embed)

        # If only one result, play it automatically
        if len(all_results) == 1:
            selected: Dict[str, Any] = all_results[0]
        else:
            # Wait for user selection
            embed.set_footer(text="Type the number of the song you want to play (1-9)")
            await search_msg.edit(embed=embed)

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

        # Add to queue
        logger.info(f"Adding to queue: {selected}")
        logger.info(
            f"Selected YouTube ID: {selected.get('id')} "
            f"(length: {len(selected.get('id', ''))})"
        )
        await player.add_to_queue(selected)  # type: ignore

        # Update embed
        embed = create_embed(
            title="Added to Queue",
            description=f"[{selected['title']}]({selected['url']})",
            color=discord.Color.green(),
        )
        embed.add_field(name="Platform", value=selected["platform"].title())
        embed.add_field(name="Channel", value=selected.get("channel", "Unknown"))

        await search_msg.edit(embed=embed)

        # Start playing if not already
        if not player.is_playing():  # type: ignore
            await player.play_next()  # type: ignore

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
