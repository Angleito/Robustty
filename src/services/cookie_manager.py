import json
import os
import logging
from typing import Dict, Optional
from pathlib import Path
import aiofiles

logger = logging.getLogger(__name__)

class CookieManager:
    """Manages cookies for authenticated platform access"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.cookie_dir = Path("data/cookies")
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.cookies: Dict[str, Dict] = {}
    
    async def load_cookies(self):
        """Load cookies from storage"""
        for platform in ['youtube', 'peertube', 'odysee', 'rumble']:
            cookie_file = self.cookie_dir / f"{platform}_cookies.json"
            if cookie_file.exists():
                try:
                    async with aiofiles.open(cookie_file, 'r') as f:
                        content = await f.read()
                        self.cookies[platform] = json.loads(content)
                        logger.info(f"Loaded cookies for {platform}")
                except Exception as e:
                    logger.error(f"Failed to load cookies for {platform}: {e}")
    
    async def save_cookies(self, platform: str, cookies: Dict):
        """Save cookies for a platform"""
        cookie_file = self.cookie_dir / f"{platform}_cookies.json"
        try:
            async with aiofiles.open(cookie_file, 'w') as f:
                await f.write(json.dumps(cookies, indent=2))
            self.cookies[platform] = cookies
            logger.info(f"Saved cookies for {platform}")
        except Exception as e:
            logger.error(f"Failed to save cookies for {platform}: {e}")
    
    def get_cookies(self, platform: str) -> Optional[Dict]:
        """Get cookies for a platform"""
        return self.cookies.get(platform)
    
    async def extract_browser_cookies(self, platform: str):
        """Extract cookies from browser profile"""
        # This would interact with the cookie extraction service
        try:
            # Send request to cookie extraction service
            # For now, this is a placeholder
            logger.info(f"Extracting cookies for {platform}")
            # cookies = await self._request_cookie_extraction(platform)
            # await self.save_cookies(platform, cookies)
        except Exception as e:
            logger.error(f"Failed to extract cookies for {platform}: {e}")
    
    async def refresh_cookies(self):
        """Refresh all cookies"""
        for platform in ['youtube', 'peertube', 'odysee', 'rumble']:
            await self.extract_browser_cookies(platform)
    
    async def cleanup(self):
        """Cleanup resources"""
        # Save any pending cookies
        pass