"""
Orchestrator - Coordinates multi-agent investigation flow
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import asyncio

from opensre_core.agents.observe import ObserverAgent, Observation, ObservationResult
from opensre_core.agents.reason import ReasonerAgent, AnalysisResult
from opensre_core.agents.act import ActorAgent, Action, ActionPlan
from opensre_core.config import settings


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
    
    # Actions
    actions: list[Action] = field(default_factory=list)
    
    # Meta
    iterations: int = 0
    completed_at: datetime | None = None
    status: str = "running"  # running, completed, failed, timeout
    error: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
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
    
    def __init__(self):
        self.observer = ObserverAgent()
        self.reasoner = ReasonerAgent()
        self.actor = ActorAgent()
    
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
            
            # Step 2: Reason
            analysis = await self.reasoner.analyze(observations)
            result.root_cause = analysis.root_cause
            result.confidence = analysis.confidence
            result.similar_incidents = analysis.similar_incidents
            
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
        
        # Step 4: Auto-execute safe actions if enabled
        if auto_execute_safe:
            for action in action_plan.get_safe_actions():
                await self.actor.execute_action(action, dry_run=False)
    
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
        
        return await self.orchestrator.actor.approve_action(action)
    
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
        
        self.orchestrator.actor.reject_action(action, reason)
        return {"status": "rejected"}
