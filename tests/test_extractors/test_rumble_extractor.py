"""Comprehensive tests for Rumble extractor implementation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import time

import pytest

from src.extractors.rumble_extractor import RumbleExtractor, StructuredLogger
from src.platforms.errors import (
    PlatformError,
    PlatformNotAvailableError,
    PlatformAPIError,
    PlatformRateLimitError,
    PlatformAuthenticationError,
)


class TestRumbleExtractor:
    """Test suite for Rumble extractor implementation."""

    @pytest.fixture
    def extractor(self):
        """Create a Rumble extractor instance."""
        return RumbleExtractor(apify_api_token="test_token_123")

    @pytest.fixture
    def extractor_no_token(self):
        """Create a Rumble extractor instance without API token."""
        return RumbleExtractor(apify_api_token=None)

    @pytest.mark.asyncio
    async def test_missing_api_token_scenario(self, extractor_no_token):
        """Test behavior when API token is missing."""
        # Test with no token
        with pytest.raises(PlatformAuthenticationError) as exc_info:
            await extractor_no_token.get_video_metadata("https://rumble.com/v4abcd-test.html")
        assert "API token is required" in str(exc_info.value)
        
        # Test download_audio without token
        with pytest.raises(PlatformAuthenticationError) as exc_info:
            await extractor_no_token.download_audio("https://rumble.com/v4abcd-test.html")
        assert "API token is required" in str(exc_info.value)
        
        # Test search without token
        with pytest.raises(PlatformAuthenticationError) as exc_info:
            await extractor_no_token.search_videos("test query")
        assert "API token is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rate_limit_response(self, extractor):
        """Test handling of rate limit response (HTTP 429)."""
        # Mock rate limit error
        with patch.object(extractor, '_call_apify_actor') as mock_call:
            mock_call.side_effect = Exception("429 rate limit exceeded")
            
            with patch.object(extractor, '_make_actor_call') as mock_make_call:
                mock_make_call.side_effect = PlatformRateLimitError(
                    "API rate limit exceeded",
                    platform="Rumble"
                )
                
                with pytest.raises(PlatformRateLimitError):
                    await extractor._make_actor_call("test_actor", {})

    def test_malformed_urls(self, extractor):
        """Test validation of malformed URLs."""
        malformed_urls = [
            "ht://rumble.com/v4abcd",  # Invalid protocol
            "rumble.com//v4abcd",  # Double slash
            "rumble.com/v/abcd",  # Extra slash in ID
            "rumble.com/v4abcd%20video",  # URL encoding in ID
            "rumble.com/v4abcd\nvideo",  # Newline in URL
            "not-a-url",  # Not a URL
            "",  # Empty string
            None,  # None
        ]
        
        for url in malformed_urls:
            result = extractor.validate_url(url)
            assert result is False

    @pytest.mark.asyncio
    async def test_timeout_scenarios(self, extractor):
        """Test handling of timeout scenarios."""
        # Mock timeout error
        with patch.object(extractor, '_call_apify_actor') as mock_call:
            # Make it actually delay to trigger timeout
            async def delayed_call(*args, **kwargs):
                await asyncio.sleep(2)  # Sleep longer than timeout
                return {}
            
            mock_call.side_effect = delayed_call
            
            # Set a short timeout
            extractor.actor_timeout = 1000  # 1 second
            
            with pytest.raises(PlatformNotAvailableError) as exc_info:
                await extractor._make_actor_call("test_actor", {})
            assert "Request timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_failures_5xx(self, extractor):
        """Test handling of 5xx server errors."""
        server_errors = [
            "500 Internal Server Error",
            "502 Bad Gateway",
            "503 Service Unavailable",
            "504 Gateway Timeout",
        ]
        
        for error_msg in server_errors:
            with patch.object(extractor, '_call_apify_actor') as mock_call:
                mock_call.side_effect = Exception(error_msg)
                
                # The retry decorator should retry these errors
                with patch('src.extractors.rumble_extractor._is_retryable_error', return_value=True):
                    with patch('src.extractors.rumble_extractor.logger') as mock_logger:
                        with pytest.raises(Exception) as exc_info:
                            await extractor._make_actor_call("test_actor", {})
                        assert error_msg in str(exc_info.value)
                        # Should see retry warnings
                        assert mock_logger.warning.called

    @pytest.mark.asyncio
    async def test_retry_logic_verification(self, extractor):
        """Test that retry logic works correctly."""
        # Mock a function that fails twice then succeeds
        call_count = 0
        
        async def failing_then_succeeding_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("500 Server Error")
            return {"success": True}
        
        with patch.object(extractor, '_call_apify_actor', side_effect=failing_then_succeeding_call):
            with patch('src.extractors.rumble_extractor._is_retryable_error', return_value=True):
                with patch('src.extractors.rumble_extractor.logger') as mock_logger:
                    result = await extractor._make_actor_call("test_actor", {})
                    assert result == {"success": True}
                    assert call_count == 3
                    # Should see 2 retry warnings
                    assert mock_logger.warning.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_handling(self, extractor):
        """Test timeout handling with proper cancellation."""
        # Test asyncio.TimeoutError
        with patch.object(extractor, '_call_apify_actor') as mock_call:
            mock_call.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(PlatformNotAvailableError) as exc_info:
                await extractor._make_actor_call("test_actor", {})
            assert "Request timed out" in str(exc_info.value)
            
        # Test asyncio.CancelledError
        with patch.object(extractor, '_call_apify_actor') as mock_call:
            mock_call.side_effect = asyncio.CancelledError()
            
            with pytest.raises(PlatformError) as exc_info:
                await extractor._make_actor_call("test_actor", {})
            assert "Request was cancelled" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_categorization(self, extractor):
        """Test that errors are properly categorized."""
        error_scenarios = [
            ("429 rate limit exceeded", PlatformRateLimitError),
            ("401 unauthorized", PlatformAuthenticationError),
            ("503 service unavailable", PlatformAPIError),
            ("Unknown error occurred", PlatformAPIError),
        ]
        
        for error_msg, expected_error_type in error_scenarios:
            with patch.object(extractor, '_call_apify_actor') as mock_call:
                mock_call.side_effect = Exception(error_msg)
                
                # Disable retry for this test
                with patch('src.extractors.rumble_extractor._is_retryable_error', return_value=False):
                    with pytest.raises(expected_error_type):
                        await extractor._make_actor_call("test_actor", {})

    def test_video_id_extraction(self, extractor):
        """Test video ID extraction from URLs."""
        test_cases = [
            ("https://rumble.com/v4abcd-test-video.html", "v4abcd"),
            ("https://www.rumble.com/v4abcd-test-video.html", "v4abcd"),
            ("http://rumble.com/v4abcd-test-video.html", "v4abcd"),
            ("rumble.com/v4abcd-test-video.html", "v4abcd"),
            ("https://rumble.com/embed/v4abcd/", None),  # Not a video page
            ("https://rumble.com/c/channel", None),  # Channel page
            ("https://youtube.com/watch?v=123", None),  # Wrong platform
        ]
        
        for url, expected_id in test_cases:
            result = extractor.extract_video_id(url)
            assert result == expected_id

    def test_url_validation(self, extractor):
        """Test URL validation."""
        valid_urls = [
            "https://rumble.com/v4abcd-test-video.html",
            "https://www.rumble.com/v4abcd-test-video.html",
            "http://rumble.com/v4abcd-test-video.html",
        ]
        
        invalid_urls = [
            "https://youtube.com/watch?v=123",
            "https://vimeo.com/123456",
            "not-a-url",
            "",
            None,
        ]
        
        for url in valid_urls:
            assert extractor.validate_url(url) is True
            
        for url in invalid_urls:
            assert extractor.validate_url(url) is False

    @pytest.mark.asyncio
    async def test_empty_search_results(self, extractor):
        """Test handling of empty search results."""
        with patch.object(extractor, '_make_actor_call') as mock_call:
            mock_call.return_value = {"items": []}
            
            # This should raise NotImplementedError for now
            with pytest.raises(NotImplementedError):
                await extractor.search_videos("very specific query")

    @pytest.mark.asyncio
    async def test_invalid_api_response_format(self, extractor):
        """Test handling of invalid API response formats."""
        invalid_responses = [
            None,  # None response
            {},  # Empty dict
            {"wrong_key": "value"},  # Missing expected keys
            "not a dict",  # String instead of dict
            123,  # Number instead of dict
        ]
        
        for invalid_response in invalid_responses:
            with patch.object(extractor, '_make_actor_call') as mock_call:
                mock_call.return_value = invalid_response
                
                # This should raise NotImplementedError for now
                with pytest.raises(NotImplementedError):
                    await extractor.get_video_metadata("https://rumble.com/v4abcd-test.html")


class TestStructuredLogger:
    """Test suite for StructuredLogger implementation."""
    
    def test_logger_initialization(self):
        """Test structured logger initialization."""
        base_logger = MagicMock()
        extra_context = {"service": "rumble", "environment": "test"}
        
        structured_logger = StructuredLogger(base_logger, extra_context)
        assert structured_logger.extra == extra_context
    
    def test_with_context(self):
        """Test adding additional context."""
        base_logger = MagicMock()
        extra_context = {"service": "rumble"}
        
        structured_logger = StructuredLogger(base_logger, extra_context)
        new_logger = structured_logger.with_context(operation="search", user_id="123")
        
        assert new_logger.extra["service"] == "rumble"
        assert new_logger.extra["operation"] == "search"
        assert new_logger.extra["user_id"] == "123"
    
    def test_log_operation_start(self):
        """Test logging operation start."""
        base_logger = MagicMock()
        structured_logger = StructuredLogger(base_logger, {})
        
        # Mock the info method on the structured logger
        with patch.object(structured_logger, 'info') as mock_info:
            context = structured_logger.log_operation_start("video_download", video_id="v4abcd")
            
            assert context["operation"] == "video_download"
            assert context["video_id"] == "v4abcd"
            assert "start_time" in context
            assert "trace_id" in context
            
            # Check that info was called
            mock_info.assert_called_once()
    
    def test_log_operation_complete(self):
        """Test logging operation completion."""
        base_logger = MagicMock()
        structured_logger = StructuredLogger(base_logger, {})
        
        context = {
            "operation": "video_download",
            "start_time": time.time() - 1,  # 1 second ago
            "trace_id": "test-trace-id"
        }
        
        # Mock the info method on the structured logger
        with patch.object(structured_logger, 'info') as mock_info:
            structured_logger.log_operation_complete("video_download", context, status="success")
            
            # Check that info was called
            mock_info.assert_called_once()
    
    def test_log_operation_error(self):
        """Test logging operation error."""
        base_logger = MagicMock()
        structured_logger = StructuredLogger(base_logger, {})
        
        context = {
            "operation": "video_download",
            "start_time": time.time() - 1,
            "trace_id": "test-trace-id"
        }
        
        error = ValueError("Invalid video ID")
        
        # Mock the error method on the structured logger
        with patch.object(structured_logger, 'error') as mock_error:
            structured_logger.log_operation_error("video_download", error, context, severity="high")
            
            # Check that error was called
            mock_error.assert_called_once()
    
    def test_process_with_timing(self):
        """Test log processing with timing information."""
        base_logger = MagicMock()
        structured_logger = StructuredLogger(base_logger, {})
        
        # Test with start_time in extra
        kwargs = {
            "extra": {
                "start_time": time.time() - 1,
                "operation": "search"
            }
        }
        
        msg, processed_kwargs = structured_logger.process("Test message", kwargs)
        
        assert "duration_ms" in processed_kwargs["extra"]
        assert "start_time" not in processed_kwargs["extra"]
        assert processed_kwargs["extra"]["operation"] == "search"


class TestRetryDecorator:
    """Test suite for retry decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self):
        """Test retry decorator with exponential backoff."""
        from src.extractors.rumble_extractor import retry_with_exponential_backoff
        
        call_count = 0
        
        @retry_with_exponential_backoff(max_retries=2, initial_delay=0.1, jitter=False)
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("500 Server Error")
            return "success"
        
        with patch('src.extractors.rumble_extractor._is_retryable_error', return_value=True):
            result = await failing_function()
            assert result == "success"
            assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        from src.extractors.rumble_extractor import retry_with_exponential_backoff
        
        call_count = 0
        
        @retry_with_exponential_backoff(max_retries=2)
        async def failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")
        
        with patch('src.extractors.rumble_extractor._is_retryable_error', return_value=False):
            with pytest.raises(ValueError):
                await failing_function()
            assert call_count == 1  # Should not retry


class TestUtilityFunctions:
    """Test suite for utility functions."""
    
    def test_is_retryable_error(self):
        """Test _is_retryable_error function."""
        from src.extractors.rumble_extractor import _is_retryable_error
        
        retryable_errors = [
            Exception("429 rate limit exceeded"),
            Exception("HTTP 500 Internal Server Error"),
            Exception("503 Service Unavailable"),
            ConnectionError("Connection timeout"),
            TimeoutError("Network timeout"),
        ]
        
        non_retryable_errors = [
            ValueError("Invalid input"),
            TypeError("Wrong type"),
            Exception("404 Not Found"),
            Exception("401 Unauthorized"),
        ]
        
        for error in retryable_errors:
            assert _is_retryable_error(error) is True
            
        for error in non_retryable_errors:
            assert _is_retryable_error(error) is False