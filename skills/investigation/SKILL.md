# Investigation Methodology

Systematic incident investigation framework for evidence-based root cause analysis.

## Overview

This skill provides a structured approach to incident investigation, inspired by SRE best practices. It defines a 5-phase investigation methodology that guides agents through evidence collection, hypothesis testing, and root cause identification.

## Investigation Phases

### Phase 1: Triage (0-5 minutes)
- Confirm the incident is real (not noise)
- Identify affected services and scope
- Check for recent deployments or changes
- Establish timeline of first occurrence

### Phase 2: Contain (5-15 minutes)
- Assess blast radius using service dependencies
- Consider immediate mitigation (rollback, scale, redirect)
- Communicate status to stakeholders

### Phase 3: Investigate (15-60 minutes)
- Generate hypotheses based on evidence
- Test hypotheses systematically
- Follow the evidence chain
- Document findings

### Phase 4: Resolve
- Implement fix (with approval)
- Verify resolution
- Monitor for recurrence

### Phase 5: Learn
- Document root cause
- Store episode for memory
- Identify preventive measures

## Hypothesis Testing

Use structured hypothesis testing:

```
1. State the hypothesis clearly
2. Define what evidence would confirm/refute it
3. Collect evidence using appropriate tools
4. Evaluate: confirmed, ruled out, or inconclusive
5. Document the result
```

## Evidence Quality Hierarchy

Weight evidence by reliability:

1. **Direct observation** (highest): Exact log lines, metric values, resource states
2. **Computed correlation**: Metrics that move together, temporal correlation
3. **Inference**: Logical deduction from multiple sources
4. **Hypothesis** (lowest): Speculation based on patterns

## Decision Tree: Where to Start

```
Alert type?
├─ Service unavailable / 5xx spike
│  └─ Start: Kubernetes pods → recent deployments → logs
├─ High latency
│  └─ Start: Metrics (p95/p99) → dependencies → saturation
├─ Memory/CPU alert
│  └─ Start: Resource metrics → pod state → OOMKill events
├─ Database issues
│  └─ Start: DB metrics → connection pools → slow queries
└─ Unknown
   └─ Start: Recent changes → error logs → metrics correlation
```

## Red Flags (Prioritize These)

| Signal | Likely Cause | First Check |
|--------|--------------|-------------|
| CrashLoopBackOff | App bug or missing config | Pod logs, events |
| OOMKilled | Memory exhaustion | Memory metrics, heap dumps |
| Connection refused | Service/DB down | Dependency health |
| Timeout cascade | Dependency slow | Latency metrics, traces |
| Error rate spike after deploy | Bad deployment | Deployment history, rollback |

## Tool Selection Guide

| Need | Primary Tool | Secondary |
|------|--------------|-----------|
| Pod status | Kubernetes | - |
| Error patterns | Log analysis | - |
| Performance | Metrics (Prometheus/Grafana) | Traces |
| Dependencies | Service mesh / traces | Logs |
| Recent changes | Git / CI/CD | - |
| Runbooks | Knowledge base | - |

## Output Template

When reporting findings, use this structure:

```markdown
## Summary
[1-2 sentence conclusion]

## Timeline
- [Time]: [Event]

## Evidence
- [Source] at [Time]: "[Quote]"

## Root Cause
[Specific cause with evidence]

## Confidence: [low/medium/high]

## Recommendations
1. [Immediate action]
2. [Preventive measure]

## What Was Ruled Out
- [Hypothesis]: [Why ruled out]

## Gaps
- [What couldn't be checked and why]
```

## Common Mistakes to Avoid

1. **Jumping to conclusions** without evidence
2. **Stopping at symptoms** instead of finding root cause
3. **Ignoring temporal correlation** (what changed?)
4. **Not documenting** ruled-out hypotheses
5. **Assuming** instead of verifying

## Dependencies

None (methodology skill)
