"""Agent Coordinator.

Orchestrates the multi-agent investigation workflow with:
- State machine-based lifecycle management
- Event emission for real-time UI updates
- Retry handling with exponential backoff
- Timeout management with warnings
- State persistence for recovery

The Coordinator is the brain of the investigation system, deciding
when to dispatch agents, when to synthesize findings, and when to
conclude or escalate.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.agents.base import (
    AgentCapability,
    AgentConfig,
    BaseAgent,
    ExecutionContext,
    ExecutionResult,
    LLMClient,
)
from autosre.agents.prompts import (
    COORDINATOR_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
)
from autosre.agents.state import (
    EventEmitter,
    EventType,
    Event,
    InvestigationState,
    InvestigationStateMachine,
    InvestigationContext,
    RetryConfig,
    RetryManager,
    TimeoutConfig,
    TimeoutManager,
    StatePersister,
    create_persister,
    TransitionError,
)
from autosre.agents.triage import TriageAgent, TriageResult
from autosre.agents.investigator import InvestigationAgent, InvestigationOutput
from autosre.agents.remediation import RemediationAgent, RemediationOutput
from autosre.core.investigation import (
    Investigation,
    Finding,
    Hypothesis,
    InvestigationResult,
)


logger = logging.getLogger(__name__)


# =============================================================================
# Coordinator Configuration
# =============================================================================


class CoordinatorConfig(BaseModel):
    """Configuration for the AgentCoordinator."""
    
    # Investigation limits
    max_iterations: int = Field(default=3, ge=1, le=10)
    max_agents_parallel: int = Field(default=5, ge=1, le=20)
    
    # Timeouts
    total_timeout_seconds: float = Field(default=600.0)
    triage_timeout_seconds: float = Field(default=30.0)
    investigation_timeout_seconds: float = Field(default=300.0)
    analysis_timeout_seconds: float = Field(default=60.0)
    remediation_timeout_seconds: float = Field(default=60.0)
    
    # Retry settings
    max_retries: int = Field(default=3)
    retry_delay: float = Field(default=1.0)
    
    # Persistence
    persistence_backend: str = Field(default="memory")  # memory, file, sqlite
    persistence_path: Optional[str] = None
    
    # Auto-save interval (seconds)
    auto_save_interval: float = Field(default=10.0)
    
    # Synthesis
    synthesis_threshold: float = Field(default=0.7)  # Min confidence for conclusion
    
    def get_timeout_config(self) -> TimeoutConfig:
        """Convert to TimeoutConfig."""
        return TimeoutConfig(
            total_timeout=self.total_timeout_seconds,
            triage_timeout=self.triage_timeout_seconds,
            investigation_timeout=self.investigation_timeout_seconds,
            analysis_timeout=self.analysis_timeout_seconds,
            remediation_timeout=self.remediation_timeout_seconds,
        )
    
    def get_retry_config(self) -> RetryConfig:
        """Convert to RetryConfig."""
        return RetryConfig(
            max_retries=self.max_retries,
            initial_delay=self.retry_delay,
        )


# =============================================================================
# Coordinator State
# =============================================================================


@dataclass
class CoordinatorState:
    """Runtime state for the coordinator.
    
    Tracks the current investigation progress, agent states,
    and accumulated results.
    """
    
    investigation_id: str
    context: InvestigationContext
    
    # Alert and triage
    alert: dict[str, Any] = field(default_factory=dict)
    triage_result: Optional[TriageResult] = None
    
    # Hypotheses
    hypotheses: list[Hypothesis] = field(default_factory=list)
    
    # Agent results
    agent_results: dict[str, ExecutionResult] = field(default_factory=dict)
    
    # Accumulated findings
    all_findings: list[Finding] = field(default_factory=list)
    
    # Synthesis
    synthesis_result: Optional[dict[str, Any]] = None
    
    # Remediation
    remediation_output: Optional[RemediationOutput] = None
    
    # Final result
    final_result: Optional[InvestigationResult] = None
    
    # Timeline events
    timeline: list[dict[str, Any]] = field(default_factory=list)
    
    def add_timeline_event(
        self,
        event: str,
        phase: str,
        agent: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Add an event to the timeline."""
        self.timeline.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": phase,
            "event": event,
            "agent": agent,
            "details": details,
        })
    
    def add_findings(self, findings: list[Finding]) -> None:
        """Add findings to the collection."""
        self.all_findings.extend(findings)
    
    def to_persist_dict(self) -> dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "investigation_id": self.investigation_id,
            "context": self.context.to_persist_dict(),
            "alert": self.alert,
            "triage_result": self.triage_result.model_dump() if self.triage_result else None,
            "hypotheses": [h.model_dump() for h in self.hypotheses],
            "all_findings": [f.model_dump() for f in self.all_findings],
            "synthesis_result": self.synthesis_result,
            "remediation_output": self.remediation_output.model_dump() if self.remediation_output else None,
            "final_result": self.final_result.model_dump() if self.final_result else None,
            "timeline": self.timeline,
        }


# =============================================================================
# Investigation Status Response
# =============================================================================


class InvestigationStatus(BaseModel):
    """Status response for investigation queries."""
    
    investigation_id: str
    status: str
    phase: str
    iteration: int
    max_iterations: int
    
    # Timing
    started_at: Optional[datetime] = None
    elapsed_seconds: Optional[float] = None
    
    # Progress
    pending_agents: list[str] = Field(default_factory=list)
    completed_agents: list[str] = Field(default_factory=list)
    failed_agents: list[str] = Field(default_factory=list)
    
    # Findings summary
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    
    # Errors
    error_count: int = 0
    last_error: Optional[str] = None
    
    # Has result
    has_result: bool = False


# =============================================================================
# Timeline
# =============================================================================


class TimelineEntry(BaseModel):
    """A single entry in the investigation timeline."""
    
    timestamp: datetime
    phase: str
    event: str
    agent: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class Timeline(BaseModel):
    """Complete investigation timeline."""
    
    investigation_id: str
    entries: list[TimelineEntry] = Field(default_factory=list)
    
    def add(
        self,
        event: str,
        phase: str,
        agent: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Add an entry to the timeline."""
        self.entries.append(TimelineEntry(
            timestamp=datetime.now(timezone.utc),
            phase=phase,
            event=event,
            agent=agent,
            details=details,
        ))


# =============================================================================
# Agent Coordinator
# =============================================================================


class AgentCoordinator:
    """Orchestrates the multi-agent investigation workflow.
    
    The Coordinator manages the investigation lifecycle:
    1. Receives alerts and initiates triage
    2. Dispatches investigation agents based on triage
    3. Synthesizes findings and decides next steps
    4. Generates remediation recommendations
    5. Produces final investigation report
    
    Features:
    - State machine-based workflow management
    - Event emission for real-time UI updates
    - Retry handling with exponential backoff
    - Timeout management with warnings
    - State persistence for recovery
    
    Example:
        >>> coordinator = AgentCoordinator(llm_client)
        >>> coordinator.register_agent(KubernetesInvestigator())
        >>> 
        >>> # Subscribe to events
        >>> async def on_event(event):
        ...     print(f"Event: {event.type}")
        >>> coordinator.events.on_all(on_event)
        >>> 
        >>> # Run investigation
        >>> result = await coordinator.start_investigation(alert_dict)
    """
    
    # Default agents to dispatch if triage doesn't specify
    DEFAULT_AGENTS = ["kubernetes", "metrics", "logs"]
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        integrations: Optional[dict[str, Any]] = None,
        config: Optional[CoordinatorConfig] = None,
    ):
        """Initialize the AgentCoordinator.
        
        Args:
            llm_client: LLM client for synthesis decisions
            integrations: Integration clients for data collection
            config: Coordinator configuration
        """
        self.config = config or CoordinatorConfig()
        self.llm = llm_client
        self.integrations = integrations or {}
        
        # State machine
        self._state_machine = InvestigationStateMachine()
        
        # Event system
        self.events = EventEmitter()
        
        # Retry and timeout managers
        self._retry_manager = RetryManager(self.config.get_retry_config())
        self._timeout_manager = TimeoutManager(self.config.get_timeout_config())
        
        # State persistence
        self._persister = create_persister(
            backend=self.config.persistence_backend,
            path=Path(self.config.persistence_path) if self.config.persistence_path else None,
        )
        
        # Registered agents
        self._agents: dict[str, BaseAgent] = {}
        self._triage_agent: Optional[TriageAgent] = None
        self._remediation_agent: Optional[RemediationAgent] = None
        
        # Active investigations (in-memory cache)
        self._active: dict[str, CoordinatorState] = {}
        
        # Auto-save task
        self._auto_save_task: Optional[asyncio.Task] = None
    
    # -------------------------------------------------------------------------
    # Agent Registration
    # -------------------------------------------------------------------------
    
    def register_agent(self, agent: BaseAgent) -> None:
        """Register an investigation agent.
        
        Args:
            agent: Agent to register
        """
        self._agents[agent.name] = agent
        
        # Inject LLM if agent needs it
        if self.llm and hasattr(agent, 'llm'):
            agent.llm = self.llm
        
        logger.info(f"[coordinator] Registered agent: {agent.name}")
    
    def register_triage_agent(self, agent: TriageAgent) -> None:
        """Register the triage agent."""
        self._triage_agent = agent
        if self.llm:
            agent.llm = self.llm
        logger.info("[coordinator] Registered triage agent")
    
    def register_remediation_agent(self, agent: RemediationAgent) -> None:
        """Register the remediation agent."""
        self._remediation_agent = agent
        if self.llm:
            agent.llm = self.llm
        logger.info("[coordinator] Registered remediation agent")
    
    def get_available_agents(self) -> list[str]:
        """Get list of available investigation agents."""
        return list(self._agents.keys())
    
    # -------------------------------------------------------------------------
    # Main Investigation Workflow
    # -------------------------------------------------------------------------
    
    async def start_investigation(
        self,
        alert: dict[str, Any],
        investigation_id: Optional[str] = None,
    ) -> Investigation:
        """Start a new investigation for an alert.
        
        This is the main entry point. It orchestrates:
        1. Triage phase
        2. Investigation phase (may iterate)
        3. Analysis/synthesis phase
        4. Remediation recommendation phase
        5. Conclusion generation
        
        Args:
            alert: Alert data to investigate
            investigation_id: Optional ID (generated if not provided)
            
        Returns:
            Completed Investigation object
        """
        inv_id = investigation_id or str(uuid4())
        
        # Initialize context and state
        context = InvestigationContext(
            investigation_id=inv_id,
            max_iterations=self.config.max_iterations,
        )
        
        state = CoordinatorState(
            investigation_id=inv_id,
            context=context,
            alert=alert,
        )
        
        self._active[inv_id] = state
        
        logger.info(f"[coordinator] Starting investigation {inv_id}")
        
        # Start auto-save
        self._start_auto_save(inv_id)
        
        try:
            # Emit start event
            await self.events.emit(
                EventType.STATE_CHANGED,
                inv_id,
                {"from_state": "none", "to_state": "pending"},
            )
            
            # Run the investigation workflow with overall timeout
            investigation = await asyncio.wait_for(
                self._run_investigation_workflow(state),
                timeout=self.config.total_timeout_seconds,
            )
            
            return investigation
            
        except asyncio.TimeoutError:
            logger.error(f"[coordinator] Investigation {inv_id} timed out")
            await self._handle_timeout(state)
            return self._create_failed_investigation(state, "Investigation timed out")
            
        except asyncio.CancelledError:
            logger.warning(f"[coordinator] Investigation {inv_id} cancelled")
            context.status = InvestigationState.CANCELLED
            raise
            
        except Exception as e:
            logger.exception(f"[coordinator] Investigation {inv_id} failed: {e}")
            return await self._handle_investigation_error(state, e)
            
        finally:
            # Cleanup
            self._stop_auto_save()
            await self._save_state(state)
            self._active.pop(inv_id, None)
    
    async def _run_investigation_workflow(
        self,
        state: CoordinatorState,
    ) -> Investigation:
        """Run the complete investigation workflow.
        
        Args:
            state: Coordinator state
            
        Returns:
            Completed investigation
        """
        context = state.context
        inv_id = state.investigation_id
        
        # Mark started
        context.started_at = datetime.now(timezone.utc)
        context.status = InvestigationState.PENDING
        
        state.add_timeline_event("Investigation started", phase="pending")
        
        # Phase 1: Triage
        await self._transition_state(state, "start")
        await self._run_triage_phase(state)
        
        # Phase 2: Investigation (may iterate)
        await self._transition_state(state, "triage_complete")
        await self._run_investigation_phase(state)
        
        # Phase 3: Analysis/Synthesis
        await self._transition_state(state, "observations_collected")
        synthesis_complete = await self._run_analysis_phase(state)
        
        # May need more investigation
        while not synthesis_complete and context.iteration < context.max_iterations:
            context.iteration += 1
            await self._transition_state(state, "need_more_data")
            await self._run_investigation_phase(state)
            await self._transition_state(state, "observations_collected")
            synthesis_complete = await self._run_analysis_phase(state)
        
        # Phase 4: Remediation
        await self._transition_state(state, "analysis_complete")
        await self._run_remediation_phase(state)
        
        # Phase 5: Conclusion
        has_actions = bool(
            state.remediation_output and 
            state.remediation_output.recommended_actions
        )
        
        if has_actions and state.remediation_output.requires_human_approval:
            await self._transition_state(state, "actions_proposed")
            # In a real system, would wait for approval here
            # For now, auto-complete
            await self._transition_state(state, "skip_action")
        else:
            await self._transition_state(state, "no_action_needed")
        
        # Generate final investigation object
        investigation = await self._generate_investigation_result(state)
        
        # Mark complete
        context.completed_at = datetime.now(timezone.utc)
        context.has_result = True
        
        state.add_timeline_event("Investigation completed", phase="completed")
        
        await self.events.emit(
            EventType.COMPLETED,
            inv_id,
            {"duration_seconds": (context.completed_at - context.started_at).total_seconds()},
        )
        
        return investigation
    
    # -------------------------------------------------------------------------
    # State Transitions
    # -------------------------------------------------------------------------
    
    async def _transition_state(
        self,
        state: CoordinatorState,
        event: str,
    ) -> None:
        """Transition to a new state.
        
        Args:
            state: Coordinator state
            event: Event triggering transition
        """
        context = state.context
        old_state = context.status
        
        try:
            new_state = self._state_machine.transition(old_state, event)
        except TransitionError as e:
            logger.error(f"Invalid transition: {e}")
            raise
        
        context.status = new_state
        context.record_phase_transition(
            from_phase=old_state.value,
            to_phase=new_state.value,
            event=event,
        )
        
        state.add_timeline_event(
            f"State changed: {old_state.value} -> {new_state.value}",
            phase=new_state.value,
        )
        
        await self.events.emit(
            EventType.STATE_CHANGED,
            state.investigation_id,
            {
                "from_state": old_state.value,
                "to_state": new_state.value,
                "event": event,
            },
        )
        
        logger.info(
            f"[coordinator] {state.investigation_id}: "
            f"{old_state.value} -> {new_state.value} (event: {event})"
        )
    
    # -------------------------------------------------------------------------
    # Triage Phase
    # -------------------------------------------------------------------------
    
    async def _run_triage_phase(self, state: CoordinatorState) -> None:
        """Run the triage phase.
        
        Args:
            state: Coordinator state
        """
        inv_id = state.investigation_id
        
        state.add_timeline_event("Triage started", phase="triaging")
        await self.events.emit(EventType.TRIAGE_STARTED, inv_id)
        
        # Create triage agent if needed
        if not self._triage_agent:
            self._triage_agent = TriageAgent(llm=self.llm)
        
        # Build execution context
        exec_context = ExecutionContext(
            investigation_id=inv_id,
            alert=state.alert,
        )
        
        # Run with retry and timeout
        async with self._timeout_manager.timeout_context(
            "triage",
            inv_id,
            self.events,
        ):
            async with self._retry_manager.retry_context(
                "triage",
                inv_id,
                on_retry=lambda attempt, e: self._on_retry(inv_id, "triage", attempt, e),
            ):
                result = await self._triage_agent.run(exec_context)
        
        # Process result
        if result.output and isinstance(result.output, TriageResult):
            state.triage_result = result.output
            state.hypotheses = result.output.initial_hypotheses
            state.context.pending_agents = result.output.recommended_agents
            state.add_findings(result.state.findings)
            
            state.add_timeline_event(
                f"Triage complete: {result.output.severity} severity",
                phase="triaging",
                agent="triage",
                recommended_agents=result.output.recommended_agents,
            )
            
            logger.info(
                f"[coordinator] Triage: {result.output.severity}, "
                f"agents: {result.output.recommended_agents}"
            )
        else:
            # Fallback to default agents
            state.context.pending_agents = list(self.DEFAULT_AGENTS)
            state.add_timeline_event(
                "Triage fallback - using default agents",
                phase="triaging",
            )
        
        await self.events.emit(
            EventType.TRIAGE_COMPLETED,
            inv_id,
            {
                "severity": state.triage_result.severity if state.triage_result else "unknown",
                "agents": state.context.pending_agents,
            },
        )
    
    # -------------------------------------------------------------------------
    # Investigation Phase
    # -------------------------------------------------------------------------
    
    async def _run_investigation_phase(self, state: CoordinatorState) -> None:
        """Run the investigation phase.
        
        Dispatches agents in parallel and collects findings.
        
        Args:
            state: Coordinator state
        """
        inv_id = state.investigation_id
        context = state.context
        
        state.add_timeline_event(
            f"Investigation iteration {context.iteration + 1} started",
            phase="investigating",
        )
        
        await self.events.emit(
            EventType.INVESTIGATION_STARTED,
            inv_id,
            {"iteration": context.iteration + 1},
        )
        
        # Get agents to run
        agents_to_run = []
        for agent_name in context.pending_agents:
            if agent_name in self._agents:
                agents_to_run.append(self._agents[agent_name])
            else:
                logger.warning(f"[coordinator] Agent {agent_name} not registered")
        
        if not agents_to_run:
            logger.warning("[coordinator] No agents to dispatch")
            return
        
        logger.info(
            f"[coordinator] Dispatching {len(agents_to_run)} agents: "
            f"{[a.name for a in agents_to_run]}"
        )
        
        # Build context for agents
        exec_context = ExecutionContext(
            investigation_id=inv_id,
            alert=state.alert,
            hypotheses=state.hypotheses,
            previous_findings=state.all_findings,
            iteration=context.iteration,
        )
        
        # Run agents in parallel with timeout
        async with self._timeout_manager.timeout_context(
            "investigation",
            inv_id,
            self.events,
        ):
            await self._dispatch_agents_parallel(
                state,
                agents_to_run,
                exec_context,
            )
        
        # Move to completed
        context.completed_agents.extend(context.pending_agents)
        context.pending_agents = []
        
        await self.events.emit(
            EventType.INVESTIGATION_COMPLETED,
            inv_id,
            {
                "iteration": context.iteration + 1,
                "findings_count": len(state.all_findings),
            },
        )
    
    async def _dispatch_agents_parallel(
        self,
        state: CoordinatorState,
        agents: list[BaseAgent],
        context: ExecutionContext,
    ) -> None:
        """Dispatch agents in parallel.
        
        Args:
            state: Coordinator state
            agents: Agents to run
            context: Execution context
        """
        inv_id = state.investigation_id
        
        # Create tasks with semaphore for limiting parallelism
        semaphore = asyncio.Semaphore(self.config.max_agents_parallel)
        
        async def run_agent(agent: BaseAgent) -> tuple[str, ExecutionResult | Exception]:
            async with semaphore:
                await self.events.emit(
                    EventType.AGENT_STARTED,
                    inv_id,
                    {"agent": agent.name},
                    source=agent.name,
                )
                
                try:
                    async with self._retry_manager.retry_context(
                        f"agent:{agent.name}",
                        inv_id,
                        on_retry=lambda a, e: self._on_retry(inv_id, agent.name, a, e),
                    ):
                        result = await agent.run(context)
                        return agent.name, result
                        
                except Exception as e:
                    return agent.name, e
        
        # Run all agents
        tasks = [run_agent(agent) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                # gather returned an exception (shouldn't happen with our wrapper)
                logger.error(f"[coordinator] Unexpected gather exception: {result}")
                continue
            
            agent_name, agent_result = result
            
            if isinstance(agent_result, Exception):
                # Agent failed
                logger.error(f"[coordinator] Agent {agent_name} failed: {agent_result}")
                state.context.failed_agents.append(agent_name)
                state.context.record_error(str(agent_result), "investigating", recoverable=True)
                
                await self.events.emit(
                    EventType.AGENT_FAILED,
                    inv_id,
                    {"agent": agent_name, "error": str(agent_result)},
                    source=agent_name,
                )
            else:
                # Success
                state.agent_results[agent_name] = agent_result
                state.add_findings(agent_result.state.findings)
                
                state.add_timeline_event(
                    f"Agent completed with {len(agent_result.state.findings)} findings",
                    phase="investigating",
                    agent=agent_name,
                )
                
                await self.events.emit(
                    EventType.AGENT_COMPLETED,
                    inv_id,
                    {
                        "agent": agent_name,
                        "findings_count": len(agent_result.state.findings),
                    },
                    source=agent_name,
                )
    
    # -------------------------------------------------------------------------
    # Analysis Phase
    # -------------------------------------------------------------------------
    
    async def _run_analysis_phase(self, state: CoordinatorState) -> bool:
        """Run the analysis/synthesis phase.
        
        Args:
            state: Coordinator state
            
        Returns:
            True if analysis is sufficient, False if more investigation needed
        """
        inv_id = state.investigation_id
        
        state.add_timeline_event("Analysis started", phase="analyzing")
        await self.events.emit(EventType.ANALYSIS_STARTED, inv_id)
        
        async with self._timeout_manager.timeout_context(
            "analysis",
            inv_id,
            self.events,
        ):
            if self.llm:
                synthesis = await self._llm_synthesis(state)
            else:
                synthesis = self._heuristic_synthesis(state)
        
        state.synthesis_result = synthesis
        
        sufficient = synthesis.get("sufficient_evidence", False)
        confidence = synthesis.get("confidence", 0.0)
        
        state.add_timeline_event(
            f"Analysis complete: {'sufficient' if sufficient else 'insufficient'} evidence",
            phase="analyzing",
            confidence=confidence,
        )
        
        await self.events.emit(
            EventType.ANALYSIS_COMPLETED,
            inv_id,
            {
                "sufficient_evidence": sufficient,
                "confidence": confidence,
            },
        )
        
        # Update hypotheses based on synthesis
        if synthesis.get("root_cause"):
            state.add_timeline_event(
                f"Root cause identified: {synthesis['root_cause']}",
                phase="analyzing",
            )
        
        return sufficient
    
    async def _llm_synthesis(self, state: CoordinatorState) -> dict[str, Any]:
        """Perform LLM-based synthesis.
        
        Args:
            state: Coordinator state
            
        Returns:
            Synthesis result dictionary
        """
        findings_text = self._format_findings_for_synthesis(state)
        
        messages = [
            {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
            {"role": "user", "content": findings_text},
        ]
        
        try:
            response = await self.llm.generate(
                messages=messages,
                temperature=0.1,
            )
            
            return self._parse_synthesis_response(response)
            
        except Exception as e:
            logger.error(f"[coordinator] LLM synthesis failed: {e}")
            return self._heuristic_synthesis(state)
    
    def _heuristic_synthesis(self, state: CoordinatorState) -> dict[str, Any]:
        """Perform heuristic synthesis without LLM.
        
        Args:
            state: Coordinator state
            
        Returns:
            Synthesis result dictionary
        """
        findings = state.all_findings
        
        if not findings:
            return {
                "sufficient_evidence": False,
                "confidence": 0.0,
                "summary": "No findings collected",
                "gaps": ["No data collected from agents"],
            }
        
        # Count by severity
        critical = sum(1 for f in findings if f.severity == "critical")
        high = sum(1 for f in findings if f.severity == "high")
        
        # Average confidence
        avg_confidence = sum(f.confidence for f in findings) / len(findings)
        
        # Sufficient if we have critical/high findings with good confidence
        sufficient = (
            (critical > 0 and avg_confidence > 0.6) or
            (high >= 2 and avg_confidence > 0.7) or
            state.context.iteration >= state.context.max_iterations - 1
        )
        
        # Find most likely root cause
        high_conf_findings = sorted(
            [f for f in findings if f.severity in ("critical", "high")],
            key=lambda f: f.confidence,
            reverse=True,
        )
        
        root_cause = high_conf_findings[0].detail if high_conf_findings else None
        
        return {
            "sufficient_evidence": sufficient,
            "confidence": avg_confidence,
            "summary": f"Found {critical} critical, {high} high severity findings",
            "root_cause": root_cause,
            "gaps": [] if sufficient else ["Additional investigation may be needed"],
        }
    
    def _format_findings_for_synthesis(self, state: CoordinatorState) -> str:
        """Format findings for synthesis prompt.
        
        Args:
            state: Coordinator state
            
        Returns:
            Formatted findings text
        """
        lines = [
            f"# Investigation Findings (Iteration {state.context.iteration + 1})",
            f"Alert: {state.alert.get('name', 'Unknown')}",
            "",
        ]
        
        # Group by category (agent)
        by_category: dict[str, list[Finding]] = {}
        for finding in state.all_findings:
            cat = finding.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(finding)
        
        for category, findings in by_category.items():
            lines.append(f"## {category}")
            for finding in findings:
                lines.append(f"- [{finding.severity}] {finding.detail}")
                if finding.evidence:
                    lines.append(f"  Evidence: {finding.evidence[:200]}")
            lines.append("")
        
        lines.append(f"Total findings: {len(state.all_findings)}")
        
        return "\n".join(lines)
    
    def _parse_synthesis_response(self, response: Any) -> dict[str, Any]:
        """Parse synthesis response from LLM.
        
        Args:
            response: LLM response
            
        Returns:
            Parsed synthesis dictionary
        """
        text = str(response.content if hasattr(response, "content") else response)
        
        try:
            # Try to extract JSON
            if "```json" in text:
                json_text = text.split("```json")[1].split("```")[0]
            else:
                json_text = text
            
            return json.loads(json_text.strip())
            
        except Exception as e:
            logger.warning(f"[coordinator] Failed to parse synthesis: {e}")
            return {
                "sufficient_evidence": True,  # Default to proceeding
                "confidence": 0.5,
                "summary": text[:500],
            }
    
    # -------------------------------------------------------------------------
    # Remediation Phase
    # -------------------------------------------------------------------------
    
    async def _run_remediation_phase(self, state: CoordinatorState) -> None:
        """Run the remediation planning phase.
        
        Args:
            state: Coordinator state
        """
        inv_id = state.investigation_id
        
        state.add_timeline_event("Remediation planning started", phase="recommending")
        await self.events.emit(EventType.REMEDIATION_STARTED, inv_id)
        
        # Create remediation agent if needed
        if not self._remediation_agent:
            self._remediation_agent = RemediationAgent(llm=self.llm)
        
        # Build context
        exec_context = ExecutionContext(
            investigation_id=inv_id,
            alert=state.alert,
            previous_findings=state.all_findings,
        )
        
        async with self._timeout_manager.timeout_context(
            "remediation",
            inv_id,
            self.events,
        ):
            async with self._retry_manager.retry_context(
                "remediation",
                inv_id,
            ):
                result = await self._remediation_agent.run(exec_context)
        
        if result.output and isinstance(result.output, RemediationOutput):
            state.remediation_output = result.output
            state.add_findings(result.state.findings)
            
            state.add_timeline_event(
                f"Remediation planned: {len(result.output.recommended_actions)} actions",
                phase="recommending",
                agent="remediation",
            )
        
        await self.events.emit(
            EventType.REMEDIATION_COMPLETED,
            inv_id,
            {
                "action_count": len(state.remediation_output.recommended_actions) if state.remediation_output else 0,
            },
        )
    
    # -------------------------------------------------------------------------
    # Action Execution
    # -------------------------------------------------------------------------
    
    async def execute_action(
        self,
        investigation_id: str,
        action_id: str,
        approved_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute a remediation action.
        
        Args:
            investigation_id: Investigation ID
            action_id: Action to execute
            approved_by: Who approved the action
            
        Returns:
            Action result
        """
        state = self._active.get(investigation_id)
        if not state:
            return {"success": False, "error": "Investigation not found"}
        
        if not state.remediation_output:
            return {"success": False, "error": "No remediation plan"}
        
        # Find action
        action = None
        for a in state.remediation_output.recommended_actions:
            if str(a.action) == action_id:  # Simplified matching
                action = a
                break
        
        if not action:
            return {"success": False, "error": "Action not found"}
        
        # Check if action requires approval
        if action.requires_approval and not approved_by:
            return {"success": False, "error": "Action requires approval"}
        
        await self.events.emit(
            EventType.ACTION_APPROVED,
            investigation_id,
            {"action": action.action, "approved_by": approved_by},
        )
        
        # In a real system, would execute the action here
        # For now, just log it
        logger.info(f"[coordinator] Would execute action: {action.action}")
        
        state.add_timeline_event(
            f"Action approved: {action.action}",
            phase="executing",
            approved_by=approved_by,
        )
        
        await self.events.emit(
            EventType.ACTION_EXECUTED,
            investigation_id,
            {"action": action.action, "success": True},
        )
        
        return {"success": True, "action": action.action}
    
    # -------------------------------------------------------------------------
    # Status and Timeline
    # -------------------------------------------------------------------------
    
    async def get_status(self, investigation_id: str) -> InvestigationStatus:
        """Get current investigation status.
        
        Args:
            investigation_id: Investigation ID
            
        Returns:
            InvestigationStatus object
        """
        state = self._active.get(investigation_id)
        
        if not state:
            # Try to load from persistence
            persisted = await self._persister.load(investigation_id)
            if persisted:
                context = InvestigationContext.from_persist_dict(
                    persisted.get("context", {})
                )
                return InvestigationStatus(
                    investigation_id=investigation_id,
                    status=context.status.value,
                    phase=context.current_phase,
                    iteration=context.iteration,
                    max_iterations=context.max_iterations,
                    completed_agents=context.completed_agents,
                    failed_agents=context.failed_agents,
                    has_result=context.has_result,
                )
            
            return InvestigationStatus(
                investigation_id=investigation_id,
                status="not_found",
                phase="unknown",
                iteration=0,
                max_iterations=0,
            )
        
        context = state.context
        
        # Count findings
        critical = sum(1 for f in state.all_findings if f.severity == "critical")
        high = sum(1 for f in state.all_findings if f.severity == "high")
        
        elapsed = None
        if context.started_at:
            end = context.completed_at or datetime.now(timezone.utc)
            elapsed = (end - context.started_at).total_seconds()
        
        last_error = None
        if context.errors:
            last_error = context.errors[-1].get("error")
        
        return InvestigationStatus(
            investigation_id=investigation_id,
            status=context.status.value,
            phase=context.current_phase,
            iteration=context.iteration,
            max_iterations=context.max_iterations,
            started_at=context.started_at,
            elapsed_seconds=elapsed,
            pending_agents=context.pending_agents,
            completed_agents=context.completed_agents,
            failed_agents=context.failed_agents,
            total_findings=len(state.all_findings),
            critical_findings=critical,
            high_findings=high,
            error_count=len(context.errors),
            last_error=last_error,
            has_result=context.has_result,
        )
    
    def create_timeline(self, investigation_id: str) -> Timeline:
        """Create investigation timeline.
        
        Args:
            investigation_id: Investigation ID
            
        Returns:
            Timeline object
        """
        state = self._active.get(investigation_id)
        
        if not state:
            return Timeline(investigation_id=investigation_id)
        
        timeline = Timeline(investigation_id=investigation_id)
        
        for entry in state.timeline:
            timeline.entries.append(TimelineEntry(
                timestamp=datetime.fromisoformat(entry["timestamp"]),
                phase=entry["phase"],
                event=entry["event"],
                agent=entry.get("agent"),
                details=entry.get("details", {}),
            ))
        
        return timeline
    
    # -------------------------------------------------------------------------
    # Result Generation
    # -------------------------------------------------------------------------
    
    async def _generate_investigation_result(
        self,
        state: CoordinatorState,
    ) -> Investigation:
        """Generate the final investigation result.
        
        Args:
            state: Coordinator state
            
        Returns:
            Investigation object
        """
        context = state.context
        
        # Build investigation result
        result = InvestigationResult(
            root_cause=state.synthesis_result.get("root_cause") if state.synthesis_result else None,
            root_cause_confidence=state.synthesis_result.get("confidence", 0.0) if state.synthesis_result else 0.0,
            summary=self._generate_summary(state),
            contributing_factors=self._extract_contributing_factors(state),
            timeline=[e for e in state.timeline],
            recommendations=self._extract_recommendations(state),
        )
        
        state.final_result = result
        
        # Build Investigation object
        from autosre.core.alert import Alert
        
        alert_obj = Alert(
            name=state.alert.get("name", "Unknown"),
            source=state.alert.get("source", "unknown"),
            severity=state.alert.get("severity", "medium"),
        )
        
        investigation = Investigation(
            id=state.investigation_id,
            alert=alert_obj,
            status=InvestigationState(context.status.value),
            hypotheses=state.hypotheses,
            findings=state.all_findings,
            result=result,
            created_at=context.created_at,
            started_at=context.started_at,
            completed_at=context.completed_at,
        )
        
        return investigation
    
    def _generate_summary(self, state: CoordinatorState) -> str:
        """Generate executive summary.
        
        Args:
            state: Coordinator state
            
        Returns:
            Summary text
        """
        lines = []
        
        # Alert info
        lines.append(f"Investigation of alert: {state.alert.get('name', 'Unknown')}")
        lines.append("")
        
        # Triage
        if state.triage_result:
            lines.append(f"Severity: {state.triage_result.severity}")
            if state.triage_result.affected_services:
                lines.append(f"Affected services: {', '.join(state.triage_result.affected_services)}")
        
        # Root cause
        if state.synthesis_result and state.synthesis_result.get("root_cause"):
            lines.append("")
            lines.append(f"Root cause: {state.synthesis_result['root_cause']}")
            lines.append(f"Confidence: {state.synthesis_result.get('confidence', 0):.0%}")
        
        # Actions
        if state.remediation_output:
            lines.append("")
            lines.append(f"Recommended actions: {len(state.remediation_output.recommended_actions)}")
        
        return "\n".join(lines)
    
    def _extract_contributing_factors(self, state: CoordinatorState) -> list[str]:
        """Extract contributing factors from findings.
        
        Args:
            state: Coordinator state
            
        Returns:
            List of contributing factors
        """
        factors = []
        
        for finding in state.all_findings:
            if finding.is_contributing_factor:
                factors.append(finding.detail)
        
        return factors[:5]  # Limit
    
    def _extract_recommendations(self, state: CoordinatorState) -> list[str]:
        """Extract recommendations.
        
        Args:
            state: Coordinator state
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if state.remediation_output:
            for action in state.remediation_output.recommended_actions:
                recommendations.append(action.action)
            recommendations.extend(state.remediation_output.prevention_recommendations)
        
        return recommendations[:10]  # Limit
    
    def _create_failed_investigation(
        self,
        state: CoordinatorState,
        error: str,
    ) -> Investigation:
        """Create a failed investigation result.
        
        Args:
            state: Coordinator state
            error: Error message
            
        Returns:
            Failed Investigation object
        """
        from autosre.core.alert import Alert
        
        context = state.context
        context.status = InvestigationState.FAILED
        context.completed_at = datetime.now(timezone.utc)
        context.record_error(error, context.current_phase, recoverable=False)
        
        alert_obj = Alert(
            name=state.alert.get("name", "Unknown"),
            source=state.alert.get("source", "unknown"),
        )
        
        result = InvestigationResult(
            summary=f"Investigation failed: {error}",
            requires_human_review=True,
        )
        
        return Investigation(
            id=state.investigation_id,
            alert=alert_obj,
            status=InvestigationState.FAILED,
            result=result,
            findings=state.all_findings,
        )
    
    # -------------------------------------------------------------------------
    # Error Handling
    # -------------------------------------------------------------------------
    
    async def _handle_investigation_error(
        self,
        state: CoordinatorState,
        error: Exception,
    ) -> Investigation:
        """Handle investigation error.
        
        Args:
            state: Coordinator state
            error: The exception
            
        Returns:
            Failed Investigation object
        """
        context = state.context
        
        context.record_error(
            str(error),
            context.current_phase,
            recoverable=False,
        )
        
        await self.events.emit(
            EventType.ERROR_OCCURRED,
            state.investigation_id,
            {
                "error": str(error),
                "phase": context.current_phase,
                "recoverable": False,
            },
        )
        
        await self.events.emit(
            EventType.FAILED,
            state.investigation_id,
            {"error": str(error)},
        )
        
        return self._create_failed_investigation(state, str(error))
    
    async def _handle_timeout(self, state: CoordinatorState) -> None:
        """Handle investigation timeout.
        
        Args:
            state: Coordinator state
        """
        context = state.context
        context.status = InvestigationState.TIMEOUT
        context.completed_at = datetime.now(timezone.utc)
        
        context.record_error(
            "Investigation timed out",
            context.current_phase,
            recoverable=False,
        )
        
        state.add_timeline_event(
            "Investigation timed out",
            phase=context.current_phase,
        )
        
        await self.events.emit(
            EventType.FAILED,
            state.investigation_id,
            {"error": "Timeout", "phase": context.current_phase},
        )
    
    async def _on_retry(
        self,
        investigation_id: str,
        operation: str,
        attempt: int,
        error: Exception,
    ) -> None:
        """Handle retry callback.
        
        Args:
            investigation_id: Investigation ID
            operation: Operation being retried
            attempt: Retry attempt number
            error: The error
        """
        state = self._active.get(investigation_id)
        if state:
            state.context.increment_retry(operation)
        
        await self.events.emit(
            EventType.RETRY_ATTEMPTED,
            investigation_id,
            {
                "operation": operation,
                "attempt": attempt,
                "error": str(error),
            },
        )
    
    # -------------------------------------------------------------------------
    # State Persistence
    # -------------------------------------------------------------------------
    
    async def _save_state(self, state: CoordinatorState) -> None:
        """Save investigation state.
        
        Args:
            state: State to save
        """
        try:
            await self._persister.save(
                state.investigation_id,
                state.to_persist_dict(),
            )
        except Exception as e:
            logger.error(f"[coordinator] Failed to save state: {e}")
    
    def _start_auto_save(self, investigation_id: str) -> None:
        """Start auto-save background task.
        
        Args:
            investigation_id: Investigation to auto-save
        """
        async def auto_save_loop():
            while True:
                await asyncio.sleep(self.config.auto_save_interval)
                state = self._active.get(investigation_id)
                if state:
                    await self._save_state(state)
        
        self._auto_save_task = asyncio.create_task(auto_save_loop())
    
    def _stop_auto_save(self) -> None:
        """Stop auto-save task."""
        if self._auto_save_task:
            self._auto_save_task.cancel()
            self._auto_save_task = None
    
    async def recover_investigation(
        self,
        investigation_id: str,
    ) -> Optional[CoordinatorState]:
        """Recover investigation from persistence.
        
        Args:
            investigation_id: Investigation to recover
            
        Returns:
            Recovered state or None
        """
        data = await self._persister.load(investigation_id)
        if not data:
            return None
        
        context = InvestigationContext.from_persist_dict(data.get("context", {}))
        
        state = CoordinatorState(
            investigation_id=investigation_id,
            context=context,
            alert=data.get("alert", {}),
            timeline=data.get("timeline", []),
        )
        
        # Restore triage
        if data.get("triage_result"):
            state.triage_result = TriageResult(**data["triage_result"])
        
        # Restore findings
        if data.get("all_findings"):
            state.all_findings = [Finding(**f) for f in data["all_findings"]]
        
        # Restore hypotheses
        if data.get("hypotheses"):
            state.hypotheses = [Hypothesis(**h) for h in data["hypotheses"]]
        
        self._active[investigation_id] = state
        
        logger.info(f"[coordinator] Recovered investigation {investigation_id}")
        
        return state
    
    async def list_active_investigations(self) -> list[str]:
        """List active investigation IDs.
        
        Returns:
            List of investigation IDs
        """
        # Combine in-memory and persisted
        in_memory = list(self._active.keys())
        persisted = await self._persister.list_active()
        
        return list(set(in_memory + persisted))
    
    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------
    
    async def cleanup(self) -> None:
        """Clean up coordinator resources."""
        self._stop_auto_save()
        
        # Save all active investigations
        for inv_id, state in self._active.items():
            await self._save_state(state)
        
        self._active.clear()


# =============================================================================
# Convenience Factory
# =============================================================================


def create_coordinator(
    llm_client: Optional[LLMClient] = None,
    config: Optional[CoordinatorConfig] = None,
    register_default_agents: bool = True,
) -> AgentCoordinator:
    """Create and configure an AgentCoordinator.
    
    Args:
        llm_client: LLM client to use
        config: Coordinator configuration
        register_default_agents: Whether to register default agents
        
    Returns:
        Configured AgentCoordinator
    """
    coordinator = AgentCoordinator(
        llm_client=llm_client,
        config=config,
    )
    
    if register_default_agents:
        from autosre.agents.investigator import (
            KubernetesInvestigator,
            MetricsInvestigator,
            LogsInvestigator,
            TracesInvestigator,
        )
        
        coordinator.register_agent(KubernetesInvestigator(llm=llm_client))
        coordinator.register_agent(MetricsInvestigator(llm=llm_client))
        coordinator.register_agent(LogsInvestigator(llm=llm_client))
        coordinator.register_agent(TracesInvestigator(llm=llm_client))
        coordinator.register_triage_agent(TriageAgent(llm=llm_client))
        coordinator.register_remediation_agent(RemediationAgent(llm=llm_client))
    
    return coordinator
