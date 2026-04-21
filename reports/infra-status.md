# Infrastructure Status

**Last Updated:** 2026-04-21 23:10 IST

## Cluster Status
- **Kubernetes:** v1.35.0 (Kind cluster: opensre-demo)
- **Prometheus:** Running in monitoring namespace
- **Port Forward:** localhost:9090 → prometheus-kube-prometheus-prometheus

## OpenSRE Integration Status
| Service | Status | Details |
|---------|--------|---------|
| Prometheus | ✓ Connected | http://localhost:9090 |
| Kubernetes | ✓ Connected | K8s v1.35.0 |
| LLM | ✓ Connected | Ollama llama3:8b |

## Bookstore Namespace
All services running:
- catalog-service (2 replicas)
- checkout-service (1 replica)
- frontend (2 replicas)
- payment-service (1 replica)
- redis (1 replica)

## Notes
- Prometheus stack installed via Helm (kube-prometheus-stack)
- Port forwarding required for localhost access
