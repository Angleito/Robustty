#!/bin/bash

# Audio Pipeline Diagnostic Runner for Robustty
# This script provides an easy way to run comprehensive audio pipeline diagnostics

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}Robustty Audio Pipeline Diagnostics${NC}"
echo "========================================"

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            echo -e "${GREEN}✓ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠ $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}✗ $message${NC}"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ $message${NC}"
            ;;
    esac
}

# Function to check prerequisites
check_prerequisites() {
    print_status "INFO" "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_status "ERROR" "Python 3 is not installed or not in PATH"
        exit 1
    fi
    
    # Check if we're in the right directory
    if [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
        print_status "ERROR" "Not in Robustty project directory"
        exit 1
    fi
    
    # Check if diagnostic scripts exist
    if [ ! -f "$SCRIPT_DIR/test-audio-playback.py" ]; then
        print_status "ERROR" "Diagnostic script not found: test-audio-playback.py"
        exit 1
    fi
    
    if [ ! -f "$SCRIPT_DIR/fix-audio-issues.py" ]; then
        print_status "ERROR" "Fix script not found: fix-audio-issues.py"
        exit 1
    fi
    
    print_status "SUCCESS" "Prerequisites check passed"
}

# Function to run issue check
run_issue_check() {
    print_status "INFO" "Checking for common audio pipeline issues..."
    
    cd "$PROJECT_ROOT"
    
    if python3 "$SCRIPT_DIR/fix-audio-issues.py" --check; then
        print_status "SUCCESS" "Issue check completed"
    else
        print_status "WARNING" "Some issues were found - see output above"
    fi
}

# Function to run comprehensive audio tests
run_audio_tests() {
    print_status "INFO" "Running comprehensive audio pipeline tests..."
    
    cd "$PROJECT_ROOT"
    
    # Create output directory
    OUTPUT_DIR="$PROJECT_ROOT/audio_diagnostics_output"
    mkdir -p "$OUTPUT_DIR"
    
    # Generate timestamp for output files
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    REPORT_FILE="$OUTPUT_DIR/audio_test_report_$TIMESTAMP.txt"
    
    print_status "INFO" "Test results will be saved to: $REPORT_FILE"
    
    if python3 "$SCRIPT_DIR/test-audio-playback.py" --test-all --output "$REPORT_FILE" --verbose; then
        print_status "SUCCESS" "Audio pipeline tests completed successfully"
        print_status "INFO" "Full report available at: $REPORT_FILE"
        
        # Show summary
        echo ""
        echo "Test Summary:"
        echo "============="
        if grep -q "PASSED" "$REPORT_FILE"; then
            PASSED=$(grep -c "✓" "$REPORT_FILE" || echo "0")
            print_status "SUCCESS" "Tests passed: $PASSED"
        fi
        
        if grep -q "FAILED" "$REPORT_FILE"; then
            FAILED=$(grep -c "✗" "$REPORT_FILE" || echo "0")
            print_status "ERROR" "Tests failed: $FAILED"
        fi
        
        if grep -q "WARNING" "$REPORT_FILE"; then
            WARNINGS=$(grep -c "⚠" "$REPORT_FILE" || echo "0")
            print_status "WARNING" "Warnings: $WARNINGS"
        fi
        
    else
        print_status "ERROR" "Audio pipeline tests failed"
        return 1
    fi
}

# Function to attempt automatic fixes
run_auto_fixes() {
    print_status "INFO" "Attempting to fix identified issues..."
    
    cd "$PROJECT_ROOT"
    
    if python3 "$SCRIPT_DIR/fix-audio-issues.py" --fix-all; then
        print_status "SUCCESS" "Automatic fixes completed"
        print_status "INFO" "Re-run diagnostics to verify fixes"
    else
        print_status "WARNING" "Some fixes may have failed - see output above"
    fi
}

# Function to run quick test with single URL
run_quick_test() {
    local test_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    print_status "INFO" "Running quick test with URL: $test_url"
    
    cd "$PROJECT_ROOT"
    
    if python3 "$SCRIPT_DIR/test-audio-playback.py" "$test_url" --verbose; then
        print_status "SUCCESS" "Quick test passed"
    else
        print_status "ERROR" "Quick test failed"
        return 1
    fi
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --check       Check for issues only (no fixes, no tests)"
    echo "  --quick       Run quick test with single URL"
    echo "  --full        Run comprehensive audio pipeline tests"
    echo "  --fix         Attempt to fix identified issues"
    echo "  --all         Run check, fix, and comprehensive tests"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --check        # Check for issues"
    echo "  $0 --quick        # Quick functionality test"
    echo "  $0 --full         # Full diagnostic test suite"
    echo "  $0 --fix          # Fix common issues"
    echo "  $0 --all          # Complete diagnostic and fix cycle"
    echo ""
}

# Main script logic
main() {
    local option="${1:-}"
    
    if [ -z "$option" ]; then
        print_status "ERROR" "No option specified"
        show_help
        exit 1
    fi
    
    case "$option" in
        --check)
            check_prerequisites
            run_issue_check
            ;;
        --quick)
            check_prerequisites
            run_quick_test
            ;;
        --full)
            check_prerequisites
            run_audio_tests
            ;;
        --fix)
            check_prerequisites
            run_auto_fixes
            ;;
        --all)
            check_prerequisites
            echo ""
            print_status "INFO" "Running complete diagnostic cycle..."
            echo ""
            
            run_issue_check
            echo ""
            
            run_auto_fixes
            echo ""
            
            run_audio_tests
            echo ""
            
            print_status "SUCCESS" "Complete diagnostic cycle finished"
            ;;
        --help)
            show_help
            ;;
        *)
            print_status "ERROR" "Unknown option: $option"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"