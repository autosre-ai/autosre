# AutoSRE - Gap Analysis & Build Plan

## What OpenSRE HAS (✓)
1. **100+ Investigation Tools** - Datadog, Grafana, AWS, K8s, DBs, etc.
2. **Multi-LLM Support** - Anthropic, OpenAI, Gemini, Copilot, Ollama
3. **ReAct Agent Loop** - Think → Call Tools → Observe → Repeat
4. **CLI Interface** - `opensre investigate`, `opensre onboard`
5. **Integration Verification** - `opensre integrations verify`
6. **Webhook Receiver** - PagerDuty, Datadog, Grafana webhooks
7. **Slack Delivery** - Post investigation results
8. **SRE Knowledge Base** - Google SRE book excerpts
9. **Hermes Log Tailer** - Monitor Hermes error logs
10. **Correlation Engine** - Cross-correlate events

## What OpenSRE is MISSING (✗) - Our Differentiators

### 1. **MEMORY SYSTEM** (Critical Gap)
OpenSRE has NO persistent memory. Every investigation starts from scratch.

**What we add:**
- **Episodic Memory**: Store past investigations with outcomes
- **Pattern Memory**: "This symptom + this context = this root cause"
- **Infrastructure Memory**: "Service X depends on Y, owned by team Z"
- **Runbook Memory**: "For error type A, try these steps"

### 2. **SKILL SYSTEM** (Critical Gap)
OpenSRE tools are hardcoded. No way to add custom investigation procedures.

**What we add:**
- **YAML + Script Skills** (like Hermes)
- **Auto-generation from investigations** - "That worked, save as skill"
- **Skill marketplace** - Share across orgs
- **Versioned, testable skills**

### 3. **SELF-IMPROVEMENT LOOP** (Critical Gap)
OpenSRE doesn't learn. Same mistakes, same gaps, forever.

**What we add:**
- **Post-investigation analysis** - What worked? What didn't?
- **Skill extraction** - Turn successful investigations into reusable skills
- **Pattern detection** - "This is the 5th time we saw this, here's the pattern"
- **Confidence scoring** - Track accuracy over time

### 4. **MULTI-AGENT ARCHITECTURE** (Enhancement)
OpenSRE has a single agent loop.

**What we add:**
- **Orchestrator Agent** - Triage, delegate, synthesize
- **Specialist Agents** - K8s expert, DB expert, Network expert
- **Remediation Agent** - Take action (with approval gates)
- **Learning Agent** - Background self-improvement

### 5. **HUMAN-IN-THE-LOOP** (Enhancement)
OpenSRE is fully autonomous or nothing.

**What we add:**
- **Approval gates** for destructive actions
- **Confidence thresholds** - "I'm 60% sure, want me to proceed?"
- **Interactive investigation** - Ask clarifying questions
- **Escalation paths** - When to page a human

### 6. **KNOWLEDGE GRAPH** (Enhancement)
OpenSRE has static SRE knowledge.

**What we add:**
- **Dynamic infrastructure graph** - Services, dependencies, owners
- **Blast radius analysis** - "If X fails, what's affected?"
- **Change correlation** - "This broke 5 min after deploy Y"
- **Historical trends** - "This service has been flaky for 2 weeks"

### 7. **WEB UI** (Enhancement)
OpenSRE is CLI-only.

**What we add:**
- **Investigation dashboard** - See ongoing/past investigations
- **Skill editor** - Create/edit skills visually
- **Memory explorer** - Browse what the agent knows
- **Settings/integrations** - Configure without .env

### 8. **RUNBOOK GENERATION** (Major Feature)
OpenSRE doesn't create runbooks.

**What we add:**
- **Auto-generate runbooks** from successful investigations
- **Runbook execution** - Step-by-step guided remediation
- **Runbook versioning** - Track changes over time
- **Runbook validation** - Test runbooks against synthetic incidents

---

## Architecture Comparison

### OpenSRE (Current)
```
Alert → ReAct Loop → Tools → Result → Slack
         ↑    ↓
       LLM  Tools
```

### AutoSRE (Target)
```
Alert → Orchestrator → Memory Query → Skill Match
              ↓
        Specialist Agents (parallel)
              ↓
        Tool Execution + Evidence
              ↓
        Synthesis + Confidence
              ↓
        Result → Delivery
              ↓
        Learning Agent → Update Memory/Skills
```

---

## Build Priority

### Phase 1: Memory (Day 1) - MUST HAVE
Without memory, we're just another stateless agent.

1. **SQLite episodic store** - Past investigations
2. **Memory query API** - Search similar incidents
3. **Context injection** - Load relevant memory before investigation
4. **Memory update** - Save investigation outcomes

### Phase 2: Skills (Day 1) - MUST HAVE
Without skills, we can't self-improve.

1. **Skill YAML schema** - Define skill format
2. **Skill loader** - Load skills at runtime
3. **Built-in skills** - K8s, AWS, DB investigation skills
4. **Skill execution** - Run skill scripts

### Phase 3: Self-Improvement (Day 2) - MUST HAVE
This is the key differentiator.

1. **Post-investigation hook** - Analyze what worked
2. **Pattern extraction** - Identify reusable patterns
3. **Skill suggestion** - "Should I save this as a skill?"
4. **Memory update** - Store learnings

### Phase 4: Polish (Day 2)
1. Rename to AutoSRE
2. Update docs
3. Docker Compose
4. GitHub repo setup

---

## Technical Implementation

### Memory Schema (SQLite)
```sql
-- Past investigations
CREATE TABLE investigations (
    id TEXT PRIMARY KEY,
    timestamp DATETIME,
    alert_source TEXT,
    alert_type TEXT,
    symptoms TEXT,           -- JSON
    root_cause TEXT,
    root_cause_category TEXT,
    resolution TEXT,
    confidence REAL,
    outcome TEXT,            -- success/failure/partial
    duration_seconds INTEGER,
    tools_used TEXT,         -- JSON array
    evidence TEXT            -- JSON
);

-- Learned patterns
CREATE TABLE patterns (
    id TEXT PRIMARY KEY,
    symptom_fingerprint TEXT,
    context_keys TEXT,       -- JSON
    likely_cause TEXT,
    confidence REAL,
    hit_count INTEGER,
    last_hit DATETIME,
    skill_ref TEXT           -- Link to skill if exists
);

-- Infrastructure topology
CREATE TABLE services (
    id TEXT PRIMARY KEY,
    name TEXT,
    team TEXT,
    dependencies TEXT,       -- JSON array
    dependents TEXT,         -- JSON array
    metadata TEXT            -- JSON
);
```

### Skill Format (YAML)
```yaml
# skills/kubernetes/crashloop-debug.yaml
name: kubernetes-crashloop-debug
version: 1.0.0
description: Debug Kubernetes CrashLoopBackOff errors
triggers:
  - alert_contains: CrashLoopBackOff
  - alert_contains: pod restart
  - symptoms: [pod_crash, container_exit]

context:
  requires:
    - kubernetes  # Integration must be configured
  
steps:
  - name: Get pod details
    tool: eks_list_pods
    params:
      namespace: "{{ alert.namespace }}"
      pod_name: "{{ alert.pod_name }}"
    
  - name: Get pod logs
    tool: eks_pod_logs
    params:
      pod_name: "{{ step.0.pods[0].name }}"
      tail_lines: 100
    
  - name: Check events
    tool: eks_events
    params:
      namespace: "{{ alert.namespace }}"
      involved_object: "{{ alert.pod_name }}"

  - name: Check resource limits
    tool: eks_deployment_status
    condition: "{{ 'OOMKilled' in step.1.logs }}"
    params:
      deployment: "{{ alert.deployment }}"

analysis:
  patterns:
    - match: "OOMKilled"
      cause: "Container exceeded memory limits"
      remediation: "Increase memory limits or fix memory leak"
    - match: "ImagePullBackOff"
      cause: "Cannot pull container image"
      remediation: "Check image name, registry credentials, network"
    - match: "Error: /"
      cause: "Application crash"
      remediation: "Check application logs for stack trace"

metadata:
  author: autosre
  created: 2024-01-01
  updated: 2024-01-01
  usage_count: 0
  success_rate: 0.0
```

### Self-Improvement Hook
```python
# After investigation completes
async def post_investigation_analysis(investigation: Investigation):
    """Analyze investigation and extract learnings."""
    
    # 1. Store in episodic memory
    await memory.store_investigation(investigation)
    
    # 2. Look for patterns
    similar = await memory.find_similar(
        symptoms=investigation.symptoms,
        root_cause=investigation.root_cause
    )
    
    if len(similar) >= 3:
        # We've seen this pattern multiple times
        pattern = extract_pattern(similar)
        await memory.store_pattern(pattern)
        
        # Suggest creating a skill
        if not pattern.skill_ref:
            suggest_skill_creation(investigation, pattern)
    
    # 3. Update confidence scores
    if investigation.outcome == "verified":
        await memory.boost_confidence(investigation.pattern_id)
    elif investigation.outcome == "incorrect":
        await memory.reduce_confidence(investigation.pattern_id)
    
    # 4. Log for learning agent
    await learning_queue.push(investigation)
```

---

## Files to Create

```
autosre/
├── autosre/
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── store.py          # SQLite wrapper
│   │   ├── episodic.py       # Investigation history
│   │   ├── patterns.py       # Learned patterns
│   │   └── search.py         # Similarity search
│   │
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── loader.py         # Load skills from YAML
│   │   ├── executor.py       # Execute skill steps
│   │   ├── generator.py      # Generate skills from investigations
│   │   └── builtin/          # Built-in skills
│   │       ├── kubernetes/
│   │       ├── aws/
│   │       └── databases/
│   │
│   ├── learning/
│   │   ├── __init__.py
│   │   ├── analyzer.py       # Post-investigation analysis
│   │   ├── patterns.py       # Pattern extraction
│   │   └── improver.py       # Background improvement loop
│   │
│   └── cli/
│       ├── memory.py         # `autosre memory search`
│       └── skills.py         # `autosre skills list/add`
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Mean Time to Resolution | 50% faster than manual |
| Investigation Accuracy | >85% correct root cause |
| Self-Improvement Rate | Learn 1 new pattern/week |
| Skill Coverage | 80% of common incidents |
| User Satisfaction | "Would use again" >90% |

---

## Launch Checklist

- [ ] Memory system works (store/query/update)
- [ ] 5+ built-in skills (K8s, AWS, DB, Network, App)
- [ ] Self-improvement loop active
- [ ] CLI works (`autosre investigate`, `autosre memory`, `autosre skills`)
- [ ] Docker Compose deployment
- [ ] README with quickstart
- [ ] Demo video
- [ ] GitHub repo public
