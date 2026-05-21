# AutoSRE E2E Testing - Setup Complete

## ✅ Environment Status

### Kind Cluster: `autosre-e2e`
| Component | Status | Notes |
|-----------|--------|-------|
| Control Plane | ✅ Running | 1 node |
| Workers | ✅ Running | 2 nodes |
| Kubernetes | v1.35.0 | |

### Observability Stack (monitoring namespace)
| Component | Status | Access |
|-----------|--------|--------|
| Prometheus | ✅ Running | http://localhost:9090 |
| Grafana | ✅ Running | http://localhost:3000 (admin/admin) |
| Alertmanager | ✅ Running | Internal |
| Loki | ✅ Running | Via Grafana |
| Promtail | ✅ Running | 3 DaemonSet pods |
| Node Exporter | ✅ Running | 3 DaemonSet pods |

### Bookstore App (bookstore namespace)
| Component | Status | Replicas |
|-----------|--------|----------|
| bookstore-api | ✅ Running | 2 |
| postgres | ✅ Running | 1 |

## 📁 Files Created

```
e2e-testing/
├── E2E-PLAN.md
├── autosre-config.yaml
├── cluster/
│   ├── kind-config.yaml
│   └── setup.sh
├── observability/
│   ├── prometheus-values.yaml
│   ├── loki-values.yaml
│   ├── install.sh
│   └── bookstore-servicemonitor.yaml
├── bookstore/
│   ├── api/
│   │   ├── server.js
│   │   ├── package.json
│   │   └── Dockerfile
│   ├── database/
│   └── k8s/
│       ├── postgres.yaml
│       └── api.yaml
├── chaos/
│   ├── scenarios/
│   │   ├── scenario-1-high-error-rate.sh
│   │   ├── scenario-2-oom-kill.sh
│   │   ├── scenario-3-db-connection-exhaustion.sh
│   │   ├── scenario-4-cascade-failure.sh
│   │   ├── scenario-5-latency-spike.sh
│   │   └── scenario-6-cpu-throttling.sh
│   ├── run-scenario.sh
│   ├── reset-all.sh
│   ├── expected-outcomes.yaml
│   └── README.md
└── tests/
    ├── test_harness.py
    ├── test_e2e.py
    ├── generate_report.py
    └── run-all.sh
```

## 🧪 Test Scenarios

| # | Scenario | Injection Method | Expected Detection |
|---|----------|------------------|-------------------|
| 1 | High Error Rate | Kill pods / inject faults | Error rate spike in metrics |
| 2 | OOM Kill | Memory stress | OOMKilled events, restarts |
| 3 | DB Connection Exhaustion | Kill postgres | Connection timeouts |
| 4 | Cascading Failure | Delete postgres pod | Multi-service impact |
| 5 | Latency Spike | Network delay | p99 latency increase |
| 6 | CPU Throttling | CPU stress | Throttling metrics |

## 🚀 Quick Commands

```bash
# Context
kubectl config use-context kind-autosre-e2e

# Check status
kubectl get pods -n bookstore
kubectl get pods -n monitoring

# Access UIs
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80 &
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 &

# Access app
kubectl port-forward -n bookstore svc/bookstore-api 8080:80 &
curl http://localhost:8080/get

# Run chaos scenarios
cd ~/clawd/projects/autosre/e2e-testing/chaos
./run-scenario.sh 1  # High error rate

# Reset
./reset-all.sh

# Cleanup
kind delete cluster --name autosre-e2e
```

## 📊 Next Steps

1. Run chaos scenarios one by one
2. Trigger AutoSRE investigation for each
3. Verify detection and root cause analysis
4. Generate E2E report

---
*Setup completed: 2026-05-11*
