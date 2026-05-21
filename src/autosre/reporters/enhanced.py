"""
Enhanced Investigation Reporter

Generates comprehensive investigation reports with:
- AI confidence scores and evidence quality
- SLO impact and error budget burn
- Time breakdown by phase
- AI telemetry for postmortem analysis
"""
from typing import Optional, Dict, List, Any
from datetime import datetime
from dataclasses import dataclass
import json
import logging

from ..agents.state import (
    EnhancedInvestigationState,
    InvestigationPhase,
    Evidence,
    AIDecision,
    AIHypothesis,
    Change,
)

logger = logging.getLogger(__name__)


@dataclass
class ReportSection:
    """A section of the investigation report."""
    title: str
    content: str
    priority: int = 0  # Higher = more important
    

class EnhancedReporter:
    """Generates enhanced investigation reports with full AI telemetry."""
    
    def __init__(
        self,
        include_raw_telemetry: bool = False,
        include_evidence_details: bool = True,
        markdown_format: bool = True,
    ):
        self.include_raw_telemetry = include_raw_telemetry
        self.include_evidence_details = include_evidence_details
        self.markdown_format = markdown_format
    
    def generate_report(
        self,
        state: EnhancedInvestigationState,
        output_format: str = "markdown",
    ) -> str:
        """Generate a comprehensive investigation report.
        
        Args:
            state: The enhanced investigation state
            output_format: "markdown" or "json"
            
        Returns:
            Formatted report string
        """
        if output_format == "json":
            return self._generate_json_report(state)
        return self._generate_markdown_report(state)
    
    def _generate_markdown_report(self, state: EnhancedInvestigationState) -> str:
        """Generate markdown-formatted report."""
        sections = []
        
        # Header
        sections.append(self._section_header(state))
        
        # Executive Summary
        sections.append(self._section_executive_summary(state))
        
        # SLO Impact
        sections.append(self._section_slo_impact(state))
        
        # Timeline & Phase Breakdown
        sections.append(self._section_timeline(state))
        
        # Root Cause Analysis
        sections.append(self._section_root_cause(state))
        
        # Changes Correlation
        sections.append(self._section_changes(state))
        
        # Evidence Summary
        sections.append(self._section_evidence(state))
        
        # AI Telemetry
        sections.append(self._section_ai_telemetry(state))
        
        # Recommendations
        sections.append(self._section_recommendations(state))
        
        return "\n\n".join(sections)
    
    def _section_header(self, state: EnhancedInvestigationState) -> str:
        """Generate report header."""
        status_emoji = {
            "completed": "✅",
            "running": "🔄",
            "failed": "❌",
            "blocked": "⏸️",
        }.get(state.status, "❓")
        
        return f"""# Investigation Report: {state.investigation_id}

**Alert:** {state.alert.name}  
**Service:** {state.alert.service or "Unknown"}  
**Status:** {status_emoji} {state.status.upper()}  
**Phase:** {state.phase.value.title()}  
**Started:** {state.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")}  
**Duration:** {self._format_duration(state)}"""
    
    def _section_executive_summary(self, state: EnhancedInvestigationState) -> str:
        """Generate executive summary."""
        confidence_bar = self._confidence_bar(state.ai_confidence)
        
        summary = f"""## Executive Summary

**Root Cause:** {state.root_cause or "Under investigation"}  
**AI Confidence:** {confidence_bar} ({state.ai_confidence:.0%})  
**Evidence Quality:** {state.evidence_quality_score:.0%}  

{state.conclusion or "Investigation in progress..."}"""
        
        if state.triage_result:
            summary += f"""

### Triage Assessment
- **Severity:** {state.triage_result.severity_assessed.upper()}
- **Blast Radius:** {state.triage_result.blast_radius}
- **Immediate Action Required:** {"Yes ⚠️" if state.triage_result.immediate_action_required else "No"}"""
        
        return summary
    
    def _section_slo_impact(self, state: EnhancedInvestigationState) -> str:
        """Generate SLO impact section."""
        if not state.slo_context:
            return "## SLO Impact\n\n*No SLO data available*"
        
        slo = state.slo_context
        critical_indicator = "🔴" if slo.is_budget_critical else "🟢"
        
        content = f"""## SLO Impact

{critical_indicator} **Error Budget Status:** {"CRITICAL" if slo.is_budget_critical else "OK"}

| SLO | Target | Current | Budget Remaining |
|-----|--------|---------|------------------|"""
        
        for target in slo.slo_targets:
            budget_bar = self._budget_bar(target.budget_remaining_percent)
            content += f"\n| {target.name} | {target.target_percent}% | {target.current_percent:.2f}% | {budget_bar} {target.budget_remaining_percent:.1f}% |"
        
        content += f"""

**Burn Rate:** {slo.error_budget_burn_rate:.1f}x normal"""
        
        if slo.time_to_budget_exhaustion_hours:
            content += f"\n**Time to Budget Exhaustion:** {slo.time_to_budget_exhaustion_hours:.1f} hours"
        
        content += f"\n**Estimated Impact:** {state.error_budget_impact:.2f}% of monthly budget"
        
        return content
    
    def _section_timeline(self, state: EnhancedInvestigationState) -> str:
        """Generate timeline and phase breakdown."""
        content = """## Timeline & Phase Breakdown

### Phase Durations
"""
        phase_durations = state.get_duration_by_phase()
        total_duration = sum(phase_durations.values())
        
        for phase, duration in phase_durations.items():
            percentage = (duration / total_duration * 100) if total_duration > 0 else 0
            bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
            content += f"- **{phase.title()}:** {duration:.1f}s ({percentage:.0f}%) {bar}\n"
        
        content += "\n### Phase Transitions\n"
        
        for transition in state.phase_timing.transitions:
            emoji = "➡️" if transition.from_phase else "🚀"
            from_phase = transition.from_phase.value if transition.from_phase else "START"
            content += f"- {emoji} {from_phase} → {transition.to_phase.value} ({transition.timestamp.strftime('%H:%M:%S')})"
            if transition.reason:
                content += f" - {transition.reason}"
            content += "\n"
        
        return content
    
    def _section_root_cause(self, state: EnhancedInvestigationState) -> str:
        """Generate root cause analysis section."""
        content = """## Root Cause Analysis

### Hypotheses Tested
"""
        
        if not state.ai_hypotheses:
            content += "*No hypotheses recorded*\n"
        else:
            for h in sorted(state.ai_hypotheses, key=lambda x: x.current_confidence, reverse=True):
                confidence_emoji = "🎯" if h.current_confidence > 0.7 else "🔍" if h.current_confidence > 0.4 else "❓"
                content += f"\n#### {confidence_emoji} {h.hypothesis}\n"
                content += f"**Confidence:** {h.current_confidence:.0%} (started at {h.initial_confidence:.0%})\n\n"
                
                if h.supporting_evidence:
                    content += "**Supporting Evidence:**\n"
                    for e in h.supporting_evidence[:5]:
                        content += f"- ✅ {e}\n"
                
                if h.contradicting_evidence:
                    content += "\n**Contradicting Evidence:**\n"
                    for e in h.contradicting_evidence[:5]:
                        content += f"- ❌ {e}\n"
                
                if h.counter_checks_performed:
                    content += "\n**Counter-checks:**\n"
                    for c in h.counter_checks_performed:
                        content += f"- 🔬 {c}\n"
        
        # Contributing factors
        if state.contributing_factors:
            content += "\n### Contributing Factors\n"
            for factor in state.contributing_factors:
                content += f"- {factor}\n"
        
        return content
    
    def _section_changes(self, state: EnhancedInvestigationState) -> str:
        """Generate changes correlation section."""
        content = "## Recent Changes Correlation\n\n"
        
        if not state.changes_correlated:
            return content + "*No recent changes found*"
        
        # Highlight likely cause
        if state.likely_change_cause:
            lc = state.likely_change_cause
            content += f"""### ⚠️ Most Likely Cause

**{lc.description}**  
- Type: {lc.change_type}
- Time: {lc.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
- Author: {lc.author}
- Correlation Score: {lc.correlation_score:.0%}
- Rollback Available: {"Yes ✅" if lc.rollback_available else "No ❌"}

"""
        
        # All changes
        content += "### All Recent Changes\n\n"
        content += "| Time | Type | Description | Author | Correlation |\n"
        content += "|------|------|-------------|--------|-------------|\n"
        
        for change in sorted(state.changes_correlated, key=lambda c: c.correlation_score, reverse=True):
            correlation_indicator = "🔴" if change.correlation_score > 0.7 else "🟡" if change.correlation_score > 0.4 else "🟢"
            content += f"| {change.timestamp.strftime('%H:%M')} | {change.change_type} | {change.description[:40]}... | {change.author} | {correlation_indicator} {change.correlation_score:.0%} |\n"
        
        return content
    
    def _section_evidence(self, state: EnhancedInvestigationState) -> str:
        """Generate evidence summary section."""
        content = f"""## Evidence Summary

**Total Evidence Items:** {len(state.evidence_collected)}  
**Average Quality Score:** {state.evidence_quality_score:.0%}

"""
        
        if not self.include_evidence_details:
            return content + "*Detailed evidence omitted*"
        
        # Group evidence by source
        by_source: Dict[str, List[Evidence]] = {}
        for e in state.evidence_collected:
            by_source.setdefault(e.source, []).append(e)
        
        for source, evidence_list in by_source.items():
            content += f"### From: {source}\n\n"
            
            for e in evidence_list[:10]:  # Limit to 10 per source
                quality_indicator = "⭐" * max(1, int(e.quality_score * 5))
                content += f"- **[{e.skill}]** {e.finding[:200]}... {quality_indicator}\n"
            
            if len(evidence_list) > 10:
                content += f"\n*...and {len(evidence_list) - 10} more items*\n"
            
            content += "\n"
        
        return content
    
    def _section_ai_telemetry(self, state: EnhancedInvestigationState) -> str:
        """Generate AI telemetry section for postmortem analysis."""
        telemetry = state.ai_telemetry
        
        content = f"""## AI Telemetry (for Postmortem)

### Decision Statistics
- **Total Decisions:** {len(telemetry.decisions)}
- **Total LLM Calls:** {telemetry.total_llm_calls}
- **Total Tool Calls:** {telemetry.total_tool_calls}
- **Average Confidence:** {telemetry.average_confidence:.0%}

### Confidence Trend
"""
        
        # ASCII confidence trend chart
        if telemetry.confidence_trend:
            max_val = max(telemetry.confidence_trend)
            min_val = min(telemetry.confidence_trend)
            height = 5
            
            for row in range(height, 0, -1):
                threshold = min_val + (max_val - min_val) * row / height
                line = ""
                for val in telemetry.confidence_trend[-20:]:  # Last 20 points
                    if val >= threshold:
                        line += "█"
                    else:
                        line += "░"
                content += f"{threshold:.0%} |{line}\n"
            content += "     " + "─" * min(20, len(telemetry.confidence_trend)) + "\n"
        
        # Key decisions
        content += "\n### Key Decisions\n"
        
        for decision in telemetry.decisions[-10:]:
            content += f"\n**{decision.decision_type}** ({decision.timestamp.strftime('%H:%M:%S')})\n"
            content += f"- Decision: {decision.decision}\n"
            content += f"- Reasoning: {decision.reasoning[:200]}...\n"
            content += f"- Confidence: {decision.confidence:.0%}\n"
        
        return content
    
    def _section_recommendations(self, state: EnhancedInvestigationState) -> str:
        """Generate recommendations section."""
        content = "## Recommendations\n\n"
        
        recommendations = []
        
        # Based on changes
        if state.likely_change_cause and state.likely_change_cause.rollback_available:
            recommendations.append(
                f"🔄 **Consider rollback** of {state.likely_change_cause.description}"
            )
        
        # Based on SLO
        if state.slo_context and state.slo_context.is_budget_critical:
            recommendations.append(
                "⚠️ **Error budget critical** - prioritize stability over features"
            )
        
        # Based on confidence
        if state.ai_confidence < 0.5:
            recommendations.append(
                "🔍 **Low confidence** - recommend manual review and additional investigation"
            )
        
        # Based on evidence quality
        if state.evidence_quality_score < 0.5:
            recommendations.append(
                "📊 **Improve observability** - evidence quality was low"
            )
        
        # Based on mitigation
        if state.mitigation_attempted and state.mitigation_effective is False:
            recommendations.append(
                "🛠️ **Review mitigation strategies** - attempted mitigation was ineffective"
            )
        
        if not recommendations:
            recommendations.append("✅ No immediate recommendations - investigation completed successfully")
        
        for rec in recommendations:
            content += f"- {rec}\n"
        
        return content
    
    def _generate_json_report(self, state: EnhancedInvestigationState) -> str:
        """Generate JSON-formatted report."""
        report = {
            "investigation_id": state.investigation_id,
            "status": state.status,
            "phase": state.phase.value,
            "alert": state.alert.model_dump(),
            "timing": {
                "started_at": state.started_at.isoformat(),
                "completed_at": state.completed_at.isoformat() if state.completed_at else None,
                "phase_durations": state.get_duration_by_phase(),
            },
            "root_cause": {
                "conclusion": state.root_cause,
                "confidence": state.confidence,
                "ai_confidence": state.ai_confidence,
                "contributing_factors": state.contributing_factors,
            },
            "slo_impact": state.slo_context.model_dump() if state.slo_context else None,
            "error_budget_impact": state.error_budget_impact,
            "triage": state.triage_result.model_dump() if state.triage_result else None,
            "changes": {
                "correlated": [c.model_dump() for c in state.changes_correlated],
                "likely_cause": state.likely_change_cause.model_dump() if state.likely_change_cause else None,
            },
            "evidence": {
                "count": len(state.evidence_collected),
                "quality_score": state.evidence_quality_score,
                "items": [e.model_dump() for e in state.evidence_collected] if self.include_evidence_details else [],
            },
            "hypotheses": [h.model_dump() for h in state.ai_hypotheses],
            "ai_telemetry": {
                "decisions_count": len(state.ai_telemetry.decisions),
                "llm_calls": state.ai_telemetry.total_llm_calls,
                "tool_calls": state.ai_telemetry.total_tool_calls,
                "average_confidence": state.ai_telemetry.average_confidence,
                "confidence_trend": state.ai_telemetry.confidence_trend,
                "decisions": [d.model_dump() for d in state.ai_telemetry.decisions] if self.include_raw_telemetry else [],
            },
            "postmortem": {
                "generated": state.postmortem_generated,
                "path": state.postmortem_path,
            },
        }
        
        return json.dumps(report, indent=2, default=str)
    
    def _confidence_bar(self, confidence: float) -> str:
        """Generate visual confidence bar."""
        filled = int(confidence * 10)
        return "█" * filled + "░" * (10 - filled)
    
    def _budget_bar(self, percentage: float) -> str:
        """Generate visual budget bar."""
        filled = int(percentage / 10)
        if percentage < 20:
            return "🔴" + "█" * filled + "░" * (10 - filled)
        elif percentage < 50:
            return "🟡" + "█" * filled + "░" * (10 - filled)
        else:
            return "🟢" + "█" * filled + "░" * (10 - filled)
    
    def _format_duration(self, state: EnhancedInvestigationState) -> str:
        """Format investigation duration."""
        if state.completed_at:
            duration = (state.completed_at - state.started_at).total_seconds()
        else:
            duration = (datetime.utcnow() - state.started_at).total_seconds()
        
        if duration < 60:
            return f"{duration:.0f} seconds"
        elif duration < 3600:
            return f"{duration / 60:.1f} minutes"
        else:
            return f"{duration / 3600:.1f} hours"


class PostmortemGenerator:
    """Generates postmortem documents from investigation state."""
    
    def __init__(self, template_path: Optional[str] = None):
        self.template_path = template_path
        self.reporter = EnhancedReporter(
            include_raw_telemetry=True,
            include_evidence_details=True,
        )
    
    def generate(
        self,
        state: EnhancedInvestigationState,
        include_action_items: bool = True,
    ) -> str:
        """Generate a postmortem document."""
        content = f"""# Postmortem: {state.alert.name}

**Date:** {state.started_at.strftime("%Y-%m-%d")}  
**Service:** {state.alert.service or "Unknown"}  
**Duration:** {self._calculate_duration(state)}  
**Severity:** {state.triage_result.severity_assessed if state.triage_result else "Unknown"}

---

## Summary

{state.conclusion or "Investigation summary pending..."}

## Impact

"""
        
        if state.slo_context:
            content += f"""- Error budget consumed: {state.error_budget_impact:.2f}%
- Services affected: {', '.join(state.triage_result.services_affected) if state.triage_result else 'Unknown'}
- Blast radius: {state.triage_result.blast_radius if state.triage_result else 'Unknown'}
"""
        
        content += f"""
## Root Cause

{state.root_cause or "Root cause analysis in progress..."}

### Contributing Factors

"""
        for factor in state.contributing_factors:
            content += f"- {factor}\n"
        
        content += """
## Timeline

| Time | Event |
|------|-------|
"""
        
        for transition in state.phase_timing.transitions:
            content += f"| {transition.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | {transition.to_phase.value.title()}: {transition.reason or 'Phase transition'} |\n"
        
        if include_action_items:
            content += """
## Action Items

"""
            # Generate action items based on investigation
            if state.likely_change_cause:
                content += f"- [ ] Review deployment process for {state.likely_change_cause.change_type} changes\n"
            
            if state.evidence_quality_score < 0.6:
                content += "- [ ] Improve observability coverage\n"
            
            if state.slo_context and state.slo_context.is_budget_critical:
                content += "- [ ] Evaluate SLO targets and alerting thresholds\n"
            
            content += "- [ ] Update runbooks based on this incident\n"
            content += "- [ ] Schedule postmortem review meeting\n"
        
        content += """
## Lessons Learned

### What went well
- AI-assisted investigation reduced time to root cause
- Evidence gathering was systematic

### What could be improved
"""
        
        if state.phase_timing.phase_durations.get("triage", 0) > 300:
            content += "- Triage phase took longer than expected\n"
        
        if state.mitigation_attempted and state.mitigation_effective is False:
            content += "- Initial mitigation was not effective\n"
        
        content += """
---

*Generated by AutoSRE Enhanced Reporter*
"""
        
        return content
    
    def _calculate_duration(self, state: EnhancedInvestigationState) -> str:
        """Calculate human-readable duration."""
        end = state.completed_at or datetime.utcnow()
        duration = (end - state.started_at).total_seconds()
        
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
