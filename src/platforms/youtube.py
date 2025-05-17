import re
from typing import List, Dict, Optional
from .base import VideoPlatform
from googleapiclient.discovery import build
import logging

logger = logging.getLogger(__name__)

class YouTubePlatform(VideoPlatform):
    """YouTube platform implementation"""
    
    def __init__(self, config: Dict):
        super().__init__("youtube", config)
        self.api_key = config.get('api_key')
        self.youtube = None
        
        # URL patterns for YouTube
        self.url_patterns = [
            re.compile(r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)'),
            re.compile(r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]+)'),
            re.compile(r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]+)'),
        ]
    
    async def initialize(self):
        """Initialize YouTube API client"""
        await super().initialize()
        if self.api_key:
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        else:
            logger.warning("YouTube API key not provided")
    
    async def search_videos(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search YouTube videos"""
        if not self.youtube:
            return []
        
        try:
            request = self.youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=max_results
            )
            response = request.execute()
            
            results = []
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                snippet = item['snippet']
                
                results.append({
                    'id': video_id,
                    'title': snippet['title'],
                    'channel': snippet['channelTitle'],
                    'thumbnail': snippet['thumbnails']['high']['url'],
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'platform': 'youtube',
                    'description': snippet.get('description', '')
                })
            
            return results
        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            return []
    
    async def get_video_details(self, video_id: str) -> Optional[Dict]:
        """Get detailed information about a video"""
        if not self.youtube:
            return None
        
        try:
            request = self.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=video_id
            )
            response = request.execute()
            
            if not response.get('items'):
                return None
            
            item = response['items'][0]
            snippet = item['snippet']
            
            return {
                'id': video_id,
                'title': snippet['title'],
                'channel': snippet['channelTitle'],
                'thumbnail': snippet['thumbnails']['high']['url'],
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'platform': 'youtube',
                'description': snippet.get('description', ''),
                'duration': item['contentDetails']['duration'],
                'views': item['statistics'].get('viewCount', 0)
            }
        except Exception as e:
            logger.error(f"YouTube video details error: {e}")
            return None
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        for pattern in self.url_patterns:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None
    
    def is_platform_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL"""
        return any(pattern.search(url) for pattern in self.url_patterns)
    
    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL (delegated to stream service)"""
        # This will be handled by the yt-dlp stream service
        return f"http://stream-service:5000/stream/youtube/{video_id}"