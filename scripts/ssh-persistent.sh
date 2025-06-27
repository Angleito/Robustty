#!/bin/bash

# SSH Persistent Connection Manager
# This script establishes and manages persistent SSH connections using SSH control sockets (SSH multiplexing)
# Usage: source this script or call its functions to manage persistent SSH connections

set -e

# Configuration
SSH_CONTROL_DIR="${SSH_CONTROL_DIR:-${HOME}/.ssh/control}"
SSH_CONTROL_PERSIST="${SSH_CONTROL_PERSIST:-600}"  # Keep connection alive for 10 minutes after last use
DEFAULT_CONNECT_TIMEOUT=10
DEFAULT_SERVER_ALIVE_INTERVAL=60

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    
    case $level in
        INFO)  echo -e "${GREEN}[SSH-PERSIST]${NC} $message" ;;
        WARN)  echo -e "${YELLOW}[SSH-PERSIST]${NC} $message" ;;
        ERROR) echo -e "${RED}[SSH-PERSIST]${NC} $message" ;;
        DEBUG) echo -e "${BLUE}[SSH-PERSIST]${NC} $message" ;;
    esac
}

# Initialize SSH control directory
init_ssh_control() {
    if [[ ! -d "$SSH_CONTROL_DIR" ]]; then
        log INFO "Creating SSH control directory: $SSH_CONTROL_DIR"
        mkdir -p "$SSH_CONTROL_DIR"
        chmod 700 "$SSH_CONTROL_DIR"
    fi
}

# Generate control path for a given host
get_control_path() {
    local host="$1"
    local user="$2"
    local port="${3:-22}"
    
    if [[ -z "$host" ]]; then
        log ERROR "Host is required"
        return 1
    fi
    
    # Create a unique control path based on user@host:port
    local control_name="${user:-${USER}}@${host}:${port}"
    # Replace special characters with underscores for filename safety
    control_name=$(echo "$control_name" | sed 's/[^a-zA-Z0-9@.-]/_/g')
    echo "${SSH_CONTROL_DIR}/${control_name}"
}

# Establish persistent SSH connection
ssh_connect_persistent() {
    local host="$1"
    local user="${2:-${USER}}"
    local port="${3:-22}"
    local ssh_key="$4"
    local extra_opts="$5"
    
    if [[ -z "$host" ]]; then
        log ERROR "Usage: ssh_connect_persistent <host> [user] [port] [ssh_key] [extra_opts]"
        return 1
    fi
    
    init_ssh_control
    
    local control_path
    control_path=$(get_control_path "$host" "$user" "$port")
    
    # Check if connection already exists and is working
    if ssh_is_connected "$host" "$user" "$port" "$ssh_key"; then
        log INFO "✅ SSH connection to $user@$host:$port already established"
        return 0
    fi
    
    log INFO "🔗 Establishing persistent SSH connection to $user@$host:$port"
    
    # Build SSH command
    local ssh_cmd="ssh"
    
    # Add SSH key if specified
    if [[ -n "$ssh_key" && -f "$ssh_key" ]]; then
        ssh_cmd="$ssh_cmd -i \"$ssh_key\""
    fi
    
    # Add SSH multiplexing options
    ssh_cmd="$ssh_cmd -o ControlMaster=yes"
    ssh_cmd="$ssh_cmd -o ControlPath=\"$control_path\""
    ssh_cmd="$ssh_cmd -o ControlPersist=$SSH_CONTROL_PERSIST"
    
    # Add connection reliability options
    ssh_cmd="$ssh_cmd -o ConnectTimeout=$DEFAULT_CONNECT_TIMEOUT"
    ssh_cmd="$ssh_cmd -o ServerAliveInterval=$DEFAULT_SERVER_ALIVE_INTERVAL"
    ssh_cmd="$ssh_cmd -o ServerAliveCountMax=3"
    ssh_cmd="$ssh_cmd -o BatchMode=yes"
    ssh_cmd="$ssh_cmd -o StrictHostKeyChecking=no"
    
    # Add any extra options
    if [[ -n "$extra_opts" ]]; then
        ssh_cmd="$ssh_cmd $extra_opts"
    fi
    
    # Add port if not default
    if [[ "$port" != "22" ]]; then
        ssh_cmd="$ssh_cmd -p $port"
    fi
    
    # Add destination
    ssh_cmd="$ssh_cmd $user@$host"
    
    # Execute the connection in background
    log DEBUG "SSH command: $ssh_cmd -N -f"
    
    # Use eval to properly handle quoted arguments
    if eval "$ssh_cmd -N -f"; then
        log INFO "✅ Persistent SSH connection established to $user@$host:$port"
        log INFO "📍 Control socket: $control_path"
        return 0
    else
        log ERROR "❌ Failed to establish SSH connection to $user@$host:$port"
        return 1
    fi
}

# Check if SSH connection is active
ssh_is_connected() {
    local host="$1"
    local user="${2:-${USER}}"
    local port="${3:-22}"
    local ssh_key="$4"
    
    if [[ -z "$host" ]]; then
        return 1
    fi
    
    local control_path
    control_path=$(get_control_path "$host" "$user" "$port")
    
    # Check if control socket exists and is functional
    if [[ -S "$control_path" ]]; then
        local ssh_cmd="ssh"
        
        if [[ -n "$ssh_key" && -f "$ssh_key" ]]; then
            ssh_cmd="$ssh_cmd -i \"$ssh_key\""
        fi
        
        ssh_cmd="$ssh_cmd -o ControlPath=\"$control_path\""
        
        if [[ "$port" != "22" ]]; then
            ssh_cmd="$ssh_cmd -p $port"
        fi
        
        # Test the connection with a simple command
        if eval "$ssh_cmd $user@$host echo 'connection_test' >/dev/null 2>&1"; then
            return 0
        fi
    fi
    
    return 1
}

# Execute command over persistent SSH connection
ssh_exec_persistent() {
    local host="$1"
    local user="${2:-${USER}}"
    local port="${3:-22}"
    local ssh_key="$4"
    shift 4
    local command="$*"
    
    if [[ -z "$host" || -z "$command" ]]; then
        log ERROR "Usage: ssh_exec_persistent <host> [user] [port] [ssh_key] <command>"
        return 1
    fi
    
    # Ensure connection is established
    if ! ssh_connect_persistent "$host" "$user" "$port" "$ssh_key"; then
        log ERROR "Failed to establish SSH connection"
        return 1
    fi
    
    local control_path
    control_path=$(get_control_path "$host" "$user" "$port")
    
    # Build SSH command for execution
    local ssh_cmd="ssh"
    
    if [[ -n "$ssh_key" && -f "$ssh_key" ]]; then
        ssh_cmd="$ssh_cmd -i \"$ssh_key\""
    fi
    
    ssh_cmd="$ssh_cmd -o ControlPath=\"$control_path\""
    
    if [[ "$port" != "22" ]]; then
        ssh_cmd="$ssh_cmd -p $port"
    fi
    
    # Execute the command
    eval "$ssh_cmd $user@$host \"$command\""
}

# Copy files using persistent SSH connection
ssh_copy_persistent() {
    local mode="$1"  # "to" or "from"
    local host="$2"
    local user="${3:-${USER}}"
    local port="${4:-22}"
    local ssh_key="$5"
    local source="$6"
    local destination="$7"
    local extra_opts="$8"
    
    if [[ -z "$mode" || -z "$host" || -z "$source" || -z "$destination" ]]; then
        log ERROR "Usage: ssh_copy_persistent <to|from> <host> [user] [port] [ssh_key] <source> <destination> [rsync_opts]"
        return 1
    fi
    
    # Ensure connection is established
    if ! ssh_connect_persistent "$host" "$user" "$port" "$ssh_key"; then
        log ERROR "Failed to establish SSH connection"
        return 1
    fi
    
    local control_path
    control_path=$(get_control_path "$host" "$user" "$port")
    
    # Build SSH options for rsync
    local ssh_opts="-o ControlPath=\"$control_path\""
    
    if [[ -n "$ssh_key" && -f "$ssh_key" ]]; then
        ssh_opts="$ssh_opts -i \"$ssh_key\""
    fi
    
    if [[ "$port" != "22" ]]; then
        ssh_opts="$ssh_opts -p $port"
    fi
    
    # Build rsync command
    local rsync_cmd="rsync -avz --progress"
    
    if [[ -n "$extra_opts" ]]; then
        rsync_cmd="$rsync_cmd $extra_opts"
    fi
    
    rsync_cmd="$rsync_cmd -e \"ssh $ssh_opts\""
    
    if [[ "$mode" == "to" ]]; then
        # Copy to remote
        rsync_cmd="$rsync_cmd \"$source\" \"$user@$host:$destination\""
    elif [[ "$mode" == "from" ]]; then
        # Copy from remote
        rsync_cmd="$rsync_cmd \"$user@$host:$source\" \"$destination\""
    else
        log ERROR "Invalid mode: $mode. Use 'to' or 'from'"
        return 1
    fi
    
    log INFO "📦 Copying files via persistent SSH connection..."
    log DEBUG "Rsync command: $rsync_cmd"
    
    eval "$rsync_cmd"
}

# Close persistent SSH connection
ssh_disconnect_persistent() {
    local host="$1"
    local user="${2:-${USER}}"
    local port="${3:-22}"
    
    if [[ -z "$host" ]]; then
        log ERROR "Usage: ssh_disconnect_persistent <host> [user] [port]"
        return 1
    fi
    
    local control_path
    control_path=$(get_control_path "$host" "$user" "$port")
    
    if [[ -S "$control_path" ]]; then
        log INFO "🔌 Disconnecting persistent SSH connection to $user@$host:$port"
        
        # Send exit command to master connection
        if ssh -o ControlPath="$control_path" -O exit "$user@$host" 2>/dev/null; then
            log INFO "✅ SSH connection closed"
        else
            log WARN "Connection may have already been closed"
        fi
        
        # Remove control socket if it still exists
        if [[ -S "$control_path" ]]; then
            rm -f "$control_path"
        fi
    else
        log WARN "No active SSH connection found for $user@$host:$port"
    fi
}

# List active persistent SSH connections
ssh_list_persistent() {
    init_ssh_control
    
    log INFO "📋 Active persistent SSH connections:"
    
    local count=0
    for control_socket in "$SSH_CONTROL_DIR"/*; do
        if [[ -S "$control_socket" ]]; then
            local connection_name
            connection_name=$(basename "$control_socket")
            echo "  🔗 $connection_name"
            ((count++))
        fi
    done
    
    if [[ $count -eq 0 ]]; then
        echo "  (No active connections)"
    fi
    
    echo "  Total: $count connection(s)"
}

# Clean up stale control sockets
ssh_cleanup_persistent() {
    init_ssh_control
    
    log INFO "🧹 Cleaning up stale SSH control sockets..."
    
    local cleaned=0
    for control_socket in "$SSH_CONTROL_DIR"/*; do
        if [[ -e "$control_socket" && ! -S "$control_socket" ]]; then
            log DEBUG "Removing stale control file: $(basename "$control_socket")"
            rm -f "$control_socket"
            ((cleaned++))
        fi
    done
    
    log INFO "✅ Cleaned up $cleaned stale control socket(s)"
}

# Helper function to parse connection string (user@host:port)
parse_connection_string() {
    local connection_string="$1"
    local default_user="${2:-${USER}}"
    local default_port="${3:-22}"
    
    # Extract user, host, and port from connection string
    local user="$default_user"
    local host=""
    local port="$default_port"
    
    # Handle user@host:port format
    if [[ "$connection_string" =~ ^([^@]+)@([^:]+):([0-9]+)$ ]]; then
        user="${BASH_REMATCH[1]}"
        host="${BASH_REMATCH[2]}"
        port="${BASH_REMATCH[3]}"
    # Handle user@host format
    elif [[ "$connection_string" =~ ^([^@]+)@([^:]+)$ ]]; then
        user="${BASH_REMATCH[1]}"
        host="${BASH_REMATCH[2]}"
    # Handle host:port format
    elif [[ "$connection_string" =~ ^([^:]+):([0-9]+)$ ]]; then
        host="${BASH_REMATCH[1]}"
        port="${BASH_REMATCH[2]}"
    # Handle just host
    else
        host="$connection_string"
    fi
    
    echo "$user $host $port"
}

# Main function for command-line usage
main() {
    local command="$1"
    shift
    
    case "$command" in
        connect|establish)
            local connection_info
            connection_info=($(parse_connection_string "$1" "$2" "$3"))
            ssh_connect_persistent "${connection_info[@]}" "$4" "$5"
            ;;
        disconnect|close)
            local connection_info
            connection_info=($(parse_connection_string "$1" "$2" "$3"))
            ssh_disconnect_persistent "${connection_info[@]}"
            ;;
        exec|run)
            local connection_string="$1"
            shift
            local connection_info
            connection_info=($(parse_connection_string "$connection_string"))
            ssh_exec_persistent "${connection_info[@]}" "" "$@"
            ;;
        copy)
            local mode="$1"
            local connection_string="$2"
            shift 2
            local connection_info
            connection_info=($(parse_connection_string "$connection_string"))
            ssh_copy_persistent "$mode" "${connection_info[@]}" "" "$@"
            ;;
        list|ls)
            ssh_list_persistent
            ;;
        cleanup|clean)
            ssh_cleanup_persistent
            ;;
        test)
            local connection_info
            connection_info=($(parse_connection_string "$1" "$2" "$3"))
            if ssh_is_connected "${connection_info[@]}" "$4"; then
                log INFO "✅ SSH connection to ${connection_info[1]} is active"
                return 0
            else
                log WARN "❌ No active SSH connection to ${connection_info[1]}"
                return 1
            fi
            ;;
        help|--help|-h)
            cat << EOF
SSH Persistent Connection Manager

Usage: $0 <command> [options]

Commands:
    connect <host> [user] [port] [ssh_key] [extra_opts]
        Establish a persistent SSH connection
        Examples:
            $0 connect 192.168.1.100
            $0 connect example.com ubuntu 22 ~/.ssh/id_rsa
            $0 connect user@host:2222

    disconnect <host> [user] [port]
        Close a persistent SSH connection
        Examples:
            $0 disconnect 192.168.1.100
            $0 disconnect user@host:2222

    exec <connection> <command>
        Execute a command over persistent SSH connection
        Examples:
            $0 exec 192.168.1.100 "ls -la"
            $0 exec user@host:2222 "docker ps"

    copy <to|from> <connection> <source> <destination> [rsync_opts]
        Copy files using persistent SSH connection
        Examples:
            $0 copy to 192.168.1.100 ./local/file.txt /remote/path/
            $0 copy from user@host ./remote/dir/ ./local/dir/

    list
        List active persistent SSH connections

    test <host> [user] [port] [ssh_key]
        Test if SSH connection is active
        Examples:
            $0 test 192.168.1.100
            $0 test user@host:2222

    cleanup
        Clean up stale control sockets

    help
        Show this help message

Environment Variables:
    SSH_CONTROL_DIR         Directory for control sockets (default: ~/.ssh/control)
    SSH_CONTROL_PERSIST     How long to keep connection alive (default: 600 seconds)

EOF
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
