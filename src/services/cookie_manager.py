import json
import logging
from pathlib import Path
from typing import Dict, Optional, List
import asyncio
import aiofiles

from ..extractors.cross_platform_cookies import CrossPlatformCookieExtractor

logger = logging.getLogger(__name__)


class CookieManager:
    """Manages cookies for authenticated platform access"""

    def __init__(self, config: Dict):
        self.config = config
        self.cookie_dir = Path("data/cookies")
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.cookies: Dict[str, List[Dict]] = {}
        self.extractor = CrossPlatformCookieExtractor()
        self._extraction_lock = asyncio.Lock()

    async def load_cookies(self):
        """Load cookies from storage"""
        for platform in ["youtube", "peertube", "odysee", "rumble"]:
            cookie_file = self.cookie_dir / f"{platform}_cookies.json"
            if cookie_file.exists():
                try:
                    async with aiofiles.open(cookie_file, "r") as f:
                        content = await f.read()
                        self.cookies[platform] = json.loads(content)
                        logger.info(f"Loaded cookies for {platform}")
                except Exception as e:
                    logger.error(f"Failed to load cookies for {platform}: {e}")

    async def save_cookies(self, platform: str, cookies: List[Dict]):
        """Save cookies for a platform"""
        cookie_file = self.cookie_dir / f"{platform}_cookies.json"
        try:
            async with aiofiles.open(cookie_file, "w") as f:
                await f.write(json.dumps(cookies, indent=2))
            self.cookies[platform] = cookies
            logger.info(f"Saved {len(cookies)} cookies for {platform}")
        except Exception as e:
            logger.error(f"Failed to save cookies for {platform}: {e}")

    def get_cookies(self, platform: str) -> Optional[List[Dict]]:
        """Get cookies for a platform"""
        return self.cookies.get(platform)

    async def extract_browser_cookies(self, platform: str):
        """Extract cookies from browser profile using cross-platform extractor"""
        async with self._extraction_lock:
            try:
                logger.info(f"Extracting browser cookies for {platform}")
                
                # Run extraction in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                cookies = await loop.run_in_executor(
                    None, 
                    self._extract_platform_cookies, 
                    platform
                )
                
                if cookies:
                    await self.save_cookies(platform, cookies)
                    logger.info(f"Extracted and saved {len(cookies)} cookies for {platform}")
                else:
                    logger.warning(f"No cookies found for {platform}")
                    
            except Exception as e:
                logger.error(f"Failed to extract cookies for {platform}: {e}")
    
    def _extract_platform_cookies(self, platform: str) -> List[Dict]:
        """Extract cookies for a specific platform (sync method for executor)"""
        jar = self.extractor.find_platform_cookies(platform)
        
        # Convert CookieJar to list of dicts
        cookies = []
        for cookie in jar:
            cookies.append({
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path,
                'secure': cookie.secure,
                'httpOnly': False,  # Default since RequestsCookieJar doesn't track this
                'sameSite': 'None'
            })
        
        return cookies

    async def refresh_cookies(self):
        """Refresh all cookies"""
        for platform in ["youtube", "peertube", "odysee", "rumble"]:
            await self.extract_browser_cookies(platform)

    async def cleanup(self):
        """Cleanup resources"""
        # Save any pending cookies
        pass
    
    def get_cookie_jar(self, platform: str):
        """Get a requests CookieJar for a platform"""
        import requests
        
        jar = requests.cookies.RequestsCookieJar()
        cookies = self.get_cookies(platform)
        
        if cookies:
            for cookie in cookies:
                jar.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie.get('domain', ''),
                    path=cookie.get('path', '/'),
                    secure=cookie.get('secure', False)
                )
        
        return jar
