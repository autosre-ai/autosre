"""
Reasoner - LLM-powered root cause analysis.

The reasoner uses context from the foundation layer
to analyze incidents and determine root cause.
"""

import json
from datetime import datetime, timezone
from typing import Optional, Any

from pydantic import BaseModel, Field

from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import Alert, Incident, Severity


class ReasonerConfig(BaseModel):
    """Configuration for the reasoner."""
    model: str = Field(default="qwen3:14b", description="LLM model to use")
    provider: str = Field(default="ollama", description="LLM provider (ollama, openai, anthropic)")
    temperature: float = Field(default=0.1, description="LLM temperature")
    max_tokens: int = Field(default=2000, description="Max response tokens")
    
    # Ollama settings
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama server URL")
    
    # Reasoning settings
    enable_chain_of_thought: bool = Field(default=True)
    show_confidence: bool = Field(default=True)


class AnalysisResult(BaseModel):
    """Result of incident analysis."""
    alert_name: str
    service_name: Optional[str] = None
    
    # Analysis
    root_cause: str = Field(..., description="Identified root cause")
    confidence: float = Field(..., ge=0, le=1, description="Confidence 0-1")
    reasoning: str = Field(..., description="Chain of thought reasoning")
    
    # Recommendations
    immediate_actions: list[str] = Field(default_factory=list)
    runbook_suggestions: list[str] = Field(default_factory=list)
    escalation_needed: bool = Field(default=False)
    
    # Related data
    related_changes: list[str] = Field(default_factory=list)
    affected_services: list[str] = Field(default_factory=list)
    
    # Metadata
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    analysis_time_ms: Optional[float] = None


class Reasoner:
    """
    LLM-powered incident reasoner.
    
    Uses context from the foundation layer to:
    - Analyze alerts and identify root cause
    - Suggest remediation actions
    - Find relevant runbooks
    - Determine if escalation is needed
    """
    
    def __init__(
        self,
        context_store: ContextStore,
        config: Optional[ReasonerConfig] = None,
    ):
        """
        Initialize reasoner.
        
        Args:
            context_store: Context store for foundation data
            config: Reasoner configuration
        """
        self.context_store = context_store
        self.config = config or ReasonerConfig()
        self._client = None
    
    async def analyze(self, alert: Alert) -> AnalysisResult:
        """
        Analyze an alert and determine root cause.
        
        Args:
            alert: The alert to analyze
            
        Returns:
            Analysis result with root cause and recommendations
        """
        import time
        start_time = time.time()
        
        # Gather context
        context = await self._gather_context(alert)
        
        # Build prompt
        prompt = self._build_analysis_prompt(alert, context)
        
        # Query LLM
        response = await self._query_llm(prompt)
        
        # Parse response
        result = self._parse_response(response, alert)
        
        result.analysis_time_ms = (time.time() - start_time) * 1000
        
        return result
    
    async def _gather_context(self, alert: Alert) -> dict:
        """Gather relevant context for the alert."""
        context = {
            "alert": {
                "name": alert.name,
                "severity": alert.severity.value,
                "summary": alert.summary,
                "description": alert.description,
                "service": alert.service_name,
                "labels": alert.labels,
                "fired_at": alert.fired_at.isoformat(),
            },
            "recent_changes": [],
            "service_info": None,
            "ownership": None,
            "related_alerts": [],
            "runbooks": [],
        }
        
        # Get recent changes
        changes = self.context_store.get_recent_changes(
            service_name=alert.service_name,
            hours=24,
            limit=10,
        )
        context["recent_changes"] = [
            {
                "type": c.change_type.value,
                "service": c.service_name,
                "description": c.description,
                "author": c.author,
                "timestamp": c.timestamp.isoformat(),
                "successful": c.successful,
            }
            for c in changes
        ]
        
        # Get service info
        if alert.service_name:
            service = self.context_store.get_service(alert.service_name)
            if service:
                context["service_info"] = {
                    "name": service.name,
                    "status": service.status.value,
                    "replicas": service.replicas,
                    "ready_replicas": service.ready_replicas,
                    "dependencies": service.dependencies,
                }
            
            # Get ownership
            ownership = self.context_store.get_ownership(alert.service_name)
            if ownership:
                context["ownership"] = {
                    "team": ownership.team,
                    "tier": ownership.tier,
                    "slack_channel": ownership.slack_channel,
                }
        
        # Get related alerts
        firing = self.context_store.get_firing_alerts()
        context["related_alerts"] = [
            {"name": a.name, "service": a.service_name}
            for a in firing
            if a.id != alert.id
        ][:5]
        
        # Find runbooks
        runbooks = self.context_store.find_runbook(alert_name=alert.name)
        if not runbooks and alert.service_name:
            runbooks = self.context_store.find_runbook(service_name=alert.service_name)
        
        context["runbooks"] = [
            {"id": r.id, "title": r.title, "automated": r.automated}
            for r in runbooks
        ][:3]
        
        return context
    
    def _build_analysis_prompt(self, alert: Alert, context: dict) -> str:
        """Build the analysis prompt for the LLM."""
        prompt = f"""You are an expert SRE analyzing an incident. Analyze the following alert and context to determine the root cause.

## Alert
- Name: {alert.name}
- Severity: {alert.severity.value}
- Summary: {alert.summary}
- Description: {alert.description or 'N/A'}
- Service: {alert.service_name or 'Unknown'}
- Fired at: {alert.fired_at.isoformat()}

## Recent Changes (last 24 hours)
"""
        
        if context["recent_changes"]:
            for change in context["recent_changes"]:
                prompt += f"- [{change['timestamp']}] {change['type']} on {change['service']}: {change['description']} (by {change['author']}, successful: {change['successful']})\n"
        else:
            prompt += "- No recent changes recorded\n"
        
        prompt += "\n## Service Status\n"
        if context["service_info"]:
            svc = context["service_info"]
            prompt += f"- Status: {svc['status']}\n"
            prompt += f"- Replicas: {svc['ready_replicas']}/{svc['replicas']}\n"
            prompt += f"- Dependencies: {', '.join(svc['dependencies']) or 'None'}\n"
        else:
            prompt += "- No service information available\n"
        
        prompt += "\n## Related Alerts\n"
        if context["related_alerts"]:
            for ra in context["related_alerts"]:
                prompt += f"- {ra['name']} on {ra['service']}\n"
        else:
            prompt += "- No other alerts firing\n"
        
        prompt += "\n## Available Runbooks\n"
        if context["runbooks"]:
            for rb in context["runbooks"]:
                prompt += f"- {rb['id']}: {rb['title']} (automated: {rb['automated']})\n"
        else:
            prompt += "- No matching runbooks found\n"
        
        prompt += """

## Analysis Instructions
1. Identify the most likely root cause based on the context
2. Consider recent changes as the primary suspects
3. Look for patterns across related alerts
4. Suggest immediate actions to mitigate
5. Recommend relevant runbooks if available
6. Indicate if escalation is needed

Respond in JSON format:
{
    "root_cause": "Brief description of the root cause",
    "confidence": 0.0-1.0,
    "reasoning": "Step by step reasoning that led to this conclusion",
    "immediate_actions": ["action1", "action2"],
    "runbook_suggestions": ["runbook_id1"],
    "escalation_needed": true/false,
    "related_changes": ["change descriptions that may be related"],
    "affected_services": ["service1", "service2"]
}
"""
        
        return prompt
    
    async def _query_llm(self, prompt: str) -> str:
        """Query the LLM."""
        if self.config.provider == "ollama":
            return await self._query_ollama(prompt)
        elif self.config.provider == "openai":
            return await self._query_openai(prompt)
        elif self.config.provider == "anthropic":
            return await self._query_anthropic(prompt)
        else:
            raise ValueError(f"Unknown provider: {self.config.provider}")
    
    async def _query_ollama(self, prompt: str) -> str:
        """Query Ollama."""
        import httpx
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.config.ollama_host}/api/generate",
                json={
                    "model": self.config.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                    },
                },
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                raise RuntimeError(f"Ollama error: {response.text}")
    
    async def _query_openai(self, prompt: str) -> str:
        """Query OpenAI."""
        import openai
        
        client = openai.AsyncOpenAI()
        response = await client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        
        return response.choices[0].message.content or ""
    
    async def _query_anthropic(self, prompt: str) -> str:
        """Query Anthropic."""
        import anthropic
        
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        
        return response.content[0].text
    
    def _parse_response(self, response: str, alert: Alert) -> AnalysisResult:
        """Parse LLM response into AnalysisResult."""
        # Try to extract JSON from response
        import re
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        
        if json_match:
            try:
                data = json.loads(json_match.group())
                return AnalysisResult(
                    alert_name=alert.name,
                    service_name=alert.service_name,
                    root_cause=data.get("root_cause", "Unable to determine root cause"),
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=data.get("reasoning", response),
                    immediate_actions=data.get("immediate_actions", []),
                    runbook_suggestions=data.get("runbook_suggestions", []),
                    escalation_needed=data.get("escalation_needed", False),
                    related_changes=data.get("related_changes", []),
                    affected_services=data.get("affected_services", []),
                )
            except json.JSONDecodeError:
                pass
        
        # Fallback if JSON parsing fails
        return AnalysisResult(
            alert_name=alert.name,
            service_name=alert.service_name,
            root_cause="Unable to parse analysis - raw response available",
            confidence=0.3,
            reasoning=response,
            immediate_actions=[],
            runbook_suggestions=[],
            escalation_needed=True,  # Escalate if we can't analyze
            related_changes=[],
            affected_services=[],
        )
