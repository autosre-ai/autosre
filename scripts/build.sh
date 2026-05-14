#!/bin/bash
set -euo pipefail

# AutoSRE V2 - Production Build
# Builds Python wheel, Docker images, and UI static files

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
BUILD_WHEEL=true
BUILD_DOCKER=true
BUILD_UI=true
PUSH_IMAGES=false
VERSION=""
DOCKER_REGISTRY="${DOCKER_REGISTRY:-}"

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Build AutoSRE V2 for production.

Options:
    --wheel-only        Build Python wheel only
    --docker-only       Build Docker images only
    --ui-only           Build UI static files only
    --push              Push Docker images to registry
    --version VERSION   Set version tag (default: git tag or 'latest')
    --registry URL      Docker registry URL
    -h, --help          Show this help message

Environment:
    DOCKER_REGISTRY     Default Docker registry URL

Examples:
    $(basename "$0")                           # Build everything
    $(basename "$0") --docker-only --push      # Build and push images
    $(basename "$0") --version v1.0.0          # Build with specific version
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --wheel-only)
            BUILD_WHEEL=true
            BUILD_DOCKER=false
            BUILD_UI=false
            shift
            ;;
        --docker-only)
            BUILD_WHEEL=false
            BUILD_DOCKER=true
            BUILD_UI=false
            shift
            ;;
        --ui-only)
            BUILD_WHEEL=false
            BUILD_DOCKER=false
            BUILD_UI=true
            shift
            ;;
        --push)
            PUSH_IMAGES=true
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --registry)
            DOCKER_REGISTRY="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

# Determine version
if [ -z "$VERSION" ]; then
    VERSION=$(git describe --tags --always 2>/dev/null || echo "latest")
fi
log_info "Building version: $VERSION"

# Build Python wheel
build_wheel() {
    log_info "Building Python wheel..."
    
    # Clean previous builds
    rm -rf dist/ build/ *.egg-info
    
    # Activate venv if exists
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
    
    # Install build tools
    pip install --quiet build wheel
    
    # Build wheel
    python -m build --wheel
    
    log_success "Wheel built: $(ls dist/*.whl)"
}

# Build UI static files
build_ui() {
    log_info "Building UI static files..."
    
    if [ ! -d "ui" ]; then
        log_warn "UI directory not found, skipping"
        return 0
    fi
    
    cd ui
    
    # Install dependencies
    npm ci --silent
    
    # Run type check
    npm run typecheck 2>/dev/null || log_warn "Type check failed or not configured"
    
    # Build production bundle
    npm run build
    
    cd "$PROJECT_ROOT"
    
    # Copy to static dir for API serving
    mkdir -p src/autosre/api/static
    cp -r ui/dist/* src/autosre/api/static/
    
    log_success "UI built: ui/dist/"
}

# Build Docker images
build_docker() {
    log_info "Building Docker images..."
    
    if [ ! -f "Dockerfile" ]; then
        log_error "Dockerfile not found"
        return 1
    fi
    
    local IMAGE_NAME="autosre"
    local FULL_TAG="$IMAGE_NAME:$VERSION"
    
    if [ -n "$DOCKER_REGISTRY" ]; then
        FULL_TAG="$DOCKER_REGISTRY/$FULL_TAG"
    fi
    
    # Build API image
    docker build \
        --tag "$FULL_TAG" \
        --tag "$IMAGE_NAME:latest" \
        --build-arg VERSION="$VERSION" \
        --file Dockerfile \
        .
    
    log_success "Docker image built: $FULL_TAG"
    
    # Build worker image if exists
    if [ -f "Dockerfile.worker" ]; then
        local WORKER_TAG="$IMAGE_NAME-worker:$VERSION"
        if [ -n "$DOCKER_REGISTRY" ]; then
            WORKER_TAG="$DOCKER_REGISTRY/$WORKER_TAG"
        fi
        
        docker build \
            --tag "$WORKER_TAG" \
            --tag "$IMAGE_NAME-worker:latest" \
            --build-arg VERSION="$VERSION" \
            --file Dockerfile.worker \
            .
        
        log_success "Worker image built: $WORKER_TAG"
    fi
    
    # Push if requested
    if [ "$PUSH_IMAGES" = true ]; then
        if [ -z "$DOCKER_REGISTRY" ]; then
            log_error "Cannot push: DOCKER_REGISTRY not set"
            return 1
        fi
        
        log_info "Pushing images..."
        docker push "$FULL_TAG"
        docker push "$IMAGE_NAME:latest"
        
        if [ -f "Dockerfile.worker" ]; then
            docker push "$WORKER_TAG"
            docker push "$IMAGE_NAME-worker:latest"
        fi
        
        log_success "Images pushed to $DOCKER_REGISTRY"
    fi
}

# Main build
main() {
    log_info "🔨 Starting AutoSRE V2 production build..."
    echo ""
    
    local start_time=$(date +%s)
    
    if [ "$BUILD_UI" = true ]; then
        build_ui
    fi
    
    if [ "$BUILD_WHEEL" = true ]; then
        build_wheel
    fi
    
    if [ "$BUILD_DOCKER" = true ]; then
        build_docker
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    log_success "Build complete in ${duration}s"
    echo ""
    echo "  Version: $VERSION"
    [ "$BUILD_WHEEL" = true ] && echo "  Wheel:   dist/*.whl"
    [ "$BUILD_UI" = true ] && echo "  UI:      ui/dist/"
    [ "$BUILD_DOCKER" = true ] && echo "  Images:  autosre:$VERSION"
    echo ""
}

main "$@"
