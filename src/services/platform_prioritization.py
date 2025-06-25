"""
Dynamic platform prioritization system for Robustty.

This module provides intelligent platform ordering based on real-time performance
metrics, health status, and configurable scoring strategies.
"""

import logging
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from threading import Lock

from src.services.health_monitor import ConnectionStatus

logger = logging.getLogger(__name__)


class PrioritizationStrategy(Enum):
    """Available prioritization strategies"""
    BALANCED = "balanced"              # Balance all metrics (30% response, 40% reliability, 30% success)
    SPEED_FIRST = "speed_first"        # Prioritize fastest response times (70% response time)
    RELIABILITY_FIRST = "reliability_first"  # Prioritize most reliable platforms (70% reliability)
    SUCCESS_RATE_FIRST = "success_rate_first"  # Prioritize highest success rates (70% success rate)
    ADAPTIVE = "adaptive"              # Dynamically adjust based on current conditions


@dataclass
class PlatformMetrics:
    """Performance metrics for a platform"""
    # Response time metrics
    avg_response_time: float = 0.0
    response_time_samples: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Success/failure tracking
    total_requests: int = 0
    successful_requests: int = 0
    consecutive_failures: int = 0
    
    # Health integration
    current_health: ConnectionStatus = ConnectionStatus.UNKNOWN
    health_score: float = 1.0
    
    # Performance scores (0.0 to 1.0)
    response_time_score: float = 1.0
    reliability_score: float = 1.0
    success_rate_score: float = 1.0
    overall_score: float = 1.0
    
    # Timestamps
    last_updated: float = field(default_factory=time.time)
    last_failure_time: float = 0.0


class PlatformPrioritizationManager:
    """Manages dynamic platform prioritization based on performance metrics"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Configuration
        self.enabled = self.config.get('enabled', True)
        self.strategy = PrioritizationStrategy(self.config.get('strategy', 'balanced'))
        self.update_interval = self.config.get('update_interval', 60)  # seconds
        self.min_samples = self.config.get('min_samples', 5)
        self.failure_penalty_duration = self.config.get('failure_penalty_duration', 300)  # 5 minutes
        self.response_time_threshold = self.config.get('response_time_threshold', 5.0)  # seconds
        
        # Default platform order (fallback)
        self.default_order = self.config.get('default_order', ['youtube', 'odysee', 'peertube', 'rumble'])
        
        # Platform metrics storage
        self.platform_metrics: Dict[str, PlatformMetrics] = {}
        self.metrics_lock = Lock()
        
        # Prioritization weights for different strategies
        self.strategy_weights = {
            PrioritizationStrategy.BALANCED: {
                'response_time': 0.30,
                'reliability': 0.40,
                'success_rate': 0.30
            },
            PrioritizationStrategy.SPEED_FIRST: {
                'response_time': 0.70,
                'reliability': 0.15,
                'success_rate': 0.15
            },
            PrioritizationStrategy.RELIABILITY_FIRST: {
                'response_time': 0.15,
                'reliability': 0.70,
                'success_rate': 0.15
            },
            PrioritizationStrategy.SUCCESS_RATE_FIRST: {
                'response_time': 0.15,
                'reliability': 0.15,
                'success_rate': 0.70
            },
            PrioritizationStrategy.ADAPTIVE: {
                'response_time': 0.33,
                'reliability': 0.33,
                'success_rate': 0.34
            }
        }
        
        # Last prioritization update
        self.last_update = 0.0
        self.cached_priority_order: List[str] = []
        
        logger.info(f"Platform prioritization initialized with strategy: {self.strategy.value}")
    
    def record_platform_operation(self, platform_name: str, success: bool, 
                                 response_time: float, error_type: Optional[str] = None):
        """Record a platform operation result"""
        if not self.enabled:
            return
        
        with self.metrics_lock:
            if platform_name not in self.platform_metrics:
                self.platform_metrics[platform_name] = PlatformMetrics()
            
            metrics = self.platform_metrics[platform_name]
            current_time = time.time()
            
            # Update request counts
            metrics.total_requests += 1
            if success:
                metrics.successful_requests += 1
                metrics.consecutive_failures = 0
            else:
                metrics.consecutive_failures += 1
                metrics.last_failure_time = current_time
            
            # Update response time
            if response_time > 0:
                metrics.response_time_samples.append(response_time)
                if metrics.response_time_samples:
                    metrics.avg_response_time = sum(metrics.response_time_samples) / len(metrics.response_time_samples)
            
            # Update timestamp
            metrics.last_updated = current_time
            
            # Recalculate scores
            self._update_platform_scores(platform_name)
            
            logger.debug(
                f"Recorded operation for {platform_name}: success={success}, "
                f"response_time={response_time:.2f}s, error_type={error_type}"
            )
    
    def update_platform_health(self, platform_name: str, health_status: ConnectionStatus):
        """Update platform health status"""
        if not self.enabled:
            return
        
        with self.metrics_lock:
            if platform_name not in self.platform_metrics:
                self.platform_metrics[platform_name] = PlatformMetrics()
            
            metrics = self.platform_metrics[platform_name]
            metrics.current_health = health_status
            
            # Update health score based on status
            health_multipliers = {
                ConnectionStatus.HEALTHY: 1.0,
                ConnectionStatus.DEGRADED: 0.7,
                ConnectionStatus.UNHEALTHY: 0.3,
                ConnectionStatus.UNKNOWN: 0.9
            }
            metrics.health_score = health_multipliers.get(health_status, 0.5)
            
            # Recalculate scores
            self._update_platform_scores(platform_name)
            
            logger.debug(f"Updated health for {platform_name}: {health_status.value}")
    
    def _update_platform_scores(self, platform_name: str):
        """Update all scores for a platform"""
        metrics = self.platform_metrics[platform_name]
        current_time = time.time()
        
        # Response time score (lower is better)
        if metrics.avg_response_time > 0:
            # Use exponential decay - threshold of 5 seconds
            response_score = max(0.1, 1.0 / (1.0 + (metrics.avg_response_time / self.response_time_threshold)))
        else:
            response_score = 1.0
        metrics.response_time_score = response_score
        
        # Success rate score (higher is better)
        if metrics.total_requests >= self.min_samples:
            success_rate = metrics.successful_requests / metrics.total_requests
            # Use square root to emphasize high success rates
            success_score = success_rate ** 0.5
        else:
            success_score = 0.5  # Neutral score for insufficient data
        metrics.success_rate_score = success_score
        
        # Reliability score (considers consecutive failures and health)
        reliability_score = 1.0
        
        # Penalty for consecutive failures
        if metrics.consecutive_failures > 0:
            failure_penalty = min(0.8, metrics.consecutive_failures * 0.2)
            reliability_score -= failure_penalty
        
        # Bonus for consecutive successes
        if metrics.consecutive_failures == 0 and metrics.total_requests > 0:
            consecutive_successes = min(5, metrics.successful_requests)
            success_bonus = consecutive_successes * 0.05
            reliability_score = min(1.0, reliability_score + success_bonus)
        
        # Apply health multiplier
        reliability_score *= metrics.health_score
        
        # Temporary penalty for recent failures
        if metrics.last_failure_time > 0:
            time_since_failure = current_time - metrics.last_failure_time
            if time_since_failure < self.failure_penalty_duration:
                penalty_factor = 1.0 - (self.failure_penalty_duration - time_since_failure) / self.failure_penalty_duration
                temporary_penalty = 0.3 * penalty_factor  # Up to 30% penalty
                reliability_score = max(0.1, reliability_score - temporary_penalty)
        
        metrics.reliability_score = max(0.0, min(1.0, reliability_score))
        
        # Calculate overall score based on current strategy
        weights = self.strategy_weights.get(self.strategy, self.strategy_weights[PrioritizationStrategy.BALANCED])
        
        # For adaptive strategy, adjust weights based on current conditions
        if self.strategy == PrioritizationStrategy.ADAPTIVE:
            weights = self._calculate_adaptive_weights()
        
        overall_score = (
            metrics.response_time_score * weights['response_time'] +
            metrics.reliability_score * weights['reliability'] +
            metrics.success_rate_score * weights['success_rate']
        )
        
        metrics.overall_score = overall_score
    
    def _calculate_adaptive_weights(self) -> Dict[str, float]:
        """Calculate adaptive weights based on current platform conditions"""
        # Analyze current platform states to determine optimal weights
        total_platforms = len(self.platform_metrics)
        if total_platforms == 0:
            return self.strategy_weights[PrioritizationStrategy.BALANCED]
        
        # Count platforms by health status
        healthy_count = sum(1 for m in self.platform_metrics.values() 
                          if m.current_health == ConnectionStatus.HEALTHY)
        unhealthy_count = sum(1 for m in self.platform_metrics.values() 
                            if m.current_health == ConnectionStatus.UNHEALTHY)
        
        # If many platforms are unhealthy, prioritize reliability
        if unhealthy_count / total_platforms > 0.5:
            return {
                'response_time': 0.15,
                'reliability': 0.70,
                'success_rate': 0.15
            }
        
        # If all platforms are healthy, optimize for speed
        if healthy_count / total_platforms > 0.8:
            return {
                'response_time': 0.60,
                'reliability': 0.20,
                'success_rate': 0.20
            }
        
        # Default balanced approach
        return self.strategy_weights[PrioritizationStrategy.BALANCED]
    
    def get_platform_priority_order(self, available_platforms: Dict[str, Any]) -> List[str]:
        """Get platforms ordered by priority (highest first)"""
        if not self.enabled:
            # Return default order filtered by available platforms
            return [p for p in self.default_order if p in available_platforms]
        
        current_time = time.time()
        
        # Use cached order if recent enough
        if (current_time - self.last_update < self.update_interval and 
            self.cached_priority_order):
            return [p for p in self.cached_priority_order if p in available_platforms]
        
        # Calculate new priority order
        platform_scores = []
        
        for platform_name in available_platforms.keys():
            with self.metrics_lock:
                if platform_name in self.platform_metrics:
                    metrics = self.platform_metrics[platform_name]
                    # Update scores before using them
                    self._update_platform_scores(platform_name)
                    score = metrics.overall_score
                else:
                    # Default score for platforms without metrics
                    score = 0.5
            
            platform_scores.append((platform_name, score))
        
        # Sort by score (descending)
        platform_scores.sort(key=lambda x: x[1], reverse=True)
        priority_order = [platform for platform, _ in platform_scores]
        
        # Cache the result
        self.cached_priority_order = priority_order
        self.last_update = current_time
        
        logger.debug(f"Updated platform priority order: {priority_order}")
        return priority_order
    
    def get_platform_metrics_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all platform metrics"""
        summary = {}
        
        with self.metrics_lock:
            for platform_name, metrics in self.platform_metrics.items():
                summary[platform_name] = {
                    'overall_score': round(metrics.overall_score, 3),
                    'response_time_score': round(metrics.response_time_score, 3),
                    'reliability_score': round(metrics.reliability_score, 3),
                    'success_rate_score': round(metrics.success_rate_score, 3),
                    'avg_response_time': round(metrics.avg_response_time, 2),
                    'success_rate': round(metrics.successful_requests / max(1, metrics.total_requests), 3),
                    'total_requests': metrics.total_requests,
                    'consecutive_failures': metrics.consecutive_failures,
                    'health_status': metrics.current_health.value,
                    'last_updated': metrics.last_updated
                }
        
        return summary
    
    def set_strategy(self, strategy: str):
        """Change prioritization strategy"""
        try:
            new_strategy = PrioritizationStrategy(strategy)
            old_strategy = self.strategy
            self.strategy = new_strategy
            
            # Invalidate cache to force recalculation
            self.last_update = 0.0
            self.cached_priority_order = []
            
            logger.info(f"Changed prioritization strategy from {old_strategy.value} to {new_strategy.value}")
            
        except ValueError:
            logger.error(f"Invalid prioritization strategy: {strategy}")
            raise
    
    def reset_platform_metrics(self, platform_name: Optional[str] = None):
        """Reset metrics for a platform or all platforms"""
        with self.metrics_lock:
            if platform_name:
                if platform_name in self.platform_metrics:
                    self.platform_metrics[platform_name] = PlatformMetrics()
                    logger.info(f"Reset metrics for platform: {platform_name}")
            else:
                self.platform_metrics.clear()
                logger.info("Reset metrics for all platforms")
        
        # Invalidate cache
        self.last_update = 0.0
        self.cached_priority_order = []


# Global instance
_prioritization_manager: Optional[PlatformPrioritizationManager] = None


def initialize_prioritization_manager(config: Dict[str, Any]):
    """Initialize the global prioritization manager"""
    global _prioritization_manager
    prioritization_config = config.get('prioritization', {})
    _prioritization_manager = PlatformPrioritizationManager(prioritization_config)


def get_prioritization_manager() -> Optional[PlatformPrioritizationManager]:
    """Get the global prioritization manager"""
    return _prioritization_manager


def shutdown_prioritization_manager():
    """Shutdown the global prioritization manager"""
    global _prioritization_manager
    if _prioritization_manager:
        logger.info("Shutting down platform prioritization manager")
        _prioritization_manager = None