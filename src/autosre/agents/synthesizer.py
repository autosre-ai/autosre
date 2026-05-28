"""
Investigation Synthesizer

Synthesizes findings from multiple investigation steps into
coherent hypotheses and conclusions.
"""
from typing import List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel

from .state import InvestigationState, Hypothesis as StateHypothesis


@dataclass
class Hypothesis:
    """A hypothesis about the root cause."""
    id: str
    description: str
    confidence: float  # 0.0 to 1.0
    evidence: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    validation_steps: List[str] = field(default_factory=list)


class Synthesis(BaseModel):
    """Synthesized findings from an investigation."""
    hypotheses: List[StateHypothesis] = []
    primary_hypothesis: Optional[StateHypothesis] = None
    timeline: List[dict] = []
    affected_services: List[str] = []
    summary: str = ""
    root_cause: Optional[str] = None
    confidence: float = 0.0


class Synthesizer:
    """
    Synthesizes investigation findings into conclusions.
    
    Responsibilities:
    - Correlate findings across different data sources
    - Generate hypotheses about root cause
    - Identify patterns and anomalies
    - Build incident timeline
    """
    
    def __init__(self, llm_router=None):
        self.llm_router = llm_router
    
    async def synthesize(
        self,
        state: InvestigationState,
    ) -> Synthesis:
        """Synthesize findings into hypotheses."""
        # TODO: Use LLM to intelligently synthesize
        
        # Aggregate evidence from all agent results
        all_evidence = []
        for result in state.agent_results.values():
            for evidence in result.evidence:
                all_evidence.append(evidence.finding)
        
        # Create synthesis from existing hypotheses
        primary = state.hypotheses[0] if state.hypotheses else None
        
        return Synthesis(
            hypotheses=state.hypotheses,
            primary_hypothesis=primary,
            timeline=[],
            affected_services=[state.alert.service] if state.alert.service else [],
            summary=state.conclusion or "Investigation synthesis pending LLM integration",
            root_cause=state.root_cause,
            confidence=state.confidence,
        )
    
    async def validate_hypothesis(
        self,
        hypothesis: StateHypothesis,
        state: InvestigationState,
    ) -> StateHypothesis:
        """Validate a hypothesis with additional checks."""
        # TODO: Implement validation logic
        return hypothesis
    
    async def correlate_findings(
        self,
        state: InvestigationState,
    ) -> List[dict]:
        """Correlate findings across data sources.
        
        Identifies relationships between evidence from different sources
        by analyzing temporal proximity, shared hypotheses, and common patterns.
        """
        correlations = []
        
        # Group evidence by source
        by_source: dict[str, list] = {}
        for result in state.agent_results.values():
            for evidence in result.evidence:
                source = evidence.source
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(evidence)
        
        # Collect all evidence with timestamps for temporal correlation
        all_evidence = []
        for result in state.agent_results.values():
            for evidence in result.evidence:
                all_evidence.append(evidence)
        
        # 1. Temporal correlation: findings within 5 minutes of each other
        for i, e1 in enumerate(all_evidence):
            for e2 in all_evidence[i + 1:]:
                if e1.source == e2.source:
                    continue  # Skip same-source correlations
                time_diff = abs((e1.timestamp - e2.timestamp).total_seconds())
                if time_diff <= 300:  # Within 5 minutes
                    correlations.append({
                        "type": "temporal",
                        "sources": [e1.source, e2.source],
                        "findings": [e1.finding, e2.finding],
                        "time_delta_seconds": time_diff,
                        "confidence": max(0.3, 1.0 - (time_diff / 300)),  # Higher confidence for closer times
                    })
        
        # 2. Hypothesis correlation: evidence supporting the same hypothesis
        by_hypothesis: dict[str, list] = {}
        for evidence in all_evidence:
            if evidence.supports_hypothesis:
                hyp = evidence.supports_hypothesis
                if hyp not in by_hypothesis:
                    by_hypothesis[hyp] = []
                by_hypothesis[hyp].append(evidence)
        
        for hyp, evidence_list in by_hypothesis.items():
            if len(evidence_list) > 1:
                # Multiple pieces of evidence support the same hypothesis
                sources = list(set(e.source for e in evidence_list))
                if len(sources) > 1:  # From different sources
                    correlations.append({
                        "type": "hypothesis",
                        "hypothesis": hyp,
                        "sources": sources,
                        "findings": [e.finding for e in evidence_list],
                        "confidence": min(1.0, sum(e.confidence for e in evidence_list) / len(evidence_list) + 0.1 * len(sources)),
                    })
        
        # 3. Cross-source validation: when multiple sources agree on similar findings
        sources = list(by_source.keys())
        for i, src1 in enumerate(sources):
            for src2 in sources[i + 1:]:
                # Check for high-confidence evidence from both sources
                high_conf_1 = [e for e in by_source[src1] if e.confidence >= 0.7]
                high_conf_2 = [e for e in by_source[src2] if e.confidence >= 0.7]
                if high_conf_1 and high_conf_2:
                    correlations.append({
                        "type": "cross_validation",
                        "sources": [src1, src2],
                        "findings": [high_conf_1[0].finding, high_conf_2[0].finding],
                        "confidence": (high_conf_1[0].confidence + high_conf_2[0].confidence) / 2,
                    })
        
        return correlations
