from flask import Flask, jsonify, request
import yt_dlp
import logging
import redis
import json
import time
import os

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Redis connection for caching
try:
    r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
except Exception as e:
    logger.warning(f"Redis connection failed: {e}")
    r = None

# Cache TTL in seconds
CACHE_TTL = 3600  # 1 hour

# yt-dlp options
YDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'force_generic_extractor': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'no_color': True,
    'cookiefile': '/app/cookies/youtube_cookies.json',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_cache_key(platform: str, video_id: str) -> str:
    """Generate cache key for platform/video combination"""
    return f"stream:{platform}:{video_id}"

def get_cached_url(platform: str, video_id: str) -> str:
    """Get cached stream URL if available"""
    if not r:
        return None
    
    try:
        key = get_cache_key(platform, video_id)
        cached = r.get(key)
        if cached:
            data = json.loads(cached)
            # Check if URL is still valid
            if data.get('expires', 0) > time.time():
                return data.get('url')
    except Exception as e:
        logger.error(f"Cache retrieval error: {e}")
    
    return None

def cache_url(platform: str, video_id: str, url: str, ttl: int = CACHE_TTL):
    """Cache stream URL with expiration"""
    if not r:
        return
    
    try:
        key = get_cache_key(platform, video_id)
        data = {
            'url': url,
            'expires': time.time() + ttl,
            'cached_at': time.time()
        }
        r.setex(key, ttl, json.dumps(data))
    except Exception as e:
        logger.error(f"Cache storage error: {e}")

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'stream-extractor'})

@app.route('/stream/<platform>/<video_id>')
def get_stream_url(platform: str, video_id: str):
    """Extract stream URL for a video"""
    
    # Check cache first
    cached_url = get_cached_url(platform, video_id)
    if cached_url:
        logger.info(f"Cache hit for {platform}/{video_id}")
        return jsonify({'url': cached_url, 'cached': True})
    
    # Build URL based on platform
    if platform == 'youtube':
        url = f"https://www.youtube.com/watch?v={video_id}"
    elif platform == 'peertube':
        # PeerTube URLs need instance information
        instance = request.args.get('instance', 'https://framatube.org')
        url = f"{instance}/videos/watch/{video_id}"
    elif platform == 'odysee':
        url = f"https://odysee.com/{video_id}"
    elif platform == 'rumble':
        url = f"https://rumble.com/v{video_id}"
    else:
        return jsonify({'error': f'Unsupported platform: {platform}'}), 400
    
    try:
        # Custom options for specific platforms
        ydl_opts = YDL_OPTS.copy()
        
        # Platform-specific adjustments
        if platform == 'odysee':
            ydl_opts['format'] = 'best[ext=mp4]/best'
        elif platform == 'rumble':
            ydl_opts['format'] = 'mp4/best'
        
        # Extract stream URL using yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'url' in info:
                stream_url = info['url']
            elif 'formats' in info and info['formats']:
                # Get best audio format
                formats = info['formats']
                audio_formats = [f for f in formats if f.get('acodec') != 'none']
                if audio_formats:
                    # Sort by quality
                    audio_formats.sort(key=lambda f: f.get('abr', 0), reverse=True)
                    stream_url = audio_formats[0]['url']
                else:
                    # Fallback to best format
                    stream_url = formats[-1]['url']
            else:
                return jsonify({'error': 'No stream URL found'}), 404
            
            # Determine TTL based on platform
            ttl = CACHE_TTL
            if platform == 'youtube':
                # YouTube URLs expire faster
                ttl = 1800  # 30 minutes
            
            # Cache the URL
            cache_url(platform, video_id, stream_url, ttl)
            
            return jsonify({
                'url': stream_url,
                'cached': False,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail')
            })
            
    except Exception as e:
        logger.error(f"Stream extraction error for {platform}/{video_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/stream', methods=['POST'])
def get_stream_url_post():
    """Extract stream URL via POST request"""
    data = request.json
    platform = data.get('platform')
    video_id = data.get('video_id')
    
    if not platform or not video_id:
        return jsonify({'error': 'Missing platform or video_id'}), 400
    
    return get_stream_url(platform, video_id)

@app.route('/info/<platform>/<video_id>')
def get_video_info(platform: str, video_id: str):
    """Get video metadata without stream URL"""
    
    # Build URL based on platform
    if platform == 'youtube':
        url = f"https://www.youtube.com/watch?v={video_id}"
    elif platform == 'peertube':
        instance = request.args.get('instance', 'https://framatube.org')
        url = f"{instance}/videos/watch/{video_id}"
    elif platform == 'odysee':
        url = f"https://odysee.com/{video_id}"
    elif platform == 'rumble':
        url = f"https://rumble.com/v{video_id}"
    else:
        return jsonify({'error': f'Unsupported platform: {platform}'}), 400
    
    try:
        ydl_opts = YDL_OPTS.copy()
        ydl_opts['extract_flat'] = True  # Only extract metadata
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return jsonify({
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'description': info.get('description'),
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
                'upload_date': info.get('upload_date')
            })
            
    except Exception as e:
        logger.error(f"Info extraction error for {platform}/{video_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    """Clear the stream URL cache"""
    if not r:
        return jsonify({'error': 'Redis not available'}), 500
    
    try:
        # Clear all stream cache keys
        keys = r.keys('stream:*')
        if keys:
            r.delete(*keys)
        return jsonify({'status': 'success', 'cleared': len(keys)})
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)