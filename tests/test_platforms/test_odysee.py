#!/usr/bin/env python3
"""Test Odysee platform implementation"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.platforms.odysee import OdyseePlatform
from src.utils.config_loader import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_odysee():
    """Test Odysee platform functionality"""
    # Load config
    config = load_config()
    
    # Create Odysee platform instance
    odysee_config = config["platforms"]["odysee"]
    odysee_config["enabled"] = True  # Force enable for testing
    
    platform = OdyseePlatform("odysee", odysee_config)
    
    try:
        await platform.initialize()
        logger.info("Platform initialized successfully")
        
        # Test search
        logger.info("Testing search...")
        results = await platform.search_videos("blockchain", max_results=5)
        
        if results:
            logger.info(f"Found {len(results)} videos")
            for i, video in enumerate(results):
                logger.info(f"Video {i+1}: {video['title']} by {video['channel']}")
                logger.info(f"  URL: {video['url']}")
                logger.info(f"  ID: {video['id']}")
        else:
            logger.warning("No search results found")
        
        # Test URL parsing
        test_url = "https://odysee.com/@Channel:6/video-title:2"
        video_id = platform.extract_video_id(test_url)
        logger.info(f"Extracted video ID from {test_url}: {video_id}")
        
        # Test platform URL check
        is_odysee = platform.is_platform_url(test_url)
        logger.info(f"Is Odysee URL: {is_odysee}")
        
        # Test getting video details
        if results and results[0].get("id"):
            logger.info("Testing get video details...")
            details = await platform.get_video_details(results[0]["id"])
            if details:
                logger.info(f"Got details for: {details['title']}")
            else:
                logger.warning("Could not get video details")
        
    finally:
        await platform.cleanup()
        logger.info("Cleanup completed")


if __name__ == "__main__":
    asyncio.run(test_odysee())