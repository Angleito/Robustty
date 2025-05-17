"""Test admin cog with type annotations"""
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
from discord.ext import commands

# Create mock discord types to avoid import errors
class MockContext:
    send = AsyncMock()
    message = Mock()
    
class MockEmbed:
    pass

class MockBot:
    command_prefix = "!"
    guilds = []
    users = []
    voice_clients = []
    reload_extension = AsyncMock()
    close = AsyncMock()
    add_cog = AsyncMock()
    
    class platform_registry:
        @staticmethod
        def get_all_platforms():
            return {"test": Mock(enabled=True)}

# Patch imports before importing admin
@pytest.fixture(autouse=True)
def mock_imports(monkeypatch):
    """Mock external dependencies"""
    # Mock psutil
    mock_psutil = Mock()
    mock_process = Mock()
    mock_process.memory_info.return_value.rss = 100 * 1024 * 1024
    mock_psutil.Process.return_value = mock_process
    monkeypatch.setattr("sys.modules.psutil", mock_psutil)
    
    # Mock discord
    mock_discord = Mock()
    mock_discord.Color.green.return_value = "green"
    mock_discord.Color.red.return_value = "red"
    mock_discord.Color.blue.return_value = "blue"
    mock_discord.Embed = MockEmbed
    monkeypatch.setattr("sys.modules.discord", mock_discord)
    
    # Mock commands
    mock_commands = Mock()
    mock_commands.Bot = MockBot
    mock_commands.Cog = object
    mock_commands.Context = MockContext
    mock_commands.command = lambda **kwargs: lambda func: func
    mock_commands.guild_only = lambda: lambda func: func
    monkeypatch.setattr("sys.modules.discord.ext.commands", mock_commands)
    
    # Create embeds mock
    mock_embeds = Mock()
    mock_embeds.create_embed = Mock(return_value=MockEmbed())
    mock_embeds.create_error_embed = Mock(return_value=MockEmbed())
    monkeypatch.setattr("sys.modules.src.bot.utils.embeds", mock_embeds)
    
    # Create checks mock
    mock_checks = Mock()
    mock_checks.is_admin = lambda: lambda func: func
    monkeypatch.setattr("sys.modules.src.bot.utils.checks", mock_checks)


def test_admin_cog_creation():
    """Test Admin cog can be created with proper types"""
    # Import after mocks are set up
    from src.bot.cogs.admin import Admin, RobottyBot
    
    bot = MockBot()
    admin_cog = Admin(bot)
    
    assert admin_cog.bot == bot
    assert hasattr(admin_cog, 'reload')
    assert hasattr(admin_cog, 'shutdown')
    assert hasattr(admin_cog, 'set_prefix')
    assert hasattr(admin_cog, 'status')
    assert hasattr(admin_cog, 'clear_cache')


@pytest.mark.asyncio
async def test_admin_reload_command():
    """Test reload command with type annotations"""
    from src.bot.cogs.admin import Admin
    
    bot = MockBot()
    admin_cog = Admin(bot)
    ctx = MockContext()
    
    # Test reloading specific extension
    await admin_cog.reload(ctx, "music")
    bot.reload_extension.assert_called_once_with("src.bot.cogs.music")
    ctx.send.assert_called_once()
    
    # Test reloading all extensions
    bot.reload_extension.reset_mock()
    ctx.send.reset_mock()
    await admin_cog.reload(ctx)
    assert bot.reload_extension.call_count >= 3  # music, admin, info


@pytest.mark.asyncio
async def test_admin_status_command():
    """Test status command with psutil integration"""
    from src.bot.cogs.admin import Admin
    
    bot = MockBot()
    admin_cog = Admin(bot)
    ctx = MockContext()
    
    await admin_cog.status(ctx)
    ctx.send.assert_called_once()
    
    # Check that the embed was created with memory usage
    embed_call = ctx.send.call_args[1]['embed']
    assert embed_call is not None


@pytest.mark.asyncio
async def test_admin_set_prefix_command():
    """Test set prefix command with type checking"""
    from src.bot.cogs.admin import Admin
    
    bot = MockBot()
    admin_cog = Admin(bot)
    ctx = MockContext()
    
    # Test changing prefix
    await admin_cog.set_prefix(ctx, "?")
    assert bot.command_prefix == "?"
    ctx.send.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])