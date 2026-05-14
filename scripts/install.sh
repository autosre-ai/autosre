#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# AutoSRE V2 — One-Liner Installer
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/your-org/autosre-v2/main/scripts/install.sh | bash
#
# Options:
#   --docker     Install via Docker (default)
#   --k8s        Install via Kubernetes
#   --helm       Install via Helm
#   --dev        Set up development environment
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
INSTALL_MODE="docker"
AUTOSRE_VERSION="${AUTOSRE_VERSION:-latest}"
AUTOSRE_DIR="${AUTOSRE_DIR:-$HOME/autosre}"

# ─────────────────────────────────────────────────────────────────────────────
# Functions
# ─────────────────────────────────────────────────────────────────────────────

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is required but not installed."
        return 1
    fi
    return 0
}

check_docker() {
    check_command docker || return 1
    check_command "docker compose" || check_command docker-compose || return 1
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        return 1
    fi
    return 0
}

check_kubernetes() {
    check_command kubectl || return 1
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        return 1
    fi
    return 0
}

check_helm() {
    check_command helm || return 1
    check_kubernetes || return 1
    return 0
}

download_files() {
    log_info "Downloading AutoSRE V2..."
    
    mkdir -p "$AUTOSRE_DIR"
    cd "$AUTOSRE_DIR"
    
    # Clone or download release
    if command -v git &> /dev/null; then
        git clone --depth 1 https://github.com/your-org/autosre-v2.git . 2>/dev/null || \
        git pull origin main
    else
        curl -fsSL "https://github.com/your-org/autosre-v2/archive/refs/heads/main.tar.gz" | \
        tar -xz --strip-components=1
    fi
}

create_env_file() {
    if [ ! -f .env ]; then
        log_info "Creating .env file..."
        cp .env.example .env
        
        # Generate random secret key
        SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 64)
        sed -i.bak "s/AUTOSRE_SECRET_KEY=.*/AUTOSRE_SECRET_KEY=$SECRET_KEY/" .env 2>/dev/null || \
        sed -i '' "s/AUTOSRE_SECRET_KEY=.*/AUTOSRE_SECRET_KEY=$SECRET_KEY/" .env
        
        log_warn "Please edit .env file with your configuration"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Installation Methods
# ─────────────────────────────────────────────────────────────────────────────

install_docker() {
    log_info "Installing AutoSRE V2 with Docker..."
    
    check_docker || exit 1
    download_files
    create_env_file
    
    log_info "Starting services..."
    docker compose up -d
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  AutoSRE V2 is now running!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  UI:  http://localhost:3000"
    echo "  API: http://localhost:8000"
    echo ""
    echo "  Configuration: $AUTOSRE_DIR/.env"
    echo ""
    echo "  Commands:"
    echo "    cd $AUTOSRE_DIR"
    echo "    docker compose logs -f    # View logs"
    echo "    docker compose down       # Stop services"
    echo ""
}

install_docker_aio() {
    log_info "Installing AutoSRE V2 (All-in-One) with Docker..."
    
    check_docker || exit 1
    download_files
    create_env_file
    
    log_info "Pulling and starting all-in-one container..."
    docker run -d \
        --name autosre \
        --restart unless-stopped \
        -p 3000:3000 \
        -p 8000:8000 \
        -v autosre-data:/data \
        --env-file .env \
        ghcr.io/your-org/autosre:${AUTOSRE_VERSION}
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  AutoSRE V2 is now running!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  UI:  http://localhost:3000"
    echo "  API: http://localhost:8000"
    echo ""
}

install_kubernetes() {
    log_info "Installing AutoSRE V2 on Kubernetes..."
    
    check_kubernetes || exit 1
    download_files
    
    log_info "Applying Kubernetes manifests..."
    kubectl apply -f deploy/kubernetes/namespace.yaml
    kubectl apply -f deploy/kubernetes/
    
    log_info "Waiting for deployment..."
    kubectl rollout status deployment/autosre-api -n autosre --timeout=300s
    kubectl rollout status deployment/autosre-ui -n autosre --timeout=300s
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  AutoSRE V2 deployed to Kubernetes!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Check status: kubectl get pods -n autosre"
    echo ""
    echo "  Port forward:"
    echo "    kubectl port-forward -n autosre svc/autosre-ui 3000:3000"
    echo "    kubectl port-forward -n autosre svc/autosre-api 8000:8000"
    echo ""
}

install_helm() {
    log_info "Installing AutoSRE V2 with Helm..."
    
    check_helm || exit 1
    download_files
    
    log_info "Installing Helm chart..."
    helm dependency update deploy/helm
    helm upgrade --install autosre deploy/helm \
        --namespace autosre \
        --create-namespace \
        --wait
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  AutoSRE V2 deployed with Helm!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Helm status: helm status autosre -n autosre"
    echo ""
}

install_dev() {
    log_info "Setting up development environment..."
    
    check_command python3 || exit 1
    check_command node || exit 1
    
    download_files
    
    log_info "Running setup script..."
    ./scripts/setup-dev.sh
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Development environment ready!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  cd $AUTOSRE_DIR"
    echo "  make dev         # Start development servers"
    echo "  make test        # Run tests"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

print_banner() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║          AutoSRE V2 — AI-Powered SRE Platform                 ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --docker      Install via Docker Compose (default)"
    echo "  --docker-aio  Install all-in-one Docker container"
    echo "  --k8s         Install via Kubernetes manifests"
    echo "  --helm        Install via Helm chart"
    echo "  --dev         Set up development environment"
    echo "  --help        Show this help"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            INSTALL_MODE="docker"
            shift
            ;;
        --docker-aio)
            INSTALL_MODE="docker-aio"
            shift
            ;;
        --k8s|--kubernetes)
            INSTALL_MODE="k8s"
            shift
            ;;
        --helm)
            INSTALL_MODE="helm"
            shift
            ;;
        --dev)
            INSTALL_MODE="dev"
            shift
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

print_banner

case $INSTALL_MODE in
    docker)
        install_docker
        ;;
    docker-aio)
        install_docker_aio
        ;;
    k8s)
        install_kubernetes
        ;;
    helm)
        install_helm
        ;;
    dev)
        install_dev
        ;;
esac
