"""
AutoSRE Orchestrator — Main investigation flow controller.

Replaces LangGraph with plain async Python.
Manages the investigation lifecycle:
    init → memory_lookup → topology → planner → subagents → synthesizer → loop/writeup
"""

import asyncio
import logging
import time
from typing import Any, Optional

from .agents import (
    InvestigationState,
    InvestigationStatus,
    InvestigationReport,
    SynthesisDecision,
)
from .agents.planner import run_planner, apply_plan_to_state
from .agents.synthesizer import run_synthesizer, apply_synthesis_to_state
from .agents.writeup import run_writeup
from .agents.subagents import get_subagent, list_subagents
from .config import Settings, get_settings
from .llm import BaseLLMClient, get_llm_client
from .memory import EpisodicMemory, Episode
from .memory.strategy import get_or_generate_strategy, enhance_prompt_with_memory
from .topology import ServiceTopology, get_topology

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main investigation orchestrator.
    
    Coordinates the investigation flow:
    1. Initialize context (extract service, alert type)
    2. Lookup similar past investigations from memory
    3. Load service topology for blast radius awareness
    4. Run planner to generate hypotheses
    5. Dispatch subagents in parallel
    6. Synthesize findings and decide whether to loop
    7. Generate final report
    8. Store episode in memory
    
    Example:
        >>> orchestrator = Orchestrator()
        >>> report = await orchestrator.investigate("payment-service 500 errors")
        >>> print(report.root_cause)
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[BaseLLMClient] = None,
        memory: Optional[EpisodicMemory] = None,
        topology: Optional[ServiceTopology] = None,
    ):
        self.settings = settings or get_settings()
        self._llm_client = llm_client
        self._memory = memory
        self._topology = topology
    
    @property
    def llm_client(self) -> BaseLLMClient:
        """Get LLM client (lazy initialized)."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client
    
    @property
    def memory(self) -> EpisodicMemory:
        """Get episodic memory (lazy initialized)."""
        if self._memory is None:
            self._memory = EpisodicMemory(self.settings.memory.db_path)
        return self._memory
    
    @property
    def topology(self) -> ServiceTopology:
        """Get service topology (lazy initialized)."""
        if self._topology is None:
            self._topology = get_topology()
        return self._topology
    
    async def investigate(
        self,
        alert: dict[str, Any] | str,
        thread_id: str = "",
        max_iterations: Optional[int] = None,
    ) -> InvestigationReport:
        """Run a full investigation.
        
        Args:
            alert: Alert dict or description string.
            thread_id: Optional tracking ID.
            max_iterations: Override max investigation iterations.
            
        Returns:
            Final investigation report.
        """
        start_time = time.time()
        
        # Normalize alert input
        if isinstance(alert, str):
            alert = {"name": alert, "description": alert}
        
        # Initialize state
        state = InvestigationState(
            alert=alert,
            thread_id=thread_id or f"inv-{int(time.time())}",
            max_iterations=max_iterations or self.settings.investigation.max_iterations,
            max_subagent_loops=self.settings.investigation.max_subagent_loops,
        )
        
        logger.info(f"[ORCHESTRATOR] Starting investigation: {alert.get('name', 'unknown')}")
        
        try:
            # Phase 1: Initialize context
            await self._init_context(state)
            
            # Phase 2: Memory lookup
            await self._memory_lookup(state)
            
            # Phase 3: Topology context
            await self._topology_context(state)
            
            # Phase 4-6: Investigation loop
            state.status = InvestigationStatus.RUNNING
            
            while state.status == InvestigationStatus.RUNNING:
                # Run planner
                plan = await run_planner(
                    state=state,
                    available_agents=list_subagents(),
                    llm_client=self.llm_client,
                )
                apply_plan_to_state(state, plan)
                
                # Run subagents (parallel if enabled)
                await self._run_subagents(state)
                
                # Run synthesizer
                force_conclude = state.iteration >= state.max_iterations - 1
                decision = await run_synthesizer(
                    state=state,
                    llm_client=self.llm_client,
                    force_conclude=force_conclude,
                )
                apply_synthesis_to_state(state, decision)
            
            # Phase 7: Generate report
            report = await run_writeup(
                state=state,
                llm_client=self.llm_client,
            )
            state.report = report
            
            # Phase 8: Store episode
            await self._store_episode(state, report)
            
            duration = time.time() - start_time
            logger.info(
                f"[ORCHESTRATOR] Investigation complete in {duration:.1f}s: "
                f"{report.root_cause or 'no root cause determined'}"
            )
            
            return report
            
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Investigation failed: {e}")
            state.status = InvestigationStatus.FAILED
            state.error = str(e)
            
            # Return partial report
            return InvestigationReport(
                id=state.investigation_id,
                created_at=state.created_at,
                alert=state.alert,
                service_name=state.service_name,
                status=InvestigationStatus.FAILED,
                summary=f"Investigation failed: {e}",
                iterations=state.iteration,
                duration_seconds=time.time() - start_time,
            )
    
    async def _init_context(self, state: InvestigationState) -> None:
        """Extract service name and alert type from alert."""
        alert = state.alert
        
        # Extract service name
        state.service_name = (
            alert.get("service") or
            alert.get("service_name") or
            alert.get("labels", {}).get("service") or
            ""
        )
        
        # Extract alert type
        state.alert_type = (
            alert.get("alertname") or
            alert.get("alert_type") or
            alert.get("name") or
            self._classify_alert(alert)
        )
        
        logger.debug(
            f"[ORCHESTRATOR] Context: service={state.service_name}, "
            f"alert_type={state.alert_type}"
        )
    
    def _classify_alert(self, alert: dict) -> str:
        """Simple alert classification from description."""
        desc = str(alert.get("description", "")).lower()
        name = str(alert.get("name", "")).lower()
        combined = f"{name} {desc}"
        
        classifications = [
            ("503", "http_503"),
            ("500", "http_500"),
            ("5xx", "http_5xx"),
            ("timeout", "timeout"),
            ("oom", "out_of_memory"),
            ("memory", "memory_issue"),
            ("cpu", "cpu_issue"),
            ("latency", "high_latency"),
            ("error", "error"),
            ("crash", "crash"),
            ("down", "service_down"),
        ]
        
        for keyword, alert_type in classifications:
            if keyword in combined:
                return alert_type
        
        return "unknown"
    
    async def _memory_lookup(self, state: InvestigationState) -> None:
        """Look up similar past investigations."""
        try:
            similar = self.memory.search_similar(
                alert_type=state.alert_type,
                service_name=state.service_name,
                limit=self.settings.memory.max_episodes,
            )
            
            if similar:
                # Try to get/generate strategy
                strategy = await get_or_generate_strategy(
                    memory=self.memory,
                    alert_type=state.alert_type,
                    service_name=state.service_name,
                    llm_client=self.llm_client,
                )
                
                state.memory_context = {
                    "has_similar_episodes": True,
                    "episode_count": len(similar),
                    "episodes": [
                        {
                            "id": ep.id,
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
                        strategy=strategy,
                        similar_episodes=similar,
                    ),
                }
                
                logger.debug(f"[ORCHESTRATOR] Found {len(similar)} similar episodes")
            else:
                state.memory_context = {"has_similar_episodes": False}
                
        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Memory lookup failed: {e}")
            state.memory_context = {"has_similar_episodes": False, "error": str(e)}
    
    async def _topology_context(self, state: InvestigationState) -> None:
        """Load service topology context."""
        if not state.service_name:
            state.topology_context = {"available": False}
            return
        
        try:
            ctx = self.topology.to_context(state.service_name)
            state.topology_context = ctx
            
            if ctx.get("available"):
                logger.debug(
                    f"[ORCHESTRATOR] Topology: {len(ctx.get('dependencies', []))} deps, "
                    f"{ctx.get('blast_radius_size', 0)} blast radius"
                )
        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Topology lookup failed: {e}")
            state.topology_context = {"available": False, "error": str(e)}
    
    async def _run_subagents(self, state: InvestigationState) -> None:
        """Run selected subagents in parallel."""
        if not state.selected_agents:
            logger.warning("[ORCHESTRATOR] No agents selected, skipping subagent phase")
            return
        
        # Prepare hypotheses for subagents
        hypotheses = [h.hypothesis for h in state.hypotheses]
        
        # Prepare service context
        service_context = self.topology.format_for_prompt(state.service_name) if state.service_name else ""
        
        if self.settings.investigation.parallel_subagents:
            # Run in parallel
            tasks = []
            for agent_id in state.selected_agents:
                task = self._run_single_subagent(
                    agent_id=agent_id,
                    alert=state.alert,
                    hypotheses=hypotheses,
                    service_context=service_context,
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"[ORCHESTRATOR] Subagent error: {result}")
                else:
                    state.add_agent_result(result)
        else:
            # Run sequentially
            for agent_id in state.selected_agents:
                result = await self._run_single_subagent(
                    agent_id=agent_id,
                    alert=state.alert,
                    hypotheses=hypotheses,
                    service_context=service_context,
                )
                state.add_agent_result(result)
    
    async def _run_single_subagent(
        self,
        agent_id: str,
        alert: dict,
        hypotheses: list[str],
        service_context: str,
    ):
        """Run a single subagent."""
        from .agents.subagents import SubagentResult
        
        try:
            subagent = get_subagent(agent_id)
            result = await subagent.investigate(
                alert=alert,
                hypotheses=hypotheses,
                service_context=service_context,
                llm_client=self.llm_client,
            )
            return result
        except ValueError as e:
            logger.warning(f"[ORCHESTRATOR] Unknown subagent {agent_id}: {e}")
            from .agents.state import SubagentResult, InvestigationStatus
            return SubagentResult(
                agent_id=agent_id,
                status=InvestigationStatus.FAILED,
                findings=f"Unknown subagent: {agent_id}",
                error=str(e),
            )
    
    async def _store_episode(
        self,
        state: InvestigationState,
        report: InvestigationReport,
    ) -> None:
        """Store investigation as episode in memory."""
        try:
            episode = Episode(
                alert_type=state.alert_type,
                alert_description=str(state.alert.get("description", "")),
                severity=state.alert.get("severity", "info"),
                service_name=state.service_name,
                services=[state.service_name] if state.service_name else [],
                resolved=report.root_cause is not None,
                root_cause=report.root_cause,
                summary=report.summary,
                skills_used=report.skills_used,
                duration_seconds=report.duration_seconds,
                effectiveness_score=report.confidence,
            )
            
            self.memory.store(episode)
            logger.debug(f"[ORCHESTRATOR] Stored episode: {episode.id}")
            
        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Failed to store episode: {e}")


# Convenience function
async def investigate(
    alert: dict[str, Any] | str,
    **kwargs,
) -> InvestigationReport:
    """Run an investigation using default orchestrator.
    
    Args:
        alert: Alert dict or description string.
        **kwargs: Passed to Orchestrator.investigate().
        
    Returns:
        Investigation report.
    """
    orchestrator = Orchestrator()
    return await orchestrator.investigate(alert, **kwargs)
