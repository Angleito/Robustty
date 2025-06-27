# Persistent SSH Connection Manager

This system implements SSH multiplexing (persistent SSH connections) to improve performance and reduce connection overhead when running multiple SSH operations against a VPS.

## Overview

Instead of creating a new SSH connection for each command, the system:
1. **Establishes one persistent SSH connection** at the start
2. **Reuses this connection** for all subsequent SSH commands
3. **Automatically manages** connection lifecycle and cleanup

This significantly improves performance when running multiple SSH operations in sequence.

## Key Benefits

- **Faster execution**: No connection setup overhead for subsequent commands
- **Reduced server load**: Fewer TCP connections and authentication attempts
- **Better reliability**: Connection sharing reduces timeout issues
- **Automatic management**: Handles connection lifecycle transparently

## Core Components

### 1. SSH Persistent Manager (`scripts/ssh-persistent.sh`)

Main script that provides persistent SSH connection functionality:

```bash
# Establish connection
ssh_connect_persistent "hostname" "user" "port" "ssh_key"

# Execute commands using persistent connection
ssh_exec_persistent "hostname" "user" "port" "ssh_key" "command"

# Copy files using persistent connection
ssh_copy_persistent "to|from" "hostname" "user" "port" "ssh_key" "source" "dest"

# Check if connection is active
ssh_is_connected "hostname" "user" "port" "ssh_key"

# Clean up connection
ssh_disconnect_persistent "hostname" "user" "port"
```

### 2. Updated Scripts

The following scripts have been updated to use persistent SSH:

- **`sync-cookies-to-vps.sh`**: Cookie synchronization using persistent SSH
- **`deploy-vps.sh`**: VPS deployment with persistent SSH connections
- **`example-persistent-ssh.sh`**: Demonstration script with various use cases

## How It Works

### SSH Control Sockets

The system uses SSH's built-in multiplexing feature via control sockets:

```bash
# Connection established with these options:
ssh -o ControlMaster=yes \
    -o ControlPath=~/.ssh/control/user@host:port \
    -o ControlPersist=600 \
    -N -f user@host
```

**Key Options:**
- `ControlMaster=yes`: This connection becomes the master
- `ControlPath`: Unix socket file for connection sharing
- `ControlPersist=600`: Keep connection alive 600 seconds after last use
- `-N`: Don't execute remote command (for master connection)
- `-f`: Run in background

### Connection Reuse

Subsequent commands reference the control socket:

```bash
# Reuses existing connection
ssh -o ControlPath=~/.ssh/control/user@host:port user@host "command"
```

## Usage Examples

### Basic Usage

```bash
# Source the persistent SSH functions
source scripts/ssh-persistent.sh

# Establish connection
ssh_connect_persistent "192.168.1.100" "ubuntu"

# Run multiple commands efficiently
ssh_exec_persistent "192.168.1.100" "ubuntu" "22" "" "whoami"
ssh_exec_persistent "192.168.1.100" "ubuntu" "22" "" "uptime"
ssh_exec_persistent "192.168.1.100" "ubuntu" "22" "" "docker ps"

# Copy files
ssh_copy_persistent "to" "192.168.1.100" "ubuntu" "22" "" "./local-file" "/remote/path/"

# Clean up when done
ssh_disconnect_persistent "192.168.1.100" "ubuntu"
```

### Command Line Usage

```bash
# Direct script usage
./scripts/ssh-persistent.sh connect 192.168.1.100
./scripts/ssh-persistent.sh exec 192.168.1.100 "uptime"
./scripts/ssh-persistent.sh copy to 192.168.1.100 ./file /remote/path/
./scripts/ssh-persistent.sh disconnect 192.168.1.100
```

### Integration in Deployment Scripts

```bash
#!/bin/bash
source scripts/ssh-persistent.sh

VPS_HOST="your-vps-ip"
VPS_USER="ubuntu"

# Establish persistent connection once
ssh_connect_persistent "$VPS_HOST" "$VPS_USER"

# Perform multiple operations efficiently
ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "mkdir -p ~/deployment"
ssh_copy_persistent "to" "$VPS_HOST" "$VPS_USER" "22" "" "./app" "~/deployment/"
ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "cd ~/deployment && docker-compose up -d"
ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "" "docker ps"

# Connection automatically cleaned up after ControlPersist timeout
```

## Configuration

### Environment Variables

- `SSH_CONTROL_DIR`: Directory for control sockets (default: `~/.ssh/control`)
- `SSH_CONTROL_PERSIST`: Connection timeout in seconds (default: `600`)

### SSH Client Configuration

You can also configure SSH multiplexing in `~/.ssh/config`:

```
Host your-vps
    HostName 192.168.1.100
    User ubuntu
    ControlMaster auto
    ControlPath ~/.ssh/control/%r@%h:%p
    ControlPersist 600
```

## Performance Comparison

### Without Persistent SSH
```bash
# Each command creates new connection
ssh user@host "command1"  # ~2-3 seconds
ssh user@host "command2"  # ~2-3 seconds  
ssh user@host "command3"  # ~2-3 seconds
# Total: ~6-9 seconds
```

### With Persistent SSH
```bash
ssh_connect_persistent "host" "user"        # ~2-3 seconds
ssh_exec_persistent "host" "user" "command1"  # ~0.1 seconds
ssh_exec_persistent "host" "user" "command2"  # ~0.1 seconds
ssh_exec_persistent "host" "user" "command3"  # ~0.1 seconds
# Total: ~2.5 seconds
```

## Troubleshooting

### Check Active Connections

```bash
# List active persistent connections
./scripts/ssh-persistent.sh list

# Test specific connection
./scripts/ssh-persistent.sh test 192.168.1.100
```

### Clean Up Stale Connections

```bash
# Clean up stale control sockets
./scripts/ssh-persistent.sh cleanup

# Force disconnect specific connection
./scripts/ssh-persistent.sh disconnect 192.168.1.100
```

### Debug Connection Issues

```bash
# Enable debug output
SSH_PERSISTENT_DEBUG=1 ./scripts/ssh-persistent.sh connect 192.168.1.100

# Check control socket exists
ls -la ~/.ssh/control/

# Test manual SSH with control path
ssh -o ControlPath=~/.ssh/control/ubuntu@192.168.1.100:22 ubuntu@192.168.1.100 "echo test"
```

## Best Practices

1. **Establish connection early**: Set up persistent connection before multiple operations
2. **Use in scripts**: Integrate into deployment and maintenance scripts
3. **Handle errors**: Check connection status before critical operations
4. **Clean up**: Disconnect when done or rely on timeout
5. **Monitor connections**: Use `list` command to track active connections

## Security Considerations

- Control sockets are created with restrictive permissions (600)
- Control directory has 700 permissions
- Uses existing SSH key authentication
- No additional credentials stored
- Connection inherits SSH security settings

## Integration with Existing Scripts

The persistent SSH system is designed to be a drop-in replacement for regular SSH commands in existing scripts. Simply:

1. Source the persistent SSH script
2. Replace `ssh` calls with `ssh_exec_persistent`
3. Replace `scp`/`rsync` calls with `ssh_copy_persistent`
4. Add initial `ssh_connect_persistent` call

This allows gradual migration of existing automation scripts to use persistent connections for better performance.
