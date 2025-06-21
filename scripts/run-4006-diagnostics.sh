#!/bin/bash

# Discord 4006 Error Diagnostic Runner Script
# This script provides easy ways to run the Discord 4006 diagnostics

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "  Discord Error 4006 Diagnostic Tool"
    echo "=================================================="
    echo -e "${NC}"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running or not accessible"
        return 1
    fi
    return 0
}

# Function to check if docker-compose services are running
check_services() {
    if ! docker-compose ps | grep -q "robustty"; then
        print_warning "Robustty container is not running"
        return 1
    fi
    return 0
}

# Function to run diagnostics in Docker container
run_docker_diagnostics() {
    print_info "Running diagnostics in Docker container..."
    
    if ! check_docker; then
        print_error "Cannot run Docker diagnostics"
        return 1
    fi
    
    # Check if services are running
    if check_services; then
        print_info "Using running container..."
        docker-compose exec robustty python scripts/diagnose-discord-4006.py
    else
        print_info "Starting temporary container for diagnostics..."
        # Run with docker-compose run instead of exec
        docker-compose run --rm robustty python scripts/diagnose-discord-4006.py
    fi
}

# Function to run diagnostics locally
run_local_diagnostics() {
    print_info "Running diagnostics locally..."
    
    # Check if Discord token is set
    if [ -z "$DISCORD_TOKEN" ]; then
        print_error "DISCORD_TOKEN environment variable is not set"
        print_info "Please set your Discord bot token:"
        print_info "export DISCORD_TOKEN=your_bot_token_here"
        return 1
    fi
    
    # Check if Python is available
    if ! command -v python3 >/dev/null 2>&1; then
        print_error "Python 3 is not installed or not in PATH"
        return 1
    fi
    
    # Check if required packages are installed
    if ! python3 -c "import discord, aiohttp, yaml" >/dev/null 2>&1; then
        print_error "Required Python packages are not installed"
        print_info "Install with: pip install discord.py aiohttp pyyaml"
        return 1
    fi
    
    # Run the diagnostic script
    cd "$PROJECT_ROOT"
    python3 scripts/diagnose-discord-4006.py
}

# Function to show help
show_help() {
    print_header
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  -d, --docker     Run diagnostics in Docker container (default)"
    echo "  -l, --local      Run diagnostics locally"
    echo "  -h, --help       Show this help message"
    echo "  -s, --status     Check system status for diagnostics"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run in Docker (default)"
    echo "  $0 --docker          # Run in Docker explicitly"
    echo "  $0 --local           # Run locally (requires DISCORD_TOKEN)"
    echo "  $0 --status          # Check if ready to run diagnostics"
    echo ""
    echo "Prerequisites:"
    echo "  Docker mode: Docker and docker-compose must be installed"
    echo "  Local mode:  Python 3, discord.py, aiohttp, pyyaml, and DISCORD_TOKEN"
}

# Function to check system status
check_status() {
    print_header
    print_info "Checking system status for diagnostics..."
    echo ""
    
    # Check Docker
    if check_docker; then
        print_success "Docker is available"
        
        # Check if docker-compose.yml exists
        if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
            print_success "docker-compose.yml found"
            
            # Check container status
            if check_services; then
                print_success "Robustty container is running"
            else
                print_warning "Robustty container is not running (will start temporary container)"
            fi
        else
            print_warning "docker-compose.yml not found in project root"
        fi
    else
        print_error "Docker is not available"
    fi
    
    echo ""
    
    # Check local environment
    print_info "Checking local environment..."
    
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_VERSION=$(python3 --version 2>&1)
        print_success "Python 3 available: $PYTHON_VERSION"
        
        # Check packages
        if python3 -c "import discord" >/dev/null 2>&1; then
            DISCORD_VERSION=$(python3 -c "import discord; print(discord.__version__)" 2>/dev/null || echo "unknown")
            print_success "discord.py available: $DISCORD_VERSION"
        else
            print_warning "discord.py not installed locally"
        fi
        
        if python3 -c "import aiohttp, yaml" >/dev/null 2>&1; then
            print_success "aiohttp and pyyaml available"
        else
            print_warning "aiohttp or pyyaml not installed locally"
        fi
        
        # Check Discord token
        if [ -n "$DISCORD_TOKEN" ]; then
            print_success "DISCORD_TOKEN is set"
        else
            print_warning "DISCORD_TOKEN is not set"
        fi
    else
        print_error "Python 3 is not available"
    fi
    
    echo ""
    print_info "Status check complete"
}

# Main script logic
main() {
    case "${1:-}" in
        -h|--help)
            show_help
            exit 0
            ;;
        -s|--status)
            check_status
            exit 0
            ;;
        -l|--local)
            print_header
            run_local_diagnostics
            exit $?
            ;;
        -d|--docker|"")
            print_header
            run_docker_diagnostics
            exit $?
            ;;
        *)
            print_error "Unknown option: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Change to project directory
cd "$PROJECT_ROOT"

# Run main function
main "$@"