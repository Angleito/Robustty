#!/usr/bin/env python3
"""
Automatic Cookie Sync to VPS
Runs after each cookie extraction to sync cookies to VPS
"""
import os
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def sync_cookies_to_vps():
    """Sync cookies to VPS using rsync over SSH"""
    
    # Get VPS configuration from environment
    vps_host = os.getenv('VPS_HOST')
    vps_user = os.getenv('VPS_USER', 'ubuntu')
    vps_path = os.getenv('VPS_PATH', '~/robustty-bot/cookies')
    
    if not vps_host:
        logger.warning("VPS_HOST not set, skipping cookie sync")
        return False
    
    cookie_dir = Path('/app/cookies')
    if not cookie_dir.exists():
        logger.error("Cookie directory not found")
        return False
    
    # Create timestamp file
    timestamp_file = cookie_dir / 'last_sync.txt'
    timestamp_file.write_text(datetime.now().isoformat())
    
    try:
        # Use rsync to sync cookies
        # Note: SSH key must be mounted in container for this to work
        cmd = [
            'rsync', '-avz', '--delete',
            f'{cookie_dir}/',
            f'{vps_user}@{vps_host}:{vps_path}/'
        ]
        
        logger.info(f"Syncing cookies to {vps_user}@{vps_host}:{vps_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Cookie sync completed successfully")
            logger.debug(f"Synced files: {result.stdout}")
            return True
        else:
            logger.error(f"Cookie sync failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error syncing cookies: {e}")
        return False

def main():
    """Main function called after cookie extraction"""
    logger.info("Starting automatic cookie sync to VPS")
    
    # Check if auto-sync is enabled
    if os.getenv('AUTO_SYNC_VPS', 'false').lower() != 'true':
        logger.info("Auto-sync to VPS is disabled (set AUTO_SYNC_VPS=true to enable)")
        return
    
    # Perform sync
    success = sync_cookies_to_vps()
    
    if success:
        logger.info("✅ Cookies successfully synced to VPS")
    else:
        logger.warning("⚠️  Cookie sync to VPS failed or skipped")

if __name__ == '__main__':
    main()