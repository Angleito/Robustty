"""
Platform error classes for consistent error handling across all video platforms.

This module provides a hierarchy of exceptions that all platform implementations
should use for error handling. This ensures consistent user-facing error messages
and proper error categorization.

Usage:
    All platform implementations should wrap their internal exceptions with these
    error classes to provide consistent error handling. For example:
    
    try:
        # Perform platform operation
        ...
    except requests.HTTPError as e:
        if e.response.status_code == 429:
            raise PlatformRateLimitError("Too many requests", platform="YouTube", original_error=e)
        elif e.response.status_code == 401:
            raise PlatformAuthenticationError("Invalid API key", platform="YouTube", original_error=e)
        else:
            raise PlatformAPIError(f"Request failed: {e}", platform="YouTube", original_error=e)
"""

from typing import Optional
from http import HTTPStatus


class PlatformError(Exception):
    """Base exception for all platform-related errors."""
    
    def __init__(self, message: str, platform: Optional[str] = None, 
                 original_error: Optional[Exception] = None):
        self.platform = platform
        self.original_error = original_error
        self.user_message = self._create_user_message(message)
        super().__init__(message)
    
    def _create_user_message(self, message: str) -> str:
        """Create a user-friendly error message."""
        if self.platform:
            return f"{self.platform}: {message}"
        return message


class PlatformNotAvailableError(PlatformError):
    """Raised when a platform is temporarily unavailable or down."""
    
    def _create_user_message(self, message: str) -> str:
        base_msg = super()._create_user_message(message)
        return f"⚠️ {base_msg}. The platform might be temporarily unavailable."


class PlatformAPIError(PlatformError):
    """Raised when a platform's API returns an error response."""
    
    def __init__(self, message: str, platform: Optional[str] = None,
                 status_code: Optional[int] = None, 
                 original_error: Optional[Exception] = None):
        self.status_code = status_code
        super().__init__(message, platform, original_error)
    
    def _create_user_message(self, message: str) -> str:
        base_msg = super()._create_user_message(message)
        if self.status_code:
            return f"❌ API Error ({self.status_code}): {base_msg}"
        return f"❌ API Error: {base_msg}"


class PlatformRateLimitError(PlatformError):
    """Raised when a platform's rate limit is exceeded."""
    
    def __init__(self, message: str, platform: Optional[str] = None,
                 retry_after: Optional[int] = None,
                 original_error: Optional[Exception] = None):
        self.retry_after = retry_after
        super().__init__(message, platform, original_error)
    
    def _create_user_message(self, message: str) -> str:
        base_msg = super()._create_user_message(message)
        if self.retry_after:
            return f"⏳ Rate Limited: {base_msg}. Try again in {self.retry_after} seconds."
        return f"⏳ Rate Limited: {base_msg}. Please try again later."


class PlatformAuthenticationError(PlatformError):
    """Raised when authentication with a platform fails."""
    
    def _create_user_message(self, message: str) -> str:
        base_msg = super()._create_user_message(message)
        return f"🔒 Authentication Error: {base_msg}"


def from_http_status(status_code: int, platform: str, 
                    response_text: Optional[str] = None) -> PlatformError:
    """Create appropriate platform error from HTTP status code."""
    
    if status_code == HTTPStatus.UNAUTHORIZED:
        return PlatformAuthenticationError(
            response_text or "Invalid or expired credentials",
            platform=platform
        )
    elif status_code == HTTPStatus.FORBIDDEN:
        return PlatformAuthenticationError(
            response_text or "Access denied to resource",
            platform=platform
        )
    elif status_code == HTTPStatus.TOO_MANY_REQUESTS:
        return PlatformRateLimitError(
            response_text or "Too many requests",
            platform=platform
        )
    elif status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.GONE):
        return PlatformNotAvailableError(
            response_text or "Resource not found",
            platform=platform
        )
    elif status_code >= 500:
        return PlatformNotAvailableError(
            response_text or f"Server error ({status_code})",
            platform=platform
        )
    else:
        return PlatformAPIError(
            response_text or f"Request failed",
            platform=platform,
            status_code=status_code
        )