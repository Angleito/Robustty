"""Cookie synchronization recovery system for VPS deployments

This service handles cookie synchronization failures and implements
recovery mechanisms for VPS environments that depend on external
cookie sources.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
import aiohttp
import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class SyncAttempt:
    """Represents a cookie synchronization attempt"""
    timestamp: datetime
    source: str
    platform: str
    success: bool
    error: Optional[str] = None
    cookies_synced: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'platform': self.platform,
            'success': self.success,
            'error': self.error,
            'cookies_synced': self.cookies_synced
        }


@dataclass
class RecoveryAction:
    """Represents a recovery action taken"""
    timestamp: datetime
    action_type: str
    description: str
    platforms_affected: List[str]
    success: bool
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class CookieSyncRecovery:
    """Handles cookie synchronization failures and recovery"""
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Configuration
        self.sync_check_interval = config.get('sync_check_interval_minutes', 15)
        self.max_sync_failures = config.get('max_sync_failures', 3)
        self.recovery_timeout_hours = config.get('recovery_timeout_hours', 2)
        self.enable_auto_recovery = config.get('enable_auto_recovery', True)
        
        # External sync sources
        self.sync_sources = config.get('sync_sources', [])
        self.fallback_sources = config.get('fallback_sources', [])
        
        # Paths
        self.cookie_dir = Path(config.get('cookie_directory', '/app/cookies'))
        self.sync_log_file = self.cookie_dir / 'sync_recovery.log'
        self.failure_state_file = self.cookie_dir / 'sync_failures.json'
        
        # State tracking
        self.sync_attempts: List[SyncAttempt] = []
        self.recovery_actions: List[RecoveryAction] = []
        self.consecutive_failures = 0
        self.last_successful_sync: Optional[datetime] = None
        self.recovery_in_progress = False
        
        # Dependencies
        self.cookie_health_monitor = None
        self.fallback_manager = None
        self.cookie_manager = None
        
        # Recovery strategies
        self.recovery_strategies = [
            self._try_alternative_sources,
            self._request_manual_sync,
            self._activate_emergency_fallback,
            self._notify_administrators
        ]
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    def set_dependencies(self, cookie_health_monitor, fallback_manager, cookie_manager):
        """Set service dependencies"""
        self.cookie_health_monitor = cookie_health_monitor
        self.fallback_manager = fallback_manager
        self.cookie_manager = cookie_manager
        
    async def start(self):
        """Start the cookie sync recovery service"""
        logger.info("Starting cookie synchronization recovery service")
        
        # Ensure directories exist
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        
        # Load previous state
        await self._load_failure_state()
        
        # Start monitoring
        self._monitor_task = asyncio.create_task(self._monitor_sync_health())
        
    async def stop(self):
        """Stop the recovery service"""
        logger.info("Stopping cookie synchronization recovery service")
        
        self._stop_event.set()
        
        if self._monitor_task:
            try:
                await asyncio.wait_for(self._monitor_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Recovery service stop timed out")
                self._monitor_task.cancel()
        
        # Save state
        await self._save_failure_state()
        
    async def check_sync_health(self) -> Dict[str, Any]:
        """Check the health of cookie synchronization"""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'sync_healthy': True,
            'issues': [],
            'last_successful_sync': self.last_successful_sync.isoformat() if self.last_successful_sync else None,
            'consecutive_failures': self.consecutive_failures,
            'recovery_in_progress': self.recovery_in_progress
        }
        
        # Check for stale cookies
        if self.last_successful_sync:
            time_since_sync = datetime.now() - self.last_successful_sync
            if time_since_sync > timedelta(hours=self.recovery_timeout_hours):
                health_status['sync_healthy'] = False
                health_status['issues'].append(f"No successful sync for {time_since_sync}")
        else:
            health_status['sync_healthy'] = False
            health_status['issues'].append("No successful sync recorded")
        
        # Check consecutive failures
        if self.consecutive_failures >= self.max_sync_failures:
            health_status['sync_healthy'] = False
            health_status['issues'].append(f"Exceeded max failures ({self.consecutive_failures})")
        
        # Check cookie health if available
        if self.cookie_health_monitor:
            try:
                cookie_report = await self.cookie_health_monitor.get_health_report()
                unhealthy_platforms = cookie_report['overall_health']['unhealthy_platforms']
                if unhealthy_platforms:
                    health_status['sync_healthy'] = False
                    health_status['issues'].extend([
                        f"Cookie health issues: {', '.join(unhealthy_platforms)}"
                    ])
            except Exception as e:
                logger.error(f"Error checking cookie health: {e}")
                health_status['issues'].append(f"Cookie health check failed: {e}")
        
        return health_status
        
    async def record_sync_attempt(self, source: str, platform: str, success: bool, 
                                error: Optional[str] = None, cookies_synced: int = 0):
        """Record a cookie synchronization attempt"""
        attempt = SyncAttempt(
            timestamp=datetime.now(),
            source=source,
            platform=platform,
            success=success,
            error=error,
            cookies_synced=cookies_synced
        )
        
        self.sync_attempts.append(attempt)
        
        # Update failure tracking
        if success:
            self.consecutive_failures = 0
            self.last_successful_sync = datetime.now()
            logger.info(f"Successful cookie sync from {source} for {platform} ({cookies_synced} cookies)")
        else:
            self.consecutive_failures += 1
            logger.warning(f"Cookie sync failed from {source} for {platform}: {error}")
        
        # Trigger recovery if needed
        if not success and self.consecutive_failures >= self.max_sync_failures:
            if self.enable_auto_recovery and not self.recovery_in_progress:
                await self._initiate_recovery()
        
        # Keep only recent attempts
        cutoff = datetime.now() - timedelta(hours=24)
        self.sync_attempts = [a for a in self.sync_attempts if a.timestamp > cutoff]
        
        # Log the attempt
        await self._log_sync_attempt(attempt)
        
    async def _initiate_recovery(self):
        """Initiate recovery procedures for sync failures"""
        if self.recovery_in_progress:
            logger.info("Recovery already in progress, skipping")
            return
        
        self.recovery_in_progress = True
        logger.warning(f"Initiating cookie sync recovery after {self.consecutive_failures} consecutive failures")
        
        try:
            for i, strategy in enumerate(self.recovery_strategies):
                try:
                    logger.info(f"Attempting recovery strategy {i+1}: {strategy.__name__}")
                    
                    success = await strategy()
                    
                    action = RecoveryAction(
                        timestamp=datetime.now(),
                        action_type=strategy.__name__,
                        description=f"Recovery strategy {i+1}",
                        platforms_affected=['all'],  # Will be updated by specific strategies
                        success=success
                    )\n                    \n                    self.recovery_actions.append(action)\n                    \n                    if success:\n                        logger.info(f\"Recovery successful with strategy: {strategy.__name__}\")\n                        self.consecutive_failures = 0\n                        break\n                    else:\n                        logger.warning(f\"Recovery strategy failed: {strategy.__name__}\")\n                        \n                except Exception as e:\n                    logger.error(f\"Recovery strategy {strategy.__name__} error: {e}\")\n                    \n                    action = RecoveryAction(\n                        timestamp=datetime.now(),\n                        action_type=strategy.__name__,\n                        description=f\"Recovery strategy {i+1} failed with error\",\n                        platforms_affected=['all'],\n                        success=False,\n                        details={'error': str(e)}\n                    )\n                    self.recovery_actions.append(action)\n                    \n                # Wait between strategies\n                await asyncio.sleep(30)\n            \n            # Keep only recent recovery actions\n            cutoff = datetime.now() - timedelta(hours=48)\n            self.recovery_actions = [a for a in self.recovery_actions if a.timestamp > cutoff]\n            \n        finally:\n            self.recovery_in_progress = False\n    \n    async def _try_alternative_sources(self) -> bool:\n        \"\"\"Try to sync from alternative cookie sources\"\"\"\n        logger.info(\"Attempting sync from alternative sources\")\n        \n        if not self.fallback_sources:\n            logger.warning(\"No fallback sources configured\")\n            return False\n        \n        for source in self.fallback_sources:\n            try:\n                logger.info(f\"Trying fallback source: {source}\")\n                \n                # This would implement actual sync logic based on source type\n                # For now, we'll simulate the attempt\n                success = await self._attempt_sync_from_source(source)\n                \n                if success:\n                    logger.info(f\"Successful sync from fallback source: {source}\")\n                    return True\n                    \n            except Exception as e:\n                logger.error(f\"Failed to sync from fallback source {source}: {e}\")\n        \n        return False\n    \n    async def _attempt_sync_from_source(self, source: str) -> bool:\n        \"\"\"Attempt to sync cookies from a specific source\"\"\"\n        # This is a placeholder for actual sync implementation\n        # In practice, this would:\n        # 1. Connect to the source (HTTP endpoint, file share, etc.)\n        # 2. Download cookie files\n        # 3. Validate and save them\n        # 4. Update cookie managers\n        \n        logger.debug(f\"Simulating sync attempt from {source}\")\n        \n        # For demonstration, we'll check if source is \"healthy\"\n        if 'healthy' in source.lower() or 'backup' in source.lower():\n            # Simulate successful sync\n            await asyncio.sleep(1)\n            return True\n        else:\n            # Simulate failed sync\n            await asyncio.sleep(0.5)\n            return False\n    \n    async def _request_manual_sync(self) -> bool:\n        \"\"\"Request manual intervention for cookie sync\"\"\"\n        logger.info(\"Requesting manual cookie synchronization\")\n        \n        # Create a request file for external monitoring\n        request_file = self.cookie_dir / 'manual_sync_request.json'\n        \n        request_data = {\n            'timestamp': datetime.now().isoformat(),\n            'reason': 'Automatic sync recovery failed',\n            'consecutive_failures': self.consecutive_failures,\n            'last_successful_sync': self.last_successful_sync.isoformat() if self.last_successful_sync else None,\n            'required_platforms': ['youtube', 'rumble', 'odysee', 'peertube'],\n            'priority': 'high' if self.consecutive_failures > 5 else 'medium'\n        }\n        \n        try:\n            async with aiofiles.open(request_file, 'w') as f:\n                await f.write(json.dumps(request_data, indent=2))\n            \n            logger.info(f\"Manual sync request created: {request_file}\")\n            \n            # Wait for manual sync (check for response file)\n            response_file = self.cookie_dir / 'manual_sync_response.json'\n            \n            # Wait up to 30 minutes for manual intervention\n            timeout = 30 * 60  # 30 minutes\n            start_time = time.time()\n            \n            while time.time() - start_time < timeout:\n                if response_file.exists():\n                    try:\n                        async with aiofiles.open(response_file, 'r') as f:\n                            response = json.loads(await f.read())\n                        \n                        if response.get('success', False):\n                            logger.info(\"Manual sync completed successfully\")\n                            # Clean up request/response files\n                            request_file.unlink(missing_ok=True)\n                            response_file.unlink(missing_ok=True)\n                            return True\n                        else:\n                            logger.warning(f\"Manual sync failed: {response.get('error', 'Unknown error')}\")\n                            return False\n                            \n                    except Exception as e:\n                        logger.error(f\"Error reading manual sync response: {e}\")\n                        return False\n                \n                await asyncio.sleep(60)  # Check every minute\n            \n            logger.warning(\"Manual sync request timed out\")\n            return False\n            \n        except Exception as e:\n            logger.error(f\"Failed to create manual sync request: {e}\")\n            return False\n    \n    async def _activate_emergency_fallback(self) -> bool:\n        \"\"\"Activate emergency fallback mode for all platforms\"\"\"\n        logger.warning(\"Activating emergency fallback mode\")\n        \n        if not self.fallback_manager:\n            logger.error(\"Fallback manager not available\")\n            return False\n        \n        try:\n            platforms = ['youtube', 'rumble', 'odysee', 'peertube']\n            \n            for platform in platforms:\n                if not self.fallback_manager.is_platform_in_fallback(platform):\n                    self.fallback_manager.activate_fallback(\n                        platform, \n                        \"Emergency activation due to sync failure\"\n                    )\n            \n            logger.warning(\"Emergency fallback mode activated for all platforms\")\n            return True\n            \n        except Exception as e:\n            logger.error(f\"Failed to activate emergency fallback: {e}\")\n            return False\n    \n    async def _notify_administrators(self) -> bool:\n        \"\"\"Notify administrators of critical sync failure\"\"\"\n        logger.critical(\"Notifying administrators of critical cookie sync failure\")\n        \n        # Create an alert file\n        alert_file = self.cookie_dir / 'critical_sync_alert.json'\n        \n        alert_data = {\n            'timestamp': datetime.now().isoformat(),\n            'severity': 'critical',\n            'issue': 'Cookie synchronization complete failure',\n            'consecutive_failures': self.consecutive_failures,\n            'last_successful_sync': self.last_successful_sync.isoformat() if self.last_successful_sync else None,\n            'affected_platforms': ['youtube', 'rumble', 'odysee', 'peertube'],\n            'recovery_attempts': len(self.recovery_actions),\n            'recommended_actions': [\n                'Check cookie source availability',\n                'Manually sync cookies from development environment',\n                'Verify VPS network connectivity',\n                'Check cookie extraction scripts'\n            ]\n        }\n        \n        try:\n            async with aiofiles.open(alert_file, 'w') as f:\n                await f.write(json.dumps(alert_data, indent=2))\n            \n            logger.critical(f\"Critical alert created: {alert_file}\")\n            \n            # Also log to system for external monitoring\n            logger.critical(\n                f\"CRITICAL: Cookie sync failure - {self.consecutive_failures} consecutive failures, \"\n                f\"last success: {self.last_successful_sync}\"\n            )\n            \n            return True\n            \n        except Exception as e:\n            logger.error(f\"Failed to create critical alert: {e}\")\n            return False\n    \n    async def _monitor_sync_health(self):\n        \"\"\"Background monitoring of sync health\"\"\"\n        while not self._stop_event.is_set():\n            try:\n                health_status = await self.check_sync_health()\n                \n                if not health_status['sync_healthy']:\n                    logger.warning(f\"Sync health issues detected: {'; '.join(health_status['issues'])}\")\n                    \n                    # Trigger recovery if not already in progress\n                    if (not self.recovery_in_progress and \n                        self.enable_auto_recovery and \n                        self.consecutive_failures >= self.max_sync_failures):\n                        await self._initiate_recovery()\n                \n                # Wait for next check\n                try:\n                    await asyncio.wait_for(\n                        self._stop_event.wait(),\n                        timeout=self.sync_check_interval * 60\n                    )\n                except asyncio.TimeoutError:\n                    continue\n                    \n            except Exception as e:\n                logger.error(f\"Error in sync health monitoring: {e}\")\n                await asyncio.sleep(60)\n    \n    async def _log_sync_attempt(self, attempt: SyncAttempt):\n        \"\"\"Log sync attempt to file\"\"\"\n        try:\n            log_entry = f\"{attempt.timestamp.isoformat()} - {attempt.source} - {attempt.platform} - {'SUCCESS' if attempt.success else 'FAILURE'}\"\n            if attempt.error:\n                log_entry += f\" - {attempt.error}\"\n            if attempt.cookies_synced > 0:\n                log_entry += f\" - {attempt.cookies_synced} cookies\"\n            log_entry += \"\\n\"\n            \n            async with aiofiles.open(self.sync_log_file, 'a') as f:\n                await f.write(log_entry)\n                \n        except Exception as e:\n            logger.error(f\"Failed to log sync attempt: {e}\")\n    \n    async def _save_failure_state(self):\n        \"\"\"Save failure state to file\"\"\"\n        try:\n            state_data = {\n                'consecutive_failures': self.consecutive_failures,\n                'last_successful_sync': self.last_successful_sync.isoformat() if self.last_successful_sync else None,\n                'recovery_in_progress': self.recovery_in_progress,\n                'recent_attempts': [a.to_dict() for a in self.sync_attempts[-50:]]  # Keep last 50\n            }\n            \n            async with aiofiles.open(self.failure_state_file, 'w') as f:\n                await f.write(json.dumps(state_data, indent=2))\n                \n        except Exception as e:\n            logger.error(f\"Failed to save failure state: {e}\")\n    \n    async def _load_failure_state(self):\n        \"\"\"Load failure state from file\"\"\"\n        try:\n            if self.failure_state_file.exists():\n                async with aiofiles.open(self.failure_state_file, 'r') as f:\n                    state_data = json.loads(await f.read())\n                \n                self.consecutive_failures = state_data.get('consecutive_failures', 0)\n                \n                last_sync_str = state_data.get('last_successful_sync')\n                if last_sync_str:\n                    self.last_successful_sync = datetime.fromisoformat(last_sync_str)\n                \n                self.recovery_in_progress = state_data.get('recovery_in_progress', False)\n                \n                # Load recent attempts\n                for attempt_data in state_data.get('recent_attempts', []):\n                    attempt = SyncAttempt(\n                        timestamp=datetime.fromisoformat(attempt_data['timestamp']),\n                        source=attempt_data['source'],\n                        platform=attempt_data['platform'],\n                        success=attempt_data['success'],\n                        error=attempt_data.get('error'),\n                        cookies_synced=attempt_data.get('cookies_synced', 0)\n                    )\n                    self.sync_attempts.append(attempt)\n                \n                logger.info(f\"Loaded failure state: {self.consecutive_failures} consecutive failures\")\n                \n        except Exception as e:\n            logger.warning(f\"Failed to load failure state: {e}\")\n    \n    def get_recovery_report(self) -> Dict[str, Any]:\n        \"\"\"Get comprehensive recovery status report\"\"\"\n        return {\n            'timestamp': datetime.now().isoformat(),\n            'sync_status': {\n                'consecutive_failures': self.consecutive_failures,\n                'last_successful_sync': self.last_successful_sync.isoformat() if self.last_successful_sync else None,\n                'recovery_in_progress': self.recovery_in_progress\n            },\n            'recent_attempts': [\n                attempt.to_dict() for attempt in self.sync_attempts[-20:]\n            ],\n            'recovery_actions': [\n                action.to_dict() for action in self.recovery_actions[-10:]\n            ],\n            'configuration': {\n                'max_sync_failures': self.max_sync_failures,\n                'recovery_timeout_hours': self.recovery_timeout_hours,\n                'enable_auto_recovery': self.enable_auto_recovery,\n                'sync_check_interval': self.sync_check_interval\n            }\n        }