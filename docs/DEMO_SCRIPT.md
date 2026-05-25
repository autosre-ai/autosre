# AutoSRE Demo Video Script

## Overview

**Video Title:** AutoSRE: AI-Powered Incident Investigation in 5 Minutes  
**Duration:** ~5-7 minutes  
**Target Audience:** SREs, DevOps Engineers, Platform Engineers, Engineering Managers  
**Key Message:** AutoSRE reduces incident investigation time from 45 minutes to 5 minutes using AI

---

## Technical Setup Required

### Pre-Recording Checklist

1. **Environment Setup**
   ```bash
   cd ~/projects/autosre
   source .venv/bin/activate
   
   # Verify installation
   autosre --version
   
   # Clear terminal history for clean recording
   clear
   ```

2. **Terminal Configuration**
   - Font: SF Mono or JetBrains Mono, 16pt
   - Theme: Dark (recommended: Dracula or One Dark)
   - Terminal size: 120x40 characters minimum
   - Zoom level: 150% for readability

3. **Pre-seed Demo Data** (Optional but recommended)
   ```bash
   autosre demo seed --count 15
   ```

4. **Recording Tools**
   - Screen recorder: OBS, ScreenFlow, or Loom
   - Resolution: 1920x1080 minimum
   - Frame rate: 30fps
   - Microphone: External USB mic recommended

5. **Pre-warm Commands** (Run before recording to avoid cold start delays)
   ```bash
   autosre status
   autosre demo scenarios
   autosre memory search "test" 2>/dev/null || true
   ```

---

## Scene-by-Scene Walkthrough

### Scene 1: Introduction (30 seconds)

**Visual:** Clean terminal with AutoSRE banner

**Commands:**
```bash
clear
autosre --version
```

**Expected Output:**
```
AutoSRE v0.2.2
```

**Narration:**
> "Incident response is one of the most stressful parts of an SRE's job. At 3am, you're 
> paged, you open your laptop, and you spend 45 minutes gathering evidence, checking 
> metrics, reading logs, and trying to figure out what went wrong.
>
> What if an AI agent could do that first pass for you? That's AutoSRE - an AI SRE 
> that investigates incidents like your best on-call engineer, but faster."

---

### Scene 2: Quick Status Check (30 seconds)

**Visual:** Show AutoSRE status and configuration

**Commands:**
```bash
autosre status
```

**Expected Output:**
```
╭──────────────────── 🤖 AutoSRE ────────────────────╮
│                   AutoSRE Status                   │
│ ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓ │
│ ┃ Component          ┃ Status      ┃ Details     ┃ │
│ ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩ │
│ │ Version            │ 0.2.2       │             │ │
│ │ Config             │ ✓ Found     │ ~/.autosre  │ │
│ │ Memory             │ ✓ Available │ 24.5 KB     │ │
│ │ LLM Provider       │ anthropic   │ claude-3.5  │ │
│ │ Python             │ 3.12.0      │             │ │
│ └────────────────────┴─────────────┴─────────────┘ │
╰────────────────────────────────────────────────────╯
```

**Narration:**
> "AutoSRE is a Python CLI that connects to your existing infrastructure - 
> Prometheus for metrics, Kubernetes for cluster state, your log aggregator, 
> and an LLM for reasoning. Let's see it in action."

---

### Scene 3: Show Available Demo Scenarios (20 seconds)

**Visual:** List of incident scenarios

**Commands:**
```bash
autosre demo scenarios
```

**Expected Output:**
```
                  Available Demo Scenarios                   
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ ID               ┃ Name                     ┃ Service          ┃ Severity ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ redis-connection │ Redis Connection Pool    │ checkout-service │ high     │
│ memory-leak      │ Memory Leak in Gateway   │ api-gateway      │ critical │
│ latency-spike    │ Database Query Latency   │ order-service    │ high     │
│ cascading-failure│ Cascading Failure        │ payment-service  │ critical │
│ config-drift     │ Configuration Drift      │ user-service     │ medium   │
└──────────────────┴──────────────────────────┴──────────────────┴──────────┘
```

**Narration:**
> "AutoSRE ships with realistic demo scenarios that simulate common incidents.
> Let's investigate a Redis connection pool exhaustion - a classic problem 
> that takes human SREs 30-45 minutes to diagnose."

---

### Scene 4: Start Investigation (3 minutes - MAIN DEMO)

**Visual:** Full investigation flow with streaming output

**Commands:**
```bash
autosre demo run --scenario redis-connection
```

**Expected Output (streaming):**
```
╭─────────────────── 🎭 Demo Scenario ───────────────────╮
│ Redis Connection Pool Exhaustion                       │
│                                                        │
│ Alert: High error rate on checkout-service: 23% 5xx    │
│ Service: checkout-service                              │
│ Severity: high                                         │
│                                                        │
│ Classic connection pool exhaustion after traffic spike │
╰────────────────────────────────────────────────────────╯

Start investigation? [Y/n]: 
```

*Press Enter to confirm*

**Expected Output (continued):**
```
╭──────────────── Investigation Started ─────────────────╮
│ 🔍 Investigation abc12345                              │
│                                                        │
│ Alert: High error rate on checkout-service: 23% 5xx    │
│ Service: checkout-service                              │
│ Severity: high                                         │
│ Mode: Mock                                             │
╰────────────────────────────────────────────────────────╯

⠋ Searching episodic memory... Found 3 similar incidents

📊 Evidence Collected:
📋 prometheus (confidence: 92%)
   • error_rate: 23.4%
   • p99_latency: 2.3s
   • active_connections: 147

📋 kubernetes (confidence: 88%)
   • pod_status: Running
   • restarts: 0
   • events: ConnectionRefused

📋 redis (confidence: 95%)
   • connection_pool_size: 50
   • active_connections: 50
   • waiting_requests: 312

🧠 Hypotheses:
💡 Redis Connection Pool Exhaustion ⭐⭐⭐⭐⭐ (94%)
   Supporting evidence:
   • Redis pool at 100% capacity (50/50)
   • 312 requests waiting for connections

💡 Downstream Service Timeout ⭐⭐⭐ (62%)
   Supporting evidence:
   • Increased latency correlates with error rate

💡 Recent Deployment Issue ⭐⭐ (35%)
   Supporting evidence:
   • No recent deployments detected

╭─────────────── 🎯 Analysis Complete ───────────────────╮
│ Root Cause: Redis Connection Pool Exhaustion           │
│                                                        │
│ The checkout-service Redis connection pool (50 conns)  │
│ is fully saturated with 312 requests waiting.          │
│ Traffic spike at 14:23 UTC exceeded pool capacity.     │
╰────────────────────────────────────────────────────────╯

╭──────────────────── Demo Complete ─────────────────────╮
│ ✓ Demo investigation completed                         │
│                                                        │
│ Investigation ID: abc12345                             │
│ Duration: 4.2s                                         │
│ Root Cause: Redis Connection Pool Exhaustion           │
╰────────────────────────────────────────────────────────╯
```

**Narration (during streaming):**
> "Watch as AutoSRE works through this incident step by step.
>
> First, it searches episodic memory for similar past incidents. If you've seen 
> this before, AutoSRE remembers.
>
> [As evidence appears] Now it's gathering evidence in parallel - querying 
> Prometheus for metrics, checking Kubernetes pod state, and looking at Redis 
> connection stats.
>
> [As hypotheses appear] Based on the evidence, AutoSRE generates hypotheses 
> ranked by likelihood. See how Redis pool exhaustion comes up at 94% confidence 
> - the pool is at 100% capacity with 312 requests waiting.
>
> [At completion] In just over 4 seconds, we have a root cause analysis that 
> would have taken a human SRE 30-45 minutes to piece together."

---

### Scene 5: Memory Recall Feature (45 seconds)

**Visual:** Search episodic memory for similar incidents

**Commands:**
```bash
autosre memory search "connection pool"
```

**Expected Output:**
```
Found 4 similar incidents:

┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ ID        ┃ Service            ┃ Root Cause                          ┃ Resolved   ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ inv_abc12 │ checkout-service   │ Redis connection pool exhaustion    │ ✓ 8m       │
│ inv_def34 │ payment-service    │ Database connection limit reached   │ ✓ 12m      │
│ inv_ghi56 │ order-service      │ Redis connection pool exhaustion    │ ✓ 6m       │
│ inv_jkl78 │ api-gateway        │ Downstream service timeout          │ ✓ 23m      │
└───────────┴────────────────────┴─────────────────────────────────────┴────────────┘

Pattern detected: Connection pool issues occur 3x more often during 
peak traffic windows (14:00-18:00 UTC)
```

**Narration:**
> "AutoSRE learns from every investigation. Search your incident history to find 
> similar past issues. Notice the pattern - connection pool issues happen 3x more 
> during peak traffic. This is the kind of insight that usually lives in tribal 
> knowledge."

---

### Scene 6: Service Topology (30 seconds)

**Visual:** Show service dependency map

**Commands:**
```bash
autosre demo topology
```

**Expected Output:**
```
╭────────────────── Demo Service Topology ───────────────────╮
│ 🏢 Demo Platform                                           │
│ ├── 📱 Frontend Tier                                       │
│ │   ├── web-frontend                                       │
│ │   └── mobile-bff                                         │
│ ├── 🔌 API Tier                                            │
│ │   ├── api-gateway                                        │
│ │   └── auth-service                                       │
│ ├── ⚙️ Business Logic                                       │
│ │   ├── checkout-service                                   │
│ │   │   ├── → payment-service                              │
│ │   │   └── → inventory-service                            │
│ │   ├── order-service                                      │
│ │   │   └── → notification-service                         │
│ │   ├── user-service                                       │
│ │   └── search-service                                     │
│ ├── 🗄️ Data Tier                                            │
│ │   ├── postgresql (primary)                               │
│ │   ├── redis (cache)                                      │
│ │   └── elasticsearch (search)                             │
│ └── 🔧 Infrastructure                                       │
│     ├── kubernetes                                         │
│     ├── prometheus                                         │
│     └── grafana                                            │
╰────────────────────────────────────────────────────────────╯
```

**Narration:**
> "AutoSRE understands your service topology. When investigating an incident, 
> it automatically considers upstream and downstream dependencies. If checkout 
> fails, it knows to check payment and inventory services too."

---

### Scene 7: Quick CLI Investigation (30 seconds)

**Visual:** Show the one-liner investigation command

**Commands:**
```bash
autosre run "API latency spike to 2s" --service api-gateway --mock
```

**Expected Output:**
```
╭──────────────── Investigation Started ─────────────────╮
│ 🔍 Investigation def45678                              │
│                                                        │
│ Alert: API latency spike to 2s                         │
│ Service: api-gateway                                   │
│ Severity: high                                         │
│ Mode: Mock                                             │
╰────────────────────────────────────────────────────────╯

[... streaming investigation output ...]

╭─────────────── 🎯 Analysis Complete ───────────────────╮
│ Root Cause: Database query regression                  │
│                                                        │
│ P99 latency spiked after deployment v2.1.3             │
│ New query missing index on users.last_login column     │
╰────────────────────────────────────────────────────────╯
```

**Narration:**
> "For quick investigations, use the one-liner. Just describe the alert, 
> specify the service, and AutoSRE handles the rest. In production, remove 
> the --mock flag to connect to your real infrastructure."

---

### Scene 8: Production Setup Teaser (30 seconds)

**Visual:** Show config initialization

**Commands:**
```bash
# Show config init command (don't actually run)
echo "# To set up for production:"
echo "autosre config init"
echo ""
echo "# Then investigate real incidents:"
echo "autosre investigate run 'checkout errors spiking'"
```

**Expected Output:**
```
# To set up for production:
autosre config init

# Then investigate real incidents:
autosre investigate run 'checkout errors spiking'
```

**Narration:**
> "Setting up AutoSRE for production is just one command: autosre config init. 
> It walks you through connecting Prometheus, Kubernetes, and your LLM provider. 
> Then you're ready to investigate real incidents."

---

### Scene 9: Closing (30 seconds)

**Visual:** GitHub URL and key stats

**Commands:**
```bash
clear
echo ""
echo "    ╔═══════════════════════════════════════════════════════════╗"
echo "    ║                                                           ║"
echo "    ║                        AutoSRE                            ║"
echo "    ║         AI-Powered Incident Investigation                 ║"
echo "    ║                                                           ║"
echo "    ║   45-minute investigations → 5 minutes                    ║"
echo "    ║   Autonomous triage • Evidence-based RCA                  ║"
echo "    ║   Human-in-the-loop for safety                            ║"
echo "    ║                                                           ║"
echo "    ║   pip install autosre-ai                                  ║"
echo "    ║   github.com/autosre-ai/autosre                           ║"
echo "    ║                                                           ║"
echo "    ╚═══════════════════════════════════════════════════════════╝"
echo ""
```

**Narration:**
> "AutoSRE turns 45-minute investigations into 5-minute AI-assisted triage. 
> It's open source, pip-installable, and ready to help your on-call team.
>
> Check it out at github.com/autosre-ai/autosre, or install with pip install 
> autosre-ai. Thanks for watching!"

---

## Alternative Scenes (Optional)

### Alternative: Interactive Chat Mode

If you want to show the chat interface:

```bash
autosre chat start --mock
```

**Narration:**
> "AutoSRE also has an interactive chat mode where you can ask questions 
> about your infrastructure in natural language."

### Alternative: Benchmark Performance

If you want to show speed:

```bash
autosre demo benchmark --iterations 3
```

**Narration:**
> "AutoSRE can investigate multiple scenarios in parallel, with average 
> investigation times under 5 seconds in mock mode."

---

## Post-Production Notes

### Recommended Edits

1. **Speed up** typing animations to 2-3x
2. **Add captions** for key narration points
3. **Add callout boxes** highlighting:
   - Confidence scores
   - Evidence sources
   - Root cause identification
4. **Add background music** (subtle, tech-focused)
5. **Add end card** with:
   - GitHub URL
   - Star button reminder
   - Discord/Twitter links

### Key Timestamps for Chapters

- 0:00 - Introduction
- 0:30 - Status Check
- 1:00 - Demo Scenarios
- 1:20 - Main Investigation
- 4:20 - Memory Recall
- 5:00 - Service Topology
- 5:30 - Quick CLI
- 6:00 - Production Setup
- 6:30 - Closing

---

## Quick Reference Card

### Essential Commands for Demo

```bash
# Show version
autosre --version

# Show status
autosre status

# List scenarios
autosre demo scenarios

# Run specific scenario
autosre demo run --scenario redis-connection

# Quick investigation
autosre run "error description" --service service-name --mock

# Search memory
autosre memory search "keyword"

# Show topology
autosre demo topology

# Seed demo data
autosre demo seed --count 15
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Slow response | Pre-run commands to warm up |
| Memory empty | Run `autosre demo seed` |
| LLM errors | Use `--mock` flag |
| Display issues | Check terminal size (120x40) |

---

*Last updated: May 2026*
*AutoSRE v0.2.2*
