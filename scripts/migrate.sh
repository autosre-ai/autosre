#!/bin/bash
set -euo pipefail

# AutoSRE V2 - Database Migration Runner
# Runs Alembic migrations for database schema management

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
ACTION="upgrade"
REVISION="head"
MESSAGE=""
AUTOGENERATE=false
SQL_ONLY=false

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [ACTION] [REVISION]

Run AutoSRE V2 database migrations.

Actions:
    upgrade [rev]       Upgrade to revision (default: head)
    downgrade [rev]     Downgrade to revision (default: -1)
    current             Show current revision
    history             Show migration history
    heads               Show available heads
    create [message]    Create new migration
    init                Initialize database with init-db.sql

Options:
    --autogenerate      Auto-generate migration from models
    --sql               Show SQL only, don't execute
    -m, --message MSG   Migration message (for create)
    -h, --help          Show this help message

Environment:
    DATABASE_URL        PostgreSQL connection string
                        Default: postgresql://autosre:autosre@localhost:5432/autosre

Examples:
    $(basename "$0")                        # Upgrade to latest
    $(basename "$0") downgrade -1           # Rollback one migration
    $(basename "$0") create -m "Add users"  # Create migration
    $(basename "$0") --autogenerate -m "Add field"  # Auto-generate
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        upgrade|downgrade|current|history|heads|create|init)
            ACTION="$1"
            shift
            ;;
        --autogenerate)
            AUTOGENERATE=true
            shift
            ;;
        --sql)
            SQL_ONLY=true
            shift
            ;;
        -m|--message)
            MESSAGE="$2"
            shift 2
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
            REVISION="$1"
            shift
            ;;
    esac
done

cd "$PROJECT_ROOT"

# Activate venv if exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Set default database URL if not provided
export DATABASE_URL="${DATABASE_URL:-postgresql://autosre:autosre@localhost:5432/autosre}"

# Check alembic is installed
check_alembic() {
    if ! command -v alembic >/dev/null 2>&1; then
        log_error "alembic not found. Install with: pip install alembic"
        exit 1
    fi
}

# Initialize database with SQL script
init_database() {
    log_info "Initializing database with init-db.sql..."
    
    if [ ! -f "$SCRIPT_DIR/init-db.sql" ]; then
        log_error "init-db.sql not found"
        exit 1
    fi
    
    # Extract connection details from DATABASE_URL
    # Format: postgresql://user:pass@host:port/dbname
    if command -v psql >/dev/null 2>&1; then
        psql "$DATABASE_URL" -f "$SCRIPT_DIR/init-db.sql"
        log_success "Database initialized"
    else
        # Try via docker
        log_info "psql not found, trying via docker..."
        docker compose exec -T postgres psql -U autosre -d autosre < "$SCRIPT_DIR/init-db.sql"
        log_success "Database initialized"
    fi
}

# Run migrations
run_migration() {
    check_alembic
    
    local ALEMBIC_ARGS=()
    
    if [ "$SQL_ONLY" = true ]; then
        ALEMBIC_ARGS+=("--sql")
    fi
    
    case "$ACTION" in
        upgrade)
            log_info "Upgrading database to: $REVISION"
            alembic upgrade "${ALEMBIC_ARGS[@]}" "$REVISION"
            log_success "Migration complete"
            ;;
        downgrade)
            log_warn "Downgrading database to: $REVISION"
            read -p "Are you sure? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                alembic downgrade "${ALEMBIC_ARGS[@]}" "$REVISION"
                log_success "Downgrade complete"
            else
                log_info "Downgrade cancelled"
            fi
            ;;
        current)
            log_info "Current revision:"
            alembic current
            ;;
        history)
            log_info "Migration history:"
            alembic history --verbose
            ;;
        heads)
            log_info "Available heads:"
            alembic heads
            ;;
        create)
            if [ -z "$MESSAGE" ]; then
                log_error "Migration message required. Use -m or --message"
                exit 1
            fi
            
            local CREATE_ARGS=("-m" "$MESSAGE")
            if [ "$AUTOGENERATE" = true ]; then
                CREATE_ARGS+=("--autogenerate")
            fi
            
            log_info "Creating migration: $MESSAGE"
            alembic revision "${CREATE_ARGS[@]}"
            log_success "Migration created"
            ;;
        init)
            init_database
            ;;
        *)
            log_error "Unknown action: $ACTION"
            usage
            exit 1
            ;;
    esac
}

# Check database connectivity
check_database() {
    log_info "Checking database connection..."
    
    if python3 -c "
import sys
try:
    from sqlalchemy import create_engine
    engine = create_engine('$DATABASE_URL')
    with engine.connect() as conn:
        conn.execute('SELECT 1')
    sys.exit(0)
except Exception as e:
    print(f'Connection failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
        log_success "Database connection OK"
    else
        log_error "Cannot connect to database"
        log_info "DATABASE_URL: $DATABASE_URL"
        exit 1
    fi
}

main() {
    log_info "🗄️  AutoSRE V2 Migration Runner"
    echo ""
    
    # Skip connection check for certain actions
    if [[ "$ACTION" != "create" && "$ACTION" != "history" && "$ACTION" != "heads" ]]; then
        check_database
    fi
    
    run_migration
}

main "$@"
