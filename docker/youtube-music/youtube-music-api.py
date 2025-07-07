#!/usr/bin/env python3
"""
Lightweight YouTube Music API server for Discord bot integration.
Uses yt-dlp instead of the desktop app for better VPS compatibility.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import yt_dlp
import httpx
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Music API", version="1.0.0")

# yt-dlp options for YouTube Music
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'force_generic_extractor': False,
    'cookiefile': '/app/cookies/youtube_cookies.txt',  # Optional cookies
}

# yt-dlp options for getting stream URL
STREAM_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'format': 'bestaudio/best',
    'extract_flat': False,
    'cookiefile': '/app/cookies/youtube_cookies.txt',  # Optional cookies
}


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "type": "youtube-music-api-simple"
    }


@app.get("/api/search")
async def search_music(q: str, limit: int = 10, type: str = "songs"):
    """Search for music on YouTube Music"""
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    
    try:
        # Use YouTube Music search
        search_query = f"ytsearch{limit}:{q}"
        
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(search_query, download=False)
            
        if not result or 'entries' not in result:
            return {"results": []}
        
        results = []
        for entry in result['entries'][:limit]:
            if entry:
                video_data = {
                    "videoId": entry.get('id', ''),
                    "title": entry.get('title', 'Unknown'),
                    "artist": entry.get('uploader', 'Unknown Artist'),
                    "duration": entry.get('duration', 0),
                    "thumbnail": entry.get('thumbnail', ''),
                    "url": f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                    "album": "",  # YouTube doesn't provide album info
                    "year": "",
                    "explicit": False
                }
                results.append(video_data)
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/song/{video_id}")
async def get_song_details(video_id: str):
    """Get details for a specific song"""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {
            "id": video_id,
            "title": info.get('title', 'Unknown'),
            "artist": info.get('uploader', 'Unknown Artist'),
            "duration": info.get('duration', 0),
            "thumbnail": info.get('thumbnail', ''),
            "description": info.get('description', ''),
            "viewCount": info.get('view_count', 0),
            "likeCount": info.get('like_count', 0),
            "uploadDate": info.get('upload_date', '')
        }
        
    except Exception as e:
        logger.error(f"Get song details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stream/{video_id}")
async def get_stream_url(video_id: str):
    """Get stream URL for a video"""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(STREAM_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get best audio format
        formats = info.get('formats', [])
        audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        
        if not audio_formats:
            # Fallback to best format
            best_format = info.get('url')
        else:
            # Sort by quality
            audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
            best_format = audio_formats[0].get('url')
        
        if not best_format:
            raise HTTPException(status_code=404, detail="No stream URL found")
        
        return {
            "stream_url": best_format,
            "quality": "high",
            "format": "audio"
        }
        
    except Exception as e:
        logger.error(f"Get stream URL error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/status")
async def auth_status():
    """Check authentication status"""
    # Check if cookies exist
    import os
    cookies_exist = os.path.exists('/app/cookies/youtube_cookies.txt')
    
    return {
        "authenticated": cookies_exist,
        "user": None,
        "subscription": "free" if not cookies_exist else "unknown"
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "YouTube Music API",
        "version": "1.0.0",
        "endpoints": [
            "/api/health",
            "/api/search?q=query&limit=10",
            "/api/song/{video_id}",
            "/api/stream/{video_id}",
            "/api/auth/status"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9863)