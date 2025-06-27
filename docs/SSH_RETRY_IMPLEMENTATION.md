# SSH/Rsync Retry Implementation with Exponential Backoff

## Overview

The SSH/rsync retry wrapper provides robust network resilience by implementing exponential backoff retries for SSH, SCP, and rsync commands. This mitigates transient network issues, rate limits from VPS providers, and temporary connection failures.

## Implementation Details

### Core Features

- **Exponential Backoff**: Retry delays increase exponentially (1s, 2s, 4s, 8s, etc.)
- **Smart Error Detection**: Distinguishes between retryable and non-retryable errors
- **Command Type Recognition**: Automatically identifies network-related commands
- **Configurable Parameters**: Customizable retry counts, delays, and backoff multipliers
- **Integration**: Seamless integration with existing SSH persistent connections

### Files Created/Modified

1. **`scripts/ssh-retry-wrapper.sh`** - Main retry wrapper implementation
2. **`scripts/example-ssh-retry-usage.sh`** - Usage examples and documentation
3. **`deploy-vps.sh`** - Updated to use retry wrappers
4. **`deploy-vps-with-validation.sh`** - Updated to use retry wrappers  
5. **`scripts/sync-cookies-vps.sh`** - Updated to use retry wrappers
6. **`scripts/deploy-cookies-to-vps.sh`** - Updated to use retry wrappers

## Usage

### Basic Usage

```bash
# Source the wrapper to enable retry functions
source scripts/ssh-retry-wrapper.sh

# Use retry-enabled commands
ssh_retry user@host "command"
scp_retry file.txt user@host:/path/
rsync_retry -av local/ user@host:remote/
```

### Advanced Usage

```bash
# Custom retry parameters
SSH_MAX_RETRIES=6 SSH_BASE_DELAY=2 ssh_retry user@host "command"

# Persistent SSH with retry
ssh_exec_persistent_retry "host" "user" "22" "" "docker ps"

# Generic command retry
retry_with_exponential_backoff 4 1 2 30 your_command
```

## Configuration

### Environment Variables

- `SSH_MAX_RETRIES=4` - Maximum retry attempts
- `SSH_BASE_DELAY=1` - Base delay in seconds
- `SSH_BACKOFF_MULTIPLIER=2` - Exponential backoff multiplier
- `SSH_MAX_DELAY=60` - Maximum delay between retries

### Retry Sequence (Default)

1. **Attempt 1**: Immediate execution
2. **Attempt 2**: Wait 1 second, retry
3. **Attempt 3**: Wait 2 seconds, retry
4. **Attempt 4**: Wait 4 seconds, retry
5. **Final**: Fail with last error code

## Error Handling

### Enhanced Error Diagnostics

The SSH retry wrapper now provides comprehensive error analysis and troubleshooting guidance:

- **Detailed Exit Code Analysis**: Each exit code is analyzed and explained
- **Error Log Capture**: stderr output is captured and displayed for all failed attempts
- **Command-Specific Guidance**: Tailored troubleshooting based on command type (ssh, scp, rsync)
- **Pattern Recognition**: Automatic analysis of error messages for targeted advice
- **Next Steps Recommendations**: Clear guidance on what to try next when all retries fail

### Retryable Errors

- SSH connection failures (exit code 255) - Network connectivity issues
- Network timeouts (exit code 124) - Connection timeout
- Rsync protocol errors (exit codes 5, 10, 11, 12, 30, 35) - Various rsync failures
- Generic network-related errors (exit code 1) - For network commands

### Non-Retryable Errors

- Authentication failures - SSH key or password issues
- Command not found (exit code 127) - Binary not available
- Permission denied (exit code 126) - Execution permission issues
- Protocol incompatibility (exit code 2) - SSH protocol mismatch
- User interruption (exit code 130) - Ctrl+C termination

### Error Analysis Features

#### Exit Code Descriptions
Every exit code is mapped to a human-readable description:
- Exit 255: "SSH connection failure or network error"
- Exit 1: "General error (possibly network-related for ssh)"
- Exit 127: "Command not found"
- And many more...

#### Error Log Capture
```bash
🔍 DETAILED ERROR LOG:
Command: ssh user@invalid-host "echo test"
All attempts and errors:
Attempt 1 (exit 255): ssh: Could not resolve hostname invalid-host
Attempt 2 (exit 255): ssh: Could not resolve hostname invalid-host
```

#### Command-Specific Troubleshooting

**SSH Connection Issues:**
- Check host reachability: `ping <hostname>`
- Verify SSH service: `ssh -v <user@host>`
- Test with different options: `ssh -o ConnectTimeout=10`

**SCP Transfer Issues:**
- Verify source file exists and is readable
- Check destination directory permissions
- Test basic connectivity first

**Rsync Synchronization Issues:**
- Check rsync daemon status
- Try with SSH transport: `rsync -e ssh`
- Adjust timeout values: `rsync --timeout=300`

#### Pattern-Based Analysis
The system analyzes error messages for common patterns:
- "Connection refused" → Service not running or wrong port
- "Host key verification failed" → Remove old key with ssh-keygen -R
- "Permission denied" → Check authentication method
- "Network unreachable" → Check routing and network config
- "Timeout" → Increase timeout values or check latency

## Integration Points

### Deployment Scripts

All major deployment scripts now use retry wrappers:

```bash
# Before
ssh user@host "command"
scp file.txt user@host:/path/

# After  
ssh_retry user@host "command"
scp_retry file.txt user@host:/path/
```

### Persistent SSH Integration

The retry wrapper integrates with the existing SSH persistent connection system:

```bash
# Retry-enabled persistent SSH
ssh_exec_persistent_retry "host" "user" "22" "" "command"
ssh_copy_persistent_retry "to" "host" "user" "22" "" "src" "dest"
```

## Benefits

### Network Resilience

- **Transient Failures**: Automatically recovers from temporary network issues
- **Rate Limiting**: Handles VPS provider rate limits with exponential backoff
- **Connection Drops**: Retries failed SSH/rsync operations automatically
- **DNS Issues**: Retries DNS resolution failures

### Operational Benefits

- **Reduced Manual Intervention**: Automatic retry reduces need for manual re-runs
- **Improved Reliability**: Higher success rate for deployment operations
- **Better User Experience**: Clearer logging and progress indication
- **Consistent Behavior**: Standardized retry logic across all network operations

## Monitoring and Logging

### Log Format

```
[HH:MM:SS][RETRY] 🔄 Retrying in 2s (attempt 3/4)...
[HH:MM:SS][RETRY] ✅ Command succeeded on attempt 3
[HH:MM:SS][RETRY] ❌ Command failed on attempt 4 (exit code: 255)
```

### Status Indicators

- 🔄 Retry in progress
- ✅ Success after retry
- ❌ Failure (retryable)
- 🚨 Critical error (non-retryable)
- ⚠️ Warning

## Testing

### Verify Installation

```bash
# Check wrapper is available
./scripts/ssh-retry-wrapper.sh help

# Test with examples
./scripts/example-ssh-retry-usage.sh
```

### Manual Testing

```bash
# Test with invalid host (should retry and fail)
ssh_retry invalid-host "echo test"

# Test with valid host (should succeed immediately)
ssh_retry your-host "echo test"
```

## Troubleshooting

### Common Issues

1. **Script Not Found**: Ensure `ssh-retry-wrapper.sh` is in the `scripts/` directory
2. **Permission Denied**: Make sure script is executable (`chmod +x`)
3. **Sourcing Issues**: Use `source` or `.` to load the functions
4. **Environment Variables**: Check if custom retry parameters are set correctly

### Debugging

Enable verbose logging by setting environment variables:

```bash
SSH_MAX_RETRIES=6 SSH_BASE_DELAY=1 ssh_retry -v user@host "command"
```

## Best Practices

1. **Use Appropriate Timeouts**: Set reasonable SSH connection timeouts
2. **Monitor Retry Patterns**: Watch for excessive retries indicating systemic issues
3. **Customize Parameters**: Adjust retry parameters based on your network conditions
4. **Fallback Plans**: Have manual procedures for critical operations
5. **Test Regularly**: Verify retry behavior in your specific environment

## Future Enhancements

- **Jitter Addition**: Add random jitter to prevent thundering herd problems
- **Circuit Breaker**: Implement circuit breaker pattern for persistent failures
- **Metrics Collection**: Add metrics for retry success/failure rates
- **Configuration Files**: Support for configuration files instead of environment variables
