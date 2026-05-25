"""
Data Collector - Collect and structure investigation data for training.

Collects data from completed incident investigations to create training examples
that capture expert SRE reasoning patterns, tool usage, and decision-making.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class InvestigationOutcome(str, Enum):
    """Outcome categories for investigations."""
    
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    FALSE_POSITIVE = "false_positive"
    ONGOING = "ongoing"
    NEEDS_REVIEW = "needs_review"


class DataQuality(str, Enum):
    """Quality rating for training examples."""
    
    HIGH = "high"  # Expert-verified, complete reasoning chain
    MEDIUM = "medium"  # Complete but not verified
    LOW = "low"  # Incomplete or unclear reasoning
    EXCLUDED = "excluded"  # Not suitable for training


@dataclass
class ToolCall:
    """Record of a tool call during investigation."""
    
    tool_name: str
    arguments: dict[str, Any]
    result: Any
    timestamp: datetime
    duration_ms: int = 0
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class ReasoningStep:
    """A single step in the investigation reasoning chain."""
    
    thought: str
    action: Optional[str] = None  # Tool call or decision
    observation: Optional[str] = None  # Result of action
    tool_calls: list[ToolCall] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "thought": self.thought,
            "action": self.action,
            "observation": self.observation,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class InvestigationRecord:
    """Complete record of an investigation for training purposes."""
    
    id: str
    alert_name: str
    alert_severity: str
    alert_description: str
    service: str
    environment: str
    timestamp: datetime
    
    # Investigation content
    initial_context: str
    reasoning_steps: list[ReasoningStep]
    hypothesis: str
    root_cause: str
    resolution: str
    
    # Metadata
    outcome: InvestigationOutcome
    time_to_resolution_minutes: int
    engineer_feedback: Optional[str] = None
    quality_rating: DataQuality = DataQuality.MEDIUM
    
    # Additional context
    related_alerts: list[str] = field(default_factory=list)
    affected_components: list[str] = field(default_factory=list)
    metrics_queries: list[str] = field(default_factory=list)
    log_queries: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "alert_name": self.alert_name,
            "alert_severity": self.alert_severity,
            "alert_description": self.alert_description,
            "service": self.service,
            "environment": self.environment,
            "timestamp": self.timestamp.isoformat(),
            "initial_context": self.initial_context,
            "reasoning_steps": [rs.to_dict() for rs in self.reasoning_steps],
            "hypothesis": self.hypothesis,
            "root_cause": self.root_cause,
            "resolution": self.resolution,
            "outcome": self.outcome.value,
            "time_to_resolution_minutes": self.time_to_resolution_minutes,
            "engineer_feedback": self.engineer_feedback,
            "quality_rating": self.quality_rating.value,
            "related_alerts": self.related_alerts,
            "affected_components": self.affected_components,
            "metrics_queries": self.metrics_queries,
            "log_queries": self.log_queries,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InvestigationRecord":
        """Create from dictionary representation."""
        # Parse reasoning steps
        reasoning_steps = []
        for step_data in data.get("reasoning_steps", []):
            tool_calls = [
                ToolCall(
                    tool_name=tc["tool_name"],
                    arguments=tc["arguments"],
                    result=tc["result"],
                    timestamp=datetime.fromisoformat(tc["timestamp"]),
                    duration_ms=tc.get("duration_ms", 0),
                    success=tc.get("success", True),
                    error=tc.get("error"),
                )
                for tc in step_data.get("tool_calls", [])
            ]
            reasoning_steps.append(ReasoningStep(
                thought=step_data["thought"],
                action=step_data.get("action"),
                observation=step_data.get("observation"),
                tool_calls=tool_calls,
                timestamp=datetime.fromisoformat(step_data["timestamp"]) if step_data.get("timestamp") else None,
            ))
        
        return cls(
            id=data["id"],
            alert_name=data["alert_name"],
            alert_severity=data["alert_severity"],
            alert_description=data["alert_description"],
            service=data["service"],
            environment=data["environment"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            initial_context=data["initial_context"],
            reasoning_steps=reasoning_steps,
            hypothesis=data["hypothesis"],
            root_cause=data["root_cause"],
            resolution=data["resolution"],
            outcome=InvestigationOutcome(data["outcome"]),
            time_to_resolution_minutes=data["time_to_resolution_minutes"],
            engineer_feedback=data.get("engineer_feedback"),
            quality_rating=DataQuality(data.get("quality_rating", "medium")),
            related_alerts=data.get("related_alerts", []),
            affected_components=data.get("affected_components", []),
            metrics_queries=data.get("metrics_queries", []),
            log_queries=data.get("log_queries", []),
            tags=data.get("tags", []),
        )


@dataclass
class TrainingExample:
    """A formatted training example ready for fine-tuning."""
    
    id: str
    source_investigation_id: str
    
    # Instruction-following format
    system_prompt: str
    user_prompt: str
    assistant_response: str
    
    # Metadata
    quality_score: float  # 0.0 to 1.0
    difficulty: str  # "basic", "intermediate", "advanced"
    categories: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_investigation_id": self.source_investigation_id,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "assistant_response": self.assistant_response,
            "quality_score": self.quality_score,
            "difficulty": self.difficulty,
            "categories": self.categories,
        }
    
    def to_chat_format(self) -> list[dict[str, str]]:
        """Convert to chat completion format."""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt},
            {"role": "assistant", "content": self.assistant_response},
        ]
    
    def to_instruction_format(self) -> dict[str, str]:
        """Convert to instruction-following format."""
        return {
            "instruction": self.system_prompt + "\n\n" + self.user_prompt,
            "output": self.assistant_response,
        }


@dataclass
class CollectionConfig:
    """Configuration for data collection."""
    
    output_dir: Path
    min_quality: DataQuality = DataQuality.MEDIUM
    include_outcomes: list[InvestigationOutcome] = field(
        default_factory=lambda: [
            InvestigationOutcome.RESOLVED,
            InvestigationOutcome.FALSE_POSITIVE,
        ]
    )
    anonymize_pii: bool = True
    include_tool_outputs: bool = True
    max_reasoning_steps: int = 20
    
    # System prompt template
    system_prompt_template: str = """You are AutoSRE, an expert Site Reliability Engineering AI assistant. 
You help investigate incidents, analyze metrics and logs, and identify root causes.

Your capabilities include:
- Querying Prometheus/Grafana metrics
- Analyzing application and infrastructure logs  
- Examining Kubernetes resources
- Correlating events across systems
- Identifying patterns from past incidents

Always explain your reasoning step-by-step and cite evidence for your conclusions."""


class DataCollector:
    """Collects investigation data for training.
    
    Gathers completed investigations, extracts reasoning chains,
    and formats them as training examples.
    
    Example:
        collector = DataCollector(CollectionConfig(output_dir=Path("./data")))
        
        # Collect from an investigation
        record = collector.record_investigation(investigation_state)
        
        # Generate training examples
        examples = collector.create_training_examples(record)
        
        # Export for training
        collector.export_to_jsonl(examples, "training_data.jsonl")
    """
    
    def __init__(self, config: CollectionConfig):
        """Initialize the data collector.
        
        Args:
            config: Collection configuration
        """
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[InvestigationRecord] = []
        
    def record_investigation(
        self,
        alert_name: str,
        alert_severity: str,
        alert_description: str,
        service: str,
        environment: str,
        initial_context: str,
        reasoning_steps: list[ReasoningStep],
        hypothesis: str,
        root_cause: str,
        resolution: str,
        outcome: InvestigationOutcome,
        time_to_resolution_minutes: int,
        engineer_feedback: Optional[str] = None,
        **kwargs: Any,
    ) -> InvestigationRecord:
        """Record a completed investigation.
        
        Args:
            alert_name: Name of the triggering alert
            alert_severity: Severity level (critical, warning, etc.)
            alert_description: Alert description
            service: Affected service name
            environment: Environment (prod, staging, etc.)
            initial_context: Initial context provided
            reasoning_steps: Chain of reasoning steps
            hypothesis: Final hypothesis
            root_cause: Identified root cause
            resolution: Resolution applied
            outcome: Investigation outcome
            time_to_resolution_minutes: Time to resolve
            engineer_feedback: Optional engineer feedback
            **kwargs: Additional fields (tags, related_alerts, etc.)
            
        Returns:
            Recorded investigation record
        """
        # Truncate reasoning steps if needed
        if len(reasoning_steps) > self.config.max_reasoning_steps:
            logger.warning(
                f"Truncating reasoning steps from {len(reasoning_steps)} to {self.config.max_reasoning_steps}"
            )
            reasoning_steps = reasoning_steps[:self.config.max_reasoning_steps]
        
        # Create record
        record = InvestigationRecord(
            id=str(uuid4()),
            alert_name=alert_name,
            alert_severity=alert_severity,
            alert_description=alert_description,
            service=service,
            environment=environment,
            timestamp=datetime.utcnow(),
            initial_context=initial_context,
            reasoning_steps=reasoning_steps,
            hypothesis=hypothesis,
            root_cause=root_cause,
            resolution=resolution,
            outcome=outcome,
            time_to_resolution_minutes=time_to_resolution_minutes,
            engineer_feedback=engineer_feedback,
            quality_rating=self._assess_quality(reasoning_steps, outcome, engineer_feedback),
            related_alerts=kwargs.get("related_alerts", []),
            affected_components=kwargs.get("affected_components", []),
            metrics_queries=kwargs.get("metrics_queries", []),
            log_queries=kwargs.get("log_queries", []),
            tags=kwargs.get("tags", []),
        )
        
        # Apply anonymization if configured
        if self.config.anonymize_pii:
            record = self._anonymize_record(record)
        
        self._records.append(record)
        
        # Save to disk
        self._save_record(record)
        
        logger.info(f"Recorded investigation {record.id} with quality {record.quality_rating.value}")
        return record
    
    def _assess_quality(
        self,
        reasoning_steps: list[ReasoningStep],
        outcome: InvestigationOutcome,
        feedback: Optional[str],
    ) -> DataQuality:
        """Assess the quality of an investigation for training.
        
        Args:
            reasoning_steps: Chain of reasoning
            outcome: Investigation outcome
            feedback: Engineer feedback if available
            
        Returns:
            Quality rating
        """
        # Basic quality scoring
        score = 0
        
        # Points for number of reasoning steps
        if len(reasoning_steps) >= 3:
            score += 1
        if len(reasoning_steps) >= 5:
            score += 1
            
        # Points for tool usage
        has_tools = any(step.tool_calls for step in reasoning_steps)
        if has_tools:
            score += 1
            
        # Points for positive outcomes
        if outcome in (InvestigationOutcome.RESOLVED, InvestigationOutcome.FALSE_POSITIVE):
            score += 1
            
        # Points for engineer feedback
        if feedback:
            if "good" in feedback.lower() or "helpful" in feedback.lower():
                score += 2
            elif "bad" in feedback.lower() or "wrong" in feedback.lower():
                score -= 2
        
        # Map to quality rating
        if score >= 4:
            return DataQuality.HIGH
        elif score >= 2:
            return DataQuality.MEDIUM
        elif score >= 0:
            return DataQuality.LOW
        else:
            return DataQuality.EXCLUDED
    
    def _anonymize_record(self, record: InvestigationRecord) -> InvestigationRecord:
        """Anonymize PII in the record.
        
        Replaces IP addresses, hostnames, email addresses, etc.
        """
        import re
        
        # Patterns to anonymize
        patterns = [
            (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP_ADDRESS]"),
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
            (r"\b[a-z0-9-]+\.internal\b", "[INTERNAL_HOST]"),
            (r"\bprod-[a-z0-9-]+\b", "[PROD_HOST]"),
        ]
        
        def anonymize_text(text: str) -> str:
            for pattern, replacement in patterns:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            return text
        
        # Anonymize text fields
        record.initial_context = anonymize_text(record.initial_context)
        record.hypothesis = anonymize_text(record.hypothesis)
        record.root_cause = anonymize_text(record.root_cause)
        record.resolution = anonymize_text(record.resolution)
        
        # Anonymize reasoning steps
        for step in record.reasoning_steps:
            step.thought = anonymize_text(step.thought)
            if step.action:
                step.action = anonymize_text(step.action)
            if step.observation:
                step.observation = anonymize_text(step.observation)
        
        return record
    
    def _save_record(self, record: InvestigationRecord) -> None:
        """Save a record to disk."""
        records_dir = self.config.output_dir / "records"
        records_dir.mkdir(exist_ok=True)
        
        filepath = records_dir / f"{record.id}.json"
        with open(filepath, "w") as f:
            json.dump(record.to_dict(), f, indent=2)
    
    def load_records(self) -> list[InvestigationRecord]:
        """Load all saved records from disk."""
        records_dir = self.config.output_dir / "records"
        if not records_dir.exists():
            return []
        
        records = []
        for filepath in records_dir.glob("*.json"):
            with open(filepath) as f:
                data = json.load(f)
                records.append(InvestigationRecord.from_dict(data))
        
        logger.info(f"Loaded {len(records)} investigation records")
        return records
    
    def create_training_examples(
        self,
        record: InvestigationRecord,
    ) -> list[TrainingExample]:
        """Create training examples from an investigation record.
        
        Generates multiple training examples from a single investigation:
        - Full investigation chain
        - Individual reasoning steps
        - Root cause identification
        
        Args:
            record: Investigation record
            
        Returns:
            List of training examples
        """
        examples = []
        
        # Filter by quality
        if self._quality_order(record.quality_rating) < self._quality_order(self.config.min_quality):
            logger.debug(f"Skipping record {record.id} due to low quality")
            return examples
        
        # Filter by outcome
        if record.outcome not in self.config.include_outcomes:
            logger.debug(f"Skipping record {record.id} due to outcome {record.outcome}")
            return examples
        
        # Example 1: Full investigation
        full_example = self._create_full_investigation_example(record)
        if full_example:
            examples.append(full_example)
        
        # Example 2: Individual step reasoning
        step_examples = self._create_step_examples(record)
        examples.extend(step_examples)
        
        # Example 3: Root cause identification
        rca_example = self._create_rca_example(record)
        if rca_example:
            examples.append(rca_example)
        
        logger.info(f"Created {len(examples)} training examples from record {record.id}")
        return examples
    
    def _quality_order(self, quality: DataQuality) -> int:
        """Get ordering value for quality comparison."""
        order = {
            DataQuality.HIGH: 3,
            DataQuality.MEDIUM: 2,
            DataQuality.LOW: 1,
            DataQuality.EXCLUDED: 0,
        }
        return order.get(quality, 0)
    
    def _create_full_investigation_example(
        self,
        record: InvestigationRecord,
    ) -> Optional[TrainingExample]:
        """Create a full investigation example."""
        # Build user prompt
        user_prompt = f"""Alert: {record.alert_name}
Severity: {record.alert_severity}
Service: {record.service}
Environment: {record.environment}

{record.alert_description}

Context:
{record.initial_context}

Please investigate this alert and identify the root cause."""
        
        # Build assistant response with reasoning chain
        response_parts = []
        
        response_parts.append("I'll investigate this alert step by step.\n")
        
        for i, step in enumerate(record.reasoning_steps, 1):
            response_parts.append(f"**Step {i}: {step.thought}**\n")
            
            if step.action:
                response_parts.append(f"Action: {step.action}\n")
            
            if step.tool_calls and self.config.include_tool_outputs:
                for tc in step.tool_calls:
                    response_parts.append(f"Tool: {tc.tool_name}({tc.arguments})\n")
                    if tc.success:
                        result_str = str(tc.result)[:500]  # Truncate long outputs
                        response_parts.append(f"Result: {result_str}\n")
            
            if step.observation:
                response_parts.append(f"Observation: {step.observation}\n")
            
            response_parts.append("")
        
        response_parts.append(f"**Hypothesis:** {record.hypothesis}\n")
        response_parts.append(f"**Root Cause:** {record.root_cause}\n")
        response_parts.append(f"**Resolution:** {record.resolution}")
        
        return TrainingExample(
            id=str(uuid4()),
            source_investigation_id=record.id,
            system_prompt=self.config.system_prompt_template,
            user_prompt=user_prompt,
            assistant_response="\n".join(response_parts),
            quality_score=self._quality_to_score(record.quality_rating),
            difficulty=self._assess_difficulty(record),
            categories=["full_investigation"] + record.tags,
        )
    
    def _create_step_examples(
        self,
        record: InvestigationRecord,
    ) -> list[TrainingExample]:
        """Create examples for individual reasoning steps."""
        examples = []
        
        # Only create step examples for high-quality records
        if record.quality_rating != DataQuality.HIGH:
            return examples
        
        context_parts = [
            f"Alert: {record.alert_name}",
            f"Severity: {record.alert_severity}",
            f"Service: {record.service}",
            record.alert_description,
            "",
            "Investigation progress so far:",
        ]
        
        for i, step in enumerate(record.reasoning_steps[:-1]):
            # Build context from previous steps
            context_parts.append(f"- {step.thought}")
            if step.observation:
                context_parts.append(f"  → {step.observation}")
            
            # Next step is the target
            next_step = record.reasoning_steps[i + 1]
            
            user_prompt = "\n".join(context_parts) + "\n\nWhat should be the next investigation step?"
            
            assistant_response = f"**Next step:** {next_step.thought}"
            if next_step.action:
                assistant_response += f"\n\nAction: {next_step.action}"
            
            examples.append(TrainingExample(
                id=str(uuid4()),
                source_investigation_id=record.id,
                system_prompt=self.config.system_prompt_template,
                user_prompt=user_prompt,
                assistant_response=assistant_response,
                quality_score=self._quality_to_score(record.quality_rating),
                difficulty="intermediate",
                categories=["reasoning_step", "chain_of_thought"] + record.tags,
            ))
        
        return examples
    
    def _create_rca_example(
        self,
        record: InvestigationRecord,
    ) -> Optional[TrainingExample]:
        """Create a root cause analysis example."""
        if not record.root_cause or record.outcome != InvestigationOutcome.RESOLVED:
            return None
        
        # Summarize the investigation
        findings = []
        for step in record.reasoning_steps:
            if step.observation:
                findings.append(f"- {step.observation}")
        
        user_prompt = f"""Alert: {record.alert_name}
Service: {record.service}
Environment: {record.environment}

Investigation findings:
{chr(10).join(findings[:10])}

Based on these findings, what is the root cause?"""
        
        assistant_response = f"""Based on my analysis of the investigation findings, the root cause is:

**Root Cause:** {record.root_cause}

**Hypothesis:** {record.hypothesis}

**Recommended Resolution:** {record.resolution}"""
        
        return TrainingExample(
            id=str(uuid4()),
            source_investigation_id=record.id,
            system_prompt=self.config.system_prompt_template,
            user_prompt=user_prompt,
            assistant_response=assistant_response,
            quality_score=self._quality_to_score(record.quality_rating),
            difficulty="advanced",
            categories=["root_cause_analysis", "synthesis"] + record.tags,
        )
    
    def _quality_to_score(self, quality: DataQuality) -> float:
        """Convert quality rating to numeric score."""
        scores = {
            DataQuality.HIGH: 1.0,
            DataQuality.MEDIUM: 0.7,
            DataQuality.LOW: 0.4,
            DataQuality.EXCLUDED: 0.0,
        }
        return scores.get(quality, 0.0)
    
    def _assess_difficulty(self, record: InvestigationRecord) -> str:
        """Assess the difficulty level of an investigation."""
        score = 0
        
        # More steps = harder
        if len(record.reasoning_steps) > 10:
            score += 2
        elif len(record.reasoning_steps) > 5:
            score += 1
        
        # Multiple affected components = harder
        if len(record.affected_components) > 3:
            score += 1
        
        # Longer resolution time = harder
        if record.time_to_resolution_minutes > 60:
            score += 1
        
        if score >= 3:
            return "advanced"
        elif score >= 1:
            return "intermediate"
        else:
            return "basic"
    
    def export_to_jsonl(
        self,
        examples: list[TrainingExample],
        filename: str,
        format: str = "chat",
    ) -> Path:
        """Export training examples to JSONL file.
        
        Args:
            examples: Training examples to export
            filename: Output filename
            format: Output format ('chat', 'instruction', or 'raw')
            
        Returns:
            Path to the exported file
        """
        output_path = self.config.output_dir / filename
        
        with open(output_path, "w") as f:
            for example in examples:
                if format == "chat":
                    data = {"messages": example.to_chat_format()}
                elif format == "instruction":
                    data = example.to_instruction_format()
                else:
                    data = example.to_dict()
                
                f.write(json.dumps(data) + "\n")
        
        logger.info(f"Exported {len(examples)} examples to {output_path}")
        return output_path
    
    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about collected data."""
        records = self.load_records()
        
        if not records:
            return {"total_records": 0}
        
        quality_counts = {}
        outcome_counts = {}
        service_counts = {}
        total_steps = 0
        
        for record in records:
            quality_counts[record.quality_rating.value] = (
                quality_counts.get(record.quality_rating.value, 0) + 1
            )
            outcome_counts[record.outcome.value] = (
                outcome_counts.get(record.outcome.value, 0) + 1
            )
            service_counts[record.service] = (
                service_counts.get(record.service, 0) + 1
            )
            total_steps += len(record.reasoning_steps)
        
        return {
            "total_records": len(records),
            "quality_distribution": quality_counts,
            "outcome_distribution": outcome_counts,
            "service_distribution": service_counts,
            "avg_reasoning_steps": total_steps / len(records),
            "total_reasoning_steps": total_steps,
        }
