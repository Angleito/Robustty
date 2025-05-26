"""Cross-platform cookie extraction with unified API"""
import logging
import concurrent.futures
from typing import Dict, List, Optional
import requests
from pathlib import Path

from .browser_paths import detect_os, find_profiles, get_cookie_db_path
from .cookie_database import (
    extract_sqlite_cookies, 
    filter_expired_cookies,
    filter_cookies_by_domain,
    Cookie
)
from .cookie_decryption import decrypt_value

logger = logging.getLogger(__name__)

# Default supported browsers
SUPPORTED_BROWSERS = ['chrome', 'chromium', 'edge', 'brave', 'opera', 'firefox']


class CrossPlatformCookieExtractor:
    """Cross-platform cookie extraction with unified API"""
    
    def __init__(self, browsers: Optional[List[str]] = None):
        """Initialize extractor
        
        Args:
            browsers: List of browsers to extract from (default: all supported)
        """
        self.browsers = browsers or SUPPORTED_BROWSERS
        self.os_name = detect_os()
        logger.info(f"Initialized cookie extractor for {self.os_name}")
    
    def extract_all_cookies(self, domains: Optional[List[str]] = None) -> Dict[str, List[Cookie]]:
        """Extract cookies from all browsers
        
        Args:
            domains: Optional list of domains to filter cookies
            
        Returns:
            Dict mapping browser names to lists of cookies
        """
        all_cookies = {}
        
        # Use ThreadPoolExecutor for parallel extraction
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.browsers)) as executor:
            future_to_browser = {
                executor.submit(self._extract_browser_cookies, browser, domains): browser
                for browser in self.browsers
            }
            
            for future in concurrent.futures.as_completed(future_to_browser):
                browser = future_to_browser[future]
                try:
                    cookies = future.result()
                    if cookies:
                        all_cookies[browser] = cookies
                        logger.info(f"Extracted {len(cookies)} cookies from {browser}")
                except Exception as e:
                    logger.error(f"Failed to extract cookies from {browser}: {e}")
        
        return all_cookies
    
    def _extract_browser_cookies(self, browser: str, domains: Optional[List[str]] = None) -> List[Cookie]:
        """Extract cookies from a single browser
        
        Args:
            browser: Browser name
            domains: Optional list of domains to filter
            
        Returns:
            List of cookies
        """
        all_cookies = []
        profiles = find_profiles(browser)
        
        if not profiles:
            logger.debug(f"No profiles found for {browser}")
            return []
        
        for profile in profiles:
            cookie_path = get_cookie_db_path(browser, profile)
            if not cookie_path:
                continue
            
            # Extract cookies from SQLite
            cookies = extract_sqlite_cookies(cookie_path)
            
            # Decrypt values if needed
            for cookie in cookies:
                if cookie.encrypted_value:
                    decrypted = decrypt_value(cookie.encrypted_value, browser)
                    if decrypted:
                        cookie.value = decrypted
                    else:
                        # Skip cookies we can't decrypt
                        continue
            
            # Filter expired cookies
            cookies = filter_expired_cookies(cookies)
            
            # Filter by domain if specified
            if domains:
                cookies = filter_cookies_by_domain(cookies, domains)
            
            all_cookies.extend(cookies)
        
        return all_cookies
    
    def load_all_cookies(self, domains: Optional[List[str]] = None) -> requests.cookies.RequestsCookieJar:
        """Load all cookies into a unified CookieJar
        
        Args:
            domains: Optional list of domains to filter
            
        Returns:
            Unified RequestsCookieJar with all cookies
        """
        cookie_jar = requests.cookies.RequestsCookieJar()
        all_cookies = self.extract_all_cookies(domains)
        
        # Priority order for browsers
        browser_priority = ['brave', 'opera', 'chrome', 'edge', 'firefox', 'chromium']
        
        # Add cookies in priority order
        for browser in browser_priority:
            if browser in all_cookies:
                for cookie in all_cookies[browser]:
                    cookie_jar.set(
                        name=cookie.name,
                        value=cookie.value,
                        domain=cookie.host_key,
                        path=cookie.path,
                        secure=cookie.is_secure
                    )
        
        logger.info(f"Loaded {len(cookie_jar)} cookies into unified jar")
        return cookie_jar
    
    def get_browser_cookies(self, browser: str, domains: Optional[List[str]] = None) -> requests.cookies.RequestsCookieJar:
        """Get cookies from a specific browser
        
        Args:
            browser: Browser name
            domains: Optional list of domains to filter
            
        Returns:
            RequestsCookieJar with browser cookies
        """
        cookie_jar = requests.cookies.RequestsCookieJar()
        cookies = self._extract_browser_cookies(browser, domains)
        
        for cookie in cookies:
            cookie_jar.set(
                name=cookie.name,
                value=cookie.value,
                domain=cookie.host_key,
                path=cookie.path,
                secure=cookie.is_secure
            )
        
        return cookie_jar
    
    def save_cookies_json(self, output_path: Path, domains: Optional[List[str]] = None) -> None:
        """Save cookies to JSON format compatible with yt-dlp
        
        Args:
            output_path: Path to save cookies
            domains: Optional list of domains to filter
        """
        import json
        
        all_cookies = self.extract_all_cookies(domains)
        
        # Combine all cookies
        combined_cookies = []
        for browser_cookies in all_cookies.values():
            for cookie in browser_cookies:
                combined_cookies.append(cookie.to_dict())
        
        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(combined_cookies, f, indent=2)
        
        logger.info(f"Saved {len(combined_cookies)} cookies to {output_path}")
    
    def find_youtube_cookies(self) -> requests.cookies.RequestsCookieJar:
        """Extract YouTube cookies specifically
        
        Returns:
            RequestsCookieJar with YouTube cookies
        """
        youtube_domains = ['youtube.com', '.youtube.com', 'www.youtube.com']
        return self.load_all_cookies(domains=youtube_domains)
    
    def find_platform_cookies(self, platform: str) -> requests.cookies.RequestsCookieJar:
        """Extract cookies for a specific platform
        
        Args:
            platform: Platform name (youtube, peertube, etc.)
            
        Returns:
            RequestsCookieJar with platform cookies
        """
        platform_domains = {
            'youtube': ['youtube.com', '.youtube.com'],
            'peertube': ['framatube.org', 'video.ploud.fr', 'peertube.social'],
            'odysee': ['odysee.com', '.odysee.com'],
            'rumble': ['rumble.com', '.rumble.com']
        }
        
        domains = platform_domains.get(platform.lower(), [])
        if not domains:
            logger.warning(f"Unknown platform: {platform}")
            return requests.cookies.RequestsCookieJar()
        
        return self.load_all_cookies(domains=domains)


# Convenience functions for backward compatibility
def detect_os_wrapper() -> str:
    """Wrapper for OS detection"""
    return detect_os()


def find_profiles_wrapper(browser: str) -> List[Path]:
    """Wrapper for profile finding"""
    return find_profiles(browser)


def extract_sqlite_cookies_wrapper(db_path: Path) -> List[Cookie]:
    """Wrapper for SQLite extraction"""
    return extract_sqlite_cookies(db_path)


def decrypt_value_wrapper(encrypted_value: bytes, browser: str) -> Optional[str]:
    """Wrapper for value decryption"""
    return decrypt_value(encrypted_value, browser)


def load_all_cookies() -> requests.cookies.RequestsCookieJar:
    """Load all cookies from all browsers"""
    extractor = CrossPlatformCookieExtractor()
    return extractor.load_all_cookies()


async def extract_and_save_cookies():
    """Async function for scheduled cookie extraction"""
    import asyncio
    import json
    from pathlib import Path
    
    try:
        logger.info("Starting scheduled cookie extraction from Brave browser...")
        
        # Focus on Brave browser for Docker setup
        extractor = CrossPlatformCookieExtractor(browsers=['brave'])
        
        # Extract cookies for all supported platforms
        platforms = ['youtube', 'rumble', 'odysee', 'peertube']
        cookie_dir = Path('/app/cookies')
        cookie_dir.mkdir(exist_ok=True)
        
        for platform in platforms:
            try:
                cookies = extractor.find_platform_cookies(platform)
                
                # Save cookies in yt-dlp compatible format
                cookie_data = []
                for cookie in cookies:
                    cookie_data.append({
                        'name': cookie.name,
                        'value': cookie.value,
                        'domain': cookie.domain,
                        'path': cookie.path,
                        'secure': cookie.secure,
                        'httpOnly': getattr(cookie, 'httponly', False),
                        'expires': getattr(cookie, 'expires', None)
                    })
                
                output_file = cookie_dir / f'{platform}_cookies.json'
                with open(output_file, 'w') as f:
                    json.dump(cookie_data, f, indent=2)
                    
                logger.info(f"Saved {len(cookie_data)} {platform} cookies to {output_file}")
                
            except Exception as e:
                logger.error(f"Failed to extract {platform} cookies: {e}")
        
        logger.info("Completed scheduled cookie extraction")
        
    except Exception as e:
        logger.error(f"Scheduled cookie extraction failed: {e}")


def main():
    """Main function for running cookie extraction as standalone script"""
    import asyncio
    asyncio.run(extract_and_save_cookies())