# AutoSRE Iteration 1 — Gap Analysis & Implementation Spec

## Executive Summary

This document analyzes what OpenSRE has that we're missing and provides an actionable spec for Iteration 1. AutoSRE v2 already has solid foundations (orchestrator, memory, topology, subagents), but needs the following to match OpenSRE's production-grade capabilities:

1. **API Server with SSE Streaming** — FastAPI server with real-time event streaming
2. **Skill/Tool System** — Skills with `load_skill`/`run_script` tools for subagents
3. **Structured Event Protocol** — Standardized events for UI/Slack integration
4. **Knowledge Graph Context** — Neo4j integration for service topology
5. **Config Service Integration** — Remote configuration and episode storage
6. **Integrations** — Slack, PagerDuty, webhooks for triggering investigations

---

## Current State Comparison

| Feature | OpenSRE | AutoSRE v2 | Gap |
|---------|---------|------------|-----|
| **Orchestrator** | LangGraph StateGraph | Plain async Python | ✅ Different approach, both valid |
| **Episodic Memory** | PostgreSQL via config-service | SQLite local-first | ✅ Simpler, works |
| **Service Topology** | Neo4j KubernetesGraphTools | YAML-based ServiceTopology | ✅ Simpler, works |
| **Multi-Agent** | LangGraph Send() fan-out | asyncio.gather() | ✅ Both parallel |
| **Investigation Loop** | init→memory→kg→planner→subagents→synthesizer→writeup | init→memory→topology→planner→subagents→synthesizer→writeup | ✅ Same pattern |
| **Subagents** | kubernetes, metrics, logs, traces | kubernetes, metrics, logs | ⚠️ Missing traces |
| **API Server** | FastAPI + SSE streaming | ❌ None | 🔴 **CRITICAL** |
| **Event Protocol** | StreamEvent dataclasses | ❌ None | 🔴 **CRITICAL** |
| **Skill Tools** | load_skill/run_script LangChain tools | ❌ Skills exist but no tool interface | 🔴 **CRITICAL** |
| **Config Service** | Remote team config, skill toggles | ❌ Local config only | ⚠️ Nice-to-have |
| **Slack Integration** | Full slack-bot with OAuth | ❌ Basic skill scripts | 🔴 **CRITICAL** |
| **File Proxy** | Download Slack files for agent | ❌ None | ⚠️ For Slack |
| **Neo4j KG** | KubernetesGraphTools class | ❌ YAML topology only | ⚠️ Optional |
| **Writeup Reports** | JSON structured + markdown | ✅ Have InvestigationReport | ✅ Good |
| **Strategy Generation** | LLM from past episodes | ✅ Have strategy.py | ✅ Good |

---

## Gap 1: API Server with SSE Streaming (CRITICAL)

### What OpenSRE Has
- **server.py**: FastAPI app with `/investigate`, `/interrupt`, `/answer` endpoints
- **SSE streaming**: Real-time event stream with `StreamingResponse`
- **Background tasks**: `graph_background_task` runs investigation async
- **Thread management**: `_background_tasks`, `_message_queues`, `_response_queues`

### What We Need
Create `autosre/api/` module:

```python
# autosre/api/server.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="AutoSRE Investigation Server", version="2.0.0")

class InvestigateRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None
    service: Optional[str] = None

@app.post("/investigate")
async def investigate(request: InvestigateRequest):
    """Start an investigation with SSE streaming."""
    thread_id = request.thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    
    async def stream():
        orchestrator = Orchestrator()
        async for event in orchestrator.investigate_stream(
            alert={"description": request.prompt, "service": request.service},
            thread_id=thread_id,
        ):
            yield f"data: {json.dumps(event.to_dict())}\n\n"
    
    return StreamingResponse(stream(), media_type="text/event-stream")

@app.post("/interrupt")
async def interrupt(request: InterruptRequest):
    """Interrupt a running investigation."""
    pass

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0"}
```

### Implementation Tasks
- [ ] Create `autosre/api/__init__.py`
- [ ] Create `autosre/api/server.py` with FastAPI app
- [ ] Create `autosre/api/models.py` with Pydantic request/response models
- [ ] Add `investigate_stream()` generator to Orchestrator
- [ ] Add thread/session management for concurrent investigations
- [ ] Add `/interrupt` endpoint to cancel investigations
- [ ] Add `/health` endpoint
- [ ] Add CLI command: `autosre serve --port 8001`

---

## Gap 2: Structured Event Protocol (CRITICAL)

### What OpenSRE Has
- **events.py**: `StreamEvent` dataclass with factory functions
- Event types: `thought`, `tool_start`, `tool_end`, `result`, `error`, `approval`, `question`
- Standardized format for all agent-to-client communication

### What We Need
Create `autosre/api/events.py`:

```python
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

@dataclass
class StreamEvent:
    type: str  # thought | tool_start | tool_end | result | error
    data: dict
    thread_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_sse(self) -> str:
        return f"data: {json.dumps(self.to_dict())}\n\n"

def thought_event(thread_id: str, text: str, agent_name: str = "") -> StreamEvent:
    """Agent reasoning/thinking text."""
    return StreamEvent(type="thought", data={"text": text, "agent_name": agent_name}, thread_id=thread_id)

def tool_start_event(thread_id: str, name: str, tool_input: dict) -> StreamEvent:
    """Tool execution starting."""
    return StreamEvent(type="tool_start", data={"name": name, "input": tool_input}, thread_id=thread_id)

def tool_end_event(thread_id: str, name: str, success: bool, output: str) -> StreamEvent:
    """Tool execution completed."""
    return StreamEvent(type="tool_end", data={"name": name, "success": success, "output": output}, thread_id=thread_id)

def result_event(thread_id: str, text: str, report: Optional[dict] = None) -> StreamEvent:
    """Final investigation result."""
    data = {"text": text, "success": True}
    if report:
        data["structured_report"] = report
    return StreamEvent(type="result", data=data, thread_id=thread_id)
```

### Implementation Tasks
- [ ] Create `autosre/api/events.py`
- [ ] Update Orchestrator to yield StreamEvents during investigation
- [ ] Emit events from subagents (tool_start, tool_end)
- [ ] Emit thought events from planner/synthesizer
- [ ] Final result event with structured report

---

## Gap 3: Skill Tools for Subagents (CRITICAL)

### What OpenSRE Has
- **tools/skill_tools.py**: `load_skill(name)` and `run_script(command)` functions
- **tools/agent_tools.py**: `resolve_tools()` and `get_skill_catalog()` functions
- Skills loaded from `.claude/skills/{name}/SKILL.md`
- Scripts executed via subprocess with scoping to enabled skills

### What We Need
Create `autosre/skills/tools.py`:

```python
from typing import Optional, Callable

class SkillTools:
    """Provides load_skill and run_script for subagents."""
    
    def __init__(self, skills_dir: str = "skills/", enabled_skills: set[str] | None = None):
        self.skills_dir = Path(skills_dir)
        self.enabled_skills = enabled_skills  # None = all allowed
    
    def load_skill(self, skill_name: str) -> str:
        """Load a skill's SKILL.md documentation.
        
        Returns full skill documentation so agent knows available scripts.
        """
        skill_dir = self._resolve_skill_dir(skill_name)
        if not skill_dir:
            return f"Error: Skill '{skill_name}' not found."
        
        content = (skill_dir / "SKILL.md").read_text()
        
        # List available scripts
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            scripts = sorted(f.name for f in scripts_dir.iterdir() if f.is_file())
            content += f"\n\n## Available Scripts\n"
            for s in scripts:
                content += f"- `{scripts_dir / s}`\n"
        
        return content
    
    def run_script(self, command: str, timeout: int = 120) -> str:
        """Execute a skill script and return output.
        
        Validates command references an enabled skill before execution.
        """
        # Validate skill is enabled
        if self.enabled_skills is not None:
            skill_name = self._extract_skill_from_command(command)
            if skill_name and skill_name not in self.enabled_skills:
                return f"Error: Skill '{skill_name}' is not enabled."
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        
        return output or "(no output)"
    
    def get_catalog(self) -> str:
        """Build markdown catalog of available skills."""
        lines = ["## Available Skills\n"]
        for skill_dir in sorted(self.skills_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            name, description = self._parse_skill_metadata(skill_md)
            if self.enabled_skills is None or name in self.enabled_skills:
                lines.append(f"- **{name}**: {description}")
        return "\n".join(lines)
```

### How Subagents Use Skills
Update subagents to use `SkillTools` instead of hardcoded logic:

```python
class KubernetesSubagent(BaseSubagent):
    def __init__(self):
        self.skill_tools = SkillTools(enabled_skills={"kubernetes"})
    
    async def investigate(self, alert, hypotheses, service_context, llm_client):
        # Load skill to understand available scripts
        skill_docs = self.skill_tools.load_skill("kubernetes")
        
        # Build prompt with skill info
        prompt = f"""
        ## Investigation Task
        Alert: {alert}
        Hypotheses: {hypotheses}
        
        ## Available Skills
        {skill_docs}
        
        Use run_script() to execute investigation commands.
        """
        
        # Run ReAct loop with LLM
        # LLM chooses which scripts to run based on skill docs
        ...
```

### Implementation Tasks
- [ ] Create `autosre/skills/tools.py` with SkillTools class
- [ ] Create `autosre/skills/loader.py` for skill metadata parsing
- [ ] Update subagents to use SkillTools
- [ ] Add ReAct loop to subagents (LLM chooses tools)
- [ ] Add skill catalog to investigation prompts
- [ ] Implement deduplication (skip duplicate tool calls)

---

## Gap 4: Traces Subagent (NICE-TO-HAVE)

### What OpenSRE Has
- Traces subagent for Jaeger/Tempo/Datadog trace analysis
- Latency breakdown, span analysis, trace searching

### What We Need
```python
# autosre/agents/subagents/traces.py
class TracesSubagent(BaseSubagent):
    agent_id = "traces"
    
    async def investigate(self, ...):
        # Use skill_tools to load tracing skill
        # Query for relevant traces
        # Analyze latency, errors, spans
        pass
```

### Implementation Tasks
- [ ] Create `autosre/agents/subagents/traces.py`
- [ ] Create `skills/traces/` skill with Jaeger/Tempo/Datadog scripts
- [ ] Register in SUBAGENT_REGISTRY
- [ ] Add to planner's available agents

---

## Gap 5: Slack Integration (CRITICAL for Demo)

### What OpenSRE Has
- Full Slack bot with OAuth
- Slash commands, message handling
- File attachment proxying
- Thread management for conversations

### What We Need (Simplified)
For Iteration 1, use existing Slack skill scripts as foundation:

```yaml
# skills/slack/skill.yaml
name: slack
description: Slack integration for notifications and channel operations
requires:
  - SLACK_BOT_TOKEN
  - SLACK_APP_TOKEN

skills:
  - name: send_message
    script: scripts/send_message.py
    description: Send message to Slack channel
    
  - name: create_thread
    script: scripts/create_thread.py
    description: Create investigation thread
    
  - name: update_thread
    script: scripts/update_thread.py  
    description: Update investigation progress
```

For receiving alerts, add webhook endpoint:

```python
# autosre/api/webhooks.py
@app.post("/webhooks/slack/events")
async def slack_events(request: Request):
    """Handle Slack events (messages, commands)."""
    body = await request.json()
    
    if body.get("type") == "url_verification":
        return {"challenge": body["challenge"]}
    
    event = body.get("event", {})
    if event.get("type") == "app_mention":
        # Start investigation from mention
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        channel = event.get("channel")
        
        # Spawn investigation
        asyncio.create_task(investigate_and_reply(text, channel, thread_ts))
    
    return {"ok": True}
```

### Implementation Tasks
- [ ] Create `/webhooks/slack/events` endpoint
- [ ] Create `/webhooks/slack/commands` endpoint for slash commands
- [ ] Update Slack skill scripts for investigation threads
- [ ] Add investigation thread creation/update flow
- [ ] Stream events to Slack thread during investigation

---

## Gap 6: PagerDuty Integration (NICE-TO-HAVE)

### What OpenSRE Has
- PagerDuty webhook handling
- Incident creation/update
- On-call lookup

### What We Need
Use existing skill:
```
skills/pagerduty/
├── SKILL.md
└── scripts/
    ├── get_incidents.py
    ├── acknowledge.py
    └── resolve.py
```

Add webhook:
```python
@app.post("/webhooks/pagerduty")
async def pagerduty_webhook(request: Request):
    """Handle PagerDuty webhooks (incident.triggered, etc.)."""
    body = await request.json()
    
    for message in body.get("messages", []):
        if message.get("event") == "incident.triggered":
            incident = message.get("incident", {})
            # Start investigation
            asyncio.create_task(investigate_pagerduty_incident(incident))
    
    return {"ok": True}
```

### Implementation Tasks
- [ ] Create `/webhooks/pagerduty` endpoint
- [ ] Parse incident data into alert format
- [ ] Optional: Update incident notes with findings

---

## Gap 7: Demo Flow

### Target Demo Flow
```
1. Alert arrives (Slack mention, PagerDuty webhook, or API call)
   → POST /investigate {"prompt": "checkout-service 500 errors"}

2. SSE stream returns real-time events:
   → {"type": "thought", "data": {"text": "Analyzing alert...", "agent_name": "planner"}}
   → {"type": "tool_start", "data": {"name": "run_script", "input": {"command": "kubectl get pods -n checkout"}}}
   → {"type": "tool_end", "data": {"name": "run_script", "success": true, "output": "..."}}
   → {"type": "thought", "data": {"text": "Found 2 crashing pods...", "agent_name": "kubernetes"}}
   → ...

3. Final result with structured report:
   → {"type": "result", "data": {
       "text": "## Investigation Complete\n...",
       "structured_report": {
         "title": "Checkout Service 500 Errors",
         "severity": "high",
         "root_cause": {"summary": "OOM kills in checkout-service pods", ...}
       }
     }}

4. If Slack: Update thread with findings
   If PagerDuty: Add note to incident
```

### Demo Checklist
- [ ] API server running on port 8001
- [ ] Can trigger investigation via `curl -X POST /investigate`
- [ ] SSE events stream in real-time
- [ ] Kubernetes subagent runs kubectl commands
- [ ] Metrics subagent queries Prometheus
- [ ] Final report is structured JSON
- [ ] (Optional) Slack thread updates with progress

---

## Implementation Priority

### Phase 1: Core API (Days 1-2)
1. `autosre/api/server.py` — FastAPI with `/investigate`, `/health`
2. `autosre/api/events.py` — StreamEvent protocol
3. `autosre/api/models.py` — Pydantic models
4. Add `investigate_stream()` to Orchestrator
5. CLI: `autosre serve`

### Phase 2: Skill Tools (Days 3-4)
1. `autosre/skills/tools.py` — SkillTools class
2. Update subagents to use SkillTools
3. Add ReAct loop with tool_start/tool_end events
4. Test with kubernetes skill

### Phase 3: Integrations (Days 5-6)
1. Slack webhook endpoints
2. PagerDuty webhook endpoint
3. Investigation thread updates
4. End-to-end demo

### Phase 4: Polish (Day 7)
1. Error handling
2. Logging
3. Tests
4. Documentation

---

## File Structure After Iteration 1

```
autosre/
├── api/                    # NEW
│   ├── __init__.py
│   ├── server.py           # FastAPI app
│   ├── events.py           # StreamEvent protocol
│   ├── models.py           # Pydantic models
│   └── webhooks.py         # Slack/PagerDuty webhooks
├── skills/
│   ├── __init__.py
│   ├── tools.py            # NEW: SkillTools class
│   └── loader.py           # NEW: Skill metadata parsing
├── agents/
│   ├── subagents/
│   │   ├── base.py         # Updated: ReAct loop with tools
│   │   ├── kubernetes.py   # Updated: Use SkillTools
│   │   ├── metrics.py      # Updated: Use SkillTools
│   │   ├── logs.py         # Updated: Use SkillTools
│   │   └── traces.py       # NEW
│   └── ...
├── orchestrator.py          # Updated: investigate_stream() generator
└── cli.py                   # Updated: serve command
```

---

## Acceptance Criteria

### Iteration 1 Complete When:
- [ ] `autosre serve` starts API server on port 8001
- [ ] `POST /investigate` returns SSE stream
- [ ] Stream includes thought, tool_start, tool_end, result events
- [ ] Subagents use SkillTools for script execution
- [ ] Final result includes structured JSON report
- [ ] `/webhooks/slack/events` triggers investigation from @mention
- [ ] Demo: 5-minute investigation from Slack alert to findings

---

## Open Questions

1. **LangChain Tools vs Custom SkillTools?**
   - OpenSRE uses LangChain `@tool` decorator
   - We can use simpler custom implementation
   - Decision: Custom for now, can add LangChain later if needed

2. **Neo4j Knowledge Graph?**
   - OpenSRE has full Neo4j integration
   - We have YAML topology
   - Decision: Keep YAML for simplicity, Neo4j optional

3. **Config Service?**
   - OpenSRE has remote team config
   - We have local config
   - Decision: Local-first, config service optional

---

*Spec Version: 1.0*
*Author: SPEC Agent*
*Date: 2025-06-05*
