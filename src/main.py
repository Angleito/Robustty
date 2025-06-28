import asyncio
import logging
import os
import signal
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
from src.utils.network_connectivity import run_preflight_checks  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/robustty.log")],
)

logger = logging.getLogger(__name__)


# Removed the old load_config function - now using the one from config_loader


async def main() -> None:
    """Main entry point with proper signal handling"""
    bot: Optional[RobusttyBot] = None
    metrics_server: Optional[MetricsServer] = None
    shutdown_event = asyncio.Event()
    
    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        shutdown_event.set()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
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

        # Run preflight network checks (non-blocking)
        try:
            preflight_result = await run_preflight_checks(config)
            if not preflight_result:
                logger.warning("Preflight network checks failed - continuing with degraded connectivity")
                logger.warning("Some features may not work optimally")
            else:
                logger.info("Preflight network checks passed")
        except Exception as e:
            logger.warning(f"Preflight network checks encountered error: {e}")
            logger.warning("Continuing startup despite network check failure")

        # Create bot first
        bot = RobusttyBot(config)

        # Start metrics server with bot reference
        metrics_port = int(os.getenv("METRICS_PORT", "8080"))
        metrics_server = MetricsServer(port=metrics_port)
        metrics_server.bot = bot  # Add bot reference for health checks
        await metrics_server.start()
        logger.info(f"Metrics server started on port {metrics_port}")

        logger.info("Starting Robustty Music Bot...")
        
        # Create task for bot startup
        bot_task = asyncio.create_task(bot.start(token))
        
        # Wait for either shutdown signal or bot to finish
        done, pending = await asyncio.wait(
            [bot_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # If shutdown was requested, close the bot gracefully
        if shutdown_event.is_set():
            logger.info("Shutdown signal received, closing bot gracefully...")
            if bot and not bot.is_closed():
                await bot.close()
        else:
            # Bot finished on its own, check for exceptions
            for task in done:
                if task.exception():
                    raise task.exception()

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
        logger.info("Cleaning up resources...")
        
        # Cleanup bot
        if bot is not None:
            try:
                if not bot.is_closed():
                    await bot.close()
                logger.info("Bot closed successfully")
            except Exception as e:
                logger.error(f"Error closing bot: {e}")
        
        # Cleanup metrics server
        if metrics_server is not None:
            try:
                await metrics_server.stop()
                logger.info("Metrics server stopped")
            except Exception as e:
                logger.error(f"Error stopping metrics server: {e}")
        
        logger.info("Cleanup completed")


if __name__ == "__main__":
    asyncio.run(main())
