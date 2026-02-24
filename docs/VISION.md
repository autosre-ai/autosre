# SRE Agent — Complete Vision Document

**Author:** Sainath + Clawd  
**Created:** Feb 18, 2026  
**Status:** Phase 1 MVP Complete

---

## The Problem

You're an on-call SRE. It's 2 AM. Alert fires:

```
🚨 checkout-service: 5xx error rate > 5%
```

**What you do today (manually):**
1. Open Grafana → Check metrics (5 min)
2. Open Kibana/GCP Logs → Search errors (5 min)
3. Open GitHub → Check recent deploys (3 min)
4. Open OpenShift → Check pod health (3 min)
5. Check dependencies → Are downstream services OK? (5 min)
6. Check Akamai → Is it traffic/DDoS? (3 min)
7. Correlate all of this in your head (5 min)
8. Decide what to do (5 min)

**Total time to first action:** 30-40 minutes  
**Mental state:** Groggy, stressed, context-switching hell

---

## The Solution

**SRE Agent does all of this in 30 seconds.**

```bash
sre-agent analyze "checkout-service 5xx spike"
```

Output:
```
🎯 LIKELY CAUSE: Payment gateway timeout causing retry exhaustion
   Confidence: HIGH (92%)

📊 SIGNALS:
   ⚠️ [DEPLOYMENT] 2h ago: "Add retry logic for payment gateway" by @john.dev
   ⚠️ [DEPENDENCY] payment-gateway: DEGRADED (p99: 28s, errors: 45%)
   ⚠️ [LOGS] PaymentGatewayTimeout: 342 occurrences in 5 min
   
✅ RULED OUT:
   • Akamai/Traffic — normal patterns
   • OpenShift pods — all healthy
   • inventory-service — healthy
   • user-service — healthy

📋 ACTIONS:
   1. Rollback commit abc123f: git revert abc123f
   2. Increase timeout: kubectl edit configmap payment-gateway-config
   3. Check payment-gateway logs: kubectl logs payment-gateway-xxx

📚 RUNBOOK: https://wiki.ford.com/runbooks/payment-gateway-timeout
```

**Time to first action:** 30 seconds  
**Mental state:** Calm, informed, confident

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        SRE AGENT                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   TRIGGER   │───▶│   GATHER    │───▶│   ANALYZE   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│        │                  │                   │             │
│        ▼                  ▼                   ▼             │
│  • ServiceNow       • Prometheus         • Local LLM       │
│  • PagerDuty        • GitHub             • Pattern match   │
│  • Slack            • Logs (GCP/ELK)     • Correlation     │
│  • CLI              • OpenShift/K8s      • Confidence      │
│  • Webhook          • Dynatrace                            │
│                     • Akamai                               │
│                     • Dependencies                         │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   REPORT    │───▶│   OUTPUT    │───▶│   LEARN     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│        │                  │                   │             │
│        ▼                  ▼                   ▼             │
│  • Situation        • Terminal           • Past incidents  │
│  • Root cause       • Slack              • Pattern DB      │
│  • Actions          • ServiceNow         • Feedback loop   │
│  • Runbooks         • Email              • Improve prompts │
│                     • JSON API                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Sources (What It Gathers)

### 1. Prometheus / Grafana
```yaml
What it pulls:
  - Error rate (current vs baseline)
  - Request rate (current vs baseline)
  - Latency p50, p95, p99
  - Error breakdown by status code
  - Time series (last 1h, 6h, 24h)
  
Queries:
  - rate(http_requests_total{status=~"5.."}[5m])
  - histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

### 2. GitHub
```yaml
What it pulls:
  - Deployments in last 24h
  - Commit details (author, message, files changed)
  - Open PRs for the service
  - Recent CI/CD runs
  
Correlation:
  - "Deploy 2h ago → errors started 1.5h ago" = HIGH signal
```

### 3. Logs (GCP Cloud Logging / Elasticsearch / Kibana)
```yaml
What it pulls:
  - Error logs from last 15 min
  - Error patterns (group by message)
  - Stack traces
  - First occurrence timestamp
  - Request traces (trace IDs)
  
Analysis:
  - "90% of errors are PaymentGatewayTimeout" = specific cause
```

### 4. Kubernetes / OpenShift
```yaml
What it pulls:
  - Pod status (Running, CrashLoopBackOff, OOMKilled)
  - Restart counts
  - CPU/Memory usage vs limits
  - Recent events (OOM, FailedScheduling)
  - Replica count (desired vs actual)
  
Analysis:
  - "3 pods restarted in last 10 min" = infrastructure issue
```

### 5. Dependencies (Service Mesh / Istio / Custom)
```yaml
What it pulls:
  - Health status of downstream services
  - Latency to each dependency
  - Error rate to each dependency
  
Analysis:
  - "payment-gateway at 45% error rate" = upstream cause
```

### 6. Traffic / CDN (Akamai / Cloudflare)
```yaml
What it pulls:
  - Request volume (normal vs spike)
  - Geographic distribution
  - Bot/attack detection status
  - Rate limiting triggers
  
Analysis:
  - "Traffic normal, no DDoS" = rule out external cause
```

### 7. APM (Dynatrace / DataDog / New Relic)
```yaml
What it pulls:
  - Service flow / dependency map
  - Transaction traces
  - Anomaly detection alerts
  - Root cause analysis (from APM)
```

---

## Analysis Engine

### Input
All gathered data consolidated into a context object.

### Processing

**Step 1: Signal Extraction**
- Identify anomalies in each data source
- Score each signal (0-100% confidence)

**Step 2: Correlation**
- Match deployment times with error start times
- Match dependency degradation with service errors
- Match log patterns with known issues

**Step 3: Root Cause Ranking**
- Weight signals by reliability
- Combine correlated signals
- Produce top 3 likely causes with confidence

**Step 4: Action Generation**
- Match root cause to known remediation
- Generate specific commands
- Link relevant runbooks

### LLM Prompt Strategy

```
You are an expert SRE analyzing an incident.

Context:
- Alert: {alert}
- Metrics: {prometheus_data}
- Recent deploys: {github_data}
- Error logs: {logs_data}
- Infrastructure: {k8s_data}
- Dependencies: {dependency_data}
- Traffic: {traffic_data}

Analyze and provide:
1. Most likely root cause (with confidence)
2. Evidence supporting this conclusion
3. What you've ruled out and why
4. Recommended actions in priority order
5. Relevant runbooks or documentation

Be specific. Use the actual data provided.
```

---

## Output Formats

### 1. Terminal (Default)
Rich formatted output with colors, tables, panels.

### 2. Slack
```
🚨 *INCIDENT: checkout-service 5xx spike*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 *Likely Cause:* Payment gateway timeout
📊 *Confidence:* HIGH (92%)

*Signals:*
• ⚠️ Deploy 2h ago: "Add retry logic" by @john.dev
• ⚠️ payment-gateway: DEGRADED (45% errors)
• ⚠️ Logs: 342x PaymentGatewayTimeout

*Actions:*
1. `git revert abc123f`
2. Check payment-gateway team

📚 <runbook-link|Runbook>
```

### 3. ServiceNow
Auto-attach analysis to incident ticket as work note.

### 4. JSON API
For integration with other tools.

---

## Trigger Methods

### 1. CLI (Current)
```bash
sre-agent analyze "checkout-service 5xx spike"
```

### 2. ServiceNow Webhook
When incident created → trigger agent → attach analysis.

### 3. PagerDuty Webhook
When alert fires → trigger agent → post to Slack.

### 4. Slack Command
```
/sre-analyze checkout-service 5xx
```

### 5. Cron (Proactive)
Run every 5 min, detect anomalies before alerts fire.

---

## Learning & Memory

### Incident Database
Store every analysis:
```yaml
incident_id: INC0012345
service: checkout-service
alert: "5xx spike"
root_cause: "payment-gateway timeout"
confidence: 0.92
resolution: "rollback commit abc123f"
time_to_resolve: 15 min
feedback: "accurate"
```

### Pattern Matching
- "payment-gateway timeout" happened 3 times this month
- Average resolution: rollback
- Suggest: "This looks like the payment-gateway issue from Feb 5"

### Prompt Improvement
- Track which analyses were marked "accurate" vs "wrong"
- Adjust prompts based on feedback

---

## Privacy & Security

### Non-Negotiables
- **100% local execution** — no data leaves the network
- **No external APIs** — Ollama for LLM, everything else internal
- **Read-only access** — agent never modifies anything
- **Audit log** — track every query made

### Credentials
- All tokens stored in environment variables
- Support for vault integration (HashiCorp Vault, AWS Secrets Manager)

---

## Configuration

```yaml
# config.yaml

service:
  name: checkout-service
  namespace: checkout
  team: payments-sre
  slack_channel: "#payments-oncall"
  
llm:
  provider: ollama
  model: llama3.3:latest  # or mixtral, codellama
  temperature: 0.1
  
sources:
  prometheus:
    enabled: true
    url: http://prometheus.internal:9090
    token: ${PROMETHEUS_TOKEN}
    
  github:
    enabled: true
    org: ford-motor
    repo: checkout-service
    token: ${GITHUB_TOKEN}
    
  logs:
    enabled: true
    provider: gcp
    project: ford-checkout-prod
    
  kubernetes:
    enabled: true
    provider: openshift
    kubeconfig: ~/.kube/config
    
  dynatrace:
    enabled: true
    url: https://xyz.dynatrace.com
    token: ${DYNATRACE_TOKEN}
    
output:
  primary: slack
  slack_webhook: ${SLACK_WEBHOOK}
  attach_to_servicenow: true
```

---

## Roadmap

### Phase 1: MVP ✅ DONE
- CLI interface
- Mock data testing
- Local LLM analysis
- Terminal output
- Basic root cause signals

### Phase 2: Real Data
- Prometheus integration
- GitHub integration
- Log integration (GCP/ELK)
- OpenShift integration

### Phase 3: Integration
- Slack output
- ServiceNow webhook trigger
- Runbook matching

### Phase 4: Advanced
- Time-series anomaly detection
- Blast radius estimation
- Similar incident matching
- Proactive detection

### Phase 5: Learning
- Incident database
- Pattern matching
- Feedback loop
- Prompt improvement

---

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Time to first action | 30-40 min | < 2 min |
| Context switches | 6-8 tools | 1 tool |
| Missed correlations | Common | Rare |
| Escalation rate | High | Reduced 50% |
| SRE stress at 2 AM | 😰 | 😌 |

---

## The Dream

**2 AM alert fires.**

Your phone buzzes. But instead of panic, you see:

```
🤖 SRE Agent analyzed INC0012345

Root cause: Payment gateway timeout (92% confidence)
Action: Rollback already suggested to platform team
Runbook: Linked to ticket
ETA to resolution: ~10 min if rollback proceeds

Go back to sleep. I've got this.
```

---

*Built by an SRE, for SREs. Because 2 AM shouldn't suck.*
