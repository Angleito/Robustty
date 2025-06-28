"""Platform fallback manager for handling cookie failures

This service provides fallback strategies when cookies are unavailable,
ensuring platforms can continue operating with reduced functionality.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class FallbackMode(Enum):
    """Different fallback modes available for platforms"""
    # Generic modes
    API_ONLY = "api_only"              # Use API without cookies
    PUBLIC_ONLY = "public_only"        # Only public/non-authenticated content
    LIMITED_SEARCH = "limited_search"  # Reduced search capabilities
    READ_ONLY = "read_only"           # No write operations
    DISABLED = "disabled"             # Platform disabled
    
    # YouTube-specific modes
    API_PRIMARY = "api_primary"                    # Normal API usage (preferred)
    YTDLP_AUTHENTICATED = "ytdlp_authenticated"    # yt-dlp with cookies
    YTDLP_PUBLIC = "ytdlp_public"                  # yt-dlp without cookies
    CACHE_ONLY = "cache_only"                      # Only return cached results
    CROSS_PLATFORM = "cross_platform"              # Search other platforms for same content


@dataclass
class FallbackStrategy:
    """Represents a fallback strategy for a platform"""
    mode: FallbackMode
    description: str
    limitations: List[str]
    enabled: bool = True
    priority: int = 0  # Lower number = higher priority
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'mode': self.mode.value,
            'description': self.description,
            'limitations': self.limitations,
            'enabled': self.enabled,
            'priority': self.priority
        }


class PlatformFallbackManager:
    """Manages fallback strategies for platforms when cookies fail"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.fallback_strategies: Dict[str, List[FallbackStrategy]] = {}
        self.active_fallbacks: Dict[str, FallbackStrategy] = {}
        self.fallback_history: Dict[str, List[Dict]] = {}
        
        # Configuration
        self.enable_fallbacks = config.get('enable_fallbacks', True)
        self.max_fallback_duration = config.get('max_fallback_duration_hours', 24)
        self.retry_interval = config.get('retry_interval_minutes', 30)
        
        # YouTube-specific tracking
        self.youtube_quota_usage = 0
        self.youtube_quota_limit = config.get('youtube_quota_limit', 10000)  # Daily limit
        self.youtube_quota_reset_time = None
        self.youtube_error_counts = defaultdict(int)  # Track error types
        self.youtube_strategy_metrics = defaultdict(lambda: {'attempts': 0, 'successes': 0})
        self.cookie_health_status = {}  # Platform -> health status
        
        # Generic platform error tracking
        self.platform_error_counts = defaultdict(lambda: defaultdict(int))
        
        # Strategy effectiveness thresholds
        self.strategy_effectiveness_threshold = 0.7  # 70% success rate
        self.quota_conservation_threshold = 0.8  # Start conserving at 80% quota
        
        # Initialize default strategies
        self._setup_default_strategies()
        
        # Monitoring
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    def _setup_default_strategies(self):
        """Setup default fallback strategies for each platform"""
        
        # YouTube fallback strategies
        self.fallback_strategies['youtube'] = [
            FallbackStrategy(
                mode=FallbackMode.API_PRIMARY,
                description="Normal YouTube API usage with quota management",
                limitations=[
                    "Subject to daily quota limits",
                    "No access to private/age-restricted content"
                ],
                priority=1
            ),
            FallbackStrategy(
                mode=FallbackMode.YTDLP_AUTHENTICATED,
                description="Use yt-dlp with browser cookies for full access",
                limitations=[
                    "Depends on cookie health",
                    "Slower than API for searches",
                    "May trigger rate limiting"
                ],
                priority=2
            ),
            FallbackStrategy(
                mode=FallbackMode.YTDLP_PUBLIC,
                description="Use yt-dlp without authentication",
                limitations=[
                    "No access to private/age-restricted content",
                    "Limited video quality options",
                    "Higher chance of extraction failures",
                    "May encounter captchas"
                ],
                priority=3
            ),
            FallbackStrategy(
                mode=FallbackMode.CACHE_ONLY,
                description="Return only cached results",
                limitations=[
                    "No new searches possible",
                    "Limited to previously cached content",
                    "Results may be outdated"
                ],
                priority=4
            ),
            FallbackStrategy(
                mode=FallbackMode.CROSS_PLATFORM,
                description="Search other platforms for similar content",
                limitations=[
                    "Different content catalog",
                    "May not find exact matches",
                    "Quality and availability varies"
                ],
                priority=5
            ),
            FallbackStrategy(
                mode=FallbackMode.DISABLED,
                description="Disable YouTube platform entirely",
                limitations=["No YouTube functionality available"],
                priority=6
            )
        ]
        
        # Rumble fallback strategies
        self.fallback_strategies['rumble'] = [
            FallbackStrategy(
                mode=FallbackMode.PUBLIC_ONLY,
                description="Access only public Rumble content without authentication",
                limitations=[
                    "No access to private channels",
                    "No personalized content",
                    "Limited search capabilities"
                ],
                priority=1
            ),
            FallbackStrategy(
                mode=FallbackMode.LIMITED_SEARCH,
                description="Basic public search functionality",
                limitations=[
                    "Reduced search accuracy",
                    "No trending or recommended content"
                ],
                priority=2
            ),
            FallbackStrategy(
                mode=FallbackMode.DISABLED,
                description="Disable Rumble platform",
                limitations=["No Rumble functionality available"],
                priority=3
            )
        ]
        
        # Odysee fallback strategies
        self.fallback_strategies['odysee'] = [
            FallbackStrategy(
                mode=FallbackMode.PUBLIC_ONLY,
                description="Access public Odysee content without authentication",
                limitations=[
                    "No access to private content",
                    "No personalized recommendations",
                    "Basic search only"
                ],
                priority=1
            ),
            FallbackStrategy(
                mode=FallbackMode.DISABLED,
                description="Disable Odysee platform",
                limitations=["No Odysee functionality available"],
                priority=2
            )
        ]
        
        # PeerTube fallback strategies
        self.fallback_strategies['peertube'] = [
            FallbackStrategy(
                mode=FallbackMode.PUBLIC_ONLY,
                description="Access public PeerTube instances without authentication",
                limitations=[
                    "No access to private instances",
                    "Limited to federated content",
                    "No personalized features"
                ],
                priority=1
            ),
            FallbackStrategy(
                mode=FallbackMode.DISABLED,
                description="Disable PeerTube platform",
                limitations=["No PeerTube functionality available"],
                priority=2
            )
        ]
    
    async def start(self):
        """Start the fallback manager monitoring"""
        if not self.enable_fallbacks:
            logger.info("Platform fallbacks are disabled")
            return
        
        logger.info("Starting platform fallback manager")
        self._monitor_task = asyncio.create_task(self._monitor_fallbacks())
    
    async def stop(self):
        """Stop the fallback manager"""
        logger.info("Stopping platform fallback manager")
        self._stop_event.set()
        
        if self._monitor_task:
            try:
                await asyncio.wait_for(self._monitor_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Fallback manager stop timed out")
                self._monitor_task.cancel()
    
    def activate_fallback(self, platform: str, reason: str = "Cookie failure") -> Optional[FallbackStrategy]:
        """Activate fallback mode for a platform"""
        if not self.enable_fallbacks:
            logger.warning(f"Fallbacks disabled, cannot activate fallback for {platform}")
            return None
        
        if platform not in self.fallback_strategies:
            logger.error(f"No fallback strategies defined for platform: {platform}")
            return None
        
        # Find the best available strategy
        available_strategies = [s for s in self.fallback_strategies[platform] if s.enabled]
        if not available_strategies:
            logger.error(f"No enabled fallback strategies for {platform}")
            return None
        
        # Sort by priority (lower number = higher priority)
        available_strategies.sort(key=lambda s: s.priority)
        selected_strategy = available_strategies[0]
        
        # Activate the fallback
        self.active_fallbacks[platform] = selected_strategy
        
        # Record the fallback activation
        fallback_record = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'strategy': selected_strategy.to_dict(),
            'action': 'activated'
        }
        
        if platform not in self.fallback_history:
            self.fallback_history[platform] = []
        self.fallback_history[platform].append(fallback_record)
        
        logger.warning(f"Activated {selected_strategy.mode.value} fallback for {platform}: {reason}")
        logger.info(f"Platform {platform} limitations: {', '.join(selected_strategy.limitations)}")
        
        return selected_strategy
    
    def deactivate_fallback(self, platform: str, reason: str = "Cookies restored") -> bool:
        """Deactivate fallback mode for a platform"""
        if platform not in self.active_fallbacks:
            logger.debug(f"No active fallback to deactivate for {platform}")
            return False
        
        strategy = self.active_fallbacks.pop(platform)
        
        # Record the deactivation
        fallback_record = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'strategy': strategy.to_dict(),
            'action': 'deactivated'
        }
        
        if platform not in self.fallback_history:
            self.fallback_history[platform] = []
        self.fallback_history[platform].append(fallback_record)
        
        logger.info(f"Deactivated {strategy.mode.value} fallback for {platform}: {reason}")
        return True
    
    def is_platform_in_fallback(self, platform: str) -> bool:
        """Check if a platform is currently in fallback mode"""
        return platform in self.active_fallbacks
    
    def get_platform_fallback_mode(self, platform: str) -> Optional[FallbackMode]:
        """Get the current fallback mode for a platform"""
        strategy = self.active_fallbacks.get(platform)
        return strategy.mode if strategy else None
    
    def get_active_fallback(self, platform: str) -> Optional[FallbackStrategy]:
        """Get the active fallback strategy for a platform"""
        return self.active_fallbacks.get(platform)
    
    def get_platform_limitations(self, platform: str) -> List[str]:
        """Get current limitations for a platform"""
        strategy = self.active_fallbacks.get(platform)
        return strategy.limitations if strategy else []
    
    def should_use_fallback_for_operation(self, platform: str, operation: str) -> Tuple[bool, Optional[str]]:
        """Determine if an operation should use fallback mode
        
        Returns:
            Tuple of (should_use_fallback, fallback_reason)
        """
        if not self.is_platform_in_fallback(platform):
            return False, None
        
        strategy = self.active_fallbacks[platform]
        mode = strategy.mode
        
        # Define operation restrictions based on fallback mode
        if mode == FallbackMode.DISABLED:
            return True, "Platform is disabled"
        
        elif mode == FallbackMode.READ_ONLY:
            write_operations = ['upload', 'comment', 'like', 'subscribe', 'playlist_add']
            if operation in write_operations:
                return True, "Write operations disabled in read-only mode"
        
        elif mode == FallbackMode.LIMITED_SEARCH:
            if operation in ['advanced_search', 'personalized_search', 'trending']:
                return True, "Advanced search features disabled"
        
        elif mode == FallbackMode.PUBLIC_ONLY:
            if operation in ['private_content', 'authenticated_content', 'user_playlists']:
                return True, "Private content not available in public-only mode"
        
        elif mode == FallbackMode.API_ONLY:
            if operation in ['stream_extraction', 'download']:
                return True, "Stream extraction may be limited in API-only mode"
        
        # YouTube-specific modes
        elif mode == FallbackMode.API_PRIMARY:
            if operation in ['private_content', 'age_restricted_content']:
                return True, "Content requires authentication"
        
        elif mode == FallbackMode.YTDLP_AUTHENTICATED:
            # Most operations available with authenticated yt-dlp
            return False, None
        
        elif mode == FallbackMode.YTDLP_PUBLIC:
            if operation in ['private_content', 'age_restricted_content', 'user_playlists']:
                return True, "Authentication required for this content"
        
        elif mode == FallbackMode.CACHE_ONLY:
            if operation in ['search', 'stream_extraction', 'metadata_fetch']:
                return True, "Only cached content available"
        
        elif mode == FallbackMode.CROSS_PLATFORM:
            if operation == 'search':
                return False, None  # Search is available on other platforms
            return True, "Content not available on alternative platforms"
        
        return False, None
    
    def get_fallback_recommendations(self, platform: str) -> List[str]:
        """Get recommendations for users when platform is in fallback mode"""
        if not self.is_platform_in_fallback(platform):
            return []
        
        strategy = self.active_fallbacks[platform]
        recommendations = []
        
        # Generic fallback modes
        if strategy.mode == FallbackMode.DISABLED:
            recommendations.extend([
                f"The {platform} platform is temporarily disabled",
                "Try using alternative platforms for your search",
                "Check back later when the issue is resolved"
            ])
        
        elif strategy.mode == FallbackMode.LIMITED_SEARCH:
            recommendations.extend([
                f"{platform} is running with limited search capabilities",
                "Try simpler search terms for better results",
                "Some videos may not be accessible"
            ])
        
        elif strategy.mode == FallbackMode.PUBLIC_ONLY:
            recommendations.extend([
                f"{platform} can only access public content currently",
                "Private or authenticated content is not available",
                "Search results may be limited"
            ])
        
        elif strategy.mode == FallbackMode.API_ONLY:
            recommendations.extend([
                f"{platform} is using API-only mode",
                "Some features may be limited or unavailable",
                "Video quality options may be reduced"
            ])
        
        # YouTube-specific fallback modes
        elif strategy.mode == FallbackMode.API_PRIMARY:
            quota_percentage = (self.youtube_quota_usage / self.youtube_quota_limit) * 100
            recommendations.extend([
                f"YouTube is operating normally (Quota: {quota_percentage:.1f}% used)",
                "All public content is accessible",
                "Age-restricted content may require alternative methods"
            ])
        
        elif strategy.mode == FallbackMode.YTDLP_AUTHENTICATED:
            recommendations.extend([
                "Using alternative YouTube access method with authentication",
                "All content should be accessible",
                "Searches may take slightly longer than usual"
            ])
        
        elif strategy.mode == FallbackMode.YTDLP_PUBLIC:
            recommendations.extend([
                "Using alternative YouTube access method without authentication",
                "Age-restricted and private content is not available",
                "Try using direct video URLs for better results"
            ])
        
        elif strategy.mode == FallbackMode.CACHE_ONLY:
            recommendations.extend([
                "YouTube searches are temporarily unavailable",
                "Only previously searched content can be accessed",
                "Try searching on other platforms like Rumble or Odysee"
            ])
        
        elif strategy.mode == FallbackMode.CROSS_PLATFORM:
            recommendations.extend([
                "Searching alternative platforms for similar content",
                "Results may vary from YouTube's catalog",
                "Original YouTube URLs will not work"
            ])
        
        return recommendations
    
    async def _monitor_fallbacks(self):
        """Monitor active fallbacks and attempt recovery"""
        while not self._stop_event.is_set():
            try:
                await self._check_fallback_recovery()
                
                # Wait for next check
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.retry_interval * 60
                    )
                except asyncio.TimeoutError:
                    continue
                    
            except Exception as e:
                logger.error(f"Error in fallback monitoring: {e}")
                await asyncio.sleep(60)
    
    async def _check_fallback_recovery(self):
        """Check if any platforms can recover from fallback mode"""
        if not self.active_fallbacks:
            return
        
        logger.debug(f"Checking recovery for {len(self.active_fallbacks)} platforms in fallback mode")
        
        # YouTube-specific optimization
        if 'youtube' in self.active_fallbacks:
            # Try to optimize YouTube strategy
            if self.optimize_youtube_strategy():
                logger.info("YouTube strategy optimized based on current conditions")
            
            # Check if quota has reset
            if self.youtube_quota_reset_time and datetime.now() > self.youtube_quota_reset_time:
                self.youtube_quota_usage = 0
                self.youtube_quota_reset_time = None
                self.reset_youtube_metrics()
                logger.info("YouTube quota reset - cleared error metrics")
        
        # Check all platforms
        for platform, strategy in list(self.active_fallbacks.items()):
            fallback_duration = self._get_fallback_duration(platform)
            
            if fallback_duration and fallback_duration > self.max_fallback_duration:
                logger.warning(f"Platform {platform} has been in fallback mode for {fallback_duration:.1f} hours")
            
            # Platform-specific recovery checks
            if platform == 'youtube':
                health_score = self.get_youtube_health_score()
                logger.debug(f"YouTube health score: {health_score:.1f}")
                
                if health_score > 80 and strategy.mode != FallbackMode.API_PRIMARY:
                    # Try to recover to better mode
                    if self.can_recover_to_api():
                        self.deactivate_fallback('youtube', "Health score improved")
                        logger.info("YouTube recovered to normal operation")
    
    def _get_fallback_duration(self, platform: str) -> Optional[float]:
        """Get how long a platform has been in fallback mode (in hours)"""
        if platform not in self.fallback_history:
            return None
        
        # Find the most recent activation
        recent_activations = [
            record for record in self.fallback_history[platform]
            if record['action'] == 'activated'
        ]
        
        if not recent_activations:
            return None
        
        latest_activation = max(recent_activations, key=lambda r: r['timestamp'])
        activation_time = datetime.fromisoformat(latest_activation['timestamp'])
        
        # Check if there's a deactivation after this activation
        recent_deactivations = [
            record for record in self.fallback_history[platform]
            if (record['action'] == 'deactivated' and 
                record['timestamp'] > latest_activation['timestamp'])
        ]
        
        if recent_deactivations:
            return None  # Already deactivated
        
        # Calculate duration
        duration = datetime.now() - activation_time
        return duration.total_seconds() / 3600
    
    def get_fallback_report(self) -> Dict[str, Any]:
        """Get comprehensive fallback status report"""
        active_count = len(self.active_fallbacks)
        total_platforms = len(self.fallback_strategies)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'enabled': self.enable_fallbacks,
            'summary': {
                'active_fallbacks': active_count,
                'total_platforms': total_platforms,
                'fallback_rate': active_count / total_platforms if total_platforms > 0 else 0
            },
            'active_fallbacks': {
                platform: {
                    'mode': strategy.mode.value,
                    'description': strategy.description,
                    'limitations': strategy.limitations,
                    'duration_hours': self._get_fallback_duration(platform)
                }
                for platform, strategy in self.active_fallbacks.items()
            },
            'platform_strategies': {
                platform: [s.to_dict() for s in strategies]
                for platform, strategies in self.fallback_strategies.items()
            },
            'history_summary': {
                platform: len(history)
                for platform, history in self.fallback_history.items()
            }
        }
        
        # Add YouTube-specific metrics
        if 'youtube' in self.fallback_strategies:
            youtube_metrics = {
                'quota_usage': self.youtube_quota_usage,
                'quota_limit': self.youtube_quota_limit,
                'quota_percentage': (self.youtube_quota_usage / self.youtube_quota_limit) * 100,
                'quota_reset_time': self.youtube_quota_reset_time.isoformat() if self.youtube_quota_reset_time else None,
                'error_counts': dict(self.youtube_error_counts),
                'strategy_effectiveness': {
                    strategy: {
                        'attempts': metrics['attempts'],
                        'successes': metrics['successes'],
                        'effectiveness': (metrics['successes'] / metrics['attempts'] * 100) if metrics['attempts'] > 0 else 0
                    }
                    for strategy, metrics in self.youtube_strategy_metrics.items()
                },
                'cookie_health': self.cookie_health_status.get('youtube', {}),
                'recommended_strategy': self.get_youtube_strategy().value,
                'status_message': self.get_youtube_status_message()
            }
            report['youtube_metrics'] = youtube_metrics
        
        return report
    
    def clear_fallback_history(self, platform: Optional[str] = None):
        """Clear fallback history for a platform or all platforms"""
        if platform:
            if platform in self.fallback_history:
                self.fallback_history[platform] = []
                logger.info(f"Cleared fallback history for {platform}")
        else:
            self.fallback_history.clear()
            logger.info("Cleared all fallback history")
    
    def configure_platform_strategies(self, platform: str, strategies: List[FallbackStrategy]):
        """Configure custom fallback strategies for a platform"""
        if not strategies:
            logger.warning(f"No strategies provided for {platform}")
            return
        
        self.fallback_strategies[platform] = strategies
        logger.info(f"Configured {len(strategies)} fallback strategies for {platform}")
        
        # If platform is currently in fallback, re-evaluate
        if platform in self.active_fallbacks:
            logger.info(f"Re-evaluating active fallback for {platform}")
            self.deactivate_fallback(platform, "Strategy reconfiguration")
            self.activate_fallback(platform, "Strategy reconfiguration")
    
    # YouTube-specific methods
    def get_youtube_strategy(self) -> FallbackMode:
        """Get the best YouTube strategy based on current conditions"""
        # Check quota usage
        quota_percentage = self.youtube_quota_usage / self.youtube_quota_limit
        
        # Check cookie health
        cookie_healthy = self.cookie_health_status.get('youtube', {}).get('healthy', False)
        
        # Check error rates
        total_errors = sum(self.youtube_error_counts.values())
        api_errors = self.youtube_error_counts.get('api_error', 0)
        
        # Decision logic
        if quota_percentage >= 0.95:
            # Almost out of quota
            if cookie_healthy:
                return FallbackMode.YTDLP_AUTHENTICATED
            else:
                return FallbackMode.CACHE_ONLY
        
        elif quota_percentage >= self.quota_conservation_threshold:
            # Conservation mode
            if cookie_healthy:
                return FallbackMode.YTDLP_AUTHENTICATED
            else:
                return FallbackMode.YTDLP_PUBLIC
        
        elif api_errors > 10 and cookie_healthy:
            # API having issues but cookies are good
            return FallbackMode.YTDLP_AUTHENTICATED
        
        elif total_errors > 20:
            # Too many errors overall
            return FallbackMode.CACHE_ONLY
        
        else:
            # Normal operation
            return FallbackMode.API_PRIMARY
    
    def should_escalate_fallback(self, platform: str, current_mode: FallbackMode, 
                                error_type: Optional[str] = None) -> bool:
        """Determine if we should move to the next fallback strategy"""
        if platform != 'youtube':
            # Generic escalation logic for other platforms
            # Track errors per platform
            if not hasattr(self, 'platform_error_counts'):
                self.platform_error_counts = defaultdict(lambda: defaultdict(int))
            
            self.platform_error_counts[platform][error_type or 'general'] += 1
            return self.platform_error_counts[platform][error_type or 'general'] > 3
        
        # YouTube-specific escalation logic
        if current_mode == FallbackMode.API_PRIMARY:
            # Check if API is failing
            if error_type == 'quota_exceeded':
                return True
            if self.youtube_error_counts.get('api_error', 0) > 5:
                return True
                
        elif current_mode == FallbackMode.YTDLP_AUTHENTICATED:
            # Check if cookies are failing
            if error_type == 'cookie_invalid':
                return True
            if self.youtube_error_counts.get('extraction_error', 0) > 3:
                return True
                
        elif current_mode == FallbackMode.YTDLP_PUBLIC:
            # Check if yt-dlp public is failing
            if self.youtube_error_counts.get('extraction_error', 0) > 5:
                return True
                
        return False
    
    def can_recover_to_api(self) -> bool:
        """Check if we can safely return to using the YouTube API"""
        # Check quota reset
        if self.youtube_quota_reset_time and datetime.now() > self.youtube_quota_reset_time:
            self.youtube_quota_usage = 0
            self.youtube_quota_reset_time = None
            return True
        
        # Check if quota usage is low enough
        quota_percentage = self.youtube_quota_usage / self.youtube_quota_limit
        if quota_percentage < 0.5:  # Less than 50% quota used
            return True
        
        return False
    
    def update_youtube_quota(self, units_used: int):
        """Update YouTube API quota usage"""
        self.youtube_quota_usage += units_used
        
        # Set reset time if not set
        if not self.youtube_quota_reset_time:
            now = datetime.now()
            # YouTube quota resets at midnight Pacific Time
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            self.youtube_quota_reset_time = tomorrow
        
        logger.debug(f"YouTube quota usage: {self.youtube_quota_usage}/{self.youtube_quota_limit}")
    
    def record_strategy_result(self, platform: str, strategy: FallbackMode, 
                              success: bool, error_type: Optional[str] = None):
        """Record the result of using a specific strategy"""
        if platform == 'youtube':
            key = strategy.value
            self.youtube_strategy_metrics[key]['attempts'] += 1
            if success:
                self.youtube_strategy_metrics[key]['successes'] += 1
            else:
                if error_type:
                    self.youtube_error_counts[error_type] += 1
    
    def get_strategy_effectiveness(self, strategy: FallbackMode) -> float:
        """Get the effectiveness rate of a strategy"""
        metrics = self.youtube_strategy_metrics.get(strategy.value, {'attempts': 0, 'successes': 0})
        if metrics['attempts'] == 0:
            return 1.0  # Assume new strategies are effective
        return metrics['successes'] / metrics['attempts']
    
    def update_cookie_health(self, platform: str, healthy: bool, details: Optional[Dict] = None):
        """Update cookie health status for a platform"""
        self.cookie_health_status[platform] = {
            'healthy': healthy,
            'last_check': datetime.now(),
            'details': details or {}
        }
    
    def get_youtube_status_message(self) -> str:
        """Generate a user-friendly status message for YouTube"""
        current_strategy = self.active_fallbacks.get('youtube')
        if not current_strategy:
            return "YouTube is operating normally"
        
        mode = current_strategy.mode
        quota_percentage = (self.youtube_quota_usage / self.youtube_quota_limit) * 100
        
        messages = {
            FallbackMode.API_PRIMARY: f"Using YouTube API (Quota: {quota_percentage:.1f}% used)",
            FallbackMode.YTDLP_AUTHENTICATED: "Using alternative method with authentication",
            FallbackMode.YTDLP_PUBLIC: "Using alternative method without authentication - some content may be unavailable",
            FallbackMode.CACHE_ONLY: "Returning cached results only - new searches temporarily unavailable",
            FallbackMode.CROSS_PLATFORM: "Searching alternative platforms for content",
            FallbackMode.DISABLED: "YouTube is temporarily unavailable"
        }
        
        return messages.get(mode, "YouTube status unknown")
    
    def activate_youtube_strategy(self, reason: str = "Auto-selected") -> Optional[FallbackStrategy]:
        """Activate the best YouTube strategy based on current conditions"""
        best_mode = self.get_youtube_strategy()
        
        # Find the strategy with this mode
        youtube_strategies = self.fallback_strategies.get('youtube', [])
        selected_strategy = None
        
        for strategy in youtube_strategies:
            if strategy.mode == best_mode:
                selected_strategy = strategy
                break
        
        if not selected_strategy:
            logger.error(f"Could not find YouTube strategy for mode: {best_mode}")
            return None
        
        # Activate it
        self.active_fallbacks['youtube'] = selected_strategy
        
        # Record the activation
        fallback_record = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'strategy': selected_strategy.to_dict(),
            'action': 'activated',
            'quota_usage': self.youtube_quota_usage,
            'cookie_health': self.cookie_health_status.get('youtube', {})
        }
        
        if 'youtube' not in self.fallback_history:
            self.fallback_history['youtube'] = []
        self.fallback_history['youtube'].append(fallback_record)
        
        logger.info(f"Activated YouTube {selected_strategy.mode.value} strategy: {reason}")
        return selected_strategy
    
    def optimize_youtube_strategy(self) -> bool:
        """Optimize YouTube strategy based on current conditions
        
        Returns:
            bool: True if strategy was changed, False otherwise
        """
        current_strategy = self.active_fallbacks.get('youtube')
        current_mode = current_strategy.mode if current_strategy else FallbackMode.API_PRIMARY
        
        # Get the best strategy
        best_mode = self.get_youtube_strategy()
        
        # Check if we should change
        if best_mode != current_mode:
            # Check if we can recover to API
            if best_mode == FallbackMode.API_PRIMARY and self.can_recover_to_api():
                self.deactivate_fallback('youtube', "Recovered to API mode")
                return True
            else:
                # Activate new strategy
                self.activate_youtube_strategy(f"Optimized from {current_mode.value} to {best_mode.value}")
                return True
        
        return False
    
    def reset_youtube_metrics(self):
        """Reset YouTube error counts and metrics (useful after recovery)"""
        self.youtube_error_counts.clear()
        logger.info("Reset YouTube error counts")
    
    def get_youtube_health_score(self) -> float:
        """Calculate a health score for YouTube operations (0-100)"""
        score = 100.0
        
        # Deduct for quota usage
        quota_percentage = self.youtube_quota_usage / self.youtube_quota_limit
        score -= quota_percentage * 30  # Max 30 point deduction for quota
        
        # Deduct for errors
        total_errors = sum(self.youtube_error_counts.values())
        score -= min(total_errors * 2, 30)  # Max 30 point deduction for errors
        
        # Deduct for poor cookie health
        cookie_health = self.cookie_health_status.get('youtube', {})
        if not cookie_health.get('healthy', True):
            score -= 20
        
        # Deduct for strategy effectiveness
        current_strategy = self.active_fallbacks.get('youtube')
        if current_strategy:
            effectiveness = self.get_strategy_effectiveness(current_strategy.mode)
            if effectiveness < self.strategy_effectiveness_threshold:
                score -= (1 - effectiveness) * 20  # Max 20 point deduction
        
        return max(0, score)
    
    # Quota monitoring integration
    def handle_youtube_quota_warning(self, usage_percentage: float):
        """Handle a quota warning from external monitoring"""
        if usage_percentage >= self.quota_conservation_threshold:
            # Switch to conservation mode
            current_mode = self.get_platform_fallback_mode('youtube')
            if current_mode == FallbackMode.API_PRIMARY:
                self.activate_youtube_strategy(f"Quota conservation triggered at {usage_percentage:.1f}%")
    
    def handle_youtube_api_error(self, error_type: str, error_details: Optional[Dict] = None):
        """Handle YouTube API errors and potentially switch strategies"""
        # Record the error
        self.youtube_error_counts[error_type] += 1
        
        # Check if we should escalate
        current_strategy = self.active_fallbacks.get('youtube')
        if current_strategy:
            if self.should_escalate_fallback('youtube', current_strategy.mode, error_type):
                self.activate_youtube_strategy(f"Escalating due to {error_type}")
        elif error_type == 'quota_exceeded':
            # Immediate switch if quota exceeded
            self.activate_youtube_strategy("API quota exceeded")
    
    def get_youtube_operation_mode(self, operation: str) -> Tuple[FallbackMode, bool]:
        """Get the appropriate mode for a YouTube operation
        
        Returns:
            Tuple of (mode_to_use, can_proceed)
        """
        current_strategy = self.active_fallbacks.get('youtube')
        if current_strategy:
            can_proceed, reason = self.should_use_fallback_for_operation('youtube', operation)
            return current_strategy.mode, not can_proceed
        else:
            # Not in fallback, use primary mode
            return FallbackMode.API_PRIMARY, True