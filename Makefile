# ═══════════════════════════════════════════════════════════════════════════════
# AutoSRE V2 — Makefile
# ═══════════════════════════════════════════════════════════════════════════════
#
# AI-Powered Site Reliability Engineering Assistant
#
# Usage:
#   make help          Show available commands
#   make dev           Start local development
#   make docker-up     Start Docker Compose stack
#   make k8s-apply     Deploy to Kubernetes
#
# ═══════════════════════════════════════════════════════════════════════════════

.PHONY: help install dev test lint format docker-build docker-up docker-down \
        docker-logs k8s-apply helm-install clean test-cov dev-api dev-ui \
        docker-clean docker-rebuild docker-ps db-migrate db-upgrade db-downgrade \
        docs docs-serve version pre-commit check build build-api build-ui \
        helm-deps helm-uninstall helm-template helm-lint k8s-delete k8s-status \
        k8s-logs k8s-shell k8s-port-forward test-unit test-integration test-e2e \
        test-watch lint-fix setup

# Default target
.DEFAULT_GOAL := help

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Tools
DOCKER_COMPOSE := docker compose
KUBECTL        := kubectl
HELM           := helm
UV             := uv
NPM            := npm

# Docker
IMAGE_REGISTRY ?= ghcr.io/autosre
IMAGE_TAG      ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
DOCKER_BUILDKIT := 1

# Kubernetes
NAMESPACE      := autosre
RELEASE_NAME   := autosre

# Python
PYTHON_VERSION := 3.11
VENV_DIR       := .venv

# Colors for pretty output
BLUE   := \033[0;34m
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
CYAN   := \033[0;36m
BOLD   := \033[1m
NC     := \033[0m

# ─────────────────────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────────────────────

help: ## Show this help
	@echo ""
	@echo "$(BOLD)$(BLUE)╔═══════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BOLD)$(BLUE)║            AutoSRE V2 — Make Commands                         ║$(NC)"
	@echo "$(BOLD)$(BLUE)╚═══════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(BOLD)$(GREEN)🚀 Quick Start:$(NC)"
	@echo "  $(YELLOW)make install$(NC)      Install all dependencies"
	@echo "  $(YELLOW)make dev$(NC)          Start development servers"
	@echo "  $(YELLOW)make docker-up$(NC)    Start with Docker Compose"
	@echo ""
	@echo "$(BOLD)$(GREEN)📦 Development:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /install|dev|setup/ {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(GREEN)🧪 Testing & Quality:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /test|lint|format|check|pre-commit/ {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(GREEN)🐳 Docker:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /docker/ {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(GREEN)☸️  Kubernetes:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /k8s/ {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(GREEN)⛵ Helm:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /helm/ {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(GREEN)🗃️  Database:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /db-/ {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(GREEN)🔧 Utilities:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /clean|docs|version|build[^-]/ {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Development
# ─────────────────────────────────────────────────────────────────────────────

install: ## Install dependencies (Python + Node)
	@echo "$(GREEN)📦 Installing Python dependencies with uv...$(NC)"
	@$(UV) sync --all-extras
	@echo ""
	@echo "$(GREEN)📦 Installing Node dependencies...$(NC)"
	@cd web-ui && $(NPM) install
	@echo ""
	@echo "$(GREEN)✅ All dependencies installed!$(NC)"
	@echo "   Run '$(YELLOW)make dev$(NC)' to start development servers"

dev: ## Run development servers (API + UI)
	@echo "$(GREEN)🚀 Starting development environment...$(NC)"
	@echo ""
	@echo "$(CYAN)Starting infrastructure...$(NC)"
	@$(DOCKER_COMPOSE) up -d postgres redis
	@echo "$(YELLOW)⏳ Waiting for services to be healthy...$(NC)"
	@sleep 3
	@echo ""
	@echo "$(CYAN)Starting servers (Ctrl+C to stop all):$(NC)"
	@echo "  • API: $(YELLOW)http://localhost:8000$(NC)"
	@echo "  • UI:  $(YELLOW)http://localhost:3000$(NC)"
	@echo "  • Docs: $(YELLOW)http://localhost:8000/docs$(NC)"
	@echo ""
	@trap 'kill 0' SIGINT; \
		(cd src && $(UV) run uvicorn autosre.api.main:app --reload --host 0.0.0.0 --port 8000) & \
		(cd web-ui && $(NPM) run dev) & \
		wait

dev-api: ## Run development API only
	@echo "$(GREEN)🚀 Starting API server...$(NC)"
	@echo "   URL: $(YELLOW)http://localhost:8000$(NC)"
	@echo "   Docs: $(YELLOW)http://localhost:8000/docs$(NC)"
	@cd src && $(UV) run uvicorn autosre.api.main:app --reload --host 0.0.0.0 --port 8000

dev-ui: ## Run development UI only
	@echo "$(GREEN)🚀 Starting UI server...$(NC)"
	@echo "   URL: $(YELLOW)http://localhost:3000$(NC)"
	@cd web-ui && $(NPM) run dev

setup: ## Initial project setup (copy configs, create dirs)
	@echo "$(GREEN)🔧 Setting up project...$(NC)"
	@test -f .env || cp .env.example .env
	@test -f config.yaml || cp config.example.yaml config.yaml
	@mkdir -p logs data
	@echo "$(GREEN)✅ Setup complete!$(NC)"
	@echo "   Edit $(YELLOW).env$(NC) with your configuration"
	@echo "   Then run $(YELLOW)make install$(NC)"

# ─────────────────────────────────────────────────────────────────────────────
# Testing & Quality
# ─────────────────────────────────────────────────────────────────────────────

test: ## Run tests
	@echo "$(GREEN)🧪 Running tests...$(NC)"
	@$(UV) run pytest tests/ -v

test-cov: ## Run tests with coverage
	@echo "$(GREEN)🧪 Running tests with coverage...$(NC)"
	@$(UV) run pytest tests/ -v --cov=src/autosre --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "$(GREEN)📊 Coverage report: $(YELLOW)htmlcov/index.html$(NC)"

test-unit: ## Run unit tests only
	@$(UV) run pytest tests/unit -v

test-integration: ## Run integration tests
	@$(UV) run pytest tests/integration -v

test-e2e: ## Run end-to-end tests
	@$(UV) run pytest tests/e2e -v --timeout=120

test-watch: ## Run tests in watch mode
	@$(UV) run ptw tests/ -- -v

lint: ## Run linters (ruff + mypy + eslint)
	@echo "$(GREEN)🔍 Running linters...$(NC)"
	@echo "$(CYAN)→ Ruff (Python)$(NC)"
	@$(UV) run ruff check src/ tests/
	@echo "$(CYAN)→ Mypy (type checking)$(NC)"
	@$(UV) run mypy src/
	@echo "$(CYAN)→ ESLint (TypeScript)$(NC)"
	@cd web-ui && $(NPM) run lint
	@echo "$(GREEN)✅ All checks passed!$(NC)"

lint-fix: ## Fix linting issues automatically
	@echo "$(GREEN)🔧 Fixing linting issues...$(NC)"
	@$(UV) run ruff check src/ tests/ --fix
	@$(UV) run ruff format src/ tests/
	@cd web-ui && $(NPM) run lint -- --fix

format: ## Format code (ruff + prettier)
	@echo "$(GREEN)✨ Formatting code...$(NC)"
	@$(UV) run ruff format src/ tests/
	@cd web-ui && $(NPM) run format
	@echo "$(GREEN)✅ Code formatted!$(NC)"

check: lint test ## Run lints and tests

pre-commit: ## Run pre-commit hooks
	@$(UV) run pre-commit run --all-files

# ─────────────────────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────────────────────

docker-build: ## Build Docker images
	@echo "$(GREEN)🐳 Building Docker images...$(NC)"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_COMPOSE) build
	@echo "$(GREEN)✅ Images built!$(NC)"

docker-up: ## Start Docker Compose stack
	@echo "$(GREEN)🐳 Starting Docker stack...$(NC)"
	@$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "$(GREEN)✅ Services started:$(NC)"
	@echo "   • API:      $(YELLOW)http://localhost:8000$(NC)"
	@echo "   • UI:       $(YELLOW)http://localhost:3000$(NC)"
	@echo "   • API Docs: $(YELLOW)http://localhost:8000/docs$(NC)"
	@echo ""
	@echo "   Run '$(YELLOW)make docker-logs$(NC)' to follow logs"

docker-down: ## Stop Docker Compose stack
	@echo "$(YELLOW)🛑 Stopping Docker stack...$(NC)"
	@$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✅ Stopped$(NC)"

docker-logs: ## Follow Docker logs
	@$(DOCKER_COMPOSE) logs -f

docker-logs-api: ## Follow API container logs
	@$(DOCKER_COMPOSE) logs -f autosre-api

docker-logs-ui: ## Follow UI container logs
	@$(DOCKER_COMPOSE) logs -f autosre-ui

docker-ps: ## Show running containers
	@$(DOCKER_COMPOSE) ps

docker-clean: ## Remove containers, volumes, and orphans
	@echo "$(RED)🗑️  Removing containers and volumes...$(NC)"
	@$(DOCKER_COMPOSE) down -v --remove-orphans
	@docker volume rm autosre-postgres-data autosre-redis-data 2>/dev/null || true
	@echo "$(GREEN)✅ Cleaned$(NC)"

docker-rebuild: ## Rebuild and restart containers
	@echo "$(YELLOW)🔄 Rebuilding containers...$(NC)"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_COMPOSE) build --no-cache
	@$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✅ Rebuilt and restarted$(NC)"

docker-shell-api: ## Shell into API container
	@$(DOCKER_COMPOSE) exec autosre-api /bin/bash

docker-shell-ui: ## Shell into UI container
	@$(DOCKER_COMPOSE) exec autosre-ui /bin/sh

# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────

build: build-api build-ui ## Build all Docker images

build-api: ## Build API Docker image
	@echo "$(GREEN)🔨 Building API image...$(NC)"
	@docker build -t $(IMAGE_REGISTRY)/autosre-api:$(IMAGE_TAG) -f docker/Dockerfile.api .
	@echo "$(GREEN)✅ Built: $(IMAGE_REGISTRY)/autosre-api:$(IMAGE_TAG)$(NC)"

build-ui: ## Build UI Docker image
	@echo "$(GREEN)🔨 Building UI image...$(NC)"
	@docker build -t $(IMAGE_REGISTRY)/autosre-ui:$(IMAGE_TAG) -f docker/Dockerfile.ui .
	@echo "$(GREEN)✅ Built: $(IMAGE_REGISTRY)/autosre-ui:$(IMAGE_TAG)$(NC)"

build-push: build ## Build and push all images
	@echo "$(GREEN)📤 Pushing images...$(NC)"
	@docker push $(IMAGE_REGISTRY)/autosre-api:$(IMAGE_TAG)
	@docker push $(IMAGE_REGISTRY)/autosre-ui:$(IMAGE_TAG)
	@echo "$(GREEN)✅ Pushed$(NC)"

# ─────────────────────────────────────────────────────────────────────────────
# Kubernetes
# ─────────────────────────────────────────────────────────────────────────────

k8s-apply: ## Apply Kubernetes manifests
	@echo "$(GREEN)☸️  Deploying to Kubernetes...$(NC)"
	@$(KUBECTL) apply -f deploy/kubernetes/namespace.yaml
	@$(KUBECTL) apply -f deploy/kubernetes/
	@echo ""
	@echo "$(GREEN)✅ Deployed!$(NC)"
	@echo "   Run '$(YELLOW)make k8s-status$(NC)' to check status"

k8s-delete: ## Delete Kubernetes resources
	@echo "$(RED)🗑️  Deleting from Kubernetes...$(NC)"
	@$(KUBECTL) delete -f deploy/kubernetes/ --ignore-not-found
	@echo "$(GREEN)✅ Deleted$(NC)"

k8s-status: ## Show Kubernetes deployment status
	@echo "$(BOLD)$(BLUE)=== Pods ===$(NC)"
	@$(KUBECTL) get pods -n $(NAMESPACE) -o wide 2>/dev/null || echo "Namespace not found"
	@echo ""
	@echo "$(BOLD)$(BLUE)=== Services ===$(NC)"
	@$(KUBECTL) get svc -n $(NAMESPACE) 2>/dev/null || echo "Namespace not found"
	@echo ""
	@echo "$(BOLD)$(BLUE)=== Ingress ===$(NC)"
	@$(KUBECTL) get ingress -n $(NAMESPACE) 2>/dev/null || echo "Namespace not found"

k8s-logs: ## Follow Kubernetes logs
	@$(KUBECTL) logs -n $(NAMESPACE) -l app.kubernetes.io/name=autosre --tail=100 -f

k8s-logs-api: ## Follow API pod logs
	@$(KUBECTL) logs -n $(NAMESPACE) -l app.kubernetes.io/component=api --tail=100 -f

k8s-shell: ## Shell into API pod
	@$(KUBECTL) exec -it -n $(NAMESPACE) deploy/autosre-api -- /bin/bash

k8s-port-forward: ## Port forward services locally
	@echo "$(GREEN)🔀 Port forwarding...$(NC)"
	@echo "   • API: $(YELLOW)http://localhost:8000$(NC)"
	@echo "   • UI:  $(YELLOW)http://localhost:3000$(NC)"
	@$(KUBECTL) port-forward -n $(NAMESPACE) svc/autosre-api 8000:8000 &
	@$(KUBECTL) port-forward -n $(NAMESPACE) svc/autosre-ui 3000:3000

# ─────────────────────────────────────────────────────────────────────────────
# Helm
# ─────────────────────────────────────────────────────────────────────────────

helm-deps: ## Update Helm dependencies
	@$(HELM) dependency update deploy/helm

helm-install: helm-deps ## Install Helm chart
	@echo "$(GREEN)⛵ Installing with Helm...$(NC)"
	@$(HELM) upgrade --install $(RELEASE_NAME) deploy/helm \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--wait
	@echo "$(GREEN)✅ Installed!$(NC)"

helm-install-prod: helm-deps ## Install Helm chart with production values
	@$(HELM) upgrade --install $(RELEASE_NAME) deploy/helm \
		--namespace $(NAMESPACE) \
		--create-namespace \
		-f deploy/helm/values-production.yaml \
		--wait

helm-uninstall: ## Uninstall Helm release
	@$(HELM) uninstall $(RELEASE_NAME) -n $(NAMESPACE)

helm-template: ## Render Helm templates locally
	@$(HELM) template $(RELEASE_NAME) deploy/helm --debug

helm-lint: ## Lint Helm chart
	@$(HELM) lint deploy/helm

# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

db-migrate: ## Run database migrations
	@echo "$(GREEN)🗃️  Running migrations...$(NC)"
	@$(UV) run alembic upgrade head

db-upgrade: ## Upgrade database to head
	@$(UV) run alembic upgrade head

db-downgrade: ## Downgrade database one revision
	@$(UV) run alembic downgrade -1

db-revision: ## Create new migration (interactive)
	@read -p "Migration message: " msg; \
	$(UV) run alembic revision --autogenerate -m "$$msg"

db-reset: ## Reset database (⚠️ destructive)
	@echo "$(RED)⚠️  This will delete all data!$(NC)"
	@read -p "Are you sure? [y/N] " confirm; \
	if [ "$$confirm" = "y" ]; then \
		$(DOCKER_COMPOSE) down -v postgres; \
		$(DOCKER_COMPOSE) up -d postgres; \
		sleep 3; \
		$(MAKE) db-migrate; \
	fi

# ─────────────────────────────────────────────────────────────────────────────
# Documentation
# ─────────────────────────────────────────────────────────────────────────────

docs: ## Generate documentation
	@echo "$(GREEN)📚 Building documentation...$(NC)"
	@cd docs && mkdocs build
	@echo "$(GREEN)✅ Docs built in docs/site/$(NC)"

docs-serve: ## Serve documentation locally
	@echo "$(GREEN)📚 Serving documentation...$(NC)"
	@echo "   URL: $(YELLOW)http://localhost:8080$(NC)"
	@cd docs && mkdocs serve -a 0.0.0.0:8080

# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

clean: ## Clean build artifacts
	@echo "$(YELLOW)🧹 Cleaning...$(NC)"
	@rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@cd web-ui && rm -rf .next node_modules/.cache dist/ 2>/dev/null || true
	@echo "$(GREEN)✅ Cleaned$(NC)"

version: ## Show tool versions
	@echo "$(BOLD)$(BLUE)Tool Versions:$(NC)"
	@echo "  Python:     $$(python --version 2>/dev/null || echo 'not installed')"
	@echo "  uv:         $$($(UV) --version 2>/dev/null || echo 'not installed')"
	@echo "  Node:       $$(node --version 2>/dev/null || echo 'not installed')"
	@echo "  npm:        $$(npm --version 2>/dev/null || echo 'not installed')"
	@echo "  Docker:     $$(docker --version 2>/dev/null || echo 'not installed')"
	@echo "  kubectl:    $$($(KUBECTL) version --client --short 2>/dev/null || echo 'not installed')"
	@echo "  Helm:       $$($(HELM) version --short 2>/dev/null || echo 'not installed')"

env-check: ## Verify environment setup
	@echo "$(BOLD)$(BLUE)Environment Check:$(NC)"
	@echo ""
	@echo "$(CYAN)Required:$(NC)"
	@command -v python >/dev/null && echo "  ✅ Python" || echo "  ❌ Python (required)"
	@command -v uv >/dev/null && echo "  ✅ uv" || echo "  ❌ uv (install: curl -LsSf https://astral.sh/uv/install.sh | sh)"
	@command -v node >/dev/null && echo "  ✅ Node.js" || echo "  ❌ Node.js (required)"
	@command -v docker >/dev/null && echo "  ✅ Docker" || echo "  ❌ Docker (required)"
	@echo ""
	@echo "$(CYAN)Optional:$(NC)"
	@command -v kubectl >/dev/null && echo "  ✅ kubectl" || echo "  ⚪ kubectl (for k8s deployment)"
	@command -v helm >/dev/null && echo "  ✅ Helm" || echo "  ⚪ Helm (for helm deployment)"
	@echo ""
	@echo "$(CYAN)Config:$(NC)"
	@test -f .env && echo "  ✅ .env exists" || echo "  ⚪ .env missing (run: make setup)"
	@test -f config.yaml && echo "  ✅ config.yaml exists" || echo "  ⚪ config.yaml missing"
