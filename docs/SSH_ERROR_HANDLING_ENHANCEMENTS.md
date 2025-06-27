# SSH Error Handling and Diagnostics Enhancements

## Overview

This document outlines the comprehensive enhancements made to SSH error handling and diagnostics in the Robustty project. These improvements provide detailed exit code analysis, error log capture, and actionable troubleshooting guidance when SSH commands fail after all retry attempts.

## Enhanced Features

### 1. Detailed Exit Code Analysis

Every exit code is now mapped to human-readable descriptions:

```bash
# Examples of exit code descriptions:
Exit 255: "SSH connection failure or network error"
Exit 1:   "General error (possibly network-related for ssh)"
Exit 127: "Command not found"
Exit 126: "Command invoked cannot execute (permission denied)"
```

### 2. Comprehensive Error Log Capture

The system now captures and displays stderr output from all failed attempts:

```bash
🔍 DETAILED ERROR LOG:
Command: ssh user@invalid-host "echo test"
All attempts and errors:
Attempt 1 (exit 255): ssh: Could not resolve hostname invalid-host
Attempt 2 (exit 255): ssh: Could not resolve hostname invalid-host
```

### 3. Command-Specific Troubleshooting Guidance

Tailored diagnostic information based on the type of command that failed:

#### SSH Connection Issues
- Network connectivity checks: `ping <hostname>`
- Service verification: `ssh -v <user@host>`
- Configuration validation: Check `~/.ssh/config`
- Authentication troubleshooting

#### SCP Transfer Issues
- File existence verification
- Permission checks
- Disk space validation
- Basic connectivity tests

#### Rsync Synchronization Issues
- Daemon status checks
- Transport method alternatives
- Timeout adjustments
- Network stability considerations

### 4. Pattern-Based Error Analysis

Automatic analysis of error messages for targeted advice:

- **"Connection refused"** → Service not running or wrong port
- **"Host key verification failed"** → Remove old key with `ssh-keygen -R`
- **"Permission denied"** → Check authentication method
- **"Network unreachable"** → Check routing and network config
- **"Timeout"** → Increase timeout values or check latency

### 5. Next Steps Recommendations

When all retries are exhausted, the system provides:

- **Immediate retry options** with different parameters
- **Quick diagnostic commands** to run
- **Log saving instructions** for analysis
- **General recovery options**

## Implementation Files

### Core Enhancement Files

1. **`scripts/ssh-retry-wrapper.sh`** - Enhanced with detailed error handling
   - `get_error_description()` - Maps exit codes to descriptions
   - `provide_next_steps()` - Comprehensive troubleshooting guidance
   - Enhanced `retry_with_exponential_backoff()` with error capture

2. **`scripts/ssh-persistent.sh`** - Enhanced persistent SSH connections
   - Detailed error capture for connection establishment
   - Pattern-based error analysis
   - Specific troubleshooting for connection failures

### Demo and Testing Files

3. **`scripts/ssh-error-diagnostics-demo.sh`** - Interactive demonstration
   - Shows error handling for various failure scenarios
   - Educational examples of diagnostic output

4. **`scripts/test-ssh-error-handling.sh`** - Comprehensive validation
   - Automated testing of error handling features
   - Validates diagnostic output generation
   - Tests retryable vs non-retryable error detection

### Documentation Updates

5. **`docs/SSH_RETRY_IMPLEMENTATION.md`** - Updated with error handling details
6. **`docs/SSH_ERROR_HANDLING_ENHANCEMENTS.md`** - This comprehensive guide

## Usage Examples

### Basic Usage with Enhanced Error Handling

```bash
# Source the wrapper to enable enhanced error handling
source scripts/ssh-retry-wrapper.sh

# Use retry-enabled commands with detailed diagnostics
ssh_retry user@invalid-host "command"
# Will show detailed error analysis and next steps when it fails

scp_retry file.txt user@invalid-host:/path/
# Will provide SCP-specific troubleshooting guidance

rsync_retry -av local/ user@invalid-host:remote/
# Will show rsync-specific diagnostic information
```

### Custom Retry Parameters

```bash
# Adjust retry behavior for specific scenarios
SSH_MAX_RETRIES=8 SSH_BASE_DELAY=5 SSH_MAX_DELAY=120 ssh_retry user@host "command"
```

### Testing the Enhanced Error Handling

```bash
# Run the diagnostic demo
./scripts/ssh-error-diagnostics-demo.sh

# Run comprehensive validation tests
./scripts/test-ssh-error-handling.sh

# View help for all options
./scripts/ssh-retry-wrapper.sh help
```

## Error Analysis Workflow

### When a Command Fails

1. **Exit Code Capture** - Record the exact exit code
2. **Error Log Capture** - Capture stderr output to temporary file
3. **Error Description** - Map exit code to human-readable description
4. **Retryability Check** - Determine if error should be retried
5. **Pattern Analysis** - Analyze error message for known patterns
6. **Guidance Generation** - Provide command-specific troubleshooting

### After All Retries Exhausted

1. **Summary Display** - Show all attempts and their errors
2. **Detailed Analysis** - Display comprehensive error information
3. **Next Steps** - Provide actionable troubleshooting guidance
4. **Quick Commands** - Suggest diagnostic commands to run
5. **Recovery Options** - Offer immediate and long-term solutions

## Benefits

### For Users
- **Clear Guidance** - Know exactly what went wrong and how to fix it
- **Reduced Frustration** - No more mysterious failures
- **Learning Opportunity** - Understand SSH/network issues better
- **Time Savings** - Quick path to resolution

### For Operations
- **Faster Troubleshooting** - Immediate diagnostic information
- **Better Logging** - Detailed error logs for analysis
- **Reduced Support** - Self-service troubleshooting guidance
- **Improved Reliability** - Better handling of transient issues

### For Development
- **Consistent Error Handling** - Standardized across all SSH operations
- **Maintainable Code** - Centralized error handling logic
- **Testable Components** - Comprehensive test coverage
- **Documentation** - Well-documented error scenarios

## Configuration Options

### Environment Variables

```bash
# Retry behavior
SSH_MAX_RETRIES=4           # Maximum retry attempts
SSH_BASE_DELAY=1            # Base delay in seconds
SSH_BACKOFF_MULTIPLIER=2    # Exponential backoff multiplier
SSH_MAX_DELAY=60            # Maximum delay between retries

# Command-specific settings
SCP_MAX_RETRIES=4           # SCP-specific retry count
RSYNC_MAX_RETRIES=4         # Rsync-specific retry count
```

### Usage Patterns

```bash
# For unstable networks - more retries, longer delays
SSH_MAX_RETRIES=8 SSH_BASE_DELAY=3 SSH_MAX_DELAY=180 ssh_retry ...

# For fast networks - fewer retries, shorter delays
SSH_MAX_RETRIES=3 SSH_BASE_DELAY=1 SSH_MAX_DELAY=30 ssh_retry ...

# For rate-limited services - longer delays
SSH_BASE_DELAY=5 SSH_MAX_DELAY=300 ssh_retry ...
```

## Validation and Testing

### Automated Tests

The test suite validates:
- Exit code analysis accuracy
- Error log capture functionality
- Diagnostic output generation
- Retryable vs non-retryable error detection
- Pattern-based error analysis

### Manual Testing

Use the demo script to see error handling in action:

```bash
./scripts/ssh-error-diagnostics-demo.sh
```

This demonstrates error handling for:
- Invalid hostnames
- Wrong ports
- File not found errors
- Network unreachable scenarios

## Future Enhancements

### Potential Improvements

1. **Machine-Readable Output** - JSON format for programmatic analysis
2. **Integration with Monitoring** - Send error metrics to monitoring systems
3. **Historical Analysis** - Track error patterns over time
4. **Auto-Resolution** - Attempt automatic fixes for common issues
5. **User Customization** - Allow custom error handlers and guidance

### Extensibility

The error handling system is designed to be easily extensible:

- Add new exit code mappings in `get_error_description()`
- Extend command-specific guidance in `provide_next_steps()`
- Add new error patterns in the pattern analysis section
- Create custom retry functions for new command types

## Conclusion

These enhancements significantly improve the SSH error handling experience by providing:

- **Detailed diagnostic information** for all failures
- **Actionable troubleshooting guidance** specific to the error type
- **Comprehensive error logging** for analysis and debugging
- **Clear next steps** when automated retries are insufficient

The implementation maintains backward compatibility while adding powerful new diagnostic capabilities that help users quickly identify and resolve SSH connectivity issues.
