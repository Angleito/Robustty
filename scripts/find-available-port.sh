#!/bin/bash

# Find an available port starting from a base port
find_available_port() {
    local base_port=${1:-5000}
    local max_attempts=100
    
    for i in $(seq 0 $max_attempts); do
        local port=$((base_port + i))
        if ! lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo $port
            return 0
        fi
    done
    
    echo "Error: Could not find available port" >&2
    return 1
}

# Export the function for use in other scripts
if [ "$1" ]; then
    find_available_port "$1"
fi