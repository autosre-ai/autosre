# AutoSRE V2 — Deployment Guide

## Overview

AutoSRE V2 supports multiple deployment modes:

| Mode | Use Case | Complexity |
|------|----------|------------|
| **All-in-One Docker** | Single developer, demos | ⭐ Easiest |
| **Docker Compose** | Local development, small teams | ⭐⭐ Easy |
| **Kubernetes (kubectl)** | Production, manual deployment | ⭐⭐⭐ Medium |
| **Helm** | Production, GitOps, enterprise | ⭐⭐⭐⭐ Advanced |

## Quick Start

### One-Liner Install

```bash
# Docker (recommended for getting started)
curl -fsSL https://raw.githubusercontent.com/your-org/autosre-v2/main/scripts/install.sh | bash

# All-in-one container
curl -fsSL https://raw.githubusercontent.com/your-org/autosre-v2/main/scripts/install.sh | bash -s -- --docker-aio

# Kubernetes
curl -fsSL https://raw.githubusercontent.com/your-org/autosre-v2/main/scripts/install.sh | bash -s -- --k8s

# Helm
curl -fsSL https://raw.githubusercontent.com/your-org/autosre-v2/main/scripts/install.sh | bash -s -- --helm
```

---

## MODE 1: Local Docker (for individuals)

### Prerequisites

- Docker 20.10+
- Docker Compose v2

### Using Docker Compose

```bash
# Clone the repository
git clone https://github.com/your-org/autosre-v2.git
cd autosre-v2

# Copy and configure environment
cp .env.example .env
vi .env  # Add your API keys

# Start all services
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

**Services:**
- UI: http://localhost:3000
- API: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Using All-in-One Container

For the simplest deployment (single container with SQLite):

```bash
docker run -d \
  --name autosre \
  -p 3000:3000 \
  -p 8000:8000 \
  -v autosre-data:/data \
  -e OPENAI_API_KEY=sk-... \
  ghcr.io/your-org/autosre:latest
```

---

## MODE 2: Kubernetes Enterprise

### Prerequisites

- Kubernetes 1.25+
- kubectl configured
- (Optional) Helm 3.x
- (Optional) cert-manager for TLS
- (Optional) Prometheus Operator for monitoring

### Using kubectl

```bash
# Create namespace and deploy
make k8s-deploy

# Or manually:
kubectl apply -f deploy/kubernetes/namespace.yaml
kubectl apply -f deploy/kubernetes/

# Check status
kubectl get pods -n autosre

# Port forward for testing
kubectl port-forward -n autosre svc/autosre-ui 3000:3000
kubectl port-forward -n autosre svc/autosre-api 8000:8000
```

### Using Helm

```bash
# Update dependencies
helm dependency update deploy/helm

# Install
helm install autosre deploy/helm \
  --namespace autosre \
  --create-namespace \
  --set postgresql.auth.password=secretpassword \
  --set secrets.secretKey=$(openssl rand -hex 32)

# Or with custom values file
helm install autosre deploy/helm \
  -f my-values.yaml \
  --namespace autosre \
  --create-namespace
```

### Production Values Example

Create `values-production.yaml`:

```yaml
api:
  replicas: 3
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 4
      memory: 4Gi

ui:
  replicas: 2

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: autosre.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
          service: ui
        - path: /api
          pathType: Prefix
          service: api
  tls:
    - secretName: autosre-tls
      hosts:
        - autosre.yourdomain.com

postgresql:
  enabled: false  # Use external database

externalDatabase:
  host: your-rds-endpoint.amazonaws.com
  existingSecret: autosre-db-secret
```

---

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AUTOSRE_SECRET_KEY` | JWT signing key | `openssl rand -hex 32` |
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://...` |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | LLM API key | `sk-...` |

### Optional Integrations

| Variable | Service |
|----------|---------|
| `SLACK_BOT_TOKEN` | Slack integration |
| `PAGERDUTY_API_KEY` | PagerDuty alerts |
| `GITHUB_TOKEN` | GitHub operations |
| `DATADOG_API_KEY` | Datadog monitoring |

See `.env.example` for all options.

---

## Makefile Commands

```bash
# Development
make dev           # Start local dev environment
make install       # Install dependencies
make test          # Run tests
make lint          # Run linters

# Docker
make docker-up     # Start Docker stack
make docker-down   # Stop Docker stack
make docker-logs   # Follow logs
make build         # Build images

# Kubernetes
make k8s-deploy    # Deploy to K8s
make k8s-delete    # Remove from K8s
make k8s-status    # Check status
make k8s-logs      # Follow logs

# Helm
make helm-install  # Install with Helm
make helm-template # Render templates
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Ingress                              │
│                    (nginx/ALB/etc)                          │
└─────────────────────┬───────────────────┬───────────────────┘
                      │                   │
              ┌───────▼───────┐   ┌───────▼───────┐
              │   autosre-ui  │   │  autosre-api  │
              │   (Next.js)   │   │  (FastAPI)    │
              │   Port 3000   │   │   Port 8000   │
              └───────────────┘   └───────┬───────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
            ┌───────▼───────┐     ┌───────▼───────┐     ┌───────▼───────┐
            │   PostgreSQL  │     │     Redis     │     │  Kubernetes   │
            │   (Storage)   │     │   (Cache)     │     │    (Target)   │
            └───────────────┘     └───────────────┘     └───────────────┘
```

---

## Monitoring

### Prometheus Metrics

The API exposes metrics at `/metrics`:

- `http_requests_total` — Request count by status
- `http_request_duration_seconds` — Request latency histogram
- `autosre_investigations_total` — Investigation count
- `autosre_remediation_total` — Remediation actions

### Grafana Dashboard

A pre-built dashboard is included in `deploy/kubernetes/servicemonitor.yaml`.

### Alerts

Pre-configured alerts for:
- API down
- High error rate (>5%)
- High latency (p95 > 2s)
- Pod restarts
- Memory pressure

---

## Security

### RBAC Permissions

By default, AutoSRE has **read-only** access to Kubernetes resources.

To enable write operations (remediation):

```yaml
# In Helm values
rbac:
  level: operator  # Instead of 'reader'
```

Or uncomment the operator ClusterRoleBinding in `deploy/kubernetes/rbac.yaml`.

### Network Policies

Enable network isolation:

```yaml
networkPolicy:
  enabled: true
  allowedNamespaces:
    - ingress-nginx
    - monitoring
```

---

## Troubleshooting

### Pods not starting

```bash
kubectl describe pod -n autosre <pod-name>
kubectl logs -n autosre <pod-name> --previous
```

### Database connection issues

```bash
# Check if PostgreSQL is ready
kubectl exec -it -n autosre autosre-postgres-0 -- pg_isready

# Test connection from API pod
kubectl exec -it -n autosre deploy/autosre-api -- \
  python -c "import asyncpg; asyncpg.connect('...')"
```

### Ingress not working

```bash
kubectl describe ingress -n autosre
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller
```

---

## Upgrading

### Docker Compose

```bash
git pull
make docker-rebuild
```

### Helm

```bash
helm upgrade autosre deploy/helm -n autosre --reuse-values
```

### Rollback

```bash
helm rollback autosre -n autosre
```

---

## Support

- Documentation: https://docs.autosre.dev
- Issues: https://github.com/your-org/autosre-v2/issues
- Discussions: https://github.com/your-org/autosre-v2/discussions
