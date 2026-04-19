# OpenSRE — The Open Source SRE Agent Platform

> "OpenClaw for Infrastructure" — Cloud-agnostic, vendor-neutral SRE automation

## 🎯 Vision

OpenSRE is an open-source platform that lets you build, deploy, and orchestrate SRE agents that can:
- Monitor any system (Prometheus, Datadog, Dynatrace, CloudWatch, etc.)
- Respond to incidents automatically
- Execute runbooks as code
- Learn from past incidents
- Work across any cloud (AWS, GCP, Azure, on-prem)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         OpenSRE Core                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Agent     │  │   Agent     │  │   Agent     │             │
│  │  Runtime    │  │  Orchestr.  │  │   Memory    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
├─────────────────────────────────────────────────────────────────┤
│                        Skill Layer                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │Promethe│ │Dynatrac│ │  GCP   │ │  AWS   │ │  K8s   │ ...   │
│  │  us    │ │   e    │ │        │ │        │ │        │       │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘       │
├─────────────────────────────────────────────────────────────────┤
│                      Integration Layer                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │ Slack  │ │PagerDut│ │ Jira   │ │ GitHub │ │Telegram│ ...   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## 🧩 Core Components

### 1. Agent Runtime
- Executes SRE agents (Python/TypeScript)
- Manages agent lifecycle
- Provides tool/skill access
- Handles authentication & secrets

### 2. Skill System (Plugin Architecture)
Each skill is a self-contained module:
```
skills/
├── prometheus/
│   ├── SKILL.md          # Docs + usage
│   ├── skill.yaml        # Metadata
│   ├── actions.py        # Query, alert, silence
│   └── tests/
├── kubernetes/
│   ├── SKILL.md
│   ├── skill.yaml
│   ├── actions.py        # Get pods, scale, rollback
│   └── tests/
└── ...
```

### 3. Agent Definitions
Agents are YAML + optional code:
```yaml
# agents/incident-responder.yaml
name: incident-responder
description: Auto-responds to PagerDuty incidents
triggers:
  - type: webhook
    source: pagerduty
skills:
  - prometheus
  - kubernetes
  - slack
runbook: |
  1. Acknowledge incident
  2. Query Prometheus for affected metrics
  3. Check Kubernetes pod health
  4. Post findings to Slack
  5. Suggest remediation
```

### 4. Memory & Learning
- Vector store for past incidents
- Pattern matching for similar issues
- Runbook suggestions based on history

## 🔌 Skill Categories

### Observability
- `prometheus` — Query metrics, manage alerts, silences
- `dynatrace` — Problems, metrics, smartscape
- `datadog` — Metrics, monitors, dashboards
- `grafana` — Dashboards, annotations
- `cloudwatch` — AWS metrics and alarms
- `stackdriver` — GCP monitoring
- `elastic` — Logs, APM

### Infrastructure
- `kubernetes` — Pods, deployments, scaling, rollbacks
- `terraform` — Plan, apply, state
- `ansible` — Playbook execution
- `docker` — Container management

### Cloud Providers
- `aws` — EC2, ECS, Lambda, RDS, S3
- `gcp` — GCE, GKE, Cloud Run, BigQuery
- `azure` — VMs, AKS, Functions

### Incident Management
- `pagerduty` — Incidents, on-call, escalations
- `opsgenie` — Alerts, schedules
- `servicenow` — Tickets, changes

### Communication
- `slack` — Messages, threads, reactions
- `teams` — Messages, cards
- `telegram` — Notifications

### Code & CI/CD
- `github` — Issues, PRs, Actions
- `gitlab` — Pipelines, merge requests
- `argocd` — Sync, rollback
- `jenkins` — Build triggers

## 🚀 Example Use Cases

### 1. Auto-Remediation Agent
```yaml
name: pod-restarter
trigger: prometheus_alert("PodCrashLooping")
steps:
  - kubernetes.get_pod_logs(pod_name)
  - analyze_logs_for_error()
  - if OOM: kubernetes.increase_memory(pod_name)
  - else: kubernetes.rollback_deployment()
  - slack.notify(channel="#incidents")
```

### 2. Incident Summarizer
```yaml
name: incident-summarizer
trigger: pagerduty.incident_resolved()
steps:
  - gather_timeline_from_slack()
  - query_metrics_during_incident()
  - generate_postmortem_draft()
  - create_jira_ticket()
```

### 3. Cost Anomaly Detector
```yaml
name: cost-watcher
schedule: "0 9 * * *"
steps:
  - aws.get_cost_report(last_7_days)
  - compare_to_baseline()
  - if anomaly: slack.alert(channel="#finops")
```

## 📦 Installation

```bash
# Install core
pip install opensre

# Install skills
opensre skill install prometheus kubernetes slack

# Run an agent
opensre agent run incident-responder
```

## 🛠️ Development

```bash
# Create new skill
opensre skill create my-tool

# Test skill
opensre skill test prometheus

# Run agent locally
opensre agent dev my-agent.yaml
```

## 🎯 MVP Scope (Tonight)

### Phase 1: Core Framework (2 hours)
- [ ] Skill loader and registry
- [ ] Agent runtime
- [ ] Config management
- [ ] CLI scaffolding

### Phase 2: Base Skills (3 hours)
- [ ] Prometheus skill
- [ ] Kubernetes skill
- [ ] Slack skill
- [ ] Generic HTTP skill

### Phase 3: First Agent (2 hours)
- [ ] Incident responder agent
- [ ] Alert → investigate → notify flow
- [ ] Memory/context between runs

### Phase 4: Polish (1 hour)
- [ ] Documentation
- [ ] Example configs
- [ ] Docker packaging
- [ ] GitHub repo setup

## 🏆 Success Criteria

By morning:
1. `opensre skill install prometheus` works
2. `opensre agent run incident-responder` responds to test alert
3. Skills are truly pluggable (add new skill without changing core)
4. README is compelling enough for GitHub stars
5. Working demo video script ready

## 📊 Competitive Landscape

| Tool | Pros | Cons | OpenSRE Advantage |
|------|------|------|-------------------|
| Rundeck | Mature, enterprise | Complex, dated UI | AI-native, simpler |
| StackStorm | Powerful rules | Heavy, complex setup | Lightweight, YAML-first |
| Shoreline | AI remediation | Proprietary, expensive | Open source, extensible |
| PagerDuty AIOps | Great integrations | Vendor lock-in | Cloud-agnostic |

## 🧑‍💻 Target Users

1. **SRE Teams** — Automate toil, reduce MTTR
2. **Platform Engineers** — Build self-healing infra
3. **DevOps Engineers** — Standardize incident response
4. **Solo SREs** — Force multiplier for small teams

---

*"The SRE agent platform that works with YOUR stack, not against it."*
