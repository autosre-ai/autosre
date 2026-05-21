# AutoSRE Skills - Iteration 1 Summary

## Overview

This iteration analyzed OpenSRE's skill architecture and created enhanced skills for AutoSRE based on their patterns and methodologies.

## OpenSRE Skills Architecture

### How OpenSRE Organizes Skills

1. **Skills Directory**: `.claude/skills/` contains skill folders
2. **Each Skill Has**:
   - `SKILL.md` - Methodology documentation with YAML frontmatter
   - Python scripts in `scripts/` subdirectory
   - Configuration via team config service

3. **Skill Loading**:
   - Progressive disclosure (~100 tokens metadata initially)
   - Full content loaded on demand via `load_skill(name)`
   - Scripts executed via `run_script(command)`

### OpenSRE Skill Categories (46 skills)

| Category | Skills |
|----------|--------|
| **Methodology** | investigate, observability, infrastructure |
| **Observability** | Coralogix, Datadog, Elasticsearch, Splunk, Loki, Jaeger, Grafana, New Relic, Honeycomb, Sentry, VictoriaLogs, VictoriaMetrics |
| **Infrastructure** | Kubernetes, AWS, Docker, GCP, Azure, Neo4j |
| **Incidents** | PagerDuty, Incident.io, Opsgenie, Blameless, FireHydrant |
| **Databases** | PostgreSQL, MySQL, Snowflake, BigQuery |
| **Streaming** | Kafka |
| **Platform** | Vercel, flagd |
| **Project & Docs** | GitLab, Jira, Linear, Notion, ClickUp, Sourcegraph, Google Docs |

### Key Patterns from OpenSRE

1. **Gateway-First for K8s**: No direct kubectl - all via k8s-gateway scripts
2. **Statistics Before Dump**: Never dump all logs - start with statistics
3. **RED/USE Methods**: Structured metrics analysis methodology
4. **Tool Call Limits**: Max 15 tool calls per task
5. **Evidence Quoting**: `[SOURCE] at [TIMESTAMP]: "[QUOTE]"`
6. **Structured Output**: Hypotheses, sources, ruled out, gaps

## Skills Created

### 1. Investigation Methodology (`skills/investigation/`)
**Type**: Methodology (no executable actions)

Provides:
- 5-phase investigation framework (Triage → Contain → Investigate → Resolve → Learn)
- Hypothesis testing methodology
- Evidence quality hierarchy
- Decision trees for where to start
- Output templates

### 2. Log Analysis (`skills/log-analysis/`)
**Type**: Observability skill with actions

Provides:
- Partition-first, sampling-based methodology
- Statistics → Sample → Pattern → Temporal → Correlate workflow
- Query patterns for Elasticsearch, Splunk, Loki, Coralogix
- Correlation ID tracking
- Noise filtering guidance

Actions:
- `get_log_statistics`
- `sample_logs`
- `search_logs_by_pattern`
- `extract_log_signatures`
- `get_logs_around_timestamp`
- `trace_request`

### 3. Metrics Analysis (`skills/metrics-analysis/`)
**Type**: Observability skill with actions

Provides:
- RED method (Rate, Errors, Duration) for services
- USE method (Utilization, Saturation, Errors) for resources
- Statistical anomaly detection (σ thresholds)
- SLO/SLI awareness and burn rate
- Seasonality and baseline comparison
- PromQL examples

Actions:
- `query_metrics`
- `get_red_metrics`
- `get_use_metrics`
- `detect_anomalies`
- `find_change_points`
- `correlate_metrics`
- `compare_to_baseline`
- `get_slo_status`

### 4. Infrastructure Debugging (`skills/infrastructure/`)
**Type**: Infrastructure skill with actions

Provides:
- Kubernetes troubleshooting decision tree
- Common issues by resource type (Pod, Deployment, StatefulSet, etc.)
- Node-level issue patterns
- Network troubleshooting workflow
- kubectl command reference
- AWS EKS and GCP GKE specific issues

Actions:
- All Kubernetes operations (list, describe, logs, events)
- Resource usage queries
- Write operations with approval (restart, scale, rollback)

### 5. Trace Analysis (`skills/traces/`)
**Type**: Observability skill with actions

Provides:
- Distributed tracing analysis methodology
- Critical path analysis
- Latency breakdown
- Bottleneck identification
- Request flow visualization
- Query examples for Jaeger/Tempo

Actions:
- `find_traces`
- `get_trace`
- `analyze_trace`
- `compare_traces`
- `get_service_latency`
- `get_service_dependencies`

### 6. Enhanced Kubernetes Skill (`skills/kubernetes/`)
**Type**: Updated existing skill

Enhanced with:
- OpenSRE troubleshooting decision tree
- Common issues by resource type
- Node-level issue patterns
- Network troubleshooting workflow
- Investigation steps

## Files Created/Modified

```
skills/
├── investigation/
│   ├── SKILL.md          # Methodology documentation
│   ├── skill.yaml        # Skill configuration
│   └── __init__.py       # Package marker
├── log-analysis/
│   ├── SKILL.md          # Log analysis methodology
│   ├── skill.yaml        # Actions configuration
│   └── __init__.py       # Backend implementations
├── metrics-analysis/
│   ├── SKILL.md          # Metrics methodology (RED/USE)
│   ├── skill.yaml        # Actions configuration
│   └── __init__.py       # Backend implementations
├── infrastructure/
│   ├── SKILL.md          # Infrastructure debugging
│   ├── skill.yaml        # Actions configuration
│   └── __init__.py       # K8s operations
├── traces/
│   ├── SKILL.md          # Trace analysis methodology
│   ├── skill.yaml        # Actions configuration
│   └── __init__.py       # Tracing backends
└── kubernetes/
    └── SKILL.md          # Enhanced with troubleshooting tree
```

## What We Learned from OpenSRE

### Architecture Decisions

1. **Skills vs Tools**: OpenSRE uses skills (methodology + scripts) rather than direct MCP tools
2. **Progressive Disclosure**: Metadata first, full content on demand
3. **Config Service**: Centralized configuration with team/org hierarchy
4. **Memory System**: Episodic memory for learning from past incidents

### Investigation Patterns

1. **Never dump all logs** - Always start with statistics
2. **RED/USE methods** - Structured approach to metrics
3. **Tool call limits** - Prevent infinite loops (max 15 calls)
4. **Evidence-based** - Quote specific logs, timestamps, values
5. **Hypothesis tracking** - Confirmed, ruled out, untested
6. **Transparency** - Document what was checked and what wasn't

### Error Handling

1. **Classify errors** - Retryable vs non-retryable
2. **Auth errors** - 401/403 need human intervention
3. **Config required** - Integration not configured
4. **Discovery fallback** - If context fails, try discovery

## Next Steps

1. **Implement Backends**: Add actual implementations for log/metrics backends
2. **Add More Skills**: Port remaining OpenSRE skills (alerting, incidents, etc.)
3. **Skill Loader**: Create skill loading system similar to OpenSRE's
4. **Memory Integration**: Add episodic memory for learning
5. **Config Service**: Build configuration hierarchy for skills

## Compatibility

The skills created follow the same patterns as OpenSRE:
- YAML frontmatter in SKILL.md
- skill.yaml for configuration
- Python implementations
- Methodology-first approach
- Structured output templates

This makes future integration or migration straightforward.
