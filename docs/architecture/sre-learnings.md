# SRE Learnings Architecture

This document describes how AutoSRE implements key learnings from the SRE discipline, based on Google's SRE book and industry best practices.

## Overview

AutoSRE is built on five core SRE principles:

1. **SLO-Driven Operations** - Error budgets guide all decisions
2. **AI Safety** - Structured reasoning with human oversight
3. **Investigation Phases** - Triage first, then mitigate
4. **Postmortem Culture** - Learn from every incident
5. **Toil Reduction** - Automate repetitive work

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AutoSRE Core                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  SLO Engine  │  │  AI Safety   │  │ Investigation│  │  Postmortem │ │
│  │              │  │   Module     │  │    Engine    │  │   Generator │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
│         │                 │                 │                  │        │
│         └─────────────────┼─────────────────┼──────────────────┘        │
│                           │                 │                           │
│                    ┌──────▼─────────────────▼──────┐                    │
│                    │      Decision Engine          │                    │
│                    │  (Hypothesis → Action)        │                    │
│                    └──────────────┬────────────────┘                    │
│                                   │                                      │
│  ┌──────────────┐  ┌──────────────▼──────────────┐  ┌────────────────┐ │
│  │ Toil Tracker │  │     Telemetry Collector     │  │ Golden Signals │ │
│  │              │  │                              │  │    Monitor     │ │
│  └──────────────┘  └─────────────────────────────┘  └────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 1. SLO-Driven Operations

### Implementation

The SLO Engine is the heart of AutoSRE's decision-making:

```
┌─────────────────────────────────────────────────────────────┐
│                      SLO Engine                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │ SLI Metrics │───▶│ Budget Calc │───▶│ Policy Enforcer │ │
│  │  Collector  │    │             │    │                 │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│         │                  │                    │           │
│         ▼                  ▼                    ▼           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │  Prometheus │    │ Burn Rate   │    │   Deployment    │ │
│  │   Queries   │    │  Alerting   │    │     Gating      │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Purpose | Location |
|-----------|---------|----------|
| SLI Collector | Gathers availability, latency metrics | `autosre/slo/collector.py` |
| Budget Calculator | Computes error budget remaining | `autosre/slo/budget.py` |
| Policy Enforcer | Applies deployment policies | `autosre/slo/policy.py` |
| Burn Rate Alerter | Multi-window burn rate alerts | `autosre/slo/alerts.py` |

### Configuration Points

```yaml
# config/autosre.yaml
slo:
  default_target: 0.999
  error_budget_warning_threshold: 0.20
  block_deploy_when_exhausted: true
  
  calculation:
    window_days: 30
    exclude_maintenance: true
```

### Integration Points

- **CI/CD**: Pre-deployment budget check via API
- **Prometheus**: SLI metric queries
- **Alertmanager**: Burn rate alert rules
- **Kubernetes**: Admission webhook for deployment gating

## 2. AI Safety Module

### Implementation

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Safety Module                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │ Hypothesis  │───▶│ Confidence  │───▶│    Approval     │ │
│  │  Formatter  │    │  Validator  │    │    Gateway      │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│         │                  │                    │           │
│         ▼                  ▼                    ▼           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │  Evidence   │    │   AI Error  │    │     Human       │ │
│  │  Collector  │    │   Budget    │    │   Oversight     │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                 Telemetry Exporter                      ││
│  │  (Decisions, Outcomes, Confidence Calibration)          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Hypothesis Formatter | Enforces structured reasoning | `autosre/safety/hypothesis.py` |
| Confidence Validator | Validates confidence thresholds | `autosre/safety/confidence.py` |
| Approval Gateway | Routes high-risk actions for approval | `autosre/safety/approval.py` |
| AI Error Budget | Tracks AI accuracy over time | `autosre/safety/error_budget.py` |
| Telemetry Exporter | Exports AI metrics to Prometheus | `autosre/safety/telemetry.py` |

### Configuration Points

```yaml
# config/autosre.yaml
ai_safety:
  confidence_threshold: 0.7
  
  require_human_approval_for:
    - destructive_actions
    - high_blast_radius
  
  hypothesis_format:
    require_confidence_score: true
    require_evidence: true
    require_falsifiable_criteria: true
  
  error_budget:
    high_severity_accuracy: 0.80
    safe_action_rate: 0.99
```

### Integration Points

- **LLM Providers**: Structured output formatting
- **Slack/PagerDuty**: Approval workflows
- **Prometheus**: AI performance metrics
- **Audit Log**: Decision tracking

## 3. Investigation Engine

### Implementation

```
┌─────────────────────────────────────────────────────────────┐
│                   Investigation Engine                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    Phase Controller                     ││
│  │                                                          ││
│  │   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌────────┐ ││
│  │   │ TRIAGE  │──▶│ MITIGATE│──▶│DIAGNOSE │──▶│ RESOLVE│ ││
│  │   └─────────┘   └─────────┘   └─────────┘   └────────┘ ││
│  │                                                          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │  Hypothesis │    │    Action   │    │    Timeline     │ │
│  │   Manager   │    │   Executor  │    │    Recorder     │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Phase Flow

1. **TRIAGE** (mandatory first)
   - Assess scope and impact
   - Classify severity
   - Notify stakeholders

2. **MITIGATE** (stop the bleeding)
   - Apply quick fixes
   - Redirect traffic
   - Scale resources

3. **DIAGNOSE** (find root cause)
   - Generate hypotheses
   - Gather evidence
   - Validate/invalidate

4. **RESOLVE** (permanent fix)
   - Implement fix
   - Verify resolution
   - Document

### Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Phase Controller | Manages investigation state machine | `autosre/investigation/phases.py` |
| Hypothesis Manager | Tracks and evaluates hypotheses | `autosre/investigation/hypothesis.py` |
| Action Executor | Executes remediation actions | `autosre/investigation/actions.py` |
| Timeline Recorder | Creates incident timeline | `autosre/investigation/timeline.py` |

### Configuration Points

```yaml
# config/autosre.yaml
investigation:
  phases:
    triage_required: true
    mitigation_timeout_minutes: 15
    minimum_evidence_threshold: 3
```

## 4. Postmortem Generator

### Implementation

```
┌─────────────────────────────────────────────────────────────┐
│                   Postmortem Generator                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │   Trigger   │───▶│   Content   │───▶│    Document     │ │
│  │  Evaluator  │    │  Assembler  │    │   Generator     │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│         │                  │                    │           │
│         ▼                  ▼                    ▼           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │   Incident  │    │   Metrics   │    │   Action Item   │ │
│  │  Classifier │    │  Snapshots  │    │    Tracker      │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Trigger Conditions

- User-visible degradation
- Data loss (any amount)
- Resolution time > 30 minutes
- Repeat incident (same pattern)
- Error budget impact > 5%

### Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Trigger Evaluator | Determines if postmortem needed | `autosre/postmortem/triggers.py` |
| Content Assembler | Gathers timeline, metrics, decisions | `autosre/postmortem/assembler.py` |
| Document Generator | Creates markdown/Confluence doc | `autosre/postmortem/generator.py` |
| Action Item Tracker | Tracks follow-up completion | `autosre/postmortem/actions.py` |

### Configuration Points

```yaml
# config/autosre.yaml
postmortem:
  triggers:
    - user_visible_degradation
    - data_loss
    - resolution_time_minutes: 30
  
  auto_generate: true
  
  template:
    include_timeline: true
    include_metrics: true
    include_ai_decisions: true
    blameless_language: true
```

## 5. Toil Tracker

### Implementation

```
┌─────────────────────────────────────────────────────────────┐
│                      Toil Tracker                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │   Activity  │───▶│ Classifier  │───▶│   Automation    │ │
│  │   Monitor   │    │             │    │   Recommender   │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│         │                  │                    │           │
│         ▼                  ▼                    ▼           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │   Action    │    │    Toil     │    │    Weekly       │ │
│  │   Logging   │    │   Budget    │    │    Reports      │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Toil Categories

- Manual remediation (should be automated)
- Repetitive investigation (same patterns)
- Ticket management (routing, updates)
- Capacity management (manual scaling)
- Deployment babysitting

### Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Activity Monitor | Tracks SRE activities | `autosre/toil/monitor.py` |
| Classifier | Categorizes work as toil or project | `autosre/toil/classifier.py` |
| Automation Recommender | Suggests automation targets | `autosre/toil/recommender.py` |
| Budget Tracker | Tracks toil vs. 50% target | `autosre/toil/budget.py` |

### Configuration Points

```yaml
# config/autosre.yaml
toil:
  budget_percentage: 50
  track_automatically: true
  
  automation:
    suggestion_threshold: 3
    prioritize_by:
      - frequency
      - time_spent
      - error_prone
```

## Data Flow

```
                 ┌──────────────────────┐
                 │   Alert/Incident     │
                 └──────────┬───────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    Investigation Engine                       │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────────┐  │
│  │ TRIAGE  │──▶│ MITIGATE│──▶│ DIAGNOSE│──▶│   RESOLVE   │  │
│  └────┬────┘   └────┬────┘   └────┬────┘   └──────┬──────┘  │
└───────┼─────────────┼────────────┼────────────────┼──────────┘
        │             │            │                │
        ▼             ▼            ▼                ▼
   ┌─────────┐   ┌─────────┐  ┌─────────┐    ┌──────────┐
   │ AI Safe │   │ SLO     │  │ Golden  │    │ Postmort │
   │ Classif │   │ Budget  │  │ Signals │    │ Generate │
   └────┬────┘   └────┬────┘  └────┬────┘    └─────┬────┘
        │             │            │               │
        └─────────────┴────────────┴───────────────┘
                            │
                            ▼
                   ┌────────────────┐
                   │   Telemetry    │
                   │   Collector    │
                   └────────┬───────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
       ┌─────────┐    ┌─────────┐    ┌─────────┐
       │Prometheus│    │ Audit   │    │ Toil    │
       │ Metrics │    │  Log    │    │ Tracker │
       └─────────┘    └─────────┘    └─────────┘
```

## Database Schema

### Key Tables

```sql
-- AI Decision Tracking
CREATE TABLE ai_decisions (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    decision_type VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    input JSONB NOT NULL,
    output JSONB NOT NULL,
    model VARCHAR(100),
    latency_ms INT,
    outcome VARCHAR(20),  -- correct, incorrect, pending
    human_feedback TEXT
);

-- Error Budget Tracking
CREATE TABLE error_budget_snapshots (
    id UUID PRIMARY KEY,
    service VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    slo_target FLOAT NOT NULL,
    current_sli FLOAT NOT NULL,
    budget_remaining FLOAT NOT NULL,
    burn_rate_1h FLOAT,
    burn_rate_6h FLOAT
);

-- Toil Tracking
CREATE TABLE toil_activities (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    category VARCHAR(50) NOT NULL,
    description TEXT,
    duration_minutes INT,
    is_automated BOOLEAN DEFAULT FALSE,
    automation_potential FLOAT
);
```

## Metrics Reference

### SLO Metrics

```promql
autosre_slo_target{service="..."}
autosre_sli_current{service="...", indicator="..."}
autosre_error_budget_remaining_ratio{service="..."}
autosre_error_budget_burn_rate{service="...", window="1h|6h|24h"}
```

### AI Safety Metrics

```promql
autosre_ai_decisions_total{type="...", outcome="..."}
autosre_ai_accuracy_ratio{metric="high_severity|safe_action|root_cause"}
autosre_ai_confidence_histogram{type="..."}
autosre_ai_human_overrides_total{type="..."}
```

### Investigation Metrics

```promql
autosre_investigation_duration_seconds{phase="..."}
autosre_investigation_phase_transitions_total{from="...", to="..."}
autosre_hypothesis_count{outcome="validated|invalidated"}
```

### Toil Metrics

```promql
autosre_toil_budget_ratio
autosre_toil_activities_total{category="..."}
autosre_toil_automation_opportunities{category="..."}
```

## Extension Points

### Custom Skills

Add new skills by implementing the base class:

```python
from autosre.skills.base import BaseSkill

class CustomSkill(BaseSkill):
    name = "custom"
    
    async def execute(self, action: str, params: dict) -> dict:
        ...
```

### Custom Postmortem Templates

Add templates in `config/templates/postmortem/`:

```jinja2
# Incident Postmortem: {{ incident.title }}

## Summary
{{ incident.summary }}

## Timeline
{% for event in timeline %}
- {{ event.time }}: {{ event.description }}
{% endfor %}
```

### Custom Toil Classifiers

Extend the toil classifier:

```python
from autosre.toil.classifier import ToilClassifier

class CustomClassifier(ToilClassifier):
    def classify(self, activity: Activity) -> Classification:
        ...
```

## See Also

- [Investigation Phases](../operations/investigation_phases.md)
- [AI Telemetry Monitoring](../operations/ai_telemetry.md)
- [Postmortem Workflow](../operations/postmortem_workflow.md)
