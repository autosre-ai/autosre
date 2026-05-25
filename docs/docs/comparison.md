# AutoSRE vs Competitors

A comprehensive comparison of AutoSRE with other AI-powered SRE and incident response platforms.

## Executive Summary

AutoSRE is an open-source, AI-powered incident response platform that automatically investigates alerts, identifies root causes, and suggests remediations. This document compares AutoSRE with leading competitors in the AIOps and intelligent incident management space.

| Platform | Type | Open Source | Local LLM Support | Pricing Model |
|----------|------|-------------|-------------------|---------------|
| **AutoSRE** | AI Incident Response | ✅ Apache 2.0 | ✅ Full (Ollama) | Free / Enterprise |
| kagent | Kubernetes AI Agent | ✅ Apache 2.0 | ❌ | Free |
| OpenSRE.io | SRE Platform | ❌ | ❌ | Subscription |
| RunWhen | Runbook Automation | ❌ | ❌ | Subscription |
| Shoreline | Incident Automation | ❌ | ❌ | Enterprise |
| PagerDuty AI | AI Incident Management | ❌ | ❌ | Per-user + AI add-on |

---

## Detailed Comparisons

### AutoSRE vs kagent

[kagent](https://github.com/kagent-ai/kagent) is an open-source Kubernetes-native AI agent focused on K8s operations.

| Feature | AutoSRE | kagent |
|---------|---------|--------|
| **Focus** | Full-stack incident response | Kubernetes-specific |
| **Multi-signal correlation** | ✅ Metrics, logs, traces, events | ❌ K8s only |
| **Knowledge Graph** | ✅ Neo4j service topology | ❌ |
| **Episodic Memory** | ✅ Learns from past incidents | ❌ |
| **Multi-agent architecture** | ✅ LangGraph orchestration | ✅ Single agent |
| **Cloud provider support** | ✅ AWS, GCP, Azure | ❌ |
| **Observability integrations** | ✅ Prometheus, Datadog, Dynatrace, Splunk, ELK | ❌ |
| **Incident management** | ✅ PagerDuty, OpsGenie, ServiceNow | ❌ |
| **Human-in-the-loop** | ✅ Approval workflows | Limited |
| **Chat platforms** | ✅ Slack, Telegram | ❌ |

**When to choose kagent:** You only need Kubernetes troubleshooting and want a lightweight solution.

**When to choose AutoSRE:** You need comprehensive incident investigation across your entire stack with learning capabilities.

---

### AutoSRE vs OpenSRE.io

OpenSRE.io is a commercial SRE platform focused on reliability management and SLO tracking.

| Feature | AutoSRE | OpenSRE.io |
|---------|---------|------------|
| **Open Source** | ✅ Apache 2.0 | ❌ Proprietary |
| **AI Investigation** | ✅ Autonomous analysis | ❌ Manual workflows |
| **Root Cause Analysis** | ✅ AI-powered | ❌ Manual |
| **SLO Management** | Planned | ✅ Core feature |
| **Error Budgets** | Planned | ✅ Core feature |
| **Self-hosted** | ✅ | ❌ SaaS only |
| **Data Privacy** | ✅ Your data stays yours | ❌ Cloud-processed |
| **Vendor Lock-in** | None | High |
| **Extensibility** | ✅ 27+ skills, plugin system | Limited |
| **Local LLM** | ✅ Ollama support | ❌ |

**When to choose OpenSRE.io:** Your primary need is SLO tracking and reliability reporting rather than incident investigation.

**When to choose AutoSRE:** You need AI-powered incident investigation with data privacy and extensibility.

---

### AutoSRE vs RunWhen

[RunWhen](https://runwhen.com) is a runbook automation platform that uses codebundles to automate operational tasks.

| Feature | AutoSRE | RunWhen |
|---------|---------|---------|
| **Open Source** | ✅ Apache 2.0 | ❌ Proprietary |
| **AI-driven Investigation** | ✅ Autonomous reasoning | ❌ Scripted workflows |
| **Approach** | AI agents with reasoning | Pre-defined codebundles |
| **Root Cause Analysis** | ✅ LLM-powered hypothesis | ❌ Rule-based |
| **Learning** | ✅ Episodic memory | ❌ |
| **Adaptability** | ✅ Handles novel issues | ❌ Requires pre-built bundles |
| **Multi-cloud** | ✅ AWS, GCP, Azure | ✅ |
| **Kubernetes** | ✅ | ✅ |
| **Setup Complexity** | Moderate | Higher (codebundle development) |
| **Customization** | ✅ Skills + prompts | ✅ Codebundles |

**When to choose RunWhen:** You have well-defined, repeatable operational procedures and want deterministic automation.

**When to choose AutoSRE:** You need AI that can reason about novel issues and adapt to situations not covered by pre-built runbooks.

---

### AutoSRE vs Shoreline

[Shoreline](https://shoreline.io) is an enterprise incident automation platform for debugging and remediation.

| Feature | AutoSRE | Shoreline |
|---------|---------|-----------|
| **Open Source** | ✅ Apache 2.0 | ❌ Proprietary |
| **Pricing** | Free / Enterprise option | Enterprise only |
| **AI Investigation** | ✅ Multi-agent LLM | ✅ Op Language |
| **Agent-based** | No agents on hosts | ✅ Requires agents |
| **Learning** | ✅ Episodic memory | ✅ Pattern learning |
| **Remediation** | ✅ AI-suggested, human-approved | ✅ Automated |
| **Language** | Python, natural language | Op (proprietary DSL) |
| **Fleet Management** | Via integrations | ✅ Native |
| **Real-time Debugging** | ✅ Via observability stack | ✅ Native |
| **Setup Complexity** | Low (agentless) | Higher (agent deployment) |
| **Data Privacy** | ✅ Self-hosted option | ❌ SaaS |

**When to choose Shoreline:** You need enterprise fleet management with guaranteed support and don't mind agent deployment.

**When to choose AutoSRE:** You want agentless deployment, open-source flexibility, and LLM-powered reasoning.

---

### AutoSRE vs PagerDuty AI

[PagerDuty AI](https://www.pagerduty.com/platform/aiops/) adds AI capabilities to PagerDuty's incident management platform.

| Feature | AutoSRE | PagerDuty AI |
|---------|---------|--------------|
| **Open Source** | ✅ Apache 2.0 | ❌ Proprietary |
| **Pricing** | Free / Enterprise | Per-user + AI add-on (~$20/user/mo) |
| **AI Investigation** | ✅ Autonomous multi-agent | ✅ AI summaries, suggested actions |
| **Root Cause Analysis** | ✅ Deep correlation | ✅ Pattern-based |
| **Incident Management** | Via PagerDuty integration | ✅ Native |
| **On-call Scheduling** | Via PagerDuty integration | ✅ Native |
| **Alerting** | Via integrations | ✅ Native |
| **Event Correlation** | ✅ AI + knowledge graph | ✅ |
| **Local LLM** | ✅ Full support | ❌ |
| **Self-hosted** | ✅ | ❌ |
| **Data Privacy** | ✅ Your data stays local | ❌ Processed in PagerDuty cloud |
| **Vendor Lock-in** | None | High |

**When to choose PagerDuty AI:** You're already using PagerDuty and want AI features integrated into your existing workflow.

**When to choose AutoSRE:** You want open-source flexibility, local LLM support, data privacy, and deeper investigation capabilities.

---

## Feature Matrix

### Core Capabilities

| Capability | AutoSRE | kagent | OpenSRE.io | RunWhen | Shoreline | PagerDuty AI |
|------------|---------|--------|------------|---------|-----------|--------------|
| Autonomous Investigation | ✅ | ⚠️ | ❌ | ❌ | ⚠️ | ⚠️ |
| Multi-signal Correlation | ✅ | ❌ | ❌ | ⚠️ | ✅ | ✅ |
| Root Cause Analysis | ✅ | ⚠️ | ❌ | ❌ | ⚠️ | ⚠️ |
| Episodic Memory | ✅ | ❌ | ❌ | ❌ | ⚠️ | ❌ |
| Knowledge Graph | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Human-in-the-loop | ✅ | ⚠️ | N/A | ✅ | ✅ | ✅ |
| Auto-remediation | ✅ | ⚠️ | ❌ | ✅ | ✅ | ⚠️ |

✅ = Full support | ⚠️ = Partial/Limited | ❌ = Not available

### Integrations

| Integration | AutoSRE | kagent | OpenSRE.io | RunWhen | Shoreline | PagerDuty AI |
|-------------|---------|--------|------------|---------|-----------|--------------|
| Kubernetes | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ |
| Prometheus | ✅ | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| Datadog | ✅ | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| AWS | ✅ | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| GCP | ✅ | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| Azure | ✅ | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| Slack | ✅ | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| PagerDuty | ✅ | ❌ | ⚠️ | ✅ | ✅ | ✅ (Native) |
| ServiceNow | ✅ | ❌ | ⚠️ | ⚠️ | ✅ | ✅ |
| Jira | ✅ | ❌ | ⚠️ | ⚠️ | ⚠️ | ✅ |
| ArgoCD | ✅ | ❌ | ❌ | ⚠️ | ❌ | ❌ |
| Terraform | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Vault | ✅ | ❌ | ❌ | ⚠️ | ❌ | ❌ |

### Deployment & Security

| Feature | AutoSRE | kagent | OpenSRE.io | RunWhen | Shoreline | PagerDuty AI |
|---------|---------|--------|------------|---------|-----------|--------------|
| Self-hosted | ✅ | ✅ | ❌ | ⚠️ | ❌ | ❌ |
| Air-gapped | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| Local LLM (Ollama) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Data never leaves network | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| SOC2 Compliant | Depends on deployment | N/A | ✅ | ✅ | ✅ | ✅ |

---

## AutoSRE Advantages

### 1. True AI-Powered Investigation
Unlike rule-based or scripted approaches, AutoSRE uses multi-agent LLM architecture with:
- **Planner Agent**: Generates investigation hypotheses
- **Specialist Subagents**: Execute domain-specific queries (K8s, metrics, logs, traces)
- **Synthesizer**: Correlates findings and determines root cause
- **Memory**: Learns from past investigations

### 2. Open Source & Data Privacy
- Apache 2.0 license — use, modify, contribute
- Self-hosted deployment — your data never leaves your network
- Local LLM support via Ollama — complete data sovereignty
- No vendor lock-in

### 3. Comprehensive Integration Ecosystem
27+ built-in skills covering:
- **Cloud**: AWS, GCP, Azure
- **Observability**: Prometheus, Datadog, Dynatrace, Splunk, Elasticsearch
- **Kubernetes**: Native K8s, ArgoCD
- **Incident Management**: PagerDuty, OpsGenie, ServiceNow, Jira
- **Communication**: Slack, Telegram
- **Infrastructure**: Terraform, Vault, Jenkins, GitLab, GitHub

### 4. Knowledge Graph-Powered Context
Neo4j-based service topology provides:
- Service dependencies
- Blast radius analysis
- Change correlation
- Team ownership mapping

### 5. Episodic Memory
AutoSRE learns from every investigation:
- Remembers what worked for similar issues
- Suggests proven remediation steps
- Reduces MTTR over time

### 6. Human-in-the-Loop Safety
- Dangerous actions require explicit approval
- Slack-native approval workflows
- Full audit trail
- Configurable action permissions

### 7. Cost-Effective
- Free open-source version with full functionality
- No per-user pricing
- Enterprise support available for organizations that need it

---

## Migration Guides

### From PagerDuty (with PagerDuty AI)
AutoSRE integrates with PagerDuty as an alert source and incident management system. You can:
1. Keep PagerDuty for alerting and on-call scheduling
2. Use AutoSRE for AI-powered investigation
3. Actions feed back into PagerDuty incidents

### From Shoreline
1. Replace Shoreline agents with AutoSRE's agentless integrations
2. Convert Op scripts to AutoSRE skills or natural language prompts
3. Maintain remediation patterns while gaining LLM reasoning

### From RunWhen
1. Keep valuable codebundles as AutoSRE skills
2. Gain AI-driven investigation for novel issues
3. Reduce time spent writing automation

---

## Conclusion

AutoSRE differentiates itself through:

1. **Open-source** — Full transparency, no lock-in
2. **Multi-agent AI** — True reasoning, not just pattern matching
3. **Data privacy** — Local LLM support, self-hosted deployment
4. **Comprehensive integrations** — Works with your existing stack
5. **Learning capabilities** — Gets smarter over time

For organizations that value transparency, data privacy, and AI that actually reasons about incidents, AutoSRE provides a compelling alternative to proprietary solutions.

---

## Resources

- [Getting Started Guide](/getting-started)
- [Skills Reference](/skills)
- [Architecture Overview](/architecture)
- [GitHub Repository](https://github.com/autosre/autosre)
- [Community Discord](https://discord.gg/autosre)
