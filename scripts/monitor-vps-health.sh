#!/bin/bash

# VPS Health Monitoring Script for Robustty Discord Bot
# Provides continuous monitoring of bot health, performance, and system resources
# with alerting, logging, and automatic recovery capabilities.

set -e

# Configuration
SCRIPT_NAME="$(basename "$0")"
MONITOR_LOG="/var/log/robustty-health-monitor.log"
STATUS_FILE="/tmp/robustty-health-status.json"
ALERT_LOG="/var/log/robustty-alerts.log"
METRICS_LOG="/var/log/robustty-metrics.log"

# Monitoring intervals (in seconds)
HEALTH_CHECK_INTERVAL=30
RESOURCE_CHECK_INTERVAL=60
DISCORD_CHECK_INTERVAL=120
PLATFORM_CHECK_INTERVAL=300

# Thresholds
CPU_THRESHOLD=80
MEMORY_THRESHOLD=85
DISK_THRESHOLD=90
RESPONSE_TIME_THRESHOLD=5
ERROR_RATE_THRESHOLD=10

# Recovery settings
MAX_RESTART_ATTEMPTS=3
RESTART_COOLDOWN=300
HEALTH_FAILURE_THRESHOLD=3

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Global state
declare -A service_status
declare -A failure_counts
declare -A last_restart_time
restart_attempts=0
monitoring_start_time=$(date +%s)

# Logging functions
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "$timestamp [$level] $message" >> "$MONITOR_LOG"
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" ;;
        ALERT) 
            echo -e "${RED}[ALERT]${NC} $message"
            echo "$timestamp [ALERT] $message" >> "$ALERT_LOG"
            ;;
        METRIC)
            echo "$timestamp $message" >> "$METRICS_LOG"
            ;;
    esac
}

# Alert function
send_alert() {
    local severity=$1
    local component=$2
    local message="$3"
    local full_message="[$severity] $component: $message"
    
    log ALERT "$full_message"
    
    # Future: Integration with external alerting systems
    # - Webhook notifications
    # - Email alerts
    # - Slack/Discord notifications
    # - PagerDuty integration
}

# Initialize monitoring
initialize_monitoring() {
    log INFO "🚀 Initializing Robustty VPS Health Monitoring"
    
    # Create log directories
    mkdir -p "$(dirname "$MONITOR_LOG")" "$(dirname "$ALERT_LOG")" "$(dirname "$METRICS_LOG")"
    
    # Initialize service status
    service_status["bot_container"]="unknown"
    service_status["redis_container"]="unknown"
    service_status["discord_connection"]="unknown"
    service_status["health_endpoint"]="unknown"
    service_status["system_resources"]="unknown"
    
    # Initialize failure counts
    for service in "${!service_status[@]}"; do
        failure_counts["$service"]=0
        last_restart_time["$service"]=0
    done
    
    log INFO "Health monitoring initialized at $(date)"
    log INFO "Monitoring configuration:"
    log INFO "  - Health check interval: ${HEALTH_CHECK_INTERVAL}s"
    log INFO "  - Resource check interval: ${RESOURCE_CHECK_INTERVAL}s"
    log INFO "  - CPU threshold: ${CPU_THRESHOLD}%"
    log INFO "  - Memory threshold: ${MEMORY_THRESHOLD}%"
    log INFO "  - Response time threshold: ${RESPONSE_TIME_THRESHOLD}s"
}

# Check Docker container health
check_container_health() {
    log DEBUG "Checking Docker container health..."
    
    # Check bot container
    if docker-compose ps | grep -q 'robustty-bot.*Up'; then
        service_status["bot_container"]="healthy"
        failure_counts["bot_container"]=0
        log DEBUG "✅ Bot container is running"
    else
        service_status["bot_container"]="unhealthy"
        ((failure_counts["bot_container"]++))
        send_alert "CRITICAL" "Bot Container" "Container is not running (failure count: ${failure_counts["bot_container"]})"
        
        if [ ${failure_counts["bot_container"]} -ge $HEALTH_FAILURE_THRESHOLD ]; then
            attempt_service_recovery "bot_container"
        fi
    fi
    
    # Check Redis container
    if docker-compose ps | grep -q 'robustty-redis.*Up'; then
        service_status["redis_container"]="healthy"
        failure_counts["redis_container"]=0
        log DEBUG "✅ Redis container is running"
    else
        service_status["redis_container"]="unhealthy"
        ((failure_counts["redis_container"]++))
        send_alert "CRITICAL" "Redis Container" "Container is not running (failure count: ${failure_counts["redis_container"]})"
        
        if [ ${failure_counts["redis_container"]} -ge $HEALTH_FAILURE_THRESHOLD ]; then
            attempt_service_recovery "redis_container"
        fi
    fi
}

# Check health endpoint
check_health_endpoint() {
    log DEBUG "Checking health endpoint..."
    
    local start_time=$(date +%s.%3N)
    local health_response=$(curl -s --max-time "$RESPONSE_TIME_THRESHOLD" http://localhost:8080/health 2>/dev/null || echo "")
    local end_time=$(date +%s.%3N)
    local response_time=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "999")
    
    if echo "$health_response" | grep -q -E '(status.*ok|healthy)'; then
        service_status["health_endpoint"]="healthy"
        failure_counts["health_endpoint"]=0
        log DEBUG "✅ Health endpoint responding (${response_time}s)"
        log METRIC "health_endpoint_response_time:$response_time"
    else
        service_status["health_endpoint"]="unhealthy"
        ((failure_counts["health_endpoint"]++))
        send_alert "WARNING" "Health Endpoint" "Not responding or unhealthy (${response_time}s, failure count: ${failure_counts["health_endpoint"]})"
        log METRIC "health_endpoint_response_time:$response_time:failed"
    fi
}

# Check Discord connectivity
check_discord_connectivity() {
    log DEBUG "Checking Discord connectivity..."
    
    # Check Discord API accessibility
    if curl -s --max-time 10 https://discord.com/api/v10/gateway >/dev/null 2>&1; then
        # Check bot logs for connection status
        local recent_logs=$(docker-compose logs --tail=20 robustty 2>/dev/null)
        
        if echo "$recent_logs" | grep -q -E "(heartbeat|gateway|connected)" && ! echo "$recent_logs" | grep -q -E "(disconnected|error|failed)"; then
            service_status["discord_connection"]="healthy"
            failure_counts["discord_connection"]=0
            log DEBUG "✅ Discord connection appears healthy"
        else
            service_status["discord_connection"]="degraded"
            log DEBUG "⚠️  Discord connection status unclear from logs"
        fi
    else
        service_status["discord_connection"]="unhealthy"
        ((failure_counts["discord_connection"]++))
        send_alert "CRITICAL" "Discord Connection" "Cannot reach Discord API (failure count: ${failure_counts["discord_connection"]})"
    fi
}

# Check system resources
check_system_resources() {
    log DEBUG "Checking system resources..."
    
    # CPU usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 | cut -d'u' -f1 || echo "0")
    cpu_usage=${cpu_usage%.*}  # Remove decimal part
    
    # Memory usage
    local memory_info=$(free | grep "Mem:")
    local total_memory=$(echo $memory_info | awk '{print $2}')
    local used_memory=$(echo $memory_info | awk '{print $3}')
    local memory_percentage=$((used_memory * 100 / total_memory))
    
    # Disk usage
    local disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    
    # Container resource usage
    local bot_stats=$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep robustty-bot || echo "robustty-bot 0.00% 0B / 0B")
    local bot_cpu=$(echo "$bot_stats" | awk '{print $2}' | sed 's/%//' | cut -d'.' -f1 || echo "0")
    local bot_memory=$(echo "$bot_stats" | awk '{print $3}' | cut -d'/' -f1 | sed 's/MiB//' | cut -d'.' -f1 || echo "0")
    
    # Log metrics
    log METRIC "system_cpu_usage:$cpu_usage"
    log METRIC "system_memory_usage:$memory_percentage"
    log METRIC "system_disk_usage:$disk_usage"
    log METRIC "bot_cpu_usage:$bot_cpu"
    log METRIC "bot_memory_usage:$bot_memory"
    
    # Check thresholds
    local resource_issues=()
    
    if [ "$cpu_usage" -gt "$CPU_THRESHOLD" ]; then
        resource_issues+=("CPU: ${cpu_usage}% (threshold: ${CPU_THRESHOLD}%)")
    fi
    
    if [ "$memory_percentage" -gt "$MEMORY_THRESHOLD" ]; then
        resource_issues+=("Memory: ${memory_percentage}% (threshold: ${MEMORY_THRESHOLD}%)")
    fi
    
    if [ "$disk_usage" -gt "$DISK_THRESHOLD" ]; then
        resource_issues+=("Disk: ${disk_usage}% (threshold: ${DISK_THRESHOLD}%)")
    fi
    
    if [ ${#resource_issues[@]} -eq 0 ]; then
        service_status["system_resources"]="healthy"
        failure_counts["system_resources"]=0
        log DEBUG "✅ System resources within acceptable limits"
    else
        service_status["system_resources"]="warning"
        ((failure_counts["system_resources"]++))
        
        local issue_list=$(IFS=', '; echo "${resource_issues[*]}")
        send_alert "WARNING" "System Resources" "High resource usage: $issue_list"
    fi
}

# Check platform APIs
check_platform_apis() {
    log DEBUG "Checking platform API connectivity..."
    
    local api_failures=0
    
    # YouTube API (if configured)
    if grep -q '^YOUTUBE_API_KEY=' .env 2>/dev/null && [ -n "$(grep '^YOUTUBE_API_KEY=' .env | cut -d'=' -f2-)" ]; then
        if ! curl -s --max-time 10 "https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&key=$(grep '^YOUTUBE_API_KEY=' .env | cut -d'=' -f2-)&maxResults=1" >/dev/null 2>&1; then
            ((api_failures++))
            log DEBUG "⚠️  YouTube API not accessible"
        fi
    fi
    
    # Apify API (if configured)
    if grep -q '^APIFY_API_KEY=' .env 2>/dev/null && [ -n "$(grep '^APIFY_API_KEY=' .env | cut -d'=' -f2-)" ]; then
        if ! curl -s --max-time 10 "https://api.apify.com/v2/acts?token=$(grep '^APIFY_API_KEY=' .env | cut -d'=' -f2-)" >/dev/null 2>&1; then
            ((api_failures++))
            log DEBUG "⚠️  Apify API not accessible"
        fi
    fi
    
    # General platform connectivity
    local platforms=("youtube.com" "rumble.com" "odysee.com")
    for platform in "${platforms[@]}"; do
        if ! curl -s --max-time 10 "https://$platform" >/dev/null 2>&1; then
            ((api_failures++))
            log DEBUG "⚠️  $platform not accessible"
        fi
    done
    
    if [ $api_failures -eq 0 ]; then
        log DEBUG "✅ Platform APIs accessible"
    else
        send_alert "WARNING" "Platform APIs" "$api_failures platform(s) not accessible"
    fi
}

# Attempt service recovery
attempt_service_recovery() {
    local service=$1
    local current_time=$(date +%s)
    local last_restart=${last_restart_time["$service"]}
    
    # Check cooldown period
    if [ $((current_time - last_restart)) -lt $RESTART_COOLDOWN ]; then
        log WARN "Service $service in cooldown period, skipping restart"
        return
    fi
    
    # Check restart attempts
    if [ $restart_attempts -ge $MAX_RESTART_ATTEMPTS ]; then
        send_alert "CRITICAL" "Recovery" "Max restart attempts ($MAX_RESTART_ATTEMPTS) reached for $service"
        return
    fi
    
    log WARN "🔄 Attempting recovery for service: $service"
    send_alert "WARNING" "Recovery" "Attempting to restart $service (attempt $((restart_attempts + 1))/$MAX_RESTART_ATTEMPTS)"
    
    case $service in
        "bot_container"|"redis_container")
            if docker-compose restart robustty redis; then
                log INFO "✅ Services restarted successfully"
                last_restart_time["$service"]=$current_time
                ((restart_attempts++))
                
                # Wait and verify recovery
                sleep 30
                if docker-compose ps | grep -q "Up"; then
                    log INFO "✅ Service recovery successful"
                    restart_attempts=0  # Reset on successful recovery
                    failure_counts["$service"]=0
                else
                    log ERROR "❌ Service recovery failed"
                fi
            else
                log ERROR "❌ Failed to restart services"
                send_alert "CRITICAL" "Recovery" "Failed to restart $service"
            fi
            ;;
    esac
}

# Generate status report
generate_status_report() {
    local current_time=$(date +%s)
    local uptime=$((current_time - monitoring_start_time))
    
    # Create JSON status report
    cat > "$STATUS_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "uptime_seconds": $uptime,
    "services": {
        "bot_container": "${service_status["bot_container"]}",
        "redis_container": "${service_status["redis_container"]}",
        "discord_connection": "${service_status["discord_connection"]}",
        "health_endpoint": "${service_status["health_endpoint"]}",
        "system_resources": "${service_status["system_resources"]}"
    },
    "failure_counts": {
EOF
    
    local first=true
    for service in "${!failure_counts[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$STATUS_FILE"
        fi
        echo -n "        \"$service\": ${failure_counts["$service"]}" >> "$STATUS_FILE"
    done
    
    cat >> "$STATUS_FILE" << EOF

    },
    "restart_attempts": $restart_attempts,
    "alerts_today": $(grep "$(date +%Y-%m-%d)" "$ALERT_LOG" 2>/dev/null | wc -l || echo 0)
}
EOF
}

# Display dashboard
show_dashboard() {
    clear
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    ROBUSTTY HEALTH MONITOR                     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    local current_time=$(date '+%Y-%m-%d %H:%M:%S')
    local uptime_seconds=$(($(date +%s) - monitoring_start_time))
    local uptime_human=$(printf "%d:%02d:%02d" $((uptime_seconds/3600)) $(((uptime_seconds%3600)/60)) $((uptime_seconds%60)))
    
    echo -e "${CYAN}Current Time:${NC} $current_time"
    echo -e "${CYAN}Monitor Uptime:${NC} $uptime_human"
    echo -e "${CYAN}Total Restart Attempts:${NC} $restart_attempts"
    echo ""
    
    echo -e "${BLUE}SERVICE STATUS${NC}"
    echo "=============="
    
    for service in "${!service_status[@]}"; do
        local status="${service_status["$service"]}"
        local failures="${failure_counts["$service"]}"
        local service_display="${service//_/ }"
        
        case $status in
            "healthy") echo -e "${GREEN}✅${NC} $service_display (failures: $failures)" ;;
            "unhealthy") echo -e "${RED}❌${NC} $service_display (failures: $failures)" ;;
            "degraded"|"warning") echo -e "${YELLOW}⚠️${NC} $service_display (failures: $failures)" ;;
            *) echo -e "${CYAN}❓${NC} $service_display (failures: $failures)" ;;
        esac
    done
    
    echo ""
    echo -e "${BLUE}RECENT ALERTS${NC} (Last 10)"
    echo "============="
    if [ -f "$ALERT_LOG" ]; then
        tail -10 "$ALERT_LOG" | while read -r line; do
            echo -e "${YELLOW}⚠️${NC} $line"
        done
    else
        echo "No alerts logged"
    fi
    
    echo ""
    echo -e "${BLUE}CONTROLS${NC}"
    echo "========"
    echo "Press 'q' to quit, 'r' to restart services, 's' to show full status"
}

# Interactive mode
interactive_mode() {
    log INFO "Starting interactive monitoring mode"
    
    while true; do
        # Perform health checks
        check_container_health
        check_health_endpoint
        check_system_resources
        
        # Generate and show dashboard
        generate_status_report
        show_dashboard
        
        # Wait for input with timeout
        read -t $HEALTH_CHECK_INTERVAL -n 1 key 2>/dev/null || key=""
        
        case $key in
            'q'|'Q')
                log INFO "Interactive monitoring stopped by user"
                break
                ;;
            'r'|'R')
                log INFO "Manual service restart requested"
                docker-compose restart
                sleep 5
                ;;
            's'|'S')
                less "$STATUS_FILE"
                ;;
        esac
    done
}

# Daemon mode
daemon_mode() {
    log INFO "Starting daemon monitoring mode"
    
    local last_resource_check=0
    local last_discord_check=0
    local last_platform_check=0
    
    while true; do
        local current_time=$(date +%s)
        
        # Always check container health and health endpoint
        check_container_health
        check_health_endpoint
        
        # Check system resources periodically
        if [ $((current_time - last_resource_check)) -ge $RESOURCE_CHECK_INTERVAL ]; then
            check_system_resources
            last_resource_check=$current_time
        fi
        
        # Check Discord connectivity periodically
        if [ $((current_time - last_discord_check)) -ge $DISCORD_CHECK_INTERVAL ]; then
            check_discord_connectivity
            last_discord_check=$current_time
        fi
        
        # Check platform APIs periodically
        if [ $((current_time - last_platform_check)) -ge $PLATFORM_CHECK_INTERVAL ]; then
            check_platform_apis
            last_platform_check=$current_time
        fi
        
        # Generate status report
        generate_status_report
        
        sleep $HEALTH_CHECK_INTERVAL
    done
}

# Cleanup function
cleanup() {
    log INFO "🧹 Stopping health monitoring..."
    
    # Generate final report
    generate_status_report
    
    local total_uptime=$(($(date +%s) - monitoring_start_time))
    log INFO "Health monitoring stopped after ${total_uptime}s uptime"
    log INFO "Restart attempts during session: $restart_attempts"
    log INFO "Status file: $STATUS_FILE"
    log INFO "Monitor log: $MONITOR_LOG"
    log INFO "Alert log: $ALERT_LOG"
    log INFO "Metrics log: $METRICS_LOG"
}

# Signal handlers
trap cleanup EXIT
trap 'echo ""; log INFO "Monitoring interrupted"; exit 0' INT TERM

# Help function
show_help() {
    cat << EOF
VPS Health Monitoring Script for Robustty Discord Bot

Usage: $SCRIPT_NAME [OPTIONS] [MODE]

MODES:
    daemon          Run in background daemon mode (default)
    interactive     Run with interactive dashboard
    status          Show current status and exit
    metrics         Show recent metrics and exit

OPTIONS:
    -h, --help              Show this help message
    -c, --config FILE       Use custom configuration file
    --cpu-threshold N       CPU usage alert threshold (default: 80%)
    --memory-threshold N    Memory usage alert threshold (default: 85%)
    --disk-threshold N      Disk usage alert threshold (default: 90%)
    --check-interval N      Health check interval in seconds (default: 30)
    --restart-attempts N    Max restart attempts (default: 3)
    --no-recovery           Disable automatic service recovery

EXAMPLES:
    $SCRIPT_NAME                        # Run in daemon mode
    $SCRIPT_NAME interactive             # Interactive dashboard
    $SCRIPT_NAME status                  # Show current status
    $SCRIPT_NAME --cpu-threshold 90      # Custom CPU threshold

MONITORING FEATURES:
    • Docker container health monitoring
    • Discord API connectivity checks
    • System resource monitoring (CPU, memory, disk)
    • Bot health endpoint validation
    • Platform API accessibility checks
    • Automatic service recovery
    • Alert logging and notifications
    • Performance metrics collection

LOGS AND STATUS:
    • Monitor log: $MONITOR_LOG
    • Alert log: $ALERT_LOG
    • Metrics log: $METRICS_LOG
    • Status file: $STATUS_FILE

EXIT CODES:
    0   Normal operation
    1   Configuration error
    2   Service failure detected
    3   Invalid arguments

RECOVERY FEATURES:
    • Automatic service restart on failure
    • Configurable failure thresholds
    • Restart attempt limits with cooldown
    • Alert notifications for critical issues

FOR ADVANCED USAGE:
    • Configure external alerting (webhook, email, Slack)
    • Integrate with monitoring systems (Prometheus, Grafana)
    • Set up log rotation and archival
    • Configure automated log analysis

EOF
}

# Parse command line arguments
MODE="daemon"
CONFIG_FILE=""
NO_RECOVERY=false

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
        --cpu-threshold)
            CPU_THRESHOLD="$2"
            shift 2
            ;;
        --memory-threshold)
            MEMORY_THRESHOLD="$2"
            shift 2
            ;;
        --disk-threshold)
            DISK_THRESHOLD="$2"
            shift 2
            ;;
        --check-interval)
            HEALTH_CHECK_INTERVAL="$2"
            shift 2
            ;;
        --restart-attempts)
            MAX_RESTART_ATTEMPTS="$2"
            shift 2
            ;;
        --no-recovery)
            NO_RECOVERY=true
            shift
            ;;
        daemon|interactive|status|metrics)
            MODE="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 3
            ;;
    esac
done

# Main execution
main() {
    # Check prerequisites
    if [ ! -f docker-compose.yml ]; then
        log ERROR "docker-compose.yml not found. Please run from project root."
        exit 1
    fi
    
    # Load custom configuration if provided
    if [ -n "$CONFIG_FILE" ] && [ -f "$CONFIG_FILE" ]; then
        log INFO "Loading configuration from: $CONFIG_FILE"
        source "$CONFIG_FILE"
    fi
    
    # Initialize monitoring
    initialize_monitoring
    
    case $MODE in
        "daemon")
            log INFO "Starting in daemon mode"
            daemon_mode
            ;;
        "interactive")
            log INFO "Starting in interactive mode"
            interactive_mode
            ;;
        "status")
            check_container_health
            check_health_endpoint
            check_system_resources
            generate_status_report
            echo "Current Status:"
            cat "$STATUS_FILE" | python -m json.tool 2>/dev/null || cat "$STATUS_FILE"
            ;;
        "metrics")
            if [ -f "$METRICS_LOG" ]; then
                echo "Recent Metrics (last 50 entries):"
                tail -50 "$METRICS_LOG"
            else
                echo "No metrics available yet"
            fi
            ;;
        *)
            log ERROR "Invalid mode: $MODE"
            exit 3
            ;;
    esac
}

# Execute main function
main "$@"