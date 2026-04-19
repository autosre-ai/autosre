# Deployment

Production deployment guide for OpenSRE.

## Deployment Options

| Method | Best For |
|--------|----------|
| **Docker Compose** | Local development, small teams |
| **Kubernetes (Helm)** | Production, scalability |
| **Standalone** | Single-node deployments |

## Docker Compose

### Basic Deployment

```yaml
# docker-compose.yaml
version: '3.8'

services:
  opensre:
    image: ghcr.io/srisainath/opensre:latest
    ports:
      - "8000:8000"
    environment:
      - OPENSRE_PROMETHEUS_URL=http://prometheus:9090
      - OPENSRE_LLM_PROVIDER=ollama
      - OPENSRE_OLLAMA_HOST=http://ollama:11434
      - OPENSRE_SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
    volumes:
      - ./config:/app/config
      - ./runbooks:/app/runbooks
      - opensre_data:/app/data
      - ${HOME}/.kube/config:/app/.kube/config:ro
    depends_on:
      - ollama
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped

volumes:
  opensre_data:
  ollama_data:
```

### With Observability Stack

```yaml
# docker-compose.full.yaml
version: '3.8'

services:
  opensre:
    image: ghcr.io/srisainath/opensre:latest
    ports:
      - "8000:8000"
    environment:
      - OPENSRE_PROMETHEUS_URL=http://prometheus:9090
      - OPENSRE_LLM_PROVIDER=ollama
      - OPENSRE_OLLAMA_HOST=http://ollama:11434
    volumes:
      - ./config:/app/config
      - ./runbooks:/app/runbooks
      - opensre_data:/app/data
    depends_on:
      - prometheus
      - ollama
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped

volumes:
  opensre_data:
  prometheus_data:
  grafana_data:
  ollama_data:
```

### Running

```bash
# Start services
docker-compose up -d

# Pull Ollama model
docker exec -it ollama ollama pull llama3.1:8b

# Check logs
docker-compose logs -f opensre

# Stop services
docker-compose down
```

## Kubernetes (Helm)

### Prerequisites

- Kubernetes cluster 1.24+
- Helm 3.0+
- kubectl configured

### Installation

```bash
# Add Helm repository
helm repo add opensre https://srisainath.github.io/opensre
helm repo update

# Create namespace
kubectl create namespace opensre

# Create secrets
kubectl create secret generic opensre-secrets \
  --namespace opensre \
  --from-literal=slack-bot-token=$SLACK_BOT_TOKEN \
  --from-literal=openai-api-key=$OPENAI_API_KEY

# Install
helm install opensre opensre/opensre \
  --namespace opensre \
  --values values.yaml
```

### Values File

```yaml
# values.yaml
replicaCount: 2

image:
  repository: ghcr.io/srisainath/opensre
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8000

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: opensre.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: opensre-tls
      hosts:
        - opensre.example.com

config:
  llm:
    provider: openai
    model: gpt-4o
  
  prometheus:
    url: http://prometheus-server.monitoring:9090
  
  kubernetes:
    # Uses in-cluster config by default
    inCluster: true
  
  slack:
    channel: "#incidents"

secrets:
  existingSecret: opensre-secrets

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
  targetCPUUtilizationPercentage: 80

nodeSelector: {}

tolerations: []

affinity: {}

# Ollama sidecar (optional, for local LLM)
ollama:
  enabled: false
  image:
    repository: ollama/ollama
    tag: latest
  model: llama3.1:8b
  resources:
    requests:
      cpu: 1000m
      memory: 4Gi
    limits:
      cpu: 4000m
      memory: 8Gi
```

### Alertmanager Integration

Configure Alertmanager to send alerts to OpenSRE:

```yaml
# alertmanager.yaml
route:
  receiver: opensre
  routes:
    - match:
        severity: critical
      receiver: opensre
      continue: true

receivers:
  - name: opensre
    webhook_configs:
      - url: http://opensre.opensre.svc.cluster.local:8000/webhook/alertmanager
        send_resolved: true
```

## Standalone Deployment

### systemd Service

```ini
# /etc/systemd/system/opensre.service
[Unit]
Description=OpenSRE - AI-Powered Incident Response
After=network.target

[Service]
Type=simple
User=opensre
Group=opensre
WorkingDirectory=/opt/opensre
ExecStart=/opt/opensre/venv/bin/opensre start --foreground
Restart=on-failure
RestartSec=5
Environment=OPENSRE_CONFIG_PATH=/etc/opensre/config.yaml

[Install]
WantedBy=multi-user.target
```

### Installation

```bash
# Create user
sudo useradd -r -s /bin/false opensre

# Install OpenSRE
sudo mkdir -p /opt/opensre
sudo python -m venv /opt/opensre/venv
sudo /opt/opensre/venv/bin/pip install opensre

# Copy config
sudo mkdir -p /etc/opensre
sudo cp config.yaml /etc/opensre/

# Install and start service
sudo cp opensre.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable opensre
sudo systemctl start opensre
```

## Production Considerations

### High Availability

```yaml
# Helm values for HA
replicaCount: 3

affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchLabels:
              app: opensre
          topologyKey: kubernetes.io/hostname

# Use Redis for state coordination
config:
  redis:
    url: redis://redis-master:6379
```

### Database

For production, use PostgreSQL instead of SQLite:

```yaml
config:
  database:
    type: postgresql
    host: postgres.database.svc.cluster.local
    port: 5432
    database: opensre
    username: opensre
    passwordSecret:
      name: opensre-db
      key: password
```

### Monitoring

OpenSRE exposes Prometheus metrics:

```yaml
# ServiceMonitor for Prometheus Operator
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: opensre
spec:
  selector:
    matchLabels:
      app: opensre
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### Logging

Configure structured logging:

```yaml
config:
  logging:
    level: INFO
    format: json
    output: stdout
```

### Secrets Management

Use external secrets for sensitive data:

```yaml
# ExternalSecret (with external-secrets-operator)
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: opensre-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault
    kind: ClusterSecretStore
  target:
    name: opensre-secrets
  data:
    - secretKey: slack-bot-token
      remoteRef:
        key: opensre
        property: slack-bot-token
    - secretKey: openai-api-key
      remoteRef:
        key: opensre
        property: openai-api-key
```

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: opensre
spec:
  podSelector:
    matchLabels:
      app: opensre
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - protocol: TCP
          port: 8000
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - protocol: TCP
          port: 9090  # Prometheus
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - protocol: TCP
          port: 443  # External APIs (Slack, OpenAI)
```

## Upgrading

### Docker Compose

```bash
docker-compose pull
docker-compose up -d
```

### Helm

```bash
helm repo update
helm upgrade opensre opensre/opensre --namespace opensre --values values.yaml
```

### Database Migrations

```bash
opensre db migrate
```

## Troubleshooting

### Check Status

```bash
# Kubernetes
kubectl get pods -n opensre
kubectl logs -n opensre deployment/opensre

# Docker Compose
docker-compose ps
docker-compose logs opensre

# Standalone
systemctl status opensre
journalctl -u opensre -f
```

### Common Issues

**Pod CrashLoopBackOff:**
```bash
kubectl describe pod -n opensre <pod-name>
kubectl logs -n opensre <pod-name> --previous
```

**Connection Issues:**
```bash
# Test Prometheus
kubectl run test --rm -it --image=curlimages/curl -- \
  curl http://prometheus-server.monitoring:9090/-/healthy

# Test Slack
opensre test slack
```

**LLM Timeout:**
```yaml
config:
  llm:
    timeout: 120  # Increase timeout
```

## Next Steps

- **[Configuration](configuration.md)** — Configuration options
- **[API Reference](api-reference.md)** — API documentation
- **[Architecture](architecture.md)** — System design
