# AutoSRE E2E Testing Plan

## Overview
Test AutoSRE against a real bookstore microservices app in a Kind cluster with full observability stack.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kind Cluster                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Frontend   │──│  API/Order  │──│  Database   │              │
│  │  (React)    │  │  (Node.js)  │  │  (Postgres) │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│         │                │                │                      │
│         └────────────────┴────────────────┘                      │
│                          │                                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Observability Stack                       ││
│  ├─────────────┬─────────────┬─────────────┬──────────────────┐││
│  │ Prometheus  │    Loki     │   Grafana   │ AlertManager     │││
│  │ (metrics)   │   (logs)    │   (viz)     │  (alerts)        │││
│  └─────────────┴─────────────┴─────────────┴──────────────────┘││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AutoSRE Agent                             │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Orchestrator → Triage → Investigate → Remediate → Report   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Test Scenarios

### Scenario 1: High Error Rate (500s)
- **Inject:** Break API endpoint (return 500s)
- **Expected:** AutoSRE detects via golden signals, identifies faulty deployment
- **Verify:** Root cause identified, mitigation suggested

### Scenario 2: Memory Leak / OOMKill
- **Inject:** Memory leak in order service
- **Expected:** AutoSRE detects OOMKilled pods, correlates with memory metrics
- **Verify:** Pod restart detected, memory pressure identified

### Scenario 3: Database Connection Pool Exhaustion
- **Inject:** Slow queries + connection leak
- **Expected:** AutoSRE traces connection pool saturation
- **Verify:** Database bottleneck identified

### Scenario 4: Cascading Failure
- **Inject:** Kill database, watch services cascade
- **Expected:** AutoSRE maps blast radius, identifies root cause
- **Verify:** Cascade pattern detected, recovery plan generated

### Scenario 5: Latency Spike (p99)
- **Inject:** Add artificial latency to API
- **Expected:** AutoSRE detects p99 spike via golden signals
- **Verify:** Latency increase quantified, source identified

### Scenario 6: Resource Contention (CPU Throttling)
- **Inject:** CPU-intensive workload + low limits
- **Expected:** AutoSRE detects CPU throttling
- **Verify:** Resource constraints identified

## Components to Install

1. **Kind Cluster** (autosre-e2e)
2. **Prometheus Stack** (kube-prometheus-stack helm chart)
3. **Loki** (logs)
4. **Bookstore App** (3 microservices)
5. **AutoSRE** (configured with cluster access)

## Directory Structure

```
e2e-testing/
├── E2E-PLAN.md
├── cluster/
│   ├── kind-config.yaml
│   └── setup.sh
├── observability/
│   ├── prometheus-values.yaml
│   ├── loki-values.yaml
│   └── install.sh
├── bookstore/
│   ├── frontend/
│   ├── api/
│   ├── database/
│   └── k8s/
├── chaos/
│   ├── high-error-rate.yaml
│   ├── memory-leak.yaml
│   ├── db-connection-exhaustion.yaml
│   ├── cascade-failure.yaml
│   ├── latency-spike.yaml
│   └── cpu-throttling.yaml
├── tests/
│   ├── run-all.sh
│   └── scenarios/
└── reports/
```

## Success Criteria

- [ ] All 6 scenarios detected correctly
- [ ] Root cause identified in each case
- [ ] Investigation time < 2 minutes per scenario
- [ ] Report generated with evidence
