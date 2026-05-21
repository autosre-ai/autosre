#!/usr/bin/env python3
"""
AutoSRE Demo — Run a mock investigation

This demo shows the investigation flow using mock data.
No API keys required!

Usage:
    cd ~/clawd/projects/autosre
    python examples/demo_simple.py
    
    # Or with the venv:
    source .venv/bin/activate
    python examples/demo_simple.py
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add autosre to path if running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from autosre.agents import (
    InvestigationState,
    InvestigationStatus,
    InvestigationReport,
    Hypothesis,
    Evidence,
    Priority,
    SynthesisDecision,
)


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
    
    async def investigate(self, alert: dict) -> InvestigationReport:
        """Run a simulated investigation."""
        
        # Initialize state
        state = InvestigationState(
            alert=alert,
            thread_id=f"demo-{int(datetime.now().timestamp())}",
            service_name=alert.get("service", ""),
            alert_type="http_5xx",
        )
        
        print(f"  Thread ID: {state.thread_id}")
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
            Hypothesis(
                hypothesis="Database connection pool exhausted",
                priority=Priority.HIGH,
                agents_to_test=["metrics", "logs"],
            ),
            Hypothesis(
                hypothesis="Upstream payment-service timeout",
                priority=Priority.MEDIUM,
                agents_to_test=["metrics", "traces"],
            ),
            Hypothesis(
                hypothesis="Memory pressure causing OOM kills",
                priority=Priority.MEDIUM,
                agents_to_test=["kubernetes", "metrics"],
            ),
        ]
        state.selected_agents = ["metrics", "logs", "kubernetes"]
        
        for h in state.hypotheses:
            print(f"  • [{h.priority.value.upper()}] {h.hypothesis}")
        print(f"  Selected agents: {', '.join(state.selected_agents)}")
        
        # Phase 4: Evidence Collection
        print("\n🔎 Phase 4: Evidence Collection")
        
        evidence_items = [
            Evidence(
                source="prometheus",
                skill="query_metrics",
                query='rate(http_requests_total{status=~"5.."}[5m])',
                result="checkout-service: 12.3% error rate (threshold: 5%)",
                relevance=0.95,
            ),
            Evidence(
                source="kubernetes",
                skill="pod_logs",
                query="kubectl logs checkout-service-abc123",
                result="ERROR: Connection refused to postgres:5432 - pool exhausted",
                relevance=0.98,
            ),
            Evidence(
                source="postgres",
                skill="db_connections",
                query="SELECT count(*) FROM pg_stat_activity",
                result="Active connections: 200/200 (100% utilized)",
                relevance=0.99,
            ),
        ]
        
        for ev in evidence_items:
            state.add_evidence(ev)
            print(f"  [{ev.source}] {ev.result[:60]}...")
        
        # Phase 5: Synthesis
        print("\n💡 Phase 5: Synthesis")
        state.synthesis = SynthesisDecision(
            sufficient_evidence=True,
            confidence=0.95,
            root_cause="Database connection pool exhaustion on postgres-primary",
            summary="The checkout-service is experiencing 5xx errors due to database "
                    "connection pool exhaustion. All 200 connections are in use, causing "
                    "new requests to fail with 'Connection refused'. Recommend increasing "
                    "pool size or investigating long-running queries.",
            gaps=[],
        )
        state.status = InvestigationStatus.COMPLETED
        print(f"  Confidence: {state.synthesis.confidence:.0%}")
        print(f"  Root Cause: {state.synthesis.root_cause}")
        
        # Generate final report
        report = InvestigationReport(
            id=state.investigation_id,
            created_at=state.created_at,
            alert=state.alert,
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
