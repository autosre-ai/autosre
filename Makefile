# =============================================================================
# AutoSRE Makefile
# Production-ready Docker orchestration commands
# =============================================================================

.PHONY: help dev stop logs clean build test setup init status ps shell db-shell redis-cli neo4j-shell lint format

# Default target
.DEFAULT_GOAL := help

# Variables
COMPOSE := docker compose
COMPOSE_FILE := docker-compose.yml
PROJECT_NAME := autosre

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(CYAN)AutoSRE Docker Commands$(RESET)"
	@echo "========================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# Setup & Initialization
# =============================================================================

setup: ## Initial setup - copy env file and create directories
	@echo "$(CYAN)Setting up AutoSRE...$(RESET)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(YELLOW)Created .env file. Please edit it with your configuration.$(RESET)"; \
	else \
		echo "$(GREEN).env file already exists$(RESET)"; \
	fi
	@mkdir -p config init/postgres logs
	@echo "$(GREEN)Setup complete!$(RESET)"

init: setup ## Initialize project with config files
	@echo "$(CYAN)Initializing configuration files...$(RESET)"
	@if [ ! -f config/litellm_config.yaml ]; then \
		echo "model_list:" > config/litellm_config.yaml; \
		echo "  - model_name: gpt-4o" >> config/litellm_config.yaml; \
		echo "    litellm_params:" >> config/litellm_config.yaml; \
		echo "      model: gpt-4o" >> config/litellm_config.yaml; \
		echo "      api_key: os.environ/OPENAI_API_KEY" >> config/litellm_config.yaml; \
		echo "  - model_name: claude-sonnet" >> config/litellm_config.yaml; \
		echo "    litellm_params:" >> config/litellm_config.yaml; \
		echo "      model: claude-sonnet-4-20250514" >> config/litellm_config.yaml; \
		echo "      api_key: os.environ/ANTHROPIC_API_KEY" >> config/litellm_config.yaml; \
		echo "$(GREEN)Created LiteLLM config$(RESET)"; \
	fi
	@echo "$(GREEN)Initialization complete!$(RESET)"

# =============================================================================
# Development Commands
# =============================================================================

dev: init ## Start all services in development mode
	@echo "$(CYAN)Starting AutoSRE services...$(RESET)"
	$(COMPOSE) up -d
	@echo ""
	@echo "$(GREEN)Services started!$(RESET)"
	@echo ""
	@echo "  Web UI:      http://localhost:$${WEB_PORT:-3000}"
	@echo "  API Gateway: http://localhost:$${API_PORT:-8000}"
	@echo "  LiteLLM:     http://localhost:$${LITELLM_PORT:-4000}"
	@echo "  Neo4j:       http://localhost:$${NEO4J_HTTP_PORT:-7474}"
	@echo ""
	@echo "Run '$(CYAN)make logs$(RESET)' to view logs"

up: dev ## Alias for dev

start: dev ## Alias for dev

stop: ## Stop all services
	@echo "$(CYAN)Stopping AutoSRE services...$(RESET)"
	$(COMPOSE) down
	@echo "$(GREEN)Services stopped$(RESET)"

down: stop ## Alias for stop

restart: stop dev ## Restart all services

# =============================================================================
# Logging & Monitoring
# =============================================================================

logs: ## View logs from all services (follow mode)
	$(COMPOSE) logs -f

logs-agent: ## View SRE agent logs
	$(COMPOSE) logs -f sre-agent

logs-api: ## View API gateway logs
	$(COMPOSE) logs -f api-gateway

logs-web: ## View Web UI logs
	$(COMPOSE) logs -f web-ui

status: ## Show service status
	@echo "$(CYAN)AutoSRE Service Status$(RESET)"
	@echo "======================="
	$(COMPOSE) ps

ps: status ## Alias for status

health: ## Check health of all services
	@echo "$(CYAN)Checking service health...$(RESET)"
	@echo ""
	@for service in postgres neo4j redis litellm sre-agent api-gateway web-ui; do \
		health=$$(docker inspect --format='{{.State.Health.Status}}' autosre-$$service 2>/dev/null || echo "not running"); \
		case $$health in \
			healthy) echo "$(GREEN)✓$(RESET) $$service: $$health" ;; \
			unhealthy) echo "$(RED)✗$(RESET) $$service: $$health" ;; \
			starting) echo "$(YELLOW)⋯$(RESET) $$service: $$health" ;; \
			*) echo "$(YELLOW)?$(RESET) $$service: $$health" ;; \
		esac \
	done

# =============================================================================
# Build Commands
# =============================================================================

build: ## Build all Docker images
	@echo "$(CYAN)Building AutoSRE images...$(RESET)"
	$(COMPOSE) build
	@echo "$(GREEN)Build complete!$(RESET)"

build-agent: ## Build SRE agent image only
	$(COMPOSE) build sre-agent

build-api: ## Build API gateway image only
	$(COMPOSE) build api-gateway

build-web: ## Build Web UI image only
	$(COMPOSE) build web-ui

build-no-cache: ## Build all images without cache
	$(COMPOSE) build --no-cache

pull: ## Pull latest base images
	$(COMPOSE) pull

# =============================================================================
# Testing
# =============================================================================

test: ## Run all tests
	@echo "$(CYAN)Running tests...$(RESET)"
	$(COMPOSE) exec sre-agent pytest tests/ -v
	$(COMPOSE) exec api-gateway pytest tests/ -v

test-agent: ## Run agent tests
	$(COMPOSE) exec sre-agent pytest tests/ -v --cov=src --cov-report=term-missing

test-api: ## Run API tests
	$(COMPOSE) exec api-gateway pytest tests/ -v --cov=app --cov-report=term-missing

test-e2e: ## Run end-to-end tests
	@echo "$(CYAN)Running E2E tests...$(RESET)"
	$(COMPOSE) exec api-gateway pytest tests/e2e/ -v

lint: ## Run linters
	$(COMPOSE) exec sre-agent ruff check src/
	$(COMPOSE) exec api-gateway ruff check app/

format: ## Format code
	$(COMPOSE) exec sre-agent ruff format src/
	$(COMPOSE) exec api-gateway ruff format app/

# =============================================================================
# Shell Access
# =============================================================================

shell: shell-agent ## Open shell in agent container

shell-agent: ## Open shell in SRE agent container
	$(COMPOSE) exec sre-agent /bin/bash

shell-api: ## Open shell in API gateway container
	$(COMPOSE) exec api-gateway /bin/bash

shell-web: ## Open shell in Web UI container
	$(COMPOSE) exec web-ui /bin/sh

db-shell: ## Open PostgreSQL shell
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-autosre} -d $${POSTGRES_DB:-autosre}

redis-cli: ## Open Redis CLI
	$(COMPOSE) exec redis redis-cli -a $${REDIS_PASSWORD}

neo4j-shell: ## Open Neo4j Cypher shell
	$(COMPOSE) exec neo4j cypher-shell -u $${NEO4J_USER:-neo4j} -p $${NEO4J_PASSWORD}

# =============================================================================
# Database Management
# =============================================================================

db-migrate: ## Run database migrations
	$(COMPOSE) exec api-gateway alembic upgrade head

db-rollback: ## Rollback last migration
	$(COMPOSE) exec api-gateway alembic downgrade -1

db-reset: ## Reset database (DESTRUCTIVE)
	@echo "$(RED)WARNING: This will delete all data!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	$(COMPOSE) down -v
	$(COMPOSE) up -d postgres neo4j redis
	@sleep 10
	$(COMPOSE) up -d

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Stop services and remove containers
	@echo "$(CYAN)Cleaning up...$(RESET)"
	$(COMPOSE) down --remove-orphans
	@echo "$(GREEN)Cleanup complete$(RESET)"

clean-volumes: ## Remove all volumes (DESTRUCTIVE)
	@echo "$(RED)WARNING: This will delete all data!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	$(COMPOSE) down -v --remove-orphans

clean-images: ## Remove built images
	docker rmi autosre/sre-agent:$${VERSION:-latest} 2>/dev/null || true
	docker rmi autosre/api-gateway:$${VERSION:-latest} 2>/dev/null || true
	docker rmi autosre/web-ui:$${VERSION:-latest} 2>/dev/null || true

clean-all: clean-volumes clean-images ## Remove everything (DESTRUCTIVE)
	docker system prune -f

# =============================================================================
# Production Commands
# =============================================================================

prod: ## Start in production mode with limited logs
	$(COMPOSE) up -d
	$(COMPOSE) logs -f --tail=100

scale-agent: ## Scale agent service (usage: make scale-agent N=3)
	$(COMPOSE) up -d --scale sre-agent=$${N:-2}

backup: ## Backup all data volumes
	@echo "$(CYAN)Creating backups...$(RESET)"
	@mkdir -p backups
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	docker run --rm -v autosre_postgres_data:/data -v $$(pwd)/backups:/backup alpine tar czf /backup/postgres_$$timestamp.tar.gz -C /data .; \
	docker run --rm -v autosre_neo4j_data:/data -v $$(pwd)/backups:/backup alpine tar czf /backup/neo4j_$$timestamp.tar.gz -C /data .; \
	docker run --rm -v autosre_redis_data:/data -v $$(pwd)/backups:/backup alpine tar czf /backup/redis_$$timestamp.tar.gz -C /data .; \
	echo "$(GREEN)Backups saved to ./backups/$(RESET)"

# =============================================================================
# Development Utilities
# =============================================================================

watch: ## Watch for changes and rebuild (development)
	$(COMPOSE) up --build --watch

env-check: ## Validate environment configuration
	@echo "$(CYAN)Checking environment...$(RESET)"
	@if [ ! -f .env ]; then \
		echo "$(RED)ERROR: .env file not found. Run 'make setup' first.$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Environment file found$(RESET)"
	@echo ""
	@echo "Required variables:"
	@for var in POSTGRES_PASSWORD NEO4J_PASSWORD REDIS_PASSWORD LITELLM_MASTER_KEY API_SECRET_KEY JWT_SECRET_KEY NEXTAUTH_SECRET; do \
		if grep -q "^$$var=<" .env 2>/dev/null || ! grep -q "^$$var=" .env 2>/dev/null; then \
			echo "  $(RED)✗$(RESET) $$var: NOT SET"; \
		else \
			echo "  $(GREEN)✓$(RESET) $$var: set"; \
		fi \
	done
