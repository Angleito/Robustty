"""Tests for configuration loader."""
import os
import tempfile
import pytest

from src.utils.config_loader import load_config, validate_platform_credentials, ConfigurationError


class TestConfigLoader:
    """Test configuration loading functionality."""
    
    def test_env_var_substitution(self):
        """Test environment variable substitution."""
        # Set test environment variable
        os.environ['TEST_API_KEY'] = 'test123'
        
        config_content = """
bot:
  command_prefix: "!"
  description: "Test Bot"
  activity: "Testing"

platforms:
  test:
    api_key: ${TEST_API_KEY}
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            config_path = f.name
        
        try:
            config = load_config(config_path)
            assert config['platforms']['test']['api_key'] == 'test123'
        finally:
            os.unlink(config_path)
            del os.environ['TEST_API_KEY']
    
    def test_default_values(self):
        """Test default value substitution."""
        config_content = """
bot:
  command_prefix: "!"
  description: "Test Bot"
  activity: "Testing"

platforms:
  test:
    enabled: ${TEST_ENABLED:false}
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            config_path = f.name
        
        try:
            config = load_config(config_path)
            # Should use default value
            assert config['platforms']['test']['enabled'] == 'false'
        finally:
            os.unlink(config_path)
    
    def test_youtube_api_key_validation(self):
        """Test YouTube API key validation."""
        config = {
            'platforms': {
                'youtube': {
                    'enabled': True,
                    'api_key': None
                }
            }
        }
        
        with pytest.raises(ConfigurationError, match="YouTube platform is enabled but API key is missing"):
            validate_platform_credentials(config)
        
        # With placeholder
        config['platforms']['youtube']['api_key'] = '${YOUTUBE_API_KEY}'
        with pytest.raises(ConfigurationError, match="YouTube platform is enabled but API key is missing"):
            validate_platform_credentials(config)
        
        # With valid key
        config['platforms']['youtube']['api_key'] = 'valid_key'
        validate_platform_credentials(config)  # Should not raise
    
    def test_rumble_api_token_validation(self):
        """Test Rumble API token validation."""
        config = {
            'platforms': {
                'rumble': {
                    'enabled': True,
                    'api_token': None
                }
            }
        }
        
        with pytest.raises(ConfigurationError, match="Rumble platform is enabled but API token is missing"):
            validate_platform_credentials(config)
        
        # With placeholder
        config['platforms']['rumble']['api_token'] = '${RUMBLE_API_TOKEN}'
        with pytest.raises(ConfigurationError, match="Rumble platform is enabled but API token is missing"):
            validate_platform_credentials(config)
        
        # With valid token
        config['platforms']['rumble']['api_token'] = 'valid_token'
        validate_platform_credentials(config)  # Should not raise
    
    def test_disabled_platforms_no_validation(self):
        """Test that disabled platforms don't require credentials."""
        config = {
            'platforms': {
                'youtube': {
                    'enabled': False,
                    'api_key': None
                },
                'rumble': {
                    'enabled': False,
                    'api_token': None
                }
            }
        }
        
        # Should not raise any errors
        validate_platform_credentials(config)
    
    def test_missing_platforms_section(self):
        """Test handling of missing platforms section."""
        config = {}
        
        # Should not raise any errors
        validate_platform_credentials(config)
    
    def test_configuration_error_message(self):
        """Test that ConfigurationError provides helpful error messages."""
        config = {
            'platforms': {
                'youtube': {
                    'enabled': True,
                    'api_key': None
                }
            }
        }
        
        try:
            validate_platform_credentials(config)
            assert False, "Should have raised ConfigurationError"
        except ConfigurationError as e:
            error_message = str(e)
            # Check that the error message contains helpful instructions
            assert "To fix this:" in error_message
            assert "YOUTUBE_API_KEY" in error_message
            assert "export YOUTUBE_API_KEY=" in error_message
            
        # Test for Rumble
        config = {
            'platforms': {
                'rumble': {
                    'enabled': True,
                    'api_token': None
                }
            }
        }
        
        try:
            validate_platform_credentials(config)
            assert False, "Should have raised ConfigurationError"
        except ConfigurationError as e:
            error_message = str(e)
            # Check that the error message contains helpful instructions
            assert "To fix this:" in error_message
            assert "RUMBLE_API_TOKEN" in error_message
            assert "export RUMBLE_API_TOKEN=" in error_message