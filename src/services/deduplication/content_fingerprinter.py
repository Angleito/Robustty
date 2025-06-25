"""
Content fingerprinting for cross-platform content identification.
"""

import logging
import hashlib
import re
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ContentFingerprinter:
    """Creates content fingerprints for cross-platform identification"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Known cross-platform content patterns
        self.known_patterns = {
            'youtube_to_others': {
                # Maps YouTube video patterns to potential identifiers on other platforms
                'music_videos': [
                    r'(.*?)\s*-\s*(.*?)\s*\(official\s*music\s*video\)',
                    r'(.*?)\s*-\s*(.*?)\s*official\s*video',
                    r'(.*?)\s*-\s*(.*?)\s*music\s*video',
                ],
                'artist_songs': [
                    r'(.*?)\s*-\s*(.*?)(?:\s*\(.*?\))?$',  # Artist - Song pattern
                    r'(.*?):\s*(.*?)(?:\s*\(.*?\))?$',     # Artist: Song pattern
                ]
            }
        }
        
        # Common content identifiers across platforms
        self.cross_platform_indicators = [
            'vevo',      # VEVO content appears on multiple platforms
            'records',   # Record label content
            'music',     # Music content
            'official',  # Official content
        ]
    
    def normalize_for_fingerprint(self, text: str) -> str:
        """Normalize text for fingerprint generation"""
        if not text:
            return ""
        
        # Convert to lowercase
        normalized = text.lower().strip()
        
        # Remove common variations that don't affect content identity
        replacements = [
            (r'\s*\(official\s*music\s*video\)\s*', ''),
            (r'\s*\(official\s*video\)\s*', ''),
            (r'\s*\(music\s*video\)\s*', ''),
            (r'\s*\(official\)\s*', ''),
            (r'\s*\[.*?\]\s*', ''),  # Remove [brackets]
            (r'\s*【.*?】\s*', ''),   # Remove Japanese brackets
            (r'\s*music\s*video\s*', ''),
            (r'\s*official\s*', ''),
            (r'\s*hd\s*', ''), (r'\s*4k\s*', ''), (r'\s*1080p\s*', ''), (r'\s*720p\s*', ''),
            (r'\s*remaster(ed)?\s*', ''),
            (r'\s*full\s*version\s*', ''),
            (r'\s*audio\s*only\s*', ''),
            (r'\s*lyric[s]?\s*video\s*', ''),
        ]
        
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Remove punctuation except hyphens and colons (important for artist-song separation)
        normalized = re.sub(r'[^\w\s\-:]', '', normalized)
        
        return normalized
    
    def extract_artist_song(self, title: str) -> Optional[Dict[str, str]]:
        """Extract artist and song from title"""
        normalized_title = self.normalize_for_fingerprint(title)
        
        # Try common patterns
        patterns = [
            r'^(.+?)\s*-\s*(.+)$',  # Artist - Song
            r'^(.+?):\s*(.+)$',     # Artist: Song
            r'^(.+?)\s+by\s+(.+)$', # Song by Artist (reverse)
        ]
        
        for pattern in patterns:
            match = re.match(pattern, normalized_title, re.IGNORECASE)
            if match:
                if 'by' in pattern:
                    # Reverse order for "Song by Artist" pattern
                    return {
                        'artist': match.group(2).strip(),
                        'song': match.group(1).strip()
                    }
                else:
                    return {
                        'artist': match.group(1).strip(),
                        'song': match.group(2).strip()
                    }
        
        return None
    
    def generate_content_fingerprint(self, video: Dict[str, Any]) -> str:
        """Generate a content fingerprint for cross-platform matching"""
        title = video.get('title', '')
        channel = video.get('channel', '')
        duration = video.get('duration', '')
        
        # Normalize inputs
        norm_title = self.normalize_for_fingerprint(title)
        norm_channel = self.normalize_for_fingerprint(channel)
        
        # Try to extract structured data
        artist_song = self.extract_artist_song(title)
        
        if artist_song:
            # Use structured artist-song format for fingerprint
            fingerprint_base = f"{artist_song['artist']}|{artist_song['song']}"
        else:
            # Use normalized title
            fingerprint_base = norm_title
        
        # Add duration if available (helps with matching)
        if duration and duration != "Unknown":
            # Normalize duration format
            try:
                if ':' in duration:
                    parts = duration.split(':')
                    if len(parts) == 2:  # MM:SS
                        total_seconds = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:  # HH:MM:SS
                        total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    else:
                        total_seconds = 0
                else:
                    total_seconds = int(float(duration))
                
                # Round to nearest 10 seconds for tolerance
                rounded_duration = round(total_seconds / 10) * 10
                fingerprint_base += f"|{rounded_duration}s"
            except (ValueError, TypeError):
                pass
        
        # Generate hash for compact representation
        fingerprint_hash = hashlib.md5(fingerprint_base.encode('utf-8')).hexdigest()[:16]
        
        logger.debug(f"Generated fingerprint for '{title}': {fingerprint_base} -> {fingerprint_hash}")
        
        return fingerprint_hash
    
    def generate_alternative_fingerprints(self, video: Dict[str, Any]) -> List[str]:
        """Generate alternative fingerprints for the same content"""
        title = video.get('title', '')
        fingerprints = []
        
        # Main fingerprint
        main_fingerprint = self.generate_content_fingerprint(video)
        fingerprints.append(main_fingerprint)
        
        # Try different normalization approaches
        variations = [
            # Remove featuring artists
            re.sub(r'\s*ft\.?\s+.*?(?=\s|$)', '', title, flags=re.IGNORECASE),
            re.sub(r'\s*feat\.?\s+.*?(?=\s|$)', '', title, flags=re.IGNORECASE),
            re.sub(r'\s*featuring\s+.*?(?=\s|$)', '', title, flags=re.IGNORECASE),
            
            # Remove remix/version indicators
            re.sub(r'\s*\(.*?remix.*?\)', '', title, flags=re.IGNORECASE),
            re.sub(r'\s*\(.*?version.*?\)', '', title, flags=re.IGNORECASE),
            re.sub(r'\s*\(.*?edit.*?\)', '', title, flags=re.IGNORECASE),
        ]
        
        for variation in variations:
            if variation != title:  # Only if different from original
                variation_video = video.copy()
                variation_video['title'] = variation
                fingerprint = self.generate_content_fingerprint(variation_video)
                if fingerprint not in fingerprints:
                    fingerprints.append(fingerprint)
        
        return fingerprints
    
    def find_potential_matches(self, target_video: Dict[str, Any], 
                              candidate_videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find potential cross-platform matches using fingerprints"""
        target_fingerprints = set(self.generate_alternative_fingerprints(target_video))
        matches = []
        
        for candidate in candidate_videos:
            # Skip if same platform
            if candidate.get('platform') == target_video.get('platform'):
                continue
            
            candidate_fingerprints = set(self.generate_alternative_fingerprints(candidate))
            
            # Check for fingerprint overlap
            if target_fingerprints.intersection(candidate_fingerprints):
                matches.append(candidate)
        
        return matches
    
    def build_content_database(self, all_videos: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Build a content database indexed by fingerprints"""
        content_db = {}
        
        for video in all_videos:
            fingerprints = self.generate_alternative_fingerprints(video)
            
            for fingerprint in fingerprints:
                if fingerprint not in content_db:
                    content_db[fingerprint] = []
                content_db[fingerprint].append(video)
        
        return content_db
    
    def identify_cross_platform_content(self, videos_by_platform: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """Identify content that appears across multiple platforms"""
        # Flatten all videos
        all_videos = []
        for platform, videos in videos_by_platform.items():
            for video in videos:
                video['platform'] = platform
                all_videos.append(video)
        
        # Build content database
        content_db = self.build_content_database(all_videos)
        
        # Find cross-platform content
        cross_platform_content = {}
        
        for fingerprint, videos in content_db.items():
            if len(videos) > 1:
                # Check if videos are from different platforms
                platforms = set(video.get('platform') for video in videos)
                if len(platforms) > 1:
                    cross_platform_content[fingerprint] = videos
        
        logger.info(f"Identified {len(cross_platform_content)} cross-platform content groups")
        
        return cross_platform_content