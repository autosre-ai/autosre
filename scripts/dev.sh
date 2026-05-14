#!/bin/bash
set -euo pipefail

# AutoSRE V2 - Development Environment Startup
# Starts API server, UI dev server, and compose services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cleanup() {
    log_info "Shutting down services..."
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" down 2>/dev/null || true
    kill $(jobs -p) 2>/dev/null || true
    log_success "Cleanup complete"
}

trap cleanup EXIT INT TERM

# Check dependencies
check_deps() {
    local missing=()
    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    command -v npm >/dev/null 2>&1 || missing+=("npm")
    
    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        exit 1
    fi
}

# Start docker compose services (postgres, redis)
start_compose() {
    log_info "Starting compose services (postgres, redis)..."
    if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        docker compose -f "$PROJECT_ROOT/docker-compose.yml" up -d postgres redis
        log_success "Compose services started"
    else
        log_warn "docker-compose.yml not found, skipping compose services"
    fi
}

# Wait for postgres to be ready
wait_for_postgres() {
    log_info "Waiting for PostgreSQL..."
    local retries=30
    while [ $retries -gt 0 ]; do
        if docker compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T postgres pg_isready -U autosre >/dev/null 2>&1; then
            log_success "PostgreSQL is ready"
            return 0
        fi
        retries=$((retries - 1))
        sleep 1
    done
    log_error "PostgreSQL failed to start"
    return 1
}

# Start API server with hot reload
start_api() {
    log_info "Starting API server with hot reload..."
    cd "$PROJECT_ROOT"
    
    # Activate venv if exists
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
    
    # Use uvicorn with reload
    uvicorn autosre.api.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --reload-dir src \
        --log-level info &
    
    log_success "API server started on http://localhost:8000"
}

# Start UI dev server
start_ui() {
    log_info "Starting UI dev server..."
    if [ -d "$PROJECT_ROOT/ui" ]; then
        cd "$PROJECT_ROOT/ui"
        npm run dev &
        log_success "UI dev server started on http://localhost:5173"
    else
        log_warn "UI directory not found, skipping UI server"
    fi
}

main() {
    log_info "🚀 Starting AutoSRE V2 development environment..."
    echo ""
    
    check_deps
    start_compose
    wait_for_postgres || exit 1
    
    # Run migrations before starting API
    if [ -f "$SCRIPT_DIR/migrate.sh" ]; then
        log_info "Running database migrations..."
        bash "$SCRIPT_DIR/migrate.sh" || log_warn "Migrations failed or not configured"
    fi
    
    start_api
    start_ui
    
    echo ""
    log_success "Development environment ready!"
    echo ""
    echo "  API:  http://localhost:8000"
    echo "  Docs: http://localhost:8000/docs"
    echo "  UI:   http://localhost:5173"
    echo ""
    log_info "Press Ctrl+C to stop all services"
    
    # Wait for background jobs
    wait
}

main "$@"
