#!/usr/bin/env python3
"""
OpenSRE Integration Test Runner

Runs automated test scenarios against the OpenSRE investigation system.
Captures results, timing, and confidence metrics across multiple repetitions.
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Any
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from opensre_core.agents.orchestrator import Orchestrator, InvestigationResult
from tests.integration.scenarios import SCENARIOS, TestScenario


@dataclass
class TestResult:
    """Result of a single test scenario run."""
    scenario: str
    issue: str
    namespace: str
    repetition: int
    elapsed_seconds: float
    confidence: float
    root_cause: str
    observations_count: int
    actions_count: int
    status: str
    error: str | None = None
    observations: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    expected_confidence_min: float = 0.0
    passed: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TestSummary:
    """Summary statistics for test run."""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    avg_confidence: float = 0.0
    avg_elapsed_seconds: float = 0.0
    scenarios_tested: list[str] = field(default_factory=list)
    repetitions: int = 0
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0


class TestRunner:
    """
    Automated test runner for OpenSRE investigations.
    
    Runs configured scenarios multiple times, captures results,
    and generates comprehensive reports.
    """
    
    def __init__(self, output_dir: str | None = None):
        self.orchestrator = Orchestrator()
        self.results: list[TestResult] = []
        self.output_dir = Path(output_dir) if output_dir else Path("test_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def run_scenario(
        self,
        scenario: TestScenario,
        namespace: str = "default",
        repetition: int = 1,
    ) -> TestResult:
        """
        Run a single scenario and capture results.
        
        Args:
            scenario: Test scenario configuration
            namespace: Kubernetes namespace to investigate
            repetition: Current repetition number
            
        Returns:
            TestResult with investigation outcome
        """
        start = datetime.now()
        error = None
        investigation: InvestigationResult | None = None
        
        try:
            investigation = await self.orchestrator.investigate(
                issue=scenario.issue,
                namespace=namespace,
                timeout=scenario.timeout_seconds,
                auto_execute_safe=False,  # Never auto-execute in tests
            )
        except Exception as e:
            error = str(e)
        
        elapsed = (datetime.now() - start).total_seconds()
        
        if investigation:
            result = TestResult(
                scenario=scenario.name,
                issue=scenario.issue,
                namespace=namespace,
                repetition=repetition,
                elapsed_seconds=elapsed,
                confidence=investigation.confidence,
                root_cause=investigation.root_cause,
                observations_count=len(investigation.observations),
                actions_count=len(investigation.actions),
                status=investigation.status,
                error=investigation.error,
                observations=[
                    {
                        "source": o.source,
                        "type": o.type,
                        "summary": o.summary,
                        "severity": o.severity,
                    }
                    for o in investigation.observations
                ],
                actions=[
                    {
                        "id": a.id,
                        "description": a.description,
                        "risk": a.risk.value,
                    }
                    for a in investigation.actions
                ],
                expected_confidence_min=scenario.expected_confidence_min,
            )
        else:
            result = TestResult(
                scenario=scenario.name,
                issue=scenario.issue,
                namespace=namespace,
                repetition=repetition,
                elapsed_seconds=elapsed,
                confidence=0.0,
                root_cause="",
                observations_count=0,
                actions_count=0,
                status="error",
                error=error,
                expected_confidence_min=scenario.expected_confidence_min,
            )
        
        # Evaluate pass/fail
        result.passed = self._evaluate_result(result, scenario)
        
        return result
    
    def _evaluate_result(self, result: TestResult, scenario: TestScenario) -> bool:
        """Evaluate whether a test result passes expectations."""
        if result.status == "error" or result.status == "failed":
            return False
        
        # Check confidence threshold
        if result.confidence < scenario.expected_confidence_min:
            return False
        
        # Check for expected observations
        if scenario.expected_observations:
            observation_texts = " ".join(
                f"{o.get('source', '')} {o.get('summary', '')}"
                for o in result.observations
            ).lower()
            
            for expected in scenario.expected_observations:
                if expected.lower() not in observation_texts:
                    # Soft check - don't fail if confidence is high
                    if result.confidence < 0.8:
                        return False
        
        return True
    
    async def run_all(
        self,
        repetitions: int = 10,
        scenarios: list[str] | None = None,
        namespace: str = "default",
        parallel: bool = False,
    ) -> list[TestResult]:
        """
        Run all test scenarios multiple times.
        
        Args:
            repetitions: Number of times to run each scenario
            scenarios: Specific scenarios to run (None = all)
            namespace: Kubernetes namespace
            parallel: Run scenarios in parallel (experimental)
            
        Returns:
            List of all test results
        """
        # Filter scenarios if specified
        test_scenarios = [
            s for s in SCENARIOS.values()
            if scenarios is None or s.name in scenarios
        ]
        
        if not test_scenarios:
            print("No scenarios to run!")
            return []
        
        print(f"\n{'='*60}")
        print(f"OpenSRE Integration Test Suite")
        print(f"{'='*60}")
        print(f"Scenarios: {len(test_scenarios)}")
        print(f"Repetitions: {repetitions}")
        print(f"Total tests: {len(test_scenarios) * repetitions}")
        print(f"Namespace: {namespace}")
        print(f"{'='*60}\n")
        
        for rep in range(repetitions):
            print(f"\n=== Repetition {rep+1}/{repetitions} ===")
            
            if parallel:
                # Run scenarios in parallel
                tasks = [
                    self.run_scenario(scenario, namespace, rep + 1)
                    for scenario in test_scenarios
                ]
                rep_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for r in rep_results:
                    if isinstance(r, Exception):
                        print(f"  ERROR: {r}")
                    else:
                        self.results.append(r)
                        self._print_result(r)
            else:
                # Run scenarios sequentially
                for scenario in test_scenarios:
                    result = await self.run_scenario(scenario, namespace, rep + 1)
                    self.results.append(result)
                    self._print_result(result)
        
        return self.results
    
    def _print_result(self, result: TestResult):
        """Print a single result to console."""
        status_icon = "✓" if result.passed else "✗"
        status_color = "\033[92m" if result.passed else "\033[91m"
        reset = "\033[0m"
        
        print(
            f"  {status_color}{status_icon}{reset} {result.scenario}: "
            f"{result.confidence:.0%} confidence, "
            f"{result.elapsed_seconds:.1f}s, "
            f"{result.observations_count} obs, "
            f"{result.actions_count} actions"
        )
        
        if result.error:
            print(f"    └─ Error: {result.error}")
    
    def generate_report(self, filename: str = "test_results.json") -> Path:
        """Generate comprehensive JSON report."""
        # Calculate summary statistics
        summary = self._calculate_summary()
        
        report = {
            "summary": asdict(summary),
            "results": [r.to_dict() for r in self.results],
            "by_scenario": self._group_by_scenario(),
            "generated_at": datetime.now().isoformat(),
        }
        
        output_path = self.output_dir / filename
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        
        return output_path
    
    def _calculate_summary(self) -> TestSummary:
        """Calculate summary statistics from results."""
        if not self.results:
            return TestSummary()
        
        passed = sum(1 for r in self.results if r.passed)
        errors = sum(1 for r in self.results if r.status == "error")
        failed = len(self.results) - passed
        
        confidences = [r.confidence for r in self.results if r.status != "error"]
        elapsed_times = [r.elapsed_seconds for r in self.results]
        
        return TestSummary(
            total_tests=len(self.results),
            passed=passed,
            failed=failed,
            errors=errors,
            avg_confidence=sum(confidences) / len(confidences) if confidences else 0,
            avg_elapsed_seconds=sum(elapsed_times) / len(elapsed_times) if elapsed_times else 0,
            scenarios_tested=list(set(r.scenario for r in self.results)),
            repetitions=max(r.repetition for r in self.results) if self.results else 0,
        )
    
    def _group_by_scenario(self) -> dict[str, dict]:
        """Group results by scenario for analysis."""
        grouped = {}
        
        for result in self.results:
            if result.scenario not in grouped:
                grouped[result.scenario] = {
                    "runs": [],
                    "pass_rate": 0.0,
                    "avg_confidence": 0.0,
                    "avg_elapsed_seconds": 0.0,
                    "min_confidence": 1.0,
                    "max_confidence": 0.0,
                }
            
            grouped[result.scenario]["runs"].append({
                "repetition": result.repetition,
                "passed": result.passed,
                "confidence": result.confidence,
                "elapsed_seconds": result.elapsed_seconds,
            })
        
        # Calculate aggregates
        for scenario, data in grouped.items():
            runs = data["runs"]
            if runs:
                data["pass_rate"] = sum(1 for r in runs if r["passed"]) / len(runs)
                confidences = [r["confidence"] for r in runs]
                data["avg_confidence"] = sum(confidences) / len(confidences)
                data["min_confidence"] = min(confidences)
                data["max_confidence"] = max(confidences)
                elapsed_times = [r["elapsed_seconds"] for r in runs]
                data["avg_elapsed_seconds"] = sum(elapsed_times) / len(elapsed_times)
        
        return grouped
    
    def print_summary(self):
        """Print human-readable summary to console."""
        summary = self._calculate_summary()
        by_scenario = self._group_by_scenario()
        
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests:     {summary.total_tests}")
        print(f"Passed:          {summary.passed} ({summary.passed/summary.total_tests*100:.1f}%)")
        print(f"Failed:          {summary.failed}")
        print(f"Errors:          {summary.errors}")
        print(f"Avg Confidence:  {summary.avg_confidence:.1%}")
        print(f"Avg Duration:    {summary.avg_elapsed_seconds:.2f}s")
        
        print(f"\n{'='*60}")
        print("BY SCENARIO")
        print(f"{'='*60}")
        print(f"{'Scenario':<20} {'Pass Rate':>10} {'Avg Conf':>10} {'Avg Time':>10}")
        print("-" * 60)
        
        for scenario, data in sorted(by_scenario.items()):
            print(
                f"{scenario:<20} "
                f"{data['pass_rate']:>10.1%} "
                f"{data['avg_confidence']:>10.1%} "
                f"{data['avg_elapsed_seconds']:>9.1f}s"
            )
        
        print(f"{'='*60}\n")


async def main():
    """Main entry point for test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenSRE Integration Test Runner")
    parser.add_argument(
        "-r", "--repetitions",
        type=int,
        default=10,
        help="Number of repetitions per scenario (default: 10)"
    )
    parser.add_argument(
        "-s", "--scenarios",
        nargs="+",
        help="Specific scenarios to run (default: all)"
    )
    parser.add_argument(
        "-n", "--namespace",
        default="default",
        help="Kubernetes namespace (default: default)"
    )
    parser.add_argument(
        "-o", "--output",
        default="test_output",
        help="Output directory for reports (default: test_output)"
    )
    parser.add_argument(
        "-p", "--parallel",
        action="store_true",
        help="Run scenarios in parallel (experimental)"
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy test scenarios before running"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up test scenarios after running"
    )
    
    args = parser.parse_args()
    
    # Deploy scenarios if requested
    if args.deploy:
        import subprocess
        print("Deploying test scenarios...")
        script_path = Path(__file__).parent / "deploy_scenarios.sh"
        subprocess.run(["bash", str(script_path), "deploy", args.namespace], check=True)
    
    # Run tests
    runner = TestRunner(output_dir=args.output)
    
    start_time = datetime.now()
    
    await runner.run_all(
        repetitions=args.repetitions,
        scenarios=args.scenarios,
        namespace=args.namespace,
        parallel=args.parallel,
    )
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Generate report
    report_path = runner.generate_report()
    runner.print_summary()
    
    print(f"Report saved to: {report_path}")
    print(f"Total runtime: {elapsed:.1f}s")
    
    # Cleanup if requested
    if args.cleanup:
        import subprocess
        print("\nCleaning up test scenarios...")
        script_path = Path(__file__).parent / "deploy_scenarios.sh"
        subprocess.run(["bash", str(script_path), "cleanup", args.namespace], check=True)
    
    # Exit with appropriate code
    summary = runner._calculate_summary()
    sys.exit(0 if summary.failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
