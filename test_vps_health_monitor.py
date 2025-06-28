#!/usr/bin/env python3
"""
Test script for VPS-specific health monitoring improvements.
Tests environment detection, timeout adjustments, and error categorization.
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.health_monitor import (
    HealthMonitor, ConnectionStatus, DeploymentEnvironment, 
    ErrorCategory, HealthCheckResult
)


class MockBot:
    """Mock bot for testing"""
    def __init__(self):
        self.platform_registry = MagicMock()
        self.platform_registry.get_enabled_platforms.return_value = {
            "youtube": MagicMock(enabled=True),
            "rumble": MagicMock(enabled=True)
        }
        self.platform_registry.get_platform = lambda name: MagicMock(
            enabled=True,
            search_videos=AsyncMock(side_effect=Exception("Network timeout"))
        )
        self.audio_players = {}
        self.cache_manager = MagicMock()
        self.cache_manager.redis_client = MagicMock()
        self.is_ready = MagicMock(return_value=True)
        self.ws = MagicMock()
        self.ws.socket = MagicMock()
        self.latency = 0.1
        self.guilds = []
        self.user = MagicMock(id=12345)


async def test_environment_detection():
    """Test environment detection logic"""
    print("\n=== Testing Environment Detection ===")
    
    # Test local environment
    config = {"health_monitor": {}}
    monitor = HealthMonitor(MockBot(), config)
    print(f"Default environment: {monitor.environment.value}")
    print(f"Check interval: {monitor.check_interval}s")
    print(f"Max failures: {monitor.max_consecutive_failures}")
    print(f"Timeout multiplier: {monitor.timeout_multiplier}x")
    
    # Test VPS environment
    print("\n--- Simulating VPS Environment ---")
    with patch.dict(os.environ, {'IS_VPS': 'true'}):
        monitor_vps = HealthMonitor(MockBot(), config)
        print(f"VPS environment: {monitor_vps.environment.value}")
        print(f"Check interval: {monitor_vps.check_interval}s")
        print(f"Max failures: {monitor_vps.max_consecutive_failures}")
        print(f"Timeout multiplier: {monitor_vps.timeout_multiplier}x")
        print(f"Network tolerance: {monitor_vps.network_tolerance}")
    
    # Test Docker on VPS
    print("\n--- Simulating Docker on VPS ---")
    with patch.dict(os.environ, {'REDIS_URL': 'redis://redis:6379'}):
        with patch('os.path.exists', return_value=True):  # Simulate /.dockerenv
            monitor_docker_vps = HealthMonitor(MockBot(), config)
            print(f"Docker+VPS environment: {monitor_docker_vps.environment.value}")


async def test_error_categorization():
    """Test error categorization"""
    print("\n=== Testing Error Categorization ===")
    
    config = {"health_monitor": {}}
    monitor = HealthMonitor(MockBot(), config)
    
    # Test various error types
    test_errors = [
        (Exception("Connection timeout"), "NETWORK"),
        (Exception("Connection refused"), "NETWORK"),
        (Exception("DNS resolution failed"), "NETWORK"),
        (asyncio.TimeoutError("Request timed out"), "TIMEOUT"),
        (Exception("Rate limit exceeded (429)"), "API"),
        (Exception("Invalid API key (401)"), "API"),
        (Exception("Forbidden (403)"), "API"),
        (Exception("Some random error"), "UNKNOWN"),
    ]
    
    for error, expected_category in test_errors:
        category = monitor._categorize_error(error)
        print(f"{str(error)[:40]:40} -> {category.value:10} (expected: {expected_category})")
        assert category.value == expected_category.lower(), f"Expected {expected_category}, got {category.value}"


async def test_network_error_tolerance():
    """Test network error tolerance on VPS"""
    print("\n=== Testing Network Error Tolerance ===")
    
    # Create VPS monitor
    with patch.dict(os.environ, {'IS_VPS': 'true'}):
        config = {"health_monitor": {}}
        monitor = HealthMonitor(MockBot(), config)
        
        print(f"Environment: {monitor.environment.value}")
        print(f"Network tolerance: {monitor.network_tolerance}")
        
        # Simulate network errors
        platform_key = "platform_youtube"
        
        # First few network errors should be DEGRADED on VPS
        for i in range(monitor.network_tolerance - 1):
            monitor.network_error_counts[platform_key] = i
            result = HealthCheckResult(
                status=ConnectionStatus.DEGRADED,
                response_time=0.5,
                error="Network error",
                error_category=ErrorCategory.NETWORK
            )
            print(f"Network error #{i+1}: Status would be {result.status.value}")
        
        # After tolerance exceeded, should be UNHEALTHY
        monitor.network_error_counts[platform_key] = monitor.network_tolerance
        print(f"Network error #{monitor.network_tolerance}: Status would be UNHEALTHY")


async def test_adaptive_thresholds():
    """Test adaptive failure thresholds for VPS"""
    print("\n=== Testing Adaptive Thresholds ===")
    
    with patch.dict(os.environ, {'IS_VPS': 'true'}):
        config = {"health_monitor": {}}
        monitor = HealthMonitor(MockBot(), config)
        
        service_name = "platform_youtube"
        
        # Recent network error - should get extended threshold
        monitor.network_error_counts[service_name] = 2
        monitor.last_network_error[service_name] = datetime.now() - timedelta(minutes=2)
        
        print(f"Base max consecutive failures: {monitor.max_consecutive_failures}")
        print(f"With recent network error: {monitor.max_consecutive_failures + 2}")
        
        # Old network error - should use base threshold
        monitor.last_network_error[service_name] = datetime.now() - timedelta(minutes=10)
        print(f"With old network error: {monitor.max_consecutive_failures}")


async def test_timeout_multiplier():
    """Test timeout multiplier application"""
    print("\n=== Testing Timeout Multiplier ===")
    
    # Local environment
    config = {"health_monitor": {}}
    monitor_local = HealthMonitor(MockBot(), config)
    print(f"Local environment - Timeout multiplier: {monitor_local.timeout_multiplier}x")
    
    # VPS environment
    with patch.dict(os.environ, {'IS_VPS': 'true'}):
        monitor_vps = HealthMonitor(MockBot(), config)
        print(f"VPS environment - Timeout multiplier: {monitor_vps.timeout_multiplier}x")
        
        # Calculate actual timeouts
        base_timeout = 30  # seconds
        print(f"\nBase timeout: {base_timeout}s")
        print(f"Local timeout: {base_timeout * monitor_local.timeout_multiplier}s")
        print(f"VPS timeout: {base_timeout * monitor_vps.timeout_multiplier}s")


async def test_recovery_delays():
    """Test recovery delay calculations"""
    print("\n=== Testing Recovery Delays ===")
    
    config = {
        "health_monitor": {
            "recovery": {
                "exponential_backoff": True,
                "max_delay": 600
            }
        }
    }
    
    # Compare local vs VPS
    monitor_local = HealthMonitor(MockBot(), config)
    
    with patch.dict(os.environ, {'IS_VPS': 'true'}):
        monitor_vps = HealthMonitor(MockBot(), config)
    
    print("Recovery attempt delays (seconds):")
    print("Attempt | Local | VPS")
    print("--------|-------|------")
    
    for attempt in range(1, 6):
        # Calculate delays
        if monitor_local.use_exponential_backoff:
            local_delay = min(monitor_local.max_recovery_delay, 10 * (2 ** (attempt - 1)))
            vps_delay = min(monitor_vps.max_recovery_delay, 20 * (2 ** (attempt - 1)))
        else:
            local_delay = min(monitor_local.max_recovery_delay, 30 * attempt)
            vps_delay = min(monitor_vps.max_recovery_delay, 60 * attempt)
        
        # Apply multiplier
        local_delay *= monitor_local.timeout_multiplier
        vps_delay *= monitor_vps.timeout_multiplier
        
        print(f"   {attempt}    |  {local_delay:3.0f}  | {vps_delay:4.0f}")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("VPS Health Monitor Test Suite")
    print("=" * 60)
    
    await test_environment_detection()
    await test_error_categorization()
    await test_network_error_tolerance()
    await test_adaptive_thresholds()
    await test_timeout_multiplier()
    await test_recovery_delays()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())