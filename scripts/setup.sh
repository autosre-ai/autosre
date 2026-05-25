#!/usr/bin/env bash
#
# AutoSRE Setup Wizard
# One-command setup for AutoSRE development environment
#
# Usage: ./scripts/setup.sh [--dev|--minimal|--skip-env]
#

set -euo pipefail

# ============================================================================
# Color Definitions
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# Emoji support detection
if [[ "$(uname)" == "Darwin" ]] || [[ "${TERM_PROGRAM:-}" == "vscode" ]]; then
    EMOJI_CHECK="✓"
    EMOJI_CROSS="✗"
    EMOJI_ARROW="→"
    EMOJI_ROCKET="🚀"
    EMOJI_GEAR="⚙️"
    EMOJI_KEY="🔑"
    EMOJI_PACKAGE="📦"
    EMOJI_SPARKLE="✨"
    EMOJI_WARNING="⚠️"
    EMOJI_INFO="ℹ️"
else
    EMOJI_CHECK="[OK]"
    EMOJI_CROSS="[X]"
    EMOJI_ARROW="->"
    EMOJI_ROCKET="[*]"
    EMOJI_GEAR="[*]"
    EMOJI_KEY="[*]"
    EMOJI_PACKAGE="[*]"
    EMOJI_SPARKLE="[*]"
    EMOJI_WARNING="[!]"
    EMOJI_INFO="[i]"
fi

# ============================================================================
# Configuration
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
ENV_FILE="${PROJECT_ROOT}/.env"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"
MIN_PYTHON_VERSION="3.11"

# Parse arguments
INSTALL_DEV=false
INSTALL_MINIMAL=false
SKIP_ENV=false
NON_INTERACTIVE=false
FORCE=false

for arg in "$@"; do
    case $arg in
        --dev)
            INSTALL_DEV=true
            ;;
        --minimal)
            INSTALL_MINIMAL=true
            ;;
        --skip-env)
            SKIP_ENV=true
            ;;
        --non-interactive|-y)
            NON_INTERACTIVE=true
            ;;
        --force|-f)
            FORCE=true
            ;;
        --help|-h)
            echo "AutoSRE Setup Wizard"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dev              Install development dependencies (pytest, ruff, mypy)"
            echo "  --minimal          Install minimal dependencies only"
            echo "  --skip-env         Skip .env file configuration"
            echo "  --non-interactive  Run without prompts (use defaults)"
            echo "  --force            Force overwrite existing files/venv"
            echo "  --help             Show this help message"
            exit 0
            ;;
    esac
done

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}                                                                ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}     ${EMOJI_ROCKET} ${BOLD}${WHITE}AutoSRE Setup Wizard${RESET}                                  ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}     ${DIM}AI-Powered Incident Investigation${RESET}                        ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}                                                                ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
}

print_step() {
    local step_num=$1
    local step_text=$2
    echo ""
    echo -e "${BOLD}${BLUE}[${step_num}]${RESET} ${BOLD}${step_text}${RESET}"
    echo -e "${DIM}────────────────────────────────────────────────────────${RESET}"
}

print_success() {
    echo -e "    ${GREEN}${EMOJI_CHECK}${RESET} $1"
}

print_error() {
    echo -e "    ${RED}${EMOJI_CROSS}${RESET} $1"
}

print_warning() {
    echo -e "    ${YELLOW}${EMOJI_WARNING}${RESET} $1"
}

print_info() {
    echo -e "    ${CYAN}${EMOJI_INFO}${RESET} $1"
}

print_action() {
    echo -e "    ${MAGENTA}${EMOJI_ARROW}${RESET} $1"
}

spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while ps -p "$pid" > /dev/null 2>&1; do
        for i in $(seq 0 9); do
            printf "\r    ${CYAN}%s${RESET} %s" "${spinstr:$i:1}" "$2"
            sleep $delay
        done
    done
    printf "\r"
}

check_command() {
    command -v "$1" &> /dev/null
}

compare_versions() {
    # Returns 0 if $1 >= $2
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

generate_random_string() {
    local length=${1:-32}
    # Avoid special characters that could break sed
    LC_ALL=C tr -dc 'a-zA-Z0-9_-' < /dev/urandom | head -c "$length" || true
}

generate_secure_password() {
    local length=${1:-24}
    LC_ALL=C tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c "$length" || true
}

# ============================================================================
# Setup Steps
# ============================================================================

check_prerequisites() {
    print_step "1/6" "Checking Prerequisites ${EMOJI_GEAR}"
    
    local all_ok=true
    
    # Check Python
    if check_command python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if compare_versions "$PYTHON_VERSION" "$MIN_PYTHON_VERSION"; then
            print_success "Python ${PYTHON_VERSION} found"
        else
            print_error "Python ${PYTHON_VERSION} found, but ${MIN_PYTHON_VERSION}+ required"
            all_ok=false
        fi
    else
        print_error "Python 3 not found"
        all_ok=false
    fi
    
    # Check pip
    if check_command pip3 || check_command pip; then
        print_success "pip available"
    else
        print_error "pip not found"
        all_ok=false
    fi
    
    # Check git
    if check_command git; then
        print_success "git available"
    else
        print_warning "git not found (optional, needed for version control)"
    fi
    
    # Check docker (optional)
    if check_command docker; then
        print_success "Docker available (for containerized deployment)"
    else
        print_info "Docker not found (optional, for containerized deployment)"
    fi
    
    # Check we're in the right directory
    if [[ -f "${PROJECT_ROOT}/pyproject.toml" ]]; then
        print_success "Project root detected: ${PROJECT_ROOT}"
    else
        print_error "Cannot find pyproject.toml. Run from project root."
        all_ok=false
    fi
    
    if [[ "$all_ok" == "false" ]]; then
        echo ""
        print_error "Prerequisites check failed. Please fix the issues above."
        exit 1
    fi
}

setup_environment_file() {
    print_step "2/6" "Setting Up Environment ${EMOJI_KEY}"
    
    if [[ "$SKIP_ENV" == "true" ]]; then
        print_info "Skipping .env setup (--skip-env flag)"
        return 0
    fi
    
    if [[ -f "$ENV_FILE" ]]; then
        print_info ".env file already exists"
        if [[ "$FORCE" == "true" ]]; then
            print_action "Overwriting .env (--force flag)"
        elif [[ "$NON_INTERACTIVE" == "true" ]]; then
            print_info "Keeping existing .env file (non-interactive mode)"
            return 0
        else
            echo -n "    Overwrite with new configuration? [y/N]: "
            read -r response
            if [[ ! "$response" =~ ^[Yy]$ ]]; then
                print_info "Keeping existing .env file"
                return 0
            fi
        fi
    fi
    
    if [[ ! -f "$ENV_EXAMPLE" ]]; then
        print_error ".env.example not found"
        exit 1
    fi
    
    print_action "Creating .env from .env.example"
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    
    # Generate secure random passwords and secrets
    print_action "Generating secure passwords and secrets"
    
    local postgres_password=$(generate_secure_password 24)
    local neo4j_password=$(generate_secure_password 24)
    local redis_password=$(generate_secure_password 24)
    local jwt_secret=$(generate_random_string 48)
    local token_pepper=$(generate_random_string 48)
    local admin_token=$(generate_secure_password 32)
    local litellm_key="sk-autosre-$(generate_secure_password 16)"
    
    # Use sed to replace placeholder values (portable between macOS and Linux)
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s/POSTGRES_PASSWORD=your-secure-password-here/POSTGRES_PASSWORD=${postgres_password}/" "$ENV_FILE"
        sed -i '' "s/NEO4J_PASSWORD=your-secure-password-here/NEO4J_PASSWORD=${neo4j_password}/" "$ENV_FILE"
        sed -i '' "s/REDIS_PASSWORD=your-secure-password-here/REDIS_PASSWORD=${redis_password}/" "$ENV_FILE"
        sed -i '' "s/JWT_SECRET=your-jwt-secret-here-min-32-chars!!/JWT_SECRET=${jwt_secret}/" "$ENV_FILE"
        sed -i '' "s/TOKEN_PEPPER=your-token-pepper-min-32-chars!!/TOKEN_PEPPER=${token_pepper}/" "$ENV_FILE"
        sed -i '' "s/ADMIN_TOKEN=your-admin-token-here/ADMIN_TOKEN=${admin_token}/" "$ENV_FILE"
        sed -i '' "s/LITELLM_API_KEY=sk-autosre/LITELLM_API_KEY=${litellm_key}/" "$ENV_FILE"
    else
        sed -i "s/POSTGRES_PASSWORD=your-secure-password-here/POSTGRES_PASSWORD=${postgres_password}/" "$ENV_FILE"
        sed -i "s/NEO4J_PASSWORD=your-secure-password-here/NEO4J_PASSWORD=${neo4j_password}/" "$ENV_FILE"
        sed -i "s/REDIS_PASSWORD=your-secure-password-here/REDIS_PASSWORD=${redis_password}/" "$ENV_FILE"
        sed -i "s/JWT_SECRET=your-jwt-secret-here-min-32-chars!!/JWT_SECRET=${jwt_secret}/" "$ENV_FILE"
        sed -i "s/TOKEN_PEPPER=your-token-pepper-min-32-chars!!/TOKEN_PEPPER=${token_pepper}/" "$ENV_FILE"
        sed -i "s/ADMIN_TOKEN=your-admin-token-here/ADMIN_TOKEN=${admin_token}/" "$ENV_FILE"
        sed -i "s/LITELLM_API_KEY=sk-autosre/LITELLM_API_KEY=${litellm_key}/" "$ENV_FILE"
    fi
    
    print_success "Generated secure passwords and secrets"
    
    # Prompt for LLM API keys (only in interactive mode)
    if [[ "$NON_INTERACTIVE" != "true" ]]; then
        echo ""
        print_info "Configure LLM API keys (at least one required for investigations)"
        echo ""
        
        echo -n "    Anthropic API key [press Enter to skip]: "
        read -r anthropic_key
        if [[ -n "$anthropic_key" ]]; then
            if [[ "$(uname)" == "Darwin" ]]; then
                sed -i '' "s|ANTHROPIC_API_KEY=sk-ant-...|ANTHROPIC_API_KEY=${anthropic_key}|" "$ENV_FILE"
            else
                sed -i "s|ANTHROPIC_API_KEY=sk-ant-...|ANTHROPIC_API_KEY=${anthropic_key}|" "$ENV_FILE"
            fi
            print_success "Anthropic API key configured"
        fi
        
        echo -n "    OpenAI API key [press Enter to skip]: "
        read -r openai_key
        if [[ -n "$openai_key" ]]; then
            if [[ "$(uname)" == "Darwin" ]]; then
                sed -i '' "s|OPENAI_API_KEY=sk-...|OPENAI_API_KEY=${openai_key}|" "$ENV_FILE"
            else
                sed -i "s|OPENAI_API_KEY=sk-...|OPENAI_API_KEY=${openai_key}|" "$ENV_FILE"
            fi
            print_success "OpenAI API key configured"
        fi
    else
        print_info "Skipping API key prompts (non-interactive mode)"
    fi
    
    echo ""
    print_success ".env file created at ${ENV_FILE}"
    print_warning "Review and update other settings in .env as needed"
}

create_virtual_environment() {
    print_step "3/6" "Creating Virtual Environment ${EMOJI_PACKAGE}"
    
    if [[ -d "$VENV_DIR" ]]; then
        print_info "Virtual environment already exists at ${VENV_DIR}"
        if [[ "$FORCE" == "true" ]]; then
            print_action "Removing existing virtual environment (--force flag)"
            rm -rf "$VENV_DIR"
        elif [[ "$NON_INTERACTIVE" == "true" ]]; then
            print_info "Using existing virtual environment (non-interactive mode)"
            return 0
        else
            echo -n "    Recreate virtual environment? [y/N]: "
            read -r response
            if [[ "$response" =~ ^[Yy]$ ]]; then
                print_action "Removing existing virtual environment"
                rm -rf "$VENV_DIR"
            else
                print_info "Using existing virtual environment"
                return 0
            fi
        fi
    fi
    
    print_action "Creating Python virtual environment"
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment created at ${VENV_DIR}"
    
    # Upgrade pip
    print_action "Upgrading pip"
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    print_success "pip upgraded to latest version"
}

install_dependencies() {
    print_step "4/6" "Installing Dependencies ${EMOJI_PACKAGE}"
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    if [[ "$INSTALL_MINIMAL" == "true" ]]; then
        print_action "Installing minimal dependencies"
        pip install --quiet -e ".[minimal]" 2>&1 | while read -r line; do
            printf "\r    ${DIM}%s${RESET}" "${line:0:60}"
        done
        printf "\r%-70s\r" ""
        print_success "Minimal dependencies installed"
    elif [[ "$INSTALL_DEV" == "true" ]]; then
        print_action "Installing all dependencies including dev tools"
        pip install --quiet -e ".[dev,docs]" 2>&1 | while read -r line; do
            printf "\r    ${DIM}%s${RESET}" "${line:0:60}"
        done
        printf "\r%-70s\r" ""
        print_success "All dependencies installed (including dev tools)"
    else
        print_action "Installing production dependencies"
        pip install --quiet -e . 2>&1 | while read -r line; do
            printf "\r    ${DIM}%s${RESET}" "${line:0:60}"
        done
        printf "\r%-70s\r" ""
        print_success "Production dependencies installed"
    fi
    
    deactivate
}

run_initial_configuration() {
    print_step "5/6" "Running Initial Configuration ${EMOJI_GEAR}"
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Create necessary directories
    print_action "Creating required directories"
    mkdir -p "${PROJECT_ROOT}/data"
    mkdir -p "${PROJECT_ROOT}/logs"
    mkdir -p "${PROJECT_ROOT}/.autosre"
    print_success "Directories created"
    
    # Initialize SQLite database for episodic memory (if autosre is installed)
    if check_command autosre; then
        print_action "Checking autosre CLI"
        if autosre --version &>/dev/null; then
            print_success "autosre CLI available"
        else
            print_info "autosre CLI installed but not fully configured"
        fi
    else
        print_info "autosre CLI will be available after environment activation"
    fi
    
    # Check for pre-commit hooks
    if [[ "$INSTALL_DEV" == "true" ]] && check_command pre-commit; then
        print_action "Installing pre-commit hooks"
        pre-commit install &>/dev/null || true
        print_success "Pre-commit hooks installed"
    fi
    
    deactivate
}

validate_installation() {
    print_step "6/6" "Validating Installation ${EMOJI_SPARKLE}"
    
    local all_ok=true
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Check Python in venv
    if [[ -f "${VENV_DIR}/bin/python" ]]; then
        print_success "Python virtual environment valid"
    else
        print_error "Virtual environment Python not found"
        all_ok=false
    fi
    
    # Check autosre package is installed
    if python -c "import autosre" &>/dev/null; then
        print_success "autosre package installed"
    else
        # Try to import from src
        if python -c "import sys; sys.path.insert(0, 'src'); import autosre" &>/dev/null; then
            print_success "autosre package available (development mode)"
        else
            print_warning "autosre package not fully importable (may need additional config)"
        fi
    fi
    
    # Check key dependencies
    for pkg in pydantic typer rich httpx; do
        if python -c "import $pkg" &>/dev/null; then
            print_success "${pkg} available"
        else
            print_error "${pkg} not installed"
            all_ok=false
        fi
    done
    
    # Check .env file
    if [[ -f "$ENV_FILE" ]]; then
        print_success ".env file exists"
        
        # Check for placeholder values
        if grep -q "sk-ant-\.\.\." "$ENV_FILE" && grep -q "sk-\.\.\." "$ENV_FILE"; then
            print_warning "No LLM API keys configured (required for investigations)"
        else
            print_success "At least one LLM API key configured"
        fi
    else
        print_warning ".env file not created"
    fi
    
    deactivate
    
    if [[ "$all_ok" == "false" ]]; then
        echo ""
        print_warning "Some validation checks failed, but setup may still work"
    fi
}

print_completion_message() {
    echo ""
    echo -e "${BOLD}${GREEN}╔════════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${GREEN}║${RESET}                                                                ${BOLD}${GREEN}║${RESET}"
    echo -e "${BOLD}${GREEN}║${RESET}     ${EMOJI_SPARKLE} ${BOLD}${WHITE}Setup Complete!${RESET}                                       ${BOLD}${GREEN}║${RESET}"
    echo -e "${BOLD}${GREEN}║${RESET}                                                                ${BOLD}${GREEN}║${RESET}"
    echo -e "${BOLD}${GREEN}╚════════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    echo -e "${BOLD}Next Steps:${RESET}"
    echo ""
    echo -e "  ${CYAN}1.${RESET} Activate the virtual environment:"
    echo -e "     ${DIM}source .venv/bin/activate${RESET}"
    echo ""
    echo -e "  ${CYAN}2.${RESET} Configure your LLM API key in .env (if not done):"
    echo -e "     ${DIM}ANTHROPIC_API_KEY=sk-ant-...${RESET}"
    echo -e "     ${DIM}# or${RESET}"
    echo -e "     ${DIM}OPENAI_API_KEY=sk-...${RESET}"
    echo ""
    echo -e "  ${CYAN}3.${RESET} Run your first investigation:"
    echo -e "     ${DIM}autosre investigate \"high latency on api-gateway\" --mock${RESET}"
    echo ""
    echo -e "  ${CYAN}4.${RESET} For production deployment with Docker:"
    echo -e "     ${DIM}docker compose up -d${RESET}"
    echo ""
    echo -e "${DIM}────────────────────────────────────────────────────────────────${RESET}"
    echo -e "${DIM}Documentation: https://github.com/autosre-ai/autosre${RESET}"
    echo -e "${DIM}Support: https://discord.gg/autosre${RESET}"
    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    cd "$PROJECT_ROOT"
    
    print_header
    check_prerequisites
    setup_environment_file
    create_virtual_environment
    install_dependencies
    run_initial_configuration
    validate_installation
    print_completion_message
}

main
