# Fault Scenario Test Results

**Test Started:** 2026-04-21 23:24 IST
**Test Runner:** Fault Runner v2

## Summary
| Scenario | Detection | Analysis | Remediation | Status |
|----------|-----------|----------|-------------|--------|
| crash-loop | ✅ Yes | 96% confidence | Fix Redis image, restart pods | ✅ PASSED |
| memory-leak | 🔄 Testing | - | - | In progress |
| high-latency | 🔄 Pending | - | - | Not started |
| oom-kill | 🔄 Pending | - | - | Not started |
| cpu-spike | 🔄 Pending | - | - | Not started |

---

## Test Details

### 1. Crash Loop (crash-loop.yaml)
**Target:** payment-service  
**Demo Scenario:** 4 (Pod Crash Loop)  
**Status:** ✅ PASSED

**Alert Detected:**
- Status: CrashLoopBackOff (all replicas)
- Restarts: 12 (last 5 min)
- Exit Code: 1 (application error)
- Impact: Service degraded (50% capacity)

**Signals Collected:**
- kubernetes: Pod in CrashLoopBackOff
- logs: Exception: Failed to connect to Redis at redis:6379
- kubernetes: Redis pod status: ImagePullBackOff
- events: Failed to pull image: redis:7.2 - not found

**AI Analysis:**
- 🎯 ROOT CAUSE: Cascading failure - Redis image pull failure causing catalog-service crash loops due to missing dependency
- 📊 CONFIDENCE: 96%
- ⚡ IMMEDIATE ACTION: Fix Redis image using `kubectl set image statefulset/redis redis=redis:7.0`
- 🔍 FOLLOW-UP: Investigate image availability, pin versions, add alerting

---

### 2. Memory Leak (memory-leak.yaml)
**Target:** catalog-service  
**Demo Scenario:** 1 (Memory Leak After Deployment)  
**Status:** 🔄 In Progress

---

### 3. High Latency (high-latency.yaml)
**Target:** checkout-service  
**Demo Scenario:** 2 (Database Connection Pool Exhaustion)  
**Status:** 🔄 Pending

---

### 4. OOM Kill (oom-kill.yaml)
**Target:** catalog-service  
**Demo Scenario:** 1 (Memory Leak - similar)  
**Status:** 🔄 Pending

---

### 5. CPU Spike (cpu-spike.yaml)
**Target:** frontend  
**Demo Scenario:** 5 (CPU Spike Under Load)  
**Status:** 🔄 Pending

---

## Bugs Found
None yet.

## Recommendations
TBD after testing.
