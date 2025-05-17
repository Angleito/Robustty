import discord
from discord.ext import commands
import logging
from typing import Optional
from ..utils.embeds import create_embed, create_error_embed
from ..utils.checks import is_in_voice_channel, is_same_voice_channel

logger = logging.getLogger(__name__)

class Music(commands.Cog):
    """Music commands for the bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='play', aliases=['p'])
    @is_in_voice_channel()
    async def play(self, ctx, *, query: str):
        """Play a song from any supported platform"""
        async with ctx.typing():
            # Get voice channel
            voice_channel = ctx.author.voice.channel
            
            # Connect to voice if not already connected
            if not ctx.voice_client:
                await voice_channel.connect()
            elif ctx.voice_client.channel != voice_channel:
                await ctx.voice_client.move_to(voice_channel)
            
            # Search for the song
            results = await self.bot.searcher.search_all_platforms(query)
            
            if not any(results.values()):
                embed = create_error_embed("No results found", f"Could not find any results for: {query}")
                return await ctx.send(embed=embed)
            
            # Create search results embed
            embed = create_embed(
                title="Search Results",
                description=f"Results for: **{query}**"
            )
            
            all_results = []
            for platform, platform_results in results.items():
                if platform_results:
                    # Add platform field
                    platform_text = "\n".join([
                        f"{i+1}. [{r['title']}]({r['url']})"
                        for i, r in enumerate(platform_results[:3])
                    ])
                    embed.add_field(
                        name=f"{platform.title()} Results",
                        value=platform_text,
                        inline=False
                    )
                    all_results.extend(platform_results[:3])
            
            # Send search results
            search_msg = await ctx.send(embed=embed)
            
            # If only one result, play it automatically
            if len(all_results) == 1:
                selected = all_results[0]
            else:
                # Wait for user selection
                embed.set_footer(text="Type the number of the song you want to play (1-9)")
                await search_msg.edit(embed=embed)
                
                def check(m):
                    return (m.author == ctx.author and 
                           m.channel == ctx.channel and 
                           m.content.isdigit() and 
                           1 <= int(m.content) <= len(all_results))
                
                try:
                    msg = await self.bot.wait_for('message', timeout=30.0, check=check)
                    selected = all_results[int(msg.content) - 1]
                except:
                    embed = create_error_embed("Selection timeout", "No selection made within 30 seconds")
                    await search_msg.edit(embed=embed)
                    return
            
            # Get audio player
            player = self.bot.get_audio_player(ctx.guild.id)
            player.voice_client = ctx.voice_client
            
            # Add to queue
            await player.add_to_queue(selected)
            
            # Update embed
            embed = create_embed(
                title="Added to Queue",
                description=f"[{selected['title']}]({selected['url']})",
                color=discord.Color.green()
            )
            embed.add_field(name="Platform", value=selected['platform'].title())
            embed.add_field(name="Channel", value=selected.get('channel', 'Unknown'))
            
            await search_msg.edit(embed=embed)
            
            # Start playing if not already
            if not player.is_playing():
                await player.play_next()
    
    @commands.command(name='skip', aliases=['s'])
    @is_same_voice_channel()
    async def skip(self, ctx):
        """Skip the current song"""
        player = self.bot.get_audio_player(ctx.guild.id)
        
        if not player.is_playing():
            return await ctx.send("Nothing is playing!")
        
        player.skip()
        await ctx.send("⏭️ Skipped current song!")
    
    @commands.command(name='stop')
    @is_same_voice_channel()
    async def stop(self, ctx):
        """Stop playback and clear the queue"""
        player = self.bot.get_audio_player(ctx.guild.id)
        player.stop()
        await ctx.send("⏹️ Stopped playback and cleared queue.")
    
    @commands.command(name='queue', aliases=['q'])
    async def queue(self, ctx):
        """Display the current queue"""
        player = self.bot.get_audio_player(ctx.guild.id)
        queue = player.get_queue()
        
        if not queue and not player.current:
            return await ctx.send("The queue is empty.")
        
        embed = create_embed(title="Music Queue", color=discord.Color.blue())
        
        # Add current song
        if player.current:
            embed.add_field(
                name="Now Playing",
                value=f"[{player.current['title']}]({player.current['url']})",
                inline=False
            )
        
        # Add queue items
        if queue:
            queue_text = "\n".join([
                f"{i+1}. [{item['title']}]({item['url']})"
                for i, item in enumerate(queue[:10])
            ])
            
            if len(queue) > 10:
                queue_text += f"\n\n... and {len(queue) - 10} more"
            
            embed.add_field(
                name=f"Up Next ({len(queue)} songs)",
                value=queue_text,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='leave', aliases=['l', 'disconnect', 'dc'])
    @is_same_voice_channel()
    async def leave(self, ctx):
        """Leave the voice channel"""
        if ctx.voice_client:
            player = self.bot.get_audio_player(ctx.guild.id)
            player.stop()
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Left the voice channel.")
        else:
            await ctx.send("I'm not in a voice channel.")
    
    @commands.command(name='pause')
    @is_same_voice_channel()
    async def pause(self, ctx):
        """Pause the current song"""
        player = self.bot.get_audio_player(ctx.guild.id)
        
        if player.pause():
            await ctx.send("⏸️ Paused playback.")
        else:
            await ctx.send("Nothing is playing!")
    
    @commands.command(name='resume')
    @is_same_voice_channel()
    async def resume(self, ctx):
        """Resume playback"""
        player = self.bot.get_audio_player(ctx.guild.id)
        
        if player.resume():
            await ctx.send("▶️ Resumed playback.")
        else:
            await ctx.send("Nothing to resume!")
    
    @commands.command(name='volume', aliases=['v'])
    @is_same_voice_channel()
    async def volume(self, ctx, volume: int = None):
        """Set or show the volume (0-100)"""
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

async def setup(bot):
    await bot.add_cog(Music(bot))