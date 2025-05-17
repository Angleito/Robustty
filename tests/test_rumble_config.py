#!/usr/bin/env python3
"""Test Rumble configuration loading and validation."""
import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_loader import load_config


def test_rumble_config_validation():
    """Test Rumble API token validation."""
    # Create a test config file
    config_content = """
bot:
  command_prefix: "!"
  description: "Test Bot"
  activity: "Testing"

platforms:
  rumble:
    enabled: true
    api_token: ${RUMBLE_API_TOKEN:}
    base_url: https://rumble.com
    api_base: https://rumble.com/api/v0
"""
    
    # Test without token
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        # Should raise an error
        config = load_config(config_path)
        print("❌ Expected error but got none")
    except ValueError as e:
        if "RUMBLE_API_TOKEN environment variable is not set" in str(e):
            print("✓ Correctly detected missing RUMBLE_API_TOKEN")
        else:
            print(f"❌ Unexpected error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error type: {type(e).__name__}: {e}")
    finally:
        os.unlink(config_path)
    
    # Test with token
    os.environ['RUMBLE_API_TOKEN'] = 'test_token_123'
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        if config['platforms']['rumble']['api_token'] == 'test_token_123':
            print("✓ Successfully loaded config with Rumble API token")
        else:
            print(f"❌ Token not loaded correctly: {config['platforms']['rumble'].get('api_token')}")
    except Exception as e:
        print(f"❌ Failed to load config with token: {e}")
    finally:
        os.unlink(config_path)
        del os.environ['RUMBLE_API_TOKEN']


if __name__ == "__main__":
    test_rumble_config_validation()