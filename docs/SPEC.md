# AutoSRE V2 Specification

**Version:** 2.0.0  
**Status:** Draft  
**Last Updated:** 2025-07-18  
**Authors:** AutoSRE Engineering Team

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Components](#3-components)
   - [3.1 CLI](#31-cli)
   - [3.2 API Server](#32-api-server)
   - [3.3 Web UI](#33-web-ui)
   - [3.4 Multi-Agent Core](#34-multi-agent-core)
   - [3.5 Integrations](#35-integrations)
4. [Data Models](#4-data-models)
5. [Deployment](#5-deployment)
6. [API Reference](#6-api-reference)

---

## 1. Overview

### 1.1 What is AutoSRE

AutoSRE V2 is an enterprise-grade AI-powered Site Reliability Engineering platform that automatically investigates production incidents, identifies root causes, and recommends or executes remediation actions. Built on a multi-agent architecture, AutoSRE V2 combines:

- **Intelligent Triage**: Automatic classification and prioritization of incoming alerts
- **Deep Investigation**: LLM-powered root cause analysis across logs, metrics, traces, and infrastructure
- **Episodic Memory**: Learning from past incidents to accelerate future investigations
- **Knowledge Graph**: Understanding service dependencies and blast radius
- **Automated Remediation**: Safe execution of runbook-based fixes with human-in-the-loop controls

### 1.2 Key Capabilities

| Capability | Description |
|------------|-------------|
| **Multi-Agent Investigation** | Parallel investigation by specialized agents (Kubernetes, Metrics, Logs, Traces) |
| **Episodic Memory System** | Stores and retrieves past investigations for pattern matching |
| **Knowledge Graph Integration** | Neo4j-powered service topology for dependency-aware analysis |
| **Progressive Skill Loading** | 50+ production skills loaded on-demand to minimize context overhead |
| **Real-time Streaming** | SSE-based streaming of investigation progress |
| **Multi-Provider LLM Support** | Via LiteLLM proxy (OpenAI, Anthropic, OpenRouter, Ollama, etc.) |
| **Runbook Automation** | Execute remediation steps with approval workflows |
| **Observability Integration** | Native support for Prometheus, Grafana, Datadog, Elasticsearch, and more |

### 1.3 Target Users

| User Role | Use Case |
|-----------|----------|
| **SRE Teams** | Primary operators receiving alerts, conducting investigations, and executing remediations |
| **DevOps Engineers** | Infrastructure troubleshooting, deployment correlation, and blast radius analysis |
| **Platform Engineers** | Managing AutoSRE configuration, integrations, and runbook libraries |
| **Incident Commanders** | Overseeing complex incidents with multi-service impact |
| **On-Call Engineers** | 24/7 responders needing rapid triage and investigation assistance |

---

## 2. Architecture

### 2.1 Multi-Agent System Design

AutoSRE V2 employs a hierarchical multi-agent architecture using LangGraph for orchestration:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AutoSRE V2 Architecture                        │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌───────────────────────┐
                         │     Entry Points      │
                         │  ┌─────┬─────┬─────┐  │
                         │  │ CLI │ API │Slack│  │
                         │  └──┬──┴──┬──┴──┬──┘  │
                         └─────┼─────┼─────┼─────┘
                               │     │     │
                               └─────┼─────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Web UI (Next.js)                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │  Dashboard  │ │ Agent Runs  │ │   Memory    │ │  Config Editor      │   │
│  │             │ │ + Traces    │ │  Browser    │ │  + Runbooks         │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API Server (FastAPI)                              │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐    │
│  │ REST Endpoints   │ │  SSE Streaming   │ │  WebSocket (real-time)   │    │
│  │ /investigate     │ │  /investigate    │ │  /ws/investigations      │    │
│  │ /alerts          │ │  Event Stream    │ │  Live Updates            │    │
│  └──────────────────┘ └──────────────────┘ └──────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Multi-Agent Core (LangGraph)                         │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         Investigation Graph                           │  │
│  │                                                                       │  │
│  │   ┌────────────┐                                                      │  │
│  │   │   START    │                                                      │  │
│  │   └─────┬──────┘                                                      │  │
│  │         ▼                                                             │  │
│  │   ┌────────────┐                                                      │  │
│  │   │   Init     │  Parse alert, load team config                       │  │
│  │   │  Context   │                                                      │  │
│  │   └─────┬──────┘                                                      │  │
│  │         │                                                             │  │
│  │    ┌────┴────┐    Parallel context enrichment                         │  │
│  │    ▼         ▼                                                        │  │
│  │ ┌──────┐ ┌──────┐                                                     │  │
│  │ │Memory│ │  KG  │  Similar episodes + Service topology                │  │
│  │ │Lookup│ │Context│                                                    │  │
│  │ └──┬───┘ └──┬───┘                                                     │  │
│  │    └────┬───┘                                                         │  │
│  │         ▼                                                             │  │
│  │   ┌────────────┐                                                      │  │
│  │   │  Planner   │  Generate hypotheses, select agents                  │  │
│  │   │   Agent    │                                                      │  │
│  │   └─────┬──────┘                                                      │  │
│  │         │                                                             │  │
│  │    Send() fan-out to parallel subagents                               │  │
│  │    ┌────┼────┬────┬────┐                                              │  │
│  │    ▼    ▼    ▼    ▼    ▼                                              │  │
│  │ ┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐                                   │  │
│  │ │ K8s ││Metr-││ Log ││Trace││ ... │  Investigation Subagents          │  │
│  │ │Agent││ ics ││Agent││Agent││     │  (ReAct loops with tools)         │  │
│  │ └──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘                                   │  │
│  │    └───┬──┴───┬──┴───┬──┴───┬──┘                                      │  │
│  │        └──────┼──────┘                                                │  │
│  │               ▼                                                       │  │
│  │   ┌────────────────┐                                                  │  │
│  │   │  Synthesizer   │  Combine findings, decide: loop or conclude      │  │
│  │   │     Agent      │                                                  │  │
│  │   └───────┬────────┘                                                  │  │
│  │           │                                                           │  │
│  │     ┌─────┴─────┐                                                     │  │
│  │     ▼           ▼                                                     │  │
│  │ [Loop back   [Proceed to                                              │  │
│  │  to Planner]  Writeup]                                                │  │
│  │                 │                                                     │  │
│  │                 ▼                                                     │  │
│  │   ┌────────────────┐                                                  │  │
│  │   │    Writeup     │  Generate structured report                      │  │
│  │   │     Agent      │                                                  │  │
│  │   └───────┬────────┘                                                  │  │
│  │           ▼                                                           │  │
│  │   ┌────────────────┐                                                  │  │
│  │   │ Memory Store   │  Store episode for future reference              │  │
│  │   └───────┬────────┘                                                  │  │
│  │           ▼                                                           │  │
│  │       ┌──────┐                                                        │  │
│  │       │ END  │                                                        │  │
│  │       └──────┘                                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                   │                    │                    │
                   ▼                    ▼                    ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   Config Service    │  │   LiteLLM Proxy     │  │   Neo4j Knowledge   │
│   (PostgreSQL)      │  │   (Multi-Provider)  │  │   Graph             │
│                     │  │                     │  │                     │
│ • Team configs      │  │ • OpenRouter        │  │ • Service topology  │
│ • Tokens/Auth       │  │ • Anthropic         │  │ • Dependencies      │
│ • Audit logs        │  │ • OpenAI            │  │ • Blast radius      │
│ • Agent runs        │  │ • Ollama (local)    │  │                     │
│ • Episodic memory   │  │ • 18+ providers     │  │                     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

### 2.2 Component Diagram (Detailed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            External Integrations                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │Prometheus│ │Alertmgr │ │Kubernetes│ │PagerDuty │ │  Slack   │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │            │            │            │            │                 │
│  ┌────┴────────────┴────────────┴────────────┴────────────┴────┐           │
│  │                   Integration Adapters                       │           │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐     │           │
│  │  │ Prom   │ │ Alert  │ │ K8s    │ │ PD     │ │ Slack  │     │           │
│  │  │Adapter │ │Adapter │ │Adapter │ │Adapter │ │Adapter │     │           │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘     │           │
│  └──────────────────────────────────────────────────────────────┘           │
│                                    │                                        │
│  ┌─────────────────────────────────┼───────────────────────────────────┐   │
│  │                          Skill Layer                                 │   │
│  │                                 │                                    │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │Coralogix│ │ Grafana │ │Datadog  │ │  AWS    │ │ Jaeger  │ ...    │   │
│  │  │ Skill   │ │ Skill   │ │ Skill   │ │ Skill   │ │ Skill   │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  │                                                                      │   │
│  │  50+ Skills: Observability, Infrastructure, Databases, Platform     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     ▼
                        ┌───────────────────────┐
                        │   AutoSRE V2 Core     │
                        └───────────────────────┘
```

### 2.3 Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Investigation Data Flow                              │
└─────────────────────────────────────────────────────────────────────────────┘

   [1] Alert Ingestion
        │
        ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Alert Source (Prometheus/Alertmanager/PagerDuty/Manual)                │
   │  ────────────────────────────────────────────────────────────────────── │
   │  {                                                                       │
   │    "name": "HighErrorRate",                                             │
   │    "service": "payment-service",                                        │
   │    "severity": "critical",                                              │
   │    "description": "Error rate > 5% for 10 minutes"                      │
   │  }                                                                       │
   └─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   [2] Context Enrichment (Parallel)
        │
        ├──► Memory System ──► "Similar incident 3 weeks ago: DB connection pool"
        │
        └──► Knowledge Graph ──► "payment-service depends on: postgres-primary,
                                   redis-cache, user-service"
        │
        ▼
   [3] Planning Phase
        │
        ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Planner Agent Output                                                   │
   │  ────────────────────────────────────────────────────────────────────── │
   │  Hypotheses:                                                            │
   │  1. [HIGH] Database connection exhaustion (test with: kubernetes, logs) │
   │  2. [MED]  Upstream service degradation (test with: metrics, traces)    │
   │  3. [LOW]  Recent deployment regression (test with: kubernetes, metrics)│
   │                                                                          │
   │  Dispatching: kubernetes, metrics, log_analysis, traces                 │
   └─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   [4] Parallel Investigation (Send() fan-out)
        │
        ├──► Kubernetes Agent ──► Pod restarts, OOMKilled events, resource limits
        ├──► Metrics Agent ────► Error rate spike, latency P99, connection pool
        ├──► Log Agent ────────► Stack traces, timeout errors, connection refused
        └──► Traces Agent ─────► Slow spans, error traces, dependency failures
        │
        ▼
   [5] Synthesis & Decision
        │
        ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Synthesizer Decision                                                   │
   │  ────────────────────────────────────────────────────────────────────── │
   │  sufficient_evidence: true                                              │
   │  confidence: 0.92                                                       │
   │  summary: "Root cause identified: PostgreSQL connection pool exhausted  │
   │           due to connection leak after deployment v2.3.1"               │
   └─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   [6] Report Generation & Memory Storage
        │
        ├──► Structured Report (JSON) ──► API Response
        ├──► Human-Readable Writeup ───► Slack/Web UI
        └──► Episode Storage ──────────► Memory System (for future investigations)
```

---

## 3. Components

### 3.1 CLI

The AutoSRE CLI provides command-line access to all platform capabilities.

#### 3.1.1 Installation

```bash
# Install via pip
pip install autosre-cli

# Or via Homebrew (macOS)
brew install autosre/tap/autosre

# Or via Docker
docker pull autosre/cli:latest
```

#### 3.1.2 Commands and Subcommands

```
autosre
├── investigate          # Start or manage investigations
│   ├── start            # Start a new investigation
│   ├── status           # Check investigation status
│   ├── list             # List recent investigations
│   └── cancel           # Cancel a running investigation
│
├── alerts               # Alert management
│   ├── list             # List active alerts
│   ├── ack              # Acknowledge an alert
│   ├── silence          # Silence alerts matching criteria
│   └── sync             # Sync alerts from external sources
│
├── runbooks             # Runbook management
│   ├── list             # List available runbooks
│   ├── show             # Show runbook details
│   ├── run              # Execute a runbook
│   └── create           # Create a new runbook
│
├── memory               # Memory system operations
│   ├── search           # Search past episodes
│   ├── episodes         # List recent episodes
│   └── strategies       # View generated strategies
│
├── config               # Configuration management
│   ├── show             # Show current config
│   ├── set              # Set configuration values
│   └── validate         # Validate configuration
│
├── integrations         # Integration management
│   ├── list             # List configured integrations
│   ├── test             # Test integration connectivity
│   └── configure        # Configure an integration
│
└── server               # Server management (self-hosted)
    ├── start            # Start the API server
    ├── stop             # Stop the API server
    └── status           # Check server status
```

#### 3.1.3 Usage Examples

```bash
# Start an investigation from an alert
autosre investigate start \
  --alert "HighErrorRate" \
  --service "payment-service" \
  --severity critical \
  --description "Error rate above 5% for 10 minutes"

# Start investigation from PagerDuty incident
autosre investigate start --pagerduty-incident PD12345

# Start investigation with JSON alert payload
autosre investigate start --json '{
  "name": "PodCrashLooping",
  "service": "checkout-service",
  "namespace": "production",
  "severity": "high"
}'

# Stream investigation progress
autosre investigate start --stream \
  --prompt "Why is payment-service returning 500 errors?"

# Check investigation status
autosre investigate status --id inv_abc123

# List recent investigations
autosre investigate list --limit 10 --status completed

# Search memory for similar incidents
autosre memory search "database connection timeout"

# Run a remediation runbook
autosre runbooks run \
  --name "restart-deployment" \
  --namespace production \
  --deployment payment-service \
  --dry-run

# Execute runbook with approval
autosre runbooks run \
  --name "scale-deployment" \
  --replicas 5 \
  --approval-required

# Configure Prometheus integration
autosre integrations configure prometheus \
  --url http://prometheus:9090 \
  --auth-type bearer \
  --token $PROM_TOKEN

# Test all integrations
autosre integrations test --all

# Validate configuration
autosre config validate --file autosre.yaml
```

### 3.2 API Server

The API server provides RESTful and streaming interfaces for all AutoSRE operations.

#### 3.2.1 Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/investigate` | Start a new investigation (SSE stream) |
| `GET` | `/investigations` | List investigations |
| `GET` | `/investigations/{id}` | Get investigation details |
| `DELETE` | `/investigations/{id}` | Cancel investigation |
| `POST` | `/alerts` | Create/ingest alert |
| `GET` | `/alerts` | List alerts |
| `PATCH` | `/alerts/{id}` | Update alert (ack/resolve) |
| `POST` | `/runbooks/{id}/execute` | Execute a runbook |
| `GET` | `/runbooks` | List runbooks |
| `GET` | `/memory/episodes` | List memory episodes |
| `POST` | `/memory/search` | Search memory |
| `GET` | `/config/me/effective` | Get effective team config |
| `PUT` | `/config/me` | Update team config |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |

#### 3.2.2 Authentication

AutoSRE supports multiple authentication methods:

**1. API Token (Team Token)**
```bash
curl -H "Authorization: Bearer team_abc123..." \
  https://autosre.example.com/api/v1/investigate
```

**2. OIDC/OAuth2**
```bash
curl -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  https://autosre.example.com/api/v1/investigate
```

**3. Admin Token (for admin operations)**
```bash
curl -H "Authorization: Bearer admin_xyz789..." \
  https://autosre.example.com/api/v1/admin/orgs/myorg/nodes
```

Configuration:
```yaml
auth:
  team_auth_mode: token  # token | oidc | both
  admin_auth_mode: both  # token | oidc | both
  oidc:
    enabled: true
    issuer: https://auth.example.com
    audience: autosre-api
    jwks_url: https://auth.example.com/.well-known/jwks.json
```

#### 3.2.3 WebSocket Support

Real-time updates via WebSocket:

```javascript
// Connect to WebSocket
const ws = new WebSocket('wss://autosre.example.com/ws/investigations');

// Authenticate
ws.send(JSON.stringify({
  type: 'auth',
  token: 'team_abc123...'
}));

// Subscribe to investigation updates
ws.send(JSON.stringify({
  type: 'subscribe',
  investigation_id: 'inv_xyz789'
}));

// Receive events
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case 'thought':
      console.log(`[${data.agent}] ${data.text}`);
      break;
    case 'tool_start':
      console.log(`Starting tool: ${data.name}`);
      break;
    case 'tool_end':
      console.log(`Tool ${data.name} completed: ${data.output}`);
      break;
    case 'result':
      console.log(`Investigation complete: ${data.summary}`);
      break;
  }
};
```

#### 3.2.4 Server-Sent Events (SSE)

For investigation streaming:

```bash
curl -N \
  -H "Authorization: Bearer team_abc123..." \
  -H "Accept: text/event-stream" \
  -d '{"prompt": "Why is payment-service down?"}' \
  https://autosre.example.com/api/v1/investigate
```

SSE Event Types:
- `thought`: Agent reasoning/thinking text
- `tool_start`: Tool invocation started
- `tool_end`: Tool invocation completed
- `result`: Final investigation result
- `error`: Error occurred

### 3.3 Web UI

The Web UI provides a comprehensive dashboard for managing investigations, viewing results, and configuring the system.

#### 3.3.1 Pages and Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Overview of active investigations, recent alerts, system health |
| `/investigations` | Investigation List | All investigations with filtering and search |
| `/investigations/{id}` | Investigation Detail | Full investigation with timeline, tool traces, report |
| `/investigations/new` | New Investigation | Start investigation from prompt or alert |
| `/alerts` | Alert Manager | Active alerts, acknowledgment, silencing |
| `/alerts/{id}` | Alert Detail | Alert details with linked investigations |
| `/memory` | Memory Browser | Search and browse past investigation episodes |
| `/memory/episodes/{id}` | Episode Detail | Full episode with tools, findings, report |
| `/memory/strategies` | Strategies | LLM-generated investigation strategies |
| `/runbooks` | Runbook Library | Available runbooks with execution history |
| `/runbooks/{id}` | Runbook Detail | Runbook steps, variables, execution form |
| `/runbooks/{id}/executions` | Execution History | Past executions with status and logs |
| `/config` | Team Configuration | Edit team config (agents, skills, integrations) |
| `/config/integrations` | Integration Setup | Configure and test integrations |
| `/admin` | Admin Panel | Organization management (admin only) |
| `/admin/orgs/{id}` | Org Management | Org tree, teams, tokens |
| `/admin/audit` | Audit Log | All configuration changes with diffs |
| `/settings` | User Settings | Preferences, notifications, API tokens |

#### 3.3.2 Features

**Investigation Viewer**
- Real-time streaming of agent thoughts and tool calls
- Expandable tool call traces with input/output
- Timeline view of investigation progression
- Structured report with root cause, findings, recommendations
- Copy/share investigation link

**Memory Browser**
- Full-text search across past investigations
- Filter by service, severity, alert type, date range
- Similar episode matching visualization
- Strategy generation from episode patterns

**Runbook Management**
- Visual runbook builder
- Variable interpolation with validation
- Dry-run mode for safe testing
- Approval workflow integration
- Execution logs with step-by-step status

**Configuration Editor**
- Monaco editor with YAML/JSON validation
- Live preview of effective config
- Diff view for changes
- Rollback to previous versions
- Audit trail for all changes

**Dashboard Widgets**
- Active investigations count
- MTTI (Mean Time to Investigate) trends
- Most common root causes (last 30 days)
- Agent performance metrics
- Integration health status

### 3.4 Multi-Agent Core

The Multi-Agent Core is the heart of AutoSRE V2, implementing intelligent investigation through specialized agents.

#### 3.4.1 Agent Types

**Triage Agent**
- First-line classification of incoming alerts
- Severity assessment and prioritization
- Duplicate/related alert correlation
- Initial hypothesis generation
- Routing to appropriate investigation path

**Investigation Agents (Subagents)**

| Agent | Domain | Key Capabilities |
|-------|--------|------------------|
| `kubernetes` | Kubernetes infrastructure | Pod status, events, logs, resource utilization, deployments |
| `metrics` | Metrics/Observability | PromQL queries, metric correlation, anomaly detection |
| `log_analysis` | Log analysis | Pattern matching, error extraction, timeline reconstruction |
| `traces` | Distributed tracing | Span analysis, latency breakdown, error traces |
| `database` | Database investigation | Connection pools, query performance, replication lag |
| `network` | Network troubleshooting | DNS, connectivity, load balancer health |
| `deployment` | Deployment correlation | Recent changes, rollout status, config diff |
| `security` | Security analysis | Auth failures, rate limiting, suspicious patterns |

**Planner Agent**
- Receives alert context and memory/KG enrichment
- Generates ranked hypotheses with supporting evidence
- Selects which investigation agents to dispatch
- Allocates investigation budget per agent

**Synthesizer Agent**
- Combines findings from all investigation agents
- Evaluates evidence sufficiency (confidence scoring)
- Decides: more investigation needed OR proceed to writeup
- Provides feedback for next iteration if needed

**Remediation Agent**
- Identifies applicable runbooks based on root cause
- Validates runbook prerequisites
- Executes remediation steps (with approval if required)
- Monitors remediation success

#### 3.4.2 Agent Coordination

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agent Coordination Flow                             │
└─────────────────────────────────────────────────────────────────────────────┘

   Alert Input
       │
       ▼
 ┌───────────┐
 │  Triage   │────► Classification + Priority
 │   Agent   │────► Initial Hypotheses
 └─────┬─────┘
       │
       ▼
 ┌───────────┐     ┌──────────────────────────────────────────────────────┐
 │  Planner  │────►│ Investigation Plan                                   │
 │   Agent   │     │ • Hypothesis 1: DB pool exhaustion [kubernetes, logs]│
 └─────┬─────┘     │ • Hypothesis 2: Upstream timeout [metrics, traces]   │
       │           └──────────────────────────────────────────────────────┘
       │
       ▼
   Send() Fan-Out ─────────────────────────────────────────┐
       │                                                    │
       ├─────────────────┬─────────────────┬────────────────┤
       ▼                 ▼                 ▼                ▼
 ┌───────────┐     ┌───────────┐     ┌───────────┐    ┌───────────┐
 │Kubernetes │     │  Metrics  │     │   Logs    │    │  Traces   │
 │   Agent   │     │   Agent   │     │   Agent   │    │   Agent   │
 │           │     │           │     │           │    │           │
 │ ReAct     │     │ ReAct     │     │ ReAct     │    │ ReAct     │
 │ Loop      │     │ Loop      │     │ Loop      │    │ Loop      │
 │ (tools)   │     │ (tools)   │     │ (tools)   │    │ (tools)   │
 └─────┬─────┘     └─────┬─────┘     └─────┬─────┘    └─────┬─────┘
       │                 │                 │                │
       │    Findings     │    Findings     │   Findings     │
       └────────┬────────┴────────┬────────┴───────┬────────┘
                │                 │                │
                └─────────────────┼────────────────┘
                                  ▼
                          ┌───────────┐
                          │Synthesizer│────► Evidence Sufficient?
                          │   Agent   │
                          └─────┬─────┘
                                │
                   ┌────────────┴────────────┐
                   ▼                         ▼
            [Need More Data]          [Sufficient Evidence]
                   │                         │
                   ▼                         ▼
            Back to Planner            ┌───────────┐
            (iteration++)              │  Writeup  │────► Final Report
                                       │   Agent   │
                                       └─────┬─────┘
                                             │
                                             ▼
                                       ┌───────────┐
                                       │Remediation│────► Runbook Execution
                                       │   Agent   │      (if applicable)
                                       └───────────┘
```

#### 3.4.3 Observation Collection

Each agent collects observations during investigation:

```python
@dataclass
class Observation:
    """Single observation collected during investigation."""
    agent_id: str           # Which agent collected this
    timestamp: datetime     # When collected
    source: str             # Tool or method used
    observation_type: str   # "metric", "log", "event", "trace", "status"
    content: str            # The actual finding
    confidence: float       # 0.0-1.0 confidence in this observation
    supporting_data: dict   # Raw data backing the observation
    hypothesis_ref: str     # Which hypothesis this supports/refutes
```

Observations are aggregated by the Synthesizer to determine:
- Which hypotheses are supported by evidence
- Which hypotheses can be ruled out
- What gaps remain in the investigation

### 3.5 Integrations

AutoSRE V2 supports 50+ production integrations via a skills-based architecture.

#### 3.5.1 Prometheus

**Capabilities:**
- Execute PromQL queries
- Fetch metric values over time ranges
- Detect anomalies using moving averages
- Query recording rules and alerts

**Configuration:**
```yaml
integrations:
  prometheus:
    enabled: true
    url: http://prometheus:9090
    auth:
      type: bearer  # none | basic | bearer
      token: ${PROMETHEUS_TOKEN}
    tls:
      insecure_skip_verify: false
      ca_cert: /etc/ssl/certs/prometheus-ca.crt
```

**Example Usage by Agent:**
```python
# Metrics agent queries error rate
result = prometheus.query(
    'sum(rate(http_requests_total{status=~"5.."}[5m])) '
    '/ sum(rate(http_requests_total[5m]))'
)
```

#### 3.5.2 Alertmanager

**Capabilities:**
- Fetch active alerts
- Correlate alerts with investigations
- Create silences
- Get alert history

**Configuration:**
```yaml
integrations:
  alertmanager:
    enabled: true
    url: http://alertmanager:9093
    auth:
      type: basic
      username: admin
      password: ${ALERTMANAGER_PASSWORD}
```

**Webhook Receiver:**
```yaml
# alertmanager.yml
receivers:
  - name: autosre
    webhook_configs:
      - url: http://autosre:8000/api/v1/webhooks/alertmanager
        send_resolved: true
```

#### 3.5.3 Kubernetes

**Capabilities:**
- Get pod status, events, logs
- Check deployment status and history
- Inspect resource utilization
- Query ConfigMaps and Secrets (metadata only)
- Check node health
- Analyze recent rollouts

**Configuration:**
```yaml
integrations:
  kubernetes:
    enabled: true
    auth:
      type: kubeconfig  # kubeconfig | in_cluster | service_account
      kubeconfig_path: ~/.kube/config
      context: production
    namespaces:
      allowed: ["production", "staging"]
      denied: ["kube-system"]
```

**Agent Tools:**
```python
# Get pod status
pods = k8s.get_pods(namespace="production", label_selector="app=payment-service")

# Get recent events
events = k8s.get_events(namespace="production", involved_object="payment-service")

# Get pod logs
logs = k8s.get_logs(
    namespace="production",
    pod="payment-service-abc123",
    container="main",
    since="10m",
    tail=500
)

# Check deployment
deployment = k8s.get_deployment(namespace="production", name="payment-service")
```

#### 3.5.4 PagerDuty

**Capabilities:**
- Receive incident webhooks
- Fetch incident details
- Update incident status
- Add investigation notes
- Link investigations to incidents

**Configuration:**
```yaml
integrations:
  pagerduty:
    enabled: true
    api_key: ${PAGERDUTY_API_KEY}
    service_id: PXXXXXX
    webhook_url: http://autosre:8000/api/v1/webhooks/pagerduty
```

**Webhook Events:**
- `incident.triggered` → Start investigation
- `incident.acknowledged` → Update investigation priority
- `incident.resolved` → Close investigation

#### 3.5.5 Slack

**Capabilities:**
- Receive @mentions to start investigations
- Post investigation updates to channels
- Send DMs with results
- Interactive buttons for runbook approval

**Configuration:**
```yaml
integrations:
  slack:
    enabled: true
    bot_token: ${SLACK_BOT_TOKEN}
    app_token: ${SLACK_APP_TOKEN}  # For Socket Mode
    signing_secret: ${SLACK_SIGNING_SECRET}
    channels:
      default: "#incidents"
      alerts: "#alerts"
```

**Socket Mode Setup:**
```bash
# Slack app manifest
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - channels:history
      - files:read
      - reactions:write

settings:
  socket_mode_enabled: true
  event_subscriptions:
    bot_events:
      - app_mention
      - message.channels
```

#### 3.5.6 Additional Integrations

| Category | Integrations |
|----------|--------------|
| **Observability** | Datadog, Grafana, New Relic, Splunk, Elasticsearch, Loki, Coralogix, VictoriaMetrics, Jaeger, Honeycomb, Sentry |
| **Incident Management** | PagerDuty, Opsgenie, Incident.io, FireHydrant, Blameless |
| **Cloud Providers** | AWS (EC2, CloudWatch, ECS, Lambda), GCP, Azure |
| **Databases** | PostgreSQL, MySQL, Redis, MongoDB, Snowflake, BigQuery |
| **Streaming** | Kafka, RabbitMQ, AWS SQS |
| **Platform** | Vercel, Netlify, Heroku, Render |
| **Source Control** | GitHub, GitLab, Bitbucket |
| **Project Management** | Jira, Linear, Notion, ClickUp |

---

## 4. Data Models

### 4.1 Alert

```python
@dataclass
class Alert:
    """Incoming alert that triggers an investigation."""
    id: str                     # Unique alert identifier
    name: str                   # Alert name/title
    service: str                # Affected service name
    severity: Severity          # critical | high | medium | low | info
    status: AlertStatus         # firing | acknowledged | resolved | silenced
    description: str            # Human-readable description
    source: str                 # Source system (prometheus, pagerduty, etc.)
    source_id: str              # ID in source system
    labels: Dict[str, str]      # Additional labels/tags
    annotations: Dict[str, str] # Annotations (runbook, dashboard links)
    started_at: datetime        # When alert started firing
    ended_at: Optional[datetime]# When alert resolved (if resolved)
    fingerprint: str            # Unique fingerprint for deduplication
    created_at: datetime        # When ingested into AutoSRE
    updated_at: datetime        # Last update time

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AlertStatus(str, Enum):
    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SILENCED = "silenced"
```

### 4.2 Investigation

```python
@dataclass
class Investigation:
    """An investigation instance with all related data."""
    id: str                         # inv_xxx unique identifier
    thread_id: str                  # LangGraph thread ID
    alert_id: Optional[str]         # Linked alert (if from alert)
    prompt: str                     # Original investigation prompt
    status: InvestigationStatus     # pending | running | completed | failed | cancelled
    
    # Agent execution
    iteration: int                  # Current iteration (max usually 3)
    max_iterations: int             # Maximum iterations allowed
    selected_agents: List[str]      # Agents dispatched
    agent_states: Dict[str, AgentState]  # State per agent
    
    # Context
    memory_context: MemoryContext   # Similar episodes, strategies
    kg_context: KGContext           # Service topology info
    team_config: Dict               # Effective team configuration
    
    # Results
    hypotheses: List[Hypothesis]    # Generated hypotheses
    observations: List[Observation] # Collected observations
    conclusion: str                 # Final conclusion text
    structured_report: Report       # Structured investigation report
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    tool_calls_count: int
    created_by: str                 # User/token that initiated

class InvestigationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AgentState:
    """State for a single investigation agent."""
    agent_id: str
    status: str                     # running | completed | error
    react_loops: int                # Number of ReAct iterations
    duration_seconds: float
    findings: str                   # Agent's findings summary
    tool_calls: List[ToolCall]      # Tools invoked by this agent
```

### 4.3 Observation

```python
@dataclass
class Observation:
    """Single observation collected during investigation."""
    id: str                     # Unique observation ID
    investigation_id: str       # Parent investigation
    agent_id: str               # Collecting agent
    timestamp: datetime         # When observed
    
    # Observation details
    observation_type: ObservationType
    source: str                 # Tool or method used
    content: str                # Human-readable description
    supporting_data: Dict       # Raw data (metrics, logs, etc.)
    
    # Analysis
    confidence: float           # 0.0-1.0
    hypothesis_ref: Optional[str]  # Related hypothesis ID
    relevance: str              # supports | refutes | neutral
    
class ObservationType(str, Enum):
    METRIC = "metric"           # Numeric metric observation
    LOG = "log"                 # Log entry or pattern
    EVENT = "event"             # Kubernetes event, deployment, etc.
    TRACE = "trace"             # Distributed trace finding
    STATUS = "status"           # Service/pod/resource status
    CONFIGURATION = "configuration"  # Config change observation
```

### 4.4 Action

```python
@dataclass
class Action:
    """An action taken during investigation or remediation."""
    id: str                     # Unique action ID
    investigation_id: str       # Parent investigation
    action_type: ActionType     # tool_call | runbook_step | manual
    
    # Execution details
    name: str                   # Action name
    input: Dict                 # Input parameters
    output: Optional[Dict]      # Output/result
    status: ActionStatus        # pending | running | success | failed
    error_message: Optional[str]
    
    # Metadata
    agent_id: str               # Executing agent
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: int
    sequence_number: int        # Order in investigation

class ActionType(str, Enum):
    TOOL_CALL = "tool_call"
    RUNBOOK_STEP = "runbook_step"
    MANUAL = "manual"
    APPROVAL = "approval"

class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"
```

### 4.5 Runbook

```python
@dataclass
class Runbook:
    """Automated remediation runbook."""
    id: str                     # Unique runbook ID
    name: str                   # Human-readable name
    description: str            # What this runbook does
    version: str                # Semantic version
    
    # Targeting
    services: List[str]         # Applicable services
    alert_types: List[str]      # Applicable alert types
    root_causes: List[str]      # Root causes this addresses
    
    # Definition
    steps: List[RunbookStep]    # Ordered steps
    variables: List[Variable]   # Required variables/inputs
    preconditions: List[str]    # Conditions that must be true
    
    # Execution config
    requires_approval: bool     # Human approval needed
    approval_timeout_minutes: int
    rollback_steps: List[RunbookStep]  # Rollback if failed
    dry_run_supported: bool
    
    # Metadata
    created_by: str
    created_at: datetime
    updated_at: datetime
    execution_count: int
    success_rate: float         # Historical success rate

@dataclass
class RunbookStep:
    """Single step in a runbook."""
    id: str
    name: str
    description: str
    action: str                 # Tool or command to execute
    parameters: Dict            # Parameters (may include variable refs)
    timeout_seconds: int
    on_failure: str             # continue | abort | rollback
    condition: Optional[str]    # Condition expression to run this step

@dataclass
class Variable:
    """Runbook variable definition."""
    name: str
    description: str
    type: str                   # string | number | boolean | select
    required: bool
    default: Optional[str]
    options: Optional[List[str]]  # For select type
    validation: Optional[str]   # Regex or expression
```

---

## 5. Deployment

### 5.1 Docker Compose

For local development and small deployments:

```yaml
# docker-compose.yml
version: '3.8'

services:
  # PostgreSQL - Backend storage
  postgres:
    image: postgres:15-alpine
    container_name: autosre-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: autosre
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-localdev}
      POSTGRES_DB: autosre
    ports:
      - "5433:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U autosre"]
      interval: 5s
      timeout: 5s
      retries: 10

  # Neo4j - Knowledge graph
  neo4j:
    image: neo4j:5-community
    container_name: autosre-neo4j
    restart: unless-stopped
    ports:
      - "7475:7474"  # Browser
      - "7688:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-localdev}
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j-data:/data
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      timeout: 5s
      retries: 5

  # LiteLLM Proxy - Multi-provider LLM routing
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: autosre-litellm
    restart: unless-stopped
    environment:
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    volumes:
      - ./litellm_config.yaml:/app/config.yaml:ro
    command: ["--config", "/app/config.yaml", "--port", "4000"]
    ports:
      - "4001:4000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:4000/health/readiness')"]
      interval: 10s
      timeout: 15s
      retries: 10

  # Config Service - Team config, tokens, audit
  config-service:
    build:
      context: ./config-service
      dockerfile: Dockerfile
    container_name: autosre-config-service
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+psycopg2://autosre:${POSTGRES_PASSWORD:-localdev}@postgres:5432/autosre
      TOKEN_PEPPER: ${TOKEN_PEPPER:-local-pepper-must-be-32-chars!!}
      ADMIN_TOKEN: ${ADMIN_TOKEN:-local-admin-token}
      ADMIN_AUTH_MODE: token
      TEAM_AUTH_MODE: token
    ports:
      - "8081:8080"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  # SRE Agent - Core investigation engine
  sre-agent:
    build:
      context: ./sre-agent
      dockerfile: Dockerfile
    container_name: autosre-sre-agent
    restart: unless-stopped
    environment:
      CONFIG_SERVICE_URL: http://config-service:8080
      LITELLM_BASE_URL: http://litellm:4000/v1
      LITELLM_API_KEY: ${LITELLM_API_KEY:-sk-placeholder}
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USERNAME: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD:-localdev}
      LLM_MODEL: ${LLM_MODEL:-claude-sonnet-4-20250514}
      AGENT_TIMEOUT_SECONDS: 900
    ports:
      - "8001:8000"
    depends_on:
      config-service:
        condition: service_healthy
      litellm:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Web UI - Admin console
  web-ui:
    build:
      context: ./web-ui
      dockerfile: Dockerfile
    container_name: autosre-web-ui
    restart: unless-stopped
    environment:
      CONFIG_SERVICE_URL: http://config-service:8080
      AGENT_SERVICE_URL: http://sre-agent:8000
      WEB_UI_COOKIE_SECURE: "0"
    ports:
      - "3002:3000"
    depends_on:
      config-service:
        condition: service_healthy

  # Slack Bot (optional)
  slack-bot:
    build:
      context: ./slack-bot
      dockerfile: Dockerfile
    container_name: autosre-slack-bot
    restart: unless-stopped
    environment:
      SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN}
      SLACK_APP_TOKEN: ${SLACK_APP_TOKEN}
      SRE_AGENT_URL: http://sre-agent:8000
      CONFIG_SERVICE_URL: http://config-service:8080
    depends_on:
      - sre-agent
    profiles:
      - slack

volumes:
  postgres-data:
  neo4j-data:
```

**Quick Start:**
```bash
# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Start core services
docker compose up -d

# Start with Slack integration
docker compose --profile slack up -d

# View logs
docker compose logs -f sre-agent

# Stop all services
docker compose down
```

### 5.2 Kubernetes / Helm

For production deployments:

```yaml
# values.yaml
global:
  imageRegistry: ghcr.io/autosre
  imageTag: v2.0.0

# PostgreSQL (or use external RDS)
postgresql:
  enabled: true
  auth:
    postgresPassword: ""  # Generated if empty
    database: autosre
  primary:
    persistence:
      size: 20Gi

# Neo4j Knowledge Graph
neo4j:
  enabled: true
  neo4j:
    password: ""  # Generated if empty
  volumes:
    data:
      size: 10Gi

# LiteLLM Proxy
litellm:
  enabled: true
  config:
    model_list:
      - model_name: claude-sonnet
        litellm_params:
          model: openrouter/anthropic/claude-sonnet-4
          api_key: ${OPENROUTER_API_KEY}
  resources:
    requests:
      cpu: 200m
      memory: 512Mi

# Config Service
configService:
  replicaCount: 2
  resources:
    requests:
      cpu: 200m
      memory: 256Mi
  env:
    ADMIN_AUTH_MODE: oidc
    TEAM_AUTH_MODE: both
  oidc:
    enabled: true
    issuer: https://auth.example.com
    audience: autosre

# SRE Agent
sreAgent:
  replicaCount: 3
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2
      memory: 2Gi
  env:
    AGENT_TIMEOUT_SECONDS: "900"
    LLM_MODEL: claude-sonnet-4-20250514
  integrations:
    prometheus:
      enabled: true
      url: http://prometheus:9090
    kubernetes:
      enabled: true
      # Uses in-cluster config

# Web UI
webUI:
  replicaCount: 2
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: autosre.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: autosre-tls
        hosts:
          - autosre.example.com

# Slack Bot
slackBot:
  enabled: false
  secrets:
    botToken: ""
    appToken: ""

# Monitoring
monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
  grafanaDashboard:
    enabled: true
```

**Installation:**
```bash
# Add Helm repository
helm repo add autosre https://charts.autosre.io
helm repo update

# Install with custom values
helm install autosre autosre/autosre \
  --namespace autosre \
  --create-namespace \
  -f values.yaml \
  --set global.imageTag=v2.0.0

# Upgrade
helm upgrade autosre autosre/autosre \
  --namespace autosre \
  -f values.yaml

# Check status
kubectl get pods -n autosre
kubectl get ingress -n autosre
```

### 5.3 Configuration

**Environment Variables:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `TOKEN_PEPPER` | Yes | - | Secret for token hashing (min 32 chars) |
| `ADMIN_TOKEN` | No | - | Admin API token |
| `OPENROUTER_API_KEY` | No* | - | OpenRouter API key |
| `ANTHROPIC_API_KEY` | No* | - | Anthropic API key |
| `OPENAI_API_KEY` | No* | - | OpenAI API key |
| `LLM_MODEL` | No | claude-sonnet-4-20250514 | Default LLM model |
| `NEO4J_URI` | No | bolt://localhost:7687 | Neo4j connection |
| `NEO4J_USERNAME` | No | neo4j | Neo4j username |
| `NEO4J_PASSWORD` | No | - | Neo4j password |
| `AGENT_TIMEOUT_SECONDS` | No | 900 | Max investigation time |
| `AGENT_MAX_TURNS` | No | 25 | Max ReAct loops per agent |
| `SLACK_BOT_TOKEN` | No | - | Slack bot token |
| `SLACK_APP_TOKEN` | No | - | Slack app token (Socket Mode) |

*At least one LLM provider API key required.

**Configuration File (autosre.yaml):**

```yaml
# autosre.yaml - Team configuration
version: "2"

# Agent configuration
agents:
  planner:
    enabled: true
    model:
      name: claude-sonnet-4-20250514
      temperature: 0.3
      max_tokens: 4000
    max_turns: 3
  
  investigation:
    sub_agents:
      kubernetes: true
      metrics: true
      log_analysis: true
      traces: true
      database: false
      network: false
    
    sub_agents_config:
      kubernetes:
        max_turns: 30
        skills:
          enabled: ["kubernetes", "docker"]
      metrics:
        max_turns: 25
        skills:
          enabled: ["prometheus", "grafana"]
      log_analysis:
        max_turns: 20
        skills:
          enabled: ["elasticsearch", "loki"]
  
  synthesizer:
    model:
      temperature: 0.2
  
  writeup:
    model:
      temperature: 0.4
      max_tokens: 8000

# Memory system
memory:
  enabled: true
  similarity_threshold: 0.7
  max_episodes_per_query: 5
  strategy_generation:
    enabled: true
    min_similar_episodes: 2

# Knowledge graph
knowledge_graph:
  enabled: true
  topology_depth: 3
  blast_radius_enabled: true

# Integrations
integrations:
  prometheus:
    enabled: true
    url: http://prometheus:9090
  alertmanager:
    enabled: true
    url: http://alertmanager:9093
  kubernetes:
    enabled: true
    namespaces:
      allowed: ["production", "staging"]
  pagerduty:
    enabled: false
  slack:
    enabled: true
    default_channel: "#incidents"

# Runbooks
runbooks:
  enabled: true
  require_approval_by_default: true
  approval_timeout_minutes: 30
  dry_run_by_default: true

# Skills
skills:
  enabled: ["*"]
  disabled: []
```

---

## 6. API Reference

### 6.1 Investigation API

#### Start Investigation

```http
POST /api/v1/investigate
Content-Type: application/json
Authorization: Bearer <team_token>
Accept: text/event-stream

{
  "prompt": "Why is payment-service returning 500 errors?",
  "thread_id": "optional-thread-id",
  "images": [
    {
      "type": "base64",
      "media_type": "image/png",
      "data": "iVBORw0KGgo..."
    }
  ]
}
```

**Response (SSE Stream):**
```
event: thought
data: {"text": "Analyzing the payment-service error rate...", "agent_name": "planner"}

event: tool_start
data: {"name": "prometheus_query", "tool_use_id": "tc_123", "input": {"query": "..."}}

event: tool_end
data: {"name": "prometheus_query", "tool_use_id": "tc_123", "success": true, "output": "..."}

event: result
data: {"text": "Root cause identified...", "success": true, "structured_report": {...}}
```

#### List Investigations

```http
GET /api/v1/investigations?status=completed&limit=10&offset=0
Authorization: Bearer <team_token>
```

**Response:**
```json
{
  "investigations": [
    {
      "id": "inv_abc123",
      "prompt": "Why is payment-service down?",
      "status": "completed",
      "created_at": "2025-07-18T10:00:00Z",
      "completed_at": "2025-07-18T10:05:32Z",
      "duration_seconds": 332,
      "tool_calls_count": 47
    }
  ],
  "total": 156,
  "limit": 10,
  "offset": 0
}
```

#### Get Investigation Details

```http
GET /api/v1/investigations/{investigation_id}
Authorization: Bearer <team_token>
```

**Response:**
```json
{
  "id": "inv_abc123",
  "thread_id": "thread_xyz",
  "prompt": "Why is payment-service down?",
  "status": "completed",
  "iteration": 1,
  "max_iterations": 3,
  "selected_agents": ["kubernetes", "metrics", "log_analysis"],
  "hypotheses": [
    {
      "hypothesis": "Database connection pool exhaustion",
      "priority": "high",
      "agents_to_test": ["kubernetes", "metrics"]
    }
  ],
  "conclusion": "Root cause: PostgreSQL connection pool exhausted...",
  "structured_report": {
    "root_cause": "Connection leak in payment-service v2.3.1",
    "evidence": [...],
    "recommendations": [...],
    "severity": "high"
  },
  "agent_states": {
    "kubernetes": {
      "status": "completed",
      "findings": "Found 3 pod restarts...",
      "react_loops": 12,
      "duration_seconds": 45.2
    }
  },
  "tool_calls": [
    {
      "id": "tc_001",
      "tool_name": "k8s_get_pods",
      "agent_name": "kubernetes",
      "tool_input": {"namespace": "production"},
      "tool_output": "...",
      "started_at": "2025-07-18T10:00:05Z",
      "duration_ms": 234,
      "status": "success",
      "sequence_number": 1
    }
  ],
  "created_at": "2025-07-18T10:00:00Z",
  "completed_at": "2025-07-18T10:05:32Z",
  "duration_seconds": 332
}
```

### 6.2 Alerts API

#### Create Alert

```http
POST /api/v1/alerts
Content-Type: application/json
Authorization: Bearer <team_token>

{
  "name": "HighErrorRate",
  "service": "payment-service",
  "severity": "critical",
  "description": "Error rate above 5% for 10 minutes",
  "labels": {
    "namespace": "production",
    "team": "payments"
  },
  "annotations": {
    "runbook": "https://wiki.example.com/runbooks/high-error-rate"
  }
}
```

**Response:**
```json
{
  "id": "alert_xyz789",
  "name": "HighErrorRate",
  "service": "payment-service",
  "severity": "critical",
  "status": "firing",
  "created_at": "2025-07-18T10:00:00Z"
}
```

#### List Alerts

```http
GET /api/v1/alerts?status=firing&severity=critical&service=payment-service
Authorization: Bearer <team_token>
```

#### Update Alert (Acknowledge/Resolve)

```http
PATCH /api/v1/alerts/{alert_id}
Content-Type: application/json
Authorization: Bearer <team_token>

{
  "status": "acknowledged"
}
```

### 6.3 Runbooks API

#### List Runbooks

```http
GET /api/v1/runbooks?service=payment-service
Authorization: Bearer <team_token>
```

**Response:**
```json
{
  "runbooks": [
    {
      "id": "rb_restart_pods",
      "name": "Restart Service Pods",
      "description": "Gracefully restart all pods for a service",
      "services": ["*"],
      "requires_approval": true,
      "dry_run_supported": true,
      "execution_count": 42,
      "success_rate": 0.95
    }
  ]
}
```

#### Execute Runbook

```http
POST /api/v1/runbooks/{runbook_id}/execute
Content-Type: application/json
Authorization: Bearer <team_token>

{
  "variables": {
    "namespace": "production",
    "deployment": "payment-service"
  },
  "dry_run": true,
  "investigation_id": "inv_abc123"
}
```

**Response:**
```json
{
  "execution_id": "exec_123",
  "runbook_id": "rb_restart_pods",
  "status": "running",
  "dry_run": true,
  "steps": [
    {
      "id": "step_1",
      "name": "Check current replica count",
      "status": "pending"
    },
    {
      "id": "step_2",
      "name": "Perform rolling restart",
      "status": "pending"
    }
  ],
  "created_at": "2025-07-18T10:10:00Z"
}
```

### 6.4 Memory API

#### Search Episodes

```http
POST /api/v1/memory/search
Content-Type: application/json
Authorization: Bearer <team_token>

{
  "query": "database connection timeout",
  "filters": {
    "service": "payment-service",
    "resolved": true
  },
  "limit": 10
}
```

**Response:**
```json
{
  "episodes": [
    {
      "id": "ep_abc123",
      "investigation_id": "inv_xyz",
      "summary": "Connection pool exhaustion due to leak in v2.3.0",
      "service": "payment-service",
      "root_cause": "Connection leak in database client",
      "resolution": "Deployed v2.3.1 with connection pooling fix",
      "severity": "critical",
      "similarity_score": 0.92,
      "created_at": "2025-07-01T08:30:00Z"
    }
  ],
  "strategies": [
    {
      "id": "strat_db_conn",
      "name": "Database Connection Issues",
      "description": "Strategy for investigating database connection problems",
      "steps": [
        "Check connection pool metrics",
        "Look for connection leak patterns in logs",
        "Verify recent deployments"
      ],
      "source_episodes": 3
    }
  ]
}
```

### 6.5 Configuration API

#### Get Effective Config

```http
GET /api/v1/config/me/effective
Authorization: Bearer <team_token>
```

**Response:**
```json
{
  "team_id": "team_payments",
  "org_id": "org_acme",
  "effective_config": {
    "agents": {
      "planner": {
        "enabled": true,
        "model": {...}
      }
    },
    "integrations": {...},
    "skills": {...}
  },
  "inheritance_chain": ["org_acme", "team_payments"]
}
```

#### Update Team Config

```http
PUT /api/v1/config/me
Content-Type: application/json
Authorization: Bearer <team_token>

{
  "agents": {
    "investigation": {
      "sub_agents": {
        "database": true
      }
    }
  }
}
```

### 6.6 Admin API

#### List Org Nodes

```http
GET /api/v1/admin/orgs/{org_id}/nodes
Authorization: Bearer <admin_token>
```

#### Create Team Token

```http
POST /api/v1/admin/orgs/{org_id}/teams/{team_id}/tokens
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "name": "CI/CD Integration",
  "expires_in_days": 365
}
```

**Response:**
```json
{
  "token_id": "tok_xyz123",
  "token": "team_abc123xyz789...",
  "name": "CI/CD Integration",
  "expires_at": "2026-07-18T00:00:00Z",
  "created_at": "2025-07-18T10:00:00Z"
}
```

#### Get Audit Log

```http
GET /api/v1/admin/orgs/{org_id}/audit?limit=50
Authorization: Bearer <admin_token>
```

### 6.7 Health & Metrics

#### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "components": {
    "database": "healthy",
    "neo4j": "healthy",
    "litellm": "healthy"
  }
}
```

#### Prometheus Metrics

```http
GET /metrics
```

**Response:**
```
# HELP autosre_investigations_total Total investigations
# TYPE autosre_investigations_total counter
autosre_investigations_total{status="completed"} 1523
autosre_investigations_total{status="failed"} 12

# HELP autosre_investigation_duration_seconds Investigation duration
# TYPE autosre_investigation_duration_seconds histogram
autosre_investigation_duration_seconds_bucket{le="60"} 234
autosre_investigation_duration_seconds_bucket{le="120"} 567

# HELP autosre_tool_calls_total Tool invocations
# TYPE autosre_tool_calls_total counter
autosre_tool_calls_total{tool="k8s_get_pods"} 4521
autosre_tool_calls_total{tool="prometheus_query"} 3892
```

---

## Appendix A: Error Codes

| Code | Description |
|------|-------------|
| `ERR_AUTH_INVALID_TOKEN` | Invalid or expired authentication token |
| `ERR_AUTH_INSUFFICIENT_PERMISSIONS` | Token lacks required permissions |
| `ERR_INVESTIGATION_NOT_FOUND` | Investigation ID does not exist |
| `ERR_INVESTIGATION_TIMEOUT` | Investigation exceeded timeout |
| `ERR_AGENT_FAILED` | Agent execution failed |
| `ERR_INTEGRATION_UNAVAILABLE` | Integration service unreachable |
| `ERR_RUNBOOK_VALIDATION` | Runbook preconditions not met |
| `ERR_RUNBOOK_APPROVAL_TIMEOUT` | Approval not received in time |
| `ERR_CONFIG_VALIDATION` | Invalid configuration |
| `ERR_RATE_LIMITED` | Too many requests |

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Agent** | An LLM-powered component that performs a specific investigation role |
| **Episode** | A stored record of a past investigation for memory/learning |
| **Hypothesis** | A potential root cause generated by the Planner agent |
| **Observation** | A single finding collected during investigation |
| **ReAct Loop** | Reasoning-Action loop where agent thinks then acts |
| **Runbook** | Automated remediation procedure with defined steps |
| **Skill** | Integration module providing tools and methodology |
| **Strategy** | LLM-generated investigation approach from past patterns |
| **Synthesis** | Process of combining multi-agent findings |

---

*Document Version: 2.0.0*  
*Last Updated: 2025-07-18*  
*Status: Draft - Pending Review*
