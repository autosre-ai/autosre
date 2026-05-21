# AutoSRE Helm Chart

AI SRE Agent for automated incident investigation.

## Introduction

This Helm chart deploys AutoSRE, an AI-powered SRE agent that automatically investigates production incidents. AutoSRE integrates with your observability stack (Prometheus, Grafana), alerting systems (PagerDuty, Slack), and Kubernetes to provide intelligent incident analysis.

## Prerequisites

- Kubernetes 1.25+
- Helm 3.10+
- PV provisioner support in the underlying infrastructure (for persistence)
- Ingress controller (optional, for external access)

## Installation

### Quick Start

```bash
# Add the AutoSRE Helm repository
helm repo add autosre https://autosre.io/charts
helm repo update

# Install with default configuration
helm install autosre autosre/autosre \
  --namespace autosre \
  --create-namespace
```

### Production Installation

```bash
# Create namespace
kubectl create namespace autosre

# Create secrets (recommended over values file)
kubectl create secret generic autosre-secrets \
  --namespace autosre \
  --from-literal=openai-api-key='sk-...' \
  --from-literal=database-password='your-db-password' \
  --from-literal=redis-password='your-redis-password' \
  --from-literal=neo4j-password='your-neo4j-password' \
  --from-literal=jwt-secret-key='your-jwt-secret' \
  --from-literal=encryption-key='your-32-byte-key'

# Install with production values
helm install autosre autosre/autosre \
  --namespace autosre \
  --values values-production.yaml \
  --set secrets.create=false \
  --set secrets.existingSecret=autosre-secrets
```

## Configuration

### Global Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.imagePullSecrets` | Image pull secrets for private registries | `[]` |
| `global.storageClass` | Storage class for persistent volumes | `""` |
| `commonLabels` | Labels to add to all resources | `{}` |
| `commonAnnotations` | Annotations to add to all resources | `{}` |

### Agent Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `agent.enabled` | Enable the agent component | `true` |
| `agent.replicaCount` | Number of agent replicas | `2` |
| `agent.image.repository` | Agent image repository | `autosre/agent` |
| `agent.image.tag` | Agent image tag | `""` (uses appVersion) |
| `agent.resources.limits.cpu` | CPU limit | `2000m` |
| `agent.resources.limits.memory` | Memory limit | `4Gi` |
| `agent.autoscaling.enabled` | Enable HPA | `false` |

### API Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `api.enabled` | Enable the API component | `true` |
| `api.replicaCount` | Number of API replicas | `3` |
| `api.image.repository` | API image repository | `autosre/api` |
| `api.port` | API container port | `8080` |
| `api.autoscaling.enabled` | Enable HPA | `true` |
| `api.autoscaling.minReplicas` | Minimum replicas | `3` |
| `api.autoscaling.maxReplicas` | Maximum replicas | `20` |

### Web Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `web.enabled` | Enable the web component | `true` |
| `web.replicaCount` | Number of web replicas | `2` |
| `web.image.repository` | Web image repository | `autosre/web` |
| `web.port` | Web container port | `3000` |

### Ingress Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.hosts[0].host` | Hostname | `autosre.local` |
| `ingress.tls` | TLS configuration | `[]` |

### Database Configuration

#### PostgreSQL (Bundled)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Enable PostgreSQL subchart | `true` |
| `postgresql.auth.username` | PostgreSQL username | `autosre` |
| `postgresql.auth.database` | PostgreSQL database | `autosre` |
| `postgresql.primary.persistence.size` | PVC size | `20Gi` |

#### External PostgreSQL

| Parameter | Description | Default |
|-----------|-------------|---------|
| `externalDatabase.host` | External PostgreSQL host | `""` |
| `externalDatabase.port` | External PostgreSQL port | `5432` |
| `externalDatabase.database` | Database name | `autosre` |
| `externalDatabase.username` | Username | `autosre` |
| `externalDatabase.existingSecret` | Existing secret with password | `""` |

### AI Provider Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.aiProvider` | AI provider (openai, anthropic, azure) | `openai` |
| `config.aiModel` | AI model to use | `gpt-4` |
| `secrets.openaiApiKey` | OpenAI API key | `""` |
| `secrets.anthropicApiKey` | Anthropic API key | `""` |
| `secrets.azureOpenaiApiKey` | Azure OpenAI API key | `""` |

### Integration Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.slackEnabled` | Enable Slack integration | `false` |
| `config.pagerdutyEnabled` | Enable PagerDuty integration | `false` |
| `config.prometheusEnabled` | Enable Prometheus integration | `true` |
| `config.prometheusUrl` | Prometheus URL | `http://prometheus:9090` |
| `config.kubernetesEnabled` | Enable Kubernetes integration | `true` |

## Examples

### Minimal Installation

```yaml
# values-minimal.yaml
agent:
  replicaCount: 1

api:
  replicaCount: 1
  autoscaling:
    enabled: false

web:
  replicaCount: 1
  autoscaling:
    enabled: false

postgresql:
  primary:
    persistence:
      size: 5Gi

redis:
  master:
    persistence:
      size: 1Gi

neo4j:
  volumes:
    data:
      defaultStorageClass:
        requests:
          storage: 5Gi
```

### Production with External Databases

```yaml
# values-production.yaml
postgresql:
  enabled: false

externalDatabase:
  host: prod-postgresql.example.com
  port: 5432
  database: autosre
  username: autosre
  existingSecret: autosre-db-credentials
  existingSecretKey: password

redis:
  enabled: false

externalRedis:
  host: prod-redis.example.com
  port: 6379
  existingSecret: autosre-redis-credentials
  existingSecretKey: password

neo4j:
  enabled: false

externalNeo4j:
  uri: bolt://prod-neo4j.example.com:7687
  username: neo4j
  existingSecret: autosre-neo4j-credentials
  existingSecretKey: password

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
  hosts:
    - host: autosre.example.com
      paths:
        - path: /api
          pathType: Prefix
          service: api
        - path: /
          pathType: Prefix
          service: web
  tls:
    - secretName: autosre-tls
      hosts:
        - autosre.example.com

secrets:
  create: false
  existingSecret: autosre-secrets
```

### With Slack and PagerDuty Integration

```yaml
# values-integrations.yaml
config:
  slackEnabled: true
  pagerdutyEnabled: true
  prometheusEnabled: true
  prometheusUrl: http://prometheus-operated:9090
  grafanaEnabled: true
  grafanaUrl: http://grafana:3000

secrets:
  slackBotToken: xoxb-your-token
  slackSigningSecret: your-signing-secret
  pagerdutyApiKey: your-pd-api-key
```

## Upgrading

### From 0.x to 1.x

```bash
# Backup data before upgrading
kubectl exec -n autosre autosre-postgresql-0 -- pg_dump -U autosre autosre > backup.sql

# Upgrade
helm upgrade autosre autosre/autosre \
  --namespace autosre \
  --values values.yaml
```

## Uninstallation

```bash
# Uninstall the release
helm uninstall autosre --namespace autosre

# Clean up PVCs (optional - WARNING: destroys data)
kubectl delete pvc -n autosre -l app.kubernetes.io/instance=autosre

# Delete namespace (optional)
kubectl delete namespace autosre
```

## Troubleshooting

### Check Pod Status

```bash
kubectl get pods -n autosre
kubectl describe pod -n autosre <pod-name>
kubectl logs -n autosre <pod-name>
```

### Run Helm Tests

```bash
helm test autosre -n autosre
```

### Check Secrets

```bash
kubectl get secrets -n autosre
kubectl describe secret -n autosre autosre
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
kubectl exec -n autosre -it deployment/autosre-api -- \
  psql -h autosre-postgresql -U autosre -d autosre -c "SELECT 1"

# Test Redis connection
kubectl exec -n autosre -it deployment/autosre-api -- \
  redis-cli -h autosre-redis-master ping
```

## Security Considerations

1. **Secrets Management**: Use external secrets management (Vault, AWS Secrets Manager, etc.) in production
2. **Network Policies**: Network policies are enabled by default to restrict traffic
3. **RBAC**: The chart creates minimal RBAC permissions required for operation
4. **Pod Security**: All pods run as non-root with read-only root filesystem

## Support

- Documentation: https://docs.autosre.io
- Issues: https://github.com/autosre/autosre/issues
- Slack: https://autosre.slack.com

## License

Copyright © 2024 AutoSRE

Licensed under the Apache License, Version 2.0.
