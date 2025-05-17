#!/usr/bin/env python3
"""Simple cookie extraction test"""
from src.extractors.cross_platform_cookies import CrossPlatformCookieExtractor

def main():
    print("Testing Cookie Extraction\n")
    
    # Create extractor
    extractor = CrossPlatformCookieExtractor()
    
    # Extract all cookies (without debug logging)
    print("Extracting cookies from all browsers...")
    all_cookies = extractor.extract_all_cookies()
    
    # Show summary
    print("\nCookie Summary:")
    print("-" * 30)
    for browser, cookies in all_cookies.items():
        print(f"{browser:10} | {len(cookies):5} cookies")
    
    # Extract YouTube cookies
    print("\nYouTube Cookies:")
    print("-" * 30)
    youtube_jar = extractor.find_youtube_cookies()
    
    if youtube_jar:
        print(f"Found {len(youtube_jar)} YouTube cookies")
        
        # Show some cookie names (not values for security)
        for i, cookie in enumerate(youtube_jar):
            if i < 5:  # Show first 5
                print(f"  - {cookie.name}")
        if len(youtube_jar) > 5:
            print(f"  ... and {len(youtube_jar) - 5} more")
    else:
        print("No YouTube cookies found")
    
    # Test saving cookies
    print("\nTesting cookie saving...")
    try:
        from pathlib import Path
        output_path = Path('cookies/youtube_cookies.json')
        output_path.parent.mkdir(exist_ok=True)
        
        extractor.save_cookies_json(output_path, domains=['youtube.com', '.youtube.com'])
        print(f"✓ Cookies saved to {output_path}")
    except Exception as e:
        print(f"✗ Failed to save cookies: {e}")

if __name__ == "__main__":
    main()