#!/usr/bin/env python3
"""
AutoSRE Investigation Example

Demonstrates how to use AutoSRE v2 for incident investigation.

Run:
    python examples/investigate.py
    
Or with custom alert:
    python examples/investigate.py "payment-service timeout errors"
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from autosre import Orchestrator, EpisodicMemory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


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


async def run_investigation(alert: dict | str):
    """Run an investigation and display results."""
    
    # Create orchestrator
    orchestrator = Orchestrator()
    
    logger.info("=" * 60)
    logger.info("Starting Investigation")
    logger.info("=" * 60)
    
    if isinstance(alert, str):
        logger.info(f"Alert: {alert}")
    else:
        logger.info(f"Alert: {alert.get('name', 'unknown')}")
        logger.info(f"Service: {alert.get('service', 'unknown')}")
        logger.info(f"Severity: {alert.get('severity', 'unknown')}")
    
    logger.info("-" * 60)
    
    # Run investigation
    report = await orchestrator.investigate(alert)
    
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
    
    print("\n🚨 AutoSRE v2 Investigation Demo\n")
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
    
    if len(sys.argv) > 1:
        # Run with command line argument
        alert_input = " ".join(sys.argv[1:])
        
        # Check if it's a known example
        if alert_input in EXAMPLE_ALERTS:
            alert = EXAMPLE_ALERTS[alert_input]
        else:
            # Treat as description
            alert = alert_input
        
        await run_investigation(alert)
    else:
        # Run interactive demo
        await interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())
