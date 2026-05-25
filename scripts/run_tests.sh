#!/usr/bin/env bash
#
# AutoSRE Test Runner Script
# Runs pytest with coverage and provides a summary
#
# Usage:
#   ./scripts/run_tests.sh              # Run all tests
#   ./scripts/run_tests.sh tests/test_models.py   # Run specific test file
#   ./scripts/run_tests.sh -k "test_name"         # Run tests matching pattern
#   ./scripts/run_tests.sh --fast                 # Run without coverage (faster)
#   ./scripts/run_tests.sh --verbose              # Run with verbose output
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default options
COVERAGE=true
VERBOSE=""
PYTEST_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fast)
            COVERAGE=false
            shift
            ;;
        --verbose|-v)
            VERBOSE="-v"
            shift
            ;;
        --help|-h)
            echo "AutoSRE Test Runner"
            echo ""
            echo "Usage: $0 [OPTIONS] [TEST_PATH] [PYTEST_ARGS...]"
            echo ""
            echo "Options:"
            echo "  --fast       Run without coverage (faster)"
            echo "  --verbose    Run with verbose output"
            echo "  -h, --help   Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                              # Run all tests with coverage"
            echo "  $0 tests/test_models.py        # Run specific test file"
            echo "  $0 -k 'test_prometheus'        # Run tests matching pattern"
            echo "  $0 --fast tests/               # Run fast without coverage"
            echo "  $0 --verbose -x                # Verbose + stop on first failure"
            exit 0
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

# Change to project root
cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}       AutoSRE Test Runner${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if venv exists
if [[ ! -d ".venv" ]]; then
    echo -e "${RED}Error: Virtual environment not found at .venv${NC}"
    echo "Please create it first with: python -m venv .venv && pip install -e '.[dev]'"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Check pytest is available
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found. Install dev dependencies:${NC}"
    echo "pip install -e '.[dev]'"
    exit 1
fi

# Build pytest command
CMD="pytest"

if [[ "$COVERAGE" == true ]]; then
    CMD="$CMD --cov=src/autosre --cov-report=term-missing --cov-report=html:htmlcov"
fi

if [[ -n "$VERBOSE" ]]; then
    CMD="$CMD $VERBOSE"
fi

# Add any additional arguments
if [[ ${#PYTEST_ARGS[@]} -gt 0 ]]; then
    CMD="$CMD ${PYTEST_ARGS[*]}"
fi

echo -e "${YELLOW}Running: ${NC}$CMD"
echo ""

# Run tests
START_TIME=$(date +%s)

if $CMD; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}       All tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "Duration: ${DURATION}s"
    
    if [[ "$COVERAGE" == true ]]; then
        echo ""
        echo -e "${BLUE}Coverage report generated: htmlcov/index.html${NC}"
        echo "Open with: open htmlcov/index.html"
    fi
    
    EXIT_CODE=0
else
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}       Some tests failed!${NC}"
    echo -e "${RED}========================================${NC}"
    echo -e "Duration: ${DURATION}s"
    EXIT_CODE=1
fi

# Deactivate venv (optional, not strictly necessary)
deactivate 2>/dev/null || true

exit $EXIT_CODE
