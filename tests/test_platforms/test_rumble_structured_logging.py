"""
Tests for Rumble extractor structured logging functionality.
"""

import asyncio
import pytest
import logging
from io import StringIO
from unittest.mock import MagicMock, patch
from src.extractors.rumble_extractor import RumbleExtractor, StructuredLogger
from src.platforms.errors import PlatformAuthenticationError


class TestStructuredLogging:
    """Test structured logging functionality in RumbleExtractor."""
    
    def test_structured_logger_initialization(self):
        """Test StructuredLogger initialization."""
        base_logger = logging.getLogger('test')
        extra_context = {'platform': 'test', 'user': 'test_user'}
        
        logger = StructuredLogger(base_logger, extra_context)
        
        assert logger.logger == base_logger
        assert logger.extra == extra_context
    
    def test_structured_logger_with_context(self):
        """Test creating a new logger with additional context."""
        base_logger = logging.getLogger('test')
        extra_context = {'platform': 'test'}
        
        logger = StructuredLogger(base_logger, extra_context)
        new_logger = logger.with_context(operation='download', url='test.com')
        
        assert new_logger.extra['platform'] == 'test'
        assert new_logger.extra['operation'] == 'download'
        assert new_logger.extra['url'] == 'test.com'
    
    def test_logger_operation_tracking(self):
        """Test operation tracking with timing."""
        base_logger = logging.getLogger('test')
        logger = StructuredLogger(base_logger, {})
        
        context = logger.log_operation_start('test_operation', extra_field='value')
        
        assert 'operation' in context
        assert context['operation'] == 'test_operation'
        assert 'start_time' in context
        assert 'trace_id' in context
        assert context['extra_field'] == 'value'
    
    def test_log_processing_with_timing(self):
        """Test log message processing with timing calculations."""
        base_logger = logging.getLogger('test')
        logger = StructuredLogger(base_logger, {})
        
        # Mock start time from 1 second ago
        import time
        start_time = time.time() - 1.0
        
        msg = "Test message"
        kwargs = {'extra': {'start_time': start_time}}
        
        processed_msg, processed_kwargs = logger.process(msg, kwargs)
        
        assert processed_msg == msg
        assert 'duration_ms' in processed_kwargs['extra']
        assert processed_kwargs['extra']['duration_ms'] >= 1000
        assert 'start_time' not in processed_kwargs['extra']
    
    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        logger = logging.getLogger('test')
        logger.setLevel(logging.DEBUG)
        
        # Create string stream handler
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        
        # Format with structured data
        formatter = logging.Formatter(
            '%(levelname)s: %(message)s | %(extra_data)s',
            defaults={'extra_data': '{}'}
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger, stream
    
    def test_rumble_extractor_structured_logging(self):
        """Test RumbleExtractor uses structured logging correctly."""
        extractor = RumbleExtractor(apify_api_token='test_token')
        
        assert isinstance(extractor.logger, StructuredLogger)
        assert extractor.logger.extra['extractor'] == 'rumble'
        assert extractor.logger.extra['has_api_token'] == True
        assert extractor.logger.extra['max_retries'] == 3
        assert extractor.logger.extra['actor_timeout'] == 60_000
    
    @pytest.mark.asyncio
    async def test_metadata_extraction_logging(self):
        """Test structured logging during metadata extraction."""
        extractor = RumbleExtractor(apify_api_token='test_token')
        
        # Mock the logger methods to track calls
        extractor.logger = MagicMock(spec=StructuredLogger)
        mock_context_logger = MagicMock(spec=StructuredLogger)
        extractor.logger.with_context.return_value = mock_context_logger
        
        mock_context = {'operation': 'metadata', 'trace_id': 'test-123'}
        mock_context_logger.log_operation_start.return_value = mock_context
        
        # Try to get metadata (will fail with NotImplementedError)
        with pytest.raises(NotImplementedError):
            await extractor.get_video_metadata('https://rumble.com/v1234-test.html')
        
        # Verify logging calls
        extractor.logger.with_context.assert_called_once_with(
            video_url='https://rumble.com/v1234-test.html'
        )
        mock_context_logger.log_operation_start.assert_called_once_with(
            'metadata',
            video_id='v1234'
        )
        mock_context_logger.log_operation_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_logging_with_auth_error(self):
        """Test structured logging when search fails with auth error."""
        extractor = RumbleExtractor()  # No API token
        
        # Mock the logger methods
        extractor.logger = MagicMock(spec=StructuredLogger)
        mock_context_logger = MagicMock(spec=StructuredLogger)
        extractor.logger.with_context.return_value = mock_context_logger
        
        mock_context = {'operation': 'search', 'trace_id': 'test-456'}
        mock_context_logger.log_operation_start.return_value = mock_context
        
        # Try to search (will fail with PlatformAuthenticationError)
        with pytest.raises(PlatformAuthenticationError):
            await extractor.search_videos('test query', max_results=5)
        
        # Verify logging calls
        extractor.logger.with_context.assert_called_once_with(
            query='test query',
            max_results=5
        )
        mock_context_logger.log_operation_start.assert_called_once_with('search')
        mock_context_logger.log_operation_error.assert_called_once()
        
        # Check error logging details
        error_call = mock_context_logger.log_operation_error.call_args
        assert error_call[0][0] == 'search'  # operation
        assert isinstance(error_call[0][1], PlatformAuthenticationError)  # error
        assert error_call[0][2] == mock_context  # context


if __name__ == '__main__':
    pytest.main([__file__, '-v'])