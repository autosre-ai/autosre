# Architecture

Deep dive into OpenSRE's system design and multi-agent architecture.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  OpenSRE Core                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐          │
│  │    API Server    │    │   Agent Runtime  │    │   Skill Manager  │          │
│  │   (FastAPI)      │    │   (Orchestrator) │    │   (Plugin Mgr)   │          │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘          │
│           │                       │                       │                     │
│           └───────────────────────┼───────────────────────┘                     │
│                                   │                                             │
│  ┌────────────────────────────────┴─────────────────────────────────────┐      │
│  │                          Message Bus                                  │      │
│  │                  (Events, Commands, Observations)                     │      │
│  └────────────────────────────────┬─────────────────────────────────────┘      │
│                                   │                                             │
│  ┌────────────────────────────────┴─────────────────────────────────────┐      │
│  │                        Multi-Agent System                             │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │      │
│  │  │ Observer │  │ Reasoner │  │  Actor   │  │ Notifier │             │      │
│  │  │  Agent   │  │  Agent   │  │  Agent   │  │  Agent   │             │      │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │      │
│  └──────────────────────────────────────────────────────────────────────┘      │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐      │
│  │                          Knowledge Layer                              │      │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │      │
│  │  │  Runbooks  │  │  Incident  │  │   Vector   │  │  Pattern   │     │      │
│  │  │            │  │   Store    │  │   Store    │  │  Matcher   │     │      │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘     │      │
│  └──────────────────────────────────────────────────────────────────────┘      │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐      │
│  │                           Skill Layer                                 │      │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │      │
│  │  │Promethe│ │  K8s   │ │ Slack  │ │  AWS   │ │PagerDut│ │ Custom │ │      │
│  │  │  us    │ │        │ │        │ │        │ │   y    │ │        │ │      │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │      │
│  └──────────────────────────────────────────────────────────────────────┘      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### API Server

The API server provides:

- **REST API** for programmatic access
- **WebSocket** for real-time updates
- **Webhooks** for alert ingestion
- **MCP Server** for AI assistant integration

```python
# opensre_core/api.py
from fastapi import FastAPI
app = FastAPI(title="OpenSRE API")

@app.post("/webhook/alertmanager")
async def alertmanager_webhook(alert: AlertmanagerPayload):
    """Receive alerts from Alertmanager."""
    await orchestrator.dispatch(alert)

@app.post("/investigate")
async def investigate(request: InvestigateRequest):
    """Manually trigger an investigation."""
    result = await orchestrator.investigate(request.description)
    return result

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time investigation updates."""
    await manager.connect(websocket)
```

### Agent Runtime

The runtime manages agent lifecycle:

```python
# opensre_core/runtime.py
class AgentRuntime:
    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self.skill_manager = SkillManager()
        self.orchestrator = Orchestrator()
    
    async def load_agents(self, path: str):
        """Load agents from YAML files."""
        for file in Path(path).glob("**/*.yaml"):
            agent = Agent.from_yaml(file)
            self.agents[agent.name] = agent
    
    async def dispatch(self, trigger: Trigger):
        """Dispatch trigger to matching agents."""
        for agent in self.agents.values():
            if agent.matches(trigger):
                await self.orchestrator.run(agent, trigger)
```

### Skill Manager

Manages skill loading and lifecycle:

```python
# opensre_core/skills/manager.py
class SkillManager:
    def __init__(self):
        self.skills: dict[str, Skill] = {}
    
    async def load_skill(self, name: str):
        """Load and initialize a skill."""
        spec = self.load_spec(f"skills/{name}/skill.yaml")
        module = importlib.import_module(f"skills.{name}.actions")
        skill = module.get_skill(spec.config)
        await skill.initialize()
        self.skills[name] = skill
    
    async def invoke(self, action: str, **params):
        """Invoke a skill action."""
        skill_name, action_name = action.split(".", 1)
        skill = self.skills[skill_name]
        return await skill.invoke(action_name, **params)
```

## Multi-Agent System

### Agent Pipeline

Each investigation flows through a pipeline of specialized agents:

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Alert  │───▶│ Observer│───▶│ Reasoner│───▶│  Actor  │───▶ Result
└─────────┘    └─────────┘    └─────────┘    └─────────┘
                    │              │              │
                    ▼              ▼              ▼
               Observations    Analysis      Actions
```

### Observer Agent

Gathers signals from connected systems:

```python
# opensre_core/agents/observer.py
class ObserverAgent:
    """Gathers observations from infrastructure."""
    
    async def observe(self, context: InvestigationContext) -> Observations:
        observations = Observations()
        
        # Query metrics
        if "prometheus" in context.skills:
            metrics = await self.gather_metrics(context)
            observations.add("metrics", metrics)
        
        # Check Kubernetes
        if "kubernetes" in context.skills:
            k8s_data = await self.gather_kubernetes(context)
            observations.add("kubernetes", k8s_data)
        
        # Get recent events
        events = await self.gather_events(context)
        observations.add("events", events)
        
        return observations
    
    async def gather_metrics(self, context) -> dict:
        """Gather relevant metrics."""
        queries = self.generate_queries(context)
        results = {}
        for name, query in queries.items():
            results[name] = await prometheus.query(query)
        return results
```

### Reasoner Agent

Analyzes observations and identifies root cause:

```python
# opensre_core/agents/reasoner.py
class ReasonerAgent:
    """Analyzes observations and identifies root cause."""
    
    def __init__(self, llm: LLMAdapter):
        self.llm = llm
        self.pattern_matcher = PatternMatcher()
    
    async def reason(
        self, 
        context: InvestigationContext,
        observations: Observations
    ) -> Analysis:
        # Check for similar past incidents
        similar = await self.pattern_matcher.find_similar(observations)
        
        # Build prompt with observations and context
        prompt = self.build_prompt(context, observations, similar)
        
        # Get LLM analysis
        response = await self.llm.analyze(prompt)
        
        # Parse structured response
        analysis = self.parse_analysis(response)
        
        return analysis
    
    def build_prompt(self, context, observations, similar) -> str:
        return f"""
        Analyze this incident:
        
        ## Alert
        {context.alert}
        
        ## Observations
        {observations.format()}
        
        ## Similar Past Incidents
        {self.format_similar(similar)}
        
        ## Relevant Runbooks
        {self.get_runbooks(context)}
        
        Identify the root cause and recommend remediation.
        """
```

### Actor Agent

Proposes and executes remediation:

```python
# opensre_core/agents/actor.py
class ActorAgent:
    """Executes remediation actions."""
    
    async def act(
        self,
        context: InvestigationContext,
        analysis: Analysis
    ) -> ActionResult:
        # Check if action is allowed
        action = analysis.recommended_action
        
        if self.requires_approval(action):
            # Request human approval
            approved = await self.request_approval(context, action)
            if not approved:
                return ActionResult(status="rejected")
        
        # Execute action
        try:
            result = await self.execute(action)
            return ActionResult(status="success", result=result)
        except Exception as e:
            return ActionResult(status="failed", error=str(e))
    
    async def request_approval(self, context, action) -> bool:
        """Request human approval via Slack."""
        message = await slack.post_blocks(
            channel=context.channel,
            blocks=self.format_approval_request(action)
        )
        
        # Wait for button click
        response = await self.wait_for_response(message.ts)
        return response.action_id == "approve"
```

### Notifier Agent

Keeps humans informed:

```python
# opensre_core/agents/notifier.py
class NotifierAgent:
    """Sends notifications to humans."""
    
    async def notify(
        self,
        context: InvestigationContext,
        observations: Observations,
        analysis: Analysis,
        action_result: ActionResult
    ):
        # Build notification
        blocks = self.build_notification(
            context, observations, analysis, action_result
        )
        
        # Post to Slack
        await slack.post_blocks(
            channel=context.channel,
            blocks=blocks
        )
        
        # Update PagerDuty
        if context.pagerduty_incident_id:
            await pagerduty.add_note(
                incident_id=context.pagerduty_incident_id,
                note=self.format_summary(analysis)
            )
```

## Knowledge Layer

### Runbook System

```python
# opensre_core/knowledge/runbooks.py
class RunbookManager:
    """Manages runbooks for agent reference."""
    
    def __init__(self, path: str):
        self.path = Path(path)
        self.runbooks = {}
        self.index = None
    
    async def load(self):
        """Load and index runbooks."""
        for file in self.path.glob("**/*.md"):
            runbook = self.parse_runbook(file)
            self.runbooks[runbook.name] = runbook
        
        # Build vector index for semantic search
        self.index = await self.build_index()
    
    async def find_relevant(self, context: str, limit: int = 3) -> list:
        """Find relevant runbooks for a context."""
        results = await self.index.search(context, limit=limit)
        return [self.runbooks[r.name] for r in results]
```

### Incident Store

```python
# opensre_core/knowledge/incidents.py
class IncidentStore:
    """Stores past incidents for learning."""
    
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self.vector_store = ChromaDB("incidents")
    
    async def store(self, incident: Incident):
        """Store an incident for future reference."""
        # Store in SQLite
        self.db.execute(
            "INSERT INTO incidents VALUES (?, ?, ?, ?, ?)",
            (incident.id, incident.timestamp, incident.alert,
             incident.root_cause, incident.resolution)
        )
        
        # Store embedding in vector store
        embedding = await self.embed(incident)
        self.vector_store.add(incident.id, embedding)
    
    async def find_similar(
        self, 
        observations: Observations, 
        limit: int = 5
    ) -> list[Incident]:
        """Find similar past incidents."""
        query = self.format_for_search(observations)
        results = await self.vector_store.search(query, limit=limit)
        return [self.get_incident(r.id) for r in results]
```

### Pattern Matcher

```python
# opensre_core/knowledge/patterns.py
class PatternMatcher:
    """Identifies patterns across incidents."""
    
    async def analyze_patterns(self) -> list[Pattern]:
        """Analyze historical incidents for patterns."""
        incidents = await self.incident_store.get_all()
        
        patterns = []
        
        # Time-based patterns
        patterns.extend(self.find_time_patterns(incidents))
        
        # Service-based patterns
        patterns.extend(self.find_service_patterns(incidents))
        
        # Root cause patterns
        patterns.extend(self.find_cause_patterns(incidents))
        
        return patterns
    
    def find_time_patterns(self, incidents) -> list[Pattern]:
        """Find time-based patterns (e.g., issues after deploys)."""
        deploy_related = [i for i in incidents if i.tags.get("deploy_related")]
        if len(deploy_related) > 10:
            return [Pattern(
                type="deployment",
                description="Issues commonly occur after deployments",
                confidence=len(deploy_related) / len(incidents)
            )]
        return []
```

## LLM Integration

### LLM Adapter

Abstraction over multiple LLM providers:

```python
# opensre_core/adapters/llm.py
class LLMAdapter:
    """Unified interface for LLM providers."""
    
    def __init__(self, config: LLMConfig):
        self.provider = self.create_provider(config)
    
    def create_provider(self, config):
        if config.provider == "ollama":
            return OllamaProvider(config)
        elif config.provider == "openai":
            return OpenAIProvider(config)
        elif config.provider == "anthropic":
            return AnthropicProvider(config)
        raise ValueError(f"Unknown provider: {config.provider}")
    
    async def analyze(self, prompt: str, system: str = None) -> str:
        """Send prompt to LLM and get response."""
        return await self.provider.complete(prompt, system=system)
    
    async def structured_output(
        self, 
        prompt: str, 
        schema: type[BaseModel]
    ) -> BaseModel:
        """Get structured output from LLM."""
        return await self.provider.structured(prompt, schema)
```

### Structured Reasoning

```python
# opensre_core/adapters/reasoning.py
class AnalysisSchema(BaseModel):
    """Schema for LLM analysis output."""
    root_cause: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]
    recommendation: str
    action: str | None
    urgency: Literal["low", "medium", "high", "critical"]

async def get_analysis(
    llm: LLMAdapter,
    observations: Observations
) -> AnalysisSchema:
    """Get structured analysis from LLM."""
    prompt = f"""
    Analyze these observations and identify the root cause.
    
    {observations.format()}
    
    Respond with:
    - root_cause: What caused this issue
    - confidence: Your confidence (0-1)
    - evidence: List of supporting evidence
    - recommendation: What should be done
    - action: Specific action to take (or null)
    - urgency: low/medium/high/critical
    """
    
    return await llm.structured_output(prompt, AnalysisSchema)
```

## Data Flow

### Investigation Flow

```
1. Alert Received
   └── API Server receives webhook
       └── Validates and parses alert

2. Agent Selection
   └── Orchestrator finds matching agents
       └── Creates InvestigationContext

3. Observation Phase
   └── Observer Agent runs
       └── Queries Prometheus, K8s, etc.
       └── Returns Observations

4. Reasoning Phase
   └── Reasoner Agent runs
       └── Searches similar incidents
       └── Gets relevant runbooks
       └── Sends to LLM
       └── Returns Analysis

5. Action Phase
   └── Actor Agent runs
       └── Checks safety rules
       └── Requests approval if needed
       └── Executes action
       └── Returns ActionResult

6. Notification Phase
   └── Notifier Agent runs
       └── Posts to Slack
       └── Updates PagerDuty
       └── Creates tickets

7. Learning Phase
   └── Store incident
   └── Update patterns
   └── Improve for next time
```

## Security Model

### Authentication

- API key authentication for REST API
- JWT tokens for WebSocket connections
- Slack signature verification for webhooks
- mTLS for internal communication

### Authorization

```yaml
# Role-based access control
roles:
  viewer:
    - "*.get_*"
    - "*.list_*"
  operator:
    - "*.get_*"
    - "*.list_*"
    - "slack.post_*"
    - "kubernetes.scale"
  admin:
    - "*"

users:
  - name: alice
    role: admin
  - name: bob
    role: operator
```

### Audit Logging

```python
# All actions are logged
@audit_log
async def rollback(deployment: str, namespace: str):
    """Rollback a deployment."""
    # ... implementation
```

## Scalability

### Horizontal Scaling

```yaml
# docker-compose.scale.yaml
services:
  opensre:
    image: opensre:latest
    deploy:
      replicas: 3
    environment:
      - OPENSRE_REDIS_URL=redis://redis:6379
```

### Message Queue

For high-throughput deployments:

```yaml
config:
  message_bus:
    type: redis  # or kafka, rabbitmq
    url: redis://redis:6379
```

### Database Options

- **SQLite** — Default, good for single instance
- **PostgreSQL** — Recommended for production
- **Redis** — For caching and pub/sub

## Extension Points

### Custom Agents

Write Python agents for complex logic.

### Custom Skills

Create skills for your internal tools.

### Custom Reasoners

Implement custom reasoning strategies:

```python
class MyReasoner(ReasonerAgent):
    async def reason(self, context, observations):
        # Your custom reasoning logic
        pass
```

## Next Steps

- **[Deployment](deployment.md)** — Production deployment guide
- **[API Reference](api-reference.md)** — Complete API documentation
