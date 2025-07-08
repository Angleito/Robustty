"""
Enhanced environment variable loader for Docker environments
Ensures proper loading of Discord token and other environment variables
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def load_discord_token() -> Optional[str]:
    """
    Load Discord token with multiple fallback methods
    Handles Docker environment variable loading issues
    """
    token = None
    
    # Method 1: Direct environment variable (Docker)
    token = os.environ.get('DISCORD_TOKEN')
    if token and token not in ['your_discord_bot_token_here', 'YOUR_ACTUAL_BOT_TOKEN_HERE']:
        logger.info("Discord token loaded from environment variable")
        return token.strip()
    
    # Method 2: Try loading from .env file if not in Docker
    if not os.environ.get('DOCKER_CONTAINER'):
        try:
            from dotenv import load_dotenv
            
            # Try multiple .env locations
            env_paths = [
                Path('.env'),
                Path('/app/.env'),
                Path.cwd() / '.env'
            ]
            
            for env_path in env_paths:
                if env_path.exists():
                    load_dotenv(env_path, override=True)
                    logger.info(f"Loaded .env from {env_path}")
                    token = os.getenv('DISCORD_TOKEN')
                    if token and token not in ['your_discord_bot_token_here', 'YOUR_ACTUAL_BOT_TOKEN_HERE']:
                        logger.info("Discord token loaded from .env file")
                        return token.strip()
        except Exception as e:
            logger.warning(f"Error loading .env file: {e}")
    
    # Method 3: Check for token in specific Docker paths
    docker_env_paths = ['/app/.env', '/robustty/.env']
    for path in docker_env_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    for line in f:
                        if line.startswith('DISCORD_TOKEN='):
                            token = line.split('=', 1)[1].strip().strip('"\'')
                            if token and token not in ['your_discord_bot_token_here', 'YOUR_ACTUAL_BOT_TOKEN_HERE']:
                                logger.info(f"Discord token loaded from {path}")
                                return token
            except Exception as e:
                logger.warning(f"Error reading {path}: {e}")
    
    # Log all Discord-related environment variables for debugging
    discord_vars = {k: v[:20] + '...' if len(v) > 20 else v 
                   for k, v in os.environ.items() 
                   if 'DISCORD' in k.upper()}
    if discord_vars:
        logger.debug(f"Discord-related environment variables: {discord_vars}")
    
    return None

def validate_token(token: str) -> bool:
    """
    Validate Discord token format
    """
    if not token:
        return False
    
    # Check for placeholder values
    placeholders = ['your_discord_bot_token_here', 'YOUR_ACTUAL_BOT_TOKEN_HERE', 
                   'your_bot_token', 'YOUR_BOT_TOKEN']
    if token.lower() in [p.lower() for p in placeholders]:
        return False
    
    # Basic format validation
    # Discord tokens are typically 59+ characters
    if len(token) < 50:
        logger.warning(f"Token appears too short: {len(token)} characters")
        return False
    
    # Check for common formatting issues
    if ' ' in token:
        logger.warning("Token contains spaces")
        return False
    
    if token.startswith('Bot '):
        logger.warning("Token includes 'Bot ' prefix - this should be removed")
        return False
    
    return True