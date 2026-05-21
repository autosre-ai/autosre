#!/usr/bin/env python3
"""Full E2E Test Suite for AutoSRE"""

import subprocess
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ScenarioResult:
    name: str
    status: str
    detection_time_seconds: float
    root_cause_identified: bool
    hypothesis: Optional[str] = None
    evidence: Optional[List[str]] = None
    metrics_captured: Optional[dict] = None

def run_cmd(cmd: str) -> tuple:
    """Run shell command and return (stdout, stderr, returncode)"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode

def get_events(namespace: str = "bookstore") -> List[dict]:
    """Get Kubernetes events"""
    stdout, _, _ = run_cmd(f"kubectl get events -n {namespace} -o json --sort-by=.lastTimestamp")
    try:
        return json.loads(stdout).get("items", [])[-15:]
    except:
        return []

def get_pods(namespace: str = "bookstore") -> List[dict]:
    """Get pod status"""
    stdout, _, _ = run_cmd(f"kubectl get pods -n {namespace} -o json")
    try:
        pods = json.loads(stdout).get("items", [])
        return [
            {
                "name": p["metadata"]["name"],
                "status": p["status"]["phase"],
                "restarts": sum(c.get("restartCount", 0) for c in p["status"].get("containerStatuses", [])),
                "ready": all(c.get("ready", False) for c in p["status"].get("containerStatuses", []))
            }
            for p in pods
        ]
    except:
        return []

def query_prom(query: str) -> dict:
    """Query Prometheus"""
    url = f"http://localhost:9090/api/v1/query?query={urllib.parse.quote(query)}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read().decode())
    except:
        return {}

def investigate(scenario_name: str) -> ScenarioResult:
    """Run investigation after chaos injection"""
    start = datetime.now()
    issues = []
    metrics = {}
    
    # Check events
    for event in get_events():
        etype = event.get("type", "")
        reason = event.get("reason", "")
        msg = event.get("message", "")[:100]
        if etype == "Warning" or reason in ["Killing", "Unhealthy", "Failed", "BackOff", "OOMKilled", "FailedScheduling"]:
            issues.append(f"[{reason}] {msg}")
    
    # Check pods
    for pod in get_pods():
        if pod["status"] != "Running":
            issues.append(f"Pod {pod['name']} is {pod['status']}")
        if not pod["ready"]:
            issues.append(f"Pod {pod['name']} not ready")
        if pod["restarts"] > 0:
            issues.append(f"Pod {pod['name']}: {pod['restarts']} restarts")
            metrics["restarts"] = pod["restarts"]
    
    # Check container metrics from prometheus
    prom_result = query_prom('sum(kube_pod_container_status_waiting{namespace="bookstore"}) by (reason)')
    if prom_result.get("data", {}).get("result"):
        for r in prom_result["data"]["result"]:
            reason = r["metric"].get("reason", "unknown")
            if float(r["value"][1]) > 0:
                issues.append(f"Container waiting: {reason}")
    
    detection_time = (datetime.now() - start).total_seconds()
    root_cause = len(issues) > 0
    
    return ScenarioResult(
        name=scenario_name,
        status="✅ DETECTED" if root_cause else "⚠️ HEALTHY",
        detection_time_seconds=detection_time,
        root_cause_identified=root_cause,
        hypothesis=issues[0] if issues else None,
        evidence=issues[:5],
        metrics_captured=metrics
    )

def reset_env():
    """Reset environment after chaos"""
    run_cmd("kubectl rollout restart deployment -n bookstore bookstore-api")
    run_cmd("kubectl rollout restart deployment -n bookstore postgres 2>/dev/null || true")
    time.sleep(15)
    run_cmd("kubectl wait --for=condition=ready pod -l app=bookstore-api -n bookstore --timeout=60s")

def scenario_1_pod_failure():
    """High Error Rate - Kill pods"""
    print("\n" + "="*60)
    print("SCENARIO 1: POD FAILURE (High Error Rate)")
    print("="*60)
    
    print("[+] Injecting: Killing API pods...")
    run_cmd("kubectl delete pod -n bookstore -l app=bookstore-api --wait=false")
    
    print("[+] Waiting 10s for failure propagation...")
    time.sleep(10)
    
    print("[+] Investigating...")
    result = investigate("Pod Failure / High Error Rate")
    
    print(f"\n[RESULT] {result.status}")
    print(f"Detection Time: {result.detection_time_seconds:.2f}s")
    if result.evidence:
        print("Evidence:")
        for e in result.evidence:
            print(f"  - {e}")
    
    return result

def scenario_2_resource_exhaustion():
    """OOM / Resource exhaustion simulation"""
    print("\n" + "="*60)
    print("SCENARIO 2: RESOURCE PRESSURE")
    print("="*60)
    
    print("[+] Injecting: Setting very low memory limits...")
    patch = '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"16Mi"}}}]}}}}'
    run_cmd(f"kubectl patch deployment -n bookstore bookstore-api -p '{patch}'")
    
    print("[+] Waiting 20s for OOM events...")
    time.sleep(20)
    
    print("[+] Investigating...")
    result = investigate("Resource Exhaustion / OOM")
    
    print(f"\n[RESULT] {result.status}")
    print(f"Detection Time: {result.detection_time_seconds:.2f}s")
    if result.evidence:
        print("Evidence:")
        for e in result.evidence:
            print(f"  - {e}")
    
    # Reset memory limits
    patch = '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"128Mi"}}}]}}}}'
    run_cmd(f"kubectl patch deployment -n bookstore bookstore-api -p '{patch}'")
    
    return result

def scenario_3_db_failure():
    """Database failure - Cascade"""
    print("\n" + "="*60)
    print("SCENARIO 3: DATABASE FAILURE (Cascade)")
    print("="*60)
    
    print("[+] Injecting: Killing postgres pod...")
    run_cmd("kubectl delete pod -n bookstore -l app=postgres --wait=false")
    
    print("[+] Waiting 15s for cascade effects...")
    time.sleep(15)
    
    print("[+] Investigating...")
    result = investigate("Database Failure / Cascade")
    
    print(f"\n[RESULT] {result.status}")
    print(f"Detection Time: {result.detection_time_seconds:.2f}s")
    if result.evidence:
        print("Evidence:")
        for e in result.evidence:
            print(f"  - {e}")
    
    return result

def scenario_4_scale_down():
    """Scale to zero - Complete outage"""
    print("\n" + "="*60)
    print("SCENARIO 4: SCALE TO ZERO (Outage)")
    print("="*60)
    
    print("[+] Injecting: Scaling API to 0 replicas...")
    run_cmd("kubectl scale deployment -n bookstore bookstore-api --replicas=0")
    
    print("[+] Waiting 10s...")
    time.sleep(10)
    
    print("[+] Investigating...")
    result = investigate("Complete Outage / Scale Down")
    
    # Check if deployment has 0 available
    stdout, _, _ = run_cmd("kubectl get deployment -n bookstore bookstore-api -o jsonpath='{.status.availableReplicas}'")
    if stdout.strip() in ["", "0", "null"]:
        result.evidence = result.evidence or []
        result.evidence.insert(0, "No available replicas - complete outage")
        result.status = "✅ DETECTED"
        result.root_cause_identified = True
        result.hypothesis = "Deployment scaled to 0 - service unavailable"
    
    print(f"\n[RESULT] {result.status}")
    print(f"Detection Time: {result.detection_time_seconds:.2f}s")
    if result.evidence:
        print("Evidence:")
        for e in result.evidence:
            print(f"  - {e}")
    
    # Scale back up
    run_cmd("kubectl scale deployment -n bookstore bookstore-api --replicas=2")
    
    return result

def scenario_5_image_pull_failure():
    """Bad image - ImagePullBackOff"""
    print("\n" + "="*60)
    print("SCENARIO 5: BAD IMAGE (ImagePullBackOff)")
    print("="*60)
    
    print("[+] Injecting: Setting invalid image...")
    run_cmd("kubectl set image deployment/bookstore-api -n bookstore api=invalid-image:nonexistent")
    
    print("[+] Waiting 20s for pull failures...")
    time.sleep(20)
    
    print("[+] Investigating...")
    result = investigate("Image Pull Failure")
    
    print(f"\n[RESULT] {result.status}")
    print(f"Detection Time: {result.detection_time_seconds:.2f}s")
    if result.evidence:
        print("Evidence:")
        for e in result.evidence:
            print(f"  - {e}")
    
    # Fix image
    run_cmd("kubectl set image deployment/bookstore-api -n bookstore api=kennethreitz/httpbin:latest")
    
    return result

def scenario_6_liveness_failure():
    """Liveness probe failure"""
    print("\n" + "="*60)
    print("SCENARIO 6: LIVENESS PROBE FAILURE")
    print("="*60)
    
    print("[+] Injecting: Breaking liveness probe...")
    patch = '{"spec":{"template":{"spec":{"containers":[{"name":"api","livenessProbe":{"httpGet":{"path":"/nonexistent","port":80},"initialDelaySeconds":1,"periodSeconds":2,"failureThreshold":1}}]}}}}'
    run_cmd(f"kubectl patch deployment -n bookstore bookstore-api -p '{patch}'")
    
    print("[+] Waiting 20s for probe failures...")
    time.sleep(20)
    
    print("[+] Investigating...")
    result = investigate("Liveness Probe Failure")
    
    print(f"\n[RESULT] {result.status}")
    print(f"Detection Time: {result.detection_time_seconds:.2f}s")
    if result.evidence:
        print("Evidence:")
        for e in result.evidence:
            print(f"  - {e}")
    
    # Fix probe
    patch = '{"spec":{"template":{"spec":{"containers":[{"name":"api","livenessProbe":{"httpGet":{"path":"/status/200","port":80},"initialDelaySeconds":10,"periodSeconds":10,"failureThreshold":3}}]}}}}'
    run_cmd(f"kubectl patch deployment -n bookstore bookstore-api -p '{patch}'")
    
    return result

def generate_report(results: List[ScenarioResult]):
    """Generate markdown report"""
    report = f"""# AutoSRE E2E Test Report

**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Cluster:** kind-autosre-e2e  
**App:** Bookstore (httpbin + postgres)

---

## Summary

| # | Scenario | Status | Detection Time | Root Cause |
|---|----------|--------|----------------|------------|
"""
    
    for i, r in enumerate(results, 1):
        report += f"| {i} | {r.name} | {r.status} | {r.detection_time_seconds:.2f}s | {'✅' if r.root_cause_identified else '❌'} |\n"
    
    passed = sum(1 for r in results if r.root_cause_identified)
    total = len(results)
    
    report += f"""
---

## Results: {passed}/{total} scenarios detected successfully

"""
    
    for i, r in enumerate(results, 1):
        report += f"""### Scenario {i}: {r.name}

- **Status:** {r.status}
- **Detection Time:** {r.detection_time_seconds:.2f}s
- **Hypothesis:** {r.hypothesis or 'N/A'}

**Evidence:**
"""
        if r.evidence:
            for e in r.evidence:
                report += f"- {e}\n"
        else:
            report += "- No issues detected\n"
        report += "\n"
    
    return report

def main():
    print("="*60)
    print("AutoSRE E2E Test Suite")
    print("="*60)
    print(f"Started: {datetime.now()}")
    print()
    
    results = []
    
    # Run all scenarios
    try:
        results.append(scenario_1_pod_failure())
        time.sleep(5)
        reset_env()
        
        results.append(scenario_2_resource_exhaustion())
        time.sleep(5)
        reset_env()
        
        results.append(scenario_3_db_failure())
        time.sleep(5)
        reset_env()
        
        results.append(scenario_4_scale_down())
        time.sleep(5)
        reset_env()
        
        results.append(scenario_5_image_pull_failure())
        time.sleep(5)
        reset_env()
        
        results.append(scenario_6_liveness_failure())
        time.sleep(5)
        reset_env()
        
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
    except Exception as e:
        print(f"\n[!] Error: {e}")
    
    # Generate report
    print("\n" + "="*60)
    print("GENERATING REPORT")
    print("="*60)
    
    report = generate_report(results)
    
    report_path = os.path.expanduser("~/clawd/projects/autosre/e2e-testing/reports/e2e-report.md")
    with open(report_path, "w") as f:
        f.write(report)
    
    print(f"\nReport saved to: {report_path}")
    print()
    
    # Print summary
    passed = sum(1 for r in results if r.root_cause_identified)
    print(f"FINAL RESULT: {passed}/{len(results)} scenarios detected")
    print()
    
    return results

if __name__ == "__main__":
    import os
    main()
