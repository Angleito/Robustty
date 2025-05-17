# Platform Error Handling Guide

## Overview

Robustty uses a centralized error handling system to ensure consistent error messages across all platform implementations. All platform-specific errors should inherit from `PlatformError` and use the appropriate error types.

## Error Types

| Error Class | Use Case | User Message Format |
|------------|----------|-------------------|
| `PlatformError` | Base class for all platform errors | `{platform}: {message}` |
| `PlatformNotAvailableError` | Platform is down or resource not found | `⚠️ {platform}: {message}. The platform might be temporarily unavailable.` |
| `PlatformAPIError` | API request failed | `❌ API Error ({status_code}): {platform}: {message}` |
| `PlatformRateLimitError` | Rate limit exceeded | `⏳ Rate Limited: {platform}: {message}. Try again in {retry_after} seconds.` |
| `PlatformAuthenticationError` | Auth failure (401, 403, invalid token) | `🔒 Authentication Error: {platform}: {message}` |

## Implementation Guide

### 1. Import Error Classes

```python
from .errors import (
    PlatformError,
    PlatformNotAvailableError,
    PlatformAPIError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
    from_http_status
)
```

### 2. Wrap All External API Calls

```python
async def search_videos(self, query: str) -> List[Dict[str, Any]]:
    """Search for videos on the platform."""
    try:
        response = await self.api_client.search(query)
        return self._parse_search_results(response)
    except HTTPError as e:
        # Use from_http_status for HTTP errors
        raise from_http_status(
            e.response.status_code,
            self.name,
            e.response.text
        )
    except ConnectionError as e:
        raise PlatformNotAvailableError(
            "Unable to connect to API",
            platform=self.name,
            original_error=e
        )
    except Exception as e:
        raise PlatformAPIError(
            f"Search failed: {str(e)}",
            platform=self.name,
            original_error=e
        )
```

### 3. Check Authentication Early

```python
async def initialize(self):
    """Initialize the platform client."""
    if not self.api_key:
        raise PlatformAuthenticationError(
            "API key is required. Please configure 'api_key' in config.",
            platform=self.name
        )
    
    try:
        # Test API connection
        await self._test_connection()
    except Exception as e:
        logger.error(f"Failed to initialize {self.name}: {e}")
        raise PlatformNotAvailableError(
            "Failed to connect to platform API",
            platform=self.name,
            original_error=e
        )
```

### 4. Handle Rate Limiting

```python
async def _make_api_request(self, endpoint: str, **kwargs):
    """Make an API request with rate limit handling."""
    try:
        response = await self.session.get(endpoint, **kwargs)
        response.raise_for_status()
        return response.json()
    except HTTPError as e:
        if e.response.status_code == 429:
            retry_after = e.response.headers.get('Retry-After')
            raise PlatformRateLimitError(
                "API rate limit exceeded",
                platform=self.name,
                retry_after=int(retry_after) if retry_after else None,
                original_error=e
            )
        raise from_http_status(
            e.response.status_code,
            self.name,
            e.response.text
        )
```

### 5. Error Categorization

```python
def _categorize_error(self, error: Exception) -> PlatformError:
    """Categorize an exception into the appropriate platform error."""
    error_msg = str(error).lower()
    
    if "rate limit" in error_msg or "429" in error_msg:
        return PlatformRateLimitError(
            "Request rate limit exceeded",
            platform=self.name,
            original_error=error
        )
    elif "unauthorized" in error_msg or "401" in error_msg:
        return PlatformAuthenticationError(
            "Authentication failed",
            platform=self.name,
            original_error=error
        )
    elif "forbidden" in error_msg or "403" in error_msg:
        return PlatformAuthenticationError(
            "Access forbidden",
            platform=self.name,
            original_error=error
        )
    elif "not found" in error_msg or "404" in error_msg:
        return PlatformNotAvailableError(
            "Resource not found",
            platform=self.name,
            original_error=error
        )
    else:
        return PlatformAPIError(
            f"Operation failed: {str(error)}",
            platform=self.name,
            original_error=error
        )
```

## Best Practices

1. **Always include the platform name**: This helps users identify which platform is having issues.

2. **Preserve original errors**: Use the `original_error` parameter to maintain the full error context for debugging.

3. **Use appropriate error types**: Choose the error type that best matches the failure mode.

4. **Provide helpful messages**: Include actionable information in error messages (e.g., "Please configure 'api_key' in config").

5. **Handle HTTP errors consistently**: Use `from_http_status` for HTTP errors to ensure consistent categorization.

6. **Log before raising**: Always log errors before raising them for better debugging.

## Examples

### YouTube Platform
```python
class YouTubePlatform(VideoPlatform):
    async def search_videos(self, query: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise PlatformAuthenticationError(
                "YouTube API key is required for search",
                platform="YouTube"
            )
        
        try:
            response = await self.youtube_api.search(query)
            return self._parse_results(response)
        except HttpError as e:
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                raise PlatformRateLimitError(
                    "YouTube quota exceeded",
                    platform="YouTube",
                    original_error=e
                )
            raise from_http_status(
                e.resp.status,
                "YouTube",
                str(e)
            )
```

### Rumble Platform
```python
class RumblePlatform(VideoPlatform):
    async def get_video_details(self, video_id: str) -> Dict[str, Any]:
        if not self.api_token:
            raise PlatformAuthenticationError(
                "Rumble API token required",
                platform="Rumble"
            )
        
        try:
            result = await self._make_actor_call(
                "rumble-video-extractor",
                {"video_id": video_id}
            )
            return result
        except TimeoutError:
            raise PlatformNotAvailableError(
                "Request timed out",
                platform="Rumble"
            )
        except Exception as e:
            raise self._categorize_error(e)
```

## Testing Error Handling

```python
import pytest
from unittest.mock import AsyncMock, patch

async def test_search_handles_rate_limit():
    """Test that rate limit errors are properly handled."""
    platform = YourPlatform("test", {"api_key": "key"})
    
    with patch.object(platform, '_make_request') as mock_request:
        mock_request.side_effect = HTTPError(
            response=Mock(status_code=429, headers={'Retry-After': '60'})
        )
        
        with pytest.raises(PlatformRateLimitError) as exc_info:
            await platform.search_videos("test query")
        
        assert exc_info.value.retry_after == 60
        assert "YouTube" in exc_info.value.user_message
```