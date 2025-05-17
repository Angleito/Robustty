from datetime import datetime
from typing import Any, Optional

import discord
from discord import Colour, Embed


def create_embed(
    title: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[Colour] = None,
    **kwargs: Any,
) -> Embed:
    """Create a standard embed with consistent styling"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.blue(),
        timestamp=datetime.utcnow(),
        **kwargs,
    )
    return embed


def create_error_embed(title: str = "Error", description: Optional[str] = None) -> Embed:
    """Create an error embed"""
    return create_embed(
        title=f"❌ {title}", description=description, color=discord.Color.red()
    )


def create_success_embed(title: str = "Success", description: Optional[str] = None) -> Embed:
    """Create a success embed"""
    return create_embed(
        title=f"✅ {title}", description=description, color=discord.Color.green()
    )


def create_warning_embed(title: str = "Warning", description: Optional[str] = None) -> Embed:
    """Create a warning embed"""
    return create_embed(
        title=f"⚠️ {title}", description=description, color=discord.Color.yellow()
    )


def create_music_embed(song_info: dict[str, Any], queued: bool = False) -> Embed:
    """Create an embed for music information"""
    title = "Now Playing" if not queued else "Added to Queue"
    embed = create_embed(
        title=title,
        description=f"[{song_info['title']}]({song_info['url']})",
        color=discord.Color.green() if not queued else discord.Color.blue(),
    )

    embed.add_field(name="Platform", value=song_info["platform"].title(), inline=True)
    embed.add_field(
        name="Channel", value=song_info.get("channel", "Unknown"), inline=True
    )

    if song_info.get("duration"):
        embed.add_field(name="Duration", value=song_info["duration"], inline=True)

    if song_info.get("thumbnail"):
        embed.set_thumbnail(url=song_info["thumbnail"])

    return embed
