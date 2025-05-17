"""Browser cookie extraction for YouTube authentication"""
import json
import logging
import os
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import browser_cookie3, but make it optional
try:
    import browser_cookie3
    BROWSER_COOKIE3_AVAILABLE = True
except ImportError:
    browser_cookie3 = None
    BROWSER_COOKIE3_AVAILABLE = False
    logger.warning("browser_cookie3 is not installed. Cookie extraction will be disabled.")

SUPPORTED_DOMAINS = ["youtube.com", ".youtube.com"]


def extract_cookies_browser() -> Dict[str, List[Dict]]:
    """Extract cookies from browser profiles"""
    if not BROWSER_COOKIE3_AVAILABLE:
        logger.warning("browser_cookie3 is not available. Cannot extract cookies.")
        return {}
    
    cookies = {}

    # Browser functions to try
    browsers = {
        "chrome": browser_cookie3.chrome,
        "firefox": browser_cookie3.firefox,
        "brave": browser_cookie3.brave,
        "opera": browser_cookie3.opera,
        "edge": browser_cookie3.edge,
        "chromium": browser_cookie3.chromium,
    }

    for browser_name, browser_func in browsers.items():
        try:
            browser_cookies = []
            for cookie in browser_func(domain_name=".youtube.com"):
                browser_cookies.append(
                    {
                        "name": cookie.name,
                        "value": cookie.value,
                        "domain": cookie.domain,
                        "path": cookie.path,
                        "secure": cookie.secure,
                        "httpOnly": cookie.has_nonstandard_attr("HttpOnly"),
                    }
                )

            if browser_cookies:
                cookies[browser_name] = browser_cookies
                logger.info(
                    f"Extracted {len(browser_cookies)} cookies from {browser_name.title()}"
                )
        except AttributeError:
            logger.debug(
                f"Browser {browser_name} not supported in this version of browser_cookie3"
            )
        except Exception as e:
            logger.warning(f"Failed to extract {browser_name.title()} cookies: {e}")

    return cookies


def extract_manual_cookies(cookie_file: str) -> Optional[List[Dict]]:
    """Extract cookies from a manually provided JSON file"""
    try:
        if os.path.exists(cookie_file):
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
                logger.info(f"Loaded {len(cookies)} cookies from {cookie_file}")
                return cookies
    except Exception as e:
        logger.error(f"Failed to load manual cookie file: {e}")
    return None


def save_cookies(cookies: Dict[str, List[Dict]], output_dir: str):
    """Save cookies to JSON file"""
    if not cookies:
        logger.warning("No cookies to save")
        # Check for manual cookie file
        manual_cookie_file = os.path.join(output_dir, "manual_cookies.json")
        manual_cookies = extract_manual_cookies(manual_cookie_file)
        if manual_cookies:
            output_file = os.path.join(output_dir, "youtube_cookies.json")
            with open(output_file, "w") as f:
                json.dump(manual_cookies, f, indent=2)
            logger.info(f"Saved manual cookies to {output_file}")
        return

    # Priority order for browsers (prefer Brave and Opera since user mentioned them)
    browser_priority = ["brave", "opera", "chrome", "edge", "firefox", "chromium"]

    # Use the first available browser's cookies in priority order
    browser_cookies = None
    selected_browser = None

    for browser in browser_priority:
        if browser in cookies and cookies[browser]:
            browser_cookies = cookies[browser]
            selected_browser = browser
            logger.info(f"Using cookies from {browser.title()}")
            break

    # If no priority browser found, use any available
    if not browser_cookies:
        for browser, cookie_list in cookies.items():
            if cookie_list:
                browser_cookies = cookie_list
                selected_browser = browser
                logger.info(f"Using cookies from {browser.title()}")
                break

    if not browser_cookies:
        logger.warning("No valid cookies found")
        return

    output_file = os.path.join(output_dir, "youtube_cookies.json")

    # Convert to yt-dlp format
    ytdlp_cookies = []
    for cookie in browser_cookies:
        ytdlp_cookies.append(
            {
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie["domain"],
                "path": cookie["path"],
                "secure": cookie["secure"],
                "httpOnly": cookie.get("httpOnly", False),
                "sameSite": "None",
            }
        )

    with open(output_file, "w") as f:
        json.dump(ytdlp_cookies, f, indent=2)

    browser_name = selected_browser.title() if selected_browser else "Unknown"
    logger.info(
        f"Saved {len(ytdlp_cookies)} cookies from {browser_name} to {output_file}"
    )


def main():
    """Main extraction loop"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    output_dir = "/app/cookies"
    os.makedirs(output_dir, exist_ok=True)

    refresh_interval = int(os.environ.get("REFRESH_INTERVAL", 3600))

    if not BROWSER_COOKIE3_AVAILABLE:
        logger.warning("Cookie extraction service is running in manual mode.")
        logger.warning("Place your cookies in /app/cookies/manual_cookies.json")
        logger.warning("The service will check for manual cookies periodically.")
    else:
        logger.info("Starting cookie extraction service")

    while True:
        try:
            if BROWSER_COOKIE3_AVAILABLE:
                logger.info("Extracting cookies...")
                logger.info(
                    "Attempting to extract cookies from: Brave, Opera, Chrome, Edge, Firefox, Chromium"
                )

                cookies = extract_cookies_browser()

                if cookies:
                    browsers_found = list(cookies.keys())
                    logger.info(
                        f"Successfully extracted cookies from: {', '.join(browsers_found)}"
                    )
                else:
                    logger.warning("No cookies found in any supported browser")
            else:
                cookies = {}

            save_cookies(cookies, output_dir)

            logger.info(f"Sleeping for {refresh_interval} seconds")
            time.sleep(refresh_interval)

        except KeyboardInterrupt:
            logger.info("Shutting down cookie extractor")
            break
        except Exception as e:
            logger.error(f"Error in extraction loop: {e}")
            logger.error("Stack trace: ", exc_info=True)
            time.sleep(60)  # Sleep 1 minute on error


if __name__ == "__main__":
    main()