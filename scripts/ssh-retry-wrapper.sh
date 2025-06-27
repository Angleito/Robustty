#!/bin/bash

# SSH/Rsync Retry Wrapper with Exponential Backoff
# This script provides retry functionality for SSH and rsync commands to handle
# transient network issues, rate limits, and connection failures.

set -e

# Configuration
DEFAULT_MAX_RETRIES=4
DEFAULT_BASE_DELAY=1
DEFAULT_MAX_DELAY=60
DEFAULT_BACKOFF_MULTIPLIER=2

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%H:%M:%S')
    
    case $level in
        INFO)  echo -e "${BLUE}[$timestamp][RETRY]${NC} $message" ;;
        PASS)  echo -e "${GREEN}[$timestamp][RETRY]${NC} ✅ $message" ;;
        FAIL)  echo -e "${RED}[$timestamp][RETRY]${NC} ❌ $message" ;;
        WARN)  echo -e "${YELLOW}[$timestamp][RETRY]${NC} ⚠️ $message" ;;
        ERROR) echo -e "${RED}[$timestamp][RETRY]${NC} 🚨 $message" ;;
        RETRY) echo -e "${CYAN}[$timestamp][RETRY]${NC} 🔄 $message" ;;
    esac
}

# Calculate exponential backoff delay
calculate_delay() {
    local attempt=$1
    local base_delay=${2:-$DEFAULT_BASE_DELAY}
    local backoff_multiplier=${3:-$DEFAULT_BACKOFF_MULTIPLIER}
    local max_delay=${4:-$DEFAULT_MAX_DELAY}
    
    local delay=$base_delay
    for ((i=1; i<attempt; i++)); do
        delay=$((delay * backoff_multiplier))
    done
    
    # Cap at max_delay
    if [ $delay -gt $max_delay ]; then
        delay=$max_delay
    fi
    
    echo $delay
}

# Check if command is a network-related command that should be retried
is_retryable_command() {
    local cmd="$1"
    
    case "$cmd" in
        ssh|scp|rsync|sftp)
            return 0
            ;;
        *)
            # Check if command contains ssh/rsync as part of a pipeline or complex command
            if echo "$cmd" | grep -qE "\b(ssh|scp|rsync|sftp)\b"; then
                return 0
            fi
            return 1
            ;;
    esac
}

# Get detailed error description for exit codes
get_error_description() {
    local exit_code=$1
    local command_type="$2"
    
    case $exit_code in
        0)   echo "Success" ;;
        1)   echo "General error (possibly network-related for $command_type)" ;;
        2)   echo "Protocol incompatibility or misuse of shell command" ;;
        5)   echo "Error starting client-server protocol (rsync)" ;;
        10)  echo "Error in socket I/O (rsync)" ;;
        11)  echo "Error in file I/O (rsync)" ;;
        12)  echo "Error in rsync protocol data stream" ;;
        30)  echo "Timeout in data send/receive (rsync)" ;;
        35)  echo "Timeout waiting for daemon response (rsync)" ;;
        124) echo "Command timeout" ;;
        126) echo "Command invoked cannot execute (permission denied)" ;;
        127) echo "Command not found" ;;
        128) echo "Invalid argument to exit" ;;
        130) echo "Script terminated by Control-C" ;;
        255) echo "SSH connection failure or network error" ;;
        *)   echo "Unknown error (exit code: $exit_code)" ;;
    esac
}

# Check if exit code indicates a retryable failure
is_retryable_error() {
    local exit_code=$1
    local command="$2"
    
    case $exit_code in
        # SSH/SCP common retryable errors
        255) return 0 ;; # SSH connection failure
        1)   # Generic error - check command type
            if echo "$command" | grep -qE "\b(ssh|scp|rsync)\b"; then
                return 0
            fi
            return 1
            ;;
        # Rsync retryable errors
        5)   return 0 ;; # Error starting client-server protocol
        10)  return 0 ;; # Error in socket I/O
        11)  return 0 ;; # Error in file I/O
        12)  return 0 ;; # Error in rsync protocol data stream
        30)  return 0 ;; # Timeout in data send/receive
        35)  return 0 ;; # Timeout waiting for daemon response
        # Network-related errors
        124) return 0 ;; # timeout command timeout
        # Non-retryable errors
        2)   return 1 ;; # Protocol incompatibility
        126) return 1 ;; # Command invoked cannot execute
        127) return 1 ;; # Command not found
        128) return 1 ;; # Invalid argument to exit
        130) return 1 ;; # Script terminated by Control-C
        *)   return 0 ;; # Unknown error - retry by default for network commands
    esac
}

# Enhanced retry function with exponential backoff and detailed error logging
retry_with_exponential_backoff() {
    local max_retries=${1:-$DEFAULT_MAX_RETRIES}
    local base_delay=${2:-$DEFAULT_BASE_DELAY}
    local backoff_multiplier=${3:-$DEFAULT_BACKOFF_MULTIPLIER}
    local max_delay=${4:-$DEFAULT_MAX_DELAY}
    shift 4
    local command="$*"
    
    if [ -z "$command" ]; then
        log ERROR "No command specified for retry"
        return 1
    fi
    
    # Extract the first word to determine command type
    local cmd_name=$(echo "$command" | awk '{print $1}')
    
    # Check if this is a command that should be retried
    if ! is_retryable_command "$cmd_name"; then
        log WARN "Command '$cmd_name' is not typically retryable, executing once"
        eval "$command"
        return $?
    fi
    
    log INFO "Executing with retry (max: $max_retries): $command"
    
    local attempt=1
    local last_exit_code=0
    local error_log=""
    local all_errors=""
    
    # Create temporary files for capturing stderr
    local error_file=$(mktemp)
    local debug_file=$(mktemp)
    
    # Cleanup function
    cleanup_temp_files() {
        [[ -f "$error_file" ]] && rm -f "$error_file"
        [[ -f "$debug_file" ]] && rm -f "$debug_file"
    }
    
    # Set up trap to cleanup on exit
    trap cleanup_temp_files EXIT
    
    while [ $attempt -le $max_retries ]; do
        log INFO "Attempt $attempt/$max_retries"
        
        # Execute the command and capture stderr
        if eval "$command" 2>"$error_file"; then
            log PASS "Command succeeded on attempt $attempt"
            cleanup_temp_files
            return 0
        else
            last_exit_code=$?
            
            # Capture error output
            if [[ -s "$error_file" ]]; then
                error_log=$(cat "$error_file")
                all_errors="${all_errors}Attempt $attempt (exit $last_exit_code): ${error_log}\n"
            else
                all_errors="${all_errors}Attempt $attempt (exit $last_exit_code): No error output captured\n"
            fi
            
            local error_desc=$(get_error_description $last_exit_code "$cmd_name")
            log FAIL "Command failed on attempt $attempt (exit code: $last_exit_code) - $error_desc"
            
            # Log the actual error if available
            if [[ -n "$error_log" ]] && [[ "$error_log" != *"No error output"* ]]; then
                log ERROR "Error details: $(echo "$error_log" | head -n 3 | tr '\n' ' ')"
            fi
            
            # Check if the error is retryable
            if ! is_retryable_error $last_exit_code "$command"; then
                log ERROR "Non-retryable error detected (exit code: $last_exit_code) - $error_desc"
                cleanup_temp_files
                return $last_exit_code
            fi
            
            # If this was the last attempt, don't wait
            if [ $attempt -eq $max_retries ]; then
                break
            fi
            
            # Calculate delay for next attempt
            local delay
            delay=$(calculate_delay $((attempt + 1)) $base_delay $backoff_multiplier $max_delay)
            
            log RETRY "Retrying in ${delay}s (attempt $((attempt + 1))/$max_retries)..."
            sleep $delay
            
            attempt=$((attempt + 1))
        fi
    done
    
    # All retries exhausted - provide comprehensive failure information
    log ERROR "❌ Command failed after $max_retries attempts"
    log ERROR "Final exit code: $last_exit_code - $(get_error_description $last_exit_code "$cmd_name")"
    
    # Display all error logs
    echo -e "\n${RED}🔍 DETAILED ERROR LOG:${NC}"
    echo -e "Command: $command"
    echo -e "All attempts and errors:"
    echo -e "$all_errors"
    
    # Provide next steps based on the command type and error
    provide_next_steps "$cmd_name" "$last_exit_code" "$command" "$error_log"
    
    cleanup_temp_files
    return $last_exit_code
}

# Provide next steps and troubleshooting guidance when all retries fail
provide_next_steps() {
    local cmd_name="$1"
    local exit_code="$2"
    local command="$3"
    local error_log="$4"
    
    echo -e "\n${YELLOW}🛠️  TROUBLESHOOTING NEXT STEPS:${NC}"
    echo -e "Command type: $cmd_name (exit code: $exit_code)"
    
    case $cmd_name in
        ssh)
            echo -e "\n${CYAN}SSH Connection Troubleshooting:${NC}"
            case $exit_code in
                255)
                    echo "• Check if the target host is reachable: ping <hostname>"
                    echo "• Verify SSH service is running: ssh -v <user@host> (verbose mode)"
                    echo "• Check firewall rules on target host (port 22 or custom port)"
                    echo "• Verify SSH key permissions: chmod 600 ~/.ssh/id_rsa"
                    echo "• Test network connectivity: telnet <hostname> <port>"
                    ;;
                126|127)
                    echo "• Check if SSH client is installed: which ssh"
                    echo "• Verify PATH includes SSH binary location"
                    echo "• Try absolute path: /usr/bin/ssh or /usr/local/bin/ssh"
                    ;;
                1)
                    echo "• Check SSH configuration: ~/.ssh/config"
                    echo "• Verify host key in ~/.ssh/known_hosts"
                    echo "• Try with StrictHostKeyChecking disabled: ssh -o StrictHostKeyChecking=no"
                    echo "• Check authentication: ssh-add -l (list loaded keys)"
                    ;;
                *)
                    echo "• Enable verbose SSH logging: ssh -vvv <user@host>"
                    echo "• Check system logs: journalctl -u ssh or /var/log/auth.log"
                    echo "• Verify DNS resolution: nslookup <hostname>"
                    ;;
            esac
            
            # Extract hostname for additional checks
            if echo "$command" | grep -oE '[a-zA-Z0-9.-]+@[a-zA-Z0-9.-]+' > /dev/null; then
                local connection=$(echo "$command" | grep -oE '[a-zA-Z0-9.-]+@[a-zA-Z0-9.-]+')
                echo -e "\n${BLUE}Quick diagnostic commands to try:${NC}"
                echo "  ping \$(echo '$connection' | cut -d@ -f2)"
                echo "  ssh -v $connection"
                echo "  ssh -o ConnectTimeout=10 -o BatchMode=yes $connection 'echo test'"
            fi
            ;;
            
        scp)
            echo -e "\n${CYAN}SCP Transfer Troubleshooting:${NC}"
            echo "• Verify source file exists and is readable"
            echo "• Check destination directory exists and is writable"
            echo "• Ensure sufficient disk space on destination"
            echo "• Test basic SSH connectivity first: ssh <user@host> 'echo test'"
            echo "• Try with verbose mode: scp -v <source> <destination>"
            if [[ $exit_code -eq 1 ]]; then
                echo "• Check file permissions: ls -la <source_file>"
                echo "• Verify destination path is correct"
            fi
            ;;
            
        rsync)
            echo -e "\n${CYAN}Rsync Synchronization Troubleshooting:${NC}"
            case $exit_code in
                5)
                    echo "• Check if rsync daemon is running on remote host"
                    echo "• Verify rsync is installed on both source and destination"
                    echo "• Try with SSH transport: rsync -e ssh <source> <destination>"
                    ;;
                10|11|12)
                    echo "• Check network stability and bandwidth"
                    echo "• Try with smaller batch size: rsync --max-size=100M"
                    echo "• Use compression: rsync -z for slow connections"
                    ;;
                30|35)
                    echo "• Increase timeout values: rsync --timeout=300"
                    echo "• Check for network congestion or rate limiting"
                    echo "• Consider running during off-peak hours"
                    ;;
                *)
                    echo "• Test with minimal options: rsync -v <source> <destination>"
                    echo "• Check available disk space on destination"
                    echo "• Verify file permissions and ownership"
                    ;;
            esac
            ;;
            
        *)
            echo -e "\n${CYAN}General Network Command Troubleshooting:${NC}"
            echo "• Check network connectivity: ping 8.8.8.8"
            echo "• Verify DNS resolution: nslookup google.com"
            echo "• Test with different network interface or connection"
            echo "• Check for proxy or firewall interference"
            ;;
    esac
    
    # Common suggestions for all command types
    echo -e "\n${GREEN}General Recovery Options:${NC}"
    echo "• Wait and try again later (temporary network issues)"
    echo "• Try from a different network location"
    echo "• Contact system administrator if persistent"
    echo "• Check system resources: df -h, free -m, top"
    
    # If error log contains specific patterns, provide targeted advice
    if [[ -n "$error_log" ]]; then
        echo -e "\n${YELLOW}Specific Error Analysis:${NC}"
        
        if echo "$error_log" | grep -qi "connection refused"; then
            echo "• 'Connection refused' - Service not running or wrong port"
            echo "• Check if SSH daemon is active: systemctl status ssh"
        elif echo "$error_log" | grep -qi "host key verification failed"; then
            echo "• 'Host key verification failed' - Remove old key: ssh-keygen -R <hostname>"
        elif echo "$error_log" | grep -qi "permission denied"; then
            echo "• 'Permission denied' - Check SSH key authentication or password"
        elif echo "$error_log" | grep -qi "network is unreachable"; then
            echo "• 'Network unreachable' - Check routing and network configuration"
        elif echo "$error_log" | grep -qi "timeout"; then
            echo "• 'Timeout' - Increase timeout values or check network latency"
        elif echo "$error_log" | grep -qi "no such file"; then
            echo "• 'No such file' - Verify source file path and permissions"
        fi
    fi
    
    echo -e "\n${BLUE}💡 For immediate retry with different parameters:${NC}"
    echo "  SSH_MAX_RETRIES=8 SSH_BASE_DELAY=5 SSH_MAX_DELAY=120 <retry_command>"
    echo -e "\n${BLUE}📋 To save this log for analysis:${NC}"
    echo "  <your_command> 2>&1 | tee ssh_error_$(date +%Y%m%d_%H%M%S).log"
}

# Wrapper for SSH commands with retry
ssh_retry() {
    local max_retries=${SSH_MAX_RETRIES:-$DEFAULT_MAX_RETRIES}
    local base_delay=${SSH_BASE_DELAY:-$DEFAULT_BASE_DELAY}
    local backoff_multiplier=${SSH_BACKOFF_MULTIPLIER:-$DEFAULT_BACKOFF_MULTIPLIER}
    local max_delay=${SSH_MAX_DELAY:-$DEFAULT_MAX_DELAY}
    
    retry_with_exponential_backoff $max_retries $base_delay $backoff_multiplier $max_delay ssh "$@"
}

# Wrapper for SCP commands with retry
scp_retry() {
    local max_retries=${SCP_MAX_RETRIES:-$DEFAULT_MAX_RETRIES}
    local base_delay=${SCP_BASE_DELAY:-$DEFAULT_BASE_DELAY}
    local backoff_multiplier=${SCP_BACKOFF_MULTIPLIER:-$DEFAULT_BACKOFF_MULTIPLIER}
    local max_delay=${SCP_MAX_DELAY:-$DEFAULT_MAX_DELAY}
    
    retry_with_exponential_backoff $max_retries $base_delay $backoff_multiplier $max_delay scp "$@"
}

# Wrapper for rsync commands with retry
rsync_retry() {
    local max_retries=${RSYNC_MAX_RETRIES:-$DEFAULT_MAX_RETRIES}
    local base_delay=${RSYNC_BASE_DELAY:-$DEFAULT_BASE_DELAY}
    local backoff_multiplier=${RSYNC_BACKOFF_MULTIPLIER:-$DEFAULT_BACKOFF_MULTIPLIER}
    local max_delay=${RSYNC_MAX_DELAY:-$DEFAULT_MAX_DELAY}
    
    retry_with_exponential_backoff $max_retries $base_delay $backoff_multiplier $max_delay rsync "$@"
}

# Enhanced wrapper for persistent SSH functions that adds retry capability
ssh_exec_persistent_retry() {
    local max_retries=${SSH_MAX_RETRIES:-$DEFAULT_MAX_RETRIES}
    local base_delay=${SSH_BASE_DELAY:-$DEFAULT_BASE_DELAY}
    local backoff_multiplier=${SSH_BACKOFF_MULTIPLIER:-$DEFAULT_BACKOFF_MULTIPLIER}
    local max_delay=${SSH_MAX_DELAY:-$DEFAULT_MAX_DELAY}
    
    local host="$1"
    local user="${2:-${USER}}"
    local port="${3:-22}"
    local ssh_key="$4"
    shift 4
    local command="$*"
    
    log INFO "Executing persistent SSH command with retry: $command"
    
    # Source the SSH persistent script if available
    local ssh_persistent_script="$(dirname "$0")/ssh-persistent.sh"
    if [[ -f "$ssh_persistent_script" ]]; then
        source "$ssh_persistent_script"
    else
        log ERROR "SSH persistent script not found at $ssh_persistent_script"
        return 1
    fi
    
    retry_with_exponential_backoff $max_retries $base_delay $backoff_multiplier $max_delay \
        ssh_exec_persistent "$host" "$user" "$port" "$ssh_key" "$command"
}

# Enhanced wrapper for persistent SSH copy that adds retry capability
ssh_copy_persistent_retry() {
    local max_retries=${RSYNC_MAX_RETRIES:-$DEFAULT_MAX_RETRIES}
    local base_delay=${RSYNC_BASE_DELAY:-$DEFAULT_BASE_DELAY}
    local backoff_multiplier=${RSYNC_BACKOFF_MULTIPLIER:-$DEFAULT_BACKOFF_MULTIPLIER}
    local max_delay=${RSYNC_MAX_DELAY:-$DEFAULT_MAX_DELAY}
    
    local mode="$1"  # "to" or "from"
    local host="$2"
    local user="${3:-${USER}}"
    local port="${4:-22}"
    local ssh_key="$5"
    local source="$6"
    local destination="$7"
    local extra_opts="$8"
    
    log INFO "Executing persistent SSH copy with retry: $mode $source -> $destination"
    
    # Source the SSH persistent script if available
    local ssh_persistent_script="$(dirname "$0")/ssh-persistent.sh"
    if [[ -f "$ssh_persistent_script" ]]; then
        source "$ssh_persistent_script"
    else
        log ERROR "SSH persistent script not found at $ssh_persistent_script"
        return 1
    fi
    
    retry_with_exponential_backoff $max_retries $base_delay $backoff_multiplier $max_delay \
        ssh_copy_persistent "$mode" "$host" "$user" "$port" "$ssh_key" "$source" "$destination" "$extra_opts"
}

# Show help
show_help() {
    cat << 'EOF'
SSH/Rsync Retry Wrapper with Exponential Backoff

USAGE:
    Source this script to use the retry functions:
        source ssh-retry-wrapper.sh
        
    Or call functions directly:
        ./ssh-retry-wrapper.sh ssh_retry user@host "command"
        ./ssh-retry-wrapper.sh rsync_retry -av source/ dest/

FUNCTIONS:
    retry_with_exponential_backoff MAX_RETRIES BASE_DELAY MULTIPLIER MAX_DELAY COMMAND
        Generic retry function with exponential backoff
        
    ssh_retry [ssh-options] user@host [command]
        SSH wrapper with retry logic
        
    scp_retry [scp-options] source destination
        SCP wrapper with retry logic
        
    rsync_retry [rsync-options] source destination
        Rsync wrapper with retry logic
        
    ssh_exec_persistent_retry HOST USER PORT SSH_KEY COMMAND
        Persistent SSH execution with retry
        
    ssh_copy_persistent_retry MODE HOST USER PORT SSH_KEY SOURCE DEST OPTS
        Persistent SSH copy with retry

ENVIRONMENT VARIABLES:
    SSH_MAX_RETRIES=4           Maximum retry attempts for SSH commands
    SSH_BASE_DELAY=1            Base delay in seconds for SSH retries
    SSH_BACKOFF_MULTIPLIER=2    Multiplier for exponential backoff
    SSH_MAX_DELAY=60            Maximum delay between retries
    
    SCP_MAX_RETRIES=4           Maximum retry attempts for SCP commands
    SCP_BASE_DELAY=1            Base delay for SCP retries
    
    RSYNC_MAX_RETRIES=4         Maximum retry attempts for rsync commands
    RSYNC_BASE_DELAY=1          Base delay for rsync retries

EXAMPLES:
    # Basic SSH with retry
    ssh_retry user@host "ls -la"
    
    # File copy with retry
    scp_retry file.txt user@host:/tmp/
    
    # Directory sync with retry
    rsync_retry -av ./local/ user@host:~/remote/
    
    # Persistent SSH with retry
    ssh_exec_persistent_retry "10.0.0.1" "ubuntu" "22" "" "docker ps"
    
    # Custom retry parameters
    SSH_MAX_RETRIES=6 SSH_BASE_DELAY=2 ssh_retry user@host "command"

RETRY SEQUENCE:
    Attempt 1: immediate
    Attempt 2: wait 1s
    Attempt 3: wait 2s  
    Attempt 4: wait 4s
    Attempt 5: wait 8s (or max_delay if smaller)

EXIT CODES:
    0: Success
    1: Invalid usage or non-retryable error
    N: Last command exit code after all retries exhausted
EOF
}

# Main function for command-line usage
main() {
    local command="$1"
    shift
    
    case "$command" in
        ssh_retry)
            ssh_retry "$@"
            ;;
        scp_retry)
            scp_retry "$@"
            ;;
        rsync_retry)
            rsync_retry "$@"
            ;;
        ssh_exec_persistent_retry)
            ssh_exec_persistent_retry "$@"
            ;;
        ssh_copy_persistent_retry)
            ssh_copy_persistent_retry "$@"
            ;;
        retry)
            retry_with_exponential_backoff "$@"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log ERROR "Unknown command: $command"
            log INFO "Use '$0 help' for usage information"
            return 1
            ;;
    esac
}

# If script is executed directly (not sourced), run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
