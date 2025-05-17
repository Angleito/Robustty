from discord.ext import commands
import discord

def is_in_voice_channel():
    """Check if user is in a voice channel"""
    async def predicate(ctx):
        if not ctx.author.voice:
            await ctx.send("You need to be in a voice channel to use this command!")
            return False
        return True
    return commands.check(predicate)

def is_same_voice_channel():
    """Check if user is in the same voice channel as bot"""
    async def predicate(ctx):
        if not ctx.author.voice:
            await ctx.send("You need to be in a voice channel to use this command!")
            return False
        
        if ctx.voice_client and ctx.author.voice.channel != ctx.voice_client.channel:
            await ctx.send("You need to be in the same voice channel as the bot!")
            return False
        
        return True
    return commands.check(predicate)

def is_admin():
    """Check if user has admin permissions"""
    return commands.has_permissions(administrator=True)

def is_mod():
    """Check if user has moderator permissions"""
    return commands.has_permissions(manage_messages=True)

def is_dj():
    """Check if user has DJ role or permissions"""
    async def predicate(ctx):
        # Check for DJ role
        dj_role = discord.utils.get(ctx.guild.roles, name="DJ")
        if dj_role and dj_role in ctx.author.roles:
            return True
        
        # Check for admin/mod permissions
        if ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_messages:
            return True
        
        # Check if alone with bot
        if ctx.voice_client and len(ctx.voice_client.channel.members) <= 2:
            return True
        
        await ctx.send("You need the DJ role or appropriate permissions to use this command!")
        return False
    
    return commands.check(predicate)

def is_guild_owner():
    """Check if user is the guild owner"""
    async def predicate(ctx):
        return ctx.author == ctx.guild.owner
    return commands.check(predicate)