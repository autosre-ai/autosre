# OpenSRE Helm Chart

AI-Powered Incident Response for Kubernetes

## Introduction

This Helm chart deploys OpenSRE on a Kubernetes cluster. OpenSRE is an AI-powered SRE assistant that helps investigate and remediate incidents in your Kubernetes infrastructure.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- (Optional) Prometheus for metrics queries
- (Optional) Ollama or cloud LLM provider (Anthropic/OpenAI)
- (Optional) Slack workspace for notifications

## Installation

### Add the Helm repository (coming soon)

```bash
helm repo add opensre https://srisainath.github.io/opensre
helm repo update
```

### Install from local chart

```bash
cd opensre
helm install opensre ./charts/opensre \
  --namespace opensre \
  --create-namespace
```

### Install with custom values

```bash
helm install opensre ./charts/opensre \
  --namespace opensre \
  --create-namespace \
  -f my-values.yaml
```

## Configuration

The following table lists the configurable parameters of the OpenSRE chart and their default values.

### General

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `image.repository` | Image repository | `ghcr.io/srisainath/opensre` |
| `image.tag` | Image tag (defaults to appVersion) | `""` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `nameOverride` | Override the name of the chart | `""` |
| `fullnameOverride` | Override the fullname of the chart | `""` |

### Service Account & RBAC

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceAccount.create` | Create a service account | `true` |
| `serviceAccount.annotations` | Service account annotations | `{}` |
| `serviceAccount.name` | Service account name | `""` |
| `rbac.create` | Create RBAC resources | `true` |
| `rbac.namespaces` | Namespaces to watch (empty = all) | `[]` |

### LLM Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.llm.provider` | LLM provider (ollama/anthropic/openai) | `ollama` |
| `config.llm.ollamaHost` | Ollama service URL | `http://ollama:11434` |
| `config.llm.ollamaModel` | Ollama model to use | `llama3:8b` |

### Integrations

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.prometheus.url` | Prometheus URL | `http://prometheus:9090` |
| `config.slack.enabled` | Enable Slack notifications | `false` |
| `config.slack.channel` | Slack channel for incidents | `#incidents` |

### Security

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.security.requireApproval` | Require approval for remediation | `true` |
| `config.security.autoApproveLowRisk` | Auto-approve low-risk actions | `false` |
| `config.security.auditLogging` | Enable audit logging | `true` |

### Secrets

| Parameter | Description | Default |
|-----------|-------------|---------|
| `secrets.create` | Create a secret for API keys | `true` |
| `secrets.name` | Secret name | `opensre-secrets` |
| `secrets.slackBotToken` | Slack bot token | `""` |
| `secrets.anthropicApiKey` | Anthropic API key | `""` |
| `secrets.openaiApiKey` | OpenAI API key | `""` |

### Service & Ingress

| Parameter | Description | Default |
|-----------|-------------|---------|
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `8000` |
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.className` | Ingress class name | `""` |
| `ingress.hosts` | Ingress hosts | `[{host: opensre.local, paths: [{path: /, pathType: Prefix}]}]` |

### Resources & Scheduling

| Parameter | Description | Default |
|-----------|-------------|---------|
| `resources.limits.cpu` | CPU limit | `500m` |
| `resources.limits.memory` | Memory limit | `512Mi` |
| `resources.requests.cpu` | CPU request | `100m` |
| `resources.requests.memory` | Memory request | `256Mi` |
| `nodeSelector` | Node selector | `{}` |
| `tolerations` | Tolerations | `[]` |
| `affinity` | Affinity rules | `{}` |

### Monitoring

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceMonitor.enabled` | Create ServiceMonitor (requires Prometheus Operator) | `false` |
| `serviceMonitor.interval` | Scrape interval | `30s` |
| `serviceMonitor.labels` | Additional labels for ServiceMonitor | `{}` |

## Example Configurations

### Using Ollama (local LLM)

```yaml
config:
  llm:
    provider: ollama
    ollamaHost: http://ollama.ollama:11434
    ollamaModel: llama3:8b
```

### Using Anthropic Claude

```yaml
config:
  llm:
    provider: anthropic

secrets:
  anthropicApiKey: "sk-ant-..."
```

### With Slack Integration

```yaml
config:
  slack:
    enabled: true
    channel: "#sre-incidents"

secrets:
  slackBotToken: "xoxb-..."
```

### Production Configuration

```yaml
replicaCount: 2

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi

config:
  security:
    requireApproval: true
    auditLogging: true

serviceMonitor:
  enabled: true
  labels:
    release: prometheus
```

## Upgrading

```bash
helm upgrade opensre ./charts/opensre \
  --namespace opensre \
  -f my-values.yaml
```

## Uninstalling

```bash
helm uninstall opensre --namespace opensre
```

**Note:** This will not delete the namespace or any PVCs if created.

## RBAC Permissions

OpenSRE requires cluster-wide permissions for investigation and remediation:

**Read Access (Investigation):**
- Pods, Logs, Events, Services, ConfigMaps
- Deployments, ReplicaSets, StatefulSets, DaemonSets
- Jobs, CronJobs
- Ingresses, NetworkPolicies
- HorizontalPodAutoscalers
- Nodes, Namespaces

**Write Access (Remediation):**
- Deployments, StatefulSets (patch/update)
- Scale subresources (patch/update)
- Pods (delete for restarts)
- Pod evictions (create)

Review `templates/clusterrole.yaml` to understand and customize permissions.

## Troubleshooting

### Check pod status
```bash
kubectl get pods -n opensre -l app.kubernetes.io/name=opensre
```

### View logs
```bash
kubectl logs -n opensre -l app.kubernetes.io/name=opensre -f
```

### Check configuration
```bash
kubectl get configmap -n opensre opensre-config -o yaml
```

### Test connectivity to Prometheus
```bash
kubectl exec -n opensre deploy/opensre -- curl -s http://prometheus:9090/-/healthy
```

## Contributing

Issues and pull requests are welcome at https://github.com/srisainath/opensre

## License

Apache 2.0 - See LICENSE for details.
