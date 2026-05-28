#!/usr/bin/env python3
"""
AutoSRE Investigation Example

Demonstrates how to use AutoSRE programmatically for incident investigation.

Run (interactive):
    python examples/investigate.py
    
Run (non-interactive):
    python examples/investigate.py --no-input
    
Or with custom alert:
    python examples/investigate.py "payment-service timeout errors"
    
For the simplest demo without any dependencies, see demo_simple.py
For CLI usage, use: autosre investigate run "your alert" --demo
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class InvestigationStatus(str, Enum):
    """Status of an investigation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Hypothesis:
    """A hypothesis about the root cause."""
    hypothesis: str
    confirmed: Optional[bool] = None
    priority: str = "medium"


@dataclass
class InvestigationReport:
    """Final investigation report."""
    id: str
    alert: str
    service: Optional[str]
    status: InvestigationStatus
    root_cause: Optional[str]
    summary: str
    confidence: float
    hypotheses: List[Hypothesis]
    iterations: int
    duration_seconds: float
    skills_used: List[str]
    agents_used: List[str]


# Example alerts for testing
EXAMPLE_ALERTS = {
    "checkout_5xx": {
        "name": "HighErrorRate",
        "service": "checkout-service",
        "severity": "critical",
        "description": "Checkout service error rate above 5% for 10 minutes",
        "labels": {
            "alertname": "ServiceHighErrorRate",
            "service": "checkout-service",
            "namespace": "production",
        },
    },
    "payment_timeout": {
        "name": "PaymentTimeout",
        "service": "payment-service",
        "severity": "warning",
        "description": "Payment processing timeouts increased by 300%",
        "labels": {
            "alertname": "ServiceHighLatency",
            "service": "payment-service",
        },
    },
    "inventory_oom": {
        "name": "InventoryOOM",
        "service": "inventory-service",
        "severity": "critical",
        "description": "Inventory service pod restarted due to OOM",
        "labels": {
            "alertname": "PodOOMKilled",
            "service": "inventory-service",
            "container": "inventory",
        },
    },
}


async def run_investigation(alert: dict | str) -> InvestigationReport:
    """Run an investigation using the AutoSRE CLI backend.
    
    This demonstrates programmatic usage. For production use cases,
    consider using the full Orchestrator API.
    """
    
    logger.info("=" * 60)
    logger.info("Starting Investigation")
    logger.info("=" * 60)
    
    if isinstance(alert, str):
        logger.info(f"Alert: {alert}")
        alert_desc = alert
        service = None
    else:
        logger.info(f"Alert: {alert.get('name', 'unknown')}")
        logger.info(f"Service: {alert.get('service', 'unknown')}")
        logger.info(f"Severity: {alert.get('severity', 'unknown')}")
        alert_desc = alert.get('description', alert.get('name', 'unknown alert'))
        service = alert.get('service')
    
    logger.info("-" * 60)
    
    # For this example, we use mock data to demonstrate the workflow
    # In production, you would integrate with the full Orchestrator
    import time
    start_time = time.time()
    
    # Simulate investigation phases
    logger.info("Phase 1: Triage - assessing impact...")
    await asyncio.sleep(0.3)
    
    logger.info("Phase 2: Evidence collection...")
    await asyncio.sleep(0.3)
    
    logger.info("Phase 3: Hypothesis generation...")
    hypotheses = [
        Hypothesis(hypothesis="Recent deployment introduced bug", confirmed=True, priority="high"),
        Hypothesis(hypothesis="Database connection pool exhausted", confirmed=False, priority="medium"),
        Hypothesis(hypothesis="External dependency timeout", confirmed=None, priority="low"),
    ]
    
    logger.info("Phase 4: Root cause synthesis...")
    await asyncio.sleep(0.3)
    
    duration = time.time() - start_time
    
    # Generate report
    report = InvestigationReport(
        id=f"inv-{int(datetime.now().timestamp())}",
        alert=alert_desc,
        service=service,
        status=InvestigationStatus.COMPLETED,
        root_cause="Configuration change in recent deployment caused connection pool exhaustion",
        summary=f"Investigation of '{alert_desc}' completed. Root cause identified as configuration change. Recommend rollback to previous version.",
        confidence=0.87,
        hypotheses=hypotheses,
        iterations=1,
        duration_seconds=duration,
        skills_used=["prometheus_query", "kubernetes_logs", "deployment_history"],
        agents_used=["metrics", "kubernetes", "changes"],
    )
    
    # Display results
    logger.info("=" * 60)
    logger.info("Investigation Report")
    logger.info("=" * 60)
    
    print(f"\n📋 Investigation ID: {report.id}")
    print(f"⏱️  Duration: {report.duration_seconds:.1f}s")
    print(f"🔄 Iterations: {report.iterations}")
    print(f"📊 Status: {report.status.value}")
    print(f"💯 Confidence: {report.confidence:.0%}")
    
    print(f"\n🎯 Root Cause:")
    print(f"   {report.root_cause or 'Not determined'}")
    
    print(f"\n📝 Summary:")
    print(f"   {report.summary[:500] if report.summary else 'No summary'}")
    
    if report.agents_used:
        print(f"\n🤖 Agents Used: {', '.join(report.agents_used)}")
    
    if report.skills_used:
        print(f"🛠️  Skills Used: {', '.join(report.skills_used)}")
    
    if report.hypotheses:
        print(f"\n🔍 Hypotheses Tested:")
        for h in report.hypotheses[:5]:
            status = "✓" if h.confirmed else "✗" if h.confirmed is False else "?"
            print(f"   [{status}] {h.hypothesis}")
    
    print("\n" + "=" * 60)
    
    return report


async def interactive_demo():
    """Run interactive demo with example alerts."""
    
    print("\n🚨 AutoSRE Investigation Demo\n")
    print("Choose an example alert:")
    print("  1. Checkout 5xx errors")
    print("  2. Payment timeout")
    print("  3. Inventory OOM")
    print("  4. Custom alert (enter description)")
    print()
    
    choice = input("Select [1-4]: ").strip()
    
    if choice == "1":
        alert = EXAMPLE_ALERTS["checkout_5xx"]
    elif choice == "2":
        alert = EXAMPLE_ALERTS["payment_timeout"]
    elif choice == "3":
        alert = EXAMPLE_ALERTS["inventory_oom"]
    elif choice == "4":
        alert = input("Enter alert description: ").strip()
    else:
        print("Invalid choice")
        return
    
    await run_investigation(alert)


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AutoSRE Investigation Example")
    parser.add_argument("alert", nargs="*", help="Alert description or example name")
    parser.add_argument("--no-input", action="store_true", help="Non-interactive mode (use default example)")
    args = parser.parse_args()
    
    if args.alert:
        # Run with command line argument
        alert_input = " ".join(args.alert)
        
        # Check if it's a known example
        if alert_input in EXAMPLE_ALERTS:
            alert = EXAMPLE_ALERTS[alert_input]
        else:
            # Treat as description
            alert = alert_input
        
        await run_investigation(alert)
    elif args.no_input:
        # Non-interactive mode - use first example
        alert = EXAMPLE_ALERTS["checkout_5xx"]
        print("\n🚨 AutoSRE Investigation Demo (non-interactive mode)\n")
        print(f"Running with example: checkout_5xx")
        await run_investigation(alert)
    else:
        # Run interactive demo
        await interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())
