# Installation

AutoSRE can be installed via pip, Docker, or Helm for Kubernetes deployments.

## Quick Install

=== "pip"

    ```bash
    pip install autosre
    ```

=== "pipx"

    ```bash
    pipx install autosre
    ```

=== "Docker"

    ```bash
    docker pull ghcr.io/autosre/autosre:latest
    ```

## Method 1: pip (Recommended for Development)

### Basic Installation

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install AutoSRE
pip install autosre
```

### Installation with Extras

```bash
# Full installation with all integrations
pip install "autosre[all]"

# Minimal installation (CLI only)
pip install "autosre[minimal]"

# Development installation
pip install "autosre[dev]"
```

### From Source

```bash
git clone https://github.com/autosre/autosre.git
cd autosre
pip install -e ".[dev]"
```

### Verify Installation

```bash
autosre --version
autosre status
```

---

## Method 2: Docker

### Single Container

```bash
# Pull the image
docker pull ghcr.io/autosre/autosre:latest

# Run with environment variables
docker run -it --rm \
  -e ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY} \
  -e AUTOSRE_AUTONOMY=suggest \
  -v ~/.kube:/root/.kube:ro \
  ghcr.io/autosre/autosre:latest \
  autosre investigate "High error rate on payment-service"
```

### Interactive Shell

```bash
docker run -it --rm \
  -e ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY} \
  -v ~/.kube:/root/.kube:ro \
  -v $(pwd)/config:/app/config \
  ghcr.io/autosre/autosre:latest \
  /bin/bash
```

---

## Method 3: Docker Compose (Full Stack)

The Docker Compose setup includes all dependencies:

- **API Gateway** — FastAPI REST API
- **SRE Agent** — AI investigation engine
- **LiteLLM** — LLM proxy
- **PostgreSQL** — Investigation storage
- **Neo4j** — Knowledge graph
- **Redis** — Caching & pub/sub

### Quick Start

```bash
# Clone the repository
git clone https://github.com/autosre/autosre.git
cd autosre

# Copy environment template
cp .env.example .env

# Edit configuration
vim .env  # Set API keys and passwords

# Start all services
docker compose up -d

# Check status
docker compose ps
docker compose logs -f
```

### Required Environment Variables

Create a `.env` file:

```bash
# LLM Provider (choose one)
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENAI_API_KEY=sk-...

# Database passwords
POSTGRES_PASSWORD=your-secure-password
NEO4J_PASSWORD=your-secure-password
REDIS_PASSWORD=your-secure-password

# Security keys (generate with: openssl rand -hex 32)
API_SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-key

# Optional: Integrations
SLACK_BOT_TOKEN=xoxb-...
PAGERDUTY_API_KEY=...
DATADOG_API_KEY=...
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| `web-ui` | 3000 | Web dashboard |
| `api-gateway` | 8000 | REST API |
| `litellm` | 4000 | LLM proxy |
| `postgres` | 5432 | PostgreSQL |
| `neo4j` | 7474, 7687 | Graph database |
| `redis` | 6379 | Cache |

### Useful Commands

```bash
# View logs
docker compose logs -f sre-agent

# Restart a service
docker compose restart api-gateway

# Stop everything
docker compose down

# Stop and remove data
docker compose down -v
```

---

## Method 4: Helm (Kubernetes)

### Prerequisites

- Kubernetes 1.24+
- Helm 3.8+
- kubectl configured

### Add the Helm Repository

```bash
helm repo add autosre https://charts.autosre.io
helm repo update
```

### Install

```bash
# Create namespace
kubectl create namespace autosre

# Create secrets
kubectl create secret generic autosre-secrets \
  --namespace autosre \
  --from-literal=anthropic-api-key=$ANTHROPIC_API_KEY \
  --from-literal=postgres-password=$(openssl rand -hex 16) \
  --from-literal=jwt-secret=$(openssl rand -hex 32)

# Install with default values
helm install autosre autosre/autosre \
  --namespace autosre \
  --set secrets.existingSecret=autosre-secrets
```

### Custom Values

Create a `values.yaml`:

```yaml
# values.yaml
image:
  repository: ghcr.io/autosre/autosre
  tag: "1.0.0"

agent:
  replicas: 2
  autonomy: suggest  # observe, suggest, auto_safe, auto_all
  
  resources:
    requests:
      memory: "2Gi"
      cpu: "500m"
    limits:
      memory: "4Gi"
      cpu: "2000m"

api:
  replicas: 3
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: autosre.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: autosre-tls
        hosts:
          - autosre.example.com

llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  # Or use LiteLLM proxy
  # litellm:
  #   enabled: true
  #   models:
  #     - model_name: gpt-4
  #       litellm_params:
  #         model: azure/gpt-4
  #         api_base: https://your-resource.openai.azure.com

postgresql:
  enabled: true
  auth:
    existingSecret: autosre-secrets
    secretKeys:
      adminPasswordKey: postgres-password

neo4j:
  enabled: true
  neo4j:
    password: existingSecret

redis:
  enabled: true
  auth:
    enabled: true

integrations:
  slack:
    enabled: true
    secretRef: slack-credentials
  pagerduty:
    enabled: true
    secretRef: pagerduty-credentials
  kubernetes:
    enabled: true
    inCluster: true
```

Install with custom values:

```bash
helm install autosre autosre/autosre \
  --namespace autosre \
  --values values.yaml
```

### Verify Installation

```bash
# Check pods
kubectl get pods -n autosre

# Check services
kubectl get svc -n autosre

# View logs
kubectl logs -n autosre -l app=autosre-agent -f

# Test API
kubectl port-forward -n autosre svc/autosre-api 8000:8000
curl http://localhost:8000/health
```

### Upgrade

```bash
helm repo update
helm upgrade autosre autosre/autosre \
  --namespace autosre \
  --values values.yaml
```

### Uninstall

```bash
helm uninstall autosre --namespace autosre
kubectl delete namespace autosre
```

---

## Verifying Installation

After installation, verify everything is working:

### 1. Check Status

```bash
autosre status
```

Expected output:

```
╭─────────────────────────────────────────────────────────────╮
│                       AutoSRE Status                        │
├─────────────────────────────────────────────────────────────┤
│ Version: 1.0.0                                              │
│ Config: ~/.autosre/config.yaml                              │
├─────────────────────────────────────────────────────────────┤
│ LLM Provider: anthropic (claude-3-5-sonnet)           ✓     │
│ Context Store: 47 services, 12 runbooks               ✓     │
├─────────────────────────────────────────────────────────────┤
│ Integrations:                                               │
│   • Kubernetes                                        ✓     │
│   • Prometheus                                        ✓     │
│   • Slack                                             ✓     │
│   • PagerDuty                                         ✓     │
╰─────────────────────────────────────────────────────────────╯
```

### 2. Test Investigation

```bash
autosre investigate "Test alert - high CPU usage"
```

### 3. Check API (if using Docker Compose/Helm)

```bash
curl http://localhost:8000/health
```

---

## Troubleshooting

### pip Installation Issues

**SSL Certificate Errors:**
```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org autosre
```

**Dependency Conflicts:**
```bash
pip install autosre --ignore-installed
```

### Docker Issues

**Permission Denied:**
```bash
# Add your user to the docker group
sudo usermod -aG docker $USER
# Log out and back in
```

**Kubernetes Access:**
```bash
# Mount your kubeconfig
docker run -it --rm \
  -v ~/.kube:/root/.kube:ro \
  ghcr.io/autosre/autosre:latest \
  autosre status
```

### Helm Issues

**Pending Pods:**
```bash
kubectl describe pod -n autosre <pod-name>
kubectl logs -n autosre <pod-name>
```

**Secret Not Found:**
```bash
kubectl get secrets -n autosre
kubectl describe secret -n autosre autosre-secrets
```

---

## Next Steps

- [Configure integrations →](configuration.md)
- [Run your first investigation →](quickstart.md)
- [Deploy to production →](../guides/kubernetes-deployment.md)
