#!/usr/bin/env python3
"""
AutoSRE Demo — Run a mock investigation

This demo shows the investigation flow using mock data.
No API keys required!

Usage:
    cd ~/projects/autosre
    python examples/demo_simple.py
    
    # Or with the venv:
    source .venv/bin/activate
    python examples/demo_simple.py
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional


class InvestigationStatus(str, Enum):
    """Status of an investigation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MockHypothesis:
    """A potential root cause hypothesis."""
    hypothesis: str
    priority: str = "medium"  # high, medium, low
    agents_to_test: List[str] = field(default_factory=list)


@dataclass
class MockEvidence:
    """Evidence gathered by a subagent."""
    source: str
    skill: str
    finding: str
    confidence: float = 0.5


@dataclass
class MockSynthesis:
    """Result of the synthesis phase."""
    sufficient_evidence: bool
    confidence: float
    root_cause: str
    summary: str
    gaps: List[str] = field(default_factory=list)


@dataclass
class MockInvestigationState:
    """Complete state of an investigation."""
    investigation_id: str
    alert: Dict[str, Any]
    service_name: str
    alert_type: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "running"
    
    # Context
    memory_context: Dict = field(default_factory=dict)
    topology_context: Dict = field(default_factory=dict)
    
    # Planning
    hypotheses: List[MockHypothesis] = field(default_factory=list)
    selected_agents: List[str] = field(default_factory=list)
    
    # Evidence
    all_evidence: List[MockEvidence] = field(default_factory=list)
    
    # Synthesis
    synthesis: Optional[MockSynthesis] = None
    
    def add_evidence(self, evidence: MockEvidence):
        self.all_evidence.append(evidence)


@dataclass
class InvestigationReport:
    """Final investigation report."""
    id: str
    created_at: datetime
    alert: Dict[str, Any]
    service_name: str
    alert_type: str
    status: InvestigationStatus
    root_cause: str
    summary: str
    confidence: float
    hypotheses: List[MockHypothesis]
    evidence: List[MockEvidence]
    iterations: int
    duration_seconds: float
    skills_used: List[str]
    agents_used: List[str]


# Create mock alert
alert = {
    "name": "HighErrorRate",
    "service": "checkout-service",
    "severity": "critical",
    "description": "5xx error rate above 5%",
    "labels": {
        "cluster": "prod-us-east",
        "namespace": "ecommerce",
    }
}


class MockOrchestrator:
    """Demo orchestrator that simulates investigation without LLM calls."""
    
    async def investigate(self, alert_data: Dict[str, Any]) -> InvestigationReport:
        """Run a simulated investigation."""
        
        # Initialize state
        state = MockInvestigationState(
            investigation_id=f"demo-{int(datetime.now().timestamp())}",
            alert=alert_data,
            service_name=alert_data.get("service", ""),
            alert_type="http_5xx",
        )
        
        print(f"  Investigation ID: {state.investigation_id}")
        print(f"  Service: {state.service_name}")
        print(f"  Alert Type: {state.alert_type}")
        
        # Phase 1: Memory lookup
        print("\n📚 Phase 1: Memory Lookup")
        state.memory_context = {
            "has_similar_episodes": True,
            "episode_count": 3,
            "episodes": [
                {"root_cause": "Database connection pool exhaustion", "resolved": True},
                {"root_cause": "Memory leak in checkout handler", "resolved": True},
                {"root_cause": "Rate limiter misconfiguration", "resolved": True},
            ]
        }
        print(f"  Found {state.memory_context['episode_count']} similar past incidents")
        
        # Phase 2: Topology
        print("\n🗺️  Phase 2: Service Topology")
        state.topology_context = {
            "available": True,
            "dependencies": ["payment-service", "inventory-service", "redis"],
            "dependents": ["api-gateway", "mobile-backend"],
            "blast_radius_size": 5,
        }
        print(f"  Dependencies: {', '.join(state.topology_context['dependencies'])}")
        print(f"  Blast radius: {state.topology_context['blast_radius_size']} services")
        
        # Phase 3: Planning
        print("\n🎯 Phase 3: Hypothesis Generation")
        state.hypotheses = [
            MockHypothesis(
                hypothesis="Database connection pool exhausted",
                priority="high",
                agents_to_test=["metrics", "logs"],
            ),
            MockHypothesis(
                hypothesis="Upstream payment-service timeout",
                priority="medium",
                agents_to_test=["metrics", "traces"],
            ),
            MockHypothesis(
                hypothesis="Memory pressure causing OOM kills",
                priority="medium",
                agents_to_test=["kubernetes", "metrics"],
            ),
        ]
        state.selected_agents = ["metrics", "logs", "kubernetes"]
        
        for h in state.hypotheses:
            print(f"  • [{h.priority.upper()}] {h.hypothesis}")
        print(f"  Selected agents: {', '.join(state.selected_agents)}")
        
        # Phase 4: Evidence Collection
        print("\n🔎 Phase 4: Evidence Collection")
        
        evidence_items = [
            MockEvidence(
                source="prometheus",
                skill="query_metrics",
                finding="checkout-service: 12.3% error rate (threshold: 5%)",
                confidence=0.95,
            ),
            MockEvidence(
                source="kubernetes",
                skill="pod_logs",
                finding="ERROR: Connection refused to postgres:5432 - pool exhausted",
                confidence=0.98,
            ),
            MockEvidence(
                source="postgres",
                skill="db_connections",
                finding="Active connections: 200/200 (100% utilized)",
                confidence=0.99,
            ),
        ]
        
        for ev in evidence_items:
            state.add_evidence(ev)
            print(f"  [{ev.source}] {ev.finding}")
        
        # Phase 5: Synthesis
        print("\n💡 Phase 5: Synthesis")
        state.synthesis = MockSynthesis(
            sufficient_evidence=True,
            confidence=0.95,
            root_cause="Database connection pool exhaustion on postgres-primary",
            summary="The checkout-service is experiencing 5xx errors due to database "
                    "connection pool exhaustion. All 200 connections are in use, causing "
                    "new requests to fail with 'Connection refused'. Recommend increasing "
                    "pool size or investigating long-running queries.",
            gaps=[],
        )
        state.status = "completed"
        print(f"  Confidence: {state.synthesis.confidence:.0%}")
        print(f"  Root Cause: {state.synthesis.root_cause}")
        
        # Generate final report
        report = InvestigationReport(
            id=state.investigation_id,
            created_at=state.created_at,
            alert=alert_data,
            service_name=state.service_name,
            alert_type=state.alert_type,
            status=InvestigationStatus.COMPLETED,
            root_cause=state.synthesis.root_cause,
            summary=state.synthesis.summary,
            confidence=state.synthesis.confidence,
            hypotheses=state.hypotheses,
            evidence=state.all_evidence,
            iterations=1,
            duration_seconds=2.5,
            skills_used=["query_metrics", "pod_logs", "db_connections"],
            agents_used=state.selected_agents,
        )
        
        return report


async def main():
    print("=" * 60)
    print("🚀 AutoSRE Investigation Demo")
    print("=" * 60)
    print(f"\n📋 Alert: {alert['name']}")
    print(f"   Service: {alert['service']}")
    print(f"   Severity: {alert['severity']}")
    print(f"   Description: {alert['description']}")
    
    orch = MockOrchestrator()
    
    print("\n" + "-" * 60)
    print("🔍 Running Investigation...")
    print("-" * 60)
    
    report = await orch.investigate(alert)
    
    print("\n" + "=" * 60)
    print("📊 INVESTIGATION REPORT")
    print("=" * 60)
    print(f"  Status:      {report.status.value}")
    print(f"  Root Cause:  {report.root_cause}")
    print(f"  Confidence:  {report.confidence:.0%}")
    print(f"  Duration:    {report.duration_seconds:.1f}s")
    print(f"  Iterations:  {report.iterations}")
    print(f"  Skills Used: {', '.join(report.skills_used)}")
    
    print("\n📝 Summary:")
    print(f"  {report.summary}")
    
    print("\n" + "=" * 60)
    print("✅ Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
