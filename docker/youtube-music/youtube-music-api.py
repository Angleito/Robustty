#!/usr/bin/env python3
"""
Lightweight YouTube Music API server for Discord bot integration.
Uses yt-dlp instead of the desktop app for better VPS compatibility.
"""

import asyncio
import logging
import ssl
import socket
import os
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import yt_dlp
import httpx
from datetime import datetime

# Set environment variables for SSL/TLS configuration
os.environ['SSL_CERT_FILE'] = '/etc/ssl/certs/ca-certificates.crt'
os.environ['SSL_CERT_DIR'] = '/etc/ssl/certs'
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
os.environ['CURL_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
# Disable SSL verification warnings
os.environ['PYTHONHTTPSVERIFY'] = '1'
# Set socket timeout
socket.setdefaulttimeout(90)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Music API", version="1.0.0")

# Global SSL context configuration
def setup_ssl_context():
    """Setup SSL context for better compatibility"""
    try:
        # Create SSL context with more lenient settings for VPS
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Set timeouts
        socket.setdefaulttimeout(60)
        
        logger.info("SSL context configured successfully")
        return context
    except Exception as e:
        logger.warning(f"Failed to setup SSL context: {e}")
        return None

# Initialize SSL context
ssl_context = setup_ssl_context()

# yt-dlp options for YouTube Music with SSL/TLS and timeout fixes
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'force_generic_extractor': False,
    'cookiefile': '/app/cookies/youtube_cookies.txt',  # Optional cookies
    # SSL/TLS Configuration - More lenient for VPS environments
    'nocheckcertificate': False,  # Keep certificate checking for security
    'prefer_insecure': False,     # Use HTTPS when available
    # Timeout settings for VPS environments - optimized values
    'socket_timeout': 45,         # Reduced from 120s for faster failure detection
    'http_chunk_size': 1048576,   # 1MB chunks for better VPS performance  
    # Network retry settings
    'retries': 1,                 # Reduced retries to prevent hanging
    'fragment_retries': 1,
    'retry_sleep': 1,
    # User agent to avoid blocking
    'user_agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
    # Additional headers
    'http_headers': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    },
    # DNS settings
    'force_ipv4': True,           # Force IPv4 for better VPS compatibility
    # Additional SSL debugging options
    'debug_printtraffic': False,  # Set to True for debugging
    'call_home': False,          # Disable analytics calls
    'check_formats': False,      # Skip format checks to speed up
}

# yt-dlp options for getting stream URL with SSL/TLS fixes
STREAM_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'format': 'bestaudio/best',
    'extract_flat': False,
    'cookiefile': '/app/cookies/youtube_cookies.txt',  # Optional cookies
    # SSL/TLS Configuration - More lenient for VPS environments
    'nocheckcertificate': False,  # Keep certificate checking for security
    'prefer_insecure': False,     # Use HTTPS when available
    # Timeout settings for VPS environments - optimized values
    'socket_timeout': 45,         # Reduced from 120s for faster failure detection
    'http_chunk_size': 1048576,   # 1MB chunks for better VPS performance  
    # Network retry settings
    'retries': 1,                 # Reduced retries to prevent hanging
    'fragment_retries': 1,
    'retry_sleep': 1,
    # User agent to avoid blocking
    'user_agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
    # Additional headers
    'http_headers': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    },
    # DNS settings
    'force_ipv4': True,           # Force IPv4 for better VPS compatibility
    # Additional SSL debugging options
    'debug_printtraffic': False,  # Set to True for debugging
    'call_home': False,          # Disable analytics calls
    'check_formats': False,      # Skip format checks to speed up
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


async def test_network_connectivity():
    """Test network connectivity before making requests"""
    try:
        # Test DNS resolution
        socket.gethostbyname('www.youtube.com')
        logger.info("DNS resolution test passed")
        
        # Test HTTPS connection with optimized timeout settings
        timeout = httpx.Timeout(15.0, connect=5.0, read=5.0)
        async with httpx.AsyncClient(timeout=timeout, verify=True) as client:
            response = await client.get('https://www.youtube.com')
            if response.status_code == 200:
                logger.info("Network connectivity test passed")
                return True
            else:
                logger.warning(f"Network connectivity test failed with status: {response.status_code}")
                return False
    except Exception as e:
        logger.warning(f"Network connectivity test failed: {e}")
        return False

@app.get("/api/search")
async def search_music(q: str, limit: int = 10, type: str = "songs"):
    """Search for music on YouTube Music"""
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    
    # Test network connectivity first (non-blocking)
    connectivity_ok = await test_network_connectivity()
    if not connectivity_ok:
        logger.warning("Network connectivity test failed, proceeding with caution")
    else:
        logger.info("Network connectivity test passed, proceeding with search")
    
    # Retry logic with exponential backoff
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Search attempt {attempt + 1}/{max_retries} for query: {q}")
            
            # Use YouTube Music search
            search_query = f"ytsearch{limit}:{q}"
            
            # Create a copy of YDL_OPTS with attempt-specific settings
            ydl_opts = YDL_OPTS.copy()
            
            # Optimize timeouts for VPS - shorter, more aggressive
            if attempt > 0:
                ydl_opts['socket_timeout'] = 30 + (attempt * 15)  # Reduced from 60+30
                ydl_opts['retry_sleep'] = 1 + attempt
            
            # Use asyncio.wait_for to enforce timeout at Python level
            def run_ytdlp():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(search_query, download=False)
            
            # Run with a hard timeout - reduced for faster failure detection
            timeout_seconds = 30 + (attempt * 15)  # Reduced from 60+30
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, run_ytdlp),
                timeout=timeout_seconds
            )
                
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
            
            logger.info(f"Search successful on attempt {attempt + 1}, found {len(results)} results")
            return {"results": results}
            
        except asyncio.TimeoutError:
            logger.error(f"Search timeout on attempt {attempt + 1} after {timeout_seconds} seconds")
            
            if attempt < max_retries - 1:
                retry_wait = min(retry_delay, 3)  # Cap retry delay at 3 seconds
                logger.info(f"Retrying in {retry_wait} seconds...")
                await asyncio.sleep(retry_wait)
                retry_delay = min(retry_delay * 1.5, 5)  # Gentler exponential backoff, cap at 5s
            else:
                # Last attempt failed, raise timeout exception
                raise HTTPException(status_code=500, detail=f"Search timed out after {max_retries} attempts. This may be due to SSL handshake issues with YouTube servers.")
        except Exception as e:
            logger.error(f"Search error on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                retry_wait = min(retry_delay, 3)  # Cap retry delay at 3 seconds
                logger.info(f"Retrying in {retry_wait} seconds...")
                await asyncio.sleep(retry_wait)
                retry_delay = min(retry_delay * 1.5, 5)  # Gentler exponential backoff, cap at 5s
            else:
                # Last attempt failed, raise the exception
                raise HTTPException(status_code=500, detail=f"Search failed after {max_retries} attempts: {str(e)}")


@app.get("/api/song/{video_id}")
async def get_song_details(video_id: str):
    """Get details for a specific song"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Get song details attempt {attempt + 1}/{max_retries} for video: {video_id}")
            
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Create a copy of YDL_OPTS with attempt-specific settings
            ydl_opts = YDL_OPTS.copy()
            ydl_opts['extract_flat'] = False  # Need full extraction for details
            
            # Increase timeouts for later attempts
            if attempt > 0:
                ydl_opts['socket_timeout'] = 60 + (attempt * 30)
                ydl_opts['retry_sleep'] = 2 + attempt
            
            # Use asyncio.wait_for to enforce timeout at Python level
            def run_ytdlp():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            # Run with a hard timeout
            timeout_seconds = 60 + (attempt * 30)
            info = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, run_ytdlp),
                timeout=timeout_seconds
            )
            
            if not info:
                raise HTTPException(status_code=404, detail="Video not found")
            
            logger.info(f"Song details successful on attempt {attempt + 1}")
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
            
        except asyncio.TimeoutError:
            logger.error(f"Song details timeout on attempt {attempt + 1} after {timeout_seconds} seconds")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                # Last attempt failed, raise timeout exception
                raise HTTPException(status_code=500, detail=f"Song details timed out after {max_retries} attempts. This may be due to SSL handshake issues with YouTube servers.")
        except Exception as e:
            logger.error(f"Get song details error on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                # Last attempt failed, raise the exception
                raise HTTPException(status_code=500, detail=f"Get song details failed after {max_retries} attempts: {str(e)}")


@app.get("/api/stream/{video_id}")
async def get_stream_url(video_id: str):
    """Get stream URL for a video"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Get stream URL attempt {attempt + 1}/{max_retries} for video: {video_id}")
            
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Create a copy of STREAM_OPTS with attempt-specific settings
            stream_opts = STREAM_OPTS.copy()
            
            # Increase timeouts for later attempts
            if attempt > 0:
                stream_opts['socket_timeout'] = 60 + (attempt * 30)
                stream_opts['retry_sleep'] = 2 + attempt
            
            # Use asyncio.wait_for to enforce timeout at Python level
            def run_ytdlp():
                with yt_dlp.YoutubeDL(stream_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            # Run with a hard timeout
            timeout_seconds = 60 + (attempt * 30)
            info = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, run_ytdlp),
                timeout=timeout_seconds
            )
            
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
            
            logger.info(f"Stream URL successful on attempt {attempt + 1}")
            return {
                "stream_url": best_format,
                "quality": "high",
                "format": "audio"
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Stream URL timeout on attempt {attempt + 1} after {timeout_seconds} seconds")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                # Last attempt failed, raise timeout exception
                raise HTTPException(status_code=500, detail=f"Stream URL timed out after {max_retries} attempts. This may be due to SSL handshake issues with YouTube servers.")
        except Exception as e:
            logger.error(f"Get stream URL error on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                # Last attempt failed, raise the exception
                raise HTTPException(status_code=500, detail=f"Get stream URL failed after {max_retries} attempts: {str(e)}")


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