#!/bin/bash

# Script to run integration tests with proper setup

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Running Robustty Integration Tests${NC}"
echo "=================================="

# Check for required environment variables
if [ -z "$APIFY_API_KEY" ]; then
    echo -e "${YELLOW}Warning: APIFY_API_KEY not set${NC}"
    echo "Integration tests will be skipped."
    echo "To run Rumble tests, set: export APIFY_API_KEY=your_key_here"
    echo ""
fi

# Install test dependencies if needed
echo "Checking test dependencies..."
pip install -q pytest pytest-timeout pytest-html pytest-cov pytest-mock

# Create test results directory
mkdir -p test-results

# Run integration tests
echo -e "\n${GREEN}Running integration tests...${NC}"
pytest tests/integration -v \
    --tb=short \
    --junit-xml=test-results/integration.xml \
    --html=test-results/integration-report.html \
    --self-contained-html \
    --cov=src \
    --cov-report=html:test-results/coverage \
    --cov-report=term

# Check results
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}Integration tests passed!${NC}"
else
    echo -e "\n${RED}Some integration tests failed.${NC}"
    echo "Check test-results/integration-report.html for details."
fi

echo -e "\nTest artifacts:"
echo "  - Report: test-results/integration-report.html"
echo "  - Coverage: test-results/coverage/index.html"
echo "  - JUnit XML: test-results/integration.xml"