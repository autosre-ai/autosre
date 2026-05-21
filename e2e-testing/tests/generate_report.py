"""
AutoSRE E2E Test Report Generator

Generates comprehensive markdown reports from E2E test results,
including summary tables, per-scenario details, evidence analysis,
and timing metrics.
"""

import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScenarioResult:
    """Result from a single test scenario."""
    scenario_id: int
    name: str
    passed: bool
    duration_seconds: float
    root_cause_detected: Optional[str] = None
    confidence: float = 0.0
    evidence_collected: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    error: Optional[str] = None
    verification_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestRunSummary:
    """Summary of a complete test run."""
    timestamp: str
    total_scenarios: int
    passed: int
    failed: int
    total_duration_seconds: float
    cluster_context: str
    config_path: str
    scenarios: List[ScenarioResult] = field(default_factory=list)


def load_test_results(results_path: str = "test_results.json") -> TestRunSummary:
    """Load test results from JSON file."""
    with open(results_path, "r") as f:
        data = json.load(f)
    
    scenarios = [
        ScenarioResult(**s) for s in data.get("scenarios", [])
    ]
    
    return TestRunSummary(
        timestamp=data.get("timestamp", datetime.now().isoformat()),
        total_scenarios=data.get("total_scenarios", len(scenarios)),
        passed=data.get("passed", sum(1 for s in scenarios if s.passed)),
        failed=data.get("failed", sum(1 for s in scenarios if not s.passed)),
        total_duration_seconds=data.get("total_duration_seconds", 0),
        cluster_context=data.get("cluster_context", "kind-autosre-e2e"),
        config_path=data.get("config_path", "autosre-config.yaml"),
        scenarios=scenarios
    )


def generate_summary_table(summary: TestRunSummary) -> str:
    """Generate markdown summary table."""
    pass_rate = (summary.passed / summary.total_scenarios * 100) if summary.total_scenarios > 0 else 0
    
    lines = [
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Scenarios | {summary.total_scenarios} |",
        f"| Passed | {summary.passed} ✅ |",
        f"| Failed | {summary.failed} ❌ |",
        f"| Pass Rate | {pass_rate:.1f}% |",
        f"| Total Duration | {summary.total_duration_seconds:.1f}s |",
        f"| Cluster Context | `{summary.cluster_context}` |",
        f"| Config | `{summary.config_path}` |",
        "",
    ]
    
    return "\n".join(lines)


def generate_scenario_table(scenarios: List[ScenarioResult]) -> str:
    """Generate scenario overview table."""
    lines = [
        "## Scenario Results",
        "",
        "| # | Scenario | Status | Confidence | Duration |",
        "|---|----------|--------|------------|----------|",
    ]
    
    for s in scenarios:
        status = "✅ PASS" if s.passed else "❌ FAIL"
        confidence = f"{s.confidence:.0%}" if s.confidence > 0 else "N/A"
        duration = f"{s.duration_seconds:.1f}s"
        lines.append(f"| {s.scenario_id} | {s.name} | {status} | {confidence} | {duration} |")
    
    lines.append("")
    return "\n".join(lines)


def generate_scenario_details(scenario: ScenarioResult) -> str:
    """Generate detailed section for a single scenario."""
    status_emoji = "✅" if scenario.passed else "❌"
    
    lines = [
        f"### Scenario {scenario.scenario_id}: {scenario.name} {status_emoji}",
        "",
        f"**Status:** {'PASSED' if scenario.passed else 'FAILED'}",
        f"**Duration:** {scenario.duration_seconds:.1f} seconds",
        f"**Confidence:** {scenario.confidence:.0%}",
        "",
    ]
    
    # Root cause
    if scenario.root_cause_detected:
        lines.extend([
            "#### Root Cause Detected",
            "",
            f"> {scenario.root_cause_detected}",
            "",
        ])
    elif not scenario.passed:
        lines.extend([
            "#### Root Cause",
            "",
            "⚠️ No root cause was detected",
            "",
        ])
    
    # Error (if any)
    if scenario.error:
        lines.extend([
            "#### Error",
            "",
            "```",
            scenario.error,
            "```",
            "",
        ])
    
    # Evidence
    if scenario.evidence_collected:
        lines.extend([
            "#### Evidence Collected",
            "",
        ])
        for i, evidence in enumerate(scenario.evidence_collected, 1):
            ev_type = evidence.get("type", evidence.get("source", "unknown"))
            ev_summary = evidence.get("summary", evidence.get("description", ""))
            lines.append(f"{i}. **{ev_type}**: {ev_summary}")
        lines.append("")
    
    # Recommendations
    if scenario.recommendations:
        lines.extend([
            "#### Recommendations",
            "",
        ])
        for rec in scenario.recommendations:
            lines.append(f"- {rec}")
        lines.append("")
    
    # Verification details
    if scenario.verification_details:
        lines.extend([
            "#### Verification Details",
            "",
            "<details>",
            "<summary>Click to expand</summary>",
            "",
            "```json",
            json.dumps(scenario.verification_details, indent=2),
            "```",
            "",
            "</details>",
            "",
        ])
    
    return "\n".join(lines)


def generate_timing_metrics(scenarios: List[ScenarioResult]) -> str:
    """Generate timing metrics section."""
    if not scenarios:
        return ""
    
    durations = [s.duration_seconds for s in scenarios]
    avg_duration = sum(durations) / len(durations)
    max_duration = max(durations)
    min_duration = min(durations)
    
    lines = [
        "## Timing Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Average Duration | {avg_duration:.1f}s |",
        f"| Fastest Scenario | {min_duration:.1f}s |",
        f"| Slowest Scenario | {max_duration:.1f}s |",
        "",
        "### Duration by Scenario",
        "",
        "```",
    ]
    
    # ASCII bar chart
    max_bar_width = 40
    scale = max_bar_width / max_duration if max_duration > 0 else 1
    
    for s in scenarios:
        bar_width = int(s.duration_seconds * scale)
        bar = "█" * bar_width
        lines.append(f"Scenario {s.scenario_id}: {bar} {s.duration_seconds:.1f}s")
    
    lines.extend([
        "```",
        "",
    ])
    
    return "\n".join(lines)


def generate_evidence_summary(scenarios: List[ScenarioResult]) -> str:
    """Generate evidence collection summary."""
    evidence_by_type: Dict[str, int] = {}
    
    for s in scenarios:
        for ev in s.evidence_collected:
            ev_type = ev.get("type", ev.get("source", "unknown"))
            evidence_by_type[ev_type] = evidence_by_type.get(ev_type, 0) + 1
    
    if not evidence_by_type:
        return ""
    
    lines = [
        "## Evidence Summary",
        "",
        "| Evidence Type | Count |",
        "|---------------|-------|",
    ]
    
    for ev_type, count in sorted(evidence_by_type.items(), key=lambda x: -x[1]):
        lines.append(f"| {ev_type} | {count} |")
    
    lines.append("")
    return "\n".join(lines)


def generate_recommendations_summary(scenarios: List[ScenarioResult]) -> str:
    """Generate consolidated recommendations."""
    all_recommendations: Dict[str, int] = {}
    
    for s in scenarios:
        for rec in s.recommendations:
            # Normalize recommendation
            rec_lower = rec.lower().strip()
            all_recommendations[rec_lower] = all_recommendations.get(rec_lower, 0) + 1
    
    if not all_recommendations:
        return ""
    
    lines = [
        "## Consolidated Recommendations",
        "",
        "Based on all scenarios, the following recommendations were made:",
        "",
    ]
    
    # Sort by frequency
    sorted_recs = sorted(all_recommendations.items(), key=lambda x: -x[1])
    
    for rec, count in sorted_recs[:10]:  # Top 10
        freq = f"(mentioned {count}x)" if count > 1 else ""
        lines.append(f"- {rec.capitalize()} {freq}")
    
    lines.append("")
    return "\n".join(lines)


def generate_report(
    test_results: Optional[List[ScenarioResult]] = None,
    summary: Optional[TestRunSummary] = None,
    results_path: str = "test_results.json"
) -> str:
    """
    Generate comprehensive markdown report of E2E test results.
    
    Args:
        test_results: List of scenario results (alternative to summary)
        summary: Complete test run summary
        results_path: Path to JSON results file (used if summary not provided)
        
    Returns:
        Markdown formatted report string
    """
    # Build summary if not provided
    if summary is None:
        if test_results:
            summary = TestRunSummary(
                timestamp=datetime.now().isoformat(),
                total_scenarios=len(test_results),
                passed=sum(1 for r in test_results if r.passed),
                failed=sum(1 for r in test_results if not r.passed),
                total_duration_seconds=sum(r.duration_seconds for r in test_results),
                cluster_context="kind-autosre-e2e",
                config_path="autosre-config.yaml",
                scenarios=test_results
            )
        else:
            summary = load_test_results(results_path)
    
    # Build report sections
    sections = [
        "# AutoSRE E2E Test Report",
        "",
        f"**Generated:** {summary.timestamp}",
        "",
        "---",
        "",
        generate_summary_table(summary),
        generate_scenario_table(summary.scenarios),
        generate_timing_metrics(summary.scenarios),
        generate_evidence_summary(summary.scenarios),
        generate_recommendations_summary(summary.scenarios),
        "---",
        "",
        "## Detailed Results",
        "",
    ]
    
    # Add per-scenario details
    for scenario in summary.scenarios:
        sections.append(generate_scenario_details(scenario))
    
    # Footer
    sections.extend([
        "---",
        "",
        "*Report generated by AutoSRE E2E Test Suite*",
    ])
    
    return "\n".join(sections)


def save_report(
    report: str,
    output_path: str = "e2e_report.md"
) -> None:
    """Save report to file."""
    with open(output_path, "w") as f:
        f.write(report)
    print(f"Report saved to: {output_path}")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate AutoSRE E2E test report"
    )
    parser.add_argument(
        "--input", "-i",
        default="test_results.json",
        help="Input JSON results file"
    )
    parser.add_argument(
        "--output", "-o",
        default="e2e_report.md",
        help="Output markdown report file"
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print report to stdout instead of file"
    )
    
    args = parser.parse_args()
    
    # Check if input exists
    if not os.path.exists(args.input):
        # Generate sample report with dummy data for testing
        print(f"Warning: {args.input} not found, generating sample report")
        sample_results = [
            ScenarioResult(
                scenario_id=i,
                name=name,
                passed=True,
                duration_seconds=30.0 + i * 5,
                root_cause_detected=f"Detected issue for scenario {i}",
                confidence=0.8,
                evidence_collected=[{"type": "metrics", "summary": "Sample metrics"}],
                recommendations=["Sample recommendation"]
            )
            for i, name in enumerate([
                "High Error Rate",
                "OOM Kill",
                "CPU Throttling",
                "DB Connection Pool",
                "Network Partition",
                "Cascading Failure"
            ], 1)
        ]
        report = generate_report(test_results=sample_results)
    else:
        summary = load_test_results(args.input)
        report = generate_report(summary=summary)
    
    if args.stdout:
        print(report)
    else:
        save_report(report, args.output)


if __name__ == "__main__":
    main()
