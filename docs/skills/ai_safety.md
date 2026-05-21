# AI Safety Features

AutoSRE implements comprehensive AI safety features to ensure reliable, trustworthy, and accountable AI-driven operations.

## Overview

AI-driven SRE introduces new risks:
- Incorrect diagnoses leading to wrong actions
- Automated actions causing harm
- Lack of transparency in decision-making
- Difficulty measuring AI performance

AutoSRE addresses these with structured safety mechanisms.

## Core Safety Principles

### 1. Hypothesis-Driven Investigation

All AI reasoning must follow a structured hypothesis format:

```python
from autosre.core import Hypothesis

hypothesis = Hypothesis(
    statement="Database connection pool exhaustion is causing request failures",
    confidence=0.85,
    evidence=[
        "Connection pool utilization at 98% (normal: <70%)",
        "Error logs show 'connection timeout' exceptions",
        "Correlation between pool exhaustion and error rate increase"
    ],
    falsifiable_criteria=[
        "Increasing pool size should reduce errors",
        "Errors should decrease when traffic decreases"
    ],
    risk_assessment={
        "if_correct": "Mitigation: increase pool size or reduce connections per pod",
        "if_incorrect": "Continue investigation with other hypotheses"
    }
)
```

### 2. Confidence Scoring

Every AI output includes explicit confidence:

```python
# Classification confidence
classification = await ai.classify_incident(alert)
print(f"Severity: {classification.severity}")
print(f"Confidence: {classification.confidence}")  # 0.0 - 1.0
print(f"Reasoning: {classification.reasoning}")

# Action confidence
action = await ai.recommend_action(incident)
print(f"Action: {action.name}")
print(f"Confidence: {action.confidence}")
print(f"Risk level: {action.risk_level}")
```

### 3. Human-in-the-Loop

Critical actions require human approval:

```python
from autosre.safety import ApprovalRequired

@ApprovalRequired(
    conditions=["destructive_action", "high_blast_radius", "low_confidence"]
)
async def scale_down_service(service: str, replicas: int):
    """Scale down requires approval if risky."""
    ...

# Usage - will pause for approval if conditions met
result = await scale_down_service("payment-service", 0)
# If risky: Awaiting human approval via Slack/PagerDuty...
```

## Configuration

```yaml
# config/autosre.yaml
ai_safety:
  confidence_threshold: 0.7
  
  require_human_approval_for:
    - destructive_actions
    - high_blast_radius
    - production_data_access
    - security_changes
    - cost_impacting
  
  hypothesis_format:
    require_confidence_score: true
    require_evidence: true
    require_falsifiable_criteria: true
  
  error_budget:
    high_severity_accuracy: 0.80
    safe_action_rate: 0.99
    root_cause_accuracy: 0.75
    calculation_window_days: 30
  
  telemetry:
    enabled: true
    track_confidence_correlation: true
    track_human_overrides: true
    prometheus_export: true
    metrics_prefix: "autosre_ai"
```

## AI Error Budgets

Just like service SLOs, AI systems have their own error budgets:

### Accuracy Targets

| Metric | Target | Description |
|--------|--------|-------------|
| High Severity Accuracy | 80% | Correctly identifying high-severity incidents |
| Safe Action Rate | 99% | Actions that don't cause harm |
| Root Cause Accuracy | 75% | Correctly identifying root cause |
| False Positive Rate | <10% | Alerts that aren't real incidents |

### Monitoring AI Performance

```python
from autosre.safety import AIErrorBudget

budget = AIErrorBudget()

# Get current AI accuracy
status = await budget.get_status()
print(f"High severity accuracy: {status.high_severity_accuracy}")
print(f"Safe action rate: {status.safe_action_rate}")
print(f"Budget remaining: {status.budget_remaining_percent}%")

# Check if AI should be more conservative
if status.budget_remaining_percent < 20:
    print("AI accuracy budget low - requiring more human oversight")
```

## Telemetry & Auditability

### Decision Tracking

Every AI decision is logged with full context:

```python
# Automatic telemetry for all AI decisions
{
    "timestamp": "2024-01-15T10:30:00Z",
    "decision_id": "dec_abc123",
    "type": "incident_classification",
    "input": {
        "alert_name": "HighErrorRate",
        "service": "payment-service",
        "metrics_snapshot": {...}
    },
    "output": {
        "severity": "high",
        "confidence": 0.85,
        "reasoning": "Error rate 5x normal, affecting checkout flow"
    },
    "model": "claude-3-sonnet",
    "latency_ms": 1250,
    "tokens_used": 1500
}
```

### Outcome Tracking

Track whether AI decisions were correct:

```python
# After incident resolution
await telemetry.record_outcome(
    decision_id="dec_abc123",
    outcome="correct",  # correct, incorrect, partially_correct
    human_feedback="Root cause was indeed connection pool exhaustion",
    actual_severity="high",
    resolution_time_minutes=25
)
```

### Confidence Calibration

Track if confidence scores are well-calibrated:

```python
# Get calibration report
calibration = await telemetry.get_calibration_report(window_days=30)

print(calibration)
# {
#   "confidence_buckets": {
#     "0.9-1.0": {"predictions": 50, "correct": 47, "accuracy": 0.94},
#     "0.8-0.9": {"predictions": 80, "correct": 68, "accuracy": 0.85},
#     "0.7-0.8": {"predictions": 60, "correct": 45, "accuracy": 0.75},
#     "0.6-0.7": {"predictions": 40, "correct": 26, "accuracy": 0.65}
#   },
#   "calibration_score": 0.92,  # 1.0 = perfectly calibrated
#   "recommendation": "Model is slightly overconfident in 0.8-0.9 range"
# }
```

## Approval Workflows

### Slack Integration

```python
# High-risk action triggers Slack approval
approval_request = await slack.request_approval(
    channel="#incident-response",
    action="Restart payment-service pods",
    reason="Suspected memory leak causing OOM crashes",
    confidence=0.75,
    risk_level="medium",
    blast_radius="10% of payment traffic",
    timeout_minutes=5
)

if approval_request.approved:
    await kubernetes.restart_pods("payment-service")
elif approval_request.rejected:
    log.info(f"Action rejected by {approval_request.rejected_by}: {approval_request.reason}")
else:  # Timeout
    log.warning("Approval timeout - escalating to on-call")
```

### PagerDuty Integration

```python
# Critical actions page for approval
await pagerduty.request_approval(
    policy="critical-actions",
    action="Scale down database replicas",
    urgency="high",
    details={
        "current_replicas": 5,
        "target_replicas": 2,
        "reason": "Cost optimization",
        "risk": "Reduced read capacity during scale-down"
    }
)
```

## Guardrails

### Action Blocklist

```yaml
# config/guardrails.yaml
blocked_actions:
  - pattern: "kubectl delete namespace production"
    reason: "Deleting production namespace is never allowed"
  
  - pattern: "DROP DATABASE"
    reason: "Database deletion requires manual intervention"
  
  - pattern: "scale.*replicas=0"
    services: ["payment-service", "auth-service"]
    reason: "Critical services cannot be scaled to zero"
```

### Blast Radius Limits

```python
# Automatic blast radius calculation and limiting
@BlastRadiusLimit(max_affected_percentage=0.30)
async def rolling_restart(service: str):
    """Restart limited to 30% of capacity at a time."""
    ...
```

### Rate Limiting

```python
# Limit AI actions per time window
@RateLimit(max_actions=10, window_minutes=60)
async def autonomous_remediation(incident_id: str):
    """Prevent runaway automation."""
    ...
```

## Metrics Exported

```promql
# AI decision metrics
autosre_ai_decisions_total{type="classification", outcome="correct"}
autosre_ai_decisions_total{type="classification", outcome="incorrect"}
autosre_ai_confidence_histogram{type="classification"}

# Accuracy metrics
autosre_ai_accuracy_ratio{metric="high_severity"}
autosre_ai_accuracy_ratio{metric="safe_action"}
autosre_ai_accuracy_ratio{metric="root_cause"}

# Human override metrics
autosre_ai_human_overrides_total{type="approved_corrected"}
autosre_ai_human_overrides_total{type="rejected"}

# Calibration metrics
autosre_ai_calibration_score
autosre_ai_overconfidence_rate
autosre_ai_underconfidence_rate

# Latency metrics
autosre_ai_decision_latency_seconds{type="classification"}
autosre_ai_decision_latency_seconds{type="recommendation"}
```

## Best Practices

### 1. Start Conservative

Begin with high confidence thresholds and extensive human oversight. Relax as you build trust.

```yaml
# Initial settings
ai_safety:
  confidence_threshold: 0.9  # High initially
  require_human_approval_for:
    - all_actions  # Everything needs approval at first
```

### 2. Track Everything

Every decision, every outcome, every override. This data is gold for improvement.

### 3. Regular Calibration Reviews

Weekly review AI accuracy metrics:
- Is the model well-calibrated?
- Where is it making mistakes?
- Should thresholds be adjusted?

### 4. Graceful Degradation

When AI confidence is low or error budget is exhausted, fall back to human judgment:

```python
if ai_budget.remaining < 0.10:
    log.warning("AI error budget low - switching to human-only mode")
    return await escalate_to_human(incident)
```

### 5. Feedback Loops

Make it easy for humans to provide feedback on AI decisions:

```python
# After every AI action
await slack.send_feedback_request(
    decision_id=decision.id,
    message=f"AI took action: {decision.action}. Was this correct?",
    buttons=["👍 Correct", "👎 Incorrect", "🤔 Partially Correct"]
)
```

## See Also

- [Investigation Phases](../operations/investigation_phases.md)
- [AI Telemetry Monitoring](../operations/ai_telemetry.md)
- [Error Budget Tracking](./error_budget.md)
