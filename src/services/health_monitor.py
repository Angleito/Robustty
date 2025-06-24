"""
Connection health monitoring service for proactive detection and handling of connectivity issues.
Monitors Discord gateway, Redis, and platform API connectivity with automatic recovery.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field

import aiohttp
import discord
from prometheus_client import Gauge, Counter, Histogram

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


@dataclass
class HealthCheckResult:
    """Result of a health check"""

    status: ConnectionStatus
    response_time: float
    error: Optional[str] = None
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
        self.check_interval = self.health_config.get("check_interval", 30)  # seconds
        self.max_consecutive_failures = self.health_config.get(
            "max_consecutive_failures", 3
        )
        self.recovery_callbacks: Dict[str, Callable] = {}

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

        # Prometheus metrics
        self.setup_metrics()

        # Health check tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._recovery_tasks: Set[asyncio.Task] = set()

        logger.info("Health monitor initialized")

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
            ["service", "error_type"],
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
                results = await platform.search_videos(test_query, max_results=1)

                # Check if we got results or if it's just an empty response
                if results is not None:
                    status = ConnectionStatus.HEALTHY
                    error = None
                else:
                    status = ConnectionStatus.DEGRADED
                    error = "API returned empty results"

            except Exception as api_error:
                # Check error type to determine status
                error_str = str(api_error).lower()
                if any(
                    term in error_str for term in ["timeout", "connection", "network"]
                ):
                    status = ConnectionStatus.UNHEALTHY
                elif any(term in error_str for term in ["rate limit", "quota", "429"]):
                    status = ConnectionStatus.DEGRADED
                elif any(
                    term in error_str for term in ["auth", "key", "token", "401", "403"]
                ):
                    status = ConnectionStatus.UNHEALTHY
                else:
                    status = ConnectionStatus.DEGRADED

                error = f"API test failed: {str(api_error)}"

            return HealthCheckResult(
                status=status,
                response_time=time.time() - start_time,
                error=error,
                details={"platform": platform_name, "enabled": platform.enabled},
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
            self.connection_failures_total.labels(
                service=service_name, error_type=error_type
            ).inc()

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

        # Trigger recovery if needed
        if (
            health.consecutive_failures >= self.max_consecutive_failures
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
            # Calculate delay based on configuration
            if self.use_exponential_backoff:
                delay = min(
                    self.max_recovery_delay, 10 * (2 ** (health.recovery_attempts - 1))
                )
            else:
                delay = min(self.max_recovery_delay, 30 * health.recovery_attempts)

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
        }

    def register_recovery_callback(self, service_name: str, callback: Callable):
        """Register custom recovery callback for a service"""
        self.recovery_callbacks[service_name] = callback
