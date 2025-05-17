#!/usr/bin/env python3
"""Test cookie manager integration"""
import asyncio
import logging
from src.services.cookie_manager import CookieManager

logging.basicConfig(level=logging.INFO)

async def test_cookie_manager():
    """Test the cookie manager"""
    config = {'cookie_dir': 'data/cookies'}
    manager = CookieManager(config)
    
    # Test extraction for different platforms
    platforms = ['youtube', 'rumble', 'odysee']
    
    for platform in platforms:
        print(f"\nTesting {platform} cookie extraction...")
        
        # Extract cookies
        await manager.extract_browser_cookies(platform)
        
        # Get cookies
        cookies = manager.get_cookies(platform)
        
        if cookies:
            print(f"✓ Found {len(cookies)} {platform} cookies")
            # Show some cookie names (not values)
            for cookie in cookies[:3]:
                print(f"  - {cookie['name']}")
        else:
            print(f"✗ No {platform} cookies found")
    
    # Test cookie jar creation
    print("\nTesting cookie jar creation...")
    jar = manager.get_cookie_jar('youtube')
    print(f"Created cookie jar with {len(jar)} cookies")

if __name__ == "__main__":
    asyncio.run(test_cookie_manager())