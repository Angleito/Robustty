"""
YouTube API quota monitoring service.

Tracks quota usage, predicts exhaustion, and provides conservation recommendations.
YouTube API quota resets daily at midnight Pacific Time (PST/PDT).
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum
from discord.ext import tasks

try:
    # Try the newer redis package first (aioredis was renamed)
    import redis.asyncio as aioredis
except ImportError:
    try:
        # Fall back to legacy aioredis package
        import aioredis
    except ImportError:
        # If neither is available, we'll run without Redis
        aioredis = None

from ..services.status_reporting import (
    StatusReport,
    PlatformStatus,
    SearchMethod,
    OperationResult,
    get_status_reporter
)

logger = logging.getLogger(__name__)


class QuotaLevel(Enum):
    """Quota level indicators for conservation strategies."""
    HEALTHY = "healthy"  # > 50% remaining
    CAUTION = "caution"  # 20-50% remaining
    CRITICAL = "critical"  # 10-20% remaining
    EXHAUSTED = "exhausted"  # < 10% remaining


class YouTubeAPIQuotaCost:
    """YouTube Data API v3 quota costs per operation."""
    # Search operations
    SEARCH = 100  # search.list
    
    # Video operations
    VIDEO_LIST = 1  # videos.list (per page)
    
    # Channel operations
    CHANNEL_LIST = 1  # channels.list
    
    # Playlist operations
    PLAYLIST_LIST = 1  # playlists.list
    PLAYLIST_ITEMS = 1  # playlistItems.list
    
    # Comment operations
    COMMENT_LIST = 1  # comments.list
    COMMENT_THREADS = 1  # commentThreads.list
    
    # Write operations (not used by this bot)
    VIDEO_INSERT = 1600  # videos.insert
    VIDEO_UPDATE = 50  # videos.update
    VIDEO_DELETE = 50  # videos.delete


class QuotaMonitor:
    """
    Monitors YouTube API quota usage and provides conservation recommendations.
    
    YouTube API v3 has a daily quota limit of 10,000 units by default.
    Quota resets daily at midnight Pacific Time (PST/PDT).
    """
    
    # Default YouTube API quota limit
    DEFAULT_DAILY_QUOTA = 10_000
    
    # Conservation thresholds
    CAUTION_THRESHOLD = 0.5  # 50% remaining
    CRITICAL_THRESHOLD = 0.2  # 20% remaining
    EXHAUSTED_THRESHOLD = 0.1  # 10% remaining
    
    # Time tracking
    QUOTA_RESET_HOUR_UTC = 8  # Midnight PST is 8 AM UTC (7 AM during PDT)
    
    def __init__(self, config: Dict[str, any], redis_client: Optional[aioredis.Redis] = None):
        """
        Initialize quota monitor.
        
        Args:
            config: Configuration dictionary
            redis_client: Optional Redis client for persistence
        """
        self.config = config
        self.redis_client = redis_client
        
        # Quota configuration
        self.daily_quota_limit = config.get('youtube', {}).get('quota_limit', self.DEFAULT_DAILY_QUOTA)
        self.conservation_enabled = config.get('youtube', {}).get('quota_conservation', True)
        
        # In-memory tracking
        self.current_usage = 0
        self.usage_history: List[Tuple[float, int]] = []  # (timestamp, cost) pairs
        self.last_reset_time = self._get_last_reset_time()
        
        # Redis keys
        self.REDIS_KEY_USAGE = "youtube:quota:current_usage"
        self.REDIS_KEY_HISTORY = "youtube:quota:usage_history"
        self.REDIS_KEY_RESET = "youtube:quota:last_reset"
        
        # Status reporter integration
        self.status_reporter = get_status_reporter()
        
        # Start daily reset task
        self._daily_reset_task.start()
        
    async def initialize(self):
        """Initialize quota monitor and restore state from Redis if available."""
        if self.redis_client:
            try:
                # Restore current usage
                usage = await self.redis_client.get(self.REDIS_KEY_USAGE)
                if usage:
                    self.current_usage = int(usage)
                
                # Restore usage history
                history = await self.redis_client.get(self.REDIS_KEY_HISTORY)
                if history:
                    self.usage_history = json.loads(history)
                
                # Restore last reset time
                reset_time = await self.redis_client.get(self.REDIS_KEY_RESET)
                if reset_time:
                    self.last_reset_time = datetime.fromisoformat(reset_time)
                
                logger.info(f"Quota monitor initialized: {self.current_usage}/{self.daily_quota_limit} units used")
                
            except Exception as e:
                logger.error(f"Failed to restore quota state from Redis: {e}")
        
        # Check if we need to reset quota
        await self._check_quota_reset()
    
    async def track_api_call(self, cost: int, operation: str = "unknown") -> None:
        """
        Track an API call's quota cost.
        
        Args:
            cost: Quota cost of the operation
            operation: Description of the operation
        """
        # Check for daily reset
        await self._check_quota_reset()
        
        # Update usage
        self.current_usage += cost
        timestamp = time.time()
        self.usage_history.append((timestamp, cost))
        
        # Persist to Redis
        await self._persist_state()
        
        # Log the usage
        remaining = self.get_remaining_quota()
        percentage = (remaining / self.daily_quota_limit) * 100
        
        logger.info(
            f"YouTube API call: {operation} (cost: {cost}), "
            f"Usage: {self.current_usage}/{self.daily_quota_limit} "
            f"({percentage:.1f}% remaining)"
        )
        
        # Check if we should report quota status
        level = self._get_quota_level()
        if level in [QuotaLevel.CRITICAL, QuotaLevel.EXHAUSTED]:
            await self._report_quota_status(level, operation)
    
    def get_remaining_quota(self) -> int:
        """Get remaining quota units."""
        return max(0, self.daily_quota_limit - self.current_usage)
    
    def get_usage_percentage(self) -> float:
        """Get quota usage as percentage (0-100)."""
        return (self.current_usage / self.daily_quota_limit) * 100
    
    def predict_exhaustion_time(self) -> Optional[float]:
        """
        Predict when quota will be exhausted based on current usage rate.
        
        Returns:
            Hours until exhaustion, or None if rate is too low
        """
        if not self.usage_history or len(self.usage_history) < 2:
            return None
        
        # Calculate usage rate over last hour
        current_time = time.time()
        hour_ago = current_time - 3600
        
        recent_usage = sum(
            cost for timestamp, cost in self.usage_history
            if timestamp > hour_ago
        )
        
        if recent_usage == 0:
            return None
        
        # Calculate hourly rate
        time_span = min(3600, current_time - self.usage_history[0][0])
        hourly_rate = recent_usage * (3600 / time_span)
        
        # Calculate time to exhaustion
        remaining = self.get_remaining_quota()
        if hourly_rate > 0:
            hours_to_exhaustion = remaining / hourly_rate
            return hours_to_exhaustion
        
        return None
    
    def should_activate_conservation(self) -> bool:
        """
        Determine if conservation mode should be activated.
        
        Returns:
            True if conservation measures should be taken
        """
        if not self.conservation_enabled:
            return False
        
        level = self._get_quota_level()
        return level in [QuotaLevel.CRITICAL, QuotaLevel.EXHAUSTED]
    
    def get_conservation_recommendations(self) -> Dict[str, any]:
        """
        Get conservation recommendations based on current quota status.
        
        Returns:
            Dictionary of conservation recommendations
        """
        level = self._get_quota_level()
        remaining_percentage = (self.get_remaining_quota() / self.daily_quota_limit) * 100
        
        recommendations = {
            'level': level.value,
            'remaining_percentage': remaining_percentage,
            'should_use_fallbacks': level in [QuotaLevel.CRITICAL, QuotaLevel.EXHAUSTED],
            'cache_ttl_multiplier': 1.0,
            'max_search_results': 10,
            'enable_aggressive_caching': False,
        }
        
        if level == QuotaLevel.CAUTION:
            recommendations.update({
                'cache_ttl_multiplier': 1.5,  # Extend cache TTL by 50%
                'max_search_results': 5,
                'message': "YouTube quota usage at 50%. Enabling light conservation."
            })
        elif level == QuotaLevel.CRITICAL:
            recommendations.update({
                'cache_ttl_multiplier': 2.0,  # Double cache TTL
                'max_search_results': 3,
                'enable_aggressive_caching': True,
                'message': "YouTube quota critical (< 20%). Switching to fallback methods."
            })
        elif level == QuotaLevel.EXHAUSTED:
            recommendations.update({
                'cache_ttl_multiplier': 3.0,  # Triple cache TTL
                'max_search_results': 1,
                'enable_aggressive_caching': True,
                'message': "YouTube quota nearly exhausted (< 10%). Using fallbacks only."
            })
        else:
            recommendations['message'] = "YouTube quota healthy."
        
        return recommendations
    
    async def reset_daily_quota(self) -> None:
        """Reset daily quota (called at midnight PST)."""
        logger.info(f"Resetting YouTube API quota. Previous usage: {self.current_usage}/{self.daily_quota_limit}")
        
        self.current_usage = 0
        self.usage_history = []
        self.last_reset_time = datetime.now(timezone.utc)
        
        await self._persist_state()
        
        # Report quota reset
        await self._report_quota_reset()
    
    def get_quota_status(self) -> Dict[str, any]:
        """
        Get comprehensive quota status information.
        
        Returns:
            Dictionary containing quota status details
        """
        remaining = self.get_remaining_quota()
        percentage_used = self.get_usage_percentage()
        percentage_remaining = 100 - percentage_used
        level = self._get_quota_level()
        exhaustion_time = self.predict_exhaustion_time()
        next_reset = self._get_next_reset_time()
        hours_to_reset = (next_reset - datetime.now(timezone.utc)).total_seconds() / 3600
        
        status = {
            'current_usage': self.current_usage,
            'daily_limit': self.daily_quota_limit,
            'remaining': remaining,
            'percentage_used': percentage_used,
            'percentage_remaining': percentage_remaining,
            'level': level.value,
            'conservation_active': self.should_activate_conservation(),
            'last_reset': self.last_reset_time.isoformat(),
            'next_reset': next_reset.isoformat(),
            'hours_to_reset': round(hours_to_reset, 1),
        }
        
        if exhaustion_time is not None:
            status['predicted_exhaustion_hours'] = round(exhaustion_time, 1)
            status['predicted_exhaustion_time'] = (
                datetime.now(timezone.utc) + timedelta(hours=exhaustion_time)
            ).isoformat()
        
        # Add usage rate information
        if self.usage_history:
            # Calculate rates over different time windows
            current_time = time.time()
            
            # Last hour
            hour_usage = sum(
                cost for timestamp, cost in self.usage_history
                if timestamp > current_time - 3600
            )
            status['hourly_usage_rate'] = hour_usage
            
            # Last 15 minutes
            quarter_usage = sum(
                cost for timestamp, cost in self.usage_history
                if timestamp > current_time - 900
            )
            status['quarter_hourly_usage_rate'] = quarter_usage * 4  # Projected to hourly
        
        return status
    
    # Private methods
    
    def _get_quota_level(self) -> QuotaLevel:
        """Determine current quota level."""
        remaining_percentage = self.get_remaining_quota() / self.daily_quota_limit
        
        if remaining_percentage <= self.EXHAUSTED_THRESHOLD:
            return QuotaLevel.EXHAUSTED
        elif remaining_percentage <= self.CRITICAL_THRESHOLD:
            return QuotaLevel.CRITICAL
        elif remaining_percentage <= self.CAUTION_THRESHOLD:
            return QuotaLevel.CAUTION
        else:
            return QuotaLevel.HEALTHY
    
    def _get_last_reset_time(self) -> datetime:
        """Calculate the last quota reset time."""
        now = datetime.now(timezone.utc)
        
        # Calculate today's reset time (8 AM UTC = midnight PST)
        # Adjust for PDT (7 AM UTC) during daylight saving time
        reset_hour = self.QUOTA_RESET_HOUR_UTC
        if self._is_pdt(now):
            reset_hour = 7
        
        today_reset = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        
        if now >= today_reset:
            return today_reset
        else:
            # If we haven't reached today's reset, use yesterday's
            return today_reset - timedelta(days=1)
    
    def _get_next_reset_time(self) -> datetime:
        """Calculate the next quota reset time."""
        last_reset = self.last_reset_time
        return last_reset + timedelta(days=1)
    
    def _is_pdt(self, dt: datetime) -> bool:
        """
        Check if given datetime is during Pacific Daylight Time.
        PDT is roughly from second Sunday in March to first Sunday in November.
        """
        # Simplified check - you might want to use pytz for accurate timezone handling
        month = dt.month
        if 4 <= month <= 10:  # April through October
            return True
        elif month == 3:  # March - check if after second Sunday
            # Simplified - assumes PDT starts mid-March
            return dt.day > 14
        elif month == 11:  # November - check if before first Sunday
            # Simplified - assumes PDT ends early November
            return dt.day < 7
        else:
            return False
    
    async def _check_quota_reset(self) -> None:
        """Check if quota should be reset."""
        next_reset = self._get_next_reset_time()
        now = datetime.now(timezone.utc)
        
        if now >= next_reset:
            await self.reset_daily_quota()
    
    async def _persist_state(self) -> None:
        """Persist current state to Redis."""
        if not self.redis_client:
            return
        
        try:
            # Save current usage
            await self.redis_client.set(self.REDIS_KEY_USAGE, str(self.current_usage))
            
            # Save usage history (keep only last 24 hours)
            current_time = time.time()
            day_ago = current_time - 86400
            recent_history = [
                (ts, cost) for ts, cost in self.usage_history
                if ts > day_ago
            ]
            await self.redis_client.set(
                self.REDIS_KEY_HISTORY,
                json.dumps(recent_history)
            )
            
            # Save last reset time
            await self.redis_client.set(
                self.REDIS_KEY_RESET,
                self.last_reset_time.isoformat()
            )
            
        except Exception as e:
            logger.error(f"Failed to persist quota state to Redis: {e}")
    
    async def _report_quota_status(self, level: QuotaLevel, operation: str) -> None:
        """Report quota status to status reporter."""
        remaining_percentage = (self.get_remaining_quota() / self.daily_quota_limit) * 100
        
        if level == QuotaLevel.EXHAUSTED:
            user_message = f"⚠️ YouTube API quota nearly exhausted ({remaining_percentage:.0f}% remaining). Switching to fallback methods."
            report_api_quota_exceeded("youtube", user_message)
        elif level == QuotaLevel.CRITICAL:
            user_message = f"⚠️ YouTube API quota critical ({remaining_percentage:.0f}% remaining). Conservation mode active."
            report = StatusReport(
                platform="youtube",
                method=SearchMethod.API_SEARCH,
                status=PlatformStatus.QUOTA_EXCEEDED,
                result=OperationResult.PARTIAL_SUCCESS,
                message=f"YouTube API quota critical after {operation}",
                user_message=user_message,
                timestamp=datetime.utcnow(),
                details={'remaining_percentage': remaining_percentage}
            )
            self.status_reporter.add_report(report)
    
    async def _report_quota_reset(self) -> None:
        """Report quota reset to status reporter."""
        report = StatusReport(
            platform="youtube",
            method=SearchMethod.API_SEARCH,
            status=PlatformStatus.HEALTHY,
            result=OperationResult.SUCCESS,
            message="YouTube API quota reset",
            user_message="✅ YouTube API quota has been reset. Full quota available.",
            timestamp=datetime.utcnow(),
            details={'daily_limit': self.daily_quota_limit}
        )
        self.status_reporter.add_report(report)
    
    @tasks.loop(hours=1)
    async def _daily_reset_task(self):
        """Task that runs every hour to check if quota should be reset."""
        try:
            await self._check_quota_reset()
        except Exception as e:
            logger.error(f"Error in daily quota reset task: {e}")
    
    @_daily_reset_task.before_loop
    async def _before_daily_reset_task(self):
        """Wait for the bot to be ready before starting the task."""
        # Wait a bit for initialization
        await asyncio.sleep(5)
    
    async def cleanup(self):
        """Cleanup resources and stop background tasks."""
        # Stop the daily reset task
        self._daily_reset_task.cancel()
        
        # Final state persistence
        await self._persist_state()
        
        logger.info("Quota monitor cleanup completed")


# Helper functions for easy integration

async def create_quota_monitor(config: Dict[str, any], redis_client: Optional[aioredis.Redis] = None) -> QuotaMonitor:
    """
    Create and initialize a quota monitor instance.
    
    Args:
        config: Configuration dictionary
        redis_client: Optional Redis client
        
    Returns:
        Initialized QuotaMonitor instance
    """
    monitor = QuotaMonitor(config, redis_client)
    await monitor.initialize()
    return monitor