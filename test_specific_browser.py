#!/usr/bin/env python3
"""Test specific browser cookie extraction"""
import sys
from src.extractors.cross_platform_cookies import CrossPlatformCookieExtractor

def test_browser(browser_name):
    """Test a specific browser"""
    print(f"Testing {browser_name} cookie extraction...")
    
    extractor = CrossPlatformCookieExtractor([browser_name])
    
    # Extract cookies
    cookies = extractor._extract_browser_cookies(browser_name)
    
    if cookies:
        print(f"✓ Found {len(cookies)} cookies in {browser_name}")
        
        # Group by domain
        domains = {}
        for cookie in cookies:
            domain = cookie.host_key
            if domain not in domains:
                domains[domain] = 0
            domains[domain] += 1
        
        # Show domains
        print("\nCookies by domain:")
        for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {domain}: {count} cookies")
    else:
        print(f"✗ No cookies found in {browser_name}")
        print("  Make sure the browser is installed and has been used")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        browser = sys.argv[1].lower()
    else:
        browser = 'chrome'
    
    test_browser(browser)