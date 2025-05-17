#!/usr/bin/env python3
"""Debug cookie extraction issues"""
import logging
from src.extractors.browser_paths import detect_os, find_profiles, get_browser_paths
from src.extractors.cross_platform_cookies import CrossPlatformCookieExtractor

# Enable ALL debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def debug_extraction():
    """Debug cookie extraction"""
    print("=== Cookie Extraction Debug ===\n")
    
    # 1. OS Detection
    os_name = detect_os()
    print(f"1. Detected OS: {os_name}\n")
    
    # 2. Browser paths
    print("2. Browser paths:")
    paths = get_browser_paths()
    for browser, info in paths.items():
        print(f"   {browser}:")
        print(f"     Profile dir: {info['profiles_dir']}")
        print(f"     Cookie file: {info['cookie_file']}")
        print(f"     Exists: {info['profiles_dir'].exists()}")
    print()
    
    # 3. Find profiles
    print("3. Browser profiles:")
    for browser in ['chrome', 'brave', 'firefox']:
        profiles = find_profiles(browser)
        print(f"   {browser}: {len(profiles)} profiles found")
        for profile in profiles:
            print(f"     - {profile}")
    print()
    
    # 4. Extract cookies
    print("4. Cookie extraction:")
    extractor = CrossPlatformCookieExtractor()
    
    for browser in ['chrome', 'brave', 'firefox']:
        print(f"\n   Extracting from {browser}...")
        try:
            cookies = extractor._extract_browser_cookies(browser)
            print(f"   ✓ Found {len(cookies)} cookies")
        except Exception as e:
            print(f"   ✗ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_extraction()