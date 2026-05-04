"""
AutoSRE Orchestrator

Main investigation flow coordinator. Manages the lifecycle of an investigation
from initial alert through root cause analysis to resolution.
"""
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from .config import Settings
from .agents.state import InvestigationState


@dataclass
class Investigation:
    """An active investigation instance."""
    id: str
    alert_id: str
    state: InvestigationState
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    

class Orchestrator:
    """
    Coordinates the investigation workflow.
    
    Responsibilities:
    - Receives alerts and creates investigations
    - Coordinates agents (planner, synthesizer, writeup)
    - Manages investigation state transitions
    - Integrates with memory for context
    - Produces final reports
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._investigations: dict[str, Investigation] = {}
    
    async def start_investigation(self, alert_id: str, context: dict) -> Investigation:
        """Start a new investigation from an alert."""
        from uuid import uuid4
        
        inv_id = str(uuid4())[:8]
        investigation = Investigation(
            id=inv_id,
            alert_id=alert_id,
            state=InvestigationState.PENDING,
        )
        self._investigations[inv_id] = investigation
        return investigation
    
    async def run_investigation(self, investigation_id: str) -> dict:
        """Execute the investigation workflow."""
        inv = self._investigations.get(investigation_id)
        if not inv:
            raise ValueError(f"Investigation {investigation_id} not found")
        
        # TODO: Implement full investigation flow
        # 1. Gather context via skills
        # 2. Plan investigation steps
        # 3. Execute and synthesize findings
        # 4. Generate writeup
        
        inv.state = InvestigationState.COMPLETED
        inv.ended_at = datetime.utcnow()
        
        return {"status": "completed", "investigation_id": investigation_id}
    
    def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        """Get an investigation by ID."""
        return self._investigations.get(investigation_id)
