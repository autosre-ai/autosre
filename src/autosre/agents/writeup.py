"""
Writeup Generator

Generates human-readable incident reports and postmortems.
"""
import logging
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from .state import InvestigationState
from .synthesizer import Synthesis
from ..llm import get_router
from ..llm.router import TaskType


logger = logging.getLogger(__name__)


WRITEUP_SYSTEM_PROMPT = """You are an expert SRE incident report writer. Generate clear, actionable incident reports.

Your reports should:
- Be concise but comprehensive
- Focus on facts and evidence
- Provide actionable recommendations
- Use clear, professional language
- Include specific technical details when relevant

Format your response as JSON with these fields:
- timeline: A markdown-formatted chronological timeline of events
- impact: Description of user/business impact
- resolution: Steps taken or recommended to resolve
- recommendations: Array of actionable follow-up items"""


class IncidentReport(BaseModel):
    """A generated incident report."""
    title: str
    summary: str
    timeline: str = ""
    root_cause: str = ""
    impact: str = ""
    resolution: str = ""
    recommendations: list[str] = []
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def _format_recommendations(self) -> str:
        """Format recommendations as markdown list."""
        if not self.recommendations:
            return "- No recommendations yet"
        return "\n".join(f"- {r}" for r in self.recommendations)
    
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
{self._format_recommendations()}
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
        self.llm_router = llm_router or get_router()
    
    def _build_report_prompt(
        self,
        state: InvestigationState,
        synthesis: Synthesis,
    ) -> str:
        """Build prompt for LLM-powered report generation."""
        # Collect evidence from agent results
        evidence_items = []
        for agent_name, result in state.agent_results.items():
            for ev in result.evidence:
                evidence_items.append(f"- [{agent_name}] {ev.finding} (confidence: {ev.confidence:.0%})")
        
        evidence_text = "\n".join(evidence_items) if evidence_items else "No evidence collected yet"
        
        # Format hypotheses
        hypotheses_text = "\n".join(
            f"- {h.hypothesis} (confidence: {h.confidence:.0%})"
            for h in synthesis.hypotheses
        ) if synthesis.hypotheses else "No hypotheses generated"
        
        return f"""Generate an incident report for the following alert and investigation.

## Alert
- Name: {state.alert.name}
- Service: {state.alert.service or 'Unknown'}
- Severity: {state.alert.severity}
- Description: {state.alert.description or 'No description'}
- Triggered: {state.alert.timestamp.isoformat()}

## Investigation Summary
{synthesis.summary}

## Root Cause
{state.root_cause or 'Under investigation'}

## Evidence Collected
{evidence_text}

## Hypotheses
{hypotheses_text}

## Affected Services
{', '.join(synthesis.affected_services) or 'Unknown'}

Generate a comprehensive incident report with timeline, impact assessment, resolution steps, and recommendations."""
    
    async def generate_report(
        self,
        state: InvestigationState,
        synthesis: Synthesis,
    ) -> IncidentReport:
        """Generate a full incident report using LLM."""
        # Build base report from state
        base_report = IncidentReport(
            title=f"Incident Report: {state.alert.name}",
            summary=synthesis.summary,
            root_cause=state.root_cause or "Under investigation",
        )
        
        # Try LLM enhancement if router is configured
        try:
            prompt = self._build_report_prompt(state, synthesis)
            response = await self.llm_router.complete(
                prompt,
                task=TaskType.WRITEUP,
                system_prompt=WRITEUP_SYSTEM_PROMPT,
            )
            
            # Parse LLM response for enhanced fields
            enhanced = self._parse_llm_response(response.content)
            
            return IncidentReport(
                title=base_report.title,
                summary=synthesis.summary,
                timeline=enhanced.get("timeline", "Timeline pending"),
                root_cause=state.root_cause or "Under investigation",
                impact=enhanced.get("impact", "Impact assessment pending"),
                resolution=enhanced.get("resolution", "Resolution pending"),
                recommendations=enhanced.get("recommendations", []),
            )
            
        except Exception as e:
            logger.warning(f"LLM writeup enhancement failed: {e}, using basic report")
            return base_report
    
    def _parse_llm_response(self, content: str) -> dict:
        """Parse LLM response, handling both JSON and plain text."""
        import json
        
        # Try to parse as JSON first
        try:
            # Handle markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            return json.loads(content)
        except json.JSONDecodeError:
            # Fall back to extracting key information from text
            return {
                "timeline": "Timeline pending LLM integration",
                "impact": "Impact assessment pending",
                "resolution": "Resolution pending",
                "recommendations": [],
            }
    
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
