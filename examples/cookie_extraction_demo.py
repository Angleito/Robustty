#!/usr/bin/env python3
"""Demo script for cross-platform cookie extraction"""
import asyncio
import logging
from pathlib import Path

from src.extractors.cross_platform_cookies import CrossPlatformCookieExtractor
from src.services.cookie_manager import CookieManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def demo_basic_extraction():
    """Demonstrate basic cookie extraction"""
    print("\n=== Basic Cookie Extraction Demo ===")
    
    # Create extractor
    extractor = CrossPlatformCookieExtractor()
    
    # Extract all cookies
    print("\nExtracting cookies from all browsers...")
    all_cookies = extractor.extract_all_cookies()
    
    for browser, cookies in all_cookies.items():
        print(f"{browser}: {len(cookies)} cookies found")
    
    # Extract YouTube cookies specifically
    print("\nExtracting YouTube cookies...")
    youtube_jar = extractor.find_youtube_cookies()
    print(f"Found {len(youtube_jar)} YouTube cookies")
    
    # Extract platform-specific cookies
    platforms = ['youtube', 'rumble', 'odysee', 'peertube']
    for platform in platforms:
        print(f"\nExtracting {platform} cookies...")
        platform_jar = extractor.find_platform_cookies(platform)
        print(f"Found {len(platform_jar)} {platform} cookies")


async def demo_cookie_manager():
    """Demonstrate cookie manager integration"""
    print("\n=== Cookie Manager Demo ===")
    
    # Create cookie manager
    config = {'cookie_dir': 'data/cookies'}
    manager = CookieManager(config)
    
    # Load existing cookies
    await manager.load_cookies()
    
    # Extract browser cookies for each platform
    platforms = ['youtube', 'rumble']
    for platform in platforms:
        print(f"\nExtracting {platform} cookies...")
        await manager.extract_browser_cookies(platform)
        
        # Get cookies
        cookies = manager.get_cookies(platform)
        if cookies:
            print(f"Saved {len(cookies)} {platform} cookies")
        else:
            print(f"No {platform} cookies found")


def demo_cookie_saving():
    """Demonstrate saving cookies to file"""
    print("\n=== Cookie Saving Demo ===")
    
    extractor = CrossPlatformCookieExtractor()
    
    # Save YouTube cookies
    output_path = Path('cookies/youtube_cookies.json')
    print(f"\nSaving YouTube cookies to {output_path}...")
    
    extractor.save_cookies_json(
        output_path,
        domains=['youtube.com', '.youtube.com']
    )
    
    if output_path.exists():
        print(f"Cookies saved successfully to {output_path}")
    else:
        print("Failed to save cookies")


def demo_browser_priority():
    """Demonstrate browser priority order"""
    print("\n=== Browser Priority Demo ===")
    
    extractor = CrossPlatformCookieExtractor()
    
    # Show browser priority
    print("\nBrowser priority order:")
    priority = ['brave', 'opera', 'chrome', 'edge', 'firefox', 'chromium']
    for i, browser in enumerate(priority, 1):
        print(f"{i}. {browser.title()}")
    
    # Extract with priority
    jar = extractor.load_all_cookies()
    print(f"\nLoaded {len(jar)} cookies using priority order")


async def main():
    """Run all demos"""
    print("Cross-Platform Cookie Extraction Demo")
    print("====================================")
    
    # Basic extraction
    demo_basic_extraction()
    
    # Cookie manager
    await demo_cookie_manager()
    
    # Saving cookies
    demo_cookie_saving()
    
    # Browser priority
    demo_browser_priority()
    
    print("\n\nDemo completed!")


if __name__ == "__main__":
    # Create necessary directories
    Path('cookies').mkdir(exist_ok=True)
    Path('data/cookies').mkdir(parents=True, exist_ok=True)
    
    # Run demos
    asyncio.run(main())