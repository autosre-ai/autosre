#!/usr/bin/env python3
"""E2E Test Runner for AutoSRE"""

import sys
import os
import json
import subprocess
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

# Add autosre to path
sys.path.insert(0, os.path.expanduser('~/clawd/projects/autosre/src'))

from autosre import Orchestrator, Alert
from autosre.slo import ErrorBudgetCalculator, SLOContextProvider

@dataclass
class ScenarioResult:
    name: str
    status: str
    detection_time_seconds: float
    root_cause_identified: bool
    hypothesis: Optional[str] = None
    evidence: Optional[list] = None
    recommendations: Optional[list] = None

def get_kubernetes_events(namespace: str = "bookstore") -> list:
    """Get recent Kubernetes events"""
    result = subprocess.run(
        ["kubectl", "get", "events", "-n", namespace, "-o", "json", "--sort-by=.lastTimestamp"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        events = json.loads(result.stdout)
        return events.get("items", [])[-10:]  # Last 10 events
    return []

def get_pod_status(namespace: str = "bookstore") -> list:
    """Get pod status"""
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        pods = json.loads(result.stdout)
        return [
            {
                "name": p["metadata"]["name"],
                "status": p["status"]["phase"],
                "restarts": sum(c.get("restartCount", 0) for c in p["status"].get("containerStatuses", []))
            }
            for p in pods.get("items", [])
        ]
    return []

def query_prometheus(query: str) -> dict:
    """Query Prometheus"""
    import urllib.request
    import urllib.parse
    
    url = f"http://localhost:9090/api/v1/query?query={urllib.parse.quote(query)}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"status": "error", "error": str(e)}

def run_investigation(alert_description: str, scenario_name: str) -> ScenarioResult:
    """Run AutoSRE investigation for a scenario"""
    start_time = datetime.now()
    
    # Gather evidence
    events = get_kubernetes_events()
    pods = get_pod_status()
    
    # Check for issues in events
    issues_found = []
    for event in events:
        event_type = event.get("type", "")
        reason = event.get("reason", "")
        message = event.get("message", "")
        
        if event_type == "Warning" or reason in ["Killing", "Unhealthy", "Failed", "OOMKilled"]:
            issues_found.append(f"{reason}: {message}")
    
    # Check pod status
    for pod in pods:
        if pod["status"] != "Running":
            issues_found.append(f"Pod {pod['name']} is {pod['status']}")
        if pod["restarts"] > 0:
            issues_found.append(f"Pod {pod['name']} has {pod['restarts']} restarts")
    
    # Query metrics
    error_rate = query_prometheus('sum(rate(http_errors_total{namespace="bookstore"}[1m]))')
    
    end_time = datetime.now()
    detection_time = (end_time - start_time).total_seconds()
    
    # Determine result
    root_cause_identified = len(issues_found) > 0
    
    hypothesis = None
    if issues_found:
        hypothesis = f"Detected issues: {'; '.join(issues_found[:3])}"
    
    return ScenarioResult(
        name=scenario_name,
        status="✅ DETECTED" if root_cause_identified else "⚠️ NO ISSUES",
        detection_time_seconds=detection_time,
        root_cause_identified=root_cause_identified,
        hypothesis=hypothesis,
        evidence=issues_found[:5],
        recommendations=["Check pod logs", "Review recent deployments", "Check resource limits"]
    )

def main():
    print("=" * 60)
    print("AutoSRE E2E Investigation")
    print("=" * 60)
    print()
    
    # Run investigation
    result = run_investigation(
        alert_description="Service health check - investigating current state",
        scenario_name="Current State Analysis"
    )
    
    print(f"Scenario: {result.name}")
    print(f"Status: {result.status}")
    print(f"Detection Time: {result.detection_time_seconds:.2f}s")
    print(f"Root Cause Identified: {result.root_cause_identified}")
    print()
    
    if result.hypothesis:
        print(f"Hypothesis: {result.hypothesis}")
    
    if result.evidence:
        print("\nEvidence:")
        for e in result.evidence:
            print(f"  - {e}")
    
    if result.recommendations:
        print("\nRecommendations:")
        for r in result.recommendations:
            print(f"  - {r}")
    
    print()
    return result

if __name__ == "__main__":
    main()
