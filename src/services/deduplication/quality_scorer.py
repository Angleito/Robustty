"""
Quality scoring system for ranking search results across platforms.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Quality metrics for a video result"""
    platform_score: float = 0.0
    metadata_completeness: float = 0.0
    content_quality_indicators: float = 0.0
    channel_authority: float = 0.0
    engagement_score: float = 0.0
    freshness_score: float = 0.0
    overall_score: float = 0.0


class QualityScorer:
    """Scores video results for quality ranking"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Platform reliability weights (higher = more reliable)
        self.platform_weights = self.config.get('platform_weights', {
            'youtube': 1.0,      # Highest reliability, best metadata
            'odysee': 0.8,       # Good alternative platform
            'peertube': 0.7,     # Decentralized, varies by instance
            'rumble': 0.6,       # Newer platform, less metadata
        })
        
        # Quality scoring weights
        self.scoring_weights = self.config.get('scoring_weights', {
            'platform': 0.25,     # Platform reliability
            'metadata': 0.20,     # Metadata completeness
            'content': 0.20,      # Content quality indicators
            'channel': 0.15,      # Channel authority
            'engagement': 0.15,   # Views, likes, etc.
            'freshness': 0.05,    # How recent the content is
        })
        
        # Quality indicators for content
        self.quality_indicators = {
            'positive': [
                r'\bofficial\b',
                r'\bhd\b', r'\b4k\b', r'\b1080p\b', r'\b720p\b',
                r'\bmusic\s*video\b',
                r'\bremaster(ed)?\b',
                r'\bvevo\b',
                r'\brecords?\b',
                r'\bentertainment\b',
            ],
            'negative': [
                r'\bcover\b', r'\bkaraoke\b', r'\blyrics?\s*only\b',
                r'\bfan\s*made\b', r'\bunofficial\b',
                r'\blow\s*quality\b', r'\bpotato\s*quality\b',
                r'\bcam\s*rip\b', r'\bbootleg\b',
            ]
        }
        
        # Channel authority indicators
        self.authority_indicators = {
            'high': [
                r'\bvevo\b', r'\bofficial\b', r'\brecords?\b',
                r'\bmusic\b', r'\bentertainment\b', r'\btv\b',
                r'\bmedia\b', r'\bstudios?\b',
            ],
            'medium': [
                r'\bchannel\b', r'\bnetwork\b', r'\bproductions?\b',
            ],
            'verified_patterns': [
                r'✓', r'verified', r'check',  # Verification indicators
            ]
        }
    
    def calculate_platform_score(self, platform: str) -> float:
        """Calculate platform reliability score"""
        return self.platform_weights.get(platform.lower(), 0.5)
    
    def calculate_metadata_completeness(self, video: Dict[str, Any]) -> float:
        """Calculate metadata completeness score"""
        required_fields = ['title', 'channel', 'duration', 'url']
        optional_fields = ['description', 'thumbnail', 'views', 'published']
        
        required_score = 0
        for field in required_fields:
            if video.get(field) and str(video[field]).strip() not in ['', 'Unknown', 'N/A']:
                required_score += 1
        
        optional_score = 0
        for field in optional_fields:
            if video.get(field) and str(video[field]).strip() not in ['', 'Unknown', 'N/A']:
                optional_score += 1
        
        # Required fields are weighted more heavily
        total_score = (required_score / len(required_fields)) * 0.7
        total_score += (optional_score / len(optional_fields)) * 0.3
        
        return min(1.0, total_score)
    
    def calculate_content_quality_indicators(self, video: Dict[str, Any]) -> float:
        """Calculate content quality based on title and description indicators"""
        title = video.get('title', '').lower()
        description = video.get('description', '').lower()
        content_text = f"{title} {description}"
        
        positive_score = 0
        negative_score = 0
        
        # Check for positive indicators
        for pattern in self.quality_indicators['positive']:
            if re.search(pattern, content_text, re.IGNORECASE):
                positive_score += 1
        
        # Check for negative indicators
        for pattern in self.quality_indicators['negative']:
            if re.search(pattern, content_text, re.IGNORECASE):
                negative_score += 1
        
        # Normalize scores (max 3 positive, max 2 negative to avoid over-penalization)
        positive_normalized = min(positive_score, 3) / 3.0
        negative_normalized = min(negative_score, 2) / 2.0
        
        # Calculate final score (0.5 baseline, adjusted by indicators)
        score = 0.5 + positive_normalized * 0.4 - negative_normalized * 0.3
        
        return max(0.0, min(1.0, score))
    
    def calculate_channel_authority(self, video: Dict[str, Any]) -> float:
        """Calculate channel authority score"""
        channel = video.get('channel', '').lower()
        
        if not channel:
            return 0.0
        
        authority_score = 0.0
        
        # Check for high authority indicators
        for pattern in self.authority_indicators['high']:
            if re.search(pattern, channel, re.IGNORECASE):
                authority_score = max(authority_score, 0.9)
        
        # Check for medium authority indicators
        for pattern in self.authority_indicators['medium']:
            if re.search(pattern, channel, re.IGNORECASE):
                authority_score = max(authority_score, 0.6)
        
        # Check for verification indicators
        for pattern in self.authority_indicators['verified_patterns']:
            if re.search(pattern, channel, re.IGNORECASE):
                authority_score = min(1.0, authority_score + 0.2)
        
        # Default score for unknown channels
        if authority_score == 0.0:
            authority_score = 0.3
        
        return authority_score
    
    def calculate_engagement_score(self, video: Dict[str, Any]) -> float:
        """Calculate engagement score based on views and other metrics"""
        views_raw = video.get('view_count_raw', 0)
        
        if not isinstance(views_raw, (int, float)) or views_raw <= 0:
            return 0.3  # Neutral score for unknown views
        
        # Logarithmic scoring for views (to handle wide range)
        import math
        
        # Score ranges: 
        # 1K views = 0.3, 10K = 0.4, 100K = 0.5, 1M = 0.6, 10M = 0.7, 100M+ = 0.8
        if views_raw < 1000:
            score = 0.2
        elif views_raw < 10000:
            score = 0.3
        elif views_raw < 100000:
            score = 0.4
        elif views_raw < 1000000:
            score = 0.5
        elif views_raw < 10000000:
            score = 0.6
        elif views_raw < 100000000:
            score = 0.7
        else:
            score = 0.8
        
        return score
    
    def calculate_freshness_score(self, video: Dict[str, Any]) -> float:
        """Calculate freshness score based on publication date"""
        published = video.get('published', '')
        
        if not published or published in ['Unknown', 'N/A']:
            return 0.5  # Neutral score for unknown dates
        
        try:
            # Try to parse relative dates like "2 days ago", "1 week ago"
            if 'ago' in published.lower():
                if 'hour' in published or 'minute' in published:
                    return 1.0  # Very fresh
                elif 'day' in published:
                    # Extract number of days
                    import re
                    match = re.search(r'(\d+)\s*day', published)
                    if match:
                        days = int(match.group(1))
                        if days <= 7:
                            return 0.9
                        elif days <= 30:
                            return 0.7
                        elif days <= 90:
                            return 0.5
                        else:
                            return 0.3
                elif 'week' in published:
                    return 0.7
                elif 'month' in published:
                    return 0.5
                elif 'year' in published:
                    return 0.3
            
            # For absolute dates, we'd need more complex parsing
            # For now, return neutral score
            return 0.5
            
        except Exception:
            return 0.5
    
    def calculate_quality_score(self, video: Dict[str, Any]) -> QualityMetrics:
        """Calculate comprehensive quality score for a video"""
        platform = video.get('platform', '').lower()
        
        # Calculate individual scores
        platform_score = self.calculate_platform_score(platform)
        metadata_score = self.calculate_metadata_completeness(video)
        content_score = self.calculate_content_quality_indicators(video)
        channel_score = self.calculate_channel_authority(video)
        engagement_score = self.calculate_engagement_score(video)
        freshness_score = self.calculate_freshness_score(video)
        
        # Calculate weighted overall score
        overall_score = (
            platform_score * self.scoring_weights['platform'] +
            metadata_score * self.scoring_weights['metadata'] +
            content_score * self.scoring_weights['content'] +
            channel_score * self.scoring_weights['channel'] +
            engagement_score * self.scoring_weights['engagement'] +
            freshness_score * self.scoring_weights['freshness']
        )
        
        logger.debug(
            f"Quality score for {video.get('title', 'Unknown')[:30]}... "
            f"(platform: {platform_score:.2f}, metadata: {metadata_score:.2f}, "
            f"content: {content_score:.2f}, channel: {channel_score:.2f}, "
            f"engagement: {engagement_score:.2f}, freshness: {freshness_score:.2f}, "
            f"overall: {overall_score:.2f})"
        )
        
        return QualityMetrics(
            platform_score=platform_score,
            metadata_completeness=metadata_score,
            content_quality_indicators=content_score,
            channel_authority=channel_score,
            engagement_score=engagement_score,
            freshness_score=freshness_score,
            overall_score=overall_score
        )
    
    def rank_videos(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank videos by quality score (highest first)"""
        if not videos:
            return videos
        
        # Calculate quality scores and add to videos
        scored_videos = []
        for video in videos:
            quality_metrics = self.calculate_quality_score(video)
            video_copy = video.copy()
            video_copy['_quality_score'] = quality_metrics.overall_score
            video_copy['_quality_metrics'] = quality_metrics
            scored_videos.append(video_copy)
        
        # Sort by quality score (descending)
        ranked_videos = sorted(
            scored_videos, 
            key=lambda v: v['_quality_score'], 
            reverse=True
        )
        
        return ranked_videos
    
    def select_best_from_duplicates(self, duplicate_videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the best video from a group of duplicates"""
        if not duplicate_videos:
            return None
        
        if len(duplicate_videos) == 1:
            return duplicate_videos[0]
        
        # Rank the duplicates and return the best one
        ranked = self.rank_videos(duplicate_videos)
        best_video = ranked[0]
        
        logger.debug(
            f"Selected best duplicate: {best_video.get('title', 'Unknown')[:30]}... "
            f"from {best_video.get('platform', 'unknown')} "
            f"(score: {best_video.get('_quality_score', 0):.2f})"
        )
        
        return best_video