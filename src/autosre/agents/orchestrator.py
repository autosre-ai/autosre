"""
Orchestrator - Coordinates multi-agent investigation flow
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from opensre_core.agents.act import Action, ActorAgent
from opensre_core.agents.observe import Observation, ObservationResult, ObserverAgent
from opensre_core.agents.reason import ReasonerAgent
from opensre_core.config import settings
from opensre_core.learning.patterns import PatternMatch, PatternRecognizer
from opensre_core.learning.store import IncidentStore, StoredIncident
from opensre_core.metrics import (
    record_action_approved,
    record_action_executed,
    record_action_rejected,
    record_action_suggested,
    record_investigation_end,
    record_investigation_start,
)
from opensre_core.runbooks.manager import RunbookManager
from opensre_core.streaming import InvestigationStream, StreamEvent, StreamEventType


@dataclass
class InvestigationResult:
    """Complete result of an investigation."""
    # Input
    issue: str
    namespace: str
    started_at: datetime = field(default_factory=datetime.now)

    # Observations
    observations: list[Observation] = field(default_factory=list)

    # Analysis
    root_cause: str = ""
    confidence: float = 0.0
    similar_incidents: list[str] = field(default_factory=list)
    contributing_factors: list[str] = field(default_factory=list)

    # Actions
    actions: list[Action] = field(default_factory=list)

    # Meta
    id: str = field(default_factory=lambda: __import__('uuid').uuid4().hex[:8])
    iterations: int = 0
    completed_at: datetime | None = None
    status: str = "running"  # running, completed, failed, timeout
    error: str | None = None
    alert_name: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Pattern matching
    pattern_match: Optional[PatternMatch] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "issue": self.issue,
            "namespace": self.namespace,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "observations": [
                {
                    "source": o.source,
                    "type": o.type,
                    "summary": o.summary,
                    "severity": o.severity,
                }
                for o in self.observations
            ],
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "similar_incidents": self.similar_incidents,
            "contributing_factors": self.contributing_factors,
            "alert_name": self.alert_name,
            "timestamp": self.timestamp,
            "actions": [
                {
                    "id": a.id,
                    "description": a.description,
                    "command": a.command,
                    "risk": a.risk.value,
                    "status": a.status.value,
                    "requires_approval": a.requires_approval,
                }
                for a in self.actions
            ],
            "iterations": self.iterations,
            "error": self.error,
            "pattern_match": {
                "likely_root_cause": self.pattern_match.likely_root_cause,
                "pattern_confidence": self.pattern_match.pattern_confidence,
                "similar_incidents": self.pattern_match.similar_incidents,
                "common_actions": self.pattern_match.common_actions,
                "avg_resolution_time": self.pattern_match.avg_resolution_time,
                "success_rate": self.pattern_match.success_rate,
            } if self.pattern_match else None,
        }


class Orchestrator:
    """
    Orchestrates multi-agent investigation flow.

    Flow:
    1. Observer collects data from infrastructure
    2. Reasoner analyzes and determines root cause
    3. Actor suggests remediation actions
    4. Human approves/rejects actions
    5. Actor executes approved actions

    The orchestrator manages this flow and handles:
    - Iteration if initial analysis is inconclusive
    - Timeout management
    - Error handling
    - State persistence
    """

    def __init__(self, runbook_dir: str = "runbooks", db_path: str = "data/incidents.db"):
        self.observer = ObserverAgent()
        self.reasoner = ReasonerAgent()
        self.actor = ActorAgent()
        self.runbooks = RunbookManager(runbook_dir)

        # Learning components
        self.incident_store = IncidentStore(db_path)
        self.pattern_recognizer = PatternRecognizer(self.incident_store)

    async def investigate(
        self,
        issue: str,
        namespace: str = "default",
        timeout: int | None = None,
        auto_execute_safe: bool = False,
    ) -> InvestigationResult:
        """
        Run full investigation for an issue.

        Args:
            issue: Description of the issue/alert
            namespace: Kubernetes namespace
            timeout: Investigation timeout in seconds
            auto_execute_safe: Auto-execute low-risk actions

        Returns:
            InvestigationResult with findings and suggested actions
        """
        timeout = timeout or settings.timeout_seconds
        result = InvestigationResult(issue=issue, namespace=namespace)
        start_time = time.time()

        # Record metrics
        record_investigation_start()

        try:
            # Run investigation with timeout
            await asyncio.wait_for(
                self._run_investigation(result, namespace, auto_execute_safe),
                timeout=timeout,
            )
            result.status = "completed"

        except asyncio.TimeoutError:
            result.status = "timeout"
            result.error = f"Investigation timed out after {timeout}s"

        except Exception as e:
            result.status = "failed"
            result.error = str(e)

        result.completed_at = datetime.now()
        duration = time.time() - start_time

        # Record completion metrics
        record_investigation_end(
            namespace=namespace,
            status=result.status,
            duration=duration,
            confidence=result.confidence,
            iterations=result.iterations
        )

        return result

    async def _run_investigation(
        self,
        result: InvestigationResult,
        namespace: str,
        auto_execute_safe: bool,
    ):
        """Run the investigation loop."""
        max_iterations = settings.max_iterations

        for iteration in range(max_iterations):
            result.iterations = iteration + 1

            # Step 1: Observe
            observations = await self.observer.observe(
                issue=result.issue,
                namespace=namespace,
            )
            result.observations = observations.observations

            # Check for matching patterns from past incidents
            obs_dicts = [
                {"source": o.source, "type": o.type, "summary": o.summary, "severity": o.severity}
                for o in observations.observations
            ]
            pattern = self.pattern_recognizer.find_matching_pattern(obs_dicts, namespace)

            if pattern and pattern.pattern_confidence > 0.7:
                # High confidence pattern match - use learned knowledge
                result.pattern_match = pattern
                result.similar_incidents.append(
                    f"Pattern: {pattern.similar_incidents} similar incidents, "
                    f"{pattern.success_rate:.0%} resolved"
                )

            # Find relevant runbooks based on issue and observations
            obs_summaries = [o.summary for o in observations.observations]
            relevant_runbooks = self.runbooks.find_relevant(result.issue, obs_summaries)
            runbook_context = self.runbooks.get_context(relevant_runbooks)

            # Enhance context with pattern information
            if pattern:
                runbook_context += "\n\n## Learned Pattern\n"
                runbook_context += f"- Likely root cause: {pattern.likely_root_cause}\n"
                runbook_context += f"- Pattern confidence: {pattern.pattern_confidence:.0%}\n"
                runbook_context += f"- Similar past incidents: {pattern.similar_incidents}\n"
                runbook_context += f"- Avg resolution time: {pattern.avg_resolution_time:.0f} minutes\n"
                if pattern.common_actions:
                    runbook_context += "- Common remediation actions:\n"
                    for action, count in pattern.common_actions[:3]:
                        runbook_context += f"  - {action} (used {count}x)\n"

            # Step 2: Reason (with runbook context and pattern knowledge)
            analysis = await self.reasoner.analyze(observations, runbook_context=runbook_context)
            result.root_cause = analysis.root_cause
            result.confidence = analysis.confidence
            result.similar_incidents.extend(analysis.similar_incidents)

            # Boost confidence if pattern matches analysis
            if pattern and pattern.likely_root_cause.lower() in result.root_cause.lower():
                result.confidence = max(result.confidence, pattern.pattern_confidence)

            # Add runbook titles to similar incidents if relevant
            for rb in relevant_runbooks:
                if rb.title not in result.similar_incidents:
                    result.similar_incidents.append(f"Runbook: {rb.title}")

            # Check if we have sufficient confidence
            if analysis.confidence >= settings.confidence_threshold:
                break

            # If confidence is low, we might iterate with more specific queries
            # For now, we'll proceed anyway
            break

        # Step 3: Plan actions
        action_plan = await self.actor.plan_actions(
            analysis=analysis,
            namespace=namespace,
        )
        result.actions = action_plan.actions

        # Record suggested action metrics
        for action in result.actions:
            record_action_suggested(action.risk.value)

        # Step 4: Auto-execute safe actions if enabled
        if auto_execute_safe:
            for action in action_plan.get_safe_actions():
                await self.actor.execute_action(action, dry_run=False)

        # Step 5: Store incident for future learning
        stored = StoredIncident(
            id=result.id,
            issue=result.issue,
            namespace=namespace,
            root_cause=result.root_cause,
            confidence=result.confidence,
            observations=obs_dicts,
            actions=[
                {"id": a.id, "description": a.description, "command": a.command, "risk": a.risk.value}
                for a in result.actions
            ],
            actions_executed=[],
            created_at=datetime.now(),
        )
        self.incident_store.save(stored)

    async def execute_action(
        self,
        investigation_id: str,
        action_id: str,
    ) -> dict[str, Any]:
        """Execute a specific action from an investigation."""
        # In a full implementation, this would look up the investigation
        # and execute the specific action
        # For now, this is a placeholder
        return {"status": "not_implemented"}

    async def get_investigation(self, investigation_id: str) -> InvestigationResult | None:
        """Get an investigation by ID."""
        # Placeholder for persistence layer
        return None

    def record_outcome(
        self,
        investigation_id: str,
        outcome: str,
        feedback: str = None,
    ) -> bool:
        """
        Record the outcome of an investigation for learning.

        Args:
            investigation_id: The investigation ID
            outcome: "resolved", "escalated", or "false_positive"
            feedback: Optional user feedback
        """
        return self.incident_store.update_outcome(investigation_id, outcome, feedback)

    def record_action_executed(
        self,
        investigation_id: str,
        action_command: str,
    ) -> bool:
        """Record that an action was executed for an investigation."""
        return self.incident_store.record_action_executed(investigation_id, action_command)

    def get_incident_statistics(self, namespace: str = None) -> dict:
        """Get incident statistics for learning insights."""
        return self.incident_store.get_statistics(namespace)

    def get_similar_incidents(self, issue: str, namespace: str = None) -> list[StoredIncident]:
        """Find similar past incidents."""
        return self.incident_store.find_similar(issue, namespace)

    def suggest_runbook(self, root_cause: str, namespace: str = None) -> Optional[dict]:
        """Get runbook suggestions based on past successes."""
        suggestion = self.pattern_recognizer.suggest_runbook(root_cause, namespace)
        if suggestion:
            return {
                "recommended_actions": suggestion.recommended_actions,
                "success_count": suggestion.success_count,
                "total_similar": suggestion.total_similar,
                "avg_resolution_time": suggestion.avg_resolution_time,
            }
        return None

    def get_trends(self, namespace: str = None, days: int = 30) -> dict:
        """Get incident trends for analysis."""
        return self.pattern_recognizer.analyze_trends(namespace, days)

    async def investigate_streaming(
        self,
        issue: str,
        namespace: str = "default",
    ) -> AsyncIterator[StreamEvent]:
        """
        Run investigation with real-time streaming output.

        Yields StreamEvent objects as the investigation progresses,
        allowing real-time updates via WebSocket or CLI.

        Args:
            issue: Description of the issue/alert
            namespace: Kubernetes namespace

        Yields:
            StreamEvent: Events as the investigation progresses
        """

        stream = InvestigationStream()
        result = InvestigationResult(issue=issue, namespace=namespace)

        async def run():
            """Run the investigation in background, emitting events."""
            try:
                await stream.started(issue, namespace)

                # Record metrics
                start_time = time.time()
                record_investigation_start()

                # Phase 1: Observation
                await stream.progress("Collecting observations", 1, 4)
                observations = await self._observe_streaming(result.issue, namespace, stream)
                result.observations = observations.observations

                await stream.observation_complete(
                    count=len(observations.observations),
                    services=observations.services_involved
                )

                # Find relevant runbooks
                obs_summaries = [o.summary for o in observations.observations]
                relevant_runbooks = self.runbooks.find_relevant(result.issue, obs_summaries)
                runbook_context = self.runbooks.get_context(relevant_runbooks)

                # Phase 2: Analysis
                await stream.progress("Analyzing observations", 2, 4)
                await stream.thinking("Correlating metrics, logs, and events...")

                analysis = await self.reasoner.analyze(observations, runbook_context=runbook_context)
                result.root_cause = analysis.root_cause
                result.confidence = analysis.confidence
                result.similar_incidents = analysis.similar_incidents

                # Emit hypotheses
                for hypothesis in analysis.hypotheses:
                    await stream.hypothesis(
                        hypothesis=hypothesis.description,
                        confidence=hypothesis.confidence,
                        evidence=hypothesis.evidence
                    )

                # Emit root cause
                await stream.root_cause(analysis.root_cause, analysis.confidence)

                # Phase 3: Action planning
                await stream.progress("Generating remediation actions", 3, 4)
                await stream.thinking("Planning remediation based on root cause analysis...")

                action_plan = await self.actor.plan_actions(
                    analysis=analysis,
                    namespace=namespace,
                )
                result.actions = action_plan.actions

                # Emit each action
                for action in action_plan.actions:
                    await stream.action(
                        description=action.description,
                        command=action.command,
                        risk=action.risk.value,
                        action_id=action.id
                    )
                    record_action_suggested(action.risk.value)

                # Phase 4: Finalize
                await stream.progress("Finalizing investigation", 4, 4)

                result.status = "completed"
                result.completed_at = datetime.now()
                result.iterations = 1

                # Record completion metrics
                duration = time.time() - start_time
                record_investigation_end(
                    namespace=namespace,
                    status=result.status,
                    duration=duration,
                    confidence=result.confidence,
                    iterations=result.iterations
                )

                await stream.completed(result.to_dict())

            except Exception as e:
                result.status = "failed"
                result.error = str(e)
                await stream.error(str(e), details={"traceback": str(e)})

        # Start investigation in background
        asyncio.create_task(run())

        # Yield events as they come
        async for event in stream.subscribe():
            yield event

    async def _observe_streaming(
        self,
        issue: str,
        namespace: str,
        stream: InvestigationStream
    ) -> ObservationResult:
        """
        Run observation phase with streaming updates.

        Emits observation events as data is collected.
        """
        # Collect observations from observer
        observations = await self.observer.observe(issue=issue, namespace=namespace)

        # Stream each observation
        for obs in observations.observations:
            await stream.observation(
                source=obs.source,
                summary=obs.summary,
                severity=obs.severity,
                details=obs.details
            )
            # Small delay to not overwhelm the stream
            await asyncio.sleep(0.05)

        return observations


class InvestigationManager:
    """
    Manages multiple concurrent investigations.

    Features:
    - Track active investigations
    - Persist investigation state
    - Handle concurrent investigations
    """

    def __init__(self):
        self.orchestrator = Orchestrator()
        self.investigations: dict[str, InvestigationResult] = {}
        self._lock = asyncio.Lock()

    async def start_investigation(
        self,
        issue: str,
        namespace: str = "default",
    ) -> str:
        """Start a new investigation and return its ID."""
        import uuid

        investigation_id = str(uuid.uuid4())[:8]

        # Start investigation in background
        asyncio.create_task(
            self._run_and_store(investigation_id, issue, namespace)
        )

        return investigation_id

    async def _run_and_store(
        self,
        investigation_id: str,
        issue: str,
        namespace: str,
    ):
        """Run investigation and store result."""
        result = await self.orchestrator.investigate(issue, namespace)

        async with self._lock:
            self.investigations[investigation_id] = result

    async def get_investigation(self, investigation_id: str) -> InvestigationResult | None:
        """Get investigation by ID."""
        return self.investigations.get(investigation_id)

    async def list_investigations(self) -> list[dict[str, Any]]:
        """List all investigations."""
        return [
            {
                "id": inv_id,
                "issue": inv.issue,
                "status": inv.status,
                "started_at": inv.started_at.isoformat(),
            }
            for inv_id, inv in self.investigations.items()
        ]

    async def approve_action(
        self,
        investigation_id: str,
        action_id: str,
    ) -> dict[str, Any]:
        """Approve and execute an action."""
        investigation = self.investigations.get(investigation_id)
        if not investigation:
            return {"error": "Investigation not found"}

        action = next((a for a in investigation.actions if a.id == action_id), None)
        if not action:
            return {"error": "Action not found"}

        # Record approval metric
        record_action_approved(action.risk.value)

        # Execute and record result
        start_time = time.time()
        result = await self.orchestrator.actor.approve_action(action)
        duration = time.time() - start_time

        success = result.get("success", False) or "error" not in result
        record_action_executed(action.risk.value, success, duration)

        return result

    async def reject_action(
        self,
        investigation_id: str,
        action_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject an action."""
        investigation = self.investigations.get(investigation_id)
        if not investigation:
            return {"error": "Investigation not found"}

        action = next((a for a in investigation.actions if a.id == action_id), None)
        if not action:
            return {"error": "Action not found"}

        # Record rejection metric
        record_action_rejected(action.risk.value)

        self.orchestrator.actor.reject_action(action, reason)
        return {"status": "rejected"}

    async def start_investigation_streaming(
        self,
        issue: str,
        namespace: str = "default",
    ) -> AsyncIterator[StreamEvent]:
        """
        Start investigation with real-time streaming.

        Returns an async iterator that yields events as the investigation progresses.
        Use this for WebSocket endpoints and CLI streaming output.

        Args:
            issue: Description of the issue/alert
            namespace: Kubernetes namespace

        Yields:
            StreamEvent: Events as the investigation progresses
        """
        async for event in self.orchestrator.investigate_streaming(issue, namespace):
            # Store completed result
            if event.type == StreamEventType.COMPLETED:
                result_data = event.data
                result = InvestigationResult(
                    id=result_data.get("id", ""),
                    issue=issue,
                    namespace=namespace,
                    status="completed",
                )
                # Update result from event data
                result.root_cause = result_data.get("root_cause", "")
                result.confidence = result_data.get("confidence", 0.0)
                async with self._lock:
                    self.investigations[result.id] = result

            yield event
