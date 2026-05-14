# AutoSRE Helm Chart

![Version: 2.0.0](https://img.shields.io/badge/Version-2.0.0-informational?style=flat-square)
![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square)
![AppVersion: 2.0.0](https://img.shields.io/badge/AppVersion-2.0.0-informational?style=flat-square)

AI-Powered SRE Assistant for Kubernetes

## Prerequisites

- Kubernetes 1.23+
- Helm 3.8+
- PV provisioner support (for persistence)
- Prometheus Operator (optional, for ServiceMonitor)

## Installation

### Add Dependencies

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm dependency update
```

### Basic Installation

```bash
helm install autosre ./autosre \
  --namespace autosre \
  --create-namespace
```

### Production Installation

```bash
helm install autosre ./autosre \
  --namespace autosre \
  --create-namespace \
  --set secrets.openaiApiKey=your-api-key \
  --set secrets.jwtSecret=your-jwt-secret \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=autosre.example.com \
  --set serviceMonitor.enabled=true
```

### Using External Databases

```bash
helm install autosre ./autosre \
  --namespace autosre \
  --create-namespace \
  --set postgresql.enabled=false \
  --set externalPostgresql.host=your-postgres-host \
  --set externalPostgresql.password=your-password \
  --set redis.enabled=false \
  --set externalRedis.host=your-redis-host \
  --set externalRedis.password=your-redis-password
```

## Configuration

### Global Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.imagePullSecrets` | Image pull secrets | `[]` |
| `global.storageClass` | Storage class for PVs | `""` |
| `commonLabels` | Labels applied to all resources | `{}` |
| `commonAnnotations` | Annotations applied to all resources | `{}` |

### API Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `api.enabled` | Enable API deployment | `true` |
| `api.replicaCount` | Number of API replicas | `2` |
| `api.image.repository` | API image repository | `autosre/api` |
| `api.image.tag` | API image tag | `""` (uses appVersion) |
| `api.resources.limits.cpu` | CPU limit | `2` |
| `api.resources.limits.memory` | Memory limit | `2Gi` |
| `api.resources.requests.cpu` | CPU request | `500m` |
| `api.resources.requests.memory` | Memory request | `512Mi` |
| `api.service.type` | Service type | `ClusterIP` |
| `api.service.port` | Service port | `8080` |

### UI Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ui.enabled` | Enable UI deployment | `true` |
| `ui.replicaCount` | Number of UI replicas | `2` |
| `ui.image.repository` | UI image repository | `autosre/ui` |
| `ui.image.tag` | UI image tag | `""` (uses appVersion) |
| `ui.resources.limits.cpu` | CPU limit | `500m` |
| `ui.resources.limits.memory` | Memory limit | `256Mi` |
| `ui.service.type` | Service type | `ClusterIP` |
| `ui.service.port` | Service port | `80` |

### PostgreSQL Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Enable PostgreSQL subchart | `true` |
| `postgresql.auth.username` | PostgreSQL username | `autosre` |
| `postgresql.auth.password` | PostgreSQL password | `""` (auto-generated) |
| `postgresql.auth.database` | PostgreSQL database | `autosre` |
| `postgresql.primary.persistence.size` | PVC size | `10Gi` |

### External PostgreSQL Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `externalPostgresql.host` | External PostgreSQL host | `""` |
| `externalPostgresql.port` | External PostgreSQL port | `5432` |
| `externalPostgresql.database` | Database name | `autosre` |
| `externalPostgresql.username` | Username | `autosre` |
| `externalPostgresql.password` | Password | `""` |
| `externalPostgresql.existingSecret` | Existing secret name | `""` |
| `externalPostgresql.sslMode` | SSL mode | `require` |

### Redis Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Enable Redis subchart | `true` |
| `redis.architecture` | Redis architecture | `standalone` |
| `redis.auth.enabled` | Enable authentication | `true` |
| `redis.auth.password` | Redis password | `""` (auto-generated) |
| `redis.master.persistence.size` | PVC size | `5Gi` |

### External Redis Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `externalRedis.host` | External Redis host | `""` |
| `externalRedis.port` | External Redis port | `6379` |
| `externalRedis.password` | Password | `""` |
| `externalRedis.existingSecret` | Existing secret name | `""` |
| `externalRedis.tls` | Enable TLS | `false` |

### Ingress Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.annotations` | Ingress annotations | `{}` |
| `ingress.hosts` | Ingress hosts configuration | See values.yaml |
| `ingress.tls` | TLS configuration | `[]` |

### Application Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.logLevel` | Log level | `info` |
| `config.logFormat` | Log format | `json` |
| `config.aiProvider` | AI provider | `openai` |
| `config.aiModel` | AI model | `gpt-4` |
| `config.prometheusUrl` | Prometheus URL | `""` |
| `config.alertmanagerUrl` | Alertmanager URL | `""` |

### Secrets Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `secrets.openaiApiKey` | OpenAI API key | `""` |
| `secrets.anthropicApiKey` | Anthropic API key | `""` |
| `secrets.jwtSecret` | JWT signing secret | `""` (auto-generated) |
| `secrets.existingSecret` | Use existing secret | `""` |

### RBAC Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `rbac.create` | Create RBAC resources | `true` |
| `rbac.clusterWide` | Create ClusterRole | `false` |
| `rbac.allowedNamespaces` | Namespaces for Role | `[]` |
| `rbac.extraRules` | Additional RBAC rules | `[]` |

### Autoscaling Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `autoscaling.api.enabled` | Enable HPA for API | `false` |
| `autoscaling.api.minReplicas` | Minimum replicas | `2` |
| `autoscaling.api.maxReplicas` | Maximum replicas | `10` |
| `autoscaling.api.targetCPUUtilizationPercentage` | CPU target | `70` |
| `autoscaling.ui.enabled` | Enable HPA for UI | `false` |
| `autoscaling.ui.minReplicas` | Minimum replicas | `2` |
| `autoscaling.ui.maxReplicas` | Maximum replicas | `5` |

### Pod Disruption Budget

| Parameter | Description | Default |
|-----------|-------------|---------|
| `podDisruptionBudget.api.enabled` | Enable PDB for API | `true` |
| `podDisruptionBudget.api.minAvailable` | Minimum available | `1` |
| `podDisruptionBudget.ui.enabled` | Enable PDB for UI | `true` |
| `podDisruptionBudget.ui.minAvailable` | Minimum available | `1` |

### Monitoring Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceMonitor.enabled` | Enable ServiceMonitor | `false` |
| `serviceMonitor.namespace` | ServiceMonitor namespace | `""` |
| `serviceMonitor.interval` | Scrape interval | `30s` |
| `serviceMonitor.scrapeTimeout` | Scrape timeout | `10s` |

## Examples

### High Availability Setup

```yaml
api:
  replicaCount: 3
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchLabels:
              app.kubernetes.io/component: api
          topologyKey: kubernetes.io/hostname

ui:
  replicaCount: 3

autoscaling:
  api:
    enabled: true
    minReplicas: 3
    maxReplicas: 20

podDisruptionBudget:
  api:
    minAvailable: 2
  ui:
    minAvailable: 2
```

### Multi-Cluster Management

```yaml
rbac:
  create: true
  clusterWide: true

config:
  managedClusters:
    - production
    - staging
    - development
```

### Using Existing Secrets

```yaml
secrets:
  existingSecret: my-autosre-secrets

postgresql:
  auth:
    existingSecret: my-postgres-secret

redis:
  auth:
    existingSecret: my-redis-secret
```

### With Custom Prometheus

```yaml
config:
  prometheusUrl: http://prometheus.monitoring:9090
  alertmanagerUrl: http://alertmanager.monitoring:9093

serviceMonitor:
  enabled: true
  labels:
    release: prometheus
```

## Upgrading

### From 1.x to 2.x

1. Backup your data
2. Export current values: `helm get values autosre -n autosre > values-backup.yaml`
3. Review breaking changes in CHANGELOG.md
4. Upgrade: `helm upgrade autosre ./autosre -n autosre -f values-backup.yaml`

## Uninstallation

```bash
helm uninstall autosre -n autosre
```

**Note:** PVCs are not automatically deleted. To remove all data:

```bash
kubectl delete pvc -l app.kubernetes.io/instance=autosre -n autosre
```

## Troubleshooting

### Common Issues

1. **Pods stuck in Pending**: Check PVC provisioning and node resources
2. **Database connection errors**: Verify PostgreSQL credentials and network policies
3. **Redis connection errors**: Check Redis password and service endpoints

### Debug Commands

```bash
# Check pod status
kubectl get pods -n autosre -l app.kubernetes.io/instance=autosre

# View API logs
kubectl logs -f -l app.kubernetes.io/component=api -n autosre

# Check events
kubectl get events -n autosre --sort-by='.lastTimestamp'

# Describe deployment
kubectl describe deployment autosre-api -n autosre
```

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 - See [LICENSE](../../LICENSE) for details.
