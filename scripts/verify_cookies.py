#!/usr/bin/env python3
"""Verify cookie extraction functionality"""
from src.extractors.cross_platform_cookies import CrossPlatformCookieExtractor

def main():
    print("Verifying Cookie Extraction\n")
    
    # Create extractor
    extractor = CrossPlatformCookieExtractor()
    
    # Extract YouTube cookies
    youtube_jar = extractor.find_youtube_cookies()
    
    print(f"Found {len(youtube_jar)} YouTube cookies")
    
    # Show some cookie names (not values for security)
    for i, cookie in enumerate(youtube_jar):
        if i < 5:
            print(f"  - {cookie.name} ({cookie.domain})")
        if i == 5:
            print(f"  ... and {len(youtube_jar) - 5} more")
            break
    
    # Test saving cookies to file
    from pathlib import Path
    cookie_file = Path('verification_cookies.json')
    
    try:
        extractor.save_cookies_json(cookie_file, domains=['youtube.com', '.youtube.com'])
        print(f"\n✓ Successfully saved cookies to {cookie_file}")
        
        # Check file exists and has content
        if cookie_file.exists() and cookie_file.stat().st_size > 0:
            print(f"✓ Cookie file exists with {cookie_file.stat().st_size} bytes")
        else:
            print("✗ Cookie file is empty or doesn't exist")
            
    except Exception as e:
        print(f"\n✗ Error saving cookies: {e}")
    finally:
        # Clean up
        if cookie_file.exists():
            cookie_file.unlink()
    
    print("\nVerification complete!")

if __name__ == "__main__":
    main()