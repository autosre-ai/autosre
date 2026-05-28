"""
Investigation Planner

Plans investigation steps based on the alert and available context.
Uses LLM when available for intelligent planning, falls back to heuristics.
"""
import json
import logging
import os
from typing import List, Optional, Any
from dataclasses import dataclass, field

from .state_machine import InvestigationContext


logger = logging.getLogger(__name__)


@dataclass
class InvestigationStep:
    """A planned investigation step."""
    id: str
    action: str  # gather_metrics, check_logs, query_topology, etc.
    target: str  # What to investigate
    reason: str  # Why this step
    priority: int = 1
    dependencies: List[str] = field(default_factory=list)
    completed: bool = False
    result: Optional[dict] = None


class LLMClient:
    """
    Lightweight LLM client for planning.
    Auto-detects provider from environment.
    """
    
    def __init__(self):
        self.provider = None
        self.client = None
        self._setup()
    
    def _setup(self):
        """Set up LLM client based on available API keys."""
        # Try Anthropic first
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=anthropic_key)
                self.provider = "anthropic"
                logger.debug("Planner using Anthropic Claude")
                return
            except ImportError:
                pass
        
        # Try OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=openai_key)
                self.provider = "openai"
                logger.debug("Planner using OpenAI")
                return
            except ImportError:
                pass
        
        # Try Ollama (local)
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        try:
            import httpx
            response = httpx.get(f"{ollama_host}/api/tags", timeout=2.0)
            if response.status_code == 200:
                self.provider = "ollama"
                self.client = ollama_host
                logger.debug("Planner using Ollama")
                return
        except Exception:
            pass
        
        logger.debug("No LLM available for planner, using heuristics")
    
    @property
    def available(self) -> bool:
        """Check if an LLM is available."""
        return self.provider is not None
    
    async def generate(self, prompt: str) -> Optional[str]:
        """Generate a response from the LLM."""
        if not self.available:
            return None
        
        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
            
            elif self.provider == "ollama":
                import httpx
                response = httpx.post(
                    f"{self.client}/api/generate",
                    json={
                        "model": "qwen3:14b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": 1500}
                    },
                    timeout=60.0
                )
                if response.status_code == 200:
                    return response.json().get("response", "")
        except Exception as e:
            logger.warning(f"LLM generation failed: {e}")
        
        return None


class Planner:
    """
    Plans investigation steps using LLM reasoning.
    
    Takes:
    - Alert information
    - Current context
    - Available skills
    
    Produces:
    - Ordered list of investigation steps
    - Reasoning for each step
    """
    
    # Available investigation actions
    AVAILABLE_ACTIONS = [
        "gather_metrics",       # Query Prometheus/metrics
        "check_logs",           # Search Elasticsearch/logs
        "query_topology",       # Check service dependencies
        "check_changes",        # Recent deployments/configs
        "check_kubernetes",     # Pod status, events
        "check_traces",         # Distributed tracing
        "check_memory",         # Past similar incidents
        "check_runbooks",       # Relevant runbooks
    ]
    
    def __init__(self, llm_router=None):
        self.llm_router = llm_router
        self._llm_client = None
    
    @property
    def llm_client(self) -> LLMClient:
        """Lazy-initialize LLM client."""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    def _build_plan_prompt(
        self,
        alert: dict,
        context: InvestigationContext,
        available_skills: List[str],
    ) -> str:
        """Build a prompt for the LLM to generate an investigation plan."""
        
        alert_info = f"""
ALERT INFORMATION:
- Type: {alert.get('alert_type', alert.get('type', 'unknown'))}
- Service: {alert.get('service', 'unknown')}
- Severity: {alert.get('severity', 'unknown')}
- Message: {alert.get('message', alert.get('alert', 'No message'))}
"""
        
        context_info = ""
        if context:
            context_info = f"""
CURRENT CONTEXT:
- Investigation ID: {getattr(context, 'investigation_id', 'N/A')}
- Hypotheses so far: {len(getattr(context, 'hypotheses', []))}
- Evidence collected: {len(getattr(context, 'evidence', []))}
"""
        
        return f"""You are an expert SRE planning an incident investigation.

{alert_info}
{context_info}

AVAILABLE INVESTIGATION ACTIONS:
{', '.join(self.AVAILABLE_ACTIONS)}

SKILLS AVAILABLE:
{', '.join(available_skills) if available_skills else 'All standard skills'}

Generate an investigation plan as a JSON array of steps. Each step should have:
- id: unique identifier
- action: one of the available actions
- target: what to investigate (service name, metric name, etc.)
- reason: why this step is important
- priority: 1-5 (1 is highest priority)
- dependencies: list of step IDs that must complete first (empty for first steps)

Return ONLY valid JSON array, no other text. Example:
[
  {{"id": "step1", "action": "gather_metrics", "target": "api-service", "reason": "Check error rates", "priority": 1, "dependencies": []}},
  {{"id": "step2", "action": "check_logs", "target": "api-service", "reason": "Find error patterns", "priority": 2, "dependencies": ["step1"]}}
]

Generate a focused plan (3-6 steps) for this specific alert. Prioritize steps that will quickly identify the root cause."""

    def _parse_plan_response(self, response: str) -> List[InvestigationStep]:
        """Parse LLM response into investigation steps."""
        try:
            # Clean up response - extract JSON array
            text = response.strip()
            
            # Find JSON array in response
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("No JSON array found in LLM response")
                return []
            
            json_text = text[start_idx:end_idx]
            steps_data = json.loads(json_text)
            
            steps = []
            for step in steps_data:
                # Validate action
                action = step.get("action", "")
                if action not in self.AVAILABLE_ACTIONS:
                    logger.debug(f"Skipping unknown action: {action}")
                    continue
                
                steps.append(InvestigationStep(
                    id=step.get("id", f"step_{len(steps)}"),
                    action=action,
                    target=step.get("target", "unknown"),
                    reason=step.get("reason", "No reason provided"),
                    priority=step.get("priority", 1),
                    dependencies=step.get("dependencies", []),
                ))
            
            return steps
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM plan response: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error parsing plan: {e}")
            return []

    def _generate_heuristic_plan(
        self,
        alert: dict,
        context: InvestigationContext,
    ) -> List[InvestigationStep]:
        """Generate a heuristic-based plan when LLM is unavailable."""
        service = alert.get("service", "unknown")
        alert_type = alert.get("alert_type", alert.get("type", "")).lower()
        message = alert.get("message", alert.get("alert", "")).lower()
        
        steps = []
        
        # Always start with metrics
        steps.append(InvestigationStep(
            id="gather_metrics",
            action="gather_metrics",
            target=service,
            reason="Get current state of affected service",
            priority=1,
        ))
        
        # Check for specific alert types
        if "latency" in alert_type or "latency" in message or "slow" in message:
            steps.append(InvestigationStep(
                id="check_traces",
                action="check_traces",
                target=service,
                reason="Analyze request latency breakdown",
                priority=2,
                dependencies=["gather_metrics"],
            ))
        
        if "error" in alert_type or "error" in message or "500" in message:
            steps.append(InvestigationStep(
                id="check_logs",
                action="check_logs",
                target=service,
                reason="Find error patterns and stack traces",
                priority=2,
                dependencies=["gather_metrics"],
            ))
        
        if "memory" in message or "oom" in message or "cpu" in message:
            steps.append(InvestigationStep(
                id="check_kubernetes",
                action="check_kubernetes",
                target=service,
                reason="Check pod resource usage and events",
                priority=2,
                dependencies=["gather_metrics"],
            ))
        
        # Always check recent changes
        steps.append(InvestigationStep(
            id="check_changes",
            action="check_changes",
            target=service,
            reason="Look for recent deployments that may have caused the issue",
            priority=3,
            dependencies=["gather_metrics"],
        ))
        
        # Check past incidents for patterns
        steps.append(InvestigationStep(
            id="check_memory",
            action="check_memory",
            target=service,
            reason="Find similar past incidents and their resolutions",
            priority=4,
            dependencies=[],
        ))
        
        # Check dependencies if no clear cause found
        steps.append(InvestigationStep(
            id="check_dependencies",
            action="query_topology",
            target=service,
            reason="Check upstream dependencies for cascading issues",
            priority=5,
            dependencies=["check_changes"],
        ))
        
        return steps
    
    async def plan(
        self,
        alert: dict,
        context: InvestigationContext,
        available_skills: List[str],
    ) -> List[InvestigationStep]:
        """Generate an investigation plan."""
        
        # Try LLM-based planning first
        if self.llm_client.available:
            prompt = self._build_plan_prompt(alert, context, available_skills)
            response = await self.llm_client.generate(prompt)
            
            if response:
                steps = self._parse_plan_response(response)
                if steps:
                    logger.info(f"Generated LLM plan with {len(steps)} steps")
                    return steps
        
        # Fall back to heuristic planning
        logger.info("Using heuristic planning")
        return self._generate_heuristic_plan(alert, context)
    
    async def replan(
        self,
        context: InvestigationContext,
        new_findings: dict,
    ) -> List[InvestigationStep]:
        """Adjust plan based on new findings."""
        
        # Check if we need to add new steps based on findings
        additional_steps = []
        
        evidence = new_findings.get("evidence", [])
        for ev in evidence:
            # If we found a deployment change, investigate it further
            if ev.get("source") == "changes" and ev.get("data", {}).get("recent_deploys"):
                additional_steps.append(InvestigationStep(
                    id="investigate_deploy",
                    action="check_logs",
                    target=ev["data"]["recent_deploys"][0].get("service", "unknown"),
                    reason="Investigate recent deployment that may be related",
                    priority=1,
                ))
            
            # If we found resource issues, dig deeper
            if ev.get("source") == "kubernetes":
                pod_status = ev.get("data", {}).get("pod_status", "")
                if "OOM" in pod_status or "CrashLoop" in pod_status:
                    additional_steps.append(InvestigationStep(
                        id="investigate_resources",
                        action="gather_metrics",
                        target=f"{context.service_name}_memory",
                        reason="Deep dive into resource exhaustion",
                        priority=1,
                    ))
        
        return additional_steps
