#!/usr/bin/env python3
"""
Ensure all platform cookie files exist (create empty ones if missing)
This prevents "cookie file not found" warnings in the bot logs.
"""

import json
import logging
from pathlib import Path
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# All platforms that need cookie files
PLATFORMS = ['youtube', 'rumble', 'odysee', 'peertube']

def get_cookie_directory() -> Path:
    """Get the cookie directory, trying multiple paths"""
    cookie_paths = [
        Path('/app/cookies'),
        Path('./cookies'), 
        Path('data/cookies')
    ]
    
    for path in cookie_paths:
        if path.exists() and path.is_dir():
            return path
    
    # Create default if none exist
    default_path = Path('/app/cookies')
    default_path.mkdir(parents=True, exist_ok=True)
    return default_path

def ensure_cookie_files() -> None:
    """Ensure all platforms have cookie files (create empty ones if missing)"""
    cookie_dir = get_cookie_directory()
    logger.info(f"Using cookie directory: {cookie_dir}")
    
    for platform in PLATFORMS:
        cookie_file = cookie_dir / f'{platform}_cookies.json'
        
        if not cookie_file.exists():
            logger.info(f"Creating empty cookie file for {platform}")
            
            # Create empty cookie array
            empty_cookies: List = []
            
            try:
                with open(cookie_file, 'w') as f:
                    json.dump(empty_cookies, f, indent=2)
                
                logger.info(f"Created empty cookie file: {cookie_file}")
                
            except Exception as e:
                logger.error(f"Failed to create cookie file for {platform}: {e}")
        else:
            # Verify existing file is valid JSON
            try:
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                
                if isinstance(cookies, list):
                    logger.info(f"Valid cookie file exists for {platform} ({len(cookies)} cookies)")
                else:
                    logger.warning(f"Invalid cookie file format for {platform}, fixing...")
                    with open(cookie_file, 'w') as f:
                        json.dump([], f, indent=2)
                    
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Corrupted cookie file for {platform}, recreating: {e}")
                try:
                    with open(cookie_file, 'w') as f:
                        json.dump([], f, indent=2)
                    logger.info(f"Recreated cookie file for {platform}")
                except Exception as e2:
                    logger.error(f"Failed to recreate cookie file for {platform}: {e2}")

def main():
    """Main function"""
    logger.info("Ensuring all platform cookie files exist...")
    ensure_cookie_files()
    logger.info("Cookie file check completed")

if __name__ == '__main__':
    main()