"""
Similarity matching algorithms for cross-platform content identification.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Any, Tuple, Optional
from difflib import SequenceMatcher
from datetime import timedelta

try:
    from fuzzywuzzy import fuzz
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False
    logging.warning("fuzzywuzzy not available, using basic string matching")

logger = logging.getLogger(__name__)


@dataclass
class SimilarityScore:
    """Represents similarity score between two videos"""
    title_similarity: float = 0.0
    duration_similarity: float = 0.0
    channel_similarity: float = 0.0
    overall_similarity: float = 0.0
    is_duplicate: bool = False
    confidence: float = 0.0


class SimilarityMatcher:
    """Handles similarity detection between video results from different platforms"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Similarity thresholds
        self.title_threshold = self.config.get('title_threshold', 0.85)
        self.duration_threshold = self.config.get('duration_threshold', 0.90)
        self.channel_threshold = self.config.get('channel_threshold', 0.80)
        self.overall_threshold = self.config.get('overall_threshold', 0.80)
        
        # Weights for different similarity components
        self.title_weight = self.config.get('title_weight', 0.50)
        self.duration_weight = self.config.get('duration_weight', 0.30)
        self.channel_weight = self.config.get('channel_weight', 0.20)
        
        # Duration tolerance (seconds)
        self.duration_tolerance_seconds = self.config.get('duration_tolerance_seconds', 10)
        
        # Prepare text normalization patterns
        self._init_normalization_patterns()
    
    def _init_normalization_patterns(self):
        """Initialize text normalization patterns"""
        # Common prefixes/suffixes to remove for better matching
        self.title_cleanup_patterns = [
            r'\[.*?\]',  # Remove [brackets]
            r'\(.*?\)',  # Remove (parentheses) 
            r'【.*?】',   # Remove 【Japanese brackets】
            r'official\s*video',  # Remove "official video"
            r'official\s*music\s*video',  # Remove "official music video"
            r'music\s*video',  # Remove "music video"
            r'full\s*version',  # Remove "full version"
            r'hd|4k|1080p|720p',  # Remove quality indicators
            r'remastered?',  # Remove "remaster"/"remastered"
            r'lyric[s]?\s*video',  # Remove "lyrics video"
            r'audio\s*only',  # Remove "audio only"
            r'ft\.?|feat\.?',  # Remove "ft." or "feat."
        ]
        
        # Channel name normalization patterns
        self.channel_cleanup_patterns = [
            r'official',
            r'music',
            r'records?',
            r'entertainment',
            r'vevo',
            r'channel',
            r'tv',
        ]
    
    def normalize_title(self, title: str) -> str:
        """Normalize title for better comparison"""
        if not title:
            return ""
        
        # Convert to lowercase and strip
        normalized = title.lower().strip()
        
        # Remove common patterns
        for pattern in self.title_cleanup_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        normalized = normalized.strip()
        
        return normalized
    
    def normalize_channel(self, channel: str) -> str:
        """Normalize channel name for better comparison"""
        if not channel:
            return ""
        
        # Convert to lowercase and strip
        normalized = channel.lower().strip()
        
        # Remove common patterns
        for pattern in self.channel_cleanup_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.strip()
        
        return normalized
    
    def parse_duration(self, duration_str: str) -> Optional[int]:
        """Parse duration string to seconds"""
        if not duration_str or duration_str == "Unknown":
            return None
        
        try:
            # Handle different duration formats
            if ':' in duration_str:
                parts = duration_str.split(':')
                if len(parts) == 2:  # MM:SS
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
                elif len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
            else:
                # Assume it's already in seconds
                return int(float(duration_str))
        except (ValueError, TypeError):
            logger.debug(f"Could not parse duration: {duration_str}")
            return None
    
    def calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate title similarity score"""
        if not title1 or not title2:
            return 0.0
        
        # Normalize titles
        norm_title1 = self.normalize_title(title1)
        norm_title2 = self.normalize_title(title2)
        
        if not norm_title1 or not norm_title2:
            return 0.0
        
        # Use fuzzywuzzy if available, otherwise use difflib
        if FUZZYWUZZY_AVAILABLE:
            # Use token_sort_ratio for better results with reordered words
            similarity = fuzz.token_sort_ratio(norm_title1, norm_title2) / 100.0
        else:
            # Fallback to difflib
            similarity = SequenceMatcher(None, norm_title1, norm_title2).ratio()
        
        return min(1.0, max(0.0, similarity))
    
    def calculate_duration_similarity(self, duration1: str, duration2: str) -> float:
        """Calculate duration similarity score"""
        parsed1 = self.parse_duration(duration1)
        parsed2 = self.parse_duration(duration2)
        
        if parsed1 is None or parsed2 is None:
            return 0.5  # Neutral score when duration is unknown
        
        # Calculate absolute difference
        diff = abs(parsed1 - parsed2)
        
        # If within tolerance, consider it a perfect match
        if diff <= self.duration_tolerance_seconds:
            return 1.0
        
        # Otherwise, calculate similarity based on relative difference
        max_duration = max(parsed1, parsed2)
        if max_duration == 0:
            return 1.0
        
        relative_diff = diff / max_duration
        similarity = max(0.0, 1.0 - relative_diff)
        
        return similarity
    
    def calculate_channel_similarity(self, channel1: str, channel2: str) -> float:
        """Calculate channel similarity score"""
        if not channel1 or not channel2:
            return 0.0
        
        # Normalize channel names
        norm_channel1 = self.normalize_channel(channel1)
        norm_channel2 = self.normalize_channel(channel2)
        
        if not norm_channel1 or not norm_channel2:
            return 0.0
        
        # Use fuzzywuzzy if available
        if FUZZYWUZZY_AVAILABLE:
            similarity = fuzz.ratio(norm_channel1, norm_channel2) / 100.0
        else:
            similarity = SequenceMatcher(None, norm_channel1, norm_channel2).ratio()
        
        return min(1.0, max(0.0, similarity))
    
    def calculate_similarity(self, video1: Dict[str, Any], video2: Dict[str, Any]) -> SimilarityScore:
        """Calculate comprehensive similarity score between two videos"""
        
        # Extract relevant fields
        title1 = video1.get('title', '')
        title2 = video2.get('title', '')
        duration1 = video1.get('duration', '')
        duration2 = video2.get('duration', '')
        channel1 = video1.get('channel', '')
        channel2 = video2.get('channel', '')
        
        # Calculate individual similarity scores
        title_sim = self.calculate_title_similarity(title1, title2)
        duration_sim = self.calculate_duration_similarity(duration1, duration2)
        channel_sim = self.calculate_channel_similarity(channel1, channel2)
        
        # Calculate weighted overall similarity
        overall_sim = (
            title_sim * self.title_weight +
            duration_sim * self.duration_weight +
            channel_sim * self.channel_weight
        )
        
        # Determine if it's a duplicate
        is_duplicate = (
            title_sim >= self.title_threshold and
            duration_sim >= self.duration_threshold and
            overall_sim >= self.overall_threshold
        )
        
        # Calculate confidence based on how many criteria are met
        confidence_factors = [
            title_sim >= self.title_threshold,
            duration_sim >= self.duration_threshold,
            channel_sim >= self.channel_threshold,
            overall_sim >= self.overall_threshold
        ]
        confidence = sum(confidence_factors) / len(confidence_factors)
        
        logger.debug(
            f"Similarity calculated: {title1[:30]}... vs {title2[:30]}... "
            f"(title: {title_sim:.2f}, duration: {duration_sim:.2f}, "
            f"channel: {channel_sim:.2f}, overall: {overall_sim:.2f}, "
            f"duplicate: {is_duplicate})"
        )
        
        return SimilarityScore(
            title_similarity=title_sim,
            duration_similarity=duration_sim,
            channel_similarity=channel_sim,
            overall_similarity=overall_sim,
            is_duplicate=is_duplicate,
            confidence=confidence
        )
    
    def find_duplicates(self, videos: List[Dict[str, Any]]) -> List[List[int]]:
        """Find groups of duplicate videos, returning indices"""
        if len(videos) < 2:
            return []
        
        duplicate_groups = []
        processed_indices = set()
        
        for i, video1 in enumerate(videos):
            if i in processed_indices:
                continue
            
            current_group = [i]
            
            for j, video2 in enumerate(videos[i+1:], start=i+1):
                if j in processed_indices:
                    continue
                
                similarity = self.calculate_similarity(video1, video2)
                
                if similarity.is_duplicate:
                    current_group.append(j)
                    processed_indices.add(j)
            
            if len(current_group) > 1:
                duplicate_groups.append(current_group)
                processed_indices.update(current_group)
        
        return duplicate_groups