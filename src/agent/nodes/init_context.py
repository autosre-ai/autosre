"""
Init Context Node

Entry point for the investigation graph. Validates the alert payload,
generates an investigation ID, and loads team configuration.
"""

from __future__ import annotations

import logging
import os
import uuid

from ..config import load_team_config, get_investigation_limits

logger = logging.getLogger(__name__)


def init_context(state: dict) -> dict:
    """Initialize investigation context.
    
    This is the entry node of the graph. It:
    1. Validates the alert payload
    2. Generates a unique investigation ID
    3. Loads team configuration
    4. Sets up iteration limits
    
    Args:
        state: Input state with 'alert', 'thread_id', optional 'images'
        
    Returns:
        State update with investigation metadata and defaults
    """
    alert = state.get("alert", {})
    thread_id = state.get("thread_id", str(uuid.uuid4()))
    images = state.get("images", [])
    
    # Validate alert
    if not alert:
        logger.error("[INIT] No alert data provided")
        return {
            "status": "error",
            "conclusion": "No alert data provided. Cannot start investigation.",
            "investigation_id": str(uuid.uuid4()),
        }
    
    # Load team configuration
    try:
        team_config = load_team_config()
        raw_config = team_config.raw_config
    except Exception as e:
        logger.warning(f"[INIT] Failed to load team config: {e}. Using defaults.")
        raw_config = {}
    
    # Get investigation limits
    limits = get_investigation_limits()
    
    # Check for planner-specific overrides in config
    planner_config = raw_config.get("agents", {}).get("planner", {})
    max_iterations = int(
        os.getenv("MAX_ITERATIONS", planner_config.get("max_iterations", limits["max_iterations"]))
    )
    max_react_loops = int(
        os.getenv("SUBAGENT_MAX_REACT_LOOPS", str(limits["max_react_loops"]))
    )
    
    investigation_id = str(uuid.uuid4())
    
    logger.info(
        f"[INIT] Starting investigation {investigation_id[:8]} for alert: "
        f"{alert.get('name', 'unknown')} on {alert.get('service', 'unknown')}"
    )
    logger.info(f"[INIT] Config: max_iterations={max_iterations}, max_react_loops={max_react_loops}")
    
    return {
        # Investigation metadata
        "investigation_id": investigation_id,
        "thread_id": thread_id,
        "images": images,
        
        # Team configuration
        "team_config": raw_config,
        
        # Investigation limits
        "max_iterations": max_iterations,
        "max_react_loops": max_react_loops,
        
        # State initialization
        "iteration": 0,
        "status": "running",
        "agent_states": {},
        "messages": [],
        "hypotheses": [],
        "selected_agents": [],
        
        # Placeholders for context nodes
        "memory_context": {},
        "kg_context": {},
    }
