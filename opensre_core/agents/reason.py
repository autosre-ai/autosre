"""
Reasoner Agent - Analyzes observations and determines root cause
"""

from dataclasses import dataclass, field
from typing import Any

from opensre_core.adapters.llm import LLMAdapter
from opensre_core.agents.observe import ObservationResult
from opensre_core.utils.prompts import REASONER_SYSTEM_PROMPT, REASONER_ANALYSIS_PROMPT


@dataclass
class Hypothesis:
    """A potential root cause hypothesis."""
    description: str
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)
    category: str = "unknown"  # resource, network, application, config, external


@dataclass
class AnalysisResult:
    """Result of root cause analysis."""
    root_cause: str
    confidence: float
    hypotheses: list[Hypothesis] = field(default_factory=list)
    similar_incidents: list[str] = field(default_factory=list)
    reasoning: str = ""
    
    def to_context(self) -> str:
        """Convert analysis to text context."""
        lines = [
            f"Root Cause: {self.root_cause}",
            f"Confidence: {self.confidence:.0%}",
            "",
            "Hypotheses:",
        ]
        
        for h in self.hypotheses:
            lines.append(f"  - {h.description} ({h.confidence:.0%})")
            for e in h.evidence:
                lines.append(f"    • {e}")
        
        return "\n".join(lines)


class ReasonerAgent:
    """
    Agent that analyzes observations and determines root cause.
    
    Uses LLM to:
    - Correlate metrics, logs, and events
    - Generate hypotheses ranked by probability
    - Identify root cause
    - Find similar past incidents
    """
    
    def __init__(self):
        self.llm = LLMAdapter()
    
    async def analyze(
        self,
        observations: ObservationResult,
        runbook_context: str | None = None,
    ) -> AnalysisResult:
        """
        Analyze observations to determine root cause.
        
        Args:
            observations: Collected infrastructure observations
            runbook_context: Optional runbook context for guidance
        
        Returns:
            AnalysisResult with root cause and hypotheses
        """
        # Build prompt with observations
        prompt = REASONER_ANALYSIS_PROMPT.format(
            issue=observations.issue,
            observations=observations.to_context(),
            runbook_context=runbook_context or "No runbooks available.",
        )
        
        # Get LLM analysis
        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=REASONER_SYSTEM_PROMPT,
            temperature=0.3,  # Lower temperature for more focused analysis
        )
        
        # Parse response
        return self._parse_analysis(response.content)
    
    def _parse_analysis(self, response: str) -> AnalysisResult:
        """Parse LLM response into structured AnalysisResult."""
        # Default result
        result = AnalysisResult(
            root_cause="Unable to determine root cause",
            confidence=0.0,
            reasoning=response,
        )
        
        lines = response.strip().split("\n")
        current_section = None
        current_hypothesis = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse sections
            lower_line = line.lower()
            
            if "root cause:" in lower_line:
                result.root_cause = line.split(":", 1)[-1].strip()
                current_section = "root_cause"
                
            elif "confidence:" in lower_line:
                try:
                    conf_str = line.split(":", 1)[-1].strip().rstrip("%")
                    result.confidence = float(conf_str) / 100 if float(conf_str) > 1 else float(conf_str)
                except ValueError:
                    pass
            
            elif "hypothes" in lower_line and ":" in line:
                current_section = "hypotheses"
            
            elif "similar" in lower_line and "incident" in lower_line:
                current_section = "similar"
            
            elif current_section == "hypotheses" and line.startswith(("-", "•", "*", "1", "2", "3")):
                # Parse hypothesis
                hypothesis_text = line.lstrip("-•*0123456789. ")
                
                # Try to extract confidence
                confidence = 0.5
                if "(" in hypothesis_text and "%" in hypothesis_text:
                    try:
                        conf_part = hypothesis_text.split("(")[-1].split(")")[0]
                        conf_str = conf_part.rstrip("%").strip()
                        confidence = float(conf_str) / 100
                        hypothesis_text = hypothesis_text.split("(")[0].strip()
                    except ValueError:
                        pass
                
                current_hypothesis = Hypothesis(
                    description=hypothesis_text,
                    confidence=confidence,
                )
                result.hypotheses.append(current_hypothesis)
            
            elif current_section == "hypotheses" and current_hypothesis and line.startswith(("  ", "\t")):
                # Evidence for current hypothesis
                evidence = line.strip().lstrip("-•* ")
                current_hypothesis.evidence.append(evidence)
            
            elif current_section == "similar" and line.startswith(("-", "•", "*")):
                incident_ref = line.lstrip("-•* ").strip()
                if incident_ref:
                    result.similar_incidents.append(incident_ref)
        
        # Sort hypotheses by confidence
        result.hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        
        # If no root cause extracted, use top hypothesis
        if result.root_cause == "Unable to determine root cause" and result.hypotheses:
            result.root_cause = result.hypotheses[0].description
            result.confidence = result.hypotheses[0].confidence
        
        return result
    
    async def explain(self, analysis: AnalysisResult) -> str:
        """Generate human-friendly explanation of the analysis."""
        prompt = f"""
Based on this root cause analysis, provide a brief, clear explanation 
that a human engineer can quickly understand:

Root Cause: {analysis.root_cause}
Confidence: {analysis.confidence:.0%}

Hypotheses:
{chr(10).join(f"- {h.description} ({h.confidence:.0%})" for h in analysis.hypotheses)}

Provide:
1. A one-sentence summary
2. Key evidence supporting this conclusion
3. What to investigate if this hypothesis is wrong
"""
        
        response = await self.llm.generate(
            prompt=prompt,
            system_prompt="You are an expert SRE explaining incident analysis to a colleague.",
            temperature=0.5,
        )
        
        return response.content
