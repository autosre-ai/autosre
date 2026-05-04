"""
Subagent Base — Base class for investigation subagents.

Subagents are domain-specific investigation agents (Kubernetes, Metrics, Logs, etc.)
that gather evidence to test hypotheses. They execute skills and report findings.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..llm import BaseLLMClient, get_llm_client
from ..agents.state import (
    Evidence,
    Hypothesis,
    InvestigationState,
    InvestigationStatus,
    SubagentResult,
)

logger = logging.getLogger(__name__)


class Skill(BaseModel):
    """Definition of an executable skill."""
    
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute the skill. Override in subclasses."""
        raise NotImplementedError(f"Skill {self.name} not implemented")


class SubagentConfig(BaseModel):
    """Configuration for a subagent."""
    
    name: str
    description: str = ""
    max_loops: int = 25
    skills: list[str] = Field(default_factory=list)
    custom_prompt: str = ""


SUBAGENT_SYSTEM_TEMPLATE = """You are the {agent_name} investigation agent for an AI SRE system.
Your role is to INVESTIGATE a production incident — gather evidence from your domain and report findings.

{custom_prompt}

## Investigation Context
Alert: {alert_summary}

## Service Context
{service_context}

## Hypotheses to Test
{hypotheses}

## Available Skills
{skills_list}

## How to Work
1. Use skills to gather evidence for each hypothesis
2. Be systematic — test one hypothesis at a time
3. Record what you find (or don't find) as evidence
4. Stop when you have sufficient evidence or exhaust relevant queries

## Rules
- NEVER modify production resources — investigation is read-only
- Do NOT call the same skill with the same arguments twice
- Do NOT fabricate data — if a query returns nothing, report "no data found"
- If your domain has no relevant signals for this alert, say so and stop
- Report WHAT you found (or didn't find), with evidence

When finished, respond with a JSON summary:
{{
    "findings": "Summary of what you found",
    "evidence": [
        {{"skill": "skill_name", "query": "what you queried", "result": "what you found"}}
    ],
    "confidence": 0.0-1.0
}}"""


class BaseSubagent(ABC):
    """Base class for investigation subagents.
    
    Subclasses should:
    1. Set `name` and `description` class attributes
    2. Implement `get_skills()` to return available skills
    3. Optionally override `custom_prompt` for domain-specific guidance
    """
    
    name: str = "base"
    description: str = "Base investigation subagent"
    custom_prompt: str = ""
    
    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        max_loops: int = 25,
    ):
        self.llm_client = llm_client
        self.max_loops = max_loops
        self._skills: dict[str, Skill] = {}
    
    @abstractmethod
    def get_skills(self) -> list[Skill]:
        """Return list of available skills for this subagent."""
        pass
    
    def register_skill(self, skill: Skill) -> None:
        """Register a skill for use."""
        self._skills[skill.name] = skill
    
    async def run(
        self,
        state: InvestigationState,
        hypotheses: Optional[list[Hypothesis]] = None,
    ) -> SubagentResult:
        """Run investigation and return results.
        
        Args:
            state: Current investigation state.
            hypotheses: Specific hypotheses to test.
            
        Returns:
            SubagentResult with findings and evidence.
        """
        start_time = time.time()
        
        # Get or create LLM client
        llm = self.llm_client or get_llm_client()
        
        # Get available skills
        skills = self.get_skills()
        for skill in skills:
            self.register_skill(skill)
        
        # Build skill descriptions
        skills_list = "\n".join(
            f"- **{s.name}**: {s.description}"
            for s in skills
        )
        
        # Build hypotheses text
        if hypotheses:
            hypotheses_text = "\n".join(f"- {h.hypothesis}" for h in hypotheses)
        else:
            hypotheses_text = "No specific hypotheses — investigate broadly."
        
        # Build service context
        service_context = ""
        if state.topology_context.get("available"):
            ctx = state.topology_context
            service_context = f"""Service: {ctx.get('service', 'unknown')}
Tier: {ctx.get('tier', 'unknown')}
Dependencies: {', '.join(ctx.get('dependencies', []))}
Dependents: {', '.join(ctx.get('dependents', [])[:5])}"""
        
        # Build system prompt
        import json
        system = SUBAGENT_SYSTEM_TEMPLATE.format(
            agent_name=self.name,
            custom_prompt=self.custom_prompt,
            alert_summary=json.dumps(state.alert, indent=2),
            service_context=service_context or "No topology information available.",
            hypotheses=hypotheses_text,
            skills_list=skills_list,
        )
        
        # Run investigation loop
        evidence: list[Evidence] = []
        findings = ""
        error: Optional[str] = None
        loops = 0
        
        try:
            # Simple approach: let LLM decide which skills to use
            prompt = f"Begin investigating the alert. Use available skills to gather evidence."
            
            for loop in range(self.max_loops):
                loops = loop + 1
                
                response = await llm.complete(
                    prompt=prompt,
                    system=system,
                    max_tokens=2000,
                    temperature=0.3,
                )
                
                content = response.content
                
                # Check if response contains skill calls (simple pattern matching)
                skill_calls = self._extract_skill_calls(content)
                
                if not skill_calls:
                    # No more skill calls - agent is done
                    findings = content
                    break
                
                # Execute skill calls
                results = []
                for skill_name, skill_args in skill_calls:
                    if skill_name in self._skills:
                        try:
                            result = await self._skills[skill_name].execute(**skill_args)
                            evidence.append(Evidence(
                                source=self.name,
                                skill=skill_name,
                                query=json.dumps(skill_args),
                                result=result[:5000],  # Truncate
                            ))
                            results.append(f"[{skill_name}]: {result[:1000]}")
                        except Exception as e:
                            results.append(f"[{skill_name}]: Error - {e}")
                    else:
                        results.append(f"[{skill_name}]: Unknown skill")
                
                # Build follow-up prompt with results
                prompt = f"Skill results:\n" + "\n".join(results) + "\n\nContinue investigation or provide final findings."
        
        except Exception as e:
            logger.error(f"[SUBAGENT:{self.name}] Error: {e}")
            error = str(e)
            findings = f"Investigation failed: {e}"
        
        duration = time.time() - start_time
        
        # Parse findings JSON if present
        if not findings:
            findings = f"Agent {self.name} completed {loops} loops."
        
        logger.info(
            f"[SUBAGENT:{self.name}] Completed in {duration:.1f}s, "
            f"{loops} loops, {len(evidence)} evidence items"
        )
        
        return SubagentResult(
            agent_id=self.name,
            status=InvestigationStatus.FAILED if error else InvestigationStatus.COMPLETED,
            findings=findings,
            evidence=evidence,
            duration_seconds=duration,
            react_loops=loops,
            error=error,
        )
    
    def _extract_skill_calls(self, content: str) -> list[tuple[str, dict[str, Any]]]:
        """Extract skill calls from LLM response.
        
        Looks for patterns like:
        - @skill_name(arg1="value", arg2=123)
        - SKILL: skill_name {"arg": "value"}
        
        Returns list of (skill_name, args_dict) tuples.
        """
        import re
        import json
        
        calls: list[tuple[str, dict[str, Any]]] = []
        
        # Pattern 1: SKILL: name {json}
        pattern1 = r'SKILL:\s*(\w+)\s*(\{[^}]+\})'
        for match in re.finditer(pattern1, content):
            skill_name = match.group(1)
            try:
                args = json.loads(match.group(2))
                calls.append((skill_name, args))
            except json.JSONDecodeError:
                pass
        
        # Pattern 2: @skill_name(kwargs)
        pattern2 = r'@(\w+)\(([^)]*)\)'
        for match in re.finditer(pattern2, content):
            skill_name = match.group(1)
            args_str = match.group(2)
            try:
                # Try to parse as JSON
                args = json.loads("{" + args_str + "}")
                calls.append((skill_name, args))
            except json.JSONDecodeError:
                # Parse as simple key=value pairs
                args = {}
                for pair in args_str.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        args[k.strip()] = v.strip().strip('"\'')
                if args:
                    calls.append((skill_name, args))
        
        return calls


async def run_subagents_parallel(
    state: InvestigationState,
    subagents: list[BaseSubagent],
    hypotheses: Optional[list[Hypothesis]] = None,
) -> list[SubagentResult]:
    """Run multiple subagents in parallel.
    
    Args:
        state: Investigation state.
        subagents: List of subagent instances.
        hypotheses: Hypotheses to test.
        
    Returns:
        List of results from all subagents.
    """
    tasks = [
        subagent.run(state, hypotheses)
        for subagent in subagents
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to failed results
    final_results: list[SubagentResult] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append(SubagentResult(
                agent_id=subagents[i].name,
                status=InvestigationStatus.FAILED,
                findings=f"Subagent failed: {result}",
                error=str(result),
            ))
        else:
            final_results.append(result)
    
    return final_results
