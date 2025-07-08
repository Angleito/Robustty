"""
Connection health monitoring service for proactive detection and handling of connectivity issues.
Monitors Discord gateway, Redis, and platform API connectivity with automatic recovery.

VPS-Specific Optimizations:
- Environment detection: Automatically detects VPS deployment and adjusts parameters
- Longer check intervals: 60s on VPS vs 30s on local/Docker to reduce load
- Higher failure tolerance: 5 consecutive failures before marking unhealthy (vs 3)
- Timeout multiplier: 2x longer timeouts for all operations on VPS
- Network error tolerance: Distinguishes between network and API errors
- Adaptive thresholds: More lenient for recent network errors on VPS
- Extended recovery delays: Longer backoff periods to avoid overwhelming unstable networks
"""

import asyncio
import logging
import os
import socket
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field

import aiohttp
import discord
from prometheus_client import Gauge, Counter, Histogram

from ..utils.network_routing import discord_session, platform_session

# Try importing Redis modules
try:
    import redis.asyncio as aioredis
except ImportError:
    try:
        import aioredis
    except ImportError:
        aioredis = None

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Connection status enumeration"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class DeploymentEnvironment(Enum):
    """Deployment environment types"""
    LOCAL = "local"
    DOCKER = "docker"
    VPS = "vps"


class ErrorCategory(Enum):
    """Error categorization for better handling"""
    NETWORK = "network"  # Network connectivity issues
    API = "api"  # API-specific errors (rate limits, auth)
    TIMEOUT = "timeout"  # Request timeouts
    UNKNOWN = "unknown"  # Other errors


@dataclass
class HealthCheckResult:
    """Result of a health check"""

    status: ConnectionStatus
    response_time: float
    error: Optional[str] = None
    error_category: ErrorCategory = ErrorCategory.UNKNOWN
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConnectionHealth:
    """Health information for a connection"""

    status: ConnectionStatus = ConnectionStatus.UNKNOWN
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    error_count: int = 0
    avg_response_time: float = 0.0
    recovery_attempts: int = 0


class HealthMonitor:
    """
    Comprehensive health monitoring service for Discord bot connectivity.

    Monitors:
    - Discord gateway connection
    - Redis connection
    - Platform API connectivity (YouTube, PeerTube, etc.)
    - Bot voice connections

    Features:
    - Periodic health checks every 30 seconds
    - Automatic reconnection with exponential backoff
    - Prometheus metrics integration
    - Connection recovery logging
    """

    def __init__(self, bot, config: Dict[str, Any]):
        self.bot = bot
        self.config = config
        self.health_config = config.get("health_monitor", {})
        self.is_running = False
        
        # Detect deployment environment
        self.environment = self._detect_environment()
        logger.info(f"Health monitor initialized in {self.environment.value} environment")
        
        # Set environment-specific parameters
        if self.environment == DeploymentEnvironment.VPS:
            # VPS: Less aggressive checking, more tolerance for failures
            self.check_interval = self.health_config.get("check_interval", 60)  # 1 minute
            self.max_consecutive_failures = self.health_config.get(
                "max_consecutive_failures", 5  # Allow more failures before marking unhealthy
            )
            self.timeout_multiplier = 2.0  # Double all timeouts
            self.network_tolerance = 3  # Allow more network errors before marking unhealthy
        else:
            # Local/Docker: Standard parameters
            self.check_interval = self.health_config.get("check_interval", 30)  # 30 seconds
            self.max_consecutive_failures = self.health_config.get(
                "max_consecutive_failures", 3
            )
            self.timeout_multiplier = 1.0
            self.network_tolerance = 2
        
        self.recovery_callbacks: Dict[str, Callable] = {}
        
        # Track error categories for better decision making
        self.error_history: Dict[str, List[ErrorCategory]] = {}

        # Recovery configuration
        self.recovery_config = self.health_config.get("recovery", {})
        self.max_recovery_attempts = self.recovery_config.get("max_attempts", 5)
        self.use_exponential_backoff = self.recovery_config.get(
            "exponential_backoff", True
        )
        self.max_recovery_delay = self.recovery_config.get(
            "max_delay", 300
        )  # 5 minutes

        # Connection health tracking
        self.connection_health: Dict[str, ConnectionHealth] = {
            "discord_gateway": ConnectionHealth(),
            "redis": ConnectionHealth(),
            "voice_connections": ConnectionHealth(),
        }

        # Add platform health tracking - will be populated when platforms are loaded
        # This will be updated in the health check loop
        
        # Network error tracking for VPS-specific handling
        self.network_error_counts: Dict[str, int] = {}
        self.last_network_error: Dict[str, datetime] = {}

        # Prometheus metrics
        self.setup_metrics()

        # Health check tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._recovery_tasks: Set[asyncio.Task] = set()

        logger.info(
            f"Health monitor initialized - Environment: {self.environment.value}, "
            f"Check interval: {self.check_interval}s, "
            f"Max failures: {self.max_consecutive_failures}, "
            f"Timeout multiplier: {self.timeout_multiplier}x"
        )

    def setup_metrics(self):
        """Setup Prometheus metrics for health monitoring"""
        # Connection status gauge (0=unknown, 1=healthy, 2=degraded, 3=unhealthy)
        self.connection_status_gauge = Gauge(
            "robustty_connection_status",
            "Connection status for various services",
            ["service"],
        )

        # Health check response time
        self.health_check_duration = Histogram(
            "robustty_health_check_duration_seconds",
            "Duration of health checks",
            ["service"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        # Connection failure counter
        self.connection_failures_total = Counter(
            "robustty_connection_failures_total",
            "Total connection failures",
            ["service", "error_type", "error_category"],
        )

        # Recovery attempts counter
        self.recovery_attempts_total = Counter(
            "robustty_recovery_attempts_total",
            "Total recovery attempts",
            ["service", "status"],
        )

        # Consecutive failures gauge
        self.consecutive_failures_gauge = Gauge(
            "robustty_consecutive_failures",
            "Number of consecutive failures per service",
            ["service"],
        )

    def _detect_environment(self) -> DeploymentEnvironment:
        """Detect deployment environment (Local, Docker, VPS)"""
        # Check for Docker environment
        if os.path.exists('/.dockerenv'):
            # Running in Docker container
            # Check if it's on VPS by looking for specific indicators
            if self._is_vps_environment():
                return DeploymentEnvironment.VPS
            return DeploymentEnvironment.DOCKER
        
        # Check for VPS indicators
        if self._is_vps_environment():
            return DeploymentEnvironment.VPS
        
        # Default to local
        return DeploymentEnvironment.LOCAL
    
    def _is_vps_environment(self) -> bool:
        """Check if running on VPS by various indicators"""
        vps_indicators = [
            # Environment variables
            os.getenv('IS_VPS', '').lower() == 'true',
            os.getenv('DEPLOYMENT_TYPE', '').lower() == 'vps',
            os.getenv('REDIS_URL', '').startswith('redis://redis:'),  # Container networking
            
            # Check hostname patterns common on VPS
            'vps' in socket.gethostname().lower(),
            'server' in socket.gethostname().lower(),
            'ubuntu' in socket.gethostname().lower(),  # Common VPS hostname
            
            # Check for headless environment
            os.getenv('DISPLAY') is None and os.name == 'posix',
        ]
        
        return any(vps_indicators)

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error for better handling"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Network errors
        if any(term in error_str for term in [
            "timeout", "timed out", "connection", "network", 
            "unreachable", "refused", "reset", "broken pipe",
            "name resolution", "dns", "getaddrinfo"
        ]) or any(term in error_type for term in [
            "timeout", "connection", "oserror", "socket"
        ]):
            return ErrorCategory.NETWORK
        
        # API errors
        if any(term in error_str for term in [
            "rate limit", "quota", "429", "401", "403", 
            "unauthorized", "forbidden", "invalid key", 
            "invalid token", "authentication"
        ]):
            return ErrorCategory.API
        
        # Timeout errors
        if "asyncio.timeouterror" in error_type:
            return ErrorCategory.TIMEOUT
        
        return ErrorCategory.UNKNOWN

    async def start(self):
        """Start the health monitoring service"""
        if self.is_running:
            logger.warning("Health monitor is already running")
            return

        self.is_running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Health monitor started")

    async def stop(self):
        """Stop the health monitoring service"""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Cancel recovery tasks
        for task in self._recovery_tasks:
            task.cancel()

        if self._recovery_tasks:
            await asyncio.gather(*self._recovery_tasks, return_exceptions=True)

        logger.info("Health monitor stopped")

    async def _health_check_loop(self):
        """Main health check loop"""
        while self.is_running:
            try:
                await self._run_all_health_checks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)

    async def _run_all_health_checks(self):
        """Run all health checks concurrently"""
        tasks = [
            self._check_discord_gateway(),
            self._check_redis_connection(),
            self._check_voice_connections(),
        ]

        # Add platform health checks
        for platform_name in self.bot.platform_registry.get_enabled_platforms().keys():
            # Ensure platform health tracking exists
            platform_key = f"platform_{platform_name}"
            if platform_key not in self.connection_health:
                self.connection_health[platform_key] = ConnectionHealth()
            tasks.append(self._check_platform_api(platform_name))

        # Run all checks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and update metrics
        service_names = ["discord_gateway", "redis", "voice_connections"]
        service_names.extend(
            [
                f"platform_{name}"
                for name in self.bot.platform_registry.get_enabled_platforms().keys()
            ]
        )

        for i, result in enumerate(results):
            service_name = service_names[i]
            if isinstance(result, HealthCheckResult):
                await self._process_health_result(service_name, result)
            elif isinstance(result, Exception):
                logger.error(f"Health check failed for {service_name}: {result}")
                error_result = HealthCheckResult(
                    status=ConnectionStatus.UNHEALTHY,
                    response_time=0.0,
                    error=str(result),
                )
                await self._process_health_result(service_name, error_result)

    async def _check_discord_gateway(self) -> HealthCheckResult:
        """Check Discord gateway connection health"""
        start_time = time.time()

        try:
            if not self.bot.is_ready():
                return HealthCheckResult(
                    status=ConnectionStatus.UNHEALTHY,
                    response_time=time.time() - start_time,
                    error="Bot not ready",
                )

            # Check WebSocket connection
            if self.bot.ws is None or self.bot.ws.socket is None:
                return HealthCheckResult(
                    status=ConnectionStatus.UNHEALTHY,
                    response_time=time.time() - start_time,
                    error="WebSocket not connected",
                )

            # Check latency
            latency = self.bot.latency
            if latency == float("inf"):
                status = ConnectionStatus.UNHEALTHY
                error = "Infinite latency"
            elif latency > 1.0:
                status = ConnectionStatus.DEGRADED
                error = f"High latency: {latency:.2f}s"
            else:
                status = ConnectionStatus.HEALTHY
                error = None

            return HealthCheckResult(
                status=status,
                response_time=time.time() - start_time,
                error=error,
                details={
                    "latency": latency,
                    "guild_count": len(self.bot.guilds),
                    "user_id": self.bot.user.id if self.bot.user else None,
                },
            )

        except Exception as e:
            return HealthCheckResult(
                status=ConnectionStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                error=f"Discord gateway check failed: {str(e)}",
            )

    async def _check_redis_connection(self) -> HealthCheckResult:
        """Check Redis connection health"""
        start_time = time.time()

        # Check if Redis is enabled
        if not self.config.get("cache", {}).get("redis", {}).get("enabled", False):
            return HealthCheckResult(
                status=ConnectionStatus.HEALTHY,
                response_time=time.time() - start_time,
                details={"enabled": False},
            )

        try:
            # Get cache manager from bot
            cache_manager = getattr(self.bot, "cache_manager", None)
            if not cache_manager:
                return HealthCheckResult(
                    status=ConnectionStatus.UNHEALTHY,
                    response_time=time.time() - start_time,
                    error="Cache manager not available",
                )

            if not cache_manager.redis_client:
                return HealthCheckResult(
                    status=ConnectionStatus.UNHEALTHY,
                    response_time=time.time() - start_time,
                    error="Redis client not connected",
                )

            # Test Redis with ping
            test_key = "health_check_test"
            await cache_manager.redis_client.set(test_key, "ping", ex=10)
            result = await cache_manager.redis_client.get(test_key)

            if result != "ping":
                return HealthCheckResult(
                    status=ConnectionStatus.DEGRADED,
                    response_time=time.time() - start_time,
                    error="Redis ping test failed",
                )

            # Clean up test key
            await cache_manager.redis_client.delete(test_key)

            return HealthCheckResult(
                status=ConnectionStatus.HEALTHY,
                response_time=time.time() - start_time,
                details={"ping_success": True},
            )

        except Exception as e:
            return HealthCheckResult(
                status=ConnectionStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                error=f"Redis check failed: {str(e)}",
            )

    async def _check_voice_connections(self) -> HealthCheckResult:
        """Check voice connections health"""
        start_time = time.time()

        try:
            active_connections = 0
            unhealthy_connections = 0

            for guild_id, player in self.bot.audio_players.items():
                if player.voice_client and player.voice_client.is_connected():
                    active_connections += 1
                    # Check if connection is actually working
                    if (
                        not player.voice_client.is_playing()
                        and player.queue
                        and len(player.queue) > 0
                    ):
                        # Connection exists but not playing when it should be
                        unhealthy_connections += 1

            if unhealthy_connections > 0:
                status = ConnectionStatus.DEGRADED
                error = f"{unhealthy_connections}/{active_connections} voice connections unhealthy"
            else:
                status = ConnectionStatus.HEALTHY
                error = None

            return HealthCheckResult(
                status=status,
                response_time=time.time() - start_time,
                error=error,
                details={
                    "active_connections": active_connections,
                    "unhealthy_connections": unhealthy_connections,
                    "total_players": len(self.bot.audio_players),
                },
            )

        except Exception as e:
            return HealthCheckResult(
                status=ConnectionStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                error=f"Voice connections check failed: {str(e)}",
            )

    async def _check_platform_api(self, platform_name: str) -> HealthCheckResult:
        """Check platform API connectivity"""
        start_time = time.time()

        try:
            platform = self.bot.platform_registry.get_platform(platform_name)
            if not platform or not platform.enabled:
                return HealthCheckResult(
                    status=ConnectionStatus.HEALTHY,
                    response_time=time.time() - start_time,
                    details={"enabled": False},
                )

            # Test API connectivity with a simple search
            test_query = "test"
            try:
                # Apply timeout based on environment
                timeout = aiohttp.ClientTimeout(total=30 * self.timeout_multiplier)
                
                # Create platform-specific timeout context if needed
                if hasattr(platform, 'search_videos_with_timeout'):
                    results = await platform.search_videos_with_timeout(
                        test_query, max_results=1, timeout=timeout.total
                    )
                else:
                    # Use asyncio timeout for platforms without built-in timeout
                    results = await asyncio.wait_for(
                        platform.search_videos(test_query, max_results=1),
                        timeout=timeout.total
                    )

                # Check if we got results or if it's just an empty response
                if results is not None:
                    status = ConnectionStatus.HEALTHY
                    error = None
                else:
                    status = ConnectionStatus.DEGRADED
                    error = "API returned empty results"

            except Exception as api_error:
                # Categorize the error
                error_category = self._categorize_error(api_error)
                
                # Determine status based on error category and environment
                if error_category == ErrorCategory.NETWORK:
                    # Track network errors for VPS
                    platform_key = f"platform_{platform_name}"
                    self.network_error_counts[platform_key] = \
                        self.network_error_counts.get(platform_key, 0) + 1
                    self.last_network_error[platform_key] = datetime.now()
                    
                    # Be more tolerant of network errors on VPS
                    if self.environment == DeploymentEnvironment.VPS:
                        if self.network_error_counts.get(platform_key, 0) < self.network_tolerance:
                            status = ConnectionStatus.DEGRADED
                        else:
                            status = ConnectionStatus.UNHEALTHY
                    else:
                        status = ConnectionStatus.UNHEALTHY
                        
                elif error_category == ErrorCategory.API:
                    # API errors are usually not transient
                    if "rate limit" in str(api_error).lower() or "429" in str(api_error):
                        status = ConnectionStatus.DEGRADED
                    else:
                        status = ConnectionStatus.UNHEALTHY
                        
                elif error_category == ErrorCategory.TIMEOUT:
                    # Timeouts might be more common on VPS
                    if self.environment == DeploymentEnvironment.VPS:
                        status = ConnectionStatus.DEGRADED
                    else:
                        status = ConnectionStatus.UNHEALTHY
                else:
                    status = ConnectionStatus.DEGRADED

                error = f"API test failed ({error_category.value}): {str(api_error)}"

            return HealthCheckResult(
                status=status,
                response_time=time.time() - start_time,
                error=error,
                error_category=error_category if 'error_category' in locals() else ErrorCategory.UNKNOWN,
                details={
                    "platform": platform_name, 
                    "enabled": platform.enabled,
                    "error_category": error_category.value if 'error_category' in locals() else None,
                    "network_errors": self.network_error_counts.get(f"platform_{platform_name}", 0)
                },
            )

        except Exception as e:
            return HealthCheckResult(
                status=ConnectionStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                error=f"Platform {platform_name} check failed: {str(e)}",
            )

    async def _process_health_result(
        self, service_name: str, result: HealthCheckResult
    ):
        """Process health check result and update metrics"""
        health = self.connection_health[service_name]

        # Update health information
        health.last_check = result.timestamp

        if result.status == ConnectionStatus.HEALTHY:
            health.consecutive_failures = 0
            health.last_success = result.timestamp
            health.recovery_attempts = 0
        else:
            health.consecutive_failures += 1
            health.last_failure = result.timestamp
            health.error_count += 1

            # Record failure in metrics
            error_type = "connection_error" if result.error else "unknown"
            error_category = result.error_category.value if hasattr(result, 'error_category') else "unknown"
            self.connection_failures_total.labels(
                service=service_name, 
                error_type=error_type,
                error_category=error_category
            ).inc()
            
            # Reset network error count if healthy
            if result.status == ConnectionStatus.HEALTHY and service_name in self.network_error_counts:
                self.network_error_counts[service_name] = 0

        # Update connection status
        health.status = result.status

        # Update average response time (simple moving average)
        if health.avg_response_time == 0:
            health.avg_response_time = result.response_time
        else:
            health.avg_response_time = (health.avg_response_time * 0.8) + (
                result.response_time * 0.2
            )

        # Update Prometheus metrics
        status_value = {
            ConnectionStatus.UNKNOWN: 0,
            ConnectionStatus.HEALTHY: 1,
            ConnectionStatus.DEGRADED: 2,
            ConnectionStatus.UNHEALTHY: 3,
        }[result.status]

        self.connection_status_gauge.labels(service=service_name).set(status_value)
        self.health_check_duration.labels(service=service_name).observe(
            result.response_time
        )
        self.consecutive_failures_gauge.labels(service=service_name).set(
            health.consecutive_failures
        )
        
        # Check if we should reduce severity for VPS network issues
        if (self.environment == DeploymentEnvironment.VPS and 
            service_name in self.network_error_counts and 
            self.network_error_counts[service_name] > 0):
            
            # Check if network errors are recent
            if service_name in self.last_network_error:
                time_since_error = datetime.now() - self.last_network_error[service_name]
                if time_since_error < timedelta(minutes=5):
                    # Recent network errors on VPS - be more tolerant
                    actual_threshold = self.max_consecutive_failures + 2
                else:
                    actual_threshold = self.max_consecutive_failures
            else:
                actual_threshold = self.max_consecutive_failures
        else:
            actual_threshold = self.max_consecutive_failures
        
        # Update platform prioritization if this is a platform health check
        if service_name.startswith("platform_"):
            platform_name = service_name.replace("platform_", "")
            try:
                from src.services.platform_prioritization import get_prioritization_manager
                prioritization_manager = get_prioritization_manager()
                if prioritization_manager:
                    prioritization_manager.update_platform_health(platform_name, result.status)
            except ImportError:
                pass  # Prioritization manager not available

        # Log health status changes
        if result.status != ConnectionStatus.HEALTHY:
            log_level = (
                logging.WARNING
                if result.status == ConnectionStatus.DEGRADED
                else logging.ERROR
            )
            logger.log(
                log_level,
                f"Health check failed for {service_name}: {result.error} "
                f"(consecutive failures: {health.consecutive_failures})",
            )

        # Update platform prioritization manager with health status
        if service_name.startswith("platform_"):
            platform_name = service_name.replace("platform_", "")
            try:
                from .platform_prioritization import get_prioritization_manager
                prioritization_manager = get_prioritization_manager()
                if prioritization_manager:
                    prioritization_manager.update_platform_health(platform_name, result.status)
            except ImportError:
                pass  # Platform prioritization not available

        # Trigger recovery if needed
        if (
            health.consecutive_failures >= actual_threshold
            and result.status == ConnectionStatus.UNHEALTHY
        ):
            await self._trigger_recovery(service_name, health)

    async def _trigger_recovery(self, service_name: str, health: ConnectionHealth):
        """Trigger recovery for unhealthy service"""
        if health.recovery_attempts >= self.max_recovery_attempts:
            logger.error(f"Maximum recovery attempts reached for {service_name}")
            return

        health.recovery_attempts += 1
        self.recovery_attempts_total.labels(
            service=service_name, status="started"
        ).inc()

        logger.info(
            f"Triggering recovery for {service_name} (attempt {health.recovery_attempts})"
        )

        # Create recovery task
        recovery_task = asyncio.create_task(self._recover_service(service_name, health))
        self._recovery_tasks.add(recovery_task)

        # Remove task when complete
        recovery_task.add_done_callback(self._recovery_tasks.discard)

    async def _recover_service(self, service_name: str, health: ConnectionHealth):
        """Attempt to recover a service"""
        try:
            # Calculate delay based on configuration and environment
            if self.use_exponential_backoff:
                base_delay = 10 if self.environment != DeploymentEnvironment.VPS else 20
                delay = min(
                    self.max_recovery_delay, base_delay * (2 ** (health.recovery_attempts - 1))
                )
            else:
                base_delay = 30 if self.environment != DeploymentEnvironment.VPS else 60
                delay = min(self.max_recovery_delay, base_delay * health.recovery_attempts)
            
            # Apply timeout multiplier for VPS
            delay *= self.timeout_multiplier

            logger.info(f"Waiting {delay}s before recovery attempt for {service_name}")
            await asyncio.sleep(delay)

            success = False

            if service_name == "discord_gateway":
                success = await self._recover_discord_gateway()
            elif service_name == "redis":
                success = await self._recover_redis_connection()
            elif service_name.startswith("platform_"):
                platform_name = service_name.replace("platform_", "")
                success = await self._recover_platform_api(platform_name)
            elif service_name == "voice_connections":
                success = await self._recover_voice_connections()

            if success:
                logger.info(f"Successfully recovered {service_name}")
                self.recovery_attempts_total.labels(
                    service=service_name, status="success"
                ).inc()
                health.recovery_attempts = 0
            else:
                logger.warning(f"Recovery attempt failed for {service_name}")
                self.recovery_attempts_total.labels(
                    service=service_name, status="failed"
                ).inc()

        except Exception as e:
            logger.error(f"Recovery error for {service_name}: {e}", exc_info=True)
            self.recovery_attempts_total.labels(
                service=service_name, status="error"
            ).inc()

    async def _recover_discord_gateway(self) -> bool:
        """Attempt to recover Discord gateway connection"""
        try:
            if self.bot.is_closed():
                logger.info("Bot is closed, cannot recover gateway connection")
                return False

            # Try to reconnect if WebSocket is not connected
            if self.bot.ws is None or self.bot.ws.socket is None:
                logger.info("Attempting to reconnect Discord gateway")
                await self.bot.connect(reconnect=True)
                return True

            return True
        except Exception as e:
            logger.error(f"Failed to recover Discord gateway: {e}")
            return False

    async def _recover_redis_connection(self) -> bool:
        """Attempt to recover Redis connection"""
        try:
            cache_manager = getattr(self.bot, "cache_manager", None)
            if cache_manager:
                # Try to reinitialize Redis connection
                await cache_manager.close()
                await cache_manager.initialize()
                return cache_manager.redis_client is not None
            return False
        except Exception as e:
            logger.error(f"Failed to recover Redis connection: {e}")
            return False

    async def _recover_platform_api(self, platform_name: str) -> bool:
        """Attempt to recover platform API connection"""
        try:
            platform = self.bot.platform_registry.get_platform(platform_name)
            if platform:
                # Reinitialize platform
                await platform.cleanup()
                await platform.initialize()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to recover platform {platform_name}: {e}")
            return False

    async def _recover_voice_connections(self) -> bool:
        """Attempt to recover voice connections"""
        try:
            recovered_count = 0
            for guild_id, player in self.bot.audio_players.items():
                if player.voice_client and not player.voice_client.is_connected():
                    try:
                        # Try to reconnect voice client
                        if player.voice_client.channel:
                            await player.voice_client.connect(reconnect=True)
                            recovered_count += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to recover voice connection for guild {guild_id}: {e}"
                        )

            logger.info(f"Recovered {recovered_count} voice connections")
            return recovered_count > 0
        except Exception as e:
            logger.error(f"Failed to recover voice connections: {e}")
            return False

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status for all monitored services"""
        status = {}
        overall_status = ConnectionStatus.HEALTHY

        for service_name, health in self.connection_health.items():
            service_status = {
                "status": health.status.value,
                "last_check": (
                    health.last_check.isoformat() if health.last_check else None
                ),
                "consecutive_failures": health.consecutive_failures,
                "last_success": (
                    health.last_success.isoformat() if health.last_success else None
                ),
                "last_failure": (
                    health.last_failure.isoformat() if health.last_failure else None
                ),
                "error_count": health.error_count,
                "avg_response_time": health.avg_response_time,
                "recovery_attempts": health.recovery_attempts,
            }

            status[service_name] = service_status

            # Determine overall status
            if health.status == ConnectionStatus.UNHEALTHY:
                overall_status = ConnectionStatus.UNHEALTHY
            elif (
                health.status == ConnectionStatus.DEGRADED
                and overall_status == ConnectionStatus.HEALTHY
            ):
                overall_status = ConnectionStatus.DEGRADED

        return {
            "overall_status": overall_status.value,
            "services": status,
            "timestamp": datetime.now().isoformat(),
            "environment": self.environment.value,
            "check_interval": self.check_interval,
            "timeout_multiplier": self.timeout_multiplier,
            "network_error_counts": dict(self.network_error_counts),
        }

    def register_recovery_callback(self, service_name: str, callback: Callable):
        """Register custom recovery callback for a service"""
        self.recovery_callbacks[service_name] = callback
