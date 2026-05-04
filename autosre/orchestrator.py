"""
Orchestrator — Main investigation flow coordinator.

Implements the investigation loop:
1. init_context — Parse alert, load topology
2. memory_lookup — Find similar past incidents
3. planner — Generate hypotheses, select subagents
4. subagents — Execute in parallel
5. synthesizer — Combine evidence, decide loop/done
6. writeup — Generate final report
7. memory_store — Save episode for future

This replaces LangGraph with plain async Python for simplicity.
"""

import asyncio
import logging
import time
from typing import Any, Optional

from .agents.planner import apply_plan_to_state, run_planner
from .agents.state import (
    Evidence,
    InvestigationReport,
    InvestigationState,
    InvestigationStatus,
)
from .agents.subagents import (
    BaseSubagent,
    KubernetesSubagent,
    LogsSubagent,
    MetricsSubagent,
    run_subagents_parallel,
)
from .agents.synthesizer import apply_synthesis_to_state, run_synthesizer
from .agents.writeup import run_writeup
from .config import Settings, get_settings
from .llm import BaseLLMClient, get_llm_client
from .memory import EpisodicMemory, Episode, enhance_prompt_with_memory
from .topology import ServiceTopology, get_topology, load_topology

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main investigation orchestrator.
    
    Coordinates the full investigation flow from alert to report.
    
    Example:
        >>> orch = Orchestrator()
        >>> result = await orch.investigate({
        ...     "name": "High5xxRate",
        ...     "service": "checkout-service",
        ...     "description": "5xx rate above 5% for 10 minutes"
        ... })
        >>> print(result.root_cause)
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[BaseLLMClient] = None,
        memory: Optional[EpisodicMemory] = None,
        topology: Optional[ServiceTopology] = None,
    ):
        self.settings = settings or get_settings()
        self.llm_client = llm_client
        self.memory = memory or EpisodicMemory(db_path=self.settings.memory.db_path)
        self.topology = topology
        
        # Available subagents
        self._subagents: dict[str, BaseSubagent] = {}
        self._init_subagents()
    
    def _init_subagents(self) -> None:
        """Initialize available subagents."""
        self._subagents = {
            "kubernetes": KubernetesSubagent(llm_client=self.llm_client),
            "metrics": MetricsSubagent(llm_client=self.llm_client),
            "logs": LogsSubagent(llm_client=self.llm_client),
        }
    
    def _get_topology(self) -> ServiceTopology:
        """Get topology, loading from config if needed."""
        if self.topology:
            return self.topology
        
        if self.settings.topology_path.exists():
            return load_topology(self.settings.topology_path)
        
        return get_topology()
    
    async def investigate(
        self,
        alert: dict[str, Any],
        thread_id: str = "",
        images: Optional[list[dict[str, Any]]] = None,
    ) -> InvestigationReport:
        """Run full investigation on an alert.
        
        Args:
            alert: Alert dictionary with name, service, description, etc.
            thread_id: Optional thread ID for tracking.
            images: Optional images/screenshots related to the alert.
            
        Returns:
            InvestigationReport with findings and root cause.
        """
        start_time = time.time()
        
        # Initialize state
        state = InvestigationState(
            alert=alert,
            thread_id=thread_id,
            images=images or [],
            max_iterations=self.settings.investigation.max_iterations,
            max_subagent_loops=self.settings.investigation.max_subagent_loops,
        )
        
        state.status = InvestigationStatus.RUNNING
        
        try:
            # Step 1: Init context
            await self._init_context(state)
            
            # Step 2: Memory lookup
            await self._memory_lookup(state)
            
            # Steps 3-5: Investigation loop
            while state.iteration < state.max_iterations:
                # Step 3: Plan
                plan = await run_planner(
                    state=state,
                    available_agents=list(self._subagents.keys()),
                    llm_client=self.llm_client,
                )
                apply_plan_to_state(state, plan)
                
                # Step 4: Execute subagents
                await self._run_subagents(state)
                
                # Step 5: Synthesize
                decision = await run_synthesizer(
                    state=state,
                    llm_client=self.llm_client,
                )
                apply_synthesis_to_state(state, decision)
                
                if state.status == InvestigationStatus.COMPLETED:
                    break
            
            # Step 6: Generate report
            report = await run_writeup(
                state=state,
                llm_client=self.llm_client,
            )
            state.report = report
            
            # Step 7: Store in memory
            await self._memory_store(state, time.time() - start_time)
            
            return report
            
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Investigation failed: {e}")
            state.status = InvestigationStatus.FAILED
            state.error = str(e)
            
            # Return partial report
            return state.finalize_report()
    
    async def _init_context(self, state: InvestigationState) -> None:
        """Initialize investigation context from alert."""
        logger.info(f"[ORCHESTRATOR] Initializing context for alert: {state.alert.get('name', 'unknown')}")
        
        # Extract service name
        service_name = (
            state.alert.get("service") or
            state.alert.get("service_name") or
            state.alert.get("labels", {}).get("service") or
            ""
        )
        state.service_name = service_name
        
        # Extract alert type
        alert_type = (
            state.alert.get("alert_type") or
            state.alert.get("alertname") or
            state.alert.get("name") or
            "unknown"
        )
        state.alert_type = self._normalize_alert_type(alert_type)
        
        # Load topology context
        topology = self._get_topology()
        
        if service_name and service_name in topology:
            state.topology_context = topology.to_context(service_name)
        elif service_name:
            # Try to find service from alert mapping
            mapped_service = topology.get_service_for_alert(state.alert_type)
            if mapped_service:
                state.service_name = mapped_service
                state.topology_context = topology.to_context(mapped_service)
            else:
                state.topology_context = {"available": False}
        else:
            state.topology_context = {"available": False}
        
        state.add_message("init", f"Investigating {state.alert_type} for {state.service_name or 'unknown service'}")
    
    async def _memory_lookup(self, state: InvestigationState) -> None:
        """Look up similar past investigations."""
        logger.info(f"[ORCHESTRATOR] Looking up similar incidents...")
        
        similar = self.memory.search_similar(
            alert_type=state.alert_type,
            service_name=state.service_name,
            limit=3,
        )
        
        if similar:
            state.memory_context = {
                "has_similar_episodes": True,
                "episode_count": len(similar),
                "similar_episodes": [
                    {
                        "alert_type": ep.alert_type,
                        "service_name": ep.service_name,
                        "root_cause": ep.root_cause,
                        "resolved": ep.resolved,
                    }
                    for ep in similar
                ],
                "enhanced_prompt": enhance_prompt_with_memory(
                    prompt="",
                    memory=self.memory,
                    service_name=state.service_name,
                    alert_type=state.alert_type,
                    similar_episodes=similar,
                ),
            }
            logger.info(f"[ORCHESTRATOR] Found {len(similar)} similar past incidents")
        else:
            state.memory_context = {"has_similar_episodes": False}
            logger.info("[ORCHESTRATOR] No similar past incidents found")
    
    async def _run_subagents(self, state: InvestigationState) -> None:
        """Run selected subagents in parallel."""
        selected = state.selected_agents
        
        if not selected:
            logger.warning("[ORCHESTRATOR] No subagents selected")
            return
        
        logger.info(f"[ORCHESTRATOR] Running subagents: {selected}")
        
        # Get subagent instances
        subagents = [
            self._subagents[name]
            for name in selected
            if name in self._subagents
        ]
        
        if not subagents:
            logger.warning(f"[ORCHESTRATOR] No valid subagents found for: {selected}")
            return
        
        # Run in parallel
        if self.settings.investigation.parallel_subagents:
            results = await run_subagents_parallel(
                state=state,
                subagents=subagents,
                hypotheses=state.hypotheses,
            )
        else:
            # Sequential fallback
            results = []
            for subagent in subagents:
                result = await subagent.run(state, state.hypotheses)
                results.append(result)
        
        # Add results to state
        for result in results:
            state.add_agent_result(result)
            logger.info(
                f"[ORCHESTRATOR] {result.agent_id}: "
                f"{len(result.evidence)} evidence items, "
                f"{result.duration_seconds:.1f}s"
            )
    
    async def _memory_store(self, state: InvestigationState, duration: float) -> None:
        """Store completed investigation in memory."""
        if not state.report:
            return
        
        episode = Episode(
            alert_type=state.alert_type,
            alert_description=state.alert.get("description", "")[:500],
            severity=state.alert.get("severity", "info"),
            service_name=state.service_name,
            services=[state.service_name] if state.service_name else [],
            resolved=state.status == InvestigationStatus.COMPLETED,
            root_cause=state.report.root_cause,
            summary=state.report.summary,
            skills_used=state.get_all_skills_used(),
            key_findings=[
                {"skill": ev.skill, "finding": ev.summary or ev.result[:200]}
                for ev in state.all_evidence[:10]
            ],
            duration_seconds=duration,
            effectiveness_score=state.synthesis.confidence if state.synthesis else 0.5,
        )
        
        self.memory.store(episode)
        logger.info(f"[ORCHESTRATOR] Stored episode: {episode.id}")
    
    def _normalize_alert_type(self, alert_type: str) -> str:
        """Normalize alert type to standard format."""
        # Convert to lowercase, replace spaces with underscores
        normalized = alert_type.lower().replace(" ", "_").replace("-", "_")
        
        # Map common variations
        mappings = {
            "high5xxrate": "http_500",
            "5xx": "http_500",
            "500error": "http_500",
            "highlatency": "high_latency",
            "latencyp99": "high_latency",
            "oomkilled": "out_of_memory",
            "outofmemory": "out_of_memory",
            "highcpu": "cpu_issue",
            "cpuspike": "cpu_issue",
        }
        
        return mappings.get(normalized.replace("_", ""), normalized)


# Convenience function
async def investigate(
    alert: dict[str, Any],
    **kwargs: Any,
) -> InvestigationReport:
    """Quick investigation without explicitly creating an orchestrator.
    
    Args:
        alert: Alert dictionary.
        **kwargs: Passed to Orchestrator constructor.
        
    Returns:
        InvestigationReport.
    """
    orch = Orchestrator(**kwargs)
    return await orch.investigate(alert)
