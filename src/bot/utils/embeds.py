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


def create_error_embed(
    title: str = "Error", description: Optional[str] = None
) -> Embed:
    """Create an error embed"""
    return create_embed(
        title=f"❌ {title}", description=description, color=discord.Color.red()
    )


def create_success_embed(
    title: str = "Success", description: Optional[str] = None
) -> Embed:
    """Create a success embed"""
    return create_embed(
        title=f"✅ {title}", description=description, color=discord.Color.green()
    )


def create_warning_embed(
    title: str = "Warning", description: Optional[str] = None
) -> Embed:
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


def create_service_status_embed(service_status: dict[str, Any]) -> Embed:
    """Create an embed for service status information"""
    overall_health = service_status.get("overall_health", "unknown")

    if overall_health == "healthy":
        color = discord.Color.green()
        title = "🟢 All Services Healthy"
    elif overall_health == "degraded":
        color = discord.Color.yellow()
        title = "🟡 Some Services Degraded"
    elif overall_health == "unhealthy":
        color = discord.Color.red()
        title = "🔴 Service Issues Detected"
    else:
        color = discord.Color.blue()
        title = "📊 Service Status"

    embed = create_embed(title=title, color=color)

    # Add platform status
    platforms = service_status.get("platforms", {})
    if platforms:
        platform_text = ""
        for platform, status in platforms.items():
            if status.get("available", False):
                platform_text += f"🟢 {platform.title()}\n"
            else:
                platform_text += f"🔴 {platform.title()}\n"

        embed.add_field(
            name="Platform Status",
            value=platform_text or "No platforms configured",
            inline=True,
        )

    # Add circuit breaker status
    circuit_breakers = service_status.get("circuit_breakers", {})
    if circuit_breakers:
        cb_text = ""
        for cb_name, cb_status in circuit_breakers.items():
            state = cb_status.get("state", "unknown")
            if state == "closed":
                cb_text += f"🟢 {cb_name.replace('_', ' ').title()}\n"
            elif state == "half_open":
                cb_text += f"🟡 {cb_name.replace('_', ' ').title()}\n"
            else:
                cb_text += f"🔴 {cb_name.replace('_', ' ').title()}\n"

        embed.add_field(
            name="Circuit Breakers", value=cb_text or "No circuit breakers", inline=True
        )

    # Add success rate
    global_stats = service_status.get("global_stats", {})
    success_rate = global_stats.get("success_rate", 0)
    total_calls = global_stats.get("total_calls", 0)

    stats_text = f"Success Rate: {success_rate:.1f}%\n"
    stats_text += f"Total Calls: {total_calls:,}"

    embed.add_field(name="Performance", value=stats_text, inline=True)

    return embed
