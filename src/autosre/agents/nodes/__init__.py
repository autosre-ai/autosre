"""
Investigation phase nodes for the AutoSRE workflow graph.

These nodes represent discrete phases in the investigation lifecycle.
"""

from .triage import (
    TriageNode,
    TriageResult,
    TriageStatus,
    MitigationOption,
    ImpactAssessment,
    ImpactSeverity,
    create_triage_node,
    block_investigation_without_triage,
)

# Import graph components if LangGraph is available
try:
    from .graph import (
        GraphState,
        build_investigation_graph,
        create_initial_state,
        InvestigationGraphRunner,
        triage_node,
        changes_correlation_node,
        slo_context_node,
        golden_signals_node,
        investigate_node,
        synthesize_node,
        error_budget_check_node,
        phase_router,
        should_mitigate,
        confidence_check,
    )
    _GRAPH_AVAILABLE = True
except ImportError:
    _GRAPH_AVAILABLE = False
    GraphState = None
    build_investigation_graph = None
    create_initial_state = None
    InvestigationGraphRunner = None
    triage_node = None
    changes_correlation_node = None
    slo_context_node = None
    golden_signals_node = None
    investigate_node = None
    synthesize_node = None
    error_budget_check_node = None
    phase_router = None
    should_mitigate = None
    confidence_check = None

__all__ = [
    # Triage Node (core)
    "TriageNode",
    "TriageResult",
    "TriageStatus",
    "MitigationOption",
    "ImpactAssessment",
    "ImpactSeverity",
    "create_triage_node",
    "block_investigation_without_triage",
    # Graph components (optional, requires LangGraph)
    "GraphState",
    "build_investigation_graph",
    "create_initial_state",
    "InvestigationGraphRunner",
    "triage_node",
    "changes_correlation_node",
    "slo_context_node",
    "golden_signals_node",
    "investigate_node",
    "synthesize_node",
    "error_budget_check_node",
    "phase_router",
    "should_mitigate",
    "confidence_check",
]
