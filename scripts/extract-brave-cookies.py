#!/usr/bin/env python3
"""
Brave Browser Cookie Extraction Script for Docker Container

This script extracts cookies from Brave browser mounted from the host system
and saves them in yt-dlp compatible format for the Discord bot.
"""

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Platform domains for cookie filtering
PLATFORM_DOMAINS = {
    'youtube': ['.youtube.com', 'youtube.com', 'www.youtube.com'],
    'rumble': ['.rumble.com', 'rumble.com'],
    'odysee': ['.odysee.com', 'odysee.com'],
    'peertube': ['framatube.org', 'video.ploud.fr', 'peertube.social']
}


def extract_brave_cookies_from_host(brave_base_path: Path = None) -> Dict[str, List[dict]]:
    """Extract cookies from Brave browser directory"""
    
    # Use provided path or default to mounted path
    if brave_base_path is None:
        brave_base_path = Path('/host-brave')
    
    cookies_db_path = brave_base_path / 'Default' / 'Cookies'
    
    if not cookies_db_path.exists():
        logger.error(f"Brave cookies database not found at {cookies_db_path}")
        return {}
    
    # Copy cookies database to temporary location (SQLite doesn't like shared access)
    import tempfile
    import shutil
    
    # Use secure temporary file with automatic cleanup
    temp_fd, temp_db_path = tempfile.mkstemp(suffix='.db', prefix='brave_cookies_')
    temp_db = Path(temp_db_path)
    
    try:
        os.close(temp_fd)  # Close file descriptor, keep path
        shutil.copy2(cookies_db_path, temp_db)
    except Exception as e:
        logger.error(f"Failed to copy cookies database: {e}")
        temp_db.unlink(missing_ok=True)
        return {}
    
    extracted_cookies = {}
    
    try:
        # Connect to SQLite database with timeout and read-only mode
        conn = sqlite3.connect(f'file:{temp_db}?mode=ro', uri=True, timeout=10.0)
        cursor = conn.cursor()
        
        # Query cookies table
        cursor.execute("""
            SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly
            FROM cookies
            WHERE expires_utc > ?
        """, (int(time.time() * 1000000),))  # Current time in microseconds
        
        rows = cursor.fetchall()
        logger.info(f"Found {len(rows)} valid cookies in Brave browser")
        
        # Group cookies by platform
        for platform, domains in PLATFORM_DOMAINS.items():
            platform_cookies = []
            
            for row in rows:
                name, value, host_key, path, expires_utc, is_secure, is_httponly = row
                
                # Check if cookie belongs to this platform
                if any(domain in host_key for domain in domains):
                    cookie_data = {
                        'name': name,
                        'value': value,
                        'domain': host_key,
                        'path': path,
                        'secure': bool(is_secure),
                        'httpOnly': bool(is_httponly),
                        'expires': expires_utc // 1000000 if expires_utc else None  # Convert to seconds
                    }
                    platform_cookies.append(cookie_data)
            
            if platform_cookies:
                extracted_cookies[platform] = platform_cookies
                logger.info(f"Extracted {len(platform_cookies)} cookies for {platform}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error extracting cookies: {e}")
    except Exception as e:
        logger.error(f"Failed to extract cookies from database: {e}")
    
    finally:
        # Clean up temporary database
        temp_db.unlink(missing_ok=True)
    
    return extracted_cookies


def save_cookies_to_files(cookies: Dict[str, List[dict]]) -> None:
    """Save extracted cookies to platform-specific JSON files"""
    
    # Try standardized paths in order of preference
    cookie_paths = [
        Path('/app/cookies'),
        Path('./cookies'),
        Path('data/cookies')
    ]
    
    cookie_dir = None
    for path in cookie_paths:
        try:
            path.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = path / '.test_write'
            test_file.touch()
            test_file.unlink()
            cookie_dir = path
            break
        except (PermissionError, OSError):
            continue
    
    if cookie_dir is None:
        # Last resort fallback
        cookie_dir = Path('./cookies')
        cookie_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Using cookie directory: {cookie_dir}")
    
    for platform, platform_cookies in cookies.items():
        output_file = cookie_dir / f'{platform}_cookies.json'
        
        try:
            with open(output_file, 'w') as f:
                json.dump(platform_cookies, f, indent=2)
            
            logger.info(f"Saved {len(platform_cookies)} {platform} cookies to {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to save {platform} cookies: {e}")


def main():
    """Main extraction function with enhanced security monitoring"""
    start_time = time.time()
    logger.info("Starting Brave browser cookie extraction...")
    
    try:
        # Check if running in Docker or locally
        brave_path = Path('/host-brave')
        if not brave_path.exists():
            # Try local path for testing
            brave_path = Path(os.path.expanduser('~/Library/Application Support/BraveSoftware/Brave-Browser'))
            if not brave_path.exists():
                logger.error("Brave browser data not found. Please check path or Docker volumes.")
                return
            logger.info("Using local Brave browser data for testing")
        
        # Verify Brave path is readable and looks legitimate
        if not brave_path.is_dir():
            logger.error(f"Brave path exists but is not a directory: {brave_path}")
            return
            
        # Extract cookies
        cookies = extract_brave_cookies_from_host(brave_path)
        
        if not cookies:
            logger.warning("No cookies extracted from Brave browser")
            return
        
        # Security check: Log cookie counts but not contents
        total_cookies = sum(len(platform_cookies) for platform_cookies in cookies.values())
        logger.info(f"Extracted {total_cookies} total cookies across {len(cookies)} platforms")
        
        # Save cookies to files
        save_cookies_to_files(cookies)
        
        elapsed = time.time() - start_time
        logger.info(f"Cookie extraction completed successfully in {elapsed:.2f}s")
        
        # Auto-sync to VPS if enabled
        if os.getenv('AUTO_SYNC_VPS', 'false').lower() == 'true':
            try:
                import subprocess
                logger.info("Starting auto-sync to VPS...")
                result = subprocess.run(['python3', '/app/scripts/auto-sync-cookies.py'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info("Auto-sync to VPS completed")
                else:
                    logger.warning(f"Auto-sync to VPS failed: {result.stderr}")
            except Exception as e:
                logger.error(f"Failed to run auto-sync: {e}")
        
    except Exception as e:
        logger.error(f"Cookie extraction failed with unexpected error: {e}")
        import traceback
        logger.debug(f"Full traceback: {traceback.format_exc()}")
        raise


if __name__ == '__main__':
    main()