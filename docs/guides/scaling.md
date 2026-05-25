# Scaling for Production

Best practices for running AutoSRE at scale.

## Architecture Overview

```
                    ┌─────────────┐
                    │   Load      │
                    │  Balancer   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │  AutoSRE    │ │  AutoSRE    │ │  AutoSRE    │
    │  Instance   │ │  Instance   │ │  Instance   │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────▼──────┐
                    │  PostgreSQL │
                    │   (Memory)  │
                    └─────────────┘
```

## Horizontal Scaling

### Multiple Replicas

AutoSRE supports horizontal scaling:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autosre
spec:
  replicas: 3
```

### Considerations

- Shared database for episodic memory
- Stateless request handling
- LLM API rate limits

## Resource Recommendations

| Scale | Replicas | Memory | CPU |
|-------|----------|--------|-----|
| Small (<100 alerts/day) | 1 | 512Mi | 250m |
| Medium (100-1000) | 2-3 | 1Gi | 500m |
| Large (1000+) | 5+ | 2Gi | 1000m |

## Database Scaling

### PostgreSQL

For production, use a managed PostgreSQL service:

```yaml
memory:
  backend: postgres
  connection_string: postgresql://user:pass@rds-endpoint:5432/autosre
```

Recommendations:

- Enable connection pooling (PgBouncer)
- Configure read replicas for memory lookups
- Regular backups

## Rate Limiting

### LLM API Limits

Configure rate limiting for LLM APIs:

```yaml
llm:
  rate_limit:
    requests_per_minute: 60
    retry_on_429: true
```

### Investigation Queue

For high volume, enable queuing:

```yaml
server:
  queue:
    enabled: true
    max_concurrent: 10
    redis_url: redis://redis:6379
```

## High Availability

### Multi-region

Deploy across regions for DR:

1. Deploy AutoSRE in each region
2. Use global database (CockroachDB, Spanner)
3. Configure regional failover

### Health Checks

Configure proper health checks:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Monitoring

### Prometheus Metrics

AutoSRE exports metrics at `/metrics`:

- `autosre_investigations_total` - Total investigations
- `autosre_investigation_duration_seconds` - Duration histogram
- `autosre_llm_tokens_total` - LLM token usage

### Recommended Alerts

```yaml
- alert: AutoSREHighLatency
  expr: histogram_quantile(0.95, autosre_investigation_duration_seconds) > 60
  for: 5m
  
- alert: AutoSREErrorRate
  expr: rate(autosre_investigations_total{status="error"}[5m]) > 0.1
```
