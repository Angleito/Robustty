#!/bin/bash

# Discord 4006 Voice Connection Diagnostics Script
# This script provides comprehensive diagnostics for Discord 4006 "Session Timed Out" errors

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIAGNOSTICS_DIR="$PROJECT_ROOT/scripts/diagnostics"
RESULTS_DIR="$PROJECT_ROOT/diagnostics-results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$RESULTS_DIR/4006-diagnostics-$TIMESTAMP.log"

# Default settings
RUN_LOCAL=false
STATUS_CHECK_ONLY=false
VERBOSE=false

# Help function
show_help() {
    cat << EOF
${BOLD}Discord 4006 Voice Connection Diagnostics${NC}

${BOLD}USAGE:${NC}
    $0 [OPTIONS]

${BOLD}OPTIONS:${NC}
    --status        Only check Discord status and basic connectivity
    --local         Run diagnostics against local bot instance
    --verbose, -v   Enable verbose output
    --help, -h      Show this help message

${BOLD}DESCRIPTION:${NC}
    This script runs comprehensive diagnostics for Discord 4006 "Session Timed Out" 
    errors commonly encountered with voice connections. It checks:
    
    • Discord API status and voice server health
    • Network connectivity and latency to Discord servers
    • Regional voice server accessibility
    • Bot permissions and voice channel access
    • Local environment and dependencies
    • Docker networking configuration (if applicable)

${BOLD}EXAMPLES:${NC}
    $0                  # Run full diagnostics
    $0 --status         # Quick status check only
    $0 --local          # Test local bot instance
    $0 --verbose        # Enable detailed output

${BOLD}OUTPUT:${NC}
    Results are saved to: $RESULTS_DIR/
    Live logs: $REPORT_FILE

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --status)
            STATUS_CHECK_ONLY=true
            shift
            ;;
        --local)
            RUN_LOCAL=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$REPORT_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$REPORT_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$REPORT_FILE"
}

log_debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1" | tee -a "$REPORT_FILE"
    fi
}

log_section() {
    echo -e "\n${BOLD}=== $1 ===${NC}" | tee -a "$REPORT_FILE"
}

# Initialize results directory
initialize_diagnostics() {
    mkdir -p "$RESULTS_DIR"
    mkdir -p "$DIAGNOSTICS_DIR"
    
    # Create report file
    cat > "$REPORT_FILE" << EOF
Discord 4006 Voice Connection Diagnostics Report
Generated: $(date)
Command: $0 $*
==================================================

EOF
    
    log_info "Diagnostics initialized"
    log_info "Report file: $REPORT_FILE"
}

# Check if required tools are available
check_dependencies() {
    log_section "Dependency Check"
    
    local missing_deps=()
    
    # Check for required commands
    for cmd in curl jq ping nslookup python3; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
            log_error "Missing dependency: $cmd"
        else
            log_debug "$cmd: Available"
        fi
    done
    
    # Check for Python modules
    if command -v python3 &> /dev/null; then
        for module in requests aiohttp discord; do
            if ! python3 -c "import $module" 2>/dev/null; then
                missing_deps+=("python3-$module")
                log_warn "Missing Python module: $module"
            else
                log_debug "Python module $module: Available"
            fi
        done
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Install missing dependencies and try again"
        return 1
    else
        log_info "All dependencies satisfied"
        return 0
    fi
}

# Check Discord API status
check_discord_status() {
    log_section "Discord API Status Check"
    
    local status_url="https://discordstatus.com/api/v2/status.json"
    local incidents_url="https://discordstatus.com/api/v2/incidents.json"
    
    # Check overall status
    if curl -s --max-time 10 "$status_url" | jq -r '.status.description' > /tmp/discord_status 2>/dev/null; then
        local status=$(cat /tmp/discord_status)
        log_info "Discord Status: $status"
        
        # Check for incidents
        if curl -s --max-time 10 "$incidents_url" | jq -r '.incidents[0].status' > /tmp/discord_incidents 2>/dev/null; then
            local incident_status=$(cat /tmp/discord_incidents)
            if [[ "$incident_status" != "null" && "$incident_status" != "" ]]; then
                log_warn "Active incident detected: $incident_status"
            else
                log_info "No active incidents"
            fi
        fi
    else
        log_error "Failed to fetch Discord status"
        return 1
    fi
    
    # Clean up temp files
    rm -f /tmp/discord_status /tmp/discord_incidents
}

# Test network connectivity to Discord servers
test_discord_connectivity() {
    log_section "Discord Server Connectivity"
    
    # Discord voice server regions and endpoints
    declare -A discord_endpoints=(
        ["us-west"]="us-west1.discord.gg"
        ["us-east"]="us-east1.discord.gg"
        ["us-central"]="us-central1.discord.gg"
        ["europe"]="eu-west1.discord.gg"
        ["singapore"]="singapore1.discord.gg"
        ["sydney"]="sydney1.discord.gg"
        ["japan"]="japan1.discord.gg"
        ["brazil"]="brazil1.discord.gg"
        ["india"]="india1.discord.gg"
        ["russia"]="russia1.discord.gg"
    )
    
    local failed_regions=()
    local successful_regions=()
    
    for region in "${!discord_endpoints[@]}"; do
        local endpoint="${discord_endpoints[$region]}"
        log_debug "Testing connectivity to $region ($endpoint)"
        
        # Test ping
        if ping -c 3 -W 5000 "$endpoint" > /tmp/ping_result 2>&1; then
            local avg_time=$(grep "round-trip" /tmp/ping_result | cut -d'/' -f5 | cut -d'.' -f1)
            log_info "$region: Reachable (${avg_time}ms average)"
            successful_regions+=("$region")
        else
            log_error "$region: Unreachable"
            failed_regions+=("$region")
        fi
        
        # Test DNS resolution
        if nslookup "$endpoint" > /tmp/dns_result 2>&1; then
            local ip=$(grep "Address:" /tmp/dns_result | tail -1 | cut -d' ' -f2)
            log_debug "$region DNS: $endpoint -> $ip"
        else
            log_warn "$region: DNS resolution failed"
        fi
    done
    
    # Summary
    log_info "Successful regions: ${#successful_regions[@]}/${#discord_endpoints[@]}"
    log_info "Failed regions: ${#failed_regions[@]}/${#discord_endpoints[@]}"
    
    if [[ ${#failed_regions[@]} -gt $((${#discord_endpoints[@]} / 2)) ]]; then
        log_error "More than half of Discord regions are unreachable - network issue likely"
        return 1
    fi
    
    # Clean up
    rm -f /tmp/ping_result /tmp/dns_result
}

# Test voice server specific connectivity
test_voice_servers() {
    log_section "Voice Server Connectivity"
    
    # Create Python script for voice server testing
    cat > "$DIAGNOSTICS_DIR/voice_server_test.py" << 'EOF'
#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import sys
from typing import Dict, List, Optional

async def test_voice_discovery(region_id: str = "us-west") -> Dict:
    """Test voice server discovery for a specific region"""
    discovery_url = f"https://discord.com/api/v9/voice/regions"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(discovery_url, timeout=10) as response:
                if response.status == 200:
                    regions = await response.json()
                    target_region = None
                    
                    for region in regions:
                        if region.get("id") == region_id:
                            target_region = region
                            break
                    
                    if target_region:
                        return {
                            "success": True,
                            "region": target_region,
                            "endpoint": target_region.get("endpoint"),
                            "optimal": target_region.get("optimal", False),
                            "deprecated": target_region.get("deprecated", False)
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Region {region_id} not found",
                            "available_regions": [r.get("id") for r in regions]
                        }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}",
                        "status": response.status
                    }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "exception_type": type(e).__name__
        }

async def test_voice_connection(endpoint: str, port: int = 443) -> Dict:
    """Test connection to voice server endpoint"""
    try:
        # Test WebSocket connection to voice server
        connector = aiohttp.TCPConnector()
        async with aiohttp.ClientSession(connector=connector) as session:
            # Test HTTP connectivity first
            test_url = f"https://{endpoint}/"
            async with session.get(test_url, timeout=5) as response:
                return {
                    "success": True,
                    "endpoint": endpoint,
                    "status": response.status,
                    "reachable": True
                }
    except Exception as e:
        return {
            "success": False,
            "endpoint": endpoint,
            "error": str(e),
            "exception_type": type(e).__name__,
            "reachable": False
        }

async def main():
    """Main diagnostic function"""
    regions_to_test = ["us-west", "us-east", "us-central", "europe", "singapore"]
    results = []
    
    for region in regions_to_test:
        print(f"Testing voice discovery for {region}...", file=sys.stderr)
        discovery_result = await test_voice_discovery(region)
        
        if discovery_result["success"] and discovery_result.get("endpoint"):
            endpoint = discovery_result["endpoint"]
            print(f"Testing connection to {endpoint}...", file=sys.stderr)
            connection_result = await test_voice_connection(endpoint)
            discovery_result["connection_test"] = connection_result
        
        results.append(discovery_result)
    
    # Output results as JSON
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
EOF
    
    chmod +x "$DIAGNOSTICS_DIR/voice_server_test.py"
    
    # Run voice server tests
    if python3 "$DIAGNOSTICS_DIR/voice_server_test.py" > "$RESULTS_DIR/voice_server_results.json" 2>/dev/null; then
        log_info "Voice server connectivity test completed"
        
        # Parse and display results
        if command -v jq &> /dev/null; then
            local successful=$(jq '[.[] | select(.success == true)] | length' "$RESULTS_DIR/voice_server_results.json")
            local total=$(jq 'length' "$RESULTS_DIR/voice_server_results.json")
            log_info "Voice server tests: $successful/$total successful"
            
            # Show failed regions
            local failed_regions=$(jq -r '.[] | select(.success == false) | .region // "unknown"' "$RESULTS_DIR/voice_server_results.json" 2>/dev/null || echo "")
            if [[ -n "$failed_regions" ]]; then
                log_warn "Failed voice regions: $failed_regions"
            fi
        fi
    else
        log_error "Voice server connectivity test failed"
    fi
}

# Check bot permissions and configuration
check_bot_configuration() {
    log_section "Bot Configuration Check"
    
    # Check if Discord token is set
    if [[ -z "$DISCORD_TOKEN" ]]; then
        log_warn "DISCORD_TOKEN environment variable not set"
    else
        log_info "Discord token configured"
    fi
    
    # Check bot intents configuration
    if [[ -f "$PROJECT_ROOT/src/bot/bot.py" ]]; then
        if grep -q "intents.voice_states = True" "$PROJECT_ROOT/src/bot/bot.py"; then
            log_info "Voice states intent enabled"
        else
            log_warn "Voice states intent may not be enabled"
        fi
        
        if grep -q "intents.message_content = True" "$PROJECT_ROOT/src/bot/bot.py"; then
            log_info "Message content intent enabled"
        else
            log_warn "Message content intent may not be enabled"
        fi
    fi
    
    # Check config file
    if [[ -f "$PROJECT_ROOT/config/config.yaml" ]]; then
        log_info "Bot configuration file found"
        
        # Check auto-disconnect settings
        if grep -q "auto_disconnect:" "$PROJECT_ROOT/config/config.yaml"; then
            local auto_disconnect=$(grep "auto_disconnect:" "$PROJECT_ROOT/config/config.yaml" | cut -d':' -f2 | xargs)
            log_info "Auto disconnect: $auto_disconnect"
            
            if [[ "$auto_disconnect" == "true" ]]; then
                local timeout=$(grep "auto_disconnect_timeout:" "$PROJECT_ROOT/config/config.yaml" | cut -d':' -f2 | xargs)
                log_info "Auto disconnect timeout: ${timeout}s"
            fi
        fi
    else
        log_warn "Bot configuration file not found"
    fi
}

# Test local bot instance if requested
test_local_bot() {
    log_section "Local Bot Instance Test"
    
    if [[ "$RUN_LOCAL" != "true" ]]; then
        log_info "Skipping local bot test (use --local to enable)"
        return 0
    fi
    
    # Check if bot is running locally
    if pgrep -f "python.*main.py\|python.*src.main" > /dev/null; then
        log_info "Local bot process detected"
    else
        log_warn "No local bot process found"
    fi
    
    # Check Docker containers
    if command -v docker &> /dev/null; then
        if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q robustty; then
            log_info "Docker bot container running"
            
            # Check container logs for 4006 errors
            if docker logs robustty 2>&1 | grep -q "4006\|Session.*timed.*out"; then
                log_warn "4006 errors found in container logs"
                log_info "Recent 4006 errors:"
                docker logs --tail 10 robustty 2>&1 | grep -i "4006\|session.*timed.*out" | tail -5 | while read line; do
                    log_warn "  $line"
                done
            else
                log_info "No 4006 errors in recent container logs"
            fi
        else
            log_info "No Docker bot container running"
        fi
    fi
    
    # Test Redis connectivity if configured
    if command -v redis-cli &> /dev/null; then
        if redis-cli ping > /dev/null 2>&1; then
            log_info "Redis connection: OK"
        else
            log_warn "Redis connection failed"
        fi
    fi
}

# Generate recommendations based on findings
generate_recommendations() {
    log_section "Recommendations"
    
    cat >> "$REPORT_FILE" << 'EOF'

RECOMMENDATIONS FOR FIXING 4006 ERRORS:

1. IMMEDIATE ACTIONS:
   - Restart bot to clear any stuck voice connections
   - Check Discord status at https://discordstatus.com
   - Verify bot has proper voice permissions in target channels

2. CONFIGURATION CHECKS:
   - Ensure DISCORD_TOKEN is valid and bot has voice permissions
   - Verify voice_states intent is enabled in bot configuration
   - Check auto_disconnect_timeout setting (recommend 300 seconds)

3. NETWORK TROUBLESHOOTING:
   - Test connection to multiple Discord voice regions
   - Check for firewall blocking Discord voice ports (UDP 50000-65535)
   - Verify DNS resolution for Discord endpoints

4. DOCKER/DEPLOYMENT SPECIFIC:
   - Use host networking mode if running in containers
   - Ensure proper port forwarding for voice connections
   - Check container resource limits (CPU/memory)

5. ADVANCED DIAGNOSTICS:
   - Monitor voice connection patterns to identify trigger conditions
   - Implement exponential backoff for voice reconnections
   - Consider regional failover logic for voice servers

6. MONITORING:
   - Set up alerting for 4006 errors
   - Log voice connection state changes
   - Track voice server latency metrics

EOF

    log_info "Recommendations generated in report file"
}

# Main diagnostic workflow
run_diagnostics() {
    local start_time=$(date +%s)
    
    log_section "Discord 4006 Diagnostics Starting"
    log_info "Timestamp: $(date)"
    log_info "Mode: $([ "$STATUS_CHECK_ONLY" == "true" ] && echo "Status Check Only" || echo "Full Diagnostics")"
    log_info "Local test: $([ "$RUN_LOCAL" == "true" ] && echo "Enabled" || echo "Disabled")"
    
    # Step 1: Check dependencies
    if ! check_dependencies; then
        log_error "Dependency check failed. Please install missing dependencies."
        exit 1
    fi
    
    # Step 2: Check Discord status
    check_discord_status || log_warn "Discord status check had issues"
    
    # If status check only, stop here
    if [[ "$STATUS_CHECK_ONLY" == "true" ]]; then
        log_info "Status check completed (use without --status for full diagnostics)"
        return 0
    fi
    
    # Step 3: Test network connectivity
    test_discord_connectivity || log_warn "Some connectivity tests failed"
    
    # Step 4: Test voice servers
    test_voice_servers || log_warn "Voice server tests had issues"
    
    # Step 5: Check bot configuration
    check_bot_configuration
    
    # Step 6: Test local bot if requested
    test_local_bot
    
    # Step 7: Generate recommendations
    generate_recommendations
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_section "Diagnostics Complete"
    log_info "Total time: ${duration}s"
    log_info "Full report: $REPORT_FILE"
    log_info "Results directory: $RESULTS_DIR"
}

# Script header
echo -e "${BOLD}Discord 4006 Voice Connection Diagnostics${NC}"
echo -e "==========================================="

# Initialize and run diagnostics
initialize_diagnostics
run_diagnostics

# Final summary
echo -e "\n${GREEN}Diagnostics completed successfully!${NC}"
echo -e "Check the full report at: ${BLUE}$REPORT_FILE${NC}"
echo -e "For help interpreting results, see the recommendations section."