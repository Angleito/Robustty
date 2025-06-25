"""
Cross-platform result deduplication system for Robustty.

This module provides intelligent deduplication of search results across
different video platforms, using similarity matching and quality scoring
to eliminate duplicates while preserving the best available results.
"""

from .deduplicator import CrossPlatformDeduplicator
from .similarity_matcher import SimilarityMatcher, SimilarityScore
from .quality_scorer import QualityScorer, QualityMetrics
from .content_fingerprinter import ContentFingerprinter

__all__ = [
    'CrossPlatformDeduplicator',
    'SimilarityMatcher', 
    'SimilarityScore',
    'QualityScorer',
    'QualityMetrics',
    'ContentFingerprinter'
]