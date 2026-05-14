# Installation Guide

This guide covers installing AutoSRE V2 for development, Docker-based deployment, and production Kubernetes environments.

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build/dev |
| Docker | 24+ | Container runtime |
| Docker Compose | 2.0+ | Local development stack |

### Optional (Production)

| Software | Version | Purpose |
|----------|---------|---------|
| kubectl | 1.28+ | Kubernetes CLI |
| Helm | 3.12+ | Kubernetes package manager |
| uv | 0.2+ | Fast Python package manager |

### LLM Provider

You need at least one LLM provider configured:

- **OpenAI** — `OPENAI_API_KEY`
- **Anthropic** — `ANTHROPIC_API_KEY`  
- **Ollama** — Local LLM, no API key needed

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/autosre/autosre-v2.git
cd autosre-v2
```

### 2. Run Setup

```bash
make setup
```

This creates:
- `.env` from `.env.example`
- `config.yaml` from `config.example.yaml`
- Required directories (`logs/`, `data/`)

### 3. Configure Environment

Edit `.env` with your settings:

```bash
# Required: Add your LLM API key
OPENAI_API_KEY=sk-your-key-here
# or
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 4. Install Dependencies

```bash
make install
```

This installs:
- Python dependencies via `uv`
- Node.js dependencies via `npm`

### 5. Start Development Servers

```bash
make dev
```

Services will be available at:
- **UI**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Docker Setup

### Development Stack

The Docker Compose setup includes everything needed for local development:

```bash
# Copy and configure environment
cp .env.example .env
vi .env  # Add your API keys

# Start all services
make docker-up

# Follow logs
make docker-logs

# Stop all services
make docker-down
```

### Services Started

| Service | Port | Description |
|---------|------|-------------|
| `autosre-api` | 8000 | FastAPI backend |
| `autosre-ui` | 3000 | React frontend |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache |

### Docker Commands Reference

```bash
# Build images
make docker-build

# Rebuild from scratch (no cache)
make docker-rebuild

# View running containers
make docker-ps

# Shell into API container
make docker-shell-api

# Shell into UI container
make docker-shell-ui

# Clean up volumes and containers
make docker-clean
```

### Custom Docker Compose

Override settings in `docker-compose.override.yml`:

```yaml
# docker-compose.override.yml
services:
  autosre-api:
    environment:
      AUTOSRE_DEBUG: "true"
      LLM_PROVIDER: "anthropic"
    volumes:
      # Mount custom config
      - ./my-config.yaml:/app/config.yaml:ro
```

---

## Kubernetes Setup

### Prerequisites

1. **Kubernetes cluster** (1.28+)
2. **kubectl** configured and authenticated
3. **Ingress controller** (nginx-ingress recommended)
4. **Secrets** configured for API keys

### Using kubectl

```bash
# Create namespace and apply manifests
make k8s-apply

# Check deployment status
make k8s-status

# Follow logs
make k8s-logs

# Port forward for local access
make k8s-port-forward
```

#### Manual Steps

```bash
# Create namespace
kubectl apply -f deploy/kubernetes/namespace.yaml

# Create secrets (edit with your values first!)
kubectl apply -f deploy/kubernetes/secret.yaml

# Create configmap
kubectl apply -f deploy/kubernetes/configmap.yaml

# Deploy services
kubectl apply -f deploy/kubernetes/service.yaml

# Deploy applications
kubectl apply -f deploy/kubernetes/deployment-api.yaml
kubectl apply -f deploy/kubernetes/deployment-ui.yaml

# Create ingress
kubectl apply -f deploy/kubernetes/ingress.yaml
```

### Using Helm

Helm provides templated deployment with environment-specific values.

```bash
# Install with default values
make helm-install

# Install with production values
make helm-install-prod

# Uninstall
make helm-uninstall

# Template locally (preview)
make helm-template
```

#### Custom Helm Values

Create a custom values file:

```yaml
# values-myenv.yaml
replicaCount:
  api: 3
  ui: 2

image:
  registry: your-registry.com
  tag: v2.1.0

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: autosre.yourcompany.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: autosre-tls
      hosts:
        - autosre.yourcompany.com

resources:
  api:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 2000m
      memory: 2Gi
  ui:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 256Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

postgresql:
  enabled: true
  auth:
    postgresPassword: your-password
    database: autosre

redis:
  enabled: true
  architecture: standalone

secrets:
  openaiApiKey: sk-your-key
  # Or use existing secret
  existingSecret: autosre-secrets
```

Install with custom values:

```bash
helm upgrade --install autosre deploy/helm \
  --namespace autosre \
  --create-namespace \
  -f values-myenv.yaml \
  --wait
```

---

## Configuration

### Environment Variables

After setup, configure `.env` with your settings. See [Configuration Reference](./configuration.md) for all options.

Minimum required:

```bash
# LLM Provider (at least one required)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Secret key for JWT (generate: openssl rand -hex 32)
AUTOSRE_SECRET_KEY=your-random-secret
```

### Config File

For detailed settings, edit `config.yaml`:

```yaml
# config.yaml
debug: false
log_level: INFO

default_provider: openai
default_model: gpt-4o

openai:
  enabled: true
  default_model: gpt-4o
  max_retries: 3
  timeout: 120.0

# See configuration.md for all options
```

---

## Verification

### Check Installation

```bash
# Verify all tools are available
make env-check

# Show versions
make version
```

### Test API

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"2.0.0"}
```

### Run Tests

```bash
# All tests
make test

# With coverage
make test-cov
```

---

## Troubleshooting

### Common Issues

#### Python version mismatch

```
ERROR: Python 3.11+ required
```

**Solution**: Install Python 3.11 or newer:
```bash
# macOS
brew install python@3.11

# Ubuntu
sudo apt install python3.11
```

#### Port already in use

```
ERROR: Port 8000 already in use
```

**Solution**: Find and stop the process:
```bash
lsof -i :8000
kill -9 <PID>
```

#### Docker permission denied

```
permission denied while trying to connect to the Docker daemon
```

**Solution**: Add user to docker group:
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

#### LLM API errors

```
ERROR: Invalid API key
```

**Solution**: Verify your API key:
```bash
# Check if set
echo $OPENAI_API_KEY

# Test directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Reset database
make db-reset
```

### Getting Help

1. Check the [FAQ](#faq) section
2. Search [GitHub Issues](https://github.com/autosre/autosre-v2/issues)
3. Open a new issue with:
   - Error message
   - Steps to reproduce
   - Environment details (`make version`)

---

## FAQ

### Can I use a local LLM?

Yes! Configure Ollama:

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama3

# Configure AutoSRE
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

### How do I connect to my Kubernetes cluster?

Mount your kubeconfig:

```yaml
# docker-compose.override.yml
services:
  autosre-api:
    volumes:
      - ~/.kube/config:/app/.kube/config:ro
```

### Can I run without Docker?

Yes, for development:

```bash
# Start just dependencies
docker compose up -d postgres redis

# Run API directly
make dev-api

# In another terminal, run UI
make dev-ui
```

### How do I update?

```bash
git pull origin main
make install
make docker-rebuild  # If using Docker
```
