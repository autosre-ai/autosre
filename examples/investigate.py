#!/usr/bin/env python3
"""
Example: Run an AutoSRE investigation.

This demonstrates the full investigation flow:
1. Load configuration
2. Initialize orchestrator
3. Run investigation
4. Print report

Usage:
    python examples/investigate.py
    
    # With environment variables:
    ANTHROPIC_API_KEY=sk-... python examples/investigate.py
"""

import asyncio
import sys
from pathlib import Path

# Add autosre to path if running from examples directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from autosre import Settings
from autosre.orchestrator import Orchestrator
from autosre.agents.writeup import format_report_markdown
from autosre.memory import EpisodicMemory
from autosre.topology import ServiceTopology


async def main():
    """Run an example investigation."""
    
    # Example alert (you would receive this from your alerting system)
    alert = {
        "name": "High5xxErrorRate",
        "alertname": "High5xxErrorRate",
        "service": "checkout-service",
        "severity": "critical",
        "description": "checkout-service has 5xx error rate above 5% for 10 minutes",
        "labels": {
            "namespace": "production",
            "team": "checkout",
        },
        "annotations": {
            "runbook_url": "https://runbooks.example.com/checkout-5xx",
        },
    }
    
    print("=" * 60)
    print("AutoSRE v2 Investigation Demo")
    print("=" * 60)
    print()
    print(f"Alert: {alert['name']}")
    print(f"Service: {alert['service']}")
    print(f"Severity: {alert['severity']}")
    print(f"Description: {alert['description']}")
    print()
    
    # Load topology from example file
    topology_file = Path(__file__).parent / "topology.yaml"
    topology = None
    if topology_file.exists():
        topology = ServiceTopology.from_yaml(topology_file)
        print(f"Loaded topology: {len(topology)} services")
    
    # Initialize memory (in-memory for demo)
    memory = EpisodicMemory(db_path=Path("/tmp/autosre_demo_memory.db"))
    print(f"Memory stats: {memory.get_stats()['total_episodes']} episodes")
    print()
    
    # Initialize orchestrator
    print("Initializing orchestrator...")
    orch = Orchestrator(
        memory=memory,
        topology=topology,
    )
    
    # Run investigation
    print()
    print("Starting investigation...")
    print("-" * 60)
    
    try:
        report = await orch.investigate(alert)
        
        print()
        print("=" * 60)
        print("INVESTIGATION REPORT")
        print("=" * 60)
        print()
        print(format_report_markdown(report))
        
    except Exception as e:
        print(f"\nInvestigation failed: {e}")
        
        # Check if it's an API key issue
        if "API key" in str(e) or "ANTHROPIC_API_KEY" in str(e):
            print("\nTip: Set your API key:")
            print("  export ANTHROPIC_API_KEY=sk-...")
            print("  # or")
            print("  export OPENAI_API_KEY=sk-...")
        
        return 1
    
    print()
    print("=" * 60)
    print("Demo complete!")
    print()
    print("Memory after investigation:")
    print(f"  Total episodes: {memory.get_stats()['total_episodes']}")
    print(f"  Resolution rate: {memory.get_stats()['resolution_rate']:.0%}")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
