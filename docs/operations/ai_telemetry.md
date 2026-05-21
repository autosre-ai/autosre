# AI Telemetry Monitoring Guide

This guide explains how to monitor AutoSRE's AI performance, ensuring the system makes accurate and safe decisions.

## Overview

AI-driven SRE introduces new monitoring requirements. We need to track:

- **Accuracy**: Is the AI making correct decisions?
- **Calibration**: Do confidence scores reflect reality?
- **Safety**: Are autonomous actions safe?
- **Performance**: How fast is the AI responding?

## Key Metrics

### Decision Accuracy

```promql
# Overall AI accuracy (correct decisions / total decisions)
sum(autosre_ai_decisions_total{outcome="correct"}) 
/ 
sum(autosre_ai_decisions_total)

# Accuracy by decision type
sum(autosre_ai_decisions_total{outcome="correct"}) by (type)
/
sum(autosre_ai_decisions_total) by (type)

# High-severity classification accuracy (critical SLO)
sum(autosre_ai_decisions_total{type="severity_classification", actual_severity="high", predicted_severity="high"})
/
sum(autosre_ai_decisions_total{type="severity_classification", actual_severity="high"})
```

### Confidence Calibration

```promql
# Average confidence for correct vs incorrect decisions
avg(autosre_ai_confidence{outcome="correct"}) # Should be high
avg(autosre_ai_confidence{outcome="incorrect"}) # Should be low

# Overconfidence rate (high confidence but wrong)
sum(autosre_ai_decisions_total{confidence_bucket="0.8-1.0", outcome="incorrect"})
/
sum(autosre_ai_decisions_total{confidence_bucket="0.8-1.0"})
```

### Safety Metrics

```promql
# Safe action rate (actions that didn't cause harm)
sum(autosre_ai_actions_total{outcome="safe"})
/
sum(autosre_ai_actions_total)

# Human override rate
sum(autosre_ai_human_overrides_total)
/
sum(autosre_ai_decisions_total{requires_approval="true"})

# Autonomous action outcomes
sum(autosre_ai_actions_total{autonomous="true"}) by (outcome)
```

### Performance Metrics

```promql
# AI decision latency
histogram_quantile(0.99, autosre_ai_decision_latency_seconds_bucket)

# Token usage
sum(rate(autosre_ai_tokens_total[1h])) by (model)

# Cost estimation
sum(rate(autosre_ai_tokens_total{type="input"}[1h])) * 0.000003  # Example pricing
+ 
sum(rate(autosre_ai_tokens_total{type="output"}[1h])) * 0.000015
```

## Dashboard Setup

### AI Health Overview Dashboard

```json
{
  "title": "AutoSRE AI Health",
  "panels": [
    {
      "title": "AI Accuracy (7d rolling)",
      "type": "gauge",
      "query": "sum(autosre_ai_decisions_total{outcome='correct'}[7d]) / sum(autosre_ai_decisions_total[7d])",
      "thresholds": [0.7, 0.8, 0.9]
    },
    {
      "title": "Safe Action Rate",
      "type": "gauge", 
      "query": "sum(autosre_ai_actions_total{outcome='safe'}[7d]) / sum(autosre_ai_actions_total[7d])",
      "thresholds": [0.95, 0.99]
    },
    {
      "title": "Decision Types",
      "type": "pie",
      "query": "sum(autosre_ai_decisions_total) by (type)"
    },
    {
      "title": "Accuracy Trend",
      "type": "timeseries",
      "query": "sum(rate(autosre_ai_decisions_total{outcome='correct'}[1d])) / sum(rate(autosre_ai_decisions_total[1d]))"
    }
  ]
}
```

### Confidence Calibration Dashboard

```json
{
  "title": "AI Confidence Calibration",
  "panels": [
    {
      "title": "Calibration Curve",
      "type": "scatter",
      "description": "X: Confidence, Y: Actual Accuracy. Perfect = diagonal line",
      "query": "autosre_ai_calibration_by_bucket"
    },
    {
      "title": "Overconfidence Rate",
      "type": "stat",
      "query": "autosre_ai_overconfidence_rate"
    },
    {
      "title": "Confidence Distribution",
      "type": "histogram",
      "query": "autosre_ai_confidence_histogram"
    }
  ]
}
```

## Alerting Rules

### Critical Alerts

```yaml
# Prometheus alerting rules
groups:
  - name: autosre-ai-critical
    rules:
      - alert: AIAccuracyLow
        expr: |
          sum(autosre_ai_decisions_total{outcome="correct"}[24h]) 
          / sum(autosre_ai_decisions_total[24h]) < 0.7
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "AI accuracy dropped below 70%"
          description: "Consider increasing human oversight"

      - alert: AIUnsafeActions
        expr: |
          sum(autosre_ai_actions_total{outcome="harmful"}[1h]) > 0
        labels:
          severity: critical
        annotations:
          summary: "AI took harmful action"
          description: "Immediate review required"

      - alert: AIErrorBudgetExhausted
        expr: autosre_ai_error_budget_remaining_ratio < 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "AI error budget nearly exhausted"
          description: "Switching to human-only mode recommended"
```

### Warning Alerts

```yaml
groups:
  - name: autosre-ai-warnings
    rules:
      - alert: AIOverconfident
        expr: autosre_ai_overconfidence_rate > 0.2
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "AI is overconfident (20%+ high-confidence mistakes)"

      - alert: AIHighOverrideRate
        expr: |
          sum(autosre_ai_human_overrides_total[24h]) 
          / sum(autosre_ai_decisions_total{requires_approval="true"}[24h]) > 0.5
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Humans overriding AI decisions frequently"

      - alert: AILatencyHigh
        expr: histogram_quantile(0.99, autosre_ai_decision_latency_seconds_bucket) > 30
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "AI decision latency exceeding 30s"
```

## Telemetry Collection

### What We Track

Every AI decision is recorded with:

```python
telemetry_record = {
    # Decision metadata
    "decision_id": "dec_abc123",
    "timestamp": "2024-01-15T10:30:00Z",
    "type": "severity_classification",
    
    # Input context
    "input": {
        "alert_name": "HighErrorRate",
        "service": "payment-service",
        "metrics": {"error_rate": 0.05, "latency_p99": 2500}
    },
    
    # AI output
    "output": {
        "severity": "high",
        "confidence": 0.85,
        "reasoning": "Error rate 5x normal, latency degraded"
    },
    
    # Model info
    "model": "claude-3-sonnet",
    "prompt_tokens": 1200,
    "completion_tokens": 300,
    "latency_ms": 2500,
    
    # Outcome (filled later)
    "outcome": "correct",  # correct, incorrect, partially_correct, pending
    "human_feedback": "Classification was accurate",
    "actual_severity": "high"
}
```

### Outcome Recording

Outcomes are recorded after incidents resolve:

```python
# Automatic outcome inference
if incident.resolved:
    actual_severity = calculate_actual_severity(incident)
    for decision in incident.ai_decisions:
        decision.record_outcome(
            predicted=decision.output.severity,
            actual=actual_severity
        )

# Manual feedback
await telemetry.record_feedback(
    decision_id="dec_abc123",
    feedback="correct",
    notes="AI correctly identified database issue"
)
```

## Calibration Analysis

### Understanding Calibration

A well-calibrated AI means:
- When it says 90% confident → it's right 90% of the time
- When it says 70% confident → it's right 70% of the time

### Calibration Report

```python
# Generate calibration report
report = await telemetry.calibration_report(window_days=30)

print(report)
# {
#   "buckets": {
#     "0.9-1.0": {"count": 100, "accuracy": 0.94},  # Good
#     "0.8-0.9": {"count": 150, "accuracy": 0.78},  # Overconfident!
#     "0.7-0.8": {"count": 120, "accuracy": 0.73},  # Good
#     "0.6-0.7": {"count": 80, "accuracy": 0.61},   # Good
#   },
#   "overall_calibration": 0.89,
#   "recommendation": "Model overconfident in 0.8-0.9 range. Consider threshold adjustment."
# }
```

### Calibration Actions

When calibration is poor:

1. **Overconfident**: Lower confidence threshold for human approval
2. **Underconfident**: Model may need fine-tuning or better prompts
3. **Inconsistent**: Add more context to prompts

## Error Budget for AI

### AI Error Budget Concept

Just like services have SLOs, AI has accuracy targets:

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| High Severity Accuracy | 80% | 85% | ✓ Healthy |
| Safe Action Rate | 99% | 99.5% | ✓ Healthy |
| Root Cause Accuracy | 75% | 72% | ⚠ Warning |

### Budget Calculation

```python
# AI error budget remaining
error_budget = await ai_budget.get_status()

print(error_budget)
# {
#   "high_severity_accuracy": {
#     "target": 0.80,
#     "current": 0.85,
#     "budget_remaining": 1.0  # Above target = 100%
#   },
#   "safe_action_rate": {
#     "target": 0.99,
#     "current": 0.995,
#     "budget_remaining": 0.83  # Using some of the 1% budget
#   },
#   "overall_status": "healthy"
# }
```

### Budget Exhaustion Actions

When AI error budget is low:

```yaml
ai_safety:
  error_budget:
    exhaustion_actions:
      # When accuracy drops
      - increase_confidence_threshold: 0.9
      - require_approval_for_all: true
      - notify_team: true
      
      # When severely degraded
      - disable_autonomous_actions: true
      - human_only_mode: true
```

## Investigation Tools

### Decision Audit

```bash
# View all AI decisions for an incident
autosre ai audit --incident inc-123

# View decision details
autosre ai decision --id dec_abc123

# Compare predicted vs actual
autosre ai accuracy --window 7d --by-type
```

### Replay Analysis

```bash
# Replay decisions with different model/prompt
autosre ai replay --incident inc-123 --model gpt-4 --dry-run

# Compare outcomes
autosre ai compare --original inc-123 --replay replay-456
```

## Best Practices

### 1. Regular Calibration Reviews

Weekly review of AI metrics:
- Overall accuracy trending up or down?
- Calibration curves healthy?
- Any concerning patterns?

### 2. Feedback Loops

Make it easy to provide feedback:

```python
# After every investigation
await slack.send(
    channel="#sre",
    message="Investigation complete. How did AI perform?",
    buttons=["👍 Helpful", "👎 Unhelpful", "🤔 Mixed"]
)
```

### 3. Threshold Tuning

Regularly tune confidence thresholds based on data:

```python
# Find optimal threshold
optimal = await telemetry.find_optimal_threshold(
    metric="high_severity_accuracy",
    target=0.80
)
print(f"Recommended threshold: {optimal.threshold}")
print(f"Expected accuracy at threshold: {optimal.expected_accuracy}")
```

### 4. Model Comparison

When evaluating new models:

```python
# A/B test models
await telemetry.start_ab_test(
    name="sonnet-vs-opus",
    model_a="claude-3-sonnet",
    model_b="claude-3-opus",
    traffic_split=0.5,
    duration_days=14
)
```

## See Also

- [AI Safety Features](../skills/ai_safety.md)
- [Investigation Phases](./investigation_phases.md)
- [Error Budget Tracking](../skills/error_budget.md)
