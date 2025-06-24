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

logger = logging.getLogger(__name__)


class FallbackMode(Enum):
    """Different fallback modes available for platforms"""
    API_ONLY = "api_only"              # Use API without cookies
    PUBLIC_ONLY = "public_only"        # Only public/non-authenticated content
    LIMITED_SEARCH = "limited_search"  # Reduced search capabilities
    READ_ONLY = "read_only"           # No write operations
    DISABLED = "disabled"             # Platform disabled


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
                mode=FallbackMode.API_ONLY,
                description="Use YouTube API without cookies for search only",
                limitations=[
                    "No access to private videos",
                    "No personalized recommendations", 
                    "Reduced rate limits",
                    "May have region restrictions"
                ],
                priority=1
            ),
            FallbackStrategy(
                mode=FallbackMode.LIMITED_SEARCH,
                description="Basic search with generic video extraction",
                limitations=[
                    "No authenticated content",
                    "Limited video quality options",
                    "Higher chance of extraction failures"
                ],
                priority=2
            ),
            FallbackStrategy(
                mode=FallbackMode.DISABLED,
                description="Disable YouTube platform entirely",
                limitations=["No YouTube functionality available"],
                priority=3
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
        
        return False, None
    
    def get_fallback_recommendations(self, platform: str) -> List[str]:
        """Get recommendations for users when platform is in fallback mode"""
        if not self.is_platform_in_fallback(platform):
            return []
        
        strategy = self.active_fallbacks[platform]
        recommendations = []
        
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
        
        return recommendations
    
    async def _monitor_fallbacks(self):
        """Monitor active fallbacks and attempt recovery"""
        while not self._stop_event.is_set():
            try:\n                await self._check_fallback_recovery()\n                \n                # Wait for next check\n                try:\n                    await asyncio.wait_for(\n                        self._stop_event.wait(),\n                        timeout=self.retry_interval * 60\n                    )\n                except asyncio.TimeoutError:\n                    continue\n                    \n            except Exception as e:\n                logger.error(f\"Error in fallback monitoring: {e}\")\n                await asyncio.sleep(60)\n    \n    async def _check_fallback_recovery(self):\n        \"\"\"Check if any platforms can recover from fallback mode\"\"\"\n        if not self.active_fallbacks:\n            return\n        \n        logger.debug(f\"Checking recovery for {len(self.active_fallbacks)} platforms in fallback mode\")\n        \n        # This would typically check cookie health or other recovery conditions\n        # For now, we'll just log the active fallbacks\n        for platform, strategy in self.active_fallbacks.items():\n            fallback_duration = self._get_fallback_duration(platform)\n            \n            if fallback_duration and fallback_duration > self.max_fallback_duration:\n                logger.warning(f\"Platform {platform} has been in fallback mode for {fallback_duration:.1f} hours\")\n    \n    def _get_fallback_duration(self, platform: str) -> Optional[float]:\n        \"\"\"Get how long a platform has been in fallback mode (in hours)\"\"\"\n        if platform not in self.fallback_history:\n            return None\n        \n        # Find the most recent activation\n        recent_activations = [\n            record for record in self.fallback_history[platform]\n            if record['action'] == 'activated'\n        ]\n        \n        if not recent_activations:\n            return None\n        \n        latest_activation = max(recent_activations, key=lambda r: r['timestamp'])\n        activation_time = datetime.fromisoformat(latest_activation['timestamp'])\n        \n        # Check if there's a deactivation after this activation\n        recent_deactivations = [\n            record for record in self.fallback_history[platform]\n            if (record['action'] == 'deactivated' and \n                record['timestamp'] > latest_activation['timestamp'])\n        ]\n        \n        if recent_deactivations:\n            return None  # Already deactivated\n        \n        # Calculate duration\n        duration = datetime.now() - activation_time\n        return duration.total_seconds() / 3600\n    \n    def get_fallback_report(self) -> Dict[str, Any]:\n        \"\"\"Get comprehensive fallback status report\"\"\"\n        active_count = len(self.active_fallbacks)\n        total_platforms = len(self.fallback_strategies)\n        \n        return {\n            'timestamp': datetime.now().isoformat(),\n            'enabled': self.enable_fallbacks,\n            'summary': {\n                'active_fallbacks': active_count,\n                'total_platforms': total_platforms,\n                'fallback_rate': active_count / total_platforms if total_platforms > 0 else 0\n            },\n            'active_fallbacks': {\n                platform: {\n                    'mode': strategy.mode.value,\n                    'description': strategy.description,\n                    'limitations': strategy.limitations,\n                    'duration_hours': self._get_fallback_duration(platform)\n                }\n                for platform, strategy in self.active_fallbacks.items()\n            },\n            'platform_strategies': {\n                platform: [s.to_dict() for s in strategies]\n                for platform, strategies in self.fallback_strategies.items()\n            },\n            'history_summary': {\n                platform: len(history)\n                for platform, history in self.fallback_history.items()\n            }\n        }\n    \n    def clear_fallback_history(self, platform: Optional[str] = None):\n        \"\"\"Clear fallback history for a platform or all platforms\"\"\"\n        if platform:\n            if platform in self.fallback_history:\n                self.fallback_history[platform] = []\n                logger.info(f\"Cleared fallback history for {platform}\")\n        else:\n            self.fallback_history.clear()\n            logger.info(\"Cleared all fallback history\")\n    \n    def configure_platform_strategies(self, platform: str, strategies: List[FallbackStrategy]):\n        \"\"\"Configure custom fallback strategies for a platform\"\"\"\n        if not strategies:\n            logger.warning(f\"No strategies provided for {platform}\")\n            return\n        \n        self.fallback_strategies[platform] = strategies\n        logger.info(f\"Configured {len(strategies)} fallback strategies for {platform}\")\n        \n        # If platform is currently in fallback, re-evaluate\n        if platform in self.active_fallbacks:\n            logger.info(f\"Re-evaluating active fallback for {platform}\")\n            self.deactivate_fallback(platform, \"Strategy reconfiguration\")\n            self.activate_fallback(platform, \"Strategy reconfiguration\")