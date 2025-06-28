#!/usr/bin/env python3
"""
Initialize missing cookie files for platforms that work without authentication.
This prevents warning messages for platforms like PeerTube and Odysee.
"""

import json
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Platforms that can work without cookies
COOKIE_OPTIONAL_PLATFORMS = ["peertube", "odysee"]

def create_empty_cookie_files():
    """Create empty cookie files for platforms that don't require authentication"""
    
    # Find cookie directory
    cookie_paths = [
        Path('/app/cookies'),
        Path('./cookies'),
        Path('data/cookies')
    ]
    
    cookie_dir = None
    for path in cookie_paths:
        if path.exists():
            cookie_dir = path
            break
    
    if not cookie_dir:
        # Create default cookie directory
        cookie_dir = Path('./cookies')
        cookie_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Using cookie directory: {cookie_dir}")
    
    # Create empty cookie files for optional platforms
    for platform in COOKIE_OPTIONAL_PLATFORMS:
        cookie_file = cookie_dir / f'{platform}_cookies.json'
        
        if not cookie_file.exists():
            logger.info(f"Creating empty cookie file for {platform}")
            
            # Create minimal cookie structure
            empty_cookies = []
            
            # Add a placeholder cookie to prevent "empty file" warnings
            placeholder_cookie = {
                "name": f"{platform}_placeholder",
                "value": "placeholder",
                "domain": f".{platform}.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "sameSite": "None",
                "expires": None,  # Session cookie
                "_comment": f"Placeholder cookie for {platform} - platform works without authentication"
            }
            empty_cookies.append(placeholder_cookie)
            
            try:
                with open(cookie_file, 'w') as f:
                    json.dump(empty_cookies, f, indent=2)
                logger.info(f"Created {platform} cookie file with placeholder")
            except Exception as e:
                logger.error(f"Failed to create {platform} cookie file: {e}")
        else:
            # Check if existing file is empty or invalid
            try:
                with open(cookie_file, 'r') as f:
                    content = f.read().strip()
                    if not content or content == "[]":
                        logger.info(f"Updating empty {platform} cookie file")
                        # Rewrite with placeholder
                        placeholder_cookie = {
                            "name": f"{platform}_placeholder",
                            "value": "placeholder",
                            "domain": f".{platform}.com",
                            "path": "/",
                            "secure": True,
                            "httpOnly": False,
                            "sameSite": "None",
                            "expires": None
                        }
                        with open(cookie_file, 'w') as f:
                            json.dump([placeholder_cookie], f, indent=2)
                        logger.info(f"Updated {platform} cookie file with placeholder")
            except Exception as e:
                logger.warning(f"Could not check {platform} cookie file: {e}")

def main():
    """Main function"""
    logger.info("Initializing missing cookie files for optional platforms")
    
    create_empty_cookie_files()
    
    # Create timestamp file
    cookie_dir = Path('./cookies')
    if cookie_dir.exists():
        timestamp_file = cookie_dir / 'cookie_init_timestamp.txt'
        timestamp_file.write_text(f"Cookie initialization completed at {datetime.now().isoformat()}\n")
    
    logger.info("Cookie initialization completed")

if __name__ == '__main__':
    main()