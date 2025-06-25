# YouTube Platform Fallback Testing

This document describes the comprehensive test suite for YouTube platform fallback functionality in Robustty.

## Overview

The fallback testing suite validates that the YouTube platform can gracefully handle various failure scenarios and automatically switch to alternative methods when the primary YouTube API is unavailable or encounters issues.

## Test Categories

### 1. Direct YouTube URL Processing Tests

**Location**: `tests/test_platforms/test_youtube_fallback_comprehensive.py::TestDirectYouTubeURLProcessing`

Tests that YouTube URLs in search queries are processed directly without requiring API access:

- URL pattern recognition for various YouTube URL formats
- Video ID extraction from URLs
- Metadata retrieval via yt-dlp instead of API
- Functionality works even without API key configured

**Key Test Cases**:
- `test_url_extraction_from_search_query` - Basic URL processing
- `test_various_youtube_url_formats` - Multiple URL format support
- `test_url_processing_without_api_key` - No API key required for URLs
- `test_text_search_without_api_key_fails` - Text searches require API

### 2. yt-dlp Search Fallback Tests

**Location**: `tests/test_platforms/test_youtube_fallback_comprehensive.py::TestYtDlpFallbackFunctionality`

Tests automatic fallback to yt-dlp when YouTube API quota is exceeded:

- API quota exceeded detection and handling
- Automatic fallback activation
- yt-dlp metadata extraction
- Error handling when both API and fallback fail

**Key Test Cases**:
- `test_api_quota_exceeded_triggers_fallback` - Quota detection and fallback
- `test_api_quota_exceeded_with_failed_fallback` - Double failure handling
- `test_ytdlp_metadata_extraction` - Metadata extraction via yt-dlp
- `test_video_details_fallback_on_quota_exceeded` - Video details fallback

### 3. Cookie-Enhanced Authentication Tests

**Location**: `tests/test_platforms/test_youtube_fallback_comprehensive.py::TestCookieEnhancedAuthentication`

Tests cookie integration for enhanced access to YouTube content:

- JSON to Netscape cookie format conversion
- Cookie path fallback mechanism
- Stream extraction with and without cookies
- Invalid cookie file handling

**Key Test Cases**:
- `test_cookie_conversion_to_netscape_format` - Cookie format conversion
- `test_cookie_path_fallback_mechanism` - Multiple cookie path support
- `test_stream_extraction_without_cookies` - Graceful no-cookie operation
- `test_invalid_cookie_file_handling` - Error resilience

### 4. Graceful Degradation Tests

**Location**: `tests/test_platforms/test_youtube_fallback_comprehensive.py::TestGracefulDegradation`

Tests handling of various failure scenarios with graceful recovery:

- Stream format fallback when primary formats fail
- yt-dlp error handling (private videos, copyright, region blocks)
- Metadata extraction with missing data
- Duration parsing edge cases

**Key Test Cases**:
- `test_stream_url_extraction_format_fallback` - Format selection fallback
- `test_yt_dlp_download_error_handling` - Download error scenarios
- `test_metadata_extraction_error_recovery` - Partial data handling
- `test_duration_parsing_edge_cases` - Robust duration parsing

### 5. Platform Fallback Manager Tests

**Location**: `tests/test_services/test_platform_fallback_manager.py`

Tests the core fallback management system:

- Fallback strategy activation and deactivation
- Operation restrictions based on fallback mode
- User-facing recommendations
- History tracking and reporting

**Key Test Classes**:
- `TestFallbackManagerBasics` - Core functionality
- `TestFallbackActivationDeactivation` - State management
- `TestFallbackOperationRestrictions` - Mode-based restrictions
- `TestUserFacingRecommendations` - User guidance
- `TestFallbackReporting` - Status reporting

### 6. Integration Tests

**Location**: `tests/integration/test_youtube_fallback_integration.py`

End-to-end integration tests that validate complete fallback workflows:

- Complete API quota fallback workflow
- URL processing bypass during API failures
- Cookie integration during fallback
- Multiple platform coordination
- Real-world scenario simulation

**Key Test Classes**:
- `TestEndToEndFallbackWorkflow` - Complete workflows
- `TestRealWorldScenarios` - Realistic failure scenarios
- `TestFallbackRecoveryScenarios` - Recovery testing

## Running the Tests

### Quick Start

```bash
# Run all fallback tests
python tests/run_fallback_tests.py

# Run specific test categories
python tests/run_fallback_tests.py --scenarios url_processing api_quota cookies

# Include integration tests (may require external dependencies)
python tests/run_fallback_tests.py --include-integration

# Run only unit tests
python tests/run_fallback_tests.py --unit-only
```

### Using pytest Directly

```bash
# Run comprehensive tests
pytest tests/test_platforms/test_youtube_fallback_comprehensive.py -v

# Run fallback manager tests
pytest tests/test_services/test_platform_fallback_manager.py -v

# Run integration tests
pytest tests/integration/test_youtube_fallback_integration.py -v -m integration

# Run specific test class
pytest tests/test_platforms/test_youtube_fallback_comprehensive.py::TestDirectYouTubeURLProcessing -v

# Run with coverage
pytest tests/test_platforms/test_youtube_fallback_comprehensive.py --cov=src --cov-report=html
```

### Test Scenarios

The test runner supports specific scenarios:

- `url_processing` - Direct URL processing tests
- `api_quota` - API quota exceeded scenarios
- `cookies` - Cookie authentication tests
- `degradation` - Graceful degradation tests
- `manager` - Fallback manager functionality
- `integration` - End-to-end integration tests

## Test Configuration

### Environment Variables

```bash
# Optional: Use real YouTube API key for integration tests
export YOUTUBE_API_KEY="your_actual_api_key"

# Test configuration can be customized in tests/fallback_test_config.py
```

### Test Markers

The tests use pytest markers for organization:

- `@pytest.mark.unit` - Unit tests (default)
- `@pytest.mark.integration` - Integration tests (require `--include-integration`)
- `@pytest.mark.asyncio` - Async tests
- `@pytest.mark.slow` - Slower tests

## Mock Data and Fixtures

### Test Fixtures

- `youtube_platform_with_api` - YouTube platform with API key
- `youtube_platform_no_api` - YouTube platform without API key
- `fallback_manager` - Platform fallback manager instance
- `mock_cookie_file` - Temporary mock cookie file
- `sample_video_metadata` - Sample video metadata for testing

### Sample Data

Located in `tests/fallback_test_config.py`:

- `SAMPLE_YOUTUBE_URLS` - Various YouTube URL formats
- `SAMPLE_VIDEO_METADATA` - Mock video metadata
- `SAMPLE_COOKIES` - Mock cookie data
- `ERROR_SCENARIOS` - Error simulation scenarios

## Test Validation Scenarios

### 1. API Quota Exceeded Simulation

Tests simulate YouTube API quota exceeded responses:

```python
quota_error = HttpError(
    resp=Mock(status=403),
    content=b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
)
```

Validates:
- Error detection and classification
- Automatic fallback activation
- User-friendly error messaging
- Successful fallback operation

### 2. Cookie Authentication Flow

Tests cookie integration from detection to usage:

1. Cookie file discovery (multiple paths)
2. JSON to Netscape format conversion
3. Cookie validation and cleanup
4. Integration with yt-dlp
5. Graceful fallback when cookies unavailable

### 3. Graceful Degradation Scenarios

Tests various failure modes:

- Network connectivity issues
- Invalid video IDs
- Private/unavailable videos
- Copyright/region restrictions
- Malformed API responses
- Partial data scenarios

### 4. User Experience Validation

Tests user-facing aspects:

- Clear error messages with actionable guidance
- Fallback mode notifications
- Performance characteristics
- Status reporting and recommendations

## Expected Test Results

### Success Criteria

All tests should pass with the following characteristics:

1. **URL Processing**: Direct YouTube URLs work without API
2. **API Fallback**: Quota exceeded triggers yt-dlp fallback
3. **Cookie Integration**: Cookies enhance access when available
4. **Error Handling**: Failures are handled gracefully with clear messaging
5. **Performance**: Fallback operations complete within reasonable time
6. **Integration**: Components work together seamlessly

### Performance Benchmarks

- URL processing: < 2 seconds
- API fallback activation: < 1 second
- yt-dlp metadata extraction: < 10 seconds
- Cookie conversion: < 0.5 seconds

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed (`pip install -r requirements.txt`)
2. **Missing Test Files**: Run from project root directory
3. **Network Timeouts**: Some integration tests may require stable internet
4. **Permission Errors**: Ensure write permissions for temporary test files

### Debug Mode

For detailed debugging, run tests with increased verbosity:

```bash
pytest tests/test_platforms/test_youtube_fallback_comprehensive.py -v -s --log-cli-level=DEBUG
```

### Test Environment Validation

```bash
# Validate test environment
python tests/run_fallback_tests.py --validate-only

# Check test configuration
python tests/fallback_test_config.py
```

## Contributing

When adding new fallback functionality:

1. Add corresponding test cases to the appropriate test class
2. Update mock data if needed
3. Add integration tests for end-to-end workflows
4. Update this documentation
5. Ensure all tests pass before submitting

### Test Structure Guidelines

- Use descriptive test method names
- Include docstrings explaining test purpose
- Use appropriate fixtures for setup
- Mock external dependencies
- Test both success and failure scenarios
- Validate error messages and user experience

## Related Documentation

- [Platform Implementation Guide](PLATFORM_IMPLEMENTATION.md)
- [Error Handling Documentation](ERROR_HANDLING.md)
- [Cookie Extraction Guide](COOKIE_EXTRACTION.md)
- [Integration Testing Guide](INTEGRATION_TESTING.md)