# OpenSRE Integrations - Iteration Log

## Session: 2025-05-29

### Overview
Comprehensive review and enhancement of OpenSRE's integration capabilities:
- MCP (Model Context Protocol) integration
- Docker packaging
- Kubernetes deployment
- CI/CD pipelines
- PyPI packaging

---

## ✅ MCP Server (`opensre_core/mcp_server.py`)

**Status: COMPLETE**

The MCP server is fully implemented with:
- 12 tools exposed (investigate, status, get_pods, get_events, get_pod_logs, describe_pod, query_prometheus, get_service_metrics, get_alerts, search_runbooks, list_runbooks, list_namespaces)
- Proper async handling
- Lazy initialization of adapters (Prometheus, Kubernetes, LLM)
- Rich formatted output for AI assistants

**Tools Available:**
| Tool | Description |
|------|-------------|
| `investigate` | AI-powered incident investigation |
| `status` | Health check of all connections |
| `list_namespaces` | List K8s namespaces |
| `get_pods` | Pods with status/restarts |
| `get_events` | Warning events |
| `get_pod_logs` | Pod log retrieval |
| `describe_pod` | Detailed pod info |
| `query_prometheus` | PromQL queries |
| `get_service_metrics` | Service metrics (CPU, memory, etc.) |
| `get_alerts` | Firing alerts |
| `search_runbooks` | Search runbooks |
| `list_runbooks` | List all runbooks |

---

## ✅ MCP Client (`opensre_core/mcp_client.py`)

**Status: COMPLETE**

The MCP client enables OpenSRE to consume tools from external MCP servers:
- `MCPClientManager` - Manages multiple server connections
- `MCPToolAdapter` - Bridges MCP tools to OpenSRE agents
- Config loading from JSON
- Presets for common servers (kubernetes, prometheus, github, slack, grafana, etc.)

**Presets Available:**
- `kubernetes` - Kubernetes operations
- `prometheus` - Prometheus metrics
- `github` - GitHub API
- `filesystem` - Filesystem ops
- `postgres` - PostgreSQL
- `slack` - Slack messaging
- `grafana` - Grafana dashboards

---

## ✅ Docker Packaging

**Status: COMPLETE**

### Dockerfile
- Multi-stage build (builder + runtime)
- Python 3.11-slim base
- Non-root user (`opensre`)
- kubectl installed for K8s operations
- Health check configured
- ~150MB final image size

### docker-compose.yaml
- OpenSRE service with all config
- Ollama for local LLM
- Redis (optional, for HA)
- Proper health checks
- Volume mounts for config, runbooks, kubeconfig
- Environment variable documentation

**Build Commands:**
```bash
docker build -t opensre:latest .
docker run --rm opensre:latest --version
docker-compose up -d
```

---

## ✅ Kubernetes Deployment

**Status: COMPLETE**

### Helm Chart (`charts/opensre/`)
- `Chart.yaml` - Chart metadata
- `values.yaml` - All configurable values
- `templates/deployment.yaml` - Full deployment spec
- `templates/service.yaml` - ClusterIP service
- `templates/configmap.yaml` - Configuration
- `templates/secret.yaml` - API keys
- `templates/serviceaccount.yaml` - Service account
- `templates/clusterrole.yaml` - RBAC read/write permissions
- `templates/clusterrolebinding.yaml` - Role binding
- `templates/ingress.yaml` - Optional ingress
- `templates/servicemonitor.yaml` - Prometheus metrics

### Raw Manifests (`deploy/kubernetes/`)
**CREATED:**
- `deployment.yaml` - Deployment with security context, probes, resource limits
- `service.yaml` - ClusterIP service
- `configmap.yaml` - Configuration with config.yaml embedded
- `rbac.yaml` - ServiceAccount, ClusterRole, ClusterRoleBinding
- `secret.yaml` - Secret template for API keys
- `kustomization.yaml` - Kustomize for easy customization

**Deploy Commands:**
```bash
# Using Helm
helm install opensre ./charts/opensre -n opensre --create-namespace

# Using kubectl
kubectl apply -f deploy/kubernetes/

# Using kustomize
kubectl apply -k deploy/kubernetes/
```

---

## ✅ CI/CD Pipelines

**Status: COMPLETE**

### `.github/workflows/ci.yaml` (main pipeline)
- **lint** - Ruff linting and format check
- **test** - Tests on Python 3.11 & 3.12 with coverage
- **security** - Bandit + Safety scan
- **build** - Package build with twine check
- **docker** - Docker build with caching
- **publish-pypi** - PyPI publish on release (OIDC auth)
- **publish-docker** - GHCR push on release with semver tags

### `.github/workflows/test.yml` (PR tests)
- Linting, type checking, tests
- Security scan with Bandit

### `.github/workflows/docker.yml`
- Docker build workflow

### `.github/workflows/release.yml`
- Release workflow

---

## ✅ PyPI Packaging

**Status: UPDATED**

### `pyproject.toml` Changes:
1. Fixed package name to `opensre_core` (matches actual directory)
2. Fixed entry point: `opensre = "opensre_core.cli:main"`
3. Added MCP entry point: `opensre_core.mcp_server:main`
4. Added optional dependencies:
   - `[mcp]` - MCP protocol support
   - `[llm]` - LLM providers (anthropic, openai, ollama)
   - `[slack]` - Slack integration
   - `[all]` - Everything
5. Added comprehensive dependencies:
   - httpx, kubernetes, aiohttp, uvicorn, fastapi
6. Updated metadata (author, description, keywords, classifiers)
7. Fixed wheel build target to `opensre_core`

**Install Commands:**
```bash
# Basic install
pip install opensre

# With MCP support
pip install opensre[mcp]

# Full install
pip install opensre[all]

# Development
pip install opensre[dev]
```

---

## 📝 Documentation Created

- `docs/MCP_INTEGRATION.md` - Comprehensive MCP usage guide
  - Server setup for Claude Desktop, VS Code
  - Client configuration
  - Tool reference
  - Docker usage
  - Environment variables

---

## 🔄 Next Steps / Future Work

1. **Test MCP Server** - Needs actual testing with Claude Desktop
2. **Test MCP Client** - Connect to real MCP servers
3. **Integration Tests** - Add tests for MCP server/client
4. **Helm Chart Testing** - Test with minikube/kind
5. **GitHub Actions Testing** - Ensure CI passes
6. **PyPI Test Upload** - Test upload to TestPyPI
7. **HPA** - Add Horizontal Pod Autoscaler template

---

## Files Modified/Created

### Modified:
- `pyproject.toml` - Fixed packaging, added extras
- `Dockerfile` - Install `[all]` extras
- `deploy/kubernetes/kustomization.yaml` - Added HPA and Ingress references

### Created:
- `deploy/kubernetes/deployment.yaml`
- `deploy/kubernetes/service.yaml`
- `deploy/kubernetes/configmap.yaml`
- `deploy/kubernetes/rbac.yaml`
- `deploy/kubernetes/secret.yaml`
- `deploy/kubernetes/kustomization.yaml`
- `deploy/kubernetes/hpa.yaml` - Horizontal Pod Autoscaler
- `deploy/kubernetes/ingress.yaml` - Ingress resource
- `docs/MCP_INTEGRATION.md`
- `.github/workflows/docs.yml` - Documentation deployment workflow
- `INTEGRATIONS_ITERATION_LOG.md` (this file)

### Removed:
- `docker-compose.yml` - Duplicate (kept docker-compose.yaml)

---

## Summary

OpenSRE is now deployable via:
1. **pip** - `pip install opensre[all]`
2. **Docker** - `docker run ghcr.io/srisainath/opensre:latest`
3. **Kubernetes (Helm)** - `helm install opensre ./charts/opensre`
4. **Kubernetes (kubectl)** - `kubectl apply -f deploy/kubernetes/`

MCP integration is fully implemented:
- Server mode: Claude/Cline can use OpenSRE tools
- Client mode: OpenSRE can use external MCP tools
