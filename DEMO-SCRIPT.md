# AutoSRE Demo Script

## 20-Second Video Demo

### What to Show
A terminal running the AutoSRE investigation demo, showing the AI-powered incident investigation flow.

### Commands to Run

```bash
cd ~/clawd/projects/autosre
source .venv/bin/activate
python examples/demo_simple.py
```

### Expected Output

```
============================================================
🚀 AutoSRE Investigation Demo
============================================================

📋 Alert: HighErrorRate
   Service: checkout-service
   Severity: critical
   Description: 5xx error rate above 5%

------------------------------------------------------------
🔍 Running Investigation...
------------------------------------------------------------
  Thread ID: demo-XXXXXXXXX
  Service: checkout-service
  Alert Type: http_5xx

📚 Phase 1: Memory Lookup
  Found 3 similar past incidents

🗺️  Phase 2: Service Topology
  Dependencies: payment-service, inventory-service, redis
  Blast radius: 5 services

🎯 Phase 3: Hypothesis Generation
  • [HIGH] Database connection pool exhausted
  • [MEDIUM] Upstream payment-service timeout
  • [MEDIUM] Memory pressure causing OOM kills
  Selected agents: metrics, logs, kubernetes

🔎 Phase 4: Evidence Collection
  [prometheus] checkout-service: 12.3% error rate (threshold: 5%)...
  [kubernetes] ERROR: Connection refused to postgres:5432 - pool exhausted...
  [postgres] Active connections: 200/200 (100% utilized)...

💡 Phase 5: Synthesis
  Confidence: 95%
  Root Cause: Database connection pool exhaustion on postgres-primary

============================================================
📊 INVESTIGATION REPORT
============================================================
  Status:      completed
  Root Cause:  Database connection pool exhaustion on postgres-primary
  Confidence:  95%
  Duration:    2.5s
  Iterations:  1
  Skills Used: query_metrics, pod_logs, db_connections

📝 Summary:
  The checkout-service is experiencing 5xx errors due to database connection pool exhaustion...

============================================================
✅ Demo Complete!
============================================================
```

### Key Talking Points (for voiceover)

1. **"AutoSRE receives a critical alert"** - Show the alert details
2. **"Checks episodic memory for similar incidents"** - Memory lookup phase
3. **"Maps service dependencies"** - Topology phase  
4. **"Generates hypotheses ranked by priority"** - Planning phase
5. **"Collects evidence from multiple sources"** - Evidence phase
6. **"Synthesizes findings into root cause"** - Synthesis phase
7. **"95% confidence: Database connection pool exhausted"** - Final report

### Video Timeline

| Time | What's Visible | Narration |
|------|----------------|-----------|
| 0-3s | Terminal, type command | "Let's investigate a production incident" |
| 3-8s | Alert details + Memory lookup | "AutoSRE checks past incidents" |
| 8-12s | Topology + Hypotheses | "Maps dependencies, generates hypotheses" |
| 12-17s | Evidence collection | "Gathers evidence from metrics, logs, databases" |
| 17-20s | Final report | "Root cause found: Connection pool exhausted" |

### Tips for Recording

1. Use a clean terminal (dark theme recommended)
2. Font size 16+ for readability
3. Pause briefly after the command to let output render
4. The demo takes ~2 seconds to complete

### Alternative: Full Demo with Real LLM

For a demo with actual LLM calls (requires API key):

```bash
export ANTHROPIC_API_KEY="your-key-here"
python examples/investigate.py --service checkout-service "5xx error rate above 5%"
```

This runs the full orchestrator with real AI reasoning.
