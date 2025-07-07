#!/usr/bin/env python3
"""
Convert Netscape format cookies (.txt) to JSON format for the bot
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_netscape_cookie(line: str) -> Optional[Dict]:
    """Parse a single line from Netscape cookie format"""
    if not line or line.startswith('#'):
        return None
    
    parts = line.strip().split('\t')
    if len(parts) != 7:
        return None
    
    domain, include_subdomains, path, secure, expires, name, value = parts
    
    return {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
        "secure": secure.upper() == "TRUE",
        "httpOnly": False,  # Netscape format doesn't store this info
        "expires": int(expires) if expires != "0" else None
    }

def convert_netscape_to_json(txt_path: Path) -> List[Dict]:
    """Convert Netscape format cookies to JSON format"""
    cookies = []
    
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                cookie = parse_netscape_cookie(line)
                if cookie:
                    cookies.append(cookie)
    except Exception as e:
        logger.error(f"Error reading {txt_path}: {e}")
        return []
    
    return cookies

def convert_all_cookies(cookie_dir: Path):
    """Convert all .txt cookie files to .json format"""
    platforms = ['youtube', 'youtube_music', 'rumble', 'odysee', 'peertube']
    
    for platform in platforms:
        txt_file = cookie_dir / f"{platform}_cookies.txt"
        json_file = cookie_dir / f"{platform}_cookies.json"
        
        if txt_file.exists():
            logger.info(f"Converting {platform} cookies from Netscape to JSON format")
            cookies = convert_netscape_to_json(txt_file)
            
            if cookies:
                try:
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(cookies, f, indent=2)
                    logger.info(f"Successfully converted {len(cookies)} cookies for {platform}")
                except Exception as e:
                    logger.error(f"Error writing JSON for {platform}: {e}")
            else:
                logger.warning(f"No valid cookies found in {txt_file}")
        else:
            # Check if JSON already exists, if not create empty one
            if not json_file.exists():
                logger.info(f"Creating empty cookie file for {platform}")
                with open(json_file, 'w') as f:
                    json.dump([], f)

def main():
    """Main conversion function"""
    # Cookie directories to check
    cookie_dirs = [
        Path('/app/cookies'),
        Path('/app/data/cookies'),
        Path('./cookies')
    ]
    
    # Find the first existing directory
    cookie_dir = None
    for dir_path in cookie_dirs:
        if dir_path.exists():
            cookie_dir = dir_path
            logger.info(f"Using cookie directory: {cookie_dir}")
            break
    
    if not cookie_dir:
        logger.error("No cookie directory found")
        return
    
    # Convert all cookies
    convert_all_cookies(cookie_dir)
    logger.info("Cookie conversion complete")

if __name__ == "__main__":
    main()