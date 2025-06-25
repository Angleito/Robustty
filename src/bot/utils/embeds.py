from datetime import datetime
from typing import Any, Optional

import discord
from discord import Colour, Embed

from ...services.status_reporting import (
    StatusReport,
    MultiPlatformStatus,
    SearchMethod,
    PlatformStatus,
    OperationResult,
)
from ...utils.config_loader import load_config

# Load configuration
_config = None

def _get_config():
    """Lazy load configuration"""
    global _config
    if _config is None:
        try:
            _config = load_config("config/config.yaml")
        except Exception:
            # Fallback to default if config loading fails
            _config = {"features": {"show_fallback_indicators": True}}
    return _config

def _show_fallback_indicators() -> bool:
    """Check if fallback indicators should be shown"""
    config = _get_config()
    return config.get("features", {}).get("show_fallback_indicators", True)


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


def create_music_embed(song_info: dict[str, Any], queued: bool = False, search_method: Optional[SearchMethod] = None) -> Embed:
    """Create an embed for music information with optional fallback indicators"""
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
    
    # Add fallback indicator if configured and applicable
    if _show_fallback_indicators() and search_method:
        footer_text = _get_method_indicator(search_method)
        if footer_text:
            embed.set_footer(text=footer_text)

    return embed


def create_status_report_embed(status_report: StatusReport) -> Embed:
    """Create an embed for a status report"""
    # Determine color based on result
    if status_report.result == OperationResult.SUCCESS:
        color = discord.Color.green()
    elif status_report.result == OperationResult.FALLBACK_SUCCESS:
        color = discord.Color.orange()
    elif status_report.result == OperationResult.PARTIAL_SUCCESS:
        color = discord.Color.yellow()
    else:
        color = discord.Color.red()
    
    # Create embed
    embed = create_embed(
        title=f"{status_report.platform.title()} Status",
        description=status_report.user_message,
        color=color
    )
    
    # Add method information
    method_display = {
        SearchMethod.API_SEARCH: "🔍 API Search",
        SearchMethod.FALLBACK_SEARCH: "🔄 Fallback Search", 
        SearchMethod.DIRECT_URL: "🔗 Direct URL Processing",
        SearchMethod.YTDLP_SEARCH: "📥 yt-dlp Search",
        SearchMethod.MIRROR_SEARCH: "🪞 Mirror Search"
    }
    
    embed.add_field(
        name="Method",
        value=method_display.get(status_report.method, status_report.method.value),
        inline=True
    )
    
    # Add status information
    status_display = {
        PlatformStatus.HEALTHY: "🟢 Healthy",
        PlatformStatus.QUOTA_EXCEEDED: "🔴 Quota Exceeded",
        PlatformStatus.API_ERROR: "🔴 API Error",
        PlatformStatus.RATE_LIMITED: "🟡 Rate Limited",
        PlatformStatus.UNAVAILABLE: "🔴 Unavailable",
        PlatformStatus.NO_API_KEY: "🟡 No API Key",
        PlatformStatus.USING_FALLBACK: "🟡 Using Fallback"
    }
    
    embed.add_field(
        name="Status",
        value=status_display.get(status_report.status, status_report.status.value),
        inline=True
    )
    
    # Add details if available
    if status_report.details:
        details_text = []
        for key, value in status_report.details.items():
            if key == "results_count":
                details_text.append(f"Results: {value}")
            else:
                details_text.append(f"{key.title()}: {value}")
        
        if details_text:
            embed.add_field(
                name="Details",
                value="\n".join(details_text),
                inline=False
            )
    
    # Add timestamp
    embed.set_footer(text=f"Reported at {status_report.timestamp.strftime('%H:%M:%S')}")
    
    return embed


def create_multi_platform_status_embed(multi_status: MultiPlatformStatus, show_details: bool = True) -> Embed:
    """Create an embed for multi-platform search status with optional detail level"""
    # Determine color based on overall success
    if not multi_status.successful_platforms:
        color = discord.Color.red()
    elif len(multi_status.successful_platforms) == multi_status.total_platforms:
        color = discord.Color.green() if not multi_status.has_fallbacks() else discord.Color.orange()
    else:
        color = discord.Color.yellow()
    
    # Create embed with summary
    embed = create_embed(
        title="🔍 Search Status Report",
        description=multi_status.get_user_summary(),
        color=color
    )
    
    # Add query information
    embed.add_field(
        name="Query",
        value=f"`{multi_status.query}`",
        inline=False
    )
    
    # Only show detailed platform status if configured
    if show_details or not _show_fallback_indicators():
        # Add platform status
        if multi_status.successful_platforms:
            success_text = "\n".join([f"🟢 {platform.title()}" for platform in multi_status.successful_platforms])
            embed.add_field(
                name=f"Successful Platforms ({len(multi_status.successful_platforms)})",
                value=success_text,
                inline=True
            )
        
        if multi_status.failed_platforms:
            failed_text = "\n".join([f"🔴 {platform.title()}" for platform in multi_status.failed_platforms])
            embed.add_field(
                name=f"Failed Platforms ({len(multi_status.failed_platforms)})",
                value=failed_text,
                inline=True
            )
    else:
        # Show simplified status
        status_indicator = _get_overall_status_indicator(multi_status)
        embed.add_field(
            name="Status",
            value=status_indicator,
            inline=False
        )
    
    # Add fallback information if relevant and configured
    if _show_fallback_indicators() and multi_status.has_fallbacks():
        fallback_platforms = multi_status.get_fallback_platforms()
        quota_platforms = multi_status.get_quota_exceeded_platforms()
        
        fallback_info = []
        if quota_platforms:
            fallback_info.append(f"🔴 Quota exceeded: {', '.join(quota_platforms)}")
        if fallback_platforms:
            fallback_info.append(f"🟡 Using alternative methods: {', '.join(fallback_platforms)}")
        
        if fallback_info:
            embed.add_field(
                name="Search Method Info",
                value="\n".join(fallback_info),
                inline=False
            )
    
    # Add method summary only if showing details
    if show_details:
        method_text = []
        if multi_status.primary_method == SearchMethod.DIRECT_URL:
            method_text.append("🔗 Direct URL processing")
        elif multi_status.primary_method == SearchMethod.API_SEARCH:
            method_text.append("🔍 API search")
        
        if multi_status.fallback_methods_used:
            method_names = {
                SearchMethod.FALLBACK_SEARCH: "alternative search",
                SearchMethod.YTDLP_SEARCH: "direct extraction", 
                SearchMethod.MIRROR_SEARCH: "mirror search"
            }
            fallback_names = [method_names.get(method, method.value) for method in multi_status.fallback_methods_used]
            method_text.append(f"🔄 Also tried: {', '.join(fallback_names)}")
        
        if method_text:
            embed.add_field(
                name="Methods Used",
                value="\n".join(method_text),
                inline=False
            )
    
    # Add footer with indicator if configured
    if _show_fallback_indicators():
        footer_text = _get_search_quality_indicator(multi_status)
        if footer_text:
            embed.set_footer(text=footer_text)
    
    return embed


def _get_overall_status_indicator(multi_status: MultiPlatformStatus) -> str:
    """Get a simple overall status indicator"""
    total = multi_status.total_platforms
    successful = len(multi_status.successful_platforms)
    
    if successful == total and not multi_status.has_fallbacks():
        return "🟢 All platforms searched successfully"
    elif successful == total and multi_status.has_fallbacks():
        return "🟡 Results found using alternative methods"
    elif successful > 0:
        return f"🟡 Found results from {successful}/{total} platforms"
    else:
        return "🔴 No results found"


def _get_search_quality_indicator(multi_status: MultiPlatformStatus) -> str:
    """Get a footer indicator for search quality"""
    if not multi_status.has_fallbacks():
        return "🟢 Standard search"
    elif multi_status.get_quota_exceeded_platforms():
        return "🟡 Some limits reached - using alternatives"
    else:
        return "🟡 Mixed search methods"


def create_quota_exceeded_embed(platform: str, fallback_available: bool = True) -> Embed:
    """Create an embed for API quota exceeded notification"""
    description = f"The {platform} API quota has been exceeded."
    
    if fallback_available:
        description += "\n\n🔄 **Attempting fallback methods...**"
        color = discord.Color.orange()
    else:
        description += "\n\n❌ **No fallback methods available.**\n\n"
        description += "💡 **What you can do:**\n"
        description += "• Try again later when quota resets\n"
        description += "• Use direct URLs instead of search terms\n"
        description += "• Contact admin to check API configuration"
        color = discord.Color.red()
    
    return create_embed(
        title="⚠️ API Quota Exceeded",
        description=description,
        color=color
    )


def create_fallback_success_embed(platform: str, method: SearchMethod, results_count: int) -> Embed:
    """Create an embed for successful fallback operation"""
    method_names = {
        SearchMethod.FALLBACK_SEARCH: "fallback search",
        SearchMethod.YTDLP_SEARCH: "yt-dlp extraction",
        SearchMethod.DIRECT_URL: "direct URL processing",
        SearchMethod.MIRROR_SEARCH: "mirror search"
    }
    
    method_name = method_names.get(method, method.value)
    
    description = f"Successfully used {method_name} for {platform.title()}.\n\n"
    description += f"📊 **Found {results_count} result{'s' if results_count != 1 else ''}**"
    
    return create_embed(
        title="✅ Fallback Method Successful",
        description=description,
        color=discord.Color.orange()
    )


def create_all_methods_failed_embed(query: str, platform_errors: dict[str, str]) -> Embed:
    """Create an embed when all search methods fail"""
    description = f"Could not find results for: **{query}**\n\n"
    description += "❌ **All search methods failed:**\n\n"
    
    for platform, error in platform_errors.items():
        description += f"• **{platform.title()}**: {error}\n"
    
    description += "\n💡 **Try this:**\n"
    description += "• Use more specific search terms\n"
    description += "• Try direct URLs instead of search terms\n"
    description += "• Wait a few minutes for services to recover\n"
    description += "• Check if the content is available on the platforms"
    
    return create_embed(
        title="❌ Search Failed",
        description=description,
        color=discord.Color.red()
    )


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
    
    # Add YouTube quota status if available
    youtube_quota = service_status.get("youtube_quota", {})
    if youtube_quota and "error" not in youtube_quota:
        quota_emoji = "🟢"
        if youtube_quota.get("level") == "caution":
            quota_emoji = "🟡"
        elif youtube_quota.get("level") in ["critical", "exhausted"]:
            quota_emoji = "🔴"
        
        quota_text = f"{quota_emoji} Usage: {youtube_quota.get('usage', 'N/A')}\n"
        quota_text += f"Remaining: {youtube_quota.get('percentage_remaining', 0):.0f}%\n"
        
        if youtube_quota.get("conservation_active"):
            quota_text += "⚠️ Conservation mode active\n"
        
        if youtube_quota.get("predicted_exhaustion_hours"):
            quota_text += f"Est. exhaustion: {youtube_quota['predicted_exhaustion_hours']:.1f}h\n"
        
        quota_text += f"Reset in: {youtube_quota.get('hours_to_reset', 'N/A')}h"
        
        embed.add_field(name="YouTube Quota", value=quota_text, inline=True)

    return embed


def create_fallback_status_embed(platform: str, current_method: SearchMethod, is_active: bool = True) -> Embed:
    """Create an embed showing current fallback mode status"""
    if is_active:
        color = discord.Color.orange()
        emoji = "🟡"
        status = "Active"
    else:
        color = discord.Color.green()
        emoji = "🟢"
        status = "Inactive"
    
    method_names = {
        SearchMethod.API_SEARCH: "API Search",
        SearchMethod.FALLBACK_SEARCH: "Alternative Search",
        SearchMethod.YTDLP_SEARCH: "Direct Extraction",
        SearchMethod.DIRECT_URL: "URL Processing",
        SearchMethod.MIRROR_SEARCH: "Mirror Search"
    }
    
    method_name = method_names.get(current_method, current_method.value)
    
    description = f"{emoji} **Fallback Mode**: {status}\n\n"
    description += f"**Current Method**: {method_name}\n"
    description += f"**Platform**: {platform.title()}\n\n"
    
    if is_active:
        description += "ℹ️ Using alternative search methods to provide results.\n"
        description += "Results may differ from standard searches."
    else:
        description += "✅ Standard API search is functioning normally."
    
    return create_embed(
        title="Search Method Status",
        description=description,
        color=color
    )


def create_search_status_embed(
    query: str, 
    results_count: int,
    platform: str,
    method: SearchMethod,
    from_cache: bool = False
) -> Embed:
    """Create an embed showing which search strategy provided results"""
    # Determine color and indicator based on method
    if method == SearchMethod.API_SEARCH and not from_cache:
        color = discord.Color.green()
        indicator = "🟢 API"
        method_text = "Standard API search"
    elif from_cache:
        color = discord.Color.blue()
        indicator = "🔵 Cache"
        method_text = "Cached results"
    elif method in [SearchMethod.FALLBACK_SEARCH, SearchMethod.YTDLP_SEARCH]:
        color = discord.Color.orange()
        indicator = "🟡 Fallback"
        method_text = "Alternative search method"
    else:
        color = discord.Color.blue()
        indicator = "🔍 Search"
        method_text = method.value.replace('_', ' ').title()
    
    title = f"Search Results - {indicator}"
    
    description = f"**Query**: `{query}`\n"
    description += f"**Platform**: {platform.title()}\n"
    description += f"**Results**: {results_count} found\n"
    description += f"**Method**: {method_text}\n"
    
    if from_cache:
        description += "\n💾 *These are cached results from a previous search*"
    elif method != SearchMethod.API_SEARCH:
        description += "\n🔄 *Using alternative search due to API limitations*"
    
    embed = create_embed(
        title=title,
        description=description,
        color=color
    )
    
    # Add subtle footer indicator if configured
    if _show_fallback_indicators():
        footer_text = _get_method_indicator(method, from_cache)
        if footer_text:
            embed.set_footer(text=footer_text)
    
    return embed


def create_quota_warning_embed(
    platform: str,
    quota_info: Optional[dict[str, Any]] = None,
    retry_after: Optional[int] = None
) -> Embed:
    """Create a user-friendly embed warning about low/exceeded quota"""
    title = "⚠️ API Limit Reached"
    
    description = f"The {platform.title()} search limit has been reached.\n\n"
    
    if quota_info:
        remaining = quota_info.get("remaining", 0)
        limit = quota_info.get("limit", "unknown")
        resets_at = quota_info.get("resets_at", "unknown")
        
        if remaining == 0:
            description += "📊 **Status**: No searches remaining\n"
        else:
            description += f"📊 **Status**: {remaining}/{limit} searches remaining\n"
        
        if resets_at != "unknown":
            description += f"⏰ **Resets**: {resets_at}\n"
    
    if retry_after:
        minutes = retry_after // 60
        seconds = retry_after % 60
        if minutes > 0:
            description += f"⏳ **Try again in**: {minutes}m {seconds}s\n"
        else:
            description += f"⏳ **Try again in**: {seconds}s\n"
    
    description += "\n**What's happening?**\n"
    description += "• Switching to alternative search methods\n"
    description += "• You can still use direct video URLs\n"
    description += "• Results may be limited temporarily\n\n"
    description += "💡 *This is temporary - normal service will resume soon*"
    
    return create_embed(
        title=title,
        description=description,
        color=discord.Color.orange()
    )


def _get_method_indicator(method: SearchMethod, from_cache: bool = False) -> str:
    """Get a subtle indicator text for the search method"""
    if not _show_fallback_indicators():
        return ""
    
    if from_cache:
        return "📦 Cached Result"
    
    indicators = {
        SearchMethod.API_SEARCH: "🟢 Standard Search",
        SearchMethod.FALLBACK_SEARCH: "🟡 Alternative Search",
        SearchMethod.YTDLP_SEARCH: "🟡 Direct Extraction",
        SearchMethod.DIRECT_URL: "🔗 Direct URL",
        SearchMethod.MIRROR_SEARCH: "🟡 Mirror Search"
    }
    
    return indicators.get(method, "")
