import json
import logging
import os
import time
from typing import Optional

import redis
import yt_dlp
from flask import Flask, jsonify, request

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Import rumble_extractor if available
try:
    from extractors.rumble_extractor import RumbleExtractor
    RUMBLE_EXTRACTOR_AVAILABLE = True
except ImportError:
    logger.warning("RumbleExtractor not available. Using yt-dlp for Rumble.")
    RUMBLE_EXTRACTOR_AVAILABLE = False

# Initialize Rumble extractor if available and configured
rumble_extractor = None
USE_RUMBLE_EXTRACTOR = os.getenv("USE_RUMBLE_EXTRACTOR", "false").lower() == "true"

if RUMBLE_EXTRACTOR_AVAILABLE and USE_RUMBLE_EXTRACTOR:
    apify_api_token = os.getenv("APIFY_API_TOKEN")
    if apify_api_token:
        rumble_extractor = RumbleExtractor(apify_api_token)
        logger.info("RumbleExtractor initialized with Apify API token")
    else:
        logger.warning("APIFY_API_TOKEN not found. Falling back to yt-dlp for Rumble.")

# Redis connection for caching
try:
    r: Optional[redis.Redis] = redis.Redis(
        host="redis", port=6379, db=0, decode_responses=True
    )
except Exception as e:
    logger.warning(f"Redis connection failed: {e}")
    r = None

# Cache TTL in seconds
CACHE_TTL = 3600  # 1 hour

# yt-dlp options
YDL_OPTS = {
    "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
    "quiet": False,
    "no_warnings": False,
    "extract_flat": False,
    "nocheckcertificate": True,
    "simulate": True,
    "skip_download": True,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Add cookiefile if it exists
COOKIE_FILE = "/app/cookies/youtube_cookies.json"
if os.path.exists(COOKIE_FILE):
    YDL_OPTS["cookiefile"] = COOKIE_FILE


def get_cache_key(platform: str, video_id: str) -> str:
    """Generate cache key for platform/video combination"""
    return f"stream:{platform}:{video_id}"


def get_cached_url(platform: str, video_id: str) -> Optional[str]:
    """Get cached stream URL if available"""
    if not r:
        return None

    try:
        key = get_cache_key(platform, video_id)
        cached = r.get(key)
        if cached:
            data = json.loads(str(cached))
            # Check if URL is still valid
            if data.get("expires", 0) > time.time():
                return data.get("url")
    except Exception as e:
        logger.error(f"Cache retrieval error: {e}")

    return None


def cache_url(platform: str, video_id: str, url: str, ttl: int = CACHE_TTL):
    """Cache stream URL with expiration"""
    if not r:
        return

    try:
        key = get_cache_key(platform, video_id)
        data = {"url": url, "expires": time.time() + ttl, "cached_at": time.time()}
        r.setex(key, ttl, json.dumps(data))
    except Exception as e:
        logger.error(f"Cache storage error: {e}")


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "service": "stream-extractor",
        "rumble_extractor_available": RUMBLE_EXTRACTOR_AVAILABLE,
        "rumble_extractor_enabled": rumble_extractor is not None,
        "use_rumble_extractor": USE_RUMBLE_EXTRACTOR
    })


@app.route("/stream/<platform>/<video_id>")
def get_stream_url(platform: str, video_id: str):
    """Extract stream URL for a video"""

    # Check cache first
    cached_url = get_cached_url(platform, video_id)
    if cached_url:
        logger.info(f"Cache hit for {platform}/{video_id}")
        return jsonify({"url": cached_url, "cached": True})

    # Build URL based on platform
    if platform == "youtube":
        # Check if YouTube ID is complete (should be 11 characters)
        if len(video_id) != 11:
            logger.error(f"Invalid YouTube ID length: {video_id} (length: {len(video_id)})")
            return jsonify({"error": f"Invalid YouTube ID: {video_id} (should be 11 characters)"}), 400
        url = f"https://www.youtube.com/watch?v={video_id}"
    elif platform == "peertube":
        # PeerTube URLs need instance information
        instance = request.args.get("instance", "https://framatube.org")
        url = f"{instance}/videos/watch/{video_id}"
    elif platform == "odysee":
        url = f"https://odysee.com/{video_id}"
    elif platform == "rumble":
        url = f"https://rumble.com/v{video_id}"
    else:
        return jsonify({"error": f"Unsupported platform: {platform}"}), 400

    try:
        # Check if we should use Rumble extractor for Rumble videos
        if platform == "rumble" and rumble_extractor:
            logger.info(f"Using RumbleExtractor for {platform}/{video_id}")
            try:
                # Get metadata and stream URL from Rumble extractor
                metadata = rumble_extractor.get_video_metadata(url)
                stream_url = rumble_extractor.download_audio(url, quality='best')
                
                # Cache the URL
                ttl = CACHE_TTL  # Default cache time
                cache_url(platform, video_id, stream_url, ttl)
                
                return jsonify(
                    {
                        "url": stream_url,
                        "cached": False,
                        "title": metadata.get("title", "Unknown"),
                        "duration": metadata.get("duration"),
                        "thumbnail": metadata.get("thumbnail_url"),
                        "extractor": "rumble_extractor"
                    }
                )
            except NotImplementedError:
                logger.warning("RumbleExtractor not fully implemented. Falling back to yt-dlp.")
                # Fall through to yt-dlp
            except Exception as e:
                logger.error(f"RumbleExtractor error: {e}. Falling back to yt-dlp.")
                # Fall through to yt-dlp
        
        # Use yt-dlp for extraction (default or fallback)
        # Custom options for specific platforms
        ydl_opts = YDL_OPTS.copy()

        # Platform-specific adjustments
        if platform == "odysee":
            ydl_opts["format"] = "best[ext=mp4]/best"
        elif platform == "rumble":
            ydl_opts["format"] = "mp4/best"

        # Extract stream URL using yt-dlp
        logger.info(f"Extracting stream for {platform}/{video_id} from {url} using yt-dlp")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            logger.info(f"Extracted info for {platform}/{video_id}")
            if info is None:
                logger.error(f"yt-dlp returned None for {url}")
                return jsonify({"error": "Failed to extract stream info"}), 404

            if "url" in info:
                stream_url = info["url"]
            elif "formats" in info and info["formats"]:
                # Get best audio format
                formats = info["formats"]
                audio_formats = [f for f in formats if f.get("acodec") != "none"]
                if audio_formats:
                    # Sort by quality
                    audio_formats.sort(key=lambda f: f.get("abr", 0), reverse=True)
                    stream_url = audio_formats[0]["url"]
                else:
                    # Fallback to best format
                    stream_url = formats[-1]["url"]
            else:
                return jsonify({"error": "No stream URL found"}), 404

            # Determine TTL based on platform
            ttl = CACHE_TTL
            if platform == "youtube":
                # YouTube URLs expire faster
                ttl = 1800  # 30 minutes

            # Cache the URL
            cache_url(platform, video_id, stream_url, ttl)

            return jsonify(
                {
                    "url": stream_url,
                    "cached": False,
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration"),
                    "thumbnail": info.get("thumbnail"),
                    "extractor": "yt-dlp"
                }
            )

    except Exception as e:
        logger.error(f"Stream extraction error for {platform}/{video_id}: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route("/stream", methods=["POST"])
def get_stream_url_post():
    """Extract stream URL via POST request"""
    data = request.json
    platform = data.get("platform")
    video_id = data.get("video_id")

    if not platform or not video_id:
        return jsonify({"error": "Missing platform or video_id"}), 400

    return get_stream_url(platform, video_id)


@app.route("/info/<platform>/<video_id>")
def get_video_info(platform: str, video_id: str):
    """Get video metadata without stream URL"""

    # Build URL based on platform
    if platform == "youtube":
        # Check if YouTube ID is complete (should be 11 characters)
        if len(video_id) != 11:
            logger.error(f"Invalid YouTube ID length: {video_id} (length: {len(video_id)})")
            return jsonify({"error": f"Invalid YouTube ID: {video_id} (should be 11 characters)"}), 400
        url = f"https://www.youtube.com/watch?v={video_id}"
    elif platform == "peertube":
        instance = request.args.get("instance", "https://framatube.org")
        url = f"{instance}/videos/watch/{video_id}"
    elif platform == "odysee":
        url = f"https://odysee.com/{video_id}"
    elif platform == "rumble":
        url = f"https://rumble.com/v{video_id}"
    else:
        return jsonify({"error": f"Unsupported platform: {platform}"}), 400

    try:
        # Check if we should use Rumble extractor for Rumble videos
        if platform == "rumble" and rumble_extractor:
            logger.info(f"Using RumbleExtractor for info {platform}/{video_id}")
            try:
                # Get metadata from Rumble extractor
                metadata = rumble_extractor.get_video_metadata(url)
                return jsonify(
                    {
                        "title": metadata.get("title"),
                        "duration": metadata.get("duration"),
                        "thumbnail": metadata.get("thumbnail_url"),
                        "description": metadata.get("description"),
                        "uploader": metadata.get("uploader"),
                        "view_count": metadata.get("view_count"),
                        "like_count": None,  # Not available in Rumble extractor
                        "upload_date": metadata.get("publish_date"),
                        "extractor": "rumble_extractor"
                    }
                )
            except NotImplementedError:
                logger.warning("RumbleExtractor metadata not implemented. Falling back to yt-dlp.")
                # Fall through to yt-dlp
            except Exception as e:
                logger.error(f"RumbleExtractor metadata error: {e}. Falling back to yt-dlp.")
                # Fall through to yt-dlp
        
        # Use yt-dlp for metadata extraction (default or fallback)
        ydl_opts = YDL_OPTS.copy()
        ydl_opts["extract_flat"] = True  # Only extract metadata

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return jsonify(
                {
                    "title": info.get("title"),
                    "duration": info.get("duration"),
                    "thumbnail": info.get("thumbnail"),
                    "description": info.get("description"),
                    "uploader": info.get("uploader"),
                    "view_count": info.get("view_count"),
                    "like_count": info.get("like_count"),
                    "upload_date": info.get("upload_date"),
                    "extractor": "yt-dlp"
                }
            )

    except Exception as e:
        logger.error(f"Info extraction error for {platform}/{video_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/clear-cache", methods=["POST"])
def clear_cache():
    """Clear the stream URL cache"""
    if not r:
        return jsonify({"error": "Redis not available"}), 500

    try:
        # Clear all stream cache keys
        keys = r.keys("stream:*")
        if keys:
            r.delete(*keys)
        return jsonify({"status": "success", "cleared": len(keys)})
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run Flask app
    app.run(host="0.0.0.0", port=5000, debug=False)
