"""
Network resilience utilities for robust error handling and service connectivity.

This module provides decorators and utilities for handling network failures,
implementing retry logic, circuit breaker patterns, and graceful degradation
for external service calls.
"""

import asyncio
import functools
import logging
import random
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union
from dataclasses import dataclass, field

import aiohttp

logger = logging.getLogger(__name__)

# Type variable for decorated functions
T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: int = 60  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close from half-open
    timeout: int = 30  # Request timeout in seconds


@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Exponential backoff multiplier
    jitter: bool = True  # Add random jitter to prevent thundering herd


@dataclass
class NetworkStats:
    """Network call statistics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    retries: int = 0
    circuit_breaks: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100


class CircuitBreaker:
    """Circuit breaker implementation for external service calls"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.stats = NetworkStats()
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                else:
                    self.stats.circuit_breaks += 1
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker {self.name} is OPEN. "
                        f"Service unavailable (failed {self.failure_count}/{self.config.failure_threshold} times)"
                    )
        
        try:
            self.stats.total_calls += 1
            
            # Add timeout to the call
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            await self._on_success()
            return result
            
        except asyncio.TimeoutError as e:
            await self._on_failure()
            raise NetworkTimeoutError(f"Call to {self.name} timed out after {self.config.timeout}s") from e
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        """Handle successful call"""
        async with self._lock:
            self.stats.successful_calls += 1
            self.stats.last_success = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info(f"Circuit breaker {self.name} closed after {self.success_count} successes")
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0  # Reset failure count on success
    
    async def _on_failure(self):
        """Handle failed call"""
        async with self._lock:
            self.stats.failed_calls += 1
            self.stats.last_failure = datetime.now()
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker {self.name} reopened due to failure in HALF_OPEN state")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout
    
    @property
    def is_available(self) -> bool:
        """Check if circuit breaker allows calls"""
        return self.state != CircuitState.OPEN
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of circuit breaker"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "success_rate": self.stats.success_rate,
                "circuit_breaks": self.stats.circuit_breaks,
            }
        }


class NetworkResilienceManager:
    """Manages circuit breakers and network resilience for all services"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.global_stats = NetworkStats()
    
    def get_circuit_breaker(self, service_name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create circuit breaker for a service"""
        if service_name not in self.circuit_breakers:
            if config is None:
                config = CircuitBreakerConfig()
            self.circuit_breakers[service_name] = CircuitBreaker(service_name, config)
        return self.circuit_breakers[service_name]
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all circuit breakers"""
        return {
            "circuit_breakers": {name: cb.get_status() for name, cb in self.circuit_breakers.items()},
            "global_stats": {
                "total_calls": self.global_stats.total_calls,
                "successful_calls": self.global_stats.successful_calls,
                "failed_calls": self.global_stats.failed_calls,
                "success_rate": self.global_stats.success_rate,
                "retries": self.global_stats.retries,
            }
        }


# Global instance
_resilience_manager = NetworkResilienceManager()


def get_resilience_manager() -> NetworkResilienceManager:
    """Get the global network resilience manager"""
    return _resilience_manager


# Custom exceptions
class NetworkResilienceError(Exception):
    """Base exception for network resilience errors"""
    pass


class CircuitBreakerOpenError(NetworkResilienceError):
    """Raised when circuit breaker is open"""
    pass


class NetworkTimeoutError(NetworkResilienceError):
    """Raised when network call times out"""
    pass


class MaxRetriesExceededError(NetworkResilienceError):
    """Raised when maximum retry attempts are exceeded"""
    pass


async def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for retry attempt with exponential backoff and jitter"""
    delay = min(config.base_delay * (config.exponential_base ** (attempt - 1)), config.max_delay)
    
    if config.jitter:
        # Add random jitter (±25% of delay)
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)
    
    return max(0, delay)


def with_retry(
    retry_config: Optional[RetryConfig] = None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    service_name: Optional[str] = None,
    exceptions: Tuple[type, ...] = (Exception,),
    exclude_exceptions: Tuple[type, ...] = ()
):
    """
    Decorator to add retry logic and circuit breaker to async functions.
    
    Args:
        retry_config: Retry configuration
        circuit_breaker_config: Circuit breaker configuration
        service_name: Name for circuit breaker (uses function name if not provided)
        exceptions: Tuple of exceptions to retry on
        exclude_exceptions: Tuple of exceptions to never retry on
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Set defaults
            if retry_config is None:
                config = RetryConfig()
            else:
                config = retry_config
            
            # Determine service name
            cb_name = service_name or f"{func.__module__}.{func.__name__}"
            
            # Get circuit breaker
            manager = get_resilience_manager()
            circuit_breaker = manager.get_circuit_breaker(cb_name, circuit_breaker_config)
            
            # Track global stats
            manager.global_stats.total_calls += 1
            
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    # Use circuit breaker to execute function
                    result = await circuit_breaker.call(func, *args, **kwargs)
                    
                    # Success
                    manager.global_stats.successful_calls += 1
                    if attempt > 1:
                        manager.global_stats.retries += attempt - 1
                        logger.info(f"Function {func.__name__} succeeded on attempt {attempt}")
                    
                    return result
                    
                except exclude_exceptions as e:
                    # Don't retry these exceptions
                    manager.global_stats.failed_calls += 1
                    logger.error(f"Function {func.__name__} failed with non-retryable exception: {e}")
                    raise
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts:
                        # Final attempt failed
                        manager.global_stats.failed_calls += 1
                        logger.error(f"Function {func.__name__} failed after {config.max_attempts} attempts: {e}")
                        raise MaxRetriesExceededError(
                            f"Function {func.__name__} failed after {config.max_attempts} attempts. "
                            f"Last error: {str(e)}"
                        ) from e
                    
                    # Calculate delay and wait
                    delay = await _calculate_delay(attempt, config)
                    logger.warning(f"Function {func.__name__} attempt {attempt} failed: {e}. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    
                except CircuitBreakerOpenError:
                    # Circuit breaker is open, don't retry
                    manager.global_stats.failed_calls += 1
                    raise
                    
                except Exception as e:
                    # Unexpected exception
                    manager.global_stats.failed_calls += 1
                    logger.error(f"Function {func.__name__} failed with unexpected exception: {e}")
                    raise
            
            # This should never be reached
            raise last_exception
        
        return wrapper
    return decorator


def with_circuit_breaker(
    service_name: Optional[str] = None,
    config: Optional[CircuitBreakerConfig] = None
):
    """
    Decorator to add circuit breaker protection to async functions.
    
    Args:
        service_name: Name for circuit breaker (uses function name if not provided)
        config: Circuit breaker configuration
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Determine service name
            cb_name = service_name or f"{func.__module__}.{func.__name__}"
            
            # Get circuit breaker
            manager = get_resilience_manager()
            circuit_breaker = manager.get_circuit_breaker(cb_name, config)
            
            # Execute with circuit breaker protection
            return await circuit_breaker.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


async def safe_aiohttp_request(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    timeout: int = 30,
    **kwargs
) -> aiohttp.ClientResponse:
    """
    Make a safe HTTP request with proper error handling and timeout.
    
    Args:
        session: aiohttp session
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        timeout: Request timeout in seconds
        **kwargs: Additional arguments for the request
    
    Returns:
        aiohttp.ClientResponse
        
    Raises:
        NetworkTimeoutError: On timeout
        aiohttp.ClientError: On other HTTP errors
    """
    try:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with session.request(method, url, timeout=timeout_obj, **kwargs) as response:
            return response
    except asyncio.TimeoutError as e:
        raise NetworkTimeoutError(f"Request to {url} timed out after {timeout}s") from e
    except aiohttp.ClientError as e:
        logger.error(f"HTTP request to {url} failed: {e}")
        raise


# Predefined configurations for common services
PLATFORM_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30,
    success_threshold=2,
    timeout=30
)

PLATFORM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True
)

REDIS_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60,
    success_threshold=3,
    timeout=10
)

REDIS_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0,
    jitter=True
)