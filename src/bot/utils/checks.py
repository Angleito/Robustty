import discord
from discord.ext import commands
from discord.ext.commands import Context  # type: ignore[import]
from discord import Member


def is_in_voice_channel():
    """Check if user is in a voice channel"""

    async def predicate(ctx: Context) -> bool:
        author = ctx.author
        if not isinstance(author, Member) or not author.voice:
            await ctx.send("You need to be in a voice channel to use this command!")
            return False
        return True

    return commands.check(predicate)


def is_same_voice_channel():
    """Check if user is in the same voice channel as bot"""

    async def predicate(ctx: Context) -> bool:
        author = ctx.author
        if not isinstance(author, Member) or not author.voice:
            await ctx.send("You need to be in a voice channel to use this command!")
            return False

        if ctx.voice_client and author.voice.channel != ctx.voice_client.channel:
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

    async def predicate(ctx: Context) -> bool:
        # Check for DJ role
        if ctx.guild is None:
            return False

        author = ctx.author
        if not isinstance(author, Member):
            return False

        dj_role = discord.utils.get(ctx.guild.roles, name="DJ")
        if dj_role and dj_role in author.roles:
            return True

        # Check for admin/mod permissions
        if (
            author.guild_permissions.administrator
            or author.guild_permissions.manage_messages
        ):
            return True

        # Check if alone with bot
        if (ctx.voice_client and hasattr(ctx.voice_client.channel, 'members') and
                len(ctx.voice_client.channel.members) <= 2):
            return True

        await ctx.send(
            "You need the DJ role or appropriate permissions to use this command!"
        )
        return False

    return commands.check(predicate)


def is_guild_owner():
    """Check if user is the guild owner"""

    async def predicate(ctx: Context) -> bool:
        if ctx.guild is None:
            return False
        return ctx.author == ctx.guild.owner

    return commands.check(predicate)
