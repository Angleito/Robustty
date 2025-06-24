"""
Resilient Discord client with intelligent reconnection and gateway fallback logic.

This module extends discord.py with robust connection handling, exponential backoff,
and automatic gateway region fallback for VPS deployment reliability.
"""

import asyncio
import logging
import random
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass

import discord
from discord.gateway import DiscordWebSocket
from discord.http import HTTPClient

from .network_connectivity import get_connectivity_manager, ConnectivityStatus
from .network_resilience import (
    get_resilience_manager,
    RetryConfig,
    CircuitBreakerConfig,
    with_retry,
    NetworkResilienceError,
    MaxRetriesExceededError,
)

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Discord connection states"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class ConnectionAttempt:
    """Information about a connection attempt"""

    attempt_number: int
    timestamp: float
    gateway_used: Optional[str]
    success: bool
    error: Optional[str]
    response_time: Optional[float]


@dataclass
class ReconnectionConfig:
    """Configuration for reconnection behavior"""

    max_attempts: int = 10
    base_delay: float = 2.0
    max_delay: float = 300.0  # 5 minutes
    exponential_base: float = 2.0
    jitter_factor: float = 0.1
    fast_reconnect_threshold: int = 3  # Try fast reconnects first
    fast_reconnect_delay: float = 1.0
    gateway_rotation_threshold: int = 2  # Rotate gateway after N failures


class ResilientDiscordClient:
    """Resilient Discord client wrapper with intelligent reconnection"""

    def __init__(self, bot, config: Optional[Dict[str, Any]] = None):
        self.bot = bot
        self.config = config or {}
        self.connectivity_manager = get_connectivity_manager(config)
        self.resilience_manager = get_resilience_manager()

        # Connection state tracking
        self.connection_state = ConnectionState.DISCONNECTED
        self.connection_attempts: List[ConnectionAttempt] = []
        self.consecutive_failures = 0
        self.last_successful_connect: Optional[float] = None
        self.current_gateway: Optional[str] = None

        # Configuration
        self.reconnection_config = self._load_reconnection_config()

        # Event callbacks
        self.on_connection_lost: List[Callable] = []
        self.on_connection_restored: List[Callable] = []
        self.on_gateway_changed: List[Callable] = []

        # Setup circuit breaker for Discord connections
        self.discord_circuit_breaker = self.resilience_manager.get_circuit_breaker(
            "discord_connection",
            CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=60,
                success_threshold=2,
                timeout=30,
            ),
        )

        # Hook into bot events
        self._setup_event_hooks()

    def _load_reconnection_config(self) -> ReconnectionConfig:
        """Load reconnection configuration"""
        reconnect_config = self.config.get("network", {}).get("reconnection", {})

        return ReconnectionConfig(
            max_attempts=reconnect_config.get("max_attempts", 10),
            base_delay=reconnect_config.get("base_delay", 2.0),
            max_delay=reconnect_config.get("max_delay", 300.0),
            exponential_base=reconnect_config.get("exponential_base", 2.0),
            jitter_factor=reconnect_config.get("jitter_factor", 0.1),
            fast_reconnect_threshold=reconnect_config.get(
                "fast_reconnect_threshold", 3
            ),
            fast_reconnect_delay=reconnect_config.get("fast_reconnect_delay", 1.0),
            gateway_rotation_threshold=reconnect_config.get(
                "gateway_rotation_threshold", 2
            ),
        )

    def _setup_event_hooks(self):
        """Setup event hooks to monitor Discord connection"""

        @self.bot.event
        async def on_connect():
            """Called when bot connects to Discord"""
            await self._on_connect()

        @self.bot.event
        async def on_disconnect():
            """Called when bot disconnects from Discord"""
            await self._on_disconnect()

        @self.bot.event
        async def on_resumed():
            """Called when bot session is resumed"""
            await self._on_resumed()

    async def _on_connect(self):
        """Handle successful connection"""
        self.connection_state = ConnectionState.CONNECTED
        self.consecutive_failures = 0
        self.last_successful_connect = time.time()

        # Record successful attempt
        if self.connection_attempts:
            self.connection_attempts[-1].success = True
            self.connection_attempts[-1].response_time = (
                time.time() - self.connection_attempts[-1].timestamp
            )

        logger.info("Discord connection established successfully")

        # Notify callbacks
        for callback in self.on_connection_restored:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Connection restored callback failed: {e}")

    async def _on_disconnect(self):
        """Handle disconnection"""
        previous_state = self.connection_state
        self.connection_state = ConnectionState.DISCONNECTED

        logger.warning("Discord connection lost")

        # Only trigger callbacks if we were previously connected
        if previous_state == ConnectionState.CONNECTED:
            for callback in self.on_connection_lost:
                try:
                    await callback()
                except Exception as e:
                    logger.error(f"Connection lost callback failed: {e}")

    async def _on_resumed(self):
        """Handle session resume"""
        logger.info("Discord session resumed")
        await self._on_connect()  # Treat resume as successful connection

    def add_connection_callback(
        self, on_lost: Optional[Callable] = None, on_restored: Optional[Callable] = None
    ):
        """Add callbacks for connection state changes"""
        if on_lost:
            self.on_connection_lost.append(on_lost)
        if on_restored:
            self.on_connection_restored.append(on_restored)

    async def _calculate_reconnect_delay(self, attempt: int) -> float:
        """Calculate delay for reconnection attempt with exponential backoff and jitter"""
        config = self.reconnection_config

        # Use fast reconnect for initial attempts
        if attempt <= config.fast_reconnect_threshold:
            base_delay = config.fast_reconnect_delay
        else:
            base_delay = config.base_delay

        # Exponential backoff
        delay = min(
            base_delay * (config.exponential_base ** (attempt - 1)), config.max_delay
        )

        # Add jitter to prevent thundering herd
        jitter_range = delay * config.jitter_factor
        delay += random.uniform(-jitter_range, jitter_range)

        return max(0.1, delay)  # Minimum 100ms delay

    async def _should_rotate_gateway(self) -> bool:
        """Determine if we should try a different gateway"""
        if (
            len(self.connection_attempts)
            < self.reconnection_config.gateway_rotation_threshold
        ):
            return False

        # Check recent failures with current gateway
        recent_attempts = self.connection_attempts[
            -self.reconnection_config.gateway_rotation_threshold :
        ]
        current_gateway_failures = sum(
            1
            for attempt in recent_attempts
            if not attempt.success and attempt.gateway_used == self.current_gateway
        )

        return (
            current_gateway_failures
            >= self.reconnection_config.gateway_rotation_threshold
        )

    async def _select_optimal_gateway(self) -> Optional[str]:
        """Select the best available Discord gateway"""
        try:
            # Ensure we have current connectivity info
            await self.connectivity_manager.ensure_connectivity()

            # Try to get optimal gateway from connectivity manager
            optimal_gateway = (
                self.connectivity_manager.checker.get_optimal_discord_gateway()
            )

            if optimal_gateway and optimal_gateway != self.current_gateway:
                logger.info(f"Switching to optimal Discord gateway: {optimal_gateway}")
                self.current_gateway = optimal_gateway

                # Notify callbacks
                for callback in self.on_gateway_changed:
                    try:
                        await callback(optimal_gateway)
                    except Exception as e:
                        logger.error(f"Gateway changed callback failed: {e}")

                return optimal_gateway

            return self.current_gateway

        except Exception as e:
            logger.error(f"Failed to select optimal gateway: {e}")
            return None

    @with_retry(
        retry_config=RetryConfig(max_attempts=3, base_delay=1.0, max_delay=10.0),
        service_name="discord_gateway_selection",
    )
    async def _connect_with_resilience(
        self, token: str, reconnect: bool = True
    ) -> bool:
        """Connect to Discord with resilience and circuit breaker protection"""

        async def _actual_connect():
            """The actual connection logic"""
            self.connection_state = ConnectionState.CONNECTING

            # Select optimal gateway if needed
            if await self._should_rotate_gateway():
                await self._select_optimal_gateway()

            # Record connection attempt
            attempt = ConnectionAttempt(
                attempt_number=len(self.connection_attempts) + 1,
                timestamp=time.time(),
                gateway_used=self.current_gateway,
                success=False,
                error=None,
                response_time=None,
            )
            self.connection_attempts.append(attempt)

            try:
                # Use circuit breaker for the actual connection
                if reconnect:
                    await self.bot.start(token, reconnect=True)
                else:
                    await self.bot.login(token)
                    await self.bot.connect(reconnect=False)

                return True

            except Exception as e:
                attempt.error = str(e)
                self.consecutive_failures += 1
                logger.error(
                    f"Discord connection attempt {attempt.attempt_number} failed: {e}"
                )
                raise

        # Use circuit breaker to protect the connection
        return await self.discord_circuit_breaker.call(_actual_connect)

    async def connect_with_fallback(self, token: str) -> bool:
        """Connect to Discord with intelligent fallback and retry logic"""
        logger.info("Starting resilient Discord connection...")

        # Run connectivity check first
        connectivity_result = await self.connectivity_manager.ensure_connectivity()

        if connectivity_result.status == ConnectivityStatus.FAILED:
            logger.error(
                "Network connectivity check failed - cannot connect to Discord"
            )
            return False

        elif connectivity_result.status == ConnectivityStatus.DEGRADED:
            logger.warning(
                "Network connectivity is degraded - connection may be unstable"
            )

        # Try connection with retries
        for attempt in range(1, self.reconnection_config.max_attempts + 1):
            try:
                logger.info(
                    f"Discord connection attempt {attempt}/{self.reconnection_config.max_attempts}"
                )

                success = await self._connect_with_resilience(token, reconnect=True)
                if success:
                    logger.info("Discord connection established successfully!")
                    return True

            except MaxRetriesExceededError as e:
                logger.error(
                    f"Connection attempt {attempt} failed after all retries: {e}"
                )

            except NetworkResilienceError as e:
                logger.error(f"Network resilience error on attempt {attempt}: {e}")

            except Exception as e:
                logger.error(f"Unexpected error on connection attempt {attempt}: {e}")

            # Don't delay after the last attempt
            if attempt < self.reconnection_config.max_attempts:
                delay = await self._calculate_reconnect_delay(attempt)
                logger.info(f"Waiting {delay:.1f}s before next connection attempt...")
                await asyncio.sleep(delay)

                # Check if we should rotate gateway
                if await self._should_rotate_gateway():
                    await self._select_optimal_gateway()

        logger.error(
            f"Failed to establish Discord connection after {self.reconnection_config.max_attempts} attempts"
        )
        self.connection_state = ConnectionState.FAILED
        return False

    async def handle_reconnection(self) -> bool:
        """Handle automatic reconnection after connection loss"""
        if self.connection_state in [
            ConnectionState.CONNECTING,
            ConnectionState.RECONNECTING,
        ]:
            logger.debug("Reconnection already in progress")
            return False

        self.connection_state = ConnectionState.RECONNECTING
        logger.info("Starting automatic reconnection...")

        # Wait for basic connectivity if needed
        if not await self.connectivity_manager.checker.check_basic_connectivity():
            logger.info("Waiting for network connectivity to be restored...")
            if not await self.connectivity_manager.wait_for_connectivity(
                max_wait_time=300
            ):
                logger.error("Network connectivity not restored - cannot reconnect")
                return False

        # Try to reconnect using the existing bot connection
        try:
            # Let discord.py handle its own reconnection logic first
            if hasattr(self.bot, "ws") and self.bot.ws and not self.bot.ws.is_closed():
                logger.info("Attempting to resume Discord session...")
                await self.bot.ws.resume()
                return True

            # If session can't be resumed, do a full reconnect
            logger.info("Attempting full Discord reconnection...")
            if hasattr(self.bot, "_connection") and self.bot._connection:
                await self.bot._connection.reconnect()
                return True

        except Exception as e:
            logger.warning(
                f"Automatic reconnection failed, trying manual reconnection: {e}"
            )

            # Fall back to manual reconnection
            token = (
                getattr(self.bot, "http", {}).token
                if hasattr(self.bot, "http")
                else None
            )
            if token:
                return await self.connect_with_fallback(token)

        return False

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        successful_attempts = sum(
            1 for attempt in self.connection_attempts if attempt.success
        )
        failed_attempts = len(self.connection_attempts) - successful_attempts

        avg_response_time = 0.0
        if successful_attempts > 0:
            response_times = [
                attempt.response_time
                for attempt in self.connection_attempts
                if attempt.success and attempt.response_time
            ]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)

        return {
            "connection_state": self.connection_state.value,
            "current_gateway": self.current_gateway,
            "total_attempts": len(self.connection_attempts),
            "successful_attempts": successful_attempts,
            "failed_attempts": failed_attempts,
            "consecutive_failures": self.consecutive_failures,
            "last_successful_connect": self.last_successful_connect,
            "average_response_time": avg_response_time,
            "circuit_breaker_status": self.discord_circuit_breaker.get_status(),
        }

    async def force_gateway_rotation(self):
        """Force rotation to a different Discord gateway"""
        logger.info("Forcing Discord gateway rotation...")
        await self._select_optimal_gateway()

    async def health_check(self) -> bool:
        """Perform health check on Discord connection"""
        try:
            if not self.bot.is_ready():
                return False

            # Try to fetch bot user info as a connectivity test
            if hasattr(self.bot, "user") and self.bot.user:
                # Simple check - if we have user info, connection is likely healthy
                return True

            return False

        except Exception as e:
            logger.warning(f"Discord connection health check failed: {e}")
            return False


# Monkey patch to add resilient connection to discord.py Client
def add_resilient_connection_to_bot(bot, config: Optional[Dict[str, Any]] = None):
    """Add resilient connection capabilities to a Discord bot"""

    # Create resilient client
    resilient_client = ResilientDiscordClient(bot, config)
    bot._resilient_client = resilient_client

    # Override the start method to use resilient connection
    original_start = bot.start

    async def resilient_start(token: str, *, reconnect: bool = True):
        """Start bot with resilient connection"""
        if reconnect:
            success = await resilient_client.connect_with_fallback(token)
            if not success:
                raise ConnectionError(
                    "Failed to establish resilient Discord connection"
                )
        else:
            # Use original start for non-reconnecting starts
            await original_start(token, reconnect=False)

    bot.start = resilient_start

    # Add convenience methods
    bot.get_connection_stats = resilient_client.get_connection_stats
    bot.force_gateway_rotation = resilient_client.force_gateway_rotation
    bot.add_connection_callback = resilient_client.add_connection_callback

    return resilient_client
