"""Test bot type annotations and ConfigType."""
import pytest
from unittest.mock import patch, MagicMock

from src.bot.bot import RobusttyBot
from src.utils.config_loader import ConfigType, BotSection, PerformanceConfig, FeaturesConfig


def test_bot_with_typed_config():
    """Test that bot accepts ConfigType and works properly."""
    # Create a properly typed config
    config: ConfigType = {
        'bot': BotSection(
            command_prefix='!',
            description='Test bot',
            activity='Test activity'
        ),
        'platforms': {
            'youtube': {
                'enabled': True,
                'api_key': 'test_key',
                'max_results': 10
            }
        },
        'performance': PerformanceConfig(
            search_timeout=30,
            stream_timeout=300,
            max_queue_size=100,
            cache_ttl=3600
        ),
        'features': FeaturesConfig(
            auto_disconnect=True,
            auto_disconnect_timeout=300,
            save_queue=True,
            announce_songs=True
        ),
        'cookies': {}
    }
    
    # Create bot with typed config
    bot = RobusttyBot(config)
    
    # Verify bot was created with the correct config
    assert bot.config == config
    assert bot.command_prefix == '!'
    
    # Verify type annotations work for methods
    assert hasattr(bot.setup_hook, '__annotations__')
    assert hasattr(bot.on_ready, '__annotations__')
    assert hasattr(bot.on_guild_join, '__annotations__')
    assert hasattr(bot.on_guild_remove, '__annotations__')
    assert hasattr(bot.close, '__annotations__')


def test_config_types_are_correct():
    """Test that ConfigType properly validates expected config structure."""
    # This config should match what's in config.yaml
    config: ConfigType = {
        'bot': {
            'command_prefix': '!',
            'description': 'Multi-platform music bot',
            'activity': 'music from everywhere'
        },
        'platforms': {
            'youtube': {
                'enabled': True,
                'api_key': 'test_key',
                'max_results': 10
            }
        },
        'performance': {
            'search_timeout': 30,
            'stream_timeout': 300,
            'max_queue_size': 100,
            'cache_ttl': 3600
        },
        'features': {
            'auto_disconnect': True,
            'auto_disconnect_timeout': 300,
            'save_queue': True,
            'announce_songs': True
        },
        'cookies': {}
    }
    
    # This should pass type checking
    bot = RobusttyBot(config)
    assert bot.config == config