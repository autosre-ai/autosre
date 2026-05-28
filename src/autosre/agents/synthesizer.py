"""
Investigation Synthesizer

Synthesizes findings from multiple investigation steps into
coherent hypotheses and conclusions.

Uses LLM when available for intelligent synthesis, falls back to heuristics.
"""
import json
import logging
import os
from typing import List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel

from .state import InvestigationState, Hypothesis as StateHypothesis

logger = logging.getLogger(__name__)


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
    
    Uses LLM when available for richer synthesis.
    """
    
    def __init__(self, llm_router=None):
        self.llm_router = llm_router
        self._llm_available = None
    
    def _check_llm_available(self) -> bool:
        """Check if an LLM is available for synthesis."""
        if self._llm_available is not None:
            return self._llm_available
        
        # Check for API keys
        if os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"):
            self._llm_available = True
            return True
        
        # Check for Ollama
        try:
            import httpx
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            response = httpx.get(f"{host}/api/tags", timeout=2.0)
            self._llm_available = response.status_code == 200
        except Exception:
            self._llm_available = False
        
        return self._llm_available
    
    def _build_synthesis_prompt(self, state: InvestigationState, evidence: List[str]) -> str:
        """Build prompt for LLM synthesis."""
        alert_info = f"Alert: {state.alert.name}\nService: {state.alert.service or 'unknown'}\nSeverity: {state.alert.severity}"
        
        evidence_text = "\n".join(f"- {e}" for e in evidence[:20])  # Limit evidence
        
        hypotheses_text = ""
        for h in state.hypotheses[:5]:
            hypotheses_text += f"\n- {h.hypothesis} (confidence: {h.confidence:.0%})"
        
        return f"""Synthesize the following incident investigation findings into a concise summary.

{alert_info}

EVIDENCE COLLECTED:
{evidence_text}

CURRENT HYPOTHESES:{hypotheses_text}

Provide a JSON response with:
- summary: A 1-2 sentence summary of what happened
- root_cause: The most likely root cause
- confidence: Confidence 0-1 in the root cause
- timeline: Array of key events in order
- recommendations: Array of immediate actions

Respond only with valid JSON."""

    async def _llm_synthesize(self, state: InvestigationState, evidence: List[str]) -> Optional[dict]:
        """Use LLM to synthesize findings."""
        try:
            prompt = self._build_synthesis_prompt(state, evidence)
            
            # Try Anthropic
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            if anthropic_key:
                from anthropic import Anthropic
                client = Anthropic(api_key=anthropic_key)
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
                return self._parse_llm_response(response.content[0].text)
            
            # Try OpenAI
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
                return self._parse_llm_response(response.choices[0].message.content)
            
            # Try Ollama
            import httpx
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            response = httpx.post(
                f"{host}/api/generate",
                json={"model": "qwen3:14b", "prompt": prompt, "stream": False},
                timeout=30.0
            )
            if response.status_code == 200:
                return self._parse_llm_response(response.json().get("response", ""))
                
        except Exception as e:
            logger.warning(f"LLM synthesis failed: {e}")
        
        return None
    
    def _parse_llm_response(self, text: str) -> Optional[dict]:
        """Parse LLM JSON response."""
        try:
            # Extract JSON from response
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        return None
    
    async def synthesize(
        self,
        state: InvestigationState,
    ) -> Synthesis:
        """Synthesize findings into hypotheses."""
        
        # Aggregate evidence from all agent results
        all_evidence = []
        for result in state.agent_results.values():
            for evidence in result.evidence:
                all_evidence.append(evidence.finding)
        
        # Try LLM synthesis if available
        llm_result = None
        if self._check_llm_available():
            llm_result = await self._llm_synthesize(state, all_evidence)
            if llm_result:
                logger.info("Using LLM synthesis")
        
        # Create synthesis from existing hypotheses
        primary = state.hypotheses[0] if state.hypotheses else None
        
        # Build summary
        if llm_result:
            summary = llm_result.get("summary", "")
            root_cause = llm_result.get("root_cause") or state.root_cause
            confidence = llm_result.get("confidence", state.confidence)
            timeline = llm_result.get("timeline", [])
        else:
            # Heuristic summary
            summary = self._build_heuristic_summary(state, all_evidence)
            root_cause = state.root_cause
            confidence = state.confidence
            timeline = []
        
        return Synthesis(
            hypotheses=state.hypotheses,
            primary_hypothesis=primary,
            timeline=timeline,
            affected_services=[state.alert.service] if state.alert.service else [],
            summary=summary,
            root_cause=root_cause,
            confidence=confidence,
        )
    
    def _build_heuristic_summary(self, state: InvestigationState, evidence: List[str]) -> str:
        """Build a summary without LLM."""
        if state.conclusion:
            return state.conclusion
        
        parts = []
        if state.alert.service:
            parts.append(f"Investigation of {state.alert.service}")
        else:
            parts.append("Investigation")
        
        if state.root_cause:
            parts.append(f"identified {state.root_cause}")
        elif state.hypotheses:
            parts.append(f"top hypothesis: {state.hypotheses[0].hypothesis}")
        
        if evidence:
            parts.append(f"with {len(evidence)} evidence points")
        
        return ". ".join(parts) + "."
    
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
