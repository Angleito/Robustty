#!/usr/bin/env python3
"""
Test script to verify that aiohttp connections are properly cleaned up
and no "Unclosed connection" warnings appear during bot shutdown.
"""

import asyncio
import logging
import sys
import warnings
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging to capture warnings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Capture aiohttp warnings
warnings.filterwarnings('always', category=ResourceWarning)

logger = logging.getLogger(__name__)


async def test_session_manager():
    """Test the HTTP session manager"""
    from src.services.http_session_manager import get_session_manager
    
    logger.info("Testing HTTP session manager...")
    
    # Get the session manager
    manager = get_session_manager()
    
    # Create some test sessions
    for i in range(3):
        session = await manager.get_session(f"test_{i}")
        logger.info(f"Created session test_{i}")
    
    # Check health
    health = await manager.health_check()
    logger.info(f"Session health: {health}")
    
    # Get stats
    stats = manager.get_stats()
    logger.info(f"Session stats: {stats}")
    
    # Cleanup
    await manager.close_all()
    logger.info("All sessions closed")


async def test_platform_sessions():
    """Test platform session management"""
    from src.platforms.youtube import YouTubePlatform
    from src.services.cache_manager import CacheManager
    from src.utils.config_loader import load_config
    
    logger.info("Testing platform session management...")
    
    # Load config
    config = load_config()
    
    # Create cache manager
    cache_manager = CacheManager(config)
    await cache_manager.initialize()
    
    # Create platform
    platform = YouTubePlatform("youtube", config["platforms"]["youtube"], cache_manager)
    
    # Initialize (should create session via manager)
    await platform.initialize()
    logger.info("Platform initialized")
    
    # Do a test validation
    test_url = "https://www.youtube.com/"
    is_valid = await platform._validate_stream_url_async(test_url)
    logger.info(f"URL validation result: {is_valid}")
    
    # Cleanup
    await platform.cleanup()
    logger.info("Platform cleaned up")
    
    # Cleanup cache manager
    await cache_manager.close()
    logger.info("Cache manager closed")


async def test_bot_shutdown():
    """Test bot shutdown sequence"""
    from src.bot.bot import RobusttyBot
    from src.utils.config_loader import load_config
    
    logger.info("Testing bot shutdown sequence...")
    
    # Load config
    config = load_config()
    
    # Create bot instance
    bot = RobusttyBot(config)
    
    # Setup bot (but don't run it)
    await bot.setup_hook()
    logger.info("Bot setup completed")
    
    # Simulate some activity
    from src.services.http_session_manager import get_session_manager
    manager = get_session_manager()
    
    # Create some sessions
    for platform in ["youtube", "odysee", "rumble"]:
        session = await manager.get_session(f"platform_{platform}")
        logger.info(f"Created session for {platform}")
    
    # Check session stats before shutdown
    stats_before = manager.get_stats()
    logger.info(f"Sessions before shutdown: {stats_before}")
    
    # Shutdown bot
    logger.info("Starting bot shutdown...")
    await bot.close()
    logger.info("Bot shutdown completed")
    
    # Check for any remaining sessions
    stats_after = manager.get_stats()
    logger.info(f"Sessions after shutdown: {stats_after}")
    
    if stats_after['stats']['active'] > 0:
        logger.warning(f"WARNING: {stats_after['stats']['active']} sessions still active after shutdown!")
    else:
        logger.info("SUCCESS: All sessions properly closed!")


async def main():
    """Run all tests"""
    logger.info("Starting connection cleanup tests...")
    
    try:
        # Test 1: Session manager
        await test_session_manager()
        logger.info("-" * 50)
        
        # Test 2: Platform sessions
        await test_platform_sessions()
        logger.info("-" * 50)
        
        # Test 3: Bot shutdown
        await test_bot_shutdown()
        logger.info("-" * 50)
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)
    
    # Give a moment for any cleanup
    await asyncio.sleep(2)
    
    # Final check for warnings
    logger.info("Test complete. Check output above for any 'Unclosed connection' warnings.")


if __name__ == "__main__":
    # Run with warnings enabled
    import warnings
    warnings.simplefilter("always", ResourceWarning)
    
    # Run tests
    asyncio.run(main())