"""
LangGraph Investigation Graph Builder

Builds the investigation workflow graph with SRE-style phases:
TRIAGE → MITIGATE → INVESTIGATE → REMEDIATE → VERIFY → DOCUMENT

This module provides a graph that can be executed by LangGraph.
"""
from typing import Any, Dict, Optional
import logging

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None

from . import (
    GraphState,
    triage_node,
    changes_correlation_node,
    slo_context_node,
    golden_signals_node,
    investigate_node,
    synthesize_node,
    error_budget_check_node,
    should_mitigate,
    confidence_check,
)
from ..state import InvestigationPhase

logger = logging.getLogger(__name__)


def build_investigation_graph():
    """Build the LangGraph investigation workflow.
    
    Graph structure:
    
    START
      │
      ▼
    slo_context ─────────────────────────────────────┐
      │                                               │
      ▼                                               │
    triage                                            │
      │                                               │
      ├──[immediate_action]──▶ mitigate               │
      │                          │                    │
      │◀─────────────────────────┘                    │
      ▼                                               │
    changes_correlation                               │
      │                                               │
      ▼                                               │
    golden_signals                                    │
      │                                               │
      ▼                                               │
    investigate ◀──────────────────────────┐          │
      │                                    │          │
      ├──[iterate]─────────────────────────┘          │
      │                                               │
      ▼                                               │
    error_budget_check                                │
      │                                               │
      ├──[budget_critical]──▶ BLOCKED                 │
      │                                               │
      ▼                                               │
    synthesize                                        │
      │                                               │
      ├──[low_confidence]──▶ investigate (retry)      │
      │                                               │
      ▼                                               │
    END                                               │
    
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "LangGraph is not installed. Install with: pip install langgraph"
        )
    
    # Create the graph
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("slo_context", slo_context_node)
    graph.add_node("triage", triage_node)
    graph.add_node("mitigate", _mitigate_node)
    graph.add_node("changes_correlation", changes_correlation_node)
    graph.add_node("golden_signals", golden_signals_node)
    graph.add_node("investigate", investigate_node)
    graph.add_node("error_budget_check", error_budget_check_node)
    graph.add_node("synthesize", synthesize_node)
    
    # Set entry point
    graph.set_entry_point("slo_context")
    
    # Add edges
    
    # slo_context -> triage
    graph.add_edge("slo_context", "triage")
    
    # triage -> conditional (mitigate or changes_correlation)
    graph.add_conditional_edges(
        "triage",
        should_mitigate,
        {
            "mitigate": "mitigate",
            "skip_mitigate": "changes_correlation",
        }
    )
    
    # mitigate -> changes_correlation
    graph.add_edge("mitigate", "changes_correlation")
    
    # changes_correlation -> golden_signals
    graph.add_edge("changes_correlation", "golden_signals")
    
    # golden_signals -> investigate
    graph.add_edge("golden_signals", "investigate")
    
    # investigate -> error_budget_check
    graph.add_edge("investigate", "error_budget_check")
    
    # error_budget_check -> conditional
    graph.add_conditional_edges(
        "error_budget_check",
        _error_budget_router,
        {
            "allowed": "synthesize",
            "blocked": END,
        }
    )
    
    # synthesize -> conditional (end or iterate)
    graph.add_conditional_edges(
        "synthesize",
        confidence_check,
        {
            "high_confidence": END,
            "low_confidence": END,
            "iterate": "investigate",
        }
    )
    
    return graph.compile()


async def _mitigate_node(state: GraphState) -> GraphState:
    """Placeholder mitigation node.
    
    In production, this would execute mitigation playbooks.
    """
    logger.info(f"[{state['investigation_id']}] Running mitigation")
    
    # Placeholder - would execute actual mitigation
    return {
        **state,
        "phase": InvestigationPhase.MITIGATE.value,
    }


def _error_budget_router(state: GraphState) -> str:
    """Route based on error budget status."""
    if state.get("error_budget_allows_action", True):
        return "allowed"
    return "blocked"


def create_initial_state(
    investigation_id: str,
    alert: Dict[str, Any],
    memory_context: Optional[Dict[str, Any]] = None,
    topology_context: Optional[Dict[str, Any]] = None,
) -> GraphState:
    """Create the initial state for the investigation graph.
    
    Args:
        investigation_id: Unique ID for this investigation
        alert: Alert data dict with name, service, severity, etc.
        memory_context: Optional memory context from past incidents
        topology_context: Optional service topology context
        
    Returns:
        Initial GraphState ready for graph execution
    """
    return GraphState(
        investigation_id=investigation_id,
        alert=alert,
        phase=InvestigationPhase.TRIAGE.value,
        phase_complete=False,
        phase_blockers=[],
        slo_context=None,
        memory_context=memory_context or {},
        topology_context=topology_context or {},
        triage_result=None,
        golden_signals=None,
        changes_correlated=[],
        likely_change_cause=None,
        hypotheses=[],
        evidence=[],
        agent_results={},
        root_cause=None,
        confidence=0.0,
        conclusion="",
        ai_decisions=[],
        ai_confidence=0.0,
        error_budget_impact=0.0,
        error_budget_allows_action=True,
        iteration=0,
        max_iterations=5,
        status="running",
    )


class InvestigationGraphRunner:
    """Runner for the investigation graph.
    
    Provides a higher-level interface for executing investigations.
    """
    
    def __init__(self):
        self.graph = None
        if LANGGRAPH_AVAILABLE:
            self.graph = build_investigation_graph()
    
    async def run(
        self,
        investigation_id: str,
        alert: Dict[str, Any],
        memory_context: Optional[Dict[str, Any]] = None,
        topology_context: Optional[Dict[str, Any]] = None,
    ) -> GraphState:
        """Run a full investigation.
        
        Args:
            investigation_id: Unique ID for this investigation
            alert: Alert data
            memory_context: Optional memory context
            topology_context: Optional topology context
            
        Returns:
            Final investigation state
        """
        if not self.graph:
            raise RuntimeError("LangGraph not available")
        
        # Create initial state
        state = create_initial_state(
            investigation_id=investigation_id,
            alert=alert,
            memory_context=memory_context,
            topology_context=topology_context,
        )
        
        # Run the graph
        final_state = await self.graph.ainvoke(state)
        
        return final_state
    
    async def run_streaming(
        self,
        investigation_id: str,
        alert: Dict[str, Any],
        memory_context: Optional[Dict[str, Any]] = None,
        topology_context: Optional[Dict[str, Any]] = None,
    ):
        """Run investigation with streaming output.
        
        Yields state updates as the graph executes.
        """
        if not self.graph:
            raise RuntimeError("LangGraph not available")
        
        state = create_initial_state(
            investigation_id=investigation_id,
            alert=alert,
            memory_context=memory_context,
            topology_context=topology_context,
        )
        
        async for event in self.graph.astream(state):
            yield event
