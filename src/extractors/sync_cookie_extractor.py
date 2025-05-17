#!/usr/bin/env python3
"""
Cookie extractor that syncs to remote VPS
"""
import json
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
import subprocess
import aiofiles

logger = logging.getLogger(__name__)

class SyncCookieExtractor:
    """Extracts cookies locally and syncs to VPS"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.local_cookie_dir = Path("/app/cookies")
        self.vps_host = config.get("VPS_HOST")
        self.vps_user = config.get("VPS_USER")
        self.vps_path = config.get("VPS_PATH")
        self.ssh_key = config.get("VPS_SSH_KEY", "/app/ssh/id_rsa")
        
    async def sync_to_vps(self, cookie_file: Path):
        """Sync cookie file to VPS"""
        if not all([self.vps_host, self.vps_user, self.vps_path]):
            logger.warning("VPS configuration incomplete, skipping sync")
            return
            
        remote_path = f"{self.vps_user}@{self.vps_host}:{self.vps_path}/data/cookies/"
        
        try:
            # Use rsync with SSH key
            cmd = [
                "rsync", "-avz", "--mkpath",
                "-e", f"ssh -i {self.ssh_key} -o StrictHostKeyChecking=no",
                str(cookie_file),
                remote_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Successfully synced {cookie_file.name} to VPS")
            else:
                logger.error(f"Failed to sync: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Error syncing to VPS: {e}")
    
    async def extract_and_sync(self, platform: str):
        """Extract cookies and sync to VPS"""
        try:
            # Extract cookies using existing method
            cookies = await self.extract_platform_cookies(platform)
            
            if cookies:
                # Save locally
                cookie_file = self.local_cookie_dir / f"{platform}_cookies.json"
                async with aiofiles.open(cookie_file, "w") as f:
                    await f.write(json.dumps(cookies, indent=2))
                
                # Sync to VPS
                await self.sync_to_vps(cookie_file)
                
                logger.info(f"Extracted and synced {len(cookies)} cookies for {platform}")
            else:
                logger.warning(f"No cookies found for {platform}")
                
        except Exception as e:
            logger.error(f"Error processing {platform}: {e}")
    
    async def run_continuous(self):
        """Run extraction continuously"""
        interval = int(self.config.get("REFRESH_INTERVAL", 86400))
        
        while True:
            for platform in ["youtube", "odysee", "rumble"]:
                await self.extract_and_sync(platform)
            
            logger.info(f"Waiting {interval} seconds until next extraction")
            await asyncio.sleep(interval)