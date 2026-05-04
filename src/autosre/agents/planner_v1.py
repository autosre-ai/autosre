"""
Investigation Planner

Plans investigation steps based on the alert and available context.
"""
from typing import List, Optional
from dataclasses import dataclass, field

from .state_machine import InvestigationContext


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
    
    def __init__(self, llm_router=None):
        self.llm_router = llm_router
    
    async def plan(
        self,
        alert: dict,
        context: InvestigationContext,
        available_skills: List[str],
    ) -> List[InvestigationStep]:
        """Generate an investigation plan."""
        # TODO: Use LLM to generate intelligent plan
        # For now, return a basic plan
        
        steps = [
            InvestigationStep(
                id="gather_metrics",
                action="gather_metrics",
                target=alert.get("service", "unknown"),
                reason="Get current state of affected service",
                priority=1,
            ),
            InvestigationStep(
                id="check_logs",
                action="check_logs",
                target=alert.get("service", "unknown"),
                reason="Look for error patterns",
                priority=2,
                dependencies=["gather_metrics"],
            ),
            InvestigationStep(
                id="check_dependencies",
                action="query_topology",
                target=alert.get("service", "unknown"),
                reason="Check upstream dependencies",
                priority=3,
                dependencies=["gather_metrics"],
            ),
        ]
        
        return steps
    
    async def replan(
        self,
        context: InvestigationContext,
        new_findings: dict,
    ) -> List[InvestigationStep]:
        """Adjust plan based on new findings."""
        # TODO: Implement adaptive replanning
        return []
