#!/bin/bash
set -euo pipefail

# AutoSRE V2 - Test Runner
# Runs unit tests, integration tests, and generates coverage report

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Default options
RUN_UNIT=true
RUN_INTEGRATION=false
RUN_COVERAGE=false
VERBOSE=false
TEST_PATTERN=""

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [TEST_PATTERN]

Run AutoSRE V2 test suite.

Options:
    -u, --unit          Run unit tests only (default)
    -i, --integration   Run integration tests (requires services)
    -a, --all           Run all tests
    -c, --coverage      Generate coverage report
    -v, --verbose       Verbose output
    -h, --help          Show this help message

Examples:
    $(basename "$0")                    # Run unit tests
    $(basename "$0") -a -c              # Run all tests with coverage
    $(basename "$0") test_runbooks      # Run tests matching pattern
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--unit)
            RUN_UNIT=true
            RUN_INTEGRATION=false
            shift
            ;;
        -i|--integration)
            RUN_UNIT=false
            RUN_INTEGRATION=true
            shift
            ;;
        -a|--all)
            RUN_UNIT=true
            RUN_INTEGRATION=true
            shift
            ;;
        -c|--coverage)
            RUN_COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            TEST_PATTERN="$1"
            shift
            ;;
    esac
done

cd "$PROJECT_ROOT"

# Activate venv if exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Check pytest is installed
if ! command -v pytest >/dev/null 2>&1; then
    log_error "pytest not found. Install with: pip install pytest pytest-cov pytest-asyncio"
    exit 1
fi

# Build pytest command
PYTEST_ARGS=()

if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS+=("-v" "--tb=long")
else
    PYTEST_ARGS+=("--tb=short")
fi

if [ "$RUN_COVERAGE" = true ]; then
    PYTEST_ARGS+=(
        "--cov=src/autosre"
        "--cov-report=term-missing"
        "--cov-report=html:coverage_html"
        "--cov-fail-under=70"
    )
fi

# Add test paths
TEST_PATHS=()
if [ "$RUN_UNIT" = true ]; then
    TEST_PATHS+=("tests/unit")
fi
if [ "$RUN_INTEGRATION" = true ]; then
    TEST_PATHS+=("tests/integration")
fi

# Add pattern filter if specified
if [ -n "$TEST_PATTERN" ]; then
    PYTEST_ARGS+=("-k" "$TEST_PATTERN")
fi

# Start integration services if needed
if [ "$RUN_INTEGRATION" = true ]; then
    log_info "Starting test services..."
    if [ -f "docker-compose.test.yml" ]; then
        docker compose -f docker-compose.test.yml up -d
        sleep 3
    elif [ -f "docker-compose.yml" ]; then
        docker compose -f docker-compose.yml up -d postgres redis
        sleep 3
    fi
fi

# Run tests
log_info "Running tests..."
echo ""

EXIT_CODE=0
pytest "${PYTEST_ARGS[@]}" "${TEST_PATHS[@]}" || EXIT_CODE=$?

echo ""

# Print coverage location if generated
if [ "$RUN_COVERAGE" = true ] && [ -d "coverage_html" ]; then
    log_info "Coverage report: file://$PROJECT_ROOT/coverage_html/index.html"
fi

# Cleanup integration services
if [ "$RUN_INTEGRATION" = true ]; then
    if [ -f "docker-compose.test.yml" ]; then
        docker compose -f docker-compose.test.yml down 2>/dev/null || true
    fi
fi

if [ $EXIT_CODE -eq 0 ]; then
    log_success "All tests passed!"
else
    log_error "Some tests failed"
fi

exit $EXIT_CODE
