from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest
from discord.ext import commands

from src.bot.cogs.admin import Admin
from src.bot.cogs.info import Info
from src.bot.cogs.music import Music


@pytest.fixture
def bot():
    bot = Mock(spec=commands.Bot)
    bot.searcher = Mock()
    bot.searcher.search_all_platforms = AsyncMock(
        return_value={
            "youtube": [
                {
                    "id": "1",
                    "title": "Test Song",
                    "url": "http://test.com/1",
                    "platform": "youtube",
                }
            ]
        }
    )
    bot.get_audio_player = Mock()
    bot.platform_registry = Mock()
    bot.platform_registry.get_all_platforms.return_value = {
        "youtube": Mock(enabled=True)
    }
    bot.wait_for = AsyncMock()
    return bot


@pytest.fixture
def ctx():
    ctx = Mock()
    ctx.author = Mock()
    ctx.author.voice = Mock()
    ctx.author.voice.channel = Mock()
    ctx.voice_client = None
    ctx.send = AsyncMock()
    ctx.guild = Mock()
    ctx.guild.id = 12345
    ctx.channel = Mock()
    ctx.typing = Mock()
    ctx.typing.__aenter__ = AsyncMock()
    ctx.typing.__aexit__ = AsyncMock()
    return ctx


@pytest.fixture
def music_cog(bot):
    return Music(bot)


@pytest.fixture
def info_cog(bot):
    return Info(bot)


@pytest.fixture
def admin_cog(bot):
    return Admin(bot)


@pytest.mark.asyncio
async def test_play_command(music_cog, ctx, bot):
    # Setup
    ctx.voice_client = None
    player = Mock()
    player.add_to_queue = AsyncMock()
    player.is_playing = Mock(return_value=False)
    player.play_next = AsyncMock()
    bot.get_audio_player.return_value = player

    # Execute
    await music_cog.play(ctx, query="test song")

    # Verify
    bot.searcher.search_all_platforms.assert_called_once_with("test song")
    ctx.send.assert_called()
    player.add_to_queue.assert_called_once()


@pytest.mark.asyncio
async def test_skip_command(music_cog, ctx, bot):
    player = Mock()
    player.is_playing = Mock(return_value=True)
    player.skip = Mock()
    bot.get_audio_player.return_value = player

    await music_cog.skip(ctx)

    player.skip.assert_called_once()
    ctx.send.assert_called_with("⏭️ Skipped current song!")


@pytest.mark.asyncio
async def test_queue_command(music_cog, ctx, bot):
    player = Mock()
    player.get_queue = Mock(
        return_value=[
            {"title": "Song 1", "url": "http://test.com/1"},
            {"title": "Song 2", "url": "http://test.com/2"},
        ]
    )
    player.current = {"title": "Current Song", "url": "http://test.com/current"}
    bot.get_audio_player.return_value = player

    await music_cog.queue(ctx)

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert embed.title == "Music Queue"


@pytest.mark.asyncio
async def test_volume_command(music_cog, ctx, bot):
    player = Mock()
    player.get_volume = Mock(return_value=50)
    player.set_volume = Mock()
    bot.get_audio_player.return_value = player

    # Test get volume
    await music_cog.volume(ctx)
    ctx.send.assert_called_with("🔊 Current volume: 50%")

    # Test set volume
    await music_cog.volume(ctx, 75)
    player.set_volume.assert_called_with(75)
    ctx.send.assert_called_with("🔊 Volume set to 75%")


@pytest.mark.asyncio
async def test_ping_command(info_cog, ctx, bot):
    bot.latency = 0.05  # 50ms

    await info_cog.ping(ctx)

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert "Pong!" in embed.title
    assert "50ms" in embed.description


@pytest.mark.asyncio
async def test_help_command(info_cog, ctx, bot):
    bot.cogs = {
        "Music": Mock(
            get_commands=Mock(
                return_value=[
                    Mock(name="play", hidden=False),
                    Mock(name="skip", hidden=False),
                ]
            )
        )
    }
    ctx.prefix = "!"

    await info_cog.help(ctx)

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert embed.title == "Robustty Commands"


@pytest.mark.asyncio
async def test_status_command(admin_cog, ctx, bot):
    bot.guilds = [Mock(), Mock()]
    bot.users = [Mock() for _ in range(10)]
    bot.voice_clients = [Mock()]

    await admin_cog.status(ctx)

    ctx.send.assert_called_once()
    embed = ctx.send.call_args[1]["embed"]
    assert embed.title == "Bot Status"


@pytest.mark.asyncio
async def test_reload_command(admin_cog, ctx, bot):
    bot.reload_extension = AsyncMock()

    await admin_cog.reload(ctx, "music")

    bot.reload_extension.assert_called_once_with("src.bot.cogs.music")
    ctx.send.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_command(admin_cog, ctx, bot):
    bot.close = AsyncMock()

    await admin_cog.shutdown(ctx)

    bot.close.assert_called_once()
    ctx.send.assert_called_once()
