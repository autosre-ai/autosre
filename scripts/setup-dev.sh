#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# AutoSRE V2 — Development Environment Setup
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

# ─────────────────────────────────────────────────────────────────────────────
# Checks
# ─────────────────────────────────────────────────────────────────────────────

check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed."
        echo "Install Python: https://www.python.org/downloads/"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log_info "Python version: $PYTHON_VERSION"
    
    if [[ $(echo "$PYTHON_VERSION < 3.10" | bc -l) == 1 ]]; then
        log_error "Python 3.10+ is required. Found: $PYTHON_VERSION"
        exit 1
    fi
}

check_node() {
    if ! command -v node &> /dev/null; then
        log_error "Node.js is required but not installed."
        echo "Install Node.js: https://nodejs.org/"
        exit 1
    fi
    
    NODE_VERSION=$(node -v | tr -d 'v')
    log_info "Node.js version: $NODE_VERSION"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_warn "Docker is not installed. Some features will be unavailable."
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        log_warn "Docker daemon is not running."
        return 1
    fi
    
    log_info "Docker is available"
    return 0
}

# ─────────────────────────────────────────────────────────────────────────────
# Setup Functions
# ─────────────────────────────────────────────────────────────────────────────

setup_python_env() {
    log_info "Setting up Python environment..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        log_info "Created virtual environment"
    fi
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip wheel setuptools
    
    # Install dependencies
    if [ -f "pyproject.toml" ]; then
        pip install -e ".[dev]"
    elif [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    fi
    
    log_info "Python dependencies installed"
}

setup_node_env() {
    log_info "Setting up Node.js environment..."
    
    if [ -d "ui" ]; then
        cd ui
        
        # Install dependencies
        if [ -f "package-lock.json" ]; then
            npm ci
        elif [ -f "pnpm-lock.yaml" ]; then
            npm install -g pnpm
            pnpm install --frozen-lockfile
        else
            npm install
        fi
        
        cd ..
    fi
    
    log_info "Node.js dependencies installed"
}

setup_env_file() {
    log_info "Setting up environment file..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            
            # Generate random secret key
            if command -v openssl &> /dev/null; then
                SECRET_KEY=$(openssl rand -hex 32)
            else
                SECRET_KEY=$(head -c 64 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 64)
            fi
            
            # Update secret key in .env
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s/AUTOSRE_SECRET_KEY=.*/AUTOSRE_SECRET_KEY=$SECRET_KEY/" .env
            else
                sed -i "s/AUTOSRE_SECRET_KEY=.*/AUTOSRE_SECRET_KEY=$SECRET_KEY/" .env
            fi
            
            log_info "Created .env file with random secret key"
        else
            log_warn ".env.example not found, skipping .env creation"
        fi
    else
        log_info ".env file already exists"
    fi
}

setup_git_hooks() {
    log_info "Setting up Git hooks..."
    
    if [ -d ".git" ]; then
        # Install pre-commit if available
        if command -v pre-commit &> /dev/null; then
            pre-commit install
            log_info "Pre-commit hooks installed"
        else
            log_warn "pre-commit not found, installing..."
            pip install pre-commit
            pre-commit install
        fi
    fi
}

setup_database() {
    log_info "Setting up database..."
    
    # Start postgres via Docker if available
    if check_docker; then
        docker compose up -d postgres redis 2>/dev/null || true
        log_info "Started PostgreSQL and Redis containers"
        
        # Wait for postgres to be ready
        log_info "Waiting for PostgreSQL to be ready..."
        for i in {1..30}; do
            if docker compose exec -T postgres pg_isready -U autosre 2>/dev/null; then
                break
            fi
            sleep 1
        done
    else
        log_warn "Docker not available. Please start PostgreSQL manually."
    fi
}

create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p data
    mkdir -p tmp
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

main() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           AutoSRE V2 — Development Setup                      ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    check_python
    check_node
    check_docker || true
    
    echo ""
    
    create_directories
    setup_env_file
    setup_python_env
    setup_node_env
    setup_git_hooks
    setup_database
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Development environment is ready!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Next steps:"
    echo ""
    echo "  1. Activate virtual environment:"
    echo "     source .venv/bin/activate"
    echo ""
    echo "  2. Edit .env file with your configuration:"
    echo "     vi .env"
    echo ""
    echo "  3. Start development servers:"
    echo "     make dev"
    echo ""
    echo "  Or run components separately:"
    echo "     make dev-api    # API only"
    echo "     make dev-ui     # UI only"
    echo ""
}

main "$@"
