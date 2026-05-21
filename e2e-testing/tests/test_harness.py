"""
AutoSRE E2E Test Harness

Provides utilities for running AutoSRE investigations and verifying results
against expected outcomes for end-to-end testing.
"""

import subprocess
import json
import time
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class InvestigationResult:
    """Structured result from an AutoSRE investigation."""
    success: bool
    root_cause: Optional[str] = None
    confidence: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    raw_output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExpectedResult:
    """Expected outcome for verification."""
    root_cause_keywords: List[str]
    evidence_types: List[str]  # e.g., ["metrics", "logs", "events"]
    min_confidence: float = 0.5
    expected_recommendations: List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Result of verifying investigation against expected outcome."""
    passed: bool
    root_cause_match: bool
    evidence_collected: bool
    confidence_sufficient: bool
    recommendations_match: bool
    details: Dict[str, Any] = field(default_factory=dict)


class AutoSRETestHarness:
    """
    Test harness for running AutoSRE investigations in E2E tests.
    
    Usage:
        harness = AutoSRETestHarness(config_path="autosre-config.yaml")
        result = harness.run_investigation("High error rate in bookstore-api")
        verification = harness.verify_detection(result, expected)
    """
    
    def __init__(
        self,
        config_path: str = "autosre-config.yaml",
        autosre_binary: str = "autosre",
        timeout_seconds: int = 300,
        working_dir: Optional[str] = None
    ):
        self.config_path = config_path
        self.autosre_binary = autosre_binary
        self.timeout_seconds = timeout_seconds
        self.working_dir = working_dir or os.getcwd()
        self.investigation_history: List[InvestigationResult] = []
        
    def run_investigation(
        self,
        alert_description: str,
        additional_args: Optional[List[str]] = None
    ) -> InvestigationResult:
        """
        Run AutoSRE investigation and return structured results.
        
        Args:
            alert_description: Description of the alert/issue to investigate
            additional_args: Additional command-line arguments
            
        Returns:
            InvestigationResult with parsed output
        """
        start_time = time.time()
        
        cmd = [
            self.autosre_binary,
            "investigate",
            "--config", self.config_path,
            "--alert", alert_description,
            "--output", "json"
        ]
        
        if additional_args:
            cmd.extend(additional_args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=self.working_dir
            )
            
            duration = time.time() - start_time
            
            if result.returncode != 0:
                return InvestigationResult(
                    success=False,
                    duration_seconds=duration,
                    error=f"AutoSRE exited with code {result.returncode}: {result.stderr}"
                )
            
            try:
                output = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                return InvestigationResult(
                    success=False,
                    duration_seconds=duration,
                    error=f"Failed to parse JSON output: {e}\nRaw: {result.stdout[:500]}"
                )
            
            investigation_result = self._parse_output(output, duration)
            self.investigation_history.append(investigation_result)
            return investigation_result
            
        except subprocess.TimeoutExpired:
            return InvestigationResult(
                success=False,
                duration_seconds=self.timeout_seconds,
                error=f"Investigation timed out after {self.timeout_seconds}s"
            )
        except FileNotFoundError:
            return InvestigationResult(
                success=False,
                error=f"AutoSRE binary not found: {self.autosre_binary}"
            )
        except Exception as e:
            return InvestigationResult(
                success=False,
                duration_seconds=time.time() - start_time,
                error=f"Unexpected error: {str(e)}"
            )
    
    def _parse_output(self, output: dict, duration: float) -> InvestigationResult:
        """Parse AutoSRE JSON output into structured result."""
        return InvestigationResult(
            success=output.get("status") == "completed",
            root_cause=output.get("root_cause", {}).get("description"),
            confidence=output.get("root_cause", {}).get("confidence", 0.0),
            evidence=output.get("evidence", []),
            recommendations=output.get("recommendations", []),
            duration_seconds=duration,
            raw_output=output
        )
    
    def verify_detection(
        self,
        result: InvestigationResult,
        expected: ExpectedResult
    ) -> VerificationResult:
        """
        Verify that AutoSRE correctly detected the expected issue.
        
        Args:
            result: Investigation result to verify
            expected: Expected outcome to compare against
            
        Returns:
            VerificationResult with detailed comparison
        """
        details: Dict[str, Any] = {}
        
        # Check root cause match
        root_cause_match = False
        if result.root_cause:
            root_cause_lower = result.root_cause.lower()
            matching_keywords = [
                kw for kw in expected.root_cause_keywords
                if kw.lower() in root_cause_lower
            ]
            root_cause_match = len(matching_keywords) > 0
            details["root_cause_keywords_matched"] = matching_keywords
            details["root_cause_keywords_expected"] = expected.root_cause_keywords
        details["root_cause_detected"] = result.root_cause
        
        # Check evidence collected
        evidence_types_found = set()
        for ev in result.evidence:
            ev_type = ev.get("type", ev.get("source", "unknown"))
            evidence_types_found.add(ev_type)
        
        evidence_collected = all(
            et in evidence_types_found
            for et in expected.evidence_types
        )
        details["evidence_types_found"] = list(evidence_types_found)
        details["evidence_types_expected"] = expected.evidence_types
        
        # Check confidence
        confidence_sufficient = result.confidence >= expected.min_confidence
        details["confidence_actual"] = result.confidence
        details["confidence_expected"] = expected.min_confidence
        
        # Check recommendations (partial match)
        recommendations_match = True
        if expected.expected_recommendations:
            result_recs_lower = [r.lower() for r in result.recommendations]
            for expected_rec in expected.expected_recommendations:
                found = any(
                    expected_rec.lower() in rec
                    for rec in result_recs_lower
                )
                if not found:
                    recommendations_match = False
                    break
        details["recommendations_actual"] = result.recommendations
        details["recommendations_expected"] = expected.expected_recommendations
        
        # Overall pass/fail
        passed = all([
            result.success,
            root_cause_match,
            evidence_collected,
            confidence_sufficient
        ])
        
        return VerificationResult(
            passed=passed,
            root_cause_match=root_cause_match,
            evidence_collected=evidence_collected,
            confidence_sufficient=confidence_sufficient,
            recommendations_match=recommendations_match,
            details=details
        )
    
    def wait_for_metrics(self, seconds: int = 30) -> None:
        """Wait for metrics to propagate after chaos injection."""
        print(f"Waiting {seconds}s for metrics to propagate...")
        time.sleep(seconds)
    
    def run_chaos_scenario(
        self,
        scenario_script: str,
        wait_seconds: int = 30
    ) -> bool:
        """
        Run a chaos scenario script and wait for metrics.
        
        Args:
            scenario_script: Path to the chaos scenario script
            wait_seconds: Seconds to wait after injection
            
        Returns:
            True if scenario executed successfully
        """
        try:
            result = subprocess.run(
                ["bash", scenario_script],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.working_dir
            )
            
            if result.returncode != 0:
                print(f"Chaos scenario failed: {result.stderr}")
                return False
            
            self.wait_for_metrics(wait_seconds)
            return True
            
        except Exception as e:
            print(f"Error running chaos scenario: {e}")
            return False
    
    def reset_chaos(self, reset_script: str = "chaos/reset-all.sh") -> bool:
        """Reset all chaos experiments."""
        try:
            result = subprocess.run(
                ["bash", reset_script],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.working_dir
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error resetting chaos: {e}")
            return False
    
    def get_investigation_stats(self) -> Dict[str, Any]:
        """Get statistics from all investigations run in this session."""
        if not self.investigation_history:
            return {"count": 0}
        
        successful = [r for r in self.investigation_history if r.success]
        durations = [r.duration_seconds for r in self.investigation_history]
        confidences = [r.confidence for r in successful if r.confidence > 0]
        
        return {
            "count": len(self.investigation_history),
            "successful": len(successful),
            "failed": len(self.investigation_history) - len(successful),
            "avg_duration_seconds": sum(durations) / len(durations),
            "max_duration_seconds": max(durations),
            "min_duration_seconds": min(durations),
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
        }


# Convenience functions for quick testing
def quick_investigate(alert: str, config: str = "autosre-config.yaml") -> dict:
    """Quick investigation for ad-hoc testing."""
    harness = AutoSRETestHarness(config_path=config)
    result = harness.run_investigation(alert)
    return result.to_dict()


if __name__ == "__main__":
    # Example usage
    harness = AutoSRETestHarness()
    
    # Run a test investigation
    result = harness.run_investigation("High error rate detected in bookstore-api")
    print(f"Investigation completed: {result.success}")
    print(f"Root cause: {result.root_cause}")
    print(f"Confidence: {result.confidence}")
    
    # Verify against expected
    expected = ExpectedResult(
        root_cause_keywords=["error", "5xx", "failure"],
        evidence_types=["metrics", "logs"],
        min_confidence=0.7
    )
    verification = harness.verify_detection(result, expected)
    print(f"Verification passed: {verification.passed}")
