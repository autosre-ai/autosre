# Fault Scenario Test Results

**Test Started:** 2026-04-21 23:10 IST
**Last Updated:** 2026-04-21 23:30 IST

## Summary
| Scenario | Detection | Analysis | Remediation | Status |
|----------|-----------|----------|-------------|--------|
| crash-loop | ✅ Detected | ✅ Working | ⏳ Pending | **ACTIVE** |
| memory-leak | 🔄 Next | - | - | Pending |
| high-latency | ✅ Deployed | ⏳ Pending | - | Deployed |
| oom-kill | 🔄 Queued | - | - | Not started |
| cpu-spike | 🔄 Queued | - | - | Not started |

---

## Test Details

### 1. Crash Loop (crash-loop.yaml)
**Target:** payment-service
**Status:** ✅ DETECTED

**Kubernetes Detection:**
- Pod `payment-service-crashloop-6b7d9f7fc4-wwgpm` in CrashLoopBackOff
- 5 restarts recorded
- OpenSRE Kubernetes adapter successfully detected the pod

**Prometheus Detection:**
- `kube_pod_container_status_restarts_total{pod=~".*crashloop.*"}` = 4 restarts
- Metrics being scraped correctly

**Demo Test (Mock Mode):**
```
✓ PASS - Scenario 4 (Pod Crash Loop) 
- Root cause identified: Cascading failure
- Confidence: 96%
- Remediation suggested: Fix Redis image
```

---

### 2. Memory Leak (memory-leak.yaml)
**Target:** catalog-service
**Status:** Next to test

---

### 3. High Latency (high-latency.yaml)
**Target:** checkout-service
**Status:** ✅ Deployed (checkout-service-high-latency pod running)

---

### 4. OOM Kill (oom-kill.yaml)
**Target:** catalog-service
**Status:** Queued

---

### 5. CPU Spike (cpu-spike.yaml)
**Target:** frontend
**Status:** Queued

---

## Infrastructure Status
- ✅ Prometheus: 9090 port-forwarded
- ✅ Grafana: 3000 port-forwarded
- ✅ Alertmanager: Running
- ✅ kube-state-metrics: Providing pod metrics
- ✅ ServiceMonitors: Created for all bookstore services

## Bugs Found
None so far.

## Recommendations
1. Run memory-leak scenario next
2. Test real LLM analysis (not just mock)
3. Verify remediation commands work
