"""Test integration with actual config loading."""
from src.bot.bot import RobusttyBot
from src.utils.config_loader import load_config


def test_bot_with_real_config():
    """Test that bot can be instantiated with real config."""
    # Load the real config
    config = load_config("config/config.yaml")
    
    # Create bot with the loaded config
    bot = RobusttyBot(config)
    
    # Verify bot was created successfully
    assert bot.config == config
    assert bot.command_prefix == "!"
    assert bot.platform_registry is not None
    assert bot.searcher is None  # Not initialized until setup_hook
    assert bot.cookie_manager is None  # Not initialized until setup_hook
    assert bot.audio_players == {}