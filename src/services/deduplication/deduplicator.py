"""
Main cross-platform deduplication engine for Robustty.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .similarity_matcher import SimilarityMatcher, SimilarityScore
from .quality_scorer import QualityScorer, QualityMetrics
from .content_fingerprinter import ContentFingerprinter

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationResult:
    """Result of deduplication process"""
    deduplicated_videos: List[Dict[str, Any]]
    duplicate_groups: List[List[Dict[str, Any]]]
    removed_duplicates: List[Dict[str, Any]]
    deduplication_stats: Dict[str, Any]


class CrossPlatformDeduplicator:
    """Main deduplication engine that combines similarity matching, quality scoring, and content fingerprinting"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize components
        self.similarity_matcher = SimilarityMatcher(self.config.get('similarity', {}))
        self.quality_scorer = QualityScorer(self.config.get('quality_scoring', {}))
        self.content_fingerprinter = ContentFingerprinter(self.config.get('fingerprinting', {}))
        
        # Deduplication settings
        self.enabled = self.config.get('enabled', True)
        self.preserve_platform_diversity = self.config.get('preserve_platform_diversity', True)
        self.max_duplicates_per_group = self.config.get('max_duplicates_per_group', 5)
        self.min_similarity_threshold = self.config.get('min_similarity_threshold', 0.80)
        
        # Performance settings
        self.max_comparison_pairs = self.config.get('max_comparison_pairs', 1000)
        self.enable_fingerprint_optimization = self.config.get('enable_fingerprint_optimization', True)
    
    def deduplicate_search_results(self, platform_results: Dict[str, List[Dict[str, Any]]]) -> DeduplicationResult:
        """Main deduplication method for search results across platforms"""
        if not self.enabled:
            # Return original results if deduplication is disabled
            all_videos = []
            for platform, videos in platform_results.items():
                for video in videos:
                    video['platform'] = platform
                    all_videos.append(video)
            
            return DeduplicationResult(
                deduplicated_videos=all_videos,
                duplicate_groups=[],
                removed_duplicates=[],
                deduplication_stats={'enabled': False}
            )
        
        logger.info("Starting cross-platform deduplication")
        start_time = self._get_timestamp()
        
        # Flatten and tag videos with platform info
        all_videos = []
        for platform, videos in platform_results.items():
            for video in videos:
                video_copy = video.copy()
                video_copy['platform'] = platform
                all_videos.append(video_copy)
        
        original_count = len(all_videos)
        logger.debug(f"Processing {original_count} videos across {len(platform_results)} platforms")
        
        # Performance check: limit comparisons for very large result sets
        if len(all_videos) > 50:  # Arbitrary threshold
            logger.warning(f"Large result set ({len(all_videos)} videos), using optimized deduplication")
            return self._optimized_deduplication(all_videos, platform_results)
        
        # Find duplicate groups
        duplicate_groups = self._find_duplicate_groups(all_videos)
        
        # Select best videos from each group
        deduplicated_videos, removed_duplicates = self._select_best_from_groups(
            all_videos, duplicate_groups
        )
        
        # Generate statistics
        end_time = self._get_timestamp()
        stats = {
            'enabled': True,
            'original_count': original_count,
            'deduplicated_count': len(deduplicated_videos),
            'removed_count': len(removed_duplicates),
            'duplicate_groups_found': len(duplicate_groups),
            'processing_time_ms': int((end_time - start_time) * 1000),
            'platforms_processed': list(platform_results.keys()),
        }
        
        logger.info(
            f"Deduplication complete: {original_count} -> {len(deduplicated_videos)} videos "
            f"({len(removed_duplicates)} duplicates removed, {len(duplicate_groups)} groups)"
        )
        
        return DeduplicationResult(
            deduplicated_videos=deduplicated_videos,
            duplicate_groups=[[all_videos[i] for i in group] for group in duplicate_groups],
            removed_duplicates=removed_duplicates,
            deduplication_stats=stats
        )
    
    def _optimized_deduplication(self, all_videos: List[Dict[str, Any]], 
                                platform_results: Dict[str, List[Dict[str, Any]]]) -> DeduplicationResult:
        """Optimized deduplication for large result sets using fingerprints"""
        logger.debug("Using fingerprint-based optimization for large dataset")
        
        # Use content fingerprinting for initial grouping
        if self.enable_fingerprint_optimization:
            content_groups = self.content_fingerprinter.identify_cross_platform_content(platform_results)
            
            duplicate_groups_with_videos = []
            removed_duplicates = []
            deduplicated_videos = all_videos.copy()
            
            for fingerprint, videos in content_groups.items():
                if len(videos) > 1:
                    # Use quality scorer to pick the best one
                    best_video = self.quality_scorer.select_best_from_duplicates(videos)
                    
                    # Remove others from deduplicated list
                    videos_to_remove = [v for v in videos if v != best_video]
                    for video_to_remove in videos_to_remove:
                        if video_to_remove in deduplicated_videos:
                            deduplicated_videos.remove(video_to_remove)
                            removed_duplicates.append(video_to_remove)
                    
                    duplicate_groups_with_videos.append(videos)
            
            stats = {
                'enabled': True,
                'optimized': True,
                'fingerprint_based': True,
                'original_count': len(all_videos),
                'deduplicated_count': len(deduplicated_videos),
                'removed_count': len(removed_duplicates),
                'duplicate_groups_found': len(duplicate_groups_with_videos),
            }
            
            return DeduplicationResult(
                deduplicated_videos=deduplicated_videos,
                duplicate_groups=duplicate_groups_with_videos,
                removed_duplicates=removed_duplicates,
                deduplication_stats=stats
            )
        else:
            # Fallback: just use quality ranking without deduplication
            ranked_videos = self.quality_scorer.rank_videos(all_videos)
            
            return DeduplicationResult(
                deduplicated_videos=ranked_videos,
                duplicate_groups=[],
                removed_duplicates=[],
                deduplication_stats={
                    'enabled': True,
                    'optimized': True,
                    'quality_ranked_only': True,
                    'original_count': len(all_videos),
                    'deduplicated_count': len(ranked_videos),
                }
            )
    
    def _find_duplicate_groups(self, videos: List[Dict[str, Any]]) -> List[List[int]]:
        """Find groups of duplicate videos"""
        if len(videos) < 2:
            return []
        
        duplicate_groups = []
        processed_indices = set()
        
        for i, video1 in enumerate(videos):
            if i in processed_indices:
                continue
            
            current_group = [i]
            
            # Compare with all subsequent videos
            for j in range(i + 1, len(videos)):
                if j in processed_indices:
                    continue
                
                video2 = videos[j]
                
                # Skip if same platform and preserve_platform_diversity is enabled
                if (self.preserve_platform_diversity and 
                    video1.get('platform') == video2.get('platform')):
                    continue
                
                # Calculate similarity
                similarity = self.similarity_matcher.calculate_similarity(video1, video2)
                
                if similarity.is_duplicate and similarity.overall_similarity >= self.min_similarity_threshold:
                    current_group.append(j)
                    processed_indices.add(j)
                    
                    # Limit group size for performance
                    if len(current_group) >= self.max_duplicates_per_group:
                        break
            
            # Only consider it a duplicate group if it has more than one video
            if len(current_group) > 1:
                duplicate_groups.append(current_group)
                processed_indices.update(current_group)
        
        return duplicate_groups
    
    def _select_best_from_groups(self, all_videos: List[Dict[str, Any]], 
                                duplicate_groups: List[List[int]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Select the best video from each duplicate group"""
        deduplicated_videos = []
        removed_duplicates = []
        processed_indices = set()
        
        # Process duplicate groups
        for group_indices in duplicate_groups:
            group_videos = [all_videos[i] for i in group_indices]
            
            # Select the best video from this group
            best_video = self.quality_scorer.select_best_from_duplicates(group_videos)
            
            # Add best video to deduplicated list
            deduplicated_videos.append(best_video)
            
            # Add others to removed list
            for video in group_videos:
                if video != best_video:
                    removed_duplicates.append(video)
            
            # Mark all indices as processed
            processed_indices.update(group_indices)
        
        # Add non-duplicate videos
        for i, video in enumerate(all_videos):
            if i not in processed_indices:
                deduplicated_videos.append(video)
        
        return deduplicated_videos, removed_duplicates
    
    def get_deduplication_summary(self, result: DeduplicationResult) -> str:
        """Generate a human-readable summary of deduplication results"""
        stats = result.deduplication_stats
        
        if not stats.get('enabled', False):
            return "⚪ Deduplication disabled"
        
        original_count = stats.get('original_count', 0)
        final_count = stats.get('deduplicated_count', 0)
        removed_count = stats.get('removed_count', 0)
        groups_count = stats.get('duplicate_groups_found', 0)
        
        if removed_count == 0:
            return f"✅ No duplicates found ({original_count} unique results)"
        
        efficiency_percent = (removed_count / original_count * 100) if original_count > 0 else 0
        
        summary_parts = [
            f"🔄 Deduplication: {original_count} → {final_count} results",
            f"({removed_count} duplicates removed, {efficiency_percent:.1f}% reduction)",
        ]
        
        if groups_count > 0:
            summary_parts.append(f"{groups_count} duplicate groups found")
        
        if stats.get('optimized', False):
            if stats.get('fingerprint_based', False):
                summary_parts.append("(fingerprint optimized)")
            else:
                summary_parts.append("(quality ranked)")
        
        return " ".join(summary_parts)
    
    def _get_timestamp(self) -> float:
        """Get current timestamp for performance measurement"""
        import time
        return time.time()
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update configuration dynamically"""
        self.config.update(new_config)
        
        # Update component configs
        if 'similarity' in new_config:
            self.similarity_matcher = SimilarityMatcher(new_config['similarity'])
        if 'quality_scoring' in new_config:
            self.quality_scorer = QualityScorer(new_config['quality_scoring'])
        if 'fingerprinting' in new_config:
            self.content_fingerprinter = ContentFingerprinter(new_config['fingerprinting'])
        
        # Update main settings
        self.enabled = new_config.get('enabled', self.enabled)
        self.preserve_platform_diversity = new_config.get('preserve_platform_diversity', self.preserve_platform_diversity)
        self.min_similarity_threshold = new_config.get('min_similarity_threshold', self.min_similarity_threshold)
        
        logger.info("Deduplication configuration updated")
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        return {
            'enabled': self.enabled,
            'preserve_platform_diversity': self.preserve_platform_diversity,
            'max_duplicates_per_group': self.max_duplicates_per_group,
            'min_similarity_threshold': self.min_similarity_threshold,
            'max_comparison_pairs': self.max_comparison_pairs,
            'enable_fingerprint_optimization': self.enable_fingerprint_optimization,
        }