"""Enhanced cookie manager with cross-platform extraction and robust error handling"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import asyncio
import aiofiles
from datetime import datetime, timedelta

from ..extractors.cross_platform_cookies import CrossPlatformCookieExtractor

logger = logging.getLogger(__name__)


class EnhancedCookieManager:
    """Enhanced cookie manager with automatic cross-platform extraction"""

    def __init__(self, config: Dict):
        self.config = config
        # Use standardized cookie path with fallback for compatibility
        cookie_paths = [Path("/app/cookies"), Path("data/cookies"), Path("./cookies")]

        self.cookie_dir = None
        for path in cookie_paths:
            try:
                path.mkdir(parents=True, exist_ok=True)
                # Test write access
                test_file = path / ".test_write"
                test_file.touch()
                test_file.unlink()
                self.cookie_dir = path
                break
            except (PermissionError, OSError) as e:
                logger.debug(f"Cannot use cookie path {path}: {e}")
                continue

        if self.cookie_dir is None:
            # Last resort fallback
            self.cookie_dir = Path("./cookies")
            try:
                self.cookie_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Cannot create fallback cookie directory: {e}")

        logger.info(f"Using cookie directory: {self.cookie_dir}")
        self.cookies: Dict[str, List[Dict]] = {}
        self.cookie_health: Dict[str, Dict] = {}  # Track cookie health
        self.extractor = CrossPlatformCookieExtractor()
        self._extraction_lock = asyncio.Lock()

        # Enhanced configuration
        self.max_retry_attempts = config.get("max_retry_attempts", 3)
        self.retry_delay = config.get("retry_delay", 1.0)
        self.cookie_max_age_hours = config.get("cookie_max_age_hours", 12)
        self.enable_health_monitoring = config.get("enable_health_monitoring", True)
        self.fallback_mode = config.get("enable_fallback_mode", True)
        
        # VPS mode configuration - platforms that don't require authentication cookies
        self.vps_mode = config.get("vps_mode", True)
        self.cookie_optional_platforms = config.get("cookie_optional_platforms", ["peertube", "odysee"])
        
        # Platform-specific cookie age thresholds (in hours)
        self.platform_cookie_thresholds = config.get("platform_cookie_thresholds", {
            "youtube": 12,  # YouTube benefits from authenticated cookies
            "rumble": 24,   # Rumble can work longer without fresh cookies
            "peertube": 72, # PeerTube instances usually don't require authentication
            "odysee": 48    # Odysee can work with older cookies or no cookies
        })

    async def load_cookies(self) -> Dict[str, bool]:
        """Load cookies from storage with comprehensive validation"""
        platforms = ["youtube", "peertube", "odysee", "rumble"]
        results = {}

        for platform in platforms:
            results[platform] = await self._load_platform_cookies_with_validation(
                platform
            )

        # Log summary
        successful = sum(1 for success in results.values() if success)
        logger.info(
            f"Cookie loading completed: {successful}/{len(platforms)} platforms loaded successfully"
        )

        return results

    async def _load_platform_cookies_with_validation(self, platform: str) -> bool:
        """Load and validate cookies for a specific platform"""
        cookie_file = self.cookie_dir / f"{platform}_cookies.json"

        # Initialize health tracking
        self.cookie_health[platform] = {
            "loaded": False,
            "last_checked": datetime.now(),
            "error": None,
            "cookie_count": 0,
            "file_age_hours": None,
            "valid_cookies": 0,
        }

        if not cookie_file.exists():
            if platform in self.cookie_optional_platforms:
                logger.debug(f"No cookie file found for {platform} - platform works without authentication")
                self.cookie_health[platform]["error"] = "File not found (optional for this platform)"
            else:
                logger.info(f"No cookie file found for {platform}")
                self.cookie_health[platform]["error"] = "File not found"
            return False

        try:
            # Check file age and size
            file_stat = cookie_file.stat()
            if file_stat.st_size == 0:
                logger.warning(f"Empty cookie file for {platform}")
                self.cookie_health[platform]["error"] = "Empty file"
                return False

            file_age = datetime.now() - datetime.fromtimestamp(file_stat.st_mtime)
            age_hours = file_age.total_seconds() / 3600
            self.cookie_health[platform]["file_age_hours"] = age_hours

            # Warn about old cookies but don't fail completely, using platform-specific thresholds
            platform_threshold = self.platform_cookie_thresholds.get(platform, self.cookie_max_age_hours)
            
            if age_hours > platform_threshold:
                if platform in self.cookie_optional_platforms:
                    logger.debug(
                        f"{platform} cookies are {age_hours:.1f} hours old (max: {platform_threshold}h) - "
                        f"platform works without authentication cookies"
                    )
                else:
                    logger.warning(
                        f"{platform} cookies are {age_hours:.1f} hours old (recommended max: {platform_threshold}h)"
                    )

            # Load and validate content
            async with aiofiles.open(cookie_file, "r") as f:
                content = (await f.read()).strip()

                if not content:
                    logger.warning(f"Empty content in cookie file for {platform}")
                    self.cookie_health[platform]["error"] = "Empty content"
                    return False

                cookies = json.loads(content)

                if not isinstance(cookies, list):
                    logger.error(f"Invalid cookie format for {platform}: expected list")
                    self.cookie_health[platform]["error"] = "Invalid format"
                    return False

                # Validate and filter cookies
                valid_cookies = []
                for i, cookie in enumerate(cookies):
                    if self._validate_cookie(cookie, platform, i):
                        valid_cookies.append(cookie)

                if not valid_cookies:
                    logger.warning(f"No valid cookies found for {platform}")
                    self.cookie_health[platform]["error"] = "No valid cookies"
                    return False

                # Successfully loaded
                self.cookies[platform] = valid_cookies
                self.cookie_health[platform].update(
                    {
                        "loaded": True,
                        "error": None,
                        "cookie_count": len(cookies),
                        "valid_cookies": len(valid_cookies),
                    }
                )

                if len(valid_cookies) < len(cookies):
                    logger.warning(
                        f"Filtered {len(cookies) - len(valid_cookies)} invalid cookies for {platform}"
                    )

                logger.info(
                    f"Loaded {len(valid_cookies)} valid cookies for {platform} (age: {age_hours:.1f}h)"
                )
                return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in cookie file for {platform}: {e}")
            self.cookie_health[platform]["error"] = f"JSON error: {str(e)}"
            return False
        except Exception as e:
            logger.error(f"Failed to load cookies for {platform}: {e}")
            self.cookie_health[platform]["error"] = str(e)
            return False

    def _validate_cookie(self, cookie: Dict, platform: str, index: int) -> bool:
        """Validate individual cookie structure"""
        if not isinstance(cookie, dict):
            logger.debug(f"Invalid cookie {index} for {platform}: not a dict")
            return False

        required_fields = ["name", "value"]
        for field in required_fields:
            if field not in cookie or not cookie[field]:
                logger.debug(
                    f"Invalid cookie {index} for {platform}: missing or empty {field}"
                )
                return False

        # Check for problematic characters
        name = cookie["name"]
        value = cookie["value"]

        if any(char in name for char in ["\n", "\t", "\r"]):
            logger.debug(
                f"Invalid cookie {index} for {platform}: name contains invalid characters"
            )
            return False

        if any(char in value for char in ["\n", "\t", "\r"]):
            logger.debug(
                f"Invalid cookie {index} for {platform}: value contains invalid characters"
            )
            return False

        return True

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
        """Get cookies for a platform with health awareness"""
        cookies = self.cookies.get(platform)

        if self.enable_health_monitoring and platform in self.cookie_health:
            health = self.cookie_health[platform]
            if cookies and health.get("loaded", False):
                age_hours = health.get("file_age_hours", 0)
                logger.debug(
                    f"Retrieved {len(cookies)} cookies for {platform} (age: {age_hours:.1f}h, health: {'OK' if not health.get('error') else 'Issues'})"
                )
            elif not cookies:
                error = health.get("error", "No cookies loaded")
                logger.debug(f"No cookies available for {platform}: {error}")

        return cookies

    def is_platform_healthy(self, platform: str) -> bool:
        """Check if platform cookies are healthy"""
        if not self.enable_health_monitoring:
            return bool(self.cookies.get(platform))

        health = self.cookie_health.get(platform, {})
        
        # For optional platforms, consider them healthy even without cookies
        if platform in self.cookie_optional_platforms:
            error = health.get("error", "")
            if "File not found (optional for this platform)" in error:
                return True
        
        platform_threshold = self.platform_cookie_thresholds.get(platform, self.cookie_max_age_hours)
        
        return (
            health.get("loaded", False)
            and not health.get("error")
            and health.get("file_age_hours", float("inf")) <= platform_threshold
        )

    def get_platform_health_status(self, platform: str) -> Dict:
        """Get detailed health status for a platform"""
        return self.cookie_health.get(
            platform,
            {
                "loaded": False,
                "last_checked": None,
                "error": "Not initialized",
                "cookie_count": 0,
                "valid_cookies": 0,
                "file_age_hours": None,
            },
        )

    def should_use_fallback_mode(self, platform: str) -> bool:
        """Determine if platform should use fallback mode"""
        if not self.fallback_mode:
            return False

        return not self.is_platform_healthy(platform)

    async def extract_browser_cookies(self, platform: str):
        """Extract cookies from browser profile using cross-platform extractor"""
        async with self._extraction_lock:
            try:
                logger.info(f"Extracting browser cookies for {platform}")

                # Run extraction in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                cookies = await loop.run_in_executor(
                    None, self._extract_platform_cookies, platform
                )

                if cookies:
                    await self.save_cookies(platform, cookies)
                    logger.info(
                        f"Extracted and saved {len(cookies)} cookies for {platform}"
                    )
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
            cookies.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": cookie.secure,
                    "httpOnly": False,  # Default since RequestsCookieJar doesn't track this
                    "sameSite": "None",
                }
            )

        return cookies

    async def refresh_cookies(
        self, force: bool = False, platforms: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Refresh cookies with enhanced error handling and selective refresh"""
        target_platforms = platforms or ["youtube", "peertube", "odysee", "rumble"]
        results = {}

        logger.info(
            f"Refreshing cookies for {len(target_platforms)} platforms (force={force})"
        )

        # Determine which platforms need refresh
        platforms_to_refresh = []
        for platform in target_platforms:
            should_refresh = force

            if not should_refresh and self.enable_health_monitoring:
                health = self.cookie_health.get(platform, {})
                age_hours = health.get("file_age_hours", float("inf"))
                has_error = health.get("error") is not None
                not_loaded = not health.get("loaded", False)

                if age_hours > self.cookie_max_age_hours or has_error or not_loaded:
                    should_refresh = True

            if should_refresh:
                platforms_to_refresh.append(platform)
            else:
                results[platform] = True  # Already fresh

        if not platforms_to_refresh:
            logger.info("All cookies are fresh, no refresh needed")
            return results

        # Limit concurrent extractions to avoid overwhelming the system
        semaphore = asyncio.Semaphore(2)

        async def refresh_single_platform(platform: str) -> Tuple[str, bool]:
            async with semaphore:
                try:
                    logger.debug(f"Starting refresh for {platform}")
                    await self.extract_browser_cookies(platform)

                    # Verify the refresh was successful
                    if self.cookies.get(platform):
                        logger.info(f"Successfully refreshed cookies for {platform}")
                        return platform, True
                    else:
                        logger.warning(
                            f"Cookie refresh for {platform} completed but no cookies available"
                        )
                        return platform, False

                except Exception as e:
                    logger.error(f"Cookie refresh failed for {platform}: {e}")
                    return platform, False

        # Execute refreshes with error handling
        refresh_tasks = [
            refresh_single_platform(platform) for platform in platforms_to_refresh
        ]

        try:
            refresh_results = await asyncio.gather(
                *refresh_tasks, return_exceptions=True
            )

            for result in refresh_results:
                if isinstance(result, tuple):
                    platform, success = result
                    results[platform] = success
                elif isinstance(result, Exception):
                    logger.error(f"Unexpected error during refresh: {result}")
                    # Try to find which platform failed
                    for platform in platforms_to_refresh:
                        if platform not in results:
                            results[platform] = False
                            break

        except Exception as e:
            logger.error(f"Critical error during cookie refresh: {e}")
            # Mark all pending platforms as failed
            for platform in platforms_to_refresh:
                if platform not in results:
                    results[platform] = False

        # Log summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        logger.info(
            f"Cookie refresh completed: {successful}/{total} platforms successful"
        )

        failed_platforms = [
            platform for platform, success in results.items() if not success
        ]
        if failed_platforms:
            logger.warning(
                f"Cookie refresh failed for platforms: {', '.join(failed_platforms)}"
            )

        return results

    async def get_cookies_for_url(self, url: str) -> Tuple[Optional[List[Dict]], bool]:
        """Get cookies for URL with fallback indication

        Returns:
            Tuple of (cookies, should_use_fallback)
        """
        platform = self._get_platform_from_url(url)

        if not platform:
            logger.debug(f"Unknown platform for URL: {url}")
            return None, True

        cookies = self.get_cookies(platform)
        should_use_fallback = False

        # Check cookie health
        if self.enable_health_monitoring:
            health = self.cookie_health.get(platform, {})
            age_hours = health.get("file_age_hours", 0)
            has_error = health.get("error") is not None

            # Suggest fallback if cookies are problematic
            if has_error or age_hours > self.cookie_max_age_hours:
                should_use_fallback = True
                logger.debug(
                    f"Cookie health issues for {platform}, suggesting fallback mode"
                )

        # If no cookies found, try extracting once
        if not cookies:
            logger.debug(f"No cookies available for {platform}, attempting extraction")
            try:
                await self.extract_browser_cookies(platform)
                cookies = self.get_cookies(platform)

                if cookies:
                    should_use_fallback = False
                    logger.info(f"Successfully extracted cookies for {platform}")
                else:
                    should_use_fallback = True
                    logger.warning(
                        f"Cookie extraction failed for {platform}, using fallback mode"
                    )
            except Exception as e:
                logger.error(f"Cookie extraction error for {platform}: {e}")
                should_use_fallback = True

        return cookies, should_use_fallback

    def _get_platform_from_url(self, url: str) -> Optional[str]:
        """Determine platform from URL"""
        url_lower = url.lower()

        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif "peertube" in url_lower or "framatube" in url_lower:
            return "peertube"
        elif "odysee.com" in url_lower:
            return "odysee"
        elif "rumble.com" in url_lower:
            return "rumble"

        return None

    async def cleanup(self):
        """Enhanced cleanup with health status reporting"""
        logger.info("Cleaning up enhanced cookie manager")

        try:
            # Save comprehensive health report
            health_report = {
                "timestamp": datetime.now().isoformat(),
                "cookie_directory": str(self.cookie_dir),
                "platform_health": {},
            }

            for platform, health in self.cookie_health.items():
                health_report["platform_health"][platform] = {
                    "loaded": health.get("loaded", False),
                    "last_checked": (
                        health.get("last_checked", "").isoformat()
                        if health.get("last_checked")
                        else None
                    ),
                    "error": health.get("error"),
                    "cookie_count": health.get("cookie_count", 0),
                    "valid_cookies": health.get("valid_cookies", 0),
                    "file_age_hours": health.get("file_age_hours"),
                    "needs_refresh": health.get("file_age_hours", 0)
                    > self.cookie_max_age_hours,
                }

            # Save health report
            health_file = self.cookie_dir / "enhanced_cookie_health.json"
            async with aiofiles.open(health_file, "w") as f:
                await f.write(json.dumps(health_report, indent=2, default=str))

            logger.debug(f"Saved enhanced cookie health report to {health_file}")

            # Log final summary
            healthy_count = sum(
                1
                for h in self.cookie_health.values()
                if h.get("loaded", False) and not h.get("error")
            )
            total_count = len(self.cookie_health)

            logger.info(
                f"Enhanced cookie manager cleanup complete - {healthy_count}/{total_count} platforms healthy"
            )

            # List problematic platforms
            problematic = []
            for platform, health in self.cookie_health.items():
                if not health.get("loaded", False) or health.get("error"):
                    error = health.get("error", "Not loaded")
                    problematic.append(f"{platform}: {error}")

            if problematic:
                logger.warning(f"Platforms with issues: {'; '.join(problematic)}")

        except Exception as e:
            logger.error(f"Error during enhanced cookie manager cleanup: {e}")

    def get_cookie_jar(self, platform: str):
        """Get a requests CookieJar for a platform"""
        import requests

        jar = requests.cookies.RequestsCookieJar()
        cookies = self.get_cookies(platform)

        if cookies:
            for cookie in cookies:
                jar.set(
                    name=cookie["name"],
                    value=cookie["value"],
                    domain=cookie.get("domain", ""),
                    path=cookie.get("path", "/"),
                    secure=cookie.get("secure", False),
                )

        return jar

    async def auto_refresh_loop(self, interval: int = 3600):
        """Automatically refresh cookies at specified interval"""
        while True:
            try:
                await self.refresh_cookies()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto-refresh loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
