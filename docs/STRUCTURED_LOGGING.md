# Structured Logging in RumbleExtractor

The RumbleExtractor implements structured logging to provide comprehensive visibility into operations, performance metrics, and error tracking.

## Overview

All logging in the RumbleExtractor uses a custom `StructuredLogger` adapter that automatically adds contextual information to every log message.

## Key Features

### 1. Automatic Context Injection

Every log message includes:
- `extractor`: Always "rumble"
- `has_api_token`: Boolean indicating if API token is present
- `max_retries`: Number of retry attempts configured
- `actor_timeout`: Timeout in milliseconds for actor calls

### 2. Operation Tracking

Operations are tracked with:
- `operation`: Type of operation (metadata, download, search, actor_call)
- `trace_id`: Unique identifier for request tracing
- `start_time`: Unix timestamp when operation started
- `duration_ms`: Operation duration in milliseconds (automatically calculated)

### 3. Contextual Logging

Additional context is added based on the operation:
- **Video operations**: `video_url`, `video_id`, `quality`
- **Search operations**: `query`, `max_results`
- **Actor calls**: `actor_id`, `input_size`, `result_size`
- **Retry attempts**: `retry_attempt`, `retry_delay`, `error_type`

## Usage Examples

### Basic Initialization
```python
extractor = RumbleExtractor(apify_api_token='your-token')
# Logs: "Initialized RumbleExtractor" with context
```

### Operation Logging
```python
# When calling get_video_metadata()
await extractor.get_video_metadata('https://rumble.com/v123-test.html')
# Logs: "Starting metadata operation" with trace_id and video context
# Logs: "Failed metadata operation: ..." with error details and timing
```

### Retry Logging
```python
# When retries occur
# Logs: "Retry 1/3 for _make_actor_call after 1.23s delay. Error: ..."
# Includes: retry_attempt, retry_delay, error_type
```

## Benefits

1. **Debugging**: Trace operations with unique IDs
2. **Performance**: Monitor operation durations
3. **Error Analysis**: Understand failure patterns
4. **Monitoring**: Filter logs by operation type or error type
5. **Audit Trail**: Complete record of all API interactions

## Log Format Example

```json
{
  "level": "INFO",
  "message": "Starting metadata operation",
  "extractor": "rumble",
  "operation": "metadata",
  "trace_id": "e3f4d5c6-7a8b-9c0d-1e2f-3a4b5c6d7e8f",
  "video_url": "https://rumble.com/v123-test.html",
  "video_id": "v123",
  "has_api_token": true,
  "max_retries": 3,
  "actor_timeout": 60000
}
```

## Custom Logger Extension

The `with_context()` method allows adding temporary context:

```python
log = self.logger.with_context(
    actor_id=actor_id,
    input_size=len(str(input_data))
)
```

This creates a new logger instance with additional fields without modifying the base logger.

## Integration with Error Handling

The structured logging integrates seamlessly with the platform error hierarchy:

```python
except Exception as e:
    log.log_operation_error('actor_call', e, context)
    # Logs error with full context and timing information
```

## Best Practices

1. Always use `log_operation_start()` for trackable operations
2. Call `log_operation_complete()` on success
3. Use `log_operation_error()` for failures
4. Add relevant context with `with_context()`
5. Keep context keys consistent across operations