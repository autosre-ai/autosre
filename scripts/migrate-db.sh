#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# AutoSRE V2 — Database Migration Script
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Load environment
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default database URL
DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://autosre:autosre_local@localhost:5432/autosre}"

# ─────────────────────────────────────────────────────────────────────────────
# Functions
# ─────────────────────────────────────────────────────────────────────────────

wait_for_db() {
    log_info "Waiting for database to be ready..."
    
    # Extract host and port from DATABASE_URL
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
    
    for i in {1..30}; do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" 2>/dev/null; then
            log_info "Database is ready"
            return 0
        fi
        sleep 1
    done
    
    log_error "Database did not become ready in time"
    return 1
}

run_migrations() {
    log_info "Running database migrations..."
    
    # Check if alembic is available
    if ! command -v alembic &> /dev/null; then
        if [ -f ".venv/bin/alembic" ]; then
            source .venv/bin/activate
        else
            log_error "Alembic not found. Please install dependencies first."
            exit 1
        fi
    fi
    
    # Run migrations
    alembic upgrade head
    
    log_info "Migrations completed successfully"
}

create_initial_data() {
    log_info "Creating initial data..."
    
    python3 << 'EOF'
import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def create_initial_data():
    """Create initial data if needed."""
    # This is a placeholder for initial data creation
    # Add your initialization logic here
    print("Initial data created (placeholder)")

if __name__ == "__main__":
    asyncio.run(create_initial_data())
EOF
}

show_status() {
    log_info "Migration status:"
    alembic current
    echo ""
    log_info "Migration history:"
    alembic history --verbose | head -20
}

# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────

case "${1:-migrate}" in
    migrate|up)
        wait_for_db
        run_migrations
        ;;
    
    down|downgrade)
        wait_for_db
        STEPS="${2:-1}"
        log_info "Downgrading $STEPS revision(s)..."
        alembic downgrade -"$STEPS"
        ;;
    
    status)
        wait_for_db
        show_status
        ;;
    
    revision|create)
        MESSAGE="${2:-Auto migration}"
        log_info "Creating new migration: $MESSAGE"
        alembic revision --autogenerate -m "$MESSAGE"
        ;;
    
    reset)
        log_warn "This will reset the database. All data will be lost!"
        read -p "Are you sure? (y/N) " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            wait_for_db
            log_info "Resetting database..."
            alembic downgrade base
            alembic upgrade head
            create_initial_data
            log_info "Database reset complete"
        fi
        ;;
    
    init)
        wait_for_db
        run_migrations
        create_initial_data
        ;;
    
    help|--help|-h)
        echo "Usage: $0 [COMMAND] [OPTIONS]"
        echo ""
        echo "Commands:"
        echo "  migrate, up      Run pending migrations (default)"
        echo "  down [N]         Downgrade N revisions (default: 1)"
        echo "  status           Show migration status"
        echo "  revision [MSG]   Create new migration"
        echo "  reset            Reset database (WARNING: destroys data)"
        echo "  init             Run migrations + create initial data"
        echo "  help             Show this help"
        ;;
    
    *)
        log_error "Unknown command: $1"
        echo "Run '$0 help' for usage"
        exit 1
        ;;
esac
