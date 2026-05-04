"""
Writeup Generator

Generates human-readable incident reports and postmortems.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from .state import InvestigationState
from .synthesizer import Synthesis


class IncidentReport(BaseModel):
    """A generated incident report."""
    title: str
    summary: str
    timeline: str = ""
    root_cause: str = ""
    impact: str = ""
    resolution: str = ""
    recommendations: list[str] = []
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_markdown(self) -> str:
        """Render the report as Markdown."""
        return f"""# {self.title}

**Generated:** {self.generated_at.isoformat()}

## Summary
{self.summary}

## Timeline
{self.timeline if self.timeline else "Timeline pending"}

## Root Cause
{self.root_cause if self.root_cause else "Under investigation"}

## Impact
{self.impact if self.impact else "Impact assessment pending"}

## Resolution
{self.resolution if self.resolution else "Resolution pending"}

## Recommendations
{"".join(f"- {r}\n" for r in self.recommendations) if self.recommendations else "- No recommendations yet"}
"""


class WriteupGenerator:
    """
    Generates incident writeups and reports.
    
    Produces:
    - Incident summaries
    - Postmortem documents
    - Slack/PagerDuty updates
    - Runbook suggestions
    """
    
    def __init__(self, llm_router=None):
        self.llm_router = llm_router
    
    async def generate_report(
        self,
        state: InvestigationState,
        synthesis: Synthesis,
    ) -> IncidentReport:
        """Generate a full incident report."""
        # TODO: Use LLM for intelligent writeup
        
        return IncidentReport(
            title=f"Incident Report: {state.alert.name}",
            summary=synthesis.summary,
            timeline="Timeline pending",
            root_cause=state.root_cause or "Under investigation",
            impact="Impact assessment pending",
            resolution="Resolution pending",
            recommendations=[],
        )
    
    async def generate_summary(
        self,
        state: InvestigationState,
        max_length: int = 280,
    ) -> str:
        """Generate a brief summary (e.g., for Slack)."""
        if state.root_cause:
            return f"Root cause identified: {state.root_cause}"
        return f"Investigation in progress. Status: {state.status}"
    
    async def generate_postmortem(
        self,
        state: InvestigationState,
        synthesis: Synthesis,
    ) -> str:
        """Generate a full postmortem document."""
        report = await self.generate_report(state, synthesis)
        return report.to_markdown()
