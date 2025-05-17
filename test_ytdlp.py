#!/usr/bin/env python3
import yt_dlp

def test_extract():
    url = "https://www.youtube.com/watch?v=j89Qu0xu188"
    
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'no_warnings': True,
        'quiet': True,
        'no_check_certificate': True,
        'prefer_insecure': True,
        'no_color': True,
        'no_playlist': True,
        'skip_download': True,
        'age_limit': None,
        'extract_flat': False
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            if info:
                print(f"Title: {info.get('title')}")
                print(f"ID: {info.get('id')}")
                print(f"Formats available: {len(info.get('formats', []))}")
                print(f"Duration: {info.get('duration')} seconds")
                print(f"Direct URL: {info.get('url', 'Not available')}")
            else:
                print("No info extracted")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print(f"Testing with yt-dlp version: {yt_dlp.version.__version__}")
    test_extract()