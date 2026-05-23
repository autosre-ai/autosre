"""Investigation service - manages investigation lifecycle."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import structlog

from ..models.investigation import (
    AlertData,
    InvestigationCreate,
    InvestigationEvent,
    InvestigationResponse,
    InvestigationState,
    InvestigationStatus,
    InvestigationStep,
    InvestigationFeedback,
    EventType,
)

logger = structlog.get_logger()


class InvestigationService:
    """Service for managing investigations."""

    def __init__(self) -> None:
        # In production, this would be backed by Redis/PostgreSQL
        self._investigations: dict[str, InvestigationResponse] = {}
        self._event_queues: dict[str, asyncio.Queue[InvestigationEvent]] = {}

    async def create_investigation(
        self,
        request: InvestigationCreate,
    ) -> InvestigationResponse:
        """Create a new investigation from an alert."""
        investigation_id = f"inv-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Calculate priority based on severity and context
        priority = self._calculate_priority(request.alert, request.priority_override)

        investigation = InvestigationResponse(
            investigation_id=investigation_id,
            state=InvestigationState.PENDING,
            alert=request.alert,
            priority=priority,
            created_at=now,
            updated_at=now,
            steps=[],
            findings=[],
        )

        self._investigations[investigation_id] = investigation
        self._event_queues[investigation_id] = asyncio.Queue()

        logger.info(
            "investigation_created",
            investigation_id=investigation_id,
            service=request.alert.service,
            severity=request.alert.severity,
            priority=priority,
        )

        # Start investigation in background
        asyncio.create_task(self._run_investigation(investigation_id, request))

        return investigation

    async def get_investigation(self, investigation_id: str) -> InvestigationResponse | None:
        """Get investigation by ID."""
        return self._investigations.get(investigation_id)

    async def get_status(self, investigation_id: str) -> InvestigationStatus | None:
        """Get lightweight investigation status."""
        investigation = self._investigations.get(investigation_id)
        if not investigation:
            return None

        # Calculate progress based on state and steps
        progress = self._calculate_progress(investigation)

        return InvestigationStatus(
            investigation_id=investigation_id,
            state=investigation.state,
            progress=progress,
            current_step=investigation.steps[-1].action if investigation.steps else None,
            eta_seconds=self._estimate_eta(investigation),
        )

    async def stream_events(
        self,
        investigation_id: str,
    ) -> AsyncGenerator[InvestigationEvent, None]:
        """Stream investigation events via SSE."""
        queue = self._event_queues.get(investigation_id)
        if not queue:
            return

        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield event

                # Stop streaming on completion
                if event.event_type in (EventType.COMPLETE, EventType.ERROR):
                    break
        except asyncio.TimeoutError:
            # Send keepalive
            yield InvestigationEvent(
                event_type=EventType.STATE_CHANGE,
                investigation_id=investigation_id,
                data={"keepalive": True},
            )

    async def submit_feedback(
        self,
        investigation_id: str,
        feedback: InvestigationFeedback,
    ) -> bool:
        """Submit feedback for a completed investigation."""
        investigation = self._investigations.get(investigation_id)
        if not investigation:
            return False

        if investigation.state not in (
            InvestigationState.COMPLETED,
            InvestigationState.FAILED,
        ):
            return False

        logger.info(
            "feedback_received",
            investigation_id=investigation_id,
            rating=feedback.rating,
            accurate=feedback.accurate_diagnosis,
        )

        # In production, this would store feedback and trigger learning
        return True

    async def cancel_investigation(self, investigation_id: str) -> bool:
        """Cancel a running investigation."""
        investigation = self._investigations.get(investigation_id)
        if not investigation:
            return False

        if investigation.state not in (
            InvestigationState.PENDING,
            InvestigationState.RUNNING,
            InvestigationState.PAUSED,
        ):
            return False

        investigation.state = InvestigationState.CANCELLED
        investigation.updated_at = datetime.now(timezone.utc)
        investigation.completed_at = datetime.now(timezone.utc)

        # Notify stream
        await self._emit_event(
            investigation_id,
            EventType.STATE_CHANGE,
            {"new_state": "cancelled"},
        )

        logger.info("investigation_cancelled", investigation_id=investigation_id)
        return True

    async def list_investigations(
        self,
        state: InvestigationState | None = None,
        service: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[InvestigationResponse], int]:
        """List investigations with optional filters."""
        investigations = list(self._investigations.values())

        if state:
            investigations = [i for i in investigations if i.state == state]
        if service:
            investigations = [i for i in investigations if i.alert.service == service]

        # Sort by creation time descending
        investigations.sort(key=lambda x: x.created_at, reverse=True)
        total = len(investigations)

        return investigations[offset : offset + limit], total

    def _calculate_priority(
        self,
        alert: AlertData,
        override: int | None,
    ) -> int:
        """Calculate investigation priority (1=highest, 10=lowest)."""
        if override is not None:
            return override

        severity_map = {
            "critical": 1,
            "high": 3,
            "medium": 5,
            "low": 7,
            "info": 9,
        }

        return severity_map.get(alert.severity.value, 5)

    def _calculate_progress(self, investigation: InvestigationResponse) -> float:
        """Estimate investigation progress."""
        if investigation.state == InvestigationState.PENDING:
            return 0.0
        if investigation.state in (
            InvestigationState.COMPLETED,
            InvestigationState.FAILED,
            InvestigationState.CANCELLED,
        ):
            return 1.0

        # Estimate based on typical investigation (5 steps)
        return min(len(investigation.steps) / 5.0, 0.95)

    def _estimate_eta(self, investigation: InvestigationResponse) -> int | None:
        """Estimate remaining time in seconds."""
        if investigation.state != InvestigationState.RUNNING:
            return None

        # Simple estimate: 60 seconds per remaining step
        remaining_steps = max(5 - len(investigation.steps), 0)
        return remaining_steps * 60

    async def _emit_event(
        self,
        investigation_id: str,
        event_type: EventType,
        data: dict,
    ) -> None:
        """Emit an event to the investigation's event queue."""
        queue = self._event_queues.get(investigation_id)
        if queue:
            event = InvestigationEvent(
                event_type=event_type,
                investigation_id=investigation_id,
                data=data,
            )
            await queue.put(event)

    async def _run_investigation(
        self,
        investigation_id: str,
        request: InvestigationCreate,
    ) -> None:
        """Run the investigation (placeholder for agent integration)."""
        investigation = self._investigations[investigation_id]

        try:
            # Transition to running
            investigation.state = InvestigationState.RUNNING
            investigation.started_at = datetime.now(timezone.utc)
            investigation.updated_at = datetime.now(timezone.utc)

            await self._emit_event(
                investigation_id,
                EventType.STATE_CHANGE,
                {"new_state": "running"},
            )

            # Simulate investigation steps
            steps = [
                ("gather_context", "Gathering alert context and history"),
                ("query_metrics", "Querying relevant metrics"),
                ("analyze_logs", "Analyzing service logs"),
                ("check_changes", "Checking recent changes and deployments"),
                ("correlate_findings", "Correlating findings"),
            ]

            for i, (action, description) in enumerate(steps):
                step_id = f"step-{i+1}"
                step = InvestigationStep(
                    step_id=step_id,
                    action=action,
                    description=description,
                    started_at=datetime.now(timezone.utc),
                )
                investigation.steps.append(step)
                investigation.updated_at = datetime.now(timezone.utc)

                await self._emit_event(
                    investigation_id,
                    EventType.STEP_START,
                    {"step_id": step_id, "action": action, "description": description},
                )

                # Simulate work
                await asyncio.sleep(1)

                # Complete step
                step.completed_at = datetime.now(timezone.utc)
                step.result = {"status": "success"}

                await self._emit_event(
                    investigation_id,
                    EventType.STEP_COMPLETE,
                    {"step_id": step_id, "result": step.result},
                )

                # Simulate finding
                if i == 2:
                    finding = "Elevated error rates correlating with recent deployment"
                    investigation.findings.append(finding)
                    await self._emit_event(
                        investigation_id,
                        EventType.FINDING,
                        {"finding": finding, "confidence": 0.85},
                    )

            # Complete investigation
            investigation.state = InvestigationState.COMPLETED
            investigation.completed_at = datetime.now(timezone.utc)
            investigation.updated_at = datetime.now(timezone.utc)
            investigation.root_cause = "Recent deployment introduced regression"
            investigation.remediation = "Consider rollback or hotfix"
            investigation.confidence = 0.85

            await self._emit_event(
                investigation_id,
                EventType.COMPLETE,
                {
                    "root_cause": investigation.root_cause,
                    "remediation": investigation.remediation,
                    "confidence": investigation.confidence,
                },
            )

            logger.info(
                "investigation_completed",
                investigation_id=investigation_id,
                duration_seconds=(
                    investigation.completed_at - investigation.started_at
                ).total_seconds(),
            )

        except Exception as e:
            investigation.state = InvestigationState.FAILED
            investigation.completed_at = datetime.now(timezone.utc)
            investigation.updated_at = datetime.now(timezone.utc)

            await self._emit_event(
                investigation_id,
                EventType.ERROR,
                {"error": str(e)},
            )

            logger.error(
                "investigation_failed",
                investigation_id=investigation_id,
                error=str(e),
            )
