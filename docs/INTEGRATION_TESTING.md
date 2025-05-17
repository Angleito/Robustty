# Integration Testing Guide

This guide explains how to run integration tests for Robustty, particularly for the Rumble platform integration.

## Overview

Integration tests verify that our platform implementations work correctly with real external APIs. These tests are slower than unit tests and require API credentials, so they are not run by default.

## Prerequisites

### API Keys

To run integration tests for Rumble, you need:

1. **Apify API Key**: Required for Rumble platform testing
   - Sign up at [Apify](https://apify.com)
   - Get your API key from the account settings
   - Set the environment variable: `export APIFY_API_KEY=your_key_here`

## Running Integration Tests

### Run All Integration Tests

```bash
# From the project root
pytest tests/integration -v

# With coverage
pytest tests/integration --cov=src --cov-report=html
```

### Run Specific Platform Tests

```bash
# Rumble integration tests only
pytest tests/integration/test_rumble_integration.py -v

# Run a specific test
pytest tests/integration/test_rumble_integration.py::TestRumbleIntegration::test_real_rumble_search -v
```

### Skip Slow Tests

Some integration tests are marked as slow. To skip them:

```bash
pytest tests/integration -v -m "not slow"
```

### Running with Docker

If you prefer to run tests in a Docker environment:

```bash
# Build test image
docker build -f docker/test/Dockerfile -t robustty-test .

# Run integration tests
docker run -e APIFY_API_KEY=$APIFY_API_KEY robustty-test pytest tests/integration -v
```

## Test Categories

### Rumble Integration Tests

Located in `tests/integration/test_rumble_integration.py`:

1. **test_real_rumble_search**: Tests search functionality with real Rumble content
2. **test_real_video_metadata**: Tests video metadata extraction
3. **test_real_stream_extraction**: Tests stream URL extraction
4. **test_rate_limit_handling**: Verifies proper rate limit handling
5. **test_error_scenarios**: Tests various error conditions
6. **test_search_pagination**: Tests search with different limits
7. **test_category_searches**: Tests searches for common categories

### Mock Integration Tests

Some tests simulate integration scenarios using mocks:

- **test_network_timeout_handling**: Simulates network timeouts
- **test_malformed_response_handling**: Tests handling of bad API responses
- **test_concurrent_request_handling**: Tests concurrent API requests

## Environment Variables

Integration tests respect these environment variables:

- `APIFY_API_KEY`: Apify API key for Rumble tests
- `SKIP_INTEGRATION`: Set to skip all integration tests
- `TEST_TIMEOUT`: Override default test timeout (in seconds)
- `LOG_LEVEL`: Set logging level for tests (DEBUG, INFO, WARNING, ERROR)

## CI/CD Integration

In your CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Run Integration Tests
  env:
    APIFY_API_KEY: ${{ secrets.APIFY_API_KEY }}
  run: |
    pytest tests/integration -v --junitxml=test-results.xml
  continue-on-error: true  # Don't fail build on integration test failures
```

## Troubleshooting

### Tests Skipped

If tests are being skipped:

1. Check that required environment variables are set:
   ```bash
   echo $APIFY_API_KEY
   ```

2. Run pytest with `-v` to see skip reasons:
   ```bash
   pytest tests/integration -v -rs
   ```

### Rate Limiting

If you encounter rate limiting:

1. Add delays between tests
2. Reduce the number of concurrent tests
3. Use test caching where appropriate

### Network Issues

For network-related failures:

1. Check your internet connection
2. Verify API endpoints are accessible
3. Check for proxy/firewall issues

## Writing New Integration Tests

When adding new integration tests:

1. Place them in `tests/integration/`
2. Use appropriate pytest marks:
   ```python
   @pytest.mark.integration
   @pytest.mark.slow  # for tests taking >5 seconds
   ```

3. Check for required credentials:
   ```python
   pytestmark = pytest.mark.skipif(
       not os.environ.get('API_KEY'),
       reason="API_KEY not set"
   )
   ```

4. Include proper error handling:
   ```python
   try:
       result = api_call()
   except APIError:
       pytest.skip("API temporarily unavailable")
   ```

5. Add appropriate delays to avoid rate limiting:
   ```python
   import time
   time.sleep(1)  # Between API calls
   ```

## Best Practices

1. **Isolate Integration Tests**: Keep them separate from unit tests
2. **Use Real Data Carefully**: Don't depend on specific content that might change
3. **Mock When Appropriate**: Use mocks for error scenarios
4. **Document Dependencies**: Clearly state what external services are required
5. **Handle Failures Gracefully**: Integration tests may fail due to external factors
6. **Monitor API Usage**: Be mindful of API quotas and costs

## Monitoring Test Results

To generate detailed test reports:

```bash
# HTML report
pytest tests/integration --html=report.html --self-contained-html

# JUnit XML for CI systems
pytest tests/integration --junitxml=test-results.xml

# Coverage report
pytest tests/integration --cov=src --cov-report=html
```

## Common Issues and Solutions

### Timeout Errors

Increase timeout for slow tests:

```python
@pytest.mark.timeout(30)  # 30 seconds
def test_slow_operation():
    pass
```

### Intermittent Failures

For flaky tests, use retry logic:

```python
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_might_fail_intermittently():
    pass
```

### API Changes

If external APIs change:

1. Update test expectations
2. Add version checking
3. Document API version dependencies

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Integration Best Practices](https://docs.pytest.org/en/latest/goodpractices.html)
- [Apify API Documentation](https://docs.apify.com/api/v2)
- [Rumble Platform Documentation](../PLATFORMS.md#rumble)