import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import discord
from discord.ext import commands

from ..utils.checks import is_in_voice_channel, is_same_voice_channel
from ..utils.embeds import (
    create_embed, 
    create_error_embed, 
    create_warning_embed,
    create_music_embed,
    create_multi_platform_status_embed,
    create_quota_exceeded_embed,
    create_fallback_success_embed,
    create_all_methods_failed_embed,
)  # type: ignore
from ...utils.network_resilience import (
    CircuitBreakerOpenError,
    MaxRetriesExceededError,
    NetworkTimeoutError,
)
from ...services.status_reporting import (
    SearchMethod,
    PlatformStatus,
    MultiPlatformStatus,
)

if TYPE_CHECKING:
    from discord import Message

    from ..bot import RobusttyBot

logger = logging.getLogger(__name__)


class Music(commands.Cog):
    """Music commands for the bot"""

    def __init__(self, bot: "RobusttyBot") -> None:
        self.bot: "RobusttyBot" = bot
        
        # URL patterns for direct platform detection - enhanced to handle parameters
        self.youtube_url_patterns = [
            re.compile(r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:m\.)?youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]+)"),
            re.compile(r"(?:https?:\/\/)?(?:music\.)?youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]+)"),
        ]

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
            "search_status",
        ]:
            cmd_obj = getattr(type(self), cmd_name)
            if hasattr(cmd_obj, "callback"):
                func = cmd_obj.callback.__get__(self, type(self))
                setattr(self, cmd_name, func)
    
    def _detect_youtube_url(self, query: str) -> Optional[str]:
        """Detect and extract YouTube video ID from URL"""
        for pattern in self.youtube_url_patterns:
            match = pattern.search(query.strip())
            if match:
                return match.group(1)
        return None
    
    def _is_direct_url(self, query: str) -> bool:
        """Check if query is a direct URL (not just a search term)"""
        # Check for common URL patterns
        url_indicators = [
            "http://", "https://", "www.", 
            "youtube.com", "youtu.be", "rumble.com", 
            "odysee.com", "peertube"
        ]
        query_lower = query.lower().strip()
        return any(indicator in query_lower for indicator in url_indicators)
    
    async def _handle_direct_youtube_url(self, ctx: commands.Context[commands.Bot], video_id: str, original_url: str) -> Optional[Dict[str, Any]]:
        """Handle direct YouTube URL with immediate metadata extraction"""
        try:
            # Get YouTube platform from registry
            youtube_platform = None
            if hasattr(self.bot, 'platform_registry'):
                youtube_platform = self.bot.platform_registry.get_platform('youtube')
            
            if not youtube_platform:
                logger.warning("YouTube platform not available for direct URL processing")
                return None
            
            # Show user that we're processing the direct URL
            embed = create_embed(
                "Processing Direct URL",
                f"Extracting metadata from YouTube URL...\n[{original_url}]({original_url})",
                color=discord.Color.orange()
            )
            status_msg = await ctx.send(embed=embed)
            
            # Extract video details directly
            video_details = await youtube_platform.get_video_details(video_id)
            
            if video_details:
                # Update status message with metadata
                embed = create_embed(
                    "Direct URL Processed",
                    f"Found video: **{video_details['title']}**",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Channel", value=video_details.get('channel', 'Unknown'), inline=True
                )
                if video_details.get('duration') and video_details['duration'] != 'Unknown':
                    embed.add_field(
                        name="Duration", value=video_details['duration'], inline=True
                    )
                if video_details.get('views') and video_details['views'] != 'Unknown views':
                    embed.add_field(
                        name="Views", value=video_details['views'], inline=True
                    )
                
                # Add thumbnail if available
                if video_details.get('thumbnail'):
                    embed.set_thumbnail(url=video_details['thumbnail'])
                
                embed.set_footer(text="✅ Direct URL processing - No API quota used")
                await status_msg.edit(embed=embed)
                
                logger.info(f"Successfully processed direct YouTube URL: {video_id} - {video_details['title']}")
                return video_details
            else:
                # Update status message with error
                embed = create_error_embed(
                    "Direct URL Failed",
                    "Could not extract metadata from the YouTube URL.\n\n"
                    "💡 **Falling back to search mode**"
                )
                await status_msg.edit(embed=embed)
                return None
                
        except Exception as e:
            logger.error(f"Error processing direct YouTube URL {video_id}: {e}")
            # Show fallback message
            embed = create_warning_embed(
                "Direct URL Processing Failed",
                f"Could not process direct URL: {str(e)}\n\n"
                "💡 **Falling back to search mode**"
            )
            try:
                await ctx.send(embed=embed)
            except:
                pass  # Don't fail if we can't send the message
            return None
    
    async def _handle_generic_direct_url(self, ctx: commands.Context[commands.Bot], query: str) -> Optional[Dict[str, Any]]:
        """Handle direct URLs from other platforms"""
        try:
            # Check which platform can handle this URL
            if hasattr(self.bot, 'platform_registry'):
                for platform_name, platform in self.bot.platform_registry.platforms.items():
                    if hasattr(platform, 'is_platform_url') and platform.is_platform_url(query):
                        # Show processing message
                        embed = create_embed(
                            "Processing Direct URL",
                            f"Extracting metadata from {platform_name.title()} URL...\n[{query}]({query})",
                            color=discord.Color.orange()
                        )
                        status_msg = await ctx.send(embed=embed)
                        
                        # Extract video ID and get details
                        video_id = platform.extract_video_id(query)
                        if video_id and hasattr(platform, 'get_video_details'):
                            video_details = await platform.get_video_details(video_id)
                            if video_details:
                                # Update with success
                                embed = create_embed(
                                    "Direct URL Processed",
                                    f"Found video: **{video_details['title']}**",
                                    color=discord.Color.green()
                                )
                                embed.add_field(
                                    name="Platform", value=platform_name.title(), inline=True
                                )
                                embed.add_field(
                                    name="Channel", value=video_details.get('channel', 'Unknown'), inline=True
                                )
                                embed.set_footer(text="✅ Direct URL processing - No API quota used")
                                await status_msg.edit(embed=embed)
                                return video_details
                        
                        # If we get here, processing failed
                        embed = create_warning_embed(
                            "Direct URL Processing Failed",
                            f"Could not extract metadata from {platform_name.title()} URL.\n\n"
                            "💡 **Falling back to search mode**"
                        )
                        await status_msg.edit(embed=embed)
                        break
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing direct URL {query}: {e}")
            return None

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

        # Check for direct URL input first
        selected_video = None
        is_direct_url = self._is_direct_url(query)
        
        if is_direct_url:
            logger.info(f"Detected direct URL input: {query}")
            
            # Check for YouTube URL specifically
            youtube_video_id = self._detect_youtube_url(query)
            if youtube_video_id:
                logger.info(f"YouTube URL detected - bypassing search to save API quota. Video ID: {youtube_video_id}")
                selected_video = await self._handle_direct_youtube_url(ctx, youtube_video_id, query)
            else:
                # Try other platforms
                logger.info(f"Non-YouTube URL detected - checking other platforms for direct processing")
                selected_video = await self._handle_generic_direct_url(ctx, query)
        
        # If direct URL processing succeeded, skip search
        if selected_video:
            logger.info(f"Direct URL processing successful, skipping search for: {selected_video['title']}")
        else:
            # Either not a direct URL or direct URL processing failed - proceed with search
            if is_direct_url:
                logger.info("Direct URL processing failed, falling back to search")
                # Add a small delay to let users see the fallback message
                await asyncio.sleep(1)
            
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

            # Handle search results (only if direct URL processing didn't succeed)
            if not any(results.values()):
                # Get detailed search status
                search_status_multi = self.bot.searcher.get_last_search_status()
                
                if search_status_multi:
                    # Use enhanced status reporting
                    if search_status_multi.get_quota_exceeded_platforms():
                        quota_platforms = search_status_multi.get_quota_exceeded_platforms()
                        platform_errors = {platform: "API quota exceeded" for platform in quota_platforms}
                        
                        # Check if other platforms also failed
                        other_failed = [p for p in search_status_multi.failed_platforms if p not in quota_platforms]
                        for platform in other_failed:
                            report = search_status_multi.platform_reports.get(platform)
                            if report:
                                platform_errors[platform] = report.user_message
                        
                        embed = create_all_methods_failed_embed(query, platform_errors)
                    else:
                        # Create multi-platform status embed
                        embed = create_multi_platform_status_embed(search_status_multi)
                        embed.title = "❌ No Results Found"
                        embed.description = f"No results found for: **{query}**\n\n" + (embed.description or "")
                else:
                    # Fallback to basic error handling
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

            # Create search results embed with status information
            search_status_multi = self.bot.searcher.get_last_search_status()
            
            # Determine title and description based on status
            title = "🔍 Search Results"
            description = f"Results for: **{query}**"
            
            if search_status_multi:
                if search_status_multi.has_fallbacks():
                    title = "🔄 Search Results (Fallback Methods Used)"
                    fallback_platforms = search_status_multi.get_fallback_platforms()
                    quota_platforms = search_status_multi.get_quota_exceeded_platforms()
                    
                    if quota_platforms:
                        description += f"\n⚠️ *API quota exceeded on: {', '.join(quota_platforms)}*"
                    if fallback_platforms:
                        description += f"\n🔄 *Using fallback methods on: {', '.join(fallback_platforms)}*"
                elif is_direct_url:
                    title = "🔗 Direct URL Results"
                    description += "\n✅ *Direct URL processing successful*"
            
            embed = create_embed(title=title, description=description)

            all_results: List[Dict[str, Any]] = []
            for platform, platform_results in results.items():
                if platform_results:
                    # Enhanced platform field with more metadata
                    platform_lines = []
                    for i, r in enumerate(platform_results[:3]):
                        title = r["title"]
                        channel = r.get("channel", "Unknown")
                        duration = r.get("duration", "")
                        views = r.get("views", "")

                        # Create a rich description line
                        desc_parts = [f"**{channel}**"]
                        if duration and duration != "Unknown":
                            desc_parts.append(f"({duration}")
                            if views and views != "Unknown views":
                                desc_parts.append(f" • {views})")
                            else:
                                desc_parts.append(")")
                        elif views and views != "Unknown views":
                            desc_parts.append(f"({views})")

                        platform_lines.append(
                            f"{i+1}. [{title}]({r['url']})\n    {' '.join(desc_parts)}"
                        )

                    platform_text = "\n".join(platform_lines)
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
                selected_video = all_results[int(msg.content) - 1]
            except asyncio.TimeoutError:
                embed = create_error_embed(
                    "Selection timeout", "No selection made within 30 seconds"
                )
                await search_msg.edit(embed=embed)
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

        # Get audio player
        if not ctx.guild:
            return
        player = self.bot.get_audio_player(ctx.guild.id)
        if isinstance(ctx.voice_client, discord.VoiceClient):
            player.voice_client = ctx.voice_client

        # Add to queue with error handling
        logger.info(f"Adding to queue: {selected_video}")
        logger.info(
            f"Selected {selected_video.get('platform', 'unknown')} ID: {selected_video.get('id')} (length: {len(selected_video.get('id', ''))})"
        )

        try:
            await player.add_to_queue(selected_video)  # type: ignore
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

        # Update embed - handle both direct URL and search scenarios with detailed method info
        used_direct_url = is_direct_url and not ('results' in locals() and any(results.values()))
        processing_method = "Search"
        method_footer = ""
        
        # Determine the method used based on status
        search_status_multi = self.bot.searcher.get_last_search_status()
        if used_direct_url:
            processing_method = "Direct URL Processing"
            method_footer = "Bypassed search - Direct URL metadata extraction"
        elif search_status_multi:
            platform_name = selected_video["platform"]
            platform_report = search_status_multi.platform_reports.get(platform_name)
            
            if platform_report:
                if platform_report.method == SearchMethod.YTDLP_SEARCH:
                    processing_method = "yt-dlp Fallback"
                    if platform_report.status == PlatformStatus.QUOTA_EXCEEDED:
                        method_footer = "Used yt-dlp fallback due to API quota exceeded"
                    else:
                        method_footer = "Used yt-dlp fallback (no API key configured)"
                elif platform_report.method == SearchMethod.DIRECT_URL:
                    processing_method = "Direct URL Processing"
                    method_footer = "Bypassed search - Direct URL metadata extraction"
                elif platform_report.method == SearchMethod.API_SEARCH:
                    processing_method = "API Search"
                    method_footer = "Standard API search"
                elif platform_report.method == SearchMethod.MIRROR_SEARCH:
                    processing_method = "Mirror Search"
                    method_footer = "Found on platform while searching for mirrors"
        
        # Determine search method for the embed
        search_method = None
        if search_status_multi and not used_direct_url:
            platform_name = selected_video["platform"]
            platform_report = search_status_multi.platform_reports.get(platform_name)
            if platform_report:
                search_method = platform_report.method
        elif used_direct_url:
            search_method = SearchMethod.DIRECT_URL
        
        # Use the enhanced music embed with fallback indicators
        embed = create_music_embed(selected_video, queued=True, search_method=search_method)
        
        # Add method field for transparency
        embed.add_field(
            name="Method", value=processing_method, inline=True
        )
        
        # Add views if available (YouTube)
        views = selected_video.get("views")
        if views and views != "Unknown views":
            embed.add_field(name="Views", value=views, inline=True)
        
        # Override footer if we have a specific method footer
        if method_footer and not embed.footer:
            embed.set_footer(text=method_footer)

        # Send or edit the appropriate message
        if not used_direct_url and 'search_msg' in locals():
            await search_msg.edit(embed=embed)
        else:
            # For direct URL or when search_msg doesn't exist, send a new message
            await ctx.send(embed=embed)

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
            queue_lines = []
            for i, item in enumerate(queue[:10]):
                title = item["title"]
                url = item["url"]
                channel = item.get("channel", "Unknown")
                duration = item.get("duration", "")

                # Create enhanced queue line
                line = f"{i+1}. [{title}]({url})"
                if channel != "Unknown" or (duration and duration != "Unknown"):
                    details = []
                    if channel != "Unknown":
                        details.append(f"**{channel}**")
                    if duration and duration != "Unknown":
                        details.append(f"({duration})")
                    line += f"\n    {' '.join(details)}"

                queue_lines.append(line)

            queue_text = "\n".join(queue_lines)

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

    @commands.command(name="searchstatus", aliases=["sstatus", "ss"])
    async def search_status(self, ctx: commands.Context[commands.Bot]) -> None:
        """Show the status of the last search operation"""
        if not self.bot.searcher:
            embed = create_error_embed(
                "Service Unavailable", 
                "Search service is not available right now."
            )
            await ctx.send(embed=embed)
            return
        
        search_status = self.bot.searcher.get_last_search_status()
        if not search_status:
            embed = create_embed(
                "No Recent Searches",
                "No search operations have been performed yet.\n\n"
                "Use the `play` command to search for music and see detailed status information.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        # Create detailed status embed
        embed = create_multi_platform_status_embed(search_status)
        await ctx.send(embed=embed)


async def setup(bot: "RobusttyBot") -> None:
    await bot.add_cog(Music(bot))