# Fault Scenario Test Results

**Test Started:** 2026-04-21 23:10 IST
**Last Updated:** 2026-04-21 23:47 IST

## Summary
| Scenario | Detection | Analysis | Remediation | Status |
|----------|-----------|----------|-------------|--------|
| crash-loop | ✅ Observations correct | ❌ "No issues detected" | ❌ Generic actions | **BUG** |
| memory-leak | ⚠️ Port-forward died | N/A | N/A | Retry needed |
| high-latency | 🔄 Pending | - | - | Not started |
| oom-kill | 🔄 Pending | - | - | Not started |
| cpu-spike | 🔄 Pending | - | - | Not started |

---

## Test Details

### 1. Crash Loop (crash-loop.yaml)
**Target:** payment-service
**Status:** ❌ FAILED - BUG IDENTIFIED

**Observations Collected:**
- ✅ Pod restarts detected (4 restarts)
- ✅ Readiness probe failures detected
- ✅ Liveness probe failures detected
- ✅ Pods shown as not ready

**Root Cause Analysis:**
- ❌ LLM returned "No issues detected" with 100% confidence
- This is WRONG - observations clearly showed problems

**BUG:** The LLM is not properly interpreting observations with actual problems.
The reasoner prompt says "healthy = no issues" but isn't recognizing unhealthy signals.

**Next Steps:**
- Review and fix the reasoner prompt to properly weigh crash/restart signals
- Test with better prompt engineering

---

### 2. Memory Leak (memory-leak.yaml)
**Target:** catalog-service
**Status:** ⚠️ NEEDS RETRY

**Notes:**
- Port-forward died mid-investigation
- Memory leak pods reached 134MB/130MB (limit: 128MB)
- Need to retry with stable port-forward

---

### 3. High Latency (high-latency.yaml)
**Target:** checkout-service
**Status:** Not started

---

### 4. OOM Kill (oom-kill.yaml)
**Target:** catalog-service
**Status:** Not started

---

### 5. CPU Spike (cpu-spike.yaml)
**Target:** frontend
**Status:** Not started

---

## Bugs Found

### BUG-001: LLM says "No issues detected" despite clear problem signals
**Severity:** HIGH
**Component:** `opensre_core/agents/reason.py` / prompts
**Description:** When observations include crash loop restarts, probe failures, and unhealthy pods, the LLM still returns "No issues detected" with 100% confidence.
**Root Cause:** The reasoner prompt's logic for "healthy systems" is being triggered incorrectly.
**Fix Needed:** Improve prompt to explicitly check for:
- restarts > 0
- ready=False
- probe failures
- CrashLoopBackOff status

---

## Recommendations
1. Fix BUG-001 before continuing tests
2. Add a health-check wrapper to keep port-forward alive
3. Add explicit "anomaly detection" in observer that flags issues before LLM
