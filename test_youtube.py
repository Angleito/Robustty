import yt_dlp
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test YouTube video
video_id = "VNdHd1asf9s"
url = f"https://www.youtube.com/watch?v={video_id}"

print(f"Testing video: {url}")

# Simple yt-dlp options
ydl_opts = {
    'format': 'best',
    'quiet': False,
    'no_warnings': False,
    'simulate': True,
    'skip_download': True,
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        print(f"Title: {info.get('title')}")
        print(f"ID: {info.get('id')}")
        print(f"Formats: {len(info.get('formats', []))}")
        
        # Find audio formats
        formats = info.get('formats', [])
        audio_formats = [f for f in formats if f.get('acodec') != 'none']
        print(f"Audio formats: {len(audio_formats)}")
        
        if audio_formats:
            best_audio = audio_formats[0]
            print(f"Best audio URL: {best_audio.get('url', 'Not found')[:100]}...")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()