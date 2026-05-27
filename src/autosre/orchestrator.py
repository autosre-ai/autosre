"""
AutoSRE Orchestrator

Main investigation flow coordinator. Manages the lifecycle of an investigation
from initial alert through root cause analysis to resolution.

Enhanced with Investigation Quality features based on Google SRE book:
- TRIAGE phase is mandatory first
- Golden Signals checked at investigation start
- Changes subagent always runs early
- Proper phase tracking and enforcement
"""
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum

from .config import Settings


class InvestigationStatus(str, Enum):
    """Investigation lifecycle status."""
    PENDING = "pending"
    TRIAGING = "triaging"
    MITIGATING = "mitigating"
    INVESTIGATING = "investigating"
    REMEDIATING = "remediating"
    VERIFYING = "verifying"
    DOCUMENTING = "documenting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class InvestigationMetrics:
    """Time tracking for investigation quality metrics.
    
    From SRE book: Track time-to-mitigation vs time-to-root-cause.
    """
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    triage_completed_at: Optional[datetime] = None
    mitigation_completed_at: Optional[datetime] = None
    root_cause_found_at: Optional[datetime] = None
    remediation_completed_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    @property
    def time_to_triage_seconds(self) -> Optional[float]:
        if self.triage_completed_at:
            return (self.triage_completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def time_to_mitigation_seconds(self) -> Optional[float]:
        """Key SRE metric: How fast did we stop the bleeding?"""
        if self.mitigation_completed_at:
            return (self.mitigation_completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def time_to_root_cause_seconds(self) -> Optional[float]:
        if self.root_cause_found_at:
            return (self.root_cause_found_at - self.started_at).total_seconds()
        return None


@dataclass
class Investigation:
    """An active investigation instance."""
    id: str
    alert_id: str
    state: InvestigationStatus
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: Optional[datetime] = None
    
    # Quality tracking
    metrics: InvestigationMetrics = field(default_factory=InvestigationMetrics)
    
    # Triage results (MANDATORY)
    triage_result: Optional[dict] = None
    mitigation_applied: Optional[dict] = None
    mitigation_skipped_reason: Optional[str] = None
    
    # Golden signals snapshot at investigation start
    golden_signals: Optional[dict] = None
    
    # Recent changes correlated with incident
    correlated_changes: Optional[list] = None
    

class Orchestrator:
    """
    Coordinates the investigation workflow.
    
    Responsibilities:
    - Receives alerts and creates investigations
    - ENFORCES triage-first policy
    - Coordinates agents (planner, synthesizer, writeup)
    - Tracks investigation quality metrics
    - Produces final reports
    
    Investigation Flow:
    1. TRIAGE (mandatory) - Assess impact, consider mitigation
    2. MITIGATE (if needed) - Apply immediate fixes
    3. INVESTIGATE - Find root cause (changes first, then others)
    4. REMEDIATE - Apply permanent fix
    5. VERIFY - Confirm fix worked
    6. DOCUMENT - Post-incident writeup
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._investigations: dict[str, Investigation] = {}
        
        # Optional components (lazy loaded)
        self._triage_node = None
        self._golden_signals_skill = None
        self._changes_subagent = None
        self._planner = None
    
    def _get_triage_node(self):
        """Lazy load triage node."""
        if self._triage_node is None:
            from .agents.nodes.triage import TriageNode
            self._triage_node = TriageNode(
                golden_signals_skill=self._get_golden_signals_skill(),
                changes_subagent=self._get_changes_subagent(),
            )
        return self._triage_node
    
    def _get_golden_signals_skill(self):
        """Lazy load golden signals skill."""
        if self._golden_signals_skill is None:
            try:
                from .skills.golden_signals import create_golden_signals_skill
                prometheus_url = getattr(self.settings, 'prometheus_url', 'http://prometheus:9090')
                self._golden_signals_skill = create_golden_signals_skill(prometheus_url)
            except Exception as e:
                import logging
                logging.warning(f"Failed to load golden signals skill: {e}")
        return self._golden_signals_skill
    
    def _get_changes_subagent(self):
        """Lazy load changes subagent."""
        if self._changes_subagent is None:
            try:
                from .agents.subagents.changes import create_changes_subagent
                github_token = getattr(self.settings, 'github_token', None)
                self._changes_subagent = create_changes_subagent(github_token=github_token)
            except Exception as e:
                import logging
                logging.warning(f"Failed to load changes subagent: {e}")
        return self._changes_subagent
    
    def _get_planner(self):
        """Lazy load planner."""
        if self._planner is None:
            from .agents.planner import Planner
            self._planner = Planner()
        return self._planner
    
    async def start_investigation(self, alert_id: str, context: dict) -> Investigation:
        """Start a new investigation from an alert."""
        from uuid import uuid4
        
        inv_id = str(uuid4())[:8]
        investigation = Investigation(
            id=inv_id,
            alert_id=alert_id,
            state=InvestigationStatus.PENDING,
        )
        self._investigations[inv_id] = investigation
        return investigation
    
    async def run_investigation(self, investigation_id: str) -> dict:
        """
        Execute the full investigation workflow.
        
        This enforces the phase order:
        1. TRIAGE (mandatory)
        2. MITIGATE (if applicable)
        3. INVESTIGATE
        4. REMEDIATE
        5. VERIFY
        6. DOCUMENT
        """
        inv = self._investigations.get(investigation_id)
        if not inv:
            raise ValueError(f"Investigation {investigation_id} not found")
        
        try:
            # Phase 1: TRIAGE (MANDATORY)
            inv.state = InvestigationStatus.TRIAGING
            await self._run_triage_phase(inv)
            
            # Phase 2: MITIGATE (if triage recommends it)
            if inv.triage_result and inv.triage_result.get("mitigation_options"):
                inv.state = InvestigationStatus.MITIGATING
                await self._run_mitigation_phase(inv)
            
            # Phase 3: INVESTIGATE (now we can find root cause)
            inv.state = InvestigationStatus.INVESTIGATING
            await self._run_investigation_phase(inv)
            
            # Phase 4-6: REMEDIATE, VERIFY, DOCUMENT
            inv.state = InvestigationStatus.REMEDIATING
            await self._run_remediation_phase(inv)
            
            inv.state = InvestigationStatus.VERIFYING
            await self._run_verification_phase(inv)
            
            inv.state = InvestigationStatus.DOCUMENTING
            await self._run_documentation_phase(inv)
            
            # Complete
            inv.state = InvestigationStatus.COMPLETED
            inv.ended_at = datetime.now(UTC)
            inv.metrics.ended_at = inv.ended_at
            
            return self._build_investigation_report(inv)
            
        except Exception as e:
            inv.state = InvestigationStatus.FAILED
            inv.ended_at = datetime.now(UTC)
            raise
    
    async def _run_triage_phase(self, inv: Investigation) -> None:
        """
        Run mandatory triage phase.
        
        1. Check golden signals
        2. Get recent changes
        3. Assess impact
        4. Generate mitigation options
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ORCHESTRATOR] Starting TRIAGE phase for investigation {inv.id}")
        
        # Get the alert context
        alert = {"alert_id": inv.alert_id}  # Would be populated from alert store
        
        # Get golden signals first (always)
        gs_skill = self._get_golden_signals_skill()
        if gs_skill:
            try:
                service = alert.get("service", "unknown")
                inv.golden_signals = await gs_skill.check_all_signals(service)
                logger.info(f"[ORCHESTRATOR] Golden signals: {inv.golden_signals}")
            except Exception as e:
                logger.warning(f"Failed to get golden signals: {e}")
        
        # Get recent changes
        changes_agent = self._get_changes_subagent()
        if changes_agent:
            try:
                changes_result = await changes_agent.get_recent_changes(
                    service=alert.get("service"),
                    hours=24,
                )
                inv.correlated_changes = changes_result.changes_near_incident
                logger.info(f"[ORCHESTRATOR] Found {len(inv.correlated_changes or [])} changes near incident")
            except Exception as e:
                logger.warning(f"Failed to get recent changes: {e}")
        
        # Run triage node
        triage_node = self._get_triage_node()
        triage_result = await triage_node.run(
            alert=alert,
            existing_golden_signals=inv.golden_signals,
            existing_changes=inv.correlated_changes,
        )
        
        inv.triage_result = triage_result.model_dump() if hasattr(triage_result, 'model_dump') else triage_result.__dict__
        inv.metrics.triage_completed_at = datetime.now(UTC)
        
        logger.info(
            f"[ORCHESTRATOR] Triage complete: impaired={inv.triage_result.get('is_service_impaired')}, "
            f"severity={inv.triage_result.get('impact', {}).get('severity')}"
        )
    
    async def _run_mitigation_phase(self, inv: Investigation) -> None:
        """Apply mitigation if recommended and approved."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ORCHESTRATOR] Starting MITIGATE phase for investigation {inv.id}")
        
        # For now, log the mitigation options - actual execution would require approval
        options = inv.triage_result.get("mitigation_options", [])
        if options:
            logger.info(f"[ORCHESTRATOR] Mitigation options: {[o.get('action') for o in options]}")
            # In production, this would trigger an approval workflow
            # For now, we mark mitigation as "considered"
            inv.mitigation_skipped_reason = "Mitigation requires human approval"
        
        inv.metrics.mitigation_completed_at = datetime.now(UTC)
    
    async def _run_investigation_phase(self, inv: Investigation) -> None:
        """Run the investigation to find root cause."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ORCHESTRATOR] Starting INVESTIGATE phase for investigation {inv.id}")
        
        # Enforcement: Triage must be complete
        from .agents.planner import require_triage_complete, InvestigationPhase
        require_triage_complete(inv.triage_result, InvestigationPhase.INVESTIGATE)
        
        # TODO: Run planner and subagents
        # This is where the existing investigation logic would go
        
        inv.metrics.root_cause_found_at = datetime.now(UTC)
    
    async def _run_remediation_phase(self, inv: Investigation) -> None:
        """Apply remediation."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ORCHESTRATOR] Starting REMEDIATE phase for investigation {inv.id}")
        # TODO: Implement remediation
        inv.metrics.remediation_completed_at = datetime.now(UTC)
    
    async def _run_verification_phase(self, inv: Investigation) -> None:
        """Verify remediation worked."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ORCHESTRATOR] Starting VERIFY phase for investigation {inv.id}")
        # TODO: Implement verification
    
    async def _run_documentation_phase(self, inv: Investigation) -> None:
        """Generate post-incident documentation."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ORCHESTRATOR] Starting DOCUMENT phase for investigation {inv.id}")
        # TODO: Implement documentation generation
    
    def _build_investigation_report(self, inv: Investigation) -> dict:
        """Build final investigation report."""
        return {
            "status": "completed",
            "investigation_id": inv.id,
            "alert_id": inv.alert_id,
            "metrics": {
                "time_to_triage_seconds": inv.metrics.time_to_triage_seconds,
                "time_to_mitigation_seconds": inv.metrics.time_to_mitigation_seconds,
                "time_to_root_cause_seconds": inv.metrics.time_to_root_cause_seconds,
                "total_duration_seconds": (inv.ended_at - inv.started_at).total_seconds() if inv.ended_at else None,
            },
            "triage_result": inv.triage_result,
            "golden_signals": inv.golden_signals,
            "correlated_changes": inv.correlated_changes,
            "mitigation_applied": inv.mitigation_applied,
            "mitigation_skipped_reason": inv.mitigation_skipped_reason,
        }
    
    def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        """Get an investigation by ID."""
        return self._investigations.get(investigation_id)
