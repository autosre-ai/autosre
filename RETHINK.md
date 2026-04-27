# OpenSRE Rethink — Building the Foundation First

**Date:** April 27, 2026
**Insight from:** Pavan Gudiwada (HolmesGPT maintainer) + KubeCon EU learnings

---

## The Problem: Why Internal AI SRE Tools Fail

```
┌─────────────────────────────────────────────────┐
│  🏠 ROOF: Connect LLM to Alerts                 │  ← Most teams START and STOP here
│     (Where 90% of teams begin)                  │
├─────────────────────────────────────────────────┤
│  🔄 Feedback Loop                               │  ← SKIPPED
│     (Real incidents feeding agent back)         │
├─────────────────────────────────────────────────┤
│  🎭 Realistic Eval Scenarios                    │  ← SKIPPED  
│     (Actual alert payloads, real env setup)     │
├─────────────────────────────────────────────────┤
│  📊 Evals and Baselines                         │  ← SKIPPED
│     (How do you know it's getting better?)      │
├─────────────────────────────────────────────────┤
│  🏗️ FOUNDATION                                  │  ← NEVER BUILT
│     (Context, topology, ownership, history)     │
└─────────────────────────────────────────────────┘
```

**Result:** Teams dump alerts into LLM → garbage results → "AI isn't ready" → abandon project

---

## The Rethink: OpenSRE Org + AutoSRE Tool

### Organization: OpenSRE
- GitHub org: `github.com/opensre`
- Community-driven SRE AI standards
- Eval frameworks, benchmarks, best practices
- Vendor-neutral (like CNCF for SRE AI)

### Tool: AutoSRE
- The actual AI agent implementation
- Open-source equivalent to Azure SRE Agent
- Built foundation-first, not roof-first

---

## AutoSRE Architecture — Foundation First

### Layer 1: Foundation (Build This FIRST)

```yaml
foundation:
  context_store:
    - service_topology: "Who owns what, how services connect"
    - change_history: "What deployed in last 24h, who deployed it"
    - incident_history: "Past incidents, resolutions, postmortems"
    - runbooks: "Indexed, searchable, versioned"
    - team_ownership: "PagerDuty/OpsGenie ownership mapping"
    - slo_definitions: "What are the actual targets"
    
  connectors:
    - kubernetes: "Cluster state, deployments, events"
    - prometheus: "Metrics, alerts, recording rules"
    - github: "Recent commits, PRs, deployments"
    - pagerduty: "On-call, escalations, past incidents"
    - slack: "Channel history, who knows what"
    - jira: "Related tickets, known issues"
```

### Layer 2: Evals and Baselines (Build BEFORE agent logic)

```yaml
eval_framework:
  synthetic_incidents:
    - name: "memory_leak_gradual"
      setup: "Deploy pod with memory leak, wait for OOM"
      expected_detection: "< 5 minutes"
      expected_root_cause: "Memory leak in service X"
      expected_runbook: "memory-troubleshooting.md"
      
    - name: "cert_expiry"
      setup: "Create cert expiring in 1 hour"
      expected_detection: "Proactive alert"
      expected_action: "Rotate cert automatically or alert owner"
      
    - name: "cascading_failure"
      setup: "Kill upstream dependency"
      expected_correlation: "Link downstream errors to root cause"
      
  replay_incidents:
    - source: "production_incidents_2025.jsonl"
    - fields: ["alerts", "metrics", "logs", "resolution"]
    - eval: "Did agent find same root cause as human?"
    
  baselines:
    - metric: "time_to_root_cause"
    - metric: "correct_runbook_selection"
    - metric: "false_positive_rate"
    - metric: "human_override_rate"
```

### Layer 3: Realistic Eval Scenarios

```yaml
eval_environments:
  sandbox_cluster:
    - kind: "Kubernetes cluster (kind/k3s)"
    - chaos: "Inject failures programmatically"
    - observability: "Full Prometheus/Grafana stack"
    - reset: "Tear down and rebuild in < 2 minutes"
    
  alert_replay:
    - real_payloads: "Anonymized production alerts"
    - real_metrics: "Time-series from actual incidents"
    - real_logs: "Sanitized log snippets"
    
  scenarios:
    - "High CPU but no user impact"
    - "Low error rate but high latency"
    - "Deployment rollback needed"
    - "External dependency down"
    - "Alert storm (100+ alerts in 5 min)"
```

### Layer 4: Feedback Loop

```yaml
feedback_loop:
  incident_outcomes:
    - track: "Did agent recommendation help?"
    - track: "Was root cause correct?"
    - track: "Did human override?"
    - track: "Time to resolution delta"
    
  continuous_learning:
    - fine_tune: "Embed successful resolutions"
    - update_context: "New runbooks, changed topology"
    - retrain_evals: "Add new incident patterns"
    
  human_feedback:
    - thumbs_up_down: "Quick signal on recommendations"
    - correction_capture: "What should agent have said?"
    - escalation_tracking: "When does agent fail?"
```

### Layer 5: Agent Logic (Build LAST)

```yaml
agent:
  observers:
    - alert_watcher: "Ingest alerts from Prometheus/PagerDuty"
    - metric_analyzer: "Detect anomalies in time-series"
    - log_correlator: "Find related log patterns"
    - change_detector: "What changed recently?"
    
  reasoner:
    - llm: "qwen3:14b (local) or claude-sonnet (cloud)"
    - context_injection: "Foundation data + recent changes"
    - chain_of_thought: "Show reasoning, not just answer"
    - confidence_scoring: "How sure is the agent?"
    
  actors:
    - runbook_executor: "Run approved remediation"
    - notification_sender: "Alert right people"
    - ticket_creator: "Open Jira/Linear tickets"
    - rollback_initiator: "Revert bad deploys"
    
  guardrails:
    - human_approval: "Required for destructive actions"
    - blast_radius: "Limit scope of automated actions"
    - dry_run_default: "Show what would happen first"
    - audit_log: "Every action logged"
```

---

## Comparison: AutoSRE vs Azure SRE Agent

| Feature | Azure SRE Agent | AutoSRE |
|---------|-----------------|---------|
| **Source** | Proprietary | Open Source |
| **Cloud** | Azure only | Multi-cloud + on-prem |
| **LLM** | Azure OpenAI | Any (Ollama, Claude, GPT) |
| **Evals** | Internal | Public benchmarks |
| **Context** | Azure-native | Pluggable connectors |
| **Pricing** | Pay per use | Free |
| **Customization** | Limited | Full control |

---

## MVP Scope — 4 Week Sprint

### Week 1: Foundation
- [ ] Context store schema (service topology, ownership)
- [ ] Kubernetes connector (read-only)
- [ ] Prometheus connector (query metrics/alerts)
- [ ] GitHub connector (recent deployments)

### Week 2: Eval Framework
- [ ] Synthetic incident generator
- [ ] Alert replay from JSONL
- [ ] Baseline metrics (time to root cause, accuracy)
- [ ] CLI: `autosre eval run --scenario memory_leak`

### Week 3: Sandbox Environment
- [ ] Kind cluster auto-setup
- [ ] Chaos injection (pod kill, network latency)
- [ ] Prometheus + Grafana pre-configured
- [ ] CLI: `autosre sandbox create`

### Week 4: Agent MVP
- [ ] Simple reasoning loop (alert → context → recommendation)
- [ ] Ollama integration (qwen3:14b)
- [ ] Human-in-the-loop approval
- [ ] CLI: `autosre agent analyze --alert <alert.json>`

---

## Repo Structure

```
github.com/opensre/autosre/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── getting-started.md
│   ├── eval-framework.md
│   └── connectors/
├── autosre/
│   ├── foundation/
│   │   ├── context_store.py
│   │   ├── connectors/
│   │   │   ├── kubernetes.py
│   │   │   ├── prometheus.py
│   │   │   ├── github.py
│   │   │   └── pagerduty.py
│   │   └── topology.py
│   ├── evals/
│   │   ├── framework.py
│   │   ├── scenarios/
│   │   │   ├── memory_leak.yaml
│   │   │   ├── cert_expiry.yaml
│   │   │   └── cascading_failure.yaml
│   │   ├── replay.py
│   │   └── baselines.py
│   ├── sandbox/
│   │   ├── cluster.py
│   │   ├── chaos.py
│   │   └── observability.py
│   ├── agent/
│   │   ├── observer.py
│   │   ├── reasoner.py
│   │   ├── actor.py
│   │   └── guardrails.py
│   └── cli/
│       └── main.py
├── scenarios/
│   └── *.yaml
├── tests/
├── pyproject.toml
└── Makefile
```

---

## Key Differentiators

1. **Foundation-First:** Context store before agent logic
2. **Evals-First:** Measure improvement before shipping
3. **Replay-Driven:** Train on real incidents, not hypotheticals
4. **Local-First:** Ollama default, cloud optional
5. **Human-in-Loop:** Destructive actions need approval
6. **Multi-Cloud:** Not locked to any provider
7. **Community Benchmarks:** Public leaderboard for AI SRE tools

---

## Next Steps

1. Create GitHub org: `github.com/opensre`
2. Rename existing project to `autosre`
3. Build foundation layer first (Week 1)
4. Create 10 synthetic incident scenarios
5. Write eval framework before touching agent code
6. Announce on LinkedIn + HN when evals are solid

---

*"Build your evals first. Then decide whether to build on top of what's already there or start from scratch."* — Pavan Gudiwada
