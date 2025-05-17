import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

from bot.bot import RobusttyBot
import yaml
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/robustty.log')
    ]
)

logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from file and environment"""
    load_dotenv()
    
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Replace environment variables in config
    def replace_env_vars(obj):
        if isinstance(obj, dict):
            return {k: replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            env_var = obj[2:-1]
            value = os.getenv(env_var, obj)
            # Convert string booleans to actual booleans
            if value.lower() in ['true', 'false']:
                return value.lower() == 'true'
            return value
        return obj
    
    return replace_env_vars(config)

async def main():
    """Main entry point"""
    try:
        # Load configuration
        config = load_config()
        
        # Get Discord token
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            logger.error("DISCORD_TOKEN not found in environment")
            return
        
        # Create and run bot
        bot = RobusttyBot(config)
        
        logger.info("Starting Robustty Music Bot...")
        await bot.start(token)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())