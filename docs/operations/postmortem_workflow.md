# Postmortem Workflow Guide

AutoSRE automates postmortem generation and tracking, ensuring every significant incident leads to organizational learning.

## Overview

Postmortems are essential for:
- Learning from incidents
- Preventing recurrence
- Improving systems and processes
- Building organizational knowledge

AutoSRE automates the tedious parts while preserving the human judgment essential for effective postmortems.

## Trigger Conditions

A postmortem is triggered when any of these conditions are met:

| Trigger | Threshold | Rationale |
|---------|-----------|-----------|
| User-visible degradation | Any | Users were impacted |
| Data loss | Any amount | Data integrity matters |
| Security incident | Any | Security requires review |
| Long resolution time | >30 minutes | Extended impact |
| Repeat incident | Same pattern within 30 days | Systemic issue |
| Error budget impact | >5% consumed | Significant reliability hit |

### Configuration

```yaml
# config/autosre.yaml
postmortem:
  triggers:
    - user_visible_degradation
    - data_loss
    - security_incident
    - resolution_time_minutes: 30
    - repeat_incident
    - error_budget_impact: 0.05
  
  auto_generate: true
```

## Automated Content Generation

### What AutoSRE Generates

When triggered, AutoSRE automatically assembles:

```markdown
# Postmortem: [Incident Title]

## Summary
[AI-generated summary of the incident]

## Impact
- **Duration**: 45 minutes (10:00 - 10:45 UTC)
- **User Impact**: ~15% of checkout transactions failed
- **Revenue Impact**: Estimated $X (if calculable)
- **Error Budget Consumed**: 8%

## Timeline
| Time (UTC) | Event |
|------------|-------|
| 09:45 | Deploy of payment-service v2.3.4 |
| 09:55 | Slow queries begin appearing in DB |
| 10:00 | Connection pool exhaustion starts |
| 10:02 | First alerts fire |
| 10:05 | On-call acknowledges |
| 10:10 | AI identifies database issue (75% confidence) |
| 10:15 | Mitigation: scaled database read replicas |
| 10:30 | Root cause identified: missing index |
| 10:40 | Fix deployed: added index |
| 10:45 | Incident resolved |

## Root Cause Analysis
[AI-synthesized root cause with supporting evidence]

### AI Investigation Trail
| Decision | Confidence | Outcome |
|----------|------------|---------|
| Severity: High | 85% | Correct |
| Hypothesis: DB connection pool | 75% | Correct |
| Mitigation: Scale replicas | 80% | Effective |

## Metrics Snapshot
[Auto-captured graphs/metrics from incident window]

## Contributing Factors
- [List of contributing factors identified during investigation]

## Action Items
| Item | Owner | Due Date | Status |
|------|-------|----------|--------|
| Add missing database index | DB Team | Jan 22 | ✅ Done |
| Add index coverage to deploy checklist | Platform | Jan 29 | 🔄 In Progress |
| Improve slow query alerting | SRE | Feb 5 | 📋 Open |

## Lessons Learned
[Section for human input]

## References
- [Link to incident channel]
- [Link to related dashboards]
- [Link to relevant runbooks]
```

### What Requires Human Input

AutoSRE generates the framework, but humans add:

- **Lessons Learned**: What did we learn?
- **Action Item Validation**: Are these the right actions?
- **Blameless Review**: Ensure blameless language
- **Additional Context**: Things not captured in telemetry

## Workflow Stages

### Stage 1: Auto-Generation

Immediately after incident resolution:

```
┌─────────────────────────────────────────────────────────────┐
│                   Trigger Evaluation                         │
│                                                              │
│  ✓ User-visible degradation: Yes                            │
│  ✓ Resolution time: 45 min (> 30 min threshold)             │
│  ✓ Error budget impact: 8% (> 5% threshold)                 │
│                                                              │
│  Result: Postmortem REQUIRED                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Content Assembly                           │
│                                                              │
│  • Gathering timeline from investigation log                │
│  • Capturing metrics snapshots                              │
│  • Synthesizing root cause analysis                         │
│  • Generating action item suggestions                       │
│  • Creating draft document                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Stage 2: Human Review

Within 24-48 hours of incident:

```
┌─────────────────────────────────────────────────────────────┐
│                   Human Review                               │
│                                                              │
│  Incident Commander: @alice                                 │
│  Postmortem Owner: @bob                                     │
│                                                              │
│  Tasks:                                                     │
│  [ ] Review and correct timeline                            │
│  [ ] Validate root cause analysis                           │
│  [ ] Add lessons learned                                    │
│  [ ] Assign action item owners                              │
│  [ ] Ensure blameless language                              │
│                                                              │
│  Due: Jan 17, 2024 (48 hours after resolution)             │
└─────────────────────────────────────────────────────────────┘
```

### Stage 3: Review Meeting

Schedule and conduct postmortem review:

```
┌─────────────────────────────────────────────────────────────┐
│                   Postmortem Review                          │
│                                                              │
│  Meeting: Jan 18, 2024 10:00 AM                            │
│  Attendees: SRE team, Platform team, Incident participants │
│                                                              │
│  Agenda:                                                    │
│  1. Timeline walkthrough (10 min)                          │
│  2. Root cause discussion (15 min)                         │
│  3. Action items review (15 min)                           │
│  4. Lessons learned (10 min)                               │
│  5. Process improvements (10 min)                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Stage 4: Action Tracking

Ongoing until all actions complete:

```
┌─────────────────────────────────────────────────────────────┐
│                   Action Tracking                            │
│                                                              │
│  Postmortem: INC-2024-0115-001                             │
│                                                              │
│  Action Items:                                              │
│  ✅ Add missing database index (Jan 18 - Done)             │
│  🔄 Add index coverage to deploy checklist (Jan 25 - IP)   │
│  📋 Improve slow query alerting (Feb 5 - Open)             │
│                                                              │
│  Progress: 1/3 complete (33%)                              │
│  Next reminder: Jan 25 for overdue items                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Template Configuration

```yaml
postmortem:
  template:
    include_timeline: true
    include_metrics: true
    include_ai_decisions: true
    include_action_items: true
    blameless_language: true
    
    # Custom sections
    custom_sections:
      - name: "Customer Communication"
        required: false
      - name: "Cost Impact"
        required: true
```

### Follow-up Configuration

```yaml
postmortem:
  follow_up:
    track_action_items: true
    reminder_days: 7
    escalation_days: 14
    
    # Notification channels
    notifications:
      slack_channel: "#postmortems"
      email_group: "sre-team@company.com"
```

### Integration Configuration

```yaml
postmortem:
  integrations:
    # Document storage
    confluence:
      enabled: true
      space: "SRE"
      parent_page: "Postmortems"
    
    # Issue tracking
    jira:
      enabled: true
      project: "SRE"
      issue_type: "Action Item"
    
    # Notifications
    slack:
      enabled: true
      channel: "#postmortems"
```

## Blameless Culture

### What Blameless Means

- Focus on systems and processes, not individuals
- Ask "what" and "how", not "who"
- Assume good intentions
- Treat failures as learning opportunities

### Automated Blameless Review

AutoSRE scans generated content for blame language:

```python
# Patterns to flag
blame_patterns = [
    r"\b(fault|blame|mistake|error|failure) of [A-Z][a-z]+",  # "fault of John"
    r"[A-Z][a-z]+ (should have|failed to|forgot to)",         # "Alice should have"
    r"(negligent|careless|incompetent)",                       # Blame words
]

# Suggested rewrites
rewrites = {
    "John's mistake caused": "The configuration change led to",
    "Alice failed to check": "The pre-deploy checklist did not include",
    "Bob forgot to": "The process did not ensure",
}
```

### Blameless Examples

| ❌ Blameful | ✅ Blameless |
|------------|--------------|
| "Alice deployed broken code" | "The deployment included a regression" |
| "Bob forgot to check the runbook" | "The runbook was not consulted during the incident" |
| "The on-call engineer was slow to respond" | "The alerting system had a 10-minute delay" |

## Metrics

### Postmortem Metrics

```promql
# Postmortems generated
autosre_postmortems_generated_total{trigger="user_visible"}
autosre_postmortems_generated_total{trigger="resolution_time"}

# Time to complete postmortem
autosre_postmortem_completion_time_days_histogram

# Action item tracking
autosre_postmortem_action_items_total{status="open|in_progress|done"}
autosre_postmortem_action_items_overdue_total
```

### Dashboard

```json
{
  "title": "Postmortem Health",
  "panels": [
    {
      "title": "Postmortems This Month",
      "type": "stat",
      "query": "sum(increase(autosre_postmortems_generated_total[30d]))"
    },
    {
      "title": "Action Items by Status",
      "type": "pie",
      "query": "sum(autosre_postmortem_action_items_total) by (status)"
    },
    {
      "title": "Overdue Action Items",
      "type": "stat",
      "query": "sum(autosre_postmortem_action_items_overdue_total)",
      "thresholds": [0, 3, 5]
    },
    {
      "title": "Time to Complete (days)",
      "type": "histogram",
      "query": "autosre_postmortem_completion_time_days_histogram"
    }
  ]
}
```

## CLI Commands

```bash
# Generate postmortem for an incident
autosre postmortem generate --incident inc-123

# View postmortem status
autosre postmortem status --incident inc-123

# List all postmortems
autosre postmortem list --status pending

# View action items
autosre postmortem actions --incident inc-123
autosre postmortem actions --status overdue

# Update action item
autosre postmortem action update --id act-456 --status done

# Send reminders for overdue items
autosre postmortem remind --overdue
```

## Best Practices

### 1. Generate Early

Start postmortem generation immediately after resolution:
- Details are fresh
- Metrics are still in short-term storage
- Team is still engaged

### 2. Complete Within 48 Hours

Human review should happen within 48 hours:
- Memory fades quickly
- Details get lost
- Momentum is lost

### 3. Action Items Must Be Actionable

Good action items are:
- Specific: "Add index to users.email column"
- Assigned: Clear owner
- Time-bound: Due date
- Measurable: Can verify completion

### 4. Follow Through

Track action items to completion:
- Weekly reminders
- Escalate overdue items
- Report on completion rate

### 5. Learn Across Incidents

Periodically review postmortems for patterns:
- Same root causes recurring?
- Same systems involved?
- Process gaps?

## Templates

### Standard Postmortem Template

Located at `config/templates/postmortem/standard.md.j2`

### Customer-Facing Summary Template

Located at `config/templates/postmortem/customer-summary.md.j2`

### Executive Summary Template

Located at `config/templates/postmortem/executive.md.j2`

## See Also

- [Investigation Phases](./investigation_phases.md)
- [AI Telemetry Monitoring](./ai_telemetry.md)
- [Error Budget Tracking](../skills/error_budget.md)
