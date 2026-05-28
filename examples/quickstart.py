#!/usr/bin/env python3
"""
AutoSRE Quickstart Example
==========================

This quickstart demonstrates the core AutoSRE multi-agent investigation system.
It runs entirely without external dependencies (no OpenAI API, no Kubernetes, etc.)
by using mock components that simulate real investigation behavior.

How AutoSRE Works:
1. ALERT INGESTION   - Receive alerts from Prometheus, Datadog, PagerDuty, etc.
2. PLANNING          - AI Planner creates investigation steps based on alert context
3. INVESTIGATION     - Multiple investigators run in parallel to gather data
4. SYNTHESIS         - AI synthesizes all findings into root cause analysis
5. REPORT            - Generate actionable recommendations and remediation steps

Run this example:
    python examples/quickstart.py

"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path for running as standalone script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# ANSI Colors for Pretty Terminal Output
# =============================================================================
class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.RESET}\n")


def print_step(text: str) -> None:
    """Print an action step."""
    print(f"{Colors.CYAN}▶ {text}{Colors.RESET}")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"{Colors.DIM}  {text}{Colors.RESET}")


def print_agent(agent: str, message: str) -> None:
    """Print an agent's message with color coding."""
    colors = {
        "planner": Colors.BLUE,
        "investigator": Colors.YELLOW,
        "synthesizer": Colors.CYAN,
        "writeup": Colors.GREEN,
    }
    color = colors.get(agent.lower(), Colors.RESET)
    print(f"{color}[{agent.upper()}]{Colors.RESET} {message}")


# =============================================================================
# Mock Components (No External Dependencies Required)
# =============================================================================
class MockAlert:
    """
    Represents an alert from a monitoring system.
    
    In production, alerts come from integrations with:
    - Prometheus Alertmanager
    - Datadog
    - PagerDuty
    - OpsGenie
    - Grafana
    """
    
    @staticmethod
    def create_sample() -> Dict[str, Any]:
        """Create a sample high-CPU alert for demonstration."""
        return {
            "id": "alert-demo-001",
            "title": "High CPU Usage on payment-service",
            "description": "CPU usage has exceeded 90% for the past 5 minutes",
            "severity": "critical",
            "source": "prometheus",
            "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "labels": {
                "service": "payment-service",
                "namespace": "production",
                "cluster": "prod-us-east-1",
                "pod": "payment-service-6d4f5b-x7k9p",
            },
            "raw_data": {
                "current_value": 94.5,
                "threshold": 90,
                "duration_minutes": 5,
            }
        }


class MockPlanner:
    """
    The Planner agent analyzes alerts and creates investigation plans.
    
    In production, this uses an LLM (GPT-4, Claude) to intelligently
    determine what tools to run and in what order to diagnose the issue.
    """
    
    def create_plan(self, alert: Dict) -> Dict:
        """
        Create an investigation plan for the given alert.
        
        Returns a plan with steps that can be executed in parallel
        (depends_on=[]) or sequentially (depends_on=["step_id"]).
        """
        service = alert["labels"]["service"]
        namespace = alert["labels"]["namespace"]
        
        # This simulates what an LLM would produce
        return {
            "steps": [
                {
                    "id": "step_1",
                    "name": "Query error logs",
                    "description": "Check recent logs for errors and exceptions",
                    "tool": "logs_query",
                    "args": {"service": service, "level": "error", "limit": 100},
                    "depends_on": [],  # Can run in parallel
                },
                {
                    "id": "step_2",
                    "name": "Check pod status",
                    "description": "Get Kubernetes pod status and events",
                    "tool": "kubectl_exec",
                    "args": {"command": f"get pods -l app={service}", "namespace": namespace},
                    "depends_on": [],  # Can run in parallel
                },
                {
                    "id": "step_3",
                    "name": "Query CPU metrics",
                    "description": "Get detailed CPU utilization over time",
                    "tool": "metrics_query",
                    "args": {"query": f"container_cpu_usage{{{service}}}", "range": "30m"},
                    "depends_on": [],  # Can run in parallel
                },
                {
                    "id": "step_4",
                    "name": "Describe failing pod",
                    "description": "Get detailed pod info including events",
                    "tool": "kubectl_exec",
                    "args": {"command": f"describe pod", "namespace": namespace},
                    "depends_on": ["step_2"],  # Runs after step_2
                },
            ],
            "rationale": (
                f"Investigating high CPU alert for {service}. Starting with parallel "
                f"investigation of logs, pod status, and metrics. Then getting detailed "
                f"pod info based on pod status results."
            ),
            "estimated_duration_seconds": 30,
        }


class MockInvestigator:
    """
    The Investigator agent executes individual investigation steps.
    
    In production, this calls real tools:
    - Kubernetes API for kubectl commands
    - Prometheus for metrics queries  
    - Loki/Elasticsearch for log queries
    - Cloud provider APIs (AWS, GCP, Azure)
    """
    
    async def execute_step(self, step: Dict, alert: Dict) -> Dict:
        """
        Execute a single investigation step and return findings.
        
        Each step returns:
        - status: "success" or "error"
        - data: The raw data from the tool
        - summary: Human-readable summary of findings
        """
        # Simulate execution time
        await asyncio.sleep(0.3)
        
        tool = step["tool"]
        service = alert["labels"]["service"]
        
        # Return mock data based on tool type
        if tool == "logs_query":
            return {
                "step_id": step["id"],
                "step_name": step["name"],
                "status": "success",
                "data": {
                    "log_count": 47,
                    "error_types": ["OutOfMemoryError", "GCOverheadLimitExceeded"],
                    "sample_logs": [
                        f"2024-01-15T10:28:10Z ERROR [{service}] OutOfMemoryError: Java heap space",
                        f"2024-01-15T10:28:45Z WARN [{service}] Memory pressure detected, triggering GC",
                    ]
                },
                "summary": "Found 47 error logs. Dominant error: OutOfMemoryError (32 occurrences)",
            }
        
        elif tool == "metrics_query":
            return {
                "step_id": step["id"],
                "step_name": step["name"],
                "status": "success",
                "data": {
                    "current_value": 94.5,
                    "average": 72.3,
                    "max": 98.2,
                    "trend": "increasing",
                },
                "summary": "CPU at 94.5% (avg: 72.3%). Trend: increasing over last 30 minutes",
            }
        
        elif tool == "kubectl_exec":
            return {
                "step_id": step["id"],
                "step_name": step["name"],
                "status": "success",
                "data": {
                    "pods": [
                        {"name": f"{service}-6d4f5b-x7k9p", "status": "Running", "restarts": 3},
                        {"name": f"{service}-6d4f5b-y8m2q", "status": "Running", "restarts": 2},
                        {"name": f"{service}-6d4f5b-z9n3r", "status": "CrashLoopBackOff", "restarts": 8},
                    ],
                    "events": ["OOMKilled", "BackOff restarting failed container"],
                },
                "summary": "1/3 pods in CrashLoopBackOff with 8 restarts. Last termination: OOMKilled",
            }
        
        return {
            "step_id": step["id"],
            "step_name": step["name"],
            "status": "success",
            "data": {},
            "summary": "Tool executed successfully",
        }


class MockSynthesizer:
    """
    The Synthesizer agent combines all findings into root cause analysis.
    
    In production, this uses an LLM to:
    - Correlate findings across different data sources
    - Identify the most likely root cause
    - Assess confidence level
    - Generate timeline of events
    """
    
    def synthesize(self, alert: Dict, findings: List[Dict]) -> Dict:
        """
        Synthesize all investigation findings into root cause analysis.
        """
        service = alert["labels"]["service"]
        
        return {
            "root_cause": (
                f"The {service} pods are experiencing memory exhaustion (OOMKilled) "
                f"which is causing high CPU utilization due to aggressive garbage collection. "
                f"The root cause is likely a memory leak in the application or insufficient "
                f"memory limits for the current workload."
            ),
            "confidence": 0.87,
            "evidence": [
                "Logs show 32 OutOfMemoryError exceptions in the last 30 minutes",
                "Pod events confirm OOMKilled termination reason",
                "CPU spike correlates with GC overhead from memory pressure",
                "One pod in CrashLoopBackOff with 8 restarts",
            ],
            "timeline": [
                {"time": "T-30m", "event": "Memory usage starts climbing above baseline"},
                {"time": "T-15m", "event": "First OOMKilled event detected"},
                {"time": "T-10m", "event": "GC overhead increases, CPU rises to 80%"},
                {"time": "T-5m",  "event": "Alert triggered: CPU > 90%"},
                {"time": "T-2m",  "event": "Pod enters CrashLoopBackOff"},
            ],
            "severity": "critical",
        }


class MockReportGenerator:
    """
    The Report Generator creates actionable investigation reports.
    
    Reports include:
    - Executive summary
    - Root cause analysis
    - Evidence and timeline
    - Recommendations
    - Remediation steps
    """
    
    def generate(self, alert: Dict, synthesis: Dict) -> Dict:
        """Generate the final investigation report."""
        return {
            "title": f"Investigation Report: {alert['title']}",
            "alert_id": alert["id"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            
            "executive_summary": (
                f"Investigation of critical alert for {alert['labels']['service']} "
                f"identified memory exhaustion (OOMKilled) as the root cause with "
                f"{synthesis['confidence']:.0%} confidence. Immediate action required "
                f"to increase memory limits and investigate potential memory leak."
            ),
            
            "root_cause": synthesis["root_cause"],
            "confidence": synthesis["confidence"],
            "timeline": synthesis["timeline"],
            
            "recommendations": [
                "IMMEDIATE: Increase memory limits from 2Gi to 4Gi",
                "SHORT-TERM: Add memory alerts at 70% and 85% thresholds",
                "MEDIUM-TERM: Analyze heap dumps for memory leaks",
                "LONG-TERM: Implement horizontal pod autoscaling",
            ],
            
            "remediation_steps": [
                "1. kubectl edit deployment payment-service -n production",
                "2. Update resources.limits.memory to 4Gi",
                "3. Apply changes and monitor for 15 minutes",
                "4. If issue persists, scale deployment to 5 replicas",
            ],
        }


# =============================================================================
# Main Investigation Pipeline
# =============================================================================
async def run_mock_investigation(alert: Dict) -> Dict:
    """
    Run a complete mock investigation.
    
    This demonstrates the full AutoSRE pipeline:
    1. Planning - Create investigation steps
    2. Investigation - Execute steps (in parallel where possible)
    3. Synthesis - Analyze findings for root cause
    4. Report - Generate actionable report
    """
    
    # Step 1: Planning
    print_header("STEP 1: Planning Investigation")
    print_agent("planner", "Analyzing alert context...")
    
    planner = MockPlanner()
    plan = planner.create_plan(alert)
    
    print_agent("planner", f"Created investigation plan with {len(plan['steps'])} steps")
    print_info(f"Rationale: {plan['rationale']}")
    print()
    
    for step in plan["steps"]:
        deps = f" (depends on: {', '.join(step['depends_on'])})" if step['depends_on'] else " (parallel)"
        print_info(f"  {step['id']}: {step['name']}{deps}")
    
    # Step 2: Investigation (parallel execution)
    print_header("STEP 2: Executing Investigations")
    print_agent("investigator", "Running investigation steps in parallel...")
    
    investigator = MockInvestigator()
    
    # Execute all steps (simulating parallel execution)
    findings = []
    for step in plan["steps"]:
        print_step(f"Executing: {step['name']}")
        finding = await investigator.execute_step(step, alert)
        findings.append(finding)
        print_success(f"{finding['summary']}")
    
    # Step 3: Synthesis
    print_header("STEP 3: Synthesizing Findings")
    print_agent("synthesizer", "Analyzing all findings for root cause...")
    
    synthesizer = MockSynthesizer()
    synthesis = synthesizer.synthesize(alert, findings)
    
    print_agent("synthesizer", f"Root cause identified with {synthesis['confidence']:.0%} confidence")
    print()
    print(f"{Colors.BOLD}Root Cause:{Colors.RESET}")
    print(f"  {synthesis['root_cause']}")
    print()
    print(f"{Colors.BOLD}Evidence:{Colors.RESET}")
    for evidence in synthesis["evidence"]:
        print(f"  • {evidence}")
    
    # Step 4: Report Generation
    print_header("STEP 4: Generating Report")
    print_agent("writeup", "Creating investigation report...")
    
    report_gen = MockReportGenerator()
    report = report_gen.generate(alert, synthesis)
    
    print_success("Report generated successfully!")
    
    return {
        "alert": alert,
        "plan": plan,
        "findings": findings,
        "synthesis": synthesis,
        "report": report,
    }


def print_report(result: Dict) -> None:
    """Pretty-print the final investigation report."""
    report = result["report"]
    
    print_header("INVESTIGATION REPORT")
    
    print(f"{Colors.BOLD}Title:{Colors.RESET} {report['title']}")
    print(f"{Colors.BOLD}Alert ID:{Colors.RESET} {report['alert_id']}")
    print(f"{Colors.BOLD}Generated:{Colors.RESET} {report['generated_at']}")
    print()
    
    print(f"{Colors.BOLD}Executive Summary:{Colors.RESET}")
    print(f"  {report['executive_summary']}")
    print()
    
    print(f"{Colors.BOLD}Root Cause ({report['confidence']:.0%} confidence):{Colors.RESET}")
    print(f"  {report['root_cause']}")
    print()
    
    print(f"{Colors.BOLD}Timeline:{Colors.RESET}")
    for event in report["timeline"]:
        print(f"  {event['time']:>6}  {event['event']}")
    print()
    
    print(f"{Colors.BOLD}Recommendations:{Colors.RESET}")
    for rec in report["recommendations"]:
        print(f"  • {rec}")
    print()
    
    print(f"{Colors.BOLD}Remediation Steps:{Colors.RESET}")
    for step in report["remediation_steps"]:
        print(f"  {step}")


# =============================================================================
# Entry Point
# =============================================================================
async def main(interactive: bool = True):
    """
    Run the AutoSRE quickstart demonstration.
    
    Args:
        interactive: If True, pauses for user input. Set to False for automated runs.
    """
    
    print(f"""
{Colors.BOLD}{Colors.CYAN}
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║     AutoSRE - AI-Powered Site Reliability Engineering     ║
    ║                     Quickstart Demo                       ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
{Colors.RESET}
This demo shows how AutoSRE investigates incidents using a multi-agent
architecture. All components are mocked - no external APIs required.

In production, AutoSRE connects to:
  • Monitoring: Prometheus, Datadog, Grafana
  • Alerting: PagerDuty, OpsGenie, Alertmanager
  • Infrastructure: Kubernetes, AWS, GCP, Azure
  • AI: OpenAI GPT-4, Anthropic Claude, or local LLMs
""")
    
    # Create a sample alert
    alert = MockAlert.create_sample()
    
    print(f"{Colors.BOLD}Incoming Alert:{Colors.RESET}")
    print(f"  ID: {alert['id']}")
    print(f"  Title: {alert['title']}")
    print(f"  Severity: {Colors.RED}{alert['severity'].upper()}{Colors.RESET}")
    print(f"  Source: {alert['source']}")
    print(f"  Service: {alert['labels']['service']}")
    print()
    
    if interactive:
        input(f"{Colors.DIM}Press Enter to start the investigation...{Colors.RESET}")
    else:
        print(f"{Colors.DIM}Starting investigation (non-interactive mode)...{Colors.RESET}")
    
    # Run the investigation
    result = await run_mock_investigation(alert)
    
    # Print the final report
    print_report(result)
    
    print(f"""
{Colors.GREEN}{Colors.BOLD}Demo Complete!{Colors.RESET}

{Colors.BOLD}Next Steps:{Colors.RESET}
  1. Check out examples/demo_simple.py for a more detailed demonstration
  2. Configure real integrations in ~/.autosre/config.yaml
  3. Run the webhook server: autosre serve start
  4. Read the docs: https://github.com/autosre-ai/autosre

{Colors.DIM}For production use, set your LLM API key:
  export OPENSRE_OPENAI_API_KEY=your-key-here
  # or
  export OPENSRE_ANTHROPIC_API_KEY=your-key-here{Colors.RESET}
""")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AutoSRE Quickstart Demo - demonstrates the multi-agent investigation system"
    )
    parser.add_argument(
        "--no-input", "-n",
        action="store_true",
        help="Run without waiting for user input (non-interactive mode)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # Run the async main function
    asyncio.run(main(interactive=not args.no_input))
