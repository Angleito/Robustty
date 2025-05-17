"""Configuration loader with environment variable substitution."""
import os
import re
import sys
from typing import Any, Dict, List, TypedDict, Optional

import yaml


class ConfigurationError(Exception):
    """
    Custom exception for configuration-related errors.
    
    Provides clear error messages about missing configuration values
    and how to fix them.
    """
    pass


class BotSection(TypedDict):
    """Bot configuration section."""
    command_prefix: str
    description: str
    activity: str


class PlatformConfig(TypedDict, total=False):
    """Generic platform configuration."""
    enabled: bool
    api_key: Optional[str]
    max_results: Optional[int]
    instances: Optional[List[str]]
    max_results_per_instance: Optional[int]
    api_url: Optional[str]
    search_url: Optional[str]
    base_url: Optional[str]
    api_base: Optional[str]
    api_token: Optional[str]  # Added for Rumble API token


class PerformanceConfig(TypedDict):
    """Performance configuration section."""
    search_timeout: int
    stream_timeout: int
    max_queue_size: int
    cache_ttl: int


class FeaturesConfig(TypedDict):
    """Features configuration section."""
    auto_disconnect: bool
    auto_disconnect_timeout: int
    save_queue: bool
    announce_songs: bool


class ConfigType(TypedDict):
    """Main configuration type."""
    bot: BotSection
    platforms: Dict[str, PlatformConfig]
    performance: PerformanceConfig
    features: FeaturesConfig
    cookies: Dict[str, str]  # Optional section


def load_config(config_path: str) -> ConfigType:
    """Load configuration with environment variable substitution."""
    with open(config_path, "r") as f:
        content = f.read()

    # Find all ${VAR} or ${VAR:default} patterns
    pattern = r"\$\{(\w+)(?::([^}]*))?\}"

    def replace_env_var(match):
        var_name = match.group(1)
        default_value = match.group(2)
        value = os.environ.get(var_name, default_value)
        if value is None:
            # Keep the placeholder if no value
            return match.group(0)
        return value

    # Replace environment variables
    content = re.sub(pattern, replace_env_var, content)

    # Parse YAML
    config = yaml.safe_load(content)

    # Handle any direct env var lookups in the code
    process_config_dict(config)

    # Ensure cookies section exists with default empty dict
    if 'cookies' not in config:
        config['cookies'] = {}

    # Validate platform credentials
    validate_platform_credentials(config)

    return config


def process_config_dict(config: Dict[str, Any]):
    """Process config dict recursively to replace environment variables."""
    for key, value in config.items():
        if isinstance(value, dict):
            process_config_dict(value)
        elif isinstance(value, str):
            # Check if it's a placeholder that wasn't replaced
            if value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                if ":" in var_name:
                    var_name, default_value = var_name.split(":", 1)
                    config[key] = os.environ.get(var_name, default_value)
                else:
                    config[key] = os.environ.get(var_name, value)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if (
                    isinstance(item, str)
                    and item.startswith("${")
                    and item.endswith("}")
                ):
                    var_name = item[2:-1]
                    if ":" in var_name:
                        var_name, default_value = var_name.split(":", 1)
                        value[i] = os.environ.get(var_name, default_value)
                    else:
                        value[i] = os.environ.get(var_name, item)


def validate_platform_credentials(config: Dict[str, Any]):
    """Validate required API credentials for enabled platforms."""
    platforms = config.get("platforms", {})
    
    # Check YouTube API key
    if platforms.get("youtube", {}).get("enabled"):
        api_key = platforms["youtube"].get("api_key")
        if not api_key or api_key.startswith("${"):
            raise ConfigurationError(
                "YouTube platform is enabled but API key is missing.\n"
                "To fix this:\n"
                "1. Set the YOUTUBE_API_KEY environment variable\n"
                "2. Or add the key directly to config.yaml\n"
                "3. Or disable YouTube in config by setting 'enabled: false'\n"
                "\nExample: export YOUTUBE_API_KEY='your-api-key-here'"
            )
    
    # Check Rumble API token
    if platforms.get("rumble", {}).get("enabled"):
        api_token = platforms["rumble"].get("api_token")
        if not api_token or api_token.startswith("${"):
            raise ConfigurationError(
                "Rumble platform is enabled but API token is missing.\n"
                "To fix this:\n"
                "1. Set the RUMBLE_API_TOKEN environment variable\n"
                "2. Or add the token directly to config.yaml\n"
                "3. Or disable Rumble in config by setting 'enabled: false'\n"
                "\nExample: export RUMBLE_API_TOKEN='your-api-token-here'"
            )
