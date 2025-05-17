import asyncio
from typing import List, Dict, Optional
from platforms.base import VideoPlatform
import re
import logging

logger = logging.getLogger(__name__)

class PeerTubePlatform(VideoPlatform):
    """PeerTube platform implementation - federated video platform"""
    
    def __init__(self, config: Dict):
        super().__init__("peertube", config)
        self.instances = config.get('instances', [])
        self.max_results_per_instance = config.get('max_results_per_instance', 5)
        
        # URL pattern for PeerTube videos
        self.url_pattern = re.compile(r'https?://([^/]+)/videos/watch/([a-f0-9-]+)')
    
    async def search_videos(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search across all configured PeerTube instances"""
        if not self.instances:
            logger.warning("No PeerTube instances configured")
            return []
        
        all_results = []
        tasks = []
        
        # Calculate results per instance
        results_per_instance = min(
            max_results // len(self.instances) + 1,
            self.max_results_per_instance
        )
        
        # Search each instance
        for instance in self.instances:
            task = self._search_instance(instance, query, results_per_instance)
            tasks.append(task)
        
        # Gather results from all instances
        instance_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, results in enumerate(instance_results):
            if isinstance(results, Exception):
                logger.error(f"Error searching {self.instances[i]}: {results}")
            else:
                all_results.extend(results)
        
        # Sort by relevance/views and limit results
        all_results.sort(key=lambda x: x.get('views', 0), reverse=True)
        return all_results[:max_results]
    
    async def _search_instance(self, instance_url: str, query: str, max_results: int) -> List[Dict]:
        """Search a specific PeerTube instance"""
        try:
            url = f"{instance_url}/api/v1/search/videos"
            params = {
                'search': query,
                'count': max_results,
                'sort': '-views'  # Sort by views descending
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 403:
                    logger.warning(f"PeerTube instance {instance_url} returned 403 Forbidden - may require authentication")
                    return []
                elif response.status != 200:
                    logger.error(f"PeerTube search failed for {instance_url}: {response.status}")
                    return []
                
                data = await response.json()
                results = []
                
                for video in data.get('data', []):
                    results.append({
                        'id': video['uuid'],
                        'title': video['name'],
                        'channel': video['channel']['displayName'],
                        'thumbnail': f"{instance_url}{video['thumbnailPath']}",
                        'url': f"{instance_url}/videos/watch/{video['uuid']}",
                        'platform': 'peertube',
                        'instance': instance_url,
                        'description': video.get('description', ''),
                        'duration': video.get('duration'),
                        'views': video.get('views', 0)
                    })
                
                return results
        except Exception as e:
            logger.error(f"Error searching PeerTube instance {instance_url}: {e}")
            return []
    
    async def get_video_details(self, video_id: str) -> Optional[Dict]:
        """Get details for a PeerTube video"""
        # Try to find which instance hosts this video
        for instance in self.instances:
            try:
                url = f"{instance}/api/v1/videos/{video_id}"
                async with self.session.get(url) as response:
                    if response.status == 200:
                        video = await response.json()
                        
                        return {
                            'id': video['uuid'],
                            'title': video['name'],
                            'channel': video['channel']['displayName'],
                            'thumbnail': f"{instance}{video['thumbnailPath']}",
                            'url': f"{instance}/videos/watch/{video['uuid']}",
                            'platform': 'peertube',
                            'instance': instance,
                            'description': video.get('description', ''),
                            'duration': video.get('duration'),
                            'views': video.get('views', 0),
                            'likes': video.get('likes', 0),
                            'dislikes': video.get('dislikes', 0),
                            'publishedAt': video.get('publishedAt')
                        }
            except Exception as e:
                logger.debug(f"Video {video_id} not found on {instance}: {e}")
                continue
        
        return None
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from PeerTube URL"""
        match = self.url_pattern.search(url)
        if match:
            return match.group(2)
        return None
    
    def is_platform_url(self, url: str) -> bool:
        """Check if URL is a PeerTube URL"""
        return bool(self.url_pattern.search(url))
    
    async def get_stream_url(self, video_id: str) -> Optional[str]:
        """Get stream URL for a PeerTube video"""
        # Find which instance hosts this video
        video_details = await self.get_video_details(video_id)
        if not video_details:
            return None
        
        instance = video_details['instance']
        
        try:
            # Get video files
            url = f"{instance}/api/v1/videos/{video_id}"
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                
                video = await response.json()
                
                # Get best quality file
                files = video.get('files', [])
                if not files:
                    return None
                
                # Sort by resolution, get highest
                files.sort(key=lambda x: x.get('resolution', {}).get('id', 0), reverse=True)
                best_file = files[0]
                
                return best_file['fileUrl']
        except Exception as e:
            logger.error(f"Error getting stream URL for PeerTube video {video_id}: {e}")
            return None