import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))


import yaml  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from src.bot.bot import RobusttyBot  # noqa: E402
from src.utils.config_loader import load_config, ConfigurationError  # noqa: E402
from src.services.metrics_server import MetricsServer  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/robustty.log")],
)

logger = logging.getLogger(__name__)


# Removed the old load_config function - now using the one from config_loader


async def main() -> None:
    """Main entry point"""
    bot: Optional[RobusttyBot] = None
    metrics_server: Optional[MetricsServer] = None
    try:
        # Load .env file
        load_dotenv()
        
        # Load configuration
        config = load_config("config/config.yaml")

        # Get Discord token
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            logger.error("DISCORD_TOKEN not found in environment")
            sys.exit(1)

        # Start metrics server
        metrics_port = int(os.getenv("METRICS_PORT", "8080"))
        metrics_server = MetricsServer(port=metrics_port)
        await metrics_server.start()
        logger.info(f"Metrics server started on port {metrics_port}")

        # Create and run bot
        bot = RobusttyBot(config)

        logger.info("Starting Robustty Music Bot...")
        await bot.start(token)

    except ConfigurationError as e:
        logger.error(f"Configuration Error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if bot is not None:
            await bot.close()
        if metrics_server is not None:
            await metrics_server.stop()


if __name__ == "__main__":
    asyncio.run(main())
