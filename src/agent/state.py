"""
AutoSRE Agent State Models

Pydantic models and TypedDict definitions for the LangGraph investigation graph.
Defines the shape of data flowing through the graph nodes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Reducer functions for state merging
# ---------------------------------------------------------------------------


def merge_dicts(left: dict, right: dict) -> dict:
    """Shallow merge — right overwrites left keys.
    
    Used for agent_states where each subagent adds its own key.
    """
    merged = left.copy()
    merged.update(right)
    return merged


def take_latest(_left: Any, right: Any) -> Any:
    """Always take the newer value.
    
    Used for scalar values that should be overwritten by later nodes.
    """
    return right


# ---------------------------------------------------------------------------
# Graph State (TypedDict for LangGraph)
# ---------------------------------------------------------------------------


class GraphState(TypedDict):
    """Complete investigation state flowing through the graph.
    
    This is the main state object passed between nodes. Each field is annotated
    with a reducer function that determines how updates from parallel nodes
    are merged.
    
    Fields:
        alert: The incident/alert being investigated (input)
        thread_id: Unique session identifier for this investigation
        images: Optional images attached to the alert
        
        memory_context: Results from memory lookup (past similar incidents)
        kg_context: Knowledge graph context (service topology)
        team_config: Team-specific configuration (agents, prompts, tools)
        
        investigation_id: Unique ID for this investigation run
        agent_states: Results from each subagent, keyed by agent_id
        messages: Accumulated messages/notes from all nodes
        
        hypotheses: Current hypotheses to test
        selected_agents: Agents selected by planner for current iteration
        
        conclusion: Final investigation conclusion (markdown)
        structured_report: JSON-structured investigation report
        
        iteration: Current investigation iteration (0-indexed)
        max_iterations: Maximum iterations before forcing conclusion
        max_react_loops: Maximum tool calls per subagent
        status: Current status ('running', 'completed', 'error')
    """

    # --- Input ---
    alert: dict
    thread_id: str
    images: list[dict]
    
    # --- Context (set by early nodes) ---
    memory_context: Annotated[dict, take_latest]
    kg_context: Annotated[dict, take_latest]
    team_config: dict
    
    # --- Investigation tracking ---
    investigation_id: str
    agent_states: Annotated[dict, merge_dicts]
    messages: Annotated[list, operator.add]
    
    # --- Planner ---
    hypotheses: list[dict]
    selected_agents: list[str]
    
    # --- Results ---
    conclusion: str
    structured_report: dict
    
    # --- Control flow ---
    iteration: Annotated[int, take_latest]
    max_iterations: int
    max_react_loops: int
    status: Annotated[str, take_latest]


# ---------------------------------------------------------------------------
# Pydantic models for structured LLM output
# ---------------------------------------------------------------------------


class Hypothesis(BaseModel):
    """A single investigation hypothesis.
    
    Used by the planner to structure its reasoning about potential
    root causes and which agents should investigate them.
    """

    hypothesis: str = Field(
        description="Description of potential root cause or area to investigate"
    )
    priority: Literal["high", "medium", "low"] = Field(
        description="Priority level for investigating this hypothesis"
    )
    agents_to_test: list[str] = Field(
        description="Which investigation agents should test this hypothesis",
        default_factory=list,
    )

    class Config:
        extra = "forbid"


class InvestigationPlan(BaseModel):
    """Structured output from the planner node.
    
    Contains the investigation strategy: hypotheses to test
    and agents to dispatch.
    """

    hypotheses: list[Hypothesis] = Field(
        description="Ranked hypotheses to test, ordered by priority"
    )
    selected_agents: list[str] = Field(
        description="Agents to dispatch for this investigation iteration"
    )
    reasoning: str = Field(
        description="Brief explanation of the investigation strategy"
    )

    class Config:
        extra = "forbid"


class SynthesisDecision(BaseModel):
    """Structured output from the synthesizer node.
    
    Determines whether to continue investigating or conclude.
    """

    sufficient_evidence: bool = Field(
        description="Whether there is enough evidence to write a conclusion"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level in current findings (0.0-1.0)"
    )
    summary: str = Field(
        description="Brief summary of combined findings from all agents"
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Information gaps that need filling if evidence is insufficient"
    )
    feedback: str = Field(
        default="",
        description="Specific guidance for the next investigation iteration"
    )

    class Config:
        extra = "forbid"


class AgentResult(BaseModel):
    """Result from a single investigation subagent.
    
    Captures the findings, evidence, and metadata from a subagent's
    investigation cycle.
    """

    status: Literal["completed", "error", "timeout"] = Field(
        description="How the agent's investigation ended"
    )
    findings: str = Field(
        description="The agent's findings and analysis"
    )
    evidence: list[dict] = Field(
        default_factory=list,
        description="Tool calls made during investigation"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Agent's confidence in its findings"
    )
    react_loops: int = Field(
        default=0,
        description="Number of reasoning/action loops executed"
    )
    duration_seconds: float = Field(
        default=0.0,
        description="Total execution time in seconds"
    )

    class Config:
        extra = "forbid"


# ---------------------------------------------------------------------------
# Input schema (for API/Studio)
# ---------------------------------------------------------------------------


class AlertInput(BaseModel):
    """Input schema for starting an investigation.
    
    Used by the API and LangGraph Studio to validate investigation requests.
    """

    alert: dict = Field(
        default={
            "name": "HighErrorRate",
            "service": "payment-service",
            "severity": "critical",
            "timestamp": "2024-01-15T10:00:00Z",
            "description": "Payment service error rate above 5% for 10 minutes",
        },
        description="Alert JSON payload to investigate"
    )
    thread_id: str = Field(
        default="investigation-1",
        description="Session ID for tracking and state persistence"
    )
    images: list[dict] = Field(
        default_factory=list,
        description="Optional images (screenshots, graphs) attached to alert"
    )

    class Config:
        extra = "forbid"
