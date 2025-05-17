"""Tests for metrics collector functionality."""

import pytest
import asyncio
from src.services.metrics_collector import get_metrics_collector


class TestMetricsCollector:
    """Test metrics collection functionality."""
    
    def test_singleton_pattern(self):
        """Test that get_metrics_collector returns the same instance."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        assert collector1 is collector2
    
    def test_api_call_timer(self):
        """Test API call timer context manager."""
        collector = get_metrics_collector()
        
        # Test successful call
        with collector.api_call_timer("test_endpoint"):
            # Simulate some work
            pass
        
        # Test failed call
        try:
            with collector.api_call_timer("test_endpoint"):
                raise ValueError("Test error")
        except ValueError:
            pass
    
    def test_record_methods(self):
        """Test manual metric recording methods."""
        collector = get_metrics_collector()
        
        # These should not raise
        collector.record_api_call("test", "success")
        collector.record_api_response_time("test", 0.5)
        collector.record_cache_hit("metadata")
        collector.record_cache_miss("metadata")
        collector.record_rate_limit()
        collector.record_error("TestError")
        collector.set_queue_size(5)
        collector.set_active_connections(2)
    
    def test_get_metrics(self):
        """Test metrics export functionality."""
        collector = get_metrics_collector()
        
        # Generate some test metrics
        collector.record_api_call("test", "success")
        
        # Get metrics
        metrics_data = collector.get_metrics()
        
        # Should return bytes (Prometheus format)
        assert isinstance(metrics_data, bytes)
        
        # Should contain our metrics
        metrics_text = metrics_data.decode('utf-8')
        assert 'rumble_api_calls_total' in metrics_text
        assert 'rumble_api_response_time_seconds' in metrics_text
    
    @pytest.mark.asyncio
    async def test_async_decorator(self):
        """Test async API call timer decorator."""
        collector = get_metrics_collector()
        
        @collector.async_api_call_timer("test_async")
        async def test_function():
            await asyncio.sleep(0.01)
            return "success"
        
        # Test successful call
        result = await test_function()
        assert result == "success"
        
        # Test failed call
        @collector.async_api_call_timer("test_async_error")
        async def test_error_function():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await test_error_function()
    
    @pytest.mark.asyncio
    async def test_cache_tracking_decorator(self):
        """Test cache tracking decorator."""
        collector = get_metrics_collector()
        
        @collector.track_cache("test_cache")
        async def test_cache_function(return_value):
            return return_value
        
        # Test cache hit (returns non-None)
        result = await test_cache_function("cached_value")
        assert result == "cached_value"
        
        # Test cache miss (returns None)
        result = await test_cache_function(None)
        assert result is None
    
    def test_metrics_content(self):
        """Test that metrics contain expected labels and values."""
        collector = get_metrics_collector()
        
        # Generate various metrics
        collector.record_api_call("search", "success")
        collector.record_api_call("search", "error")
        collector.record_api_response_time("search", 1.5)
        collector.record_cache_hit("metadata")
        collector.record_cache_miss("stream")
        collector.record_rate_limit()
        collector.record_error("PlatformError")
        collector.set_queue_size(10)
        collector.set_active_connections(3)
        
        # Get metrics
        metrics_text = collector.get_metrics().decode('utf-8')
        
        # Check for specific metrics and labels
        assert 'rumble_api_calls_total{endpoint="search",status="success"}' in metrics_text
        assert 'rumble_api_calls_total{endpoint="search",status="error"}' in metrics_text
        assert 'rumble_cache_hits_total{cache_type="metadata"}' in metrics_text
        assert 'rumble_cache_misses_total{cache_type="stream"}' in metrics_text
        assert 'rumble_rate_limits_total' in metrics_text
        assert 'rumble_errors_total{error_type="PlatformError"}' in metrics_text
        assert 'rumble_queue_size 10' in metrics_text
        assert 'rumble_active_connections 3' in metrics_text