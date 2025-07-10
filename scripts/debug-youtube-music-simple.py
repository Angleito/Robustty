#!/usr/bin/env python3
"""
Simple debug script to test yt-dlp in the YouTube Music container
"""

import yt_dlp
import socket
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_dns():
    """Test DNS resolution"""
    try:
        ip = socket.gethostbyname('www.youtube.com')
        logger.info(f"DNS resolution successful: www.youtube.com -> {ip}")
        return True
    except Exception as e:
        logger.error(f"DNS resolution failed: {e}")
        return False

def test_ytdlp_simple():
    """Test yt-dlp with simple configuration"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'socket_timeout': 30,
            'retries': 1,
            'fragment_retries': 1,
            'user_agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
            'force_ipv4': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Testing yt-dlp with simple search...")
            result = ydl.extract_info("ytsearch1:test", download=False)
            
        if result and 'entries' in result:
            logger.info(f"yt-dlp test successful: found {len(result['entries'])} results")
            return True
        else:
            logger.error("yt-dlp test failed: no results")
            return False
    except Exception as e:
        logger.error(f"yt-dlp test failed: {e}")
        return False

def test_ytdlp_with_cookies():
    """Test yt-dlp with cookies"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'socket_timeout': 30,
            'retries': 1,
            'fragment_retries': 1,
            'user_agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
            'force_ipv4': True,
            'cookiefile': '/app/cookies/youtube_cookies.txt',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Testing yt-dlp with cookies...")
            result = ydl.extract_info("ytsearch1:test", download=False)
            
        if result and 'entries' in result:
            logger.info(f"yt-dlp with cookies test successful: found {len(result['entries'])} results")
            return True
        else:
            logger.error("yt-dlp with cookies test failed: no results")
            return False
    except Exception as e:
        logger.error(f"yt-dlp with cookies test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting YouTube Music debug tests...")
    
    # Test DNS
    logger.info("=== Testing DNS Resolution ===")
    dns_ok = test_dns()
    
    # Test yt-dlp simple
    logger.info("=== Testing yt-dlp Simple ===")
    ytdlp_simple_ok = test_ytdlp_simple()
    
    # Test yt-dlp with cookies
    logger.info("=== Testing yt-dlp with Cookies ===")
    ytdlp_cookies_ok = test_ytdlp_with_cookies()
    
    # Summary
    logger.info("=== Test Summary ===")
    logger.info(f"DNS Resolution: {'PASS' if dns_ok else 'FAIL'}")
    logger.info(f"yt-dlp Simple: {'PASS' if ytdlp_simple_ok else 'FAIL'}")
    logger.info(f"yt-dlp with Cookies: {'PASS' if ytdlp_cookies_ok else 'FAIL'}")
    
    if dns_ok and (ytdlp_simple_ok or ytdlp_cookies_ok):
        logger.info("Overall: PASS - Basic functionality works")
    else:
        logger.error("Overall: FAIL - Core functionality broken")