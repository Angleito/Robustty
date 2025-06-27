#!/bin/bash
# SSH Batch Executor - Execute multiple remote operations efficiently
# This script batches multiple SSH commands into single sessions to minimize connection overhead

set -e

# Source the SSH persistent connection manager
SSH_PERSISTENT_SCRIPT="$(dirname "$0")/ssh-persistent.sh"
if [[ -f "$SSH_PERSISTENT_SCRIPT" ]]; then
    source "$SSH_PERSISTENT_SCRIPT"
else
    echo "Error: SSH persistent script not found at $SSH_PERSISTENT_SCRIPT"
    exit 1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Global variables
BATCH_ID=""
OPERATION_COUNT=0
COMMANDS_QUEUE=()
HOST=""
USER=""
PORT="22"
SSH_KEY=""

# Generate unique batch ID
generate_batch_id() {
    BATCH_ID="batch_$(date +%Y%m%d_%H%M%S)_$$"
}

# Initialize batch session
init_batch_session() {
    local host="$1"
    local user="$2"
    local port="${3:-22}"
    local ssh_key="$4"
    
    if [[ -z "$host" ]]; then
        echo -e "${RED}❌ Error: Host is required${NC}"
        return 1
    fi
    
    HOST="$host"
    USER="${user:-${USER}}"
    PORT="$port"
    SSH_KEY="$ssh_key"
    
    generate_batch_id
    
    echo -e "${BLUE}🔄 Initializing SSH batch session${NC}"
    echo -e "${CYAN}📍 Target: $USER@$HOST:$PORT${NC}"
    echo -e "${CYAN}🆔 Batch ID: $BATCH_ID${NC}"
    
    # Establish persistent connection
    if ssh_connect_persistent "$HOST" "$USER" "$PORT" "$SSH_KEY"; then
        echo -e "${GREEN}✅ Batch session initialized successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to initialize batch session${NC}"
        return 1
    fi
}

# Add command to batch queue
add_command() {
    local command="$1"
    local description="${2:-Command $((OPERATION_COUNT + 1))}"
    
    if [[ -z "$command" ]]; then
        echo -e "${RED}❌ Error: Command cannot be empty${NC}"
        return 1
    fi
    
    COMMANDS_QUEUE+=("$description:::$command")
    ((OPERATION_COUNT++))
    
    echo -e "${BLUE}➕ Added to batch: $description${NC}"
}

# Execute all queued commands in a single SSH session
execute_batch() {
    if [[ $OPERATION_COUNT -eq 0 ]]; then
        echo -e "${YELLOW}⚠️  No commands in batch queue${NC}"
        return 0
    fi
    
    echo -e "${BLUE}🚀 Executing batch of $OPERATION_COUNT operations...${NC}"
    
    # Build comprehensive script that includes all operations
    local batch_script="
        set -e
        echo '=== SSH Batch Execution Started ==='
        echo 'Batch ID: $BATCH_ID'
        echo 'Host: \$(hostname)'
        echo 'Date: \$(date)'
        echo 'Operations: $OPERATION_COUNT'
        echo ''
        
        # Function to log operation results
        log_operation() {
            local op_num=\$1
            local description=\$2
            local status=\$3
            echo \"[Operation \$op_num] \$description: \$status\"
        }
        
        # Initialize counters
        success_count=0
        failure_count=0
        operation_num=1
        
        # Execute each operation
    "
    
    # Add each command to the batch script
    for queue_item in "${COMMANDS_QUEUE[@]}"; do
        local description="${queue_item%%:::*}"
        local command="${queue_item##*:::}"
        
        batch_script+="
        echo ''
        echo '--- Operation \$operation_num: $description ---'
        if $command; then
            log_operation \$operation_num '$description' 'SUCCESS'
            ((success_count++))
        else
            log_operation \$operation_num '$description' 'FAILED'
            ((failure_count++))
        fi
        ((operation_num++))
        "
    done
    
    # Add summary to batch script
    batch_script+="
        echo ''
        echo '=== Batch Execution Summary ==='
        echo \"Total operations: $OPERATION_COUNT\"
        echo \"Successful: \$success_count\"
        echo \"Failed: \$failure_count\"
        echo \"Batch ID: $BATCH_ID\"
        echo \"Completed at: \$(date)\"
        echo '=== SSH Batch Execution Completed ==='
        
        # Exit with appropriate code
        if [ \$failure_count -eq 0 ]; then
            exit 0
        else
            exit 1
        fi
    "
    
    # Execute the batch script
    if ssh_exec_persistent "$HOST" "$USER" "$PORT" "$SSH_KEY" "$batch_script"; then
        echo -e "${GREEN}✅ Batch execution completed successfully${NC}"
        echo -e "${GREEN}📊 All $OPERATION_COUNT operations completed${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Batch execution completed with some failures${NC}"
        echo -e "${YELLOW}📊 Check output above for detailed results${NC}"
        return 1
    fi
}

# Clean up batch session
cleanup_batch_session() {
    if [[ -n "$HOST" && -n "$USER" ]]; then
        echo -e "${BLUE}🧹 Cleaning up batch session...${NC}"
        ssh_disconnect_persistent "$HOST" "$USER" "$PORT"
        echo -e "${GREEN}✅ Batch session cleaned up${NC}"
    fi
    
    # Reset batch variables
    BATCH_ID=""
    OPERATION_COUNT=0
    COMMANDS_QUEUE=()
    HOST=""
    USER=""
    PORT="22"
    SSH_KEY=""
}

# Predefined operation templates
add_directory_operation() {
    local dir_path="$1"
    local description="Create directory: $dir_path"
    add_command "mkdir -p '$dir_path'" "$description"
}

add_backup_operation() {
    local source_dir="$1"
    local backup_dir="$2"
    local description="Backup $source_dir to $backup_dir"
    add_command "[ -d '$source_dir' ] && cp -r '$source_dir' '$backup_dir' || echo 'Source directory not found'" "$description"
}

add_cleanup_operation() {
    local target_pattern="$1"
    local description="Cleanup files matching: $target_pattern"
    add_command "find $target_pattern -type f -delete 2>/dev/null || true" "$description"
}

add_service_restart_operation() {
    local service_name="$1"
    local compose_file="${2:-docker-compose.yml}"
    local description="Restart service: $service_name"
    add_command "cd \$(dirname '$compose_file') && docker-compose -f '$compose_file' restart '$service_name'" "$description"
}

add_verification_operation() {
    local check_command="$1"
    local success_message="$2"
    local description="Verify: $success_message"
    add_command "if $check_command; then echo 'Verification passed: $success_message'; else echo 'Verification failed: $success_message'; exit 1; fi" "$description"
}

# Show help
show_help() {
    cat << EOF
SSH Batch Executor - Execute multiple remote operations efficiently

USAGE:
    Source this script and use the functions:
        source ssh-batch-executor.sh
        
    Or use command line interface:
        $0 <command> [options]

FUNCTIONS:
    init_batch_session HOST [USER] [PORT] [SSH_KEY]
        Initialize a batch session to the specified host
        
    add_command "COMMAND" "DESCRIPTION"
        Add a command to the batch queue
        
    execute_batch
        Execute all queued commands in a single SSH session
        
    cleanup_batch_session
        Clean up the batch session and persistent connection

PREDEFINED OPERATIONS:
    add_directory_operation PATH
        Add directory creation operation
        
    add_backup_operation SOURCE_DIR BACKUP_DIR
        Add backup operation
        
    add_cleanup_operation PATTERN
        Add cleanup operation
        
    add_service_restart_operation SERVICE [COMPOSE_FILE]
        Add Docker service restart operation
        
    add_verification_operation "CHECK_CMD" "SUCCESS_MSG"
        Add verification operation

EXAMPLES:
    # Basic usage
    init_batch_session "192.168.1.100" "ubuntu" "22" "~/.ssh/id_rsa"
    add_command "echo 'Hello World'" "Test echo"
    add_command "df -h" "Check disk space"
    execute_batch
    cleanup_batch_session
    
    # Using predefined operations
    init_batch_session "my-server.com" "root"
    add_directory_operation "/opt/myapp/logs"
    add_backup_operation "/opt/myapp/config" "/opt/myapp/backup/config_\$(date +%Y%m%d)"
    add_service_restart_operation "myapp" "/opt/myapp/docker-compose.yml"
    add_verification_operation "docker ps | grep myapp" "Service is running"
    execute_batch
    cleanup_batch_session

BENEFITS:
    • Minimizes SSH connection overhead
    • Reduces network latency impact
    • Better error handling and logging
    • Atomic operation grouping
    • Comprehensive execution reporting

EOF
}

# Command line interface
main() {
    local command="$1"
    shift
    
    case "$command" in
        init)
            init_batch_session "$@"
            ;;
        add)
            add_command "$@"
            ;;
        execute)
            execute_batch
            ;;
        cleanup)
            cleanup_batch_session
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown command: $command${NC}"
            echo "Use '$0 help' for usage information"
            return 1
            ;;
    esac
}

# If script is executed directly (not sourced), run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
