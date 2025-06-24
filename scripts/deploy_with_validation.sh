#!/bin/bash
set -euo pipefail

# VPS Deployment Script with Cookie Validation
# This script deploys Robustty with comprehensive cookie health validation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
CONTAINER_NAME="${CONTAINER_NAME:-robustty-vps}"
IMAGE_NAME="${IMAGE_NAME:-robustty:latest}"
CONFIG_FILE="${CONFIG_FILE:-$PROJECT_DIR/config/vps_deployment_config.yaml}"
VALIDATION_SCRIPT="$PROJECT_DIR/scripts/vps_cookie_validation.py"
LOG_FILE="${LOG_FILE:-/var/log/robustty-deployment.log}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level="$1"
    shift
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" | tee -a "$LOG_FILE"
}

log_info() { log "INFO" "${BLUE}$*${NC}"; }
log_warn() { log "WARN" "${YELLOW}$*${NC}"; }
log_error() { log "ERROR" "${RED}$*${NC}"; }
log_success() { log "SUCCESS" "${GREEN}$*${NC}"; }

# Error handling
handle_error() {
    local exit_code=$?
    local line_number=$1
    log_error "Error occurred on line $line_number (exit code: $exit_code)"
    
    # Cleanup on error
    if docker ps -q -f name="$CONTAINER_NAME" > /dev/null 2>&1; then
        log_warn "Cleaning up failed deployment..."
        docker stop "$CONTAINER_NAME" > /dev/null 2>&1 || true
        docker rm "$CONTAINER_NAME" > /dev/null 2>&1 || true
    fi
    
    exit $exit_code
}

trap 'handle_error $LINENO' ERR

# Help function
show_help() {
    cat << EOF
VPS Deployment Script with Cookie Validation

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -c, --config FILE       Configuration file (default: vps_deployment_config.yaml)
    -n, --name NAME         Container name (default: robustty-vps)
    -i, --image IMAGE       Docker image name (default: robustty:latest)
    -v, --validate-only     Only run validation, don't deploy
    -s, --skip-validation   Skip pre-deployment validation
    -f, --force             Force deployment even if validation fails
    -b, --build             Build image before deployment
    --health-check-timeout SEC  Health check timeout (default: 120)

EXAMPLES:
    $0                                    # Basic deployment
    $0 --validate-only                   # Run only validation
    $0 --build --force                   # Build and force deploy
    $0 --config prod_config.yaml         # Use custom config

ENVIRONMENT VARIABLES:
    CONTAINER_NAME          Container name
    IMAGE_NAME              Docker image name
    CONFIG_FILE             Configuration file path
    LOG_FILE                Log file path
    VALIDATION_TIMEOUT      Validation timeout in seconds
    HEALTH_CHECK_TIMEOUT    Health check timeout in seconds
EOF
}

# Parse command line arguments
VALIDATE_ONLY=false
SKIP_VALIDATION=false
FORCE_DEPLOY=false
BUILD_IMAGE=false
HEALTH_CHECK_TIMEOUT=120

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -n|--name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -i|--image)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -v|--validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        -s|--skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        -f|--force)
            FORCE_DEPLOY=true
            shift
            ;;
        -b|--build)
            BUILD_IMAGE=true
            shift
            ;;
        --health-check-timeout)
            HEALTH_CHECK_TIMEOUT="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate environment
validate_environment() {
    log_info "Validating deployment environment..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        return 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        return 1
    fi
    
    # Check configuration file
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        return 1
    fi
    
    # Check validation script
    if [[ ! -f "$VALIDATION_SCRIPT" ]]; then
        log_error "Validation script not found: $VALIDATION_SCRIPT"
        return 1
    fi
    
    # Check required environment variables
    local required_vars=("DISCORD_TOKEN")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            log_warn "Required environment variable not set: $var"
        fi
    done
    
    # Create log directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    log_success "Environment validation passed"
    return 0
}

# Pre-deployment validation
pre_deployment_validation() {
    log_info "Running pre-deployment validation..."
    
    # Check if old container exists
    if docker ps -a -q -f name="$CONTAINER_NAME" > /dev/null 2>&1; then
        log_warn "Container $CONTAINER_NAME already exists"
        
        if docker ps -q -f name="$CONTAINER_NAME" > /dev/null 2>&1; then
            log_info "Stopping existing container..."
            docker stop "$CONTAINER_NAME" > /dev/null 2>&1
        fi
        
        log_info "Removing existing container..."
        docker rm "$CONTAINER_NAME" > /dev/null 2>&1
    fi
    
    # Validate Docker image
    if ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
        log_warn "Docker image $IMAGE_NAME not found locally"
        
        if $BUILD_IMAGE; then
            log_info "Building Docker image..."
            docker build -t "$IMAGE_NAME" "$PROJECT_DIR"
        else
            log_error "Image not found and --build not specified"
            return 1
        fi
    fi
    
    log_success "Pre-deployment validation passed"
    return 0
}

# Cookie validation
validate_cookies() {
    log_info "Validating cookie health..."
    
    # Create temporary container for validation
    local temp_container="${CONTAINER_NAME}-validation"
    
    # Run validation container
    local validation_config='{
        "health_endpoint": "http://localhost:8080",
        "cookie_directory": "/app/cookies",
        "platforms": ["youtube", "rumble", "odysee", "peertube"],
        "max_cookie_age_hours": 12,
        "timeout_seconds": 30,
        "min_cookies_per_platform": 1,
        "max_acceptable_failures": 2
    }'
    
    # Start container for validation
    log_info "Starting validation container..."
    docker run -d \
        --name "$temp_container" \
        --env-file <(env | grep -E '^(DISCORD_TOKEN|YOUTUBE_API_KEY|APIFY_API_KEY)=') \
        -v "$(pwd)/cookies:/app/cookies:ro" \
        -p 8081:8080 \
        "$IMAGE_NAME" > /dev/null
    
    # Wait for container to start
    local max_wait=30
    local wait_time=0
    while ! docker exec "$temp_container" curl -s http://localhost:8080/health > /dev/null 2>&1; do
        if (( wait_time >= max_wait )); then
            log_error "Validation container failed to start within ${max_wait}s"
            docker stop "$temp_container" > /dev/null 2>&1 || true
            docker rm "$temp_container" > /dev/null 2>&1 || true
            return 1
        fi
        sleep 1
        ((wait_time++))
    done
    
    # Run Python validation script inside container
    local validation_result
    if validation_result=$(docker exec "$temp_container" python3 -c "$validation_config" --exit-code 2>/dev/null); then
        log_success "Cookie validation passed"
        local cleanup_result=0
    else
        local exit_code=$?
        log_warn "Cookie validation failed (exit code: $exit_code)"
        
        # Get detailed validation report
        if docker exec "$temp_container" python3 -c "$validation_config" --verbose 2>/dev/null; then
            log_info "Detailed validation report generated"
        fi
        
        local cleanup_result=1
    fi
    
    # Cleanup validation container
    docker stop "$temp_container" > /dev/null 2>&1 || true
    docker rm "$temp_container" > /dev/null 2>&1 || true
    
    return $cleanup_result
}

# Deploy the bot
deploy_bot() {
    log_info "Deploying Robustty bot..."
    
    # Prepare volume mounts
    local volume_args=""
    
    # Cookie directory
    if [[ -d "$(pwd)/cookies" ]]; then
        volume_args="$volume_args -v $(pwd)/cookies:/app/cookies"
    fi
    
    # Log directory
    mkdir -p "$(pwd)/logs"
    volume_args="$volume_args -v $(pwd)/logs:/var/log/robustty"
    
    # Configuration
    volume_args="$volume_args -v $CONFIG_FILE:/app/config/config.yaml:ro"
    
    # Start the container
    log_info "Starting container $CONTAINER_NAME..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        --env-file <(env | grep -E '^(DISCORD_TOKEN|YOUTUBE_API_KEY|APIFY_API_KEY|REDIS_URL)=') \
        -p 8080:8080 \
        -p 9090:9090 \
        $volume_args \
        --health-cmd="curl -f http://localhost:8080/health || exit 1" \
        --health-interval=30s \
        --health-timeout=10s \
        --health-retries=3 \
        "$IMAGE_NAME"
    
    log_success "Container started successfully"
    return 0
}

# Post-deployment validation
post_deployment_validation() {
    log_info "Running post-deployment validation..."
    
    # Wait for container to be healthy
    log_info "Waiting for container to become healthy..."
    local max_wait=$HEALTH_CHECK_TIMEOUT
    local wait_time=0
    
    while true; do
        local health_status
        health_status=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
        
        case $health_status in
            "healthy")
                log_success "Container is healthy"
                break
                ;;
            "unhealthy")
                log_error "Container failed health check"
                docker logs --tail 50 "$CONTAINER_NAME"
                return 1
                ;;
            *)
                if (( wait_time >= max_wait )); then
                    log_error "Health check timeout after ${max_wait}s"
                    docker logs --tail 50 "$CONTAINER_NAME"
                    return 1
                fi
                sleep 5
                ((wait_time += 5))
                ;;
        esac
    done
    
    # Test health endpoints
    log_info "Testing health endpoints..."
    local endpoints=("/health" "/health/cookies" "/health/platforms" "/health/fallbacks")
    
    for endpoint in "${endpoints[@]}"; do
        if curl -s -f "http://localhost:8080$endpoint" > /dev/null; then
            log_success "Endpoint $endpoint is responding"
        else
            log_warn "Endpoint $endpoint is not responding"
        fi
    done
    
    # Run full validation
    log_info "Running comprehensive cookie validation..."
    if python3 "$VALIDATION_SCRIPT" --exit-code > /dev/null 2>&1; then
        log_success "Post-deployment validation passed"
    else
        log_warn "Post-deployment validation reported issues"
        python3 "$VALIDATION_SCRIPT" --verbose
    fi
    
    return 0
}

# Main deployment function
main() {
    log_info "Starting VPS deployment with validation"
    log_info "Container: $CONTAINER_NAME, Image: $IMAGE_NAME"
    log_info "Config: $CONFIG_FILE"
    
    # Validate environment
    validate_environment
    
    # Run validation only if requested
    if $VALIDATE_ONLY; then
        log_info "Running validation-only mode"
        validate_cookies
        exit $?
    fi
    
    # Pre-deployment validation
    pre_deployment_validation
    
    # Cookie validation (unless skipped)
    if ! $SKIP_VALIDATION; then
        if ! validate_cookies; then
            if $FORCE_DEPLOY; then
                log_warn "Cookie validation failed but proceeding due to --force flag"
            else
                log_error "Cookie validation failed. Use --force to deploy anyway."
                exit 1
            fi
        fi
    else
        log_warn "Skipping cookie validation"
    fi
    
    # Deploy the bot
    deploy_bot
    
    # Post-deployment validation
    if ! post_deployment_validation; then
        log_error "Post-deployment validation failed"
        
        # Show container logs for debugging
        log_info "Container logs (last 100 lines):"
        docker logs --tail 100 "$CONTAINER_NAME"
        
        if ! $FORCE_DEPLOY; then
            log_error "Deployment failed validation. Check logs and configuration."
            exit 1
        fi
    fi
    
    # Success
    log_success "Deployment completed successfully!"
    log_info "Container: $CONTAINER_NAME"
    log_info "Health endpoint: http://localhost:8080/health"
    log_info "Logs: docker logs -f $CONTAINER_NAME"
    
    # Show final status
    docker ps -f name="$CONTAINER_NAME"
}

# Run main function
main "$@"