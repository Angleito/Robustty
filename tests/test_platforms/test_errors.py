"""
Tests for platform error handling system.
"""

import pytest
from unittest.mock import Mock

from src.platforms.errors import (
    PlatformError,
    PlatformNotAvailableError,
    PlatformAPIError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
    from_http_status
)


def test_platform_error_base():
    """Test basic PlatformError functionality."""
    error = PlatformError("Test error", platform="YouTube")
    assert str(error) == "Test error"
    assert error.user_message == "YouTube: Test error"
    assert error.platform == "YouTube"
    assert error.original_error is None


def test_platform_error_with_original():
    """Test PlatformError with original exception."""
    original = ValueError("Original error")
    error = PlatformError("Wrapped error", platform="Rumble", original_error=original)
    assert error.original_error is original
    assert error.user_message == "Rumble: Wrapped error"


def test_platform_not_available_error():
    """Test PlatformNotAvailableError messages."""
    error = PlatformNotAvailableError("Service down", platform="PeerTube")
    assert error.user_message == "⚠️ PeerTube: Service down. The platform might be temporarily unavailable."


def test_platform_api_error():
    """Test PlatformAPIError with status code."""
    error = PlatformAPIError("Request failed", platform="YouTube", status_code=400)
    assert error.user_message == "❌ API Error (400): YouTube: Request failed"
    assert error.status_code == 400
    
    # Test without status code
    error_no_code = PlatformAPIError("Request failed", platform="YouTube")
    assert error_no_code.user_message == "❌ API Error: YouTube: Request failed"


def test_platform_rate_limit_error():
    """Test PlatformRateLimitError with retry_after."""
    error = PlatformRateLimitError("Too many requests", platform="Rumble", retry_after=60)
    assert error.user_message == "⏳ Rate Limited: Rumble: Too many requests. Try again in 60 seconds."
    assert error.retry_after == 60
    
    # Test without retry_after
    error_no_retry = PlatformRateLimitError("Too many requests", platform="Rumble")
    assert error_no_retry.user_message == "⏳ Rate Limited: Rumble: Too many requests. Please try again later."


def test_platform_authentication_error():
    """Test PlatformAuthenticationError messages."""
    error = PlatformAuthenticationError("Invalid API key", platform="YouTube")
    assert error.user_message == "🔒 Authentication Error: YouTube: Invalid API key"


def test_from_http_status():
    """Test creating errors from HTTP status codes."""
    # Test 401 Unauthorized
    error_401 = from_http_status(401, "YouTube", "Invalid API key")
    assert isinstance(error_401, PlatformAuthenticationError)
    assert error_401.user_message == "🔒 Authentication Error: YouTube: Invalid API key"
    
    # Test 403 Forbidden
    error_403 = from_http_status(403, "Rumble")
    assert isinstance(error_403, PlatformAuthenticationError)
    assert "Access denied" in error_403.user_message
    
    # Test 429 Too Many Requests
    error_429 = from_http_status(429, "PeerTube", "Rate limit exceeded")
    assert isinstance(error_429, PlatformRateLimitError)
    assert "Rate limit exceeded" in error_429.user_message
    
    # Test 404 Not Found
    error_404 = from_http_status(404, "YouTube")
    assert isinstance(error_404, PlatformNotAvailableError)
    assert "Resource not found" in error_404.user_message
    
    # Test 500 Server Error
    error_500 = from_http_status(500, "Rumble")
    assert isinstance(error_500, PlatformNotAvailableError)
    assert "Server error (500)" in error_500.user_message
    
    # Test generic error
    error_400 = from_http_status(400, "YouTube", "Bad request")
    assert isinstance(error_400, PlatformAPIError)
    assert error_400.status_code == 400
    assert "Bad request" in error_400.user_message


def test_error_without_platform():
    """Test errors without platform specification."""
    error = PlatformError("Generic error")
    assert error.user_message == "Generic error"
    assert error.platform is None


def test_error_inheritance():
    """Test that all errors inherit from PlatformError."""
    errors = [
        PlatformNotAvailableError("Test"),
        PlatformAPIError("Test"),
        PlatformRateLimitError("Test"),
        PlatformAuthenticationError("Test")
    ]
    
    for error in errors:
        assert isinstance(error, PlatformError)