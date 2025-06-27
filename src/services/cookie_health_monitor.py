"""Cookie health monitoring service for robust VPS deployments

This service monitors cookie health, validates cookie freshness, and provides
fallback mechanisms when cookies fail or become invalid.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import aiofiles
import aiohttp

logger = logging.getLogger(__name__)


class CookieHealthStatus:
    """Represents the health status of cookies for a platform"""

    def __init__(self, platform: str):
        self.platform = platform
        self.is_healthy = False
        self.last_validated = None
        self.validation_error: Optional[str] = None
        self.cookie_count = 0
        self.age_hours = 0
        self.expires_in_hours: Optional[float] = None
        self.needs_refresh = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert status to dictionary for serialization"""
        return {
            "platform": self.platform,
            "is_healthy": self.is_healthy,
            "last_validated": (
                self.last_validated.isoformat() if self.last_validated else None
            ),
            "validation_error": self.validation_error,
            "cookie_count": self.cookie_count,
            "age_hours": self.age_hours,
            "expires_in_hours": self.expires_in_hours,
            "needs_refresh": self.needs_refresh,
        }


class CookieHealthMonitor:
    """Monitors cookie health and provides fallback mechanisms"""

    def __init__(self, config: Dict):
        self.config = config
        self.cookie_paths = [
            Path("/app/cookies"),
            Path("data/cookies"),
            Path("./cookies"),
        ]

        # Find the active cookie directory
        self.cookie_dir = None
        for path in self.cookie_paths:
            if path.exists() and any(path.glob("*_cookies.json")):
                self.cookie_dir = path
                break

        if self.cookie_dir is None:
            self.cookie_dir = self.cookie_paths[0]  # Default fallback

        logger.info(f"Cookie health monitor using directory: {self.cookie_dir}")

        # Platform configurations
        self.platforms = ["youtube", "rumble", "odysee", "peertube"]
        self.platform_status: Dict[str, CookieHealthStatus] = {}

        # Health check intervals and thresholds
        self.health_check_interval = config.get(
            "health_check_interval", 300
        )  # 5 minutes
        self.cookie_max_age_hours = config.get("cookie_max_age_hours", 12)  # 12 hours
        self.cookie_refresh_threshold_hours = config.get(
            "cookie_refresh_threshold_hours", 8
        )  # 8 hours
        self.validation_timeout = config.get("validation_timeout", 10)  # 10 seconds
        
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

        # Validation URLs for testing cookie validity
        self.validation_urls = {
            "youtube": "https://www.youtube.com/feed/subscriptions",
            "rumble": "https://rumble.com/",
            "odysee": "https://odysee.com/",
            "peertube": "https://framatube.org/",  # Generic PeerTube instance
        }

        # Initialize status for all platforms
        for platform in self.platforms:
            self.platform_status[platform] = CookieHealthStatus(platform)

        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self):
        """Start the health monitoring service"""
        logger.info("Starting cookie health monitor")

        # Initial health check
        await self.check_all_cookies()

        # Start background monitoring
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop the health monitoring service"""
        logger.info("Stopping cookie health monitor")

        self._stop_event.set()

        if self._monitor_task:
            try:
                await asyncio.wait_for(self._monitor_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Cookie health monitor stop timed out")
                self._monitor_task.cancel()

    async def check_all_cookies(self) -> Dict[str, CookieHealthStatus]:
        """Check health of all platform cookies"""
        logger.debug("Performing comprehensive cookie health check")

        tasks = []
        for platform in self.platforms:
            tasks.append(self._check_platform_cookies(platform))

        # Run all checks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        # Log summary
        healthy_count = sum(
            1 for status in self.platform_status.values() if status.is_healthy
        )
        logger.info(
            f"Cookie health check complete: {healthy_count}/{len(self.platforms)} platforms healthy"
        )

        return self.platform_status.copy()

    async def _check_platform_cookies(self, platform: str) -> CookieHealthStatus:
        """Check health of cookies for a specific platform"""
        status = self.platform_status[platform]

        try:
            # Load and validate cookie file
            cookie_file = self.cookie_dir / f"{platform}_cookies.json"

            if not cookie_file.exists():
                status.is_healthy = False
                status.cookie_count = 0
                if platform in self.cookie_optional_platforms:
                    status.validation_error = "Cookie file not found (optional for this platform)"
                    logger.debug(f"No cookie file found for {platform} - platform works without authentication")
                    # Mark as healthy since cookies are optional for this platform
                    status.is_healthy = True
                else:
                    status.validation_error = "Cookie file not found"
                    logger.warning(f"No cookie file found for {platform}")
                return status

            # Check file age
            file_stat = cookie_file.stat()
            file_age = datetime.now() - datetime.fromtimestamp(file_stat.st_mtime)
            status.age_hours = file_age.total_seconds() / 3600

            # Load and parse cookies
            try:
                async with aiofiles.open(cookie_file, "r") as f:
                    content = await f.read()
                    if not content.strip():
                        status.is_healthy = False
                        status.validation_error = "Cookie file is empty"
                        status.cookie_count = 0
                        return status

                    cookies = json.loads(content)
                    if not isinstance(cookies, list):
                        status.is_healthy = False
                        status.validation_error = "Invalid cookie format"
                        status.cookie_count = 0
                        return status

                    status.cookie_count = len(cookies)

            except json.JSONDecodeError as e:
                status.is_healthy = False
                status.validation_error = f"Invalid JSON: {str(e)}"
                status.cookie_count = 0
                return status
            except Exception as e:
                status.is_healthy = False
                status.validation_error = f"File read error: {str(e)}"
                status.cookie_count = 0
                return status

            # Check if cookies are too old using platform-specific thresholds
            platform_threshold = self.platform_cookie_thresholds.get(platform, self.cookie_max_age_hours)
            refresh_threshold = min(platform_threshold * 0.75, self.cookie_refresh_threshold_hours)
            
            if status.age_hours > platform_threshold:
                if platform in self.cookie_optional_platforms:
                    logger.debug(
                        f"{platform} cookies are {status.age_hours:.1f} hours old (max: {platform_threshold}h) - "
                        f"platform works without authentication cookies"
                    )
                    # Don't mark as unhealthy for optional platforms
                    status.is_healthy = True
                    status.needs_refresh = True
                else:
                    status.is_healthy = False
                    status.validation_error = (
                        f"Cookies too old ({status.age_hours:.1f} hours, max: {platform_threshold}h)"
                    )
                    status.needs_refresh = True
                    return status

            # Check if cookies need refresh soon
            status.needs_refresh = (
                status.age_hours > refresh_threshold
            )

            # Check cookie expiration
            earliest_expiry = self._check_cookie_expiration(cookies)
            if earliest_expiry:
                status.expires_in_hours = earliest_expiry
                if earliest_expiry < 1:  # Less than 1 hour
                    status.is_healthy = False
                    status.validation_error = (
                        f"Cookies expire in {earliest_expiry:.1f} hours"
                    )
                    status.needs_refresh = True
                    return status

            # Validate cookies by making a test request
            await self._validate_cookies_with_request(platform, cookies, status)

            status.last_validated = datetime.now()

            if status.is_healthy:
                logger.debug(
                    f"{platform} cookies are healthy ({status.cookie_count} cookies, {status.age_hours:.1f}h old)"
                )
            else:
                logger.warning(
                    f"{platform} cookies failed validation: {status.validation_error}"
                )

        except Exception as e:
            status.is_healthy = False
            status.validation_error = f"Health check error: {str(e)}"
            logger.error(f"Error checking {platform} cookies: {e}")

        return status

    def _check_cookie_expiration(self, cookies: List[Dict]) -> Optional[float]:
        """Check when cookies expire and return hours until earliest expiry"""
        now = time.time()
        earliest_expiry = None

        for cookie in cookies:
            expires = cookie.get("expires")
            if expires and isinstance(expires, (int, float)) and expires > 0:
                hours_until_expiry = (expires - now) / 3600
                if earliest_expiry is None or hours_until_expiry < earliest_expiry:
                    earliest_expiry = hours_until_expiry

        return earliest_expiry

    async def _validate_cookies_with_request(
        self, platform: str, cookies: List[Dict], status: CookieHealthStatus
    ):
        """Validate cookies by making a test HTTP request"""
        validation_url = self.validation_urls.get(platform)
        if not validation_url:
            status.is_healthy = True  # Assume healthy if no validation URL
            return

        try:
            # Convert cookies to aiohttp format
            cookie_jar = aiohttp.CookieJar()
            for cookie in cookies:
                try:
                    cookie_jar.update_cookies(
                        {cookie["name"]: cookie["value"]},
                        response_url=aiohttp.URL(validation_url),
                    )
                except Exception as e:
                    logger.debug(
                        f"Failed to add cookie {cookie.get('name', 'unknown')}: {e}"
                    )
                    continue

            # Make test request
            timeout = aiohttp.ClientTimeout(total=self.validation_timeout)
            async with aiohttp.ClientSession(
                cookie_jar=cookie_jar,
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            ) as session:
                async with session.get(validation_url) as response:
                    if response.status == 200:
                        status.is_healthy = True
                        status.validation_error = None
                    elif response.status == 403:
                        status.is_healthy = False
                        status.validation_error = "Cookies rejected (403 Forbidden)"
                        status.needs_refresh = True
                    elif response.status == 401:
                        status.is_healthy = False
                        status.validation_error = (
                            "Authentication failed (401 Unauthorized)"
                        )
                        status.needs_refresh = True
                    else:
                        status.is_healthy = False
                        status.validation_error = (
                            f"Unexpected response: {response.status}"
                        )

        except asyncio.TimeoutError:
            status.is_healthy = False
            status.validation_error = "Validation request timed out"
        except Exception as e:
            # Don't fail validation on network errors - cookies might still be good
            logger.debug(f"Cookie validation request failed for {platform}: {e}")
            status.is_healthy = True  # Assume healthy if we can't validate

    async def _monitor_loop(self):
        """Background monitoring loop"""
        while not self._stop_event.is_set():
            try:
                await self.check_all_cookies()

                # Log health summary periodically
                self._log_health_summary()

                # Wait for next check
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.health_check_interval
                    )
                except asyncio.TimeoutError:
                    continue  # Continue monitoring

            except Exception as e:
                logger.error(f"Error in cookie health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    def _log_health_summary(self):
        """Log a summary of cookie health"""
        healthy_platforms = []
        unhealthy_platforms = []
        refresh_needed = []

        for platform, status in self.platform_status.items():
            if status.is_healthy:
                healthy_platforms.append(platform)
            else:
                unhealthy_platforms.append(f"{platform}: {status.validation_error}")

            if status.needs_refresh:
                refresh_needed.append(platform)

        if unhealthy_platforms:
            logger.warning(f"Unhealthy cookies: {', '.join(unhealthy_platforms)}")

        if refresh_needed:
            logger.info(f"Cookies need refresh: {', '.join(refresh_needed)}")

        if healthy_platforms:
            logger.debug(f"Healthy cookies: {', '.join(healthy_platforms)}")

    def get_platform_status(self, platform: str) -> Optional[CookieHealthStatus]:
        """Get health status for a specific platform"""
        return self.platform_status.get(platform)

    def is_platform_healthy(self, platform: str) -> bool:
        """Check if a platform's cookies are healthy"""
        status = self.platform_status.get(platform)
        return status.is_healthy if status else False

    def get_unhealthy_platforms(self) -> List[str]:
        """Get list of platforms with unhealthy cookies"""
        return [
            platform
            for platform, status in self.platform_status.items()
            if not status.is_healthy
        ]

    def get_platforms_needing_refresh(self) -> List[str]:
        """Get list of platforms that need cookie refresh"""
        return [
            platform
            for platform, status in self.platform_status.items()
            if status.needs_refresh
        ]

    async def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        return {
            "timestamp": datetime.now().isoformat(),
            "cookie_directory": str(self.cookie_dir),
            "overall_health": {
                "healthy_count": sum(
                    1 for s in self.platform_status.values() if s.is_healthy
                ),
                "total_count": len(self.platform_status),
                "unhealthy_platforms": self.get_unhealthy_platforms(),
                "refresh_needed": self.get_platforms_needing_refresh(),
            },
            "platform_details": {
                platform: status.to_dict()
                for platform, status in self.platform_status.items()
            },
        }

    async def force_health_check(self) -> Dict[str, CookieHealthStatus]:
        """Force an immediate health check of all cookies"""
        logger.info("Forcing immediate cookie health check")
        return await self.check_all_cookies()

    def should_use_fallback(self, platform: str) -> bool:
        """Determine if platform should use fallback mode due to cookie issues"""
        status = self.platform_status.get(platform)
        if not status:
            return True  # Use fallback if no status available

        return not status.is_healthy
