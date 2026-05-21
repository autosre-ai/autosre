# Investigation Phases Guide

AutoSRE uses a structured, phase-based approach to incident investigation. This guide explains how each phase works and how to configure the system.

## Overview

Every investigation progresses through four phases:

```
┌─────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐
│ TRIAGE  │──▶│ MITIGATE │──▶│ DIAGNOSE │──▶│ RESOLVE │
└─────────┘   └──────────┘   └──────────┘   └─────────┘
     │              │              │              │
  Required      Optional       Optional       Required
  (always)    (if needed)   (root cause)   (permanent)
```

## Why Phases?

Without structure, incident response becomes chaotic:
- Jumping to conclusions without understanding scope
- Spending time debugging while users suffer
- Missing the forest for the trees

Phases enforce discipline:
1. **Understand** before acting
2. **Stop bleeding** before diagnosing
3. **Find root cause** before fixing permanently

## Phase 1: TRIAGE (Required)

**Purpose**: Understand what's happening before taking action.

### Activities

- Assess scope and impact
- Classify severity
- Identify affected services/users
- Notify stakeholders
- Form initial hypotheses

### AI Behavior

```python
# During triage, AI focuses on assessment
triage_output = {
    "scope": {
        "affected_services": ["payment-service", "checkout-service"],
        "affected_users": "~15% of checkout traffic",
        "geographic_scope": "US-East region"
    },
    "severity": {
        "classification": "high",
        "confidence": 0.85,
        "reasoning": "Revenue-impacting, affecting significant user traffic"
    },
    "initial_hypotheses": [
        {
            "statement": "Database connection pool exhaustion",
            "confidence": 0.7,
            "evidence": ["Connection pool at 95%", "Timeout errors in logs"]
        },
        {
            "statement": "Upstream dependency failure",
            "confidence": 0.4,
            "evidence": ["inventory-service showing elevated errors"]
        }
    ]
}
```

### Transition Criteria

Triage completes when:
- Severity is classified
- Impact scope is understood
- Stakeholders are notified
- At least one hypothesis is formed

### Configuration

```yaml
investigation:
  phases:
    triage_required: true  # Cannot skip triage
    triage_timeout_minutes: 5  # Auto-escalate if triage takes too long
```

## Phase 2: MITIGATE (If Needed)

**Purpose**: Stop the bleeding. Reduce user impact, even with temporary fixes.

### Activities

- Apply quick fixes
- Redirect traffic (failover)
- Scale resources
- Enable rate limiting
- Restart stuck services

### AI Behavior

```python
# During mitigation, AI focuses on fast relief
mitigation_actions = [
    {
        "action": "scale_up",
        "target": "payment-service",
        "params": {"replicas": 10},
        "rationale": "Increase capacity to handle load",
        "risk": "low",
        "requires_approval": False
    },
    {
        "action": "enable_rate_limit",
        "target": "api-gateway",
        "params": {"rate": "1000/min", "path": "/checkout"},
        "rationale": "Protect downstream services",
        "risk": "medium",
        "requires_approval": True
    }
]
```

### Transition Criteria

Mitigation completes when:
- User impact is reduced or eliminated
- System is stable (even if degraded)
- Timeout reached (move to diagnose anyway)

### Configuration

```yaml
investigation:
  phases:
    mitigation_timeout_minutes: 15  # Don't spend forever mitigating
    auto_mitigation_enabled: true
    auto_mitigation_actions:
      - scale_up
      - restart_pods
      - enable_circuit_breaker
```

## Phase 3: DIAGNOSE (Root Cause)

**Purpose**: Find the root cause. Understand WHY, not just WHAT.

### Activities

- Gather evidence systematically
- Test hypotheses
- Correlate metrics and logs
- Build timeline of events
- Identify contributing factors

### AI Behavior

```python
# During diagnosis, AI follows hypothesis-driven investigation
diagnosis_process = {
    "active_hypotheses": [
        {
            "id": "h1",
            "statement": "Database connection pool exhaustion due to slow queries",
            "confidence": 0.75,
            "evidence_for": [
                "Slow query log shows 50+ queries >5s",
                "Connection pool hit 100% at incident start time"
            ],
            "evidence_against": [
                "Similar slow queries seen yesterday without issue"
            ],
            "tests_to_run": [
                "Compare query volume between today and yesterday",
                "Check if connection pool size was recently changed"
            ]
        }
    ],
    "invalidated_hypotheses": ["h2", "h3"],
    "timeline": [
        {"time": "10:00", "event": "Deploy of payment-service v2.3.4"},
        {"time": "10:05", "event": "Slow queries start appearing"},
        {"time": "10:10", "event": "Connection pool exhaustion"},
        {"time": "10:12", "event": "First user-visible errors"}
    ]
}
```

### Transition Criteria

Diagnosis completes when:
- Root cause is identified with high confidence
- Contributing factors are understood
- Timeline of events is clear

### Configuration

```yaml
investigation:
  phases:
    minimum_evidence_threshold: 3  # Need 3+ pieces of evidence
    parallel_hypothesis_testing: true
    max_concurrent_hypotheses: 5
```

## Phase 4: RESOLVE (Permanent Fix)

**Purpose**: Implement the permanent fix and verify resolution.

### Activities

- Implement fix (code change, config, infrastructure)
- Deploy fix
- Verify metrics return to normal
- Remove temporary mitigations
- Document resolution

### AI Behavior

```python
# During resolution, AI focuses on verification
resolution_status = {
    "fix_applied": {
        "type": "code_change",
        "description": "Optimized slow query with proper indexing",
        "deployed_at": "2024-01-15T11:30:00Z"
    },
    "verification": {
        "metrics_normalized": True,
        "error_rate": {"before": 5.2, "after": 0.01},
        "latency_p99": {"before": 2500, "after": 180},
        "user_reports": 0
    },
    "mitigations_removed": [
        "Removed rate limiting on /checkout",
        "Scaled payment-service back to 5 replicas"
    ]
}
```

### Transition Criteria

Resolution completes when:
- Permanent fix is deployed
- Metrics are verified normal
- Temporary mitigations are removed
- Stakeholders are informed

## Phase Transitions

### Automatic Transitions

AutoSRE can automatically transition phases based on criteria:

```yaml
investigation:
  phase_transitions:
    triage_to_mitigate:
      conditions:
        - severity_classified: true
        - impact_assessed: true
    
    mitigate_to_diagnose:
      conditions:
        - user_impact_reduced: true
      timeout_minutes: 15  # Or timeout
    
    diagnose_to_resolve:
      conditions:
        - root_cause_confidence: 0.8
        - evidence_count: 3
```

### Manual Overrides

Operators can always override phase transitions:

```bash
# Force transition to next phase
autosre investigation advance --id inc-123 --to diagnose

# Go back to previous phase
autosre investigation advance --id inc-123 --to triage --reason "New information"
```

## Parallel Activities

While phases are sequential, some activities run in parallel:

```
Phase Progress:    TRIAGE ─────▶ MITIGATE ─────▶ DIAGNOSE ─────▶ RESOLVE
                      │             │              │              │
Parallel:         ┌───┴───┐     ┌───┴───┐      ┌───┴───┐      ┌───┴───┐
                  │Notify │     │Monitor│      │Gather │      │Verify │
                  │Stake  │     │Impact │      │Evidence│     │Metrics│
                  │holders│     │Metrics│      │        │     │       │
                  └───────┘     └───────┘      └───────┘      └───────┘
```

## Metrics and Visibility

### Phase Duration Metrics

```promql
# Time spent in each phase
autosre_investigation_phase_duration_seconds{phase="triage"}
autosre_investigation_phase_duration_seconds{phase="mitigate"}
autosre_investigation_phase_duration_seconds{phase="diagnose"}
autosre_investigation_phase_duration_seconds{phase="resolve"}

# Phase transition counts
autosre_investigation_phase_transitions_total{from="triage", to="mitigate"}
```

### Dashboard Views

AutoSRE provides real-time visibility into investigation phases:

```
┌──────────────────────────────────────────────────────────────┐
│ Investigation: INC-2024-0115-001                              │
│ Status: DIAGNOSING | Duration: 25m | Severity: HIGH          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│ Phase Progress:                                               │
│ [████████████] TRIAGE     ✓ Complete (3m)                     │
│ [████████████] MITIGATE   ✓ Complete (8m)                     │
│ [████████░░░░] DIAGNOSE   ◐ In Progress (14m)                 │
│ [░░░░░░░░░░░░] RESOLVE    ○ Pending                           │
│                                                               │
│ Current Hypothesis:                                           │
│ "Database connection pool exhaustion" (75% confidence)        │
│                                                               │
│ Next Actions:                                                 │
│ • Compare query volume with baseline                          │
│ • Check recent config changes to connection pool              │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## Best Practices

### 1. Don't Skip Triage

Even for "obvious" incidents, triage ensures you don't miss scope:

```
❌ "I know it's the database, let me just restart it"
   → Missed that 3 other services were also affected

✓ "Let me assess scope first"
   → Discovered cascading failure, mitigated properly
```

### 2. Time-Box Mitigation

Don't spend forever mitigating. Set timeouts:

```yaml
investigation:
  phases:
    mitigation_timeout_minutes: 15
```

After timeout, move to diagnosis even if impact isn't fully mitigated.

### 3. Hypothesis Discipline

During diagnosis, maintain hypothesis discipline:

- State hypotheses explicitly
- List evidence for and against
- Define what would invalidate the hypothesis
- Don't chase red herrings

### 4. Verify Resolution

"It looks fixed" isn't enough. Verify with data:

- Metrics returned to baseline
- Error rates normal
- No new related alerts
- User reports stopped

## CLI Commands

```bash
# View current investigation phase
autosre investigation status --id inc-123

# View phase history
autosre investigation phases --id inc-123

# Advance to next phase
autosre investigation advance --id inc-123

# Force specific phase
autosre investigation advance --id inc-123 --to mitigate --reason "Need to stop bleeding"

# View phase durations
autosre investigation metrics --id inc-123
```

## See Also

- [AI Safety Features](../skills/ai_safety.md)
- [AI Telemetry Monitoring](./ai_telemetry.md)
- [Postmortem Workflow](./postmortem_workflow.md)
