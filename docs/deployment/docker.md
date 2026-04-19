# Docker Deployment

Deploy OpenSRE using Docker or Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+ (optional)
- Access to Prometheus, Kubernetes, etc.

## Quick Start

### Single Container

```bash
docker run -d \
  --name opensre \
  -p 8000:8000 \
  -e OPENSRE_PROMETHEUS_URL=http://host.docker.internal:9090 \
  -e OPENSRE_LLM_PROVIDER=ollama \
  -e OPENSRE_OLLAMA_HOST=http://host.docker.internal:11434 \
  -e OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token \
  -v ~/.kube/config:/app/.kube/config:ro \
  ghcr.io/srisainath/opensre:latest
```

### Docker Compose

```yaml
# docker-compose.yaml
version: '3.8'

services:
  opensre:
    image: ghcr.io/srisainath/opensre:latest
    container_name: opensre
    ports:
      - "8000:8000"
    environment:
      # LLM Configuration
      OPENSRE_LLM_PROVIDER: ollama
      OPENSRE_OLLAMA_HOST: http://ollama:11434
      OPENSRE_OLLAMA_MODEL: llama3.1:8b
      
      # Prometheus
      OPENSRE_PROMETHEUS_URL: http://prometheus:9090
      
      # Slack
      OPENSRE_SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN}
      OPENSRE_SLACK_CHANNEL: "#incidents"
      
      # API
      OPENSRE_HOST: 0.0.0.0
      OPENSRE_PORT: 8000
      OPENSRE_API_KEY: ${API_KEY}
    volumes:
      # Kubernetes config (if accessing external cluster)
      - ~/.kube/config:/app/.kube/config:ro
      # Persistent data
      - opensre-data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      - ollama
    networks:
      - opensre-network

  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    volumes:
      - ollama-data:/root/.ollama
    ports:
      - "11434:11434"
    restart: unless-stopped
    networks:
      - opensre-network
    # GPU support (uncomment if available)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: all
    #           capabilities: [gpu]

volumes:
  opensre-data:
  ollama-data:

networks:
  opensre-network:
    driver: bridge
```

### Start the Stack

```bash
# Create .env file
cat > .env << EOF
SLACK_BOT_TOKEN=xoxb-your-token
API_KEY=$(openssl rand -hex 32)
EOF

# Start
docker-compose up -d

# Pull Ollama model
docker exec ollama ollama pull llama3.1:8b

# Check logs
docker-compose logs -f opensre
```

## Configuration

### Environment Variables

All OpenSRE configuration can be passed as environment variables:

```yaml
environment:
  # Core
  OPENSRE_LOG_LEVEL: INFO
  OPENSRE_CONFIG_PATH: /app/config/opensre.yaml
  
  # LLM
  OPENSRE_LLM_PROVIDER: ollama
  OPENSRE_OLLAMA_HOST: http://ollama:11434
  OPENSRE_OLLAMA_MODEL: llama3.1:8b
  
  # Prometheus
  OPENSRE_PROMETHEUS_URL: http://prometheus:9090
  
  # Kubernetes (in-cluster or external)
  OPENSRE_KUBECONFIG: /app/.kube/config
  
  # Slack
  OPENSRE_SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN}
  OPENSRE_SLACK_SIGNING_SECRET: ${SLACK_SIGNING_SECRET}
  
  # API
  OPENSRE_HOST: 0.0.0.0
  OPENSRE_PORT: 8000
  OPENSRE_API_KEY: ${API_KEY}
```

### Volume Mounts

```yaml
volumes:
  # Kubernetes config (external cluster)
  - ~/.kube/config:/app/.kube/config:ro
  
  # Custom config file
  - ./config/opensre.yaml:/app/config/opensre.yaml:ro
  
  # Custom skills
  - ./skills:/app/skills:ro
  
  # Custom agents
  - ./agents:/app/agents:ro
  
  # Runbooks
  - ./runbooks:/app/runbooks:ro
  
  # Persistent data (incidents, vectors)
  - opensre-data:/app/data
```

### Config File Mount

```yaml
# config/opensre.yaml
llm:
  provider: ollama
  ollama:
    host: http://ollama:11434
    model: llama3.1:8b

prometheus:
  url: http://prometheus:9090

slack:
  bot_token: ${OPENSRE_SLACK_BOT_TOKEN}
  channel: "#incidents"

safety:
  auto_approve:
    - "prometheus.*"
    - "kubernetes.get_*"
  require_approval:
    - "kubernetes.rollback"
    - "kubernetes.delete_*"
```

## Full Stack Example

Complete stack with observability:

```yaml
# docker-compose.full.yaml
version: '3.8'

services:
  opensre:
    image: ghcr.io/srisainath/opensre:latest
    container_name: opensre
    ports:
      - "8000:8000"
    environment:
      OPENSRE_LLM_PROVIDER: ollama
      OPENSRE_OLLAMA_HOST: http://ollama:11434
      OPENSRE_PROMETHEUS_URL: http://prometheus:9090
      OPENSRE_SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN}
    volumes:
      - ~/.kube/config:/app/.kube/config:ro
      - opensre-data:/app/data
    depends_on:
      - ollama
      - prometheus
    networks:
      - opensre-network
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    volumes:
      - ollama-data:/root/.ollama
    ports:
      - "11434:11434"
    networks:
      - opensre-network
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - opensre-network
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
    networks:
      - opensre-network
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    networks:
      - opensre-network
    restart: unless-stopped

volumes:
  opensre-data:
  ollama-data:
  prometheus-data:
  grafana-data:

networks:
  opensre-network:
    driver: bridge
```

### Alertmanager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: opensre
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: opensre
    webhook_configs:
      - url: http://opensre:8000/webhook/alertmanager
        send_resolved: true
```

## Production Considerations

### Health Checks

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

### Resource Limits

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

### Logging

```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

### Security

```yaml
security_opt:
  - no-new-privileges:true
read_only: true
tmpfs:
  - /tmp
```

## GPU Support (Ollama)

### NVIDIA GPU

```yaml
ollama:
  image: ollama/ollama:latest
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

Requires:
- NVIDIA drivers
- nvidia-container-toolkit
- Docker configured for GPU support

### Verify GPU

```bash
docker exec ollama nvidia-smi
```

## Networking

### Accessing Host Services

Use `host.docker.internal` to access services on the host:

```yaml
environment:
  OPENSRE_PROMETHEUS_URL: http://host.docker.internal:9090
  OPENSRE_OLLAMA_HOST: http://host.docker.internal:11434
```

### Exposing Webhooks

For external webhook access (Alertmanager, PagerDuty), expose port:

```yaml
ports:
  - "8000:8000"
```

Or use reverse proxy (nginx, traefik).

## Building Custom Image

```dockerfile
# Dockerfile.custom
FROM ghcr.io/srisainath/opensre:latest

# Add custom skills
COPY ./my-skills /app/skills/

# Add custom agents
COPY ./my-agents /app/agents/

# Add runbooks
COPY ./runbooks /app/runbooks/

# Custom config
COPY ./config/opensre.yaml /app/config/opensre.yaml
```

Build and run:

```bash
docker build -t my-opensre -f Dockerfile.custom .
docker run -d my-opensre
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs opensre

# Check config
docker exec opensre opensre config validate
```

### Can't Connect to Prometheus

```bash
# Test from container
docker exec opensre curl http://prometheus:9090/-/healthy

# Check network
docker network inspect opensre-network
```

### Ollama Model Not Loading

```bash
# Check Ollama
docker exec ollama ollama list

# Pull model
docker exec ollama ollama pull llama3.1:8b
```

## See Also

- [Kubernetes Deployment](kubernetes.md)
- [Configuration](../CONFIGURATION.md)
- [Troubleshooting](../troubleshooting.md)
