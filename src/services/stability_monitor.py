"""
VPS Stability Monitor Service

Monitors platform health and automatically disables problematic platforms
to maintain bot stability. Provides recovery checks and re-enables platforms
when they become stable again.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from collections import defaultdict

from ..platforms.registry import PlatformRegistry
from ..utils.config_loader import load_config

logger = logging.getLogger(__name__)


class PlatformHealthTracker:
    """Tracks health metrics for individual platforms"""
    
    def __init__(self, name: str):
        self.name = name
        self.consecutive_failures = 0
        self.total_failures = 0
        self.total_requests = 0
        self.last_failure = None
        self.last_success = None
        self.disabled_at = None
        self.failure_reasons = defaultdict(int)
        
    def record_success(self):
        """Record a successful platform operation"""
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        self.total_requests += 1
        
    def record_failure(self, reason: str = "unknown"):
        """Record a failed platform operation"""
        self.consecutive_failures += 1
        self.total_failures += 1
        self.total_requests += 1
        self.last_failure = datetime.now()
        self.failure_reasons[reason] += 1
        
    def get_failure_rate(self) -> float:
        """Get the overall failure rate"""
        if self.total_requests == 0:
            return 0.0
        return self.total_failures / self.total_requests
        
    def should_disable(self, threshold: int) -> bool:
        """Check if platform should be disabled based on failure threshold"""
        return self.consecutive_failures >= threshold
        
    def mark_disabled(self):
        """Mark platform as disabled"""
        self.disabled_at = datetime.now()
        self.consecutive_failures = 0  # Reset counter
        
    def can_retry(self, retry_interval_seconds: int) -> bool:
        """Check if enough time has passed to retry a disabled platform"""
        if not self.disabled_at:
            return True
        return (datetime.now() - self.disabled_at).total_seconds() >= retry_interval_seconds


class StabilityMonitor:
    """Monitors platform stability and manages automatic disabling/enabling"""
    
    def __init__(self, platform_registry: PlatformRegistry):
        self.platform_registry = platform_registry
        self.config = load_config("config/config.yaml")
        self.stability_config = self.config.get('stability_mode', {})
        self.enabled = self.stability_config.get('enabled', False)
        
        # Platform health trackers
        self.health_trackers: Dict[str, PlatformHealthTracker] = {}
        
        # Platforms that are temporarily disabled
        self.disabled_platforms: Set[str] = set()
        
        # Platforms that should never be auto-disabled
        self.protected_platforms = set(self.stability_config.get('stable_platforms', ['youtube']))
        
        # Platforms known to have issues
        self.problematic_platforms = set(self.stability_config.get('problematic_platforms', ['peertube', 'odysee']))
        
        # Configuration
        self.failure_threshold = self.stability_config.get('failure_threshold', 5)
        self.recovery_check_interval = self.stability_config.get('recovery_check_interval', 300)
        self.auto_disable = self.stability_config.get('auto_disable_failing_platforms', True)
        
        # Background task
        self.monitor_task = None
        
        if self.enabled:
            logger.info(f"Stability Monitor enabled with failure threshold: {self.failure_threshold}")
            logger.info(f"Protected platforms: {self.protected_platforms}")
            logger.info(f"Problematic platforms marked: {self.problematic_platforms}")
        
    def get_tracker(self, platform_name: str) -> PlatformHealthTracker:
        """Get or create a health tracker for a platform"""
        if platform_name not in self.health_trackers:
            self.health_trackers[platform_name] = PlatformHealthTracker(platform_name)
        return self.health_trackers[platform_name]
        
    async def record_platform_success(self, platform_name: str):
        """Record a successful platform operation"""
        if not self.enabled:
            return
            
        tracker = self.get_tracker(platform_name)
        tracker.record_success()
        
        # Log recovery if platform was previously failing
        if tracker.total_failures > 0 and tracker.consecutive_failures == 0:
            logger.info(f"Platform {platform_name} recovered from failures")
            
    async def record_platform_failure(self, platform_name: str, reason: str = "unknown"):
        """Record a failed platform operation"""
        if not self.enabled:
            return
            
        tracker = self.get_tracker(platform_name)
        tracker.record_failure(reason)
        
        logger.warning(
            f"Platform {platform_name} failure recorded: {reason} "
            f"(consecutive: {tracker.consecutive_failures}, total: {tracker.total_failures})"
        )
        
        # Check if platform should be disabled
        if (self.auto_disable and 
            platform_name not in self.protected_platforms and
            tracker.should_disable(self.failure_threshold)):
            
            await self.disable_platform(platform_name)
            
    async def disable_platform(self, platform_name: str):
        """Temporarily disable a failing platform"""
        if platform_name in self.disabled_platforms:
            return  # Already disabled
            
        platform = self.platform_registry.get_platform(platform_name)
        if not platform:
            return
            
        # Mark platform as disabled
        platform.enabled = False
        self.disabled_platforms.add(platform_name)
        
        tracker = self.get_tracker(platform_name)
        tracker.mark_disabled()
        
        # Log failure reasons
        top_reasons = sorted(
            tracker.failure_reasons.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:3]
        
        logger.error(
            f"STABILITY: Disabling platform {platform_name} due to excessive failures. "
            f"Top failure reasons: {top_reasons}"
        )
        
    async def try_enable_platform(self, platform_name: str) -> bool:
        """Try to re-enable a disabled platform"""
        if platform_name not in self.disabled_platforms:
            return True  # Not disabled
            
        platform = self.platform_registry.get_platform(platform_name)
        if not platform:
            return False
            
        tracker = self.get_tracker(platform_name)
        
        # Check if enough time has passed
        if not tracker.can_retry(self.recovery_check_interval):
            return False
            
        logger.info(f"STABILITY: Attempting to re-enable platform {platform_name}")
        
        # Re-enable platform
        platform.enabled = True
        self.disabled_platforms.remove(platform_name)
        
        # Reset some tracking metrics
        tracker.consecutive_failures = 0
        tracker.disabled_at = None
        
        return True
        
    async def get_platform_status(self) -> Dict[str, Dict]:
        """Get current status of all platforms"""
        status = {}
        
        for name, platform in self.platform_registry.get_all_platforms().items():
            tracker = self.get_tracker(name)
            
            status[name] = {
                'enabled': platform.enabled,
                'is_protected': name in self.protected_platforms,
                'is_problematic': name in self.problematic_platforms,
                'is_disabled': name in self.disabled_platforms,
                'consecutive_failures': tracker.consecutive_failures,
                'total_failures': tracker.total_failures,
                'total_requests': tracker.total_requests,
                'failure_rate': tracker.get_failure_rate(),
                'last_failure': tracker.last_failure.isoformat() if tracker.last_failure else None,
                'last_success': tracker.last_success.isoformat() if tracker.last_success else None,
                'disabled_at': tracker.disabled_at.isoformat() if tracker.disabled_at else None,
                'top_failure_reasons': dict(sorted(
                    tracker.failure_reasons.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5])
            }
            
        return status
        
    async def _monitor_loop(self):
        """Background task to check disabled platforms for recovery"""
        while True:
            try:
                await asyncio.sleep(self.recovery_check_interval)
                
                if not self.disabled_platforms:
                    continue
                    
                logger.info(f"STABILITY: Checking {len(self.disabled_platforms)} disabled platforms for recovery")
                
                # Try to re-enable disabled platforms
                platforms_to_check = list(self.disabled_platforms)
                for platform_name in platforms_to_check:
                    await self.try_enable_platform(platform_name)
                    
            except Exception as e:
                logger.error(f"Error in stability monitor loop: {e}")
                
    async def start(self):
        """Start the stability monitor"""
        if not self.enabled:
            logger.info("Stability Monitor is disabled")
            return
            
        if self.monitor_task:
            return  # Already running
            
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Stability Monitor started")
        
    async def stop(self):
        """Stop the stability monitor"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
            self.monitor_task = None
            logger.info("Stability Monitor stopped")
            
    def is_platform_stable(self, platform_name: str) -> bool:
        """Check if a platform is considered stable"""
        if platform_name in self.protected_platforms:
            return True
            
        if platform_name in self.disabled_platforms:
            return False
            
        tracker = self.get_tracker(platform_name)
        return tracker.consecutive_failures < self.failure_threshold