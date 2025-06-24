import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import asyncio
import aiofiles
from datetime import datetime, timedelta

from ..extractors.cross_platform_cookies import CrossPlatformCookieExtractor

logger = logging.getLogger(__name__)


class CookieManager:
    """Manages cookies for authenticated platform access with robust error handling"""

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
        self.cookie_status: Dict[str, Dict] = {}  # Track cookie health status
        self.extractor = CrossPlatformCookieExtractor()
        self._extraction_lock = asyncio.Lock()

        # Error handling configuration
        self.max_retry_attempts = config.get("max_retry_attempts", 3)
        self.retry_delay = config.get("retry_delay", 1.0)
        self.cookie_max_age_hours = config.get("cookie_max_age_hours", 12)
        self.fallback_mode = config.get("enable_fallback_mode", True)

    async def load_cookies(self):
        """Load cookies from storage with enhanced error handling"""
        platforms = ["youtube", "peertube", "odysee", "rumble"]

        for platform in platforms:
            await self._load_platform_cookies(platform)

    async def _load_platform_cookies(self, platform: str) -> bool:
        """Load cookies for a specific platform with validation"""
        cookie_file = self.cookie_dir / f"{platform}_cookies.json"

        # Initialize status tracking
        self.cookie_status[platform] = {
            "loaded": False,
            "last_loaded": None,
            "error": None,
            "cookie_count": 0,
            "file_age_hours": None,
        }

        if not cookie_file.exists():
            logger.info(f"No cookie file found for {platform}, will use fallback mode")
            self.cookie_status[platform]["error"] = "File not found"
            return False

        try:
            # Check file age
            file_stat = cookie_file.stat()
            file_age = datetime.now() - datetime.fromtimestamp(file_stat.st_mtime)
            age_hours = file_age.total_seconds() / 3600
            self.cookie_status[platform]["file_age_hours"] = age_hours

            # Check if cookies are too old
            if age_hours > self.cookie_max_age_hours:
                logger.warning(
                    f"{platform} cookies are {age_hours:.1f} hours old (max: {self.cookie_max_age_hours}h)"
                )
                if not self.fallback_mode:
                    self.cookie_status[platform][
                        "error"
                    ] = f"Cookies too old ({age_hours:.1f}h)"
                    return False

            # Load and validate cookie content
            async with aiofiles.open(cookie_file, "r") as f:
                content = await f.read().strip()

                if not content:
                    logger.warning(f"Empty cookie file for {platform}")
                    self.cookie_status[platform]["error"] = "Empty file"
                    return False

                try:
                    cookies = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in {platform} cookie file: {e}")
                    self.cookie_status[platform]["error"] = f"Invalid JSON: {str(e)}"
                    return False

                if not isinstance(cookies, list):
                    logger.error(
                        f"Invalid cookie format for {platform}: expected list, got {type(cookies)}"
                    )
                    self.cookie_status[platform]["error"] = "Invalid format"
                    return False

                # Validate cookie structure
                valid_cookies = []
                for cookie in cookies:
                    if (
                        isinstance(cookie, dict)
                        and "name" in cookie
                        and "value" in cookie
                    ):
                        valid_cookies.append(cookie)
                    else:
                        logger.debug(f"Skipping invalid cookie in {platform}: {cookie}")

                if not valid_cookies:
                    logger.warning(f"No valid cookies found for {platform}")
                    self.cookie_status[platform]["error"] = "No valid cookies"
                    return False

                # Successfully loaded
                self.cookies[platform] = valid_cookies
                self.cookie_status[platform].update(
                    {
                        "loaded": True,
                        "last_loaded": datetime.now(),
                        "error": None,
                        "cookie_count": len(valid_cookies),
                    }
                )

                logger.info(
                    f"Loaded {len(valid_cookies)} cookies for {platform} (age: {age_hours:.1f}h)"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to load cookies for {platform}: {e}")
            self.cookie_status[platform]["error"] = str(e)
            return False

    async def save_cookies(self, platform: str, cookies: List[Dict]) -> bool:
        """Save cookies for a platform with enhanced error handling"""
        if not cookies:
            logger.warning(f"Attempted to save empty cookies for {platform}")
            return False

        cookie_file = self.cookie_dir / f"{platform}_cookies.json"
        backup_file = self.cookie_dir / f"{platform}_cookies.json.backup"

        try:
            # Create backup of existing file if it exists
            if cookie_file.exists():
                try:
                    import shutil

                    shutil.copy2(cookie_file, backup_file)
                    logger.debug(f"Created backup for {platform} cookies")
                except Exception as backup_error:
                    logger.warning(
                        f"Failed to create backup for {platform}: {backup_error}"
                    )

            # Validate cookies before saving
            valid_cookies = []
            for cookie in cookies:
                if isinstance(cookie, dict) and "name" in cookie and "value" in cookie:
                    valid_cookies.append(cookie)
                else:
                    logger.debug(f"Excluding invalid cookie for {platform}: {cookie}")

            if not valid_cookies:
                logger.error(f"No valid cookies to save for {platform}")
                return False

            # Write cookies atomically
            temp_file = cookie_file.with_suffix(".tmp")
            try:
                async with aiofiles.open(temp_file, "w") as f:
                    await f.write(json.dumps(valid_cookies, indent=2))

                # Atomic move
                temp_file.replace(cookie_file)

                # Update in-memory cookies
                self.cookies[platform] = valid_cookies

                # Update status
                if platform not in self.cookie_status:
                    self.cookie_status[platform] = {}

                self.cookie_status[platform].update(
                    {
                        "loaded": True,
                        "last_loaded": datetime.now(),
                        "error": None,
                        "cookie_count": len(valid_cookies),
                        "file_age_hours": 0,
                    }
                )

                logger.info(f"Saved {len(valid_cookies)} cookies for {platform}")

                # Clean up backup on success
                if backup_file.exists():
                    try:
                        backup_file.unlink()
                    except Exception:
                        pass  # Ignore cleanup errors

                return True

            except Exception as e:
                # Clean up temp file on error
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                raise e

        except Exception as e:
            logger.error(f"Failed to save cookies for {platform}: {e}")

            # Restore from backup if available
            if backup_file.exists():
                try:
                    backup_file.replace(cookie_file)
                    logger.info(f"Restored {platform} cookies from backup")
                except Exception as restore_error:
                    logger.error(
                        f"Failed to restore backup for {platform}: {restore_error}"
                    )

            return False

    def get_cookies(self, platform: str) -> Optional[List[Dict]]:
        """Get cookies for a platform with fallback handling"""
        cookies = self.cookies.get(platform)

        # Log cookie availability for debugging
        if cookies:
            status = self.cookie_status.get(platform, {})
            age_hours = status.get("file_age_hours", 0)
            logger.debug(
                f"Retrieved {len(cookies)} cookies for {platform} (age: {age_hours:.1f}h)"
            )
        else:
            logger.debug(
                f"No cookies available for {platform}, platform will use fallback mode"
            )

        return cookies

    def is_platform_healthy(self, platform: str) -> bool:
        """Check if platform cookies are healthy and available"""
        status = self.cookie_status.get(platform, {})
        return status.get("loaded", False) and status.get("error") is None

    def get_platform_status(self, platform: str) -> Dict:
        """Get detailed status information for a platform"""
        return self.cookie_status.get(
            platform,
            {
                "loaded": False,
                "last_loaded": None,
                "error": "Not initialized",
                "cookie_count": 0,
                "file_age_hours": None,
            },
        )

    def get_unhealthy_platforms(self) -> List[str]:
        """Get list of platforms with cookie issues"""
        unhealthy = []
        for platform, status in self.cookie_status.items():
            if not status.get("loaded", False) or status.get("error"):
                unhealthy.append(platform)
        return unhealthy

    async def extract_browser_cookies(
        self, platform: str, retry_count: int = 0
    ) -> bool:
        """Extract cookies from browser profile with retry logic"""
        async with self._extraction_lock:
            try:
                logger.info(
                    f"Extracting browser cookies for {platform} (attempt {retry_count + 1})"
                )

                # Run extraction in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                cookies = await loop.run_in_executor(
                    None, self._extract_platform_cookies, platform
                )

                if cookies:
                    success = await self.save_cookies(platform, cookies)
                    if success:
                        logger.info(
                            f"Extracted and saved {len(cookies)} cookies for {platform}"
                        )
                        return True
                    else:
                        logger.error(f"Failed to save extracted cookies for {platform}")
                        return False
                else:
                    logger.warning(f"No cookies found for {platform}")

                    # Mark platform as having extraction issues
                    if platform not in self.cookie_status:
                        self.cookie_status[platform] = {}
                    self.cookie_status[platform]["error"] = "No cookies extracted"
                    return False

            except Exception as e:
                logger.error(f"Failed to extract cookies for {platform}: {e}")

                # Retry logic
                if retry_count < self.max_retry_attempts - 1:
                    logger.info(
                        f"Retrying cookie extraction for {platform} in {self.retry_delay}s"
                    )
                    await asyncio.sleep(self.retry_delay)
                    return await self.extract_browser_cookies(platform, retry_count + 1)
                else:
                    logger.error(
                        f"Cookie extraction failed for {platform} after {self.max_retry_attempts} attempts"
                    )

                    # Update status to reflect failure
                    if platform not in self.cookie_status:
                        self.cookie_status[platform] = {}
                    self.cookie_status[platform][
                        "error"
                    ] = f"Extraction failed: {str(e)}"
                    return False

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

    async def refresh_cookies(self, force: bool = False) -> Dict[str, bool]:
        """Refresh all cookies with comprehensive error handling"""
        platforms = ["youtube", "peertube", "odysee", "rumble"]
        results = {}

        logger.info(
            f"Refreshing cookies for {len(platforms)} platforms (force={force})"
        )

        # Determine which platforms need refresh
        platforms_to_refresh = []
        for platform in platforms:
            should_refresh = force

            if not should_refresh:
                status = self.cookie_status.get(platform, {})
                # Refresh if cookies are old, missing, or have errors
                if (
                    status.get("file_age_hours", float("inf"))
                    > self.cookie_max_age_hours
                    or not status.get("loaded", False)
                    or status.get("error")
                ):
                    should_refresh = True

            if should_refresh:
                platforms_to_refresh.append(platform)
                logger.debug(f"Platform {platform} scheduled for refresh")
            else:
                logger.debug(f"Platform {platform} cookies are fresh, skipping")
                results[platform] = True

        # Refresh platforms concurrently with controlled concurrency
        semaphore = asyncio.Semaphore(2)  # Limit concurrent extractions

        async def refresh_platform(platform: str) -> Tuple[str, bool]:
            async with semaphore:
                try:
                    success = await self.extract_browser_cookies(platform)
                    return platform, success
                except Exception as e:
                    logger.error(f"Error refreshing {platform}: {e}")
                    return platform, False

        # Execute refreshes
        if platforms_to_refresh:
            refresh_tasks = [
                refresh_platform(platform) for platform in platforms_to_refresh
            ]
            refresh_results = await asyncio.gather(
                *refresh_tasks, return_exceptions=True
            )

            for result in refresh_results:
                if isinstance(result, tuple):
                    platform, success = result
                    results[platform] = success
                else:
                    logger.error(f"Unexpected refresh result: {result}")

        # Log summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        logger.info(
            f"Cookie refresh completed: {successful}/{total} platforms successful"
        )

        if successful < total:
            failed_platforms = [
                platform for platform, success in results.items() if not success
            ]
            logger.warning(f"Cookie refresh failed for: {', '.join(failed_platforms)}")

        return results

    async def cleanup(self):
        """Cleanup resources and save health status"""
        logger.info("Cleaning up cookie manager")

        # Save cookie status summary for diagnostics
        try:
            status_file = self.cookie_dir / "cookie_status.json"
            status_data = {
                "timestamp": datetime.now().isoformat(),
                "platforms": self.cookie_status,
            }

            async with aiofiles.open(status_file, "w") as f:
                await f.write(json.dumps(status_data, indent=2, default=str))

            logger.debug(f"Saved cookie status to {status_file}")
        except Exception as e:
            logger.warning(f"Failed to save cookie status: {e}")

        # Log final status summary
        healthy_platforms = [
            p for p in self.cookie_status.keys() if self.is_platform_healthy(p)
        ]
        unhealthy_platforms = self.get_unhealthy_platforms()

        logger.info(
            f"Cookie manager cleanup - Healthy: {len(healthy_platforms)}, Unhealthy: {len(unhealthy_platforms)}"
        )
        if unhealthy_platforms:
            logger.warning(
                f"Platforms with cookie issues: {', '.join(unhealthy_platforms)}"
            )

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
