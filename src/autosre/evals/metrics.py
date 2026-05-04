"""
Evaluation Metrics - Track and compare agent performance.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class EvalMetrics:
    """Metrics for a single evaluation run."""
    time_to_detection: Optional[float] = None  # Seconds to detect issue
    time_to_root_cause: Optional[float] = None  # Seconds to identify root cause
    time_to_resolution: Optional[float] = None  # Seconds to suggest resolution
    
    root_cause_accuracy: float = 0.0  # 0-1 score for root cause identification
    runbook_accuracy: float = 0.0  # 0-1 score for runbook selection
    action_accuracy: float = 0.0  # 0-1 score for suggested action
    
    false_positives: int = 0  # Number of incorrect diagnoses
    false_negatives: int = 0  # Number of missed issues
    
    human_override_rate: float = 0.0  # How often humans override the agent
    
    @property
    def overall_accuracy(self) -> float:
        """Calculate overall accuracy."""
        return (self.root_cause_accuracy + self.runbook_accuracy + self.action_accuracy) / 3
    
    @property
    def precision(self) -> float:
        """Calculate precision (of root cause identification)."""
        tp = self.root_cause_accuracy  # Simplified
        fp = self.false_positives
        if tp + fp == 0:
            return 0.0
        return tp / (tp + fp)
    
    @property
    def recall(self) -> float:
        """Calculate recall (of root cause identification)."""
        tp = self.root_cause_accuracy  # Simplified
        fn = self.false_negatives
        if tp + fn == 0:
            return 0.0
        return tp / (tp + fn)
    
    @property
    def f1_score(self) -> float:
        """Calculate F1 score."""
        p = self.precision
        r = self.recall
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)


def calculate_metrics(
    expected: dict,
    actual: dict,
    timing: dict,
) -> EvalMetrics:
    """
    Calculate metrics by comparing expected vs actual results.
    
    Args:
        expected: Expected outcomes (root_cause, service, runbook, action)
        actual: Actual agent outputs
        timing: Timing information (detection_time, root_cause_time, resolution_time)
        
    Returns:
        EvalMetrics object
    """
    metrics = EvalMetrics()
    
    # Timing metrics
    metrics.time_to_detection = timing.get("detection_time")
    metrics.time_to_root_cause = timing.get("root_cause_time")
    metrics.time_to_resolution = timing.get("resolution_time")
    
    # Root cause accuracy
    expected_rc = expected.get("root_cause", "").lower()
    actual_rc = actual.get("root_cause", "").lower()
    
    if expected_rc and actual_rc:
        # Simple string matching - could be improved with semantic similarity
        if expected_rc == actual_rc:
            metrics.root_cause_accuracy = 1.0
        elif expected_rc in actual_rc or actual_rc in expected_rc:
            metrics.root_cause_accuracy = 0.7
        else:
            metrics.root_cause_accuracy = 0.0
    
    # Runbook accuracy
    expected_rb = expected.get("runbook", "").lower()
    actual_rb = actual.get("runbook", "").lower()
    
    if expected_rb and actual_rb:
        if expected_rb == actual_rb:
            metrics.runbook_accuracy = 1.0
        elif expected_rb in actual_rb:
            metrics.runbook_accuracy = 0.5
    
    # Action accuracy
    expected_action = expected.get("action", "").lower()
    actual_action = actual.get("action", "").lower()
    
    if expected_action and actual_action:
        if expected_action == actual_action:
            metrics.action_accuracy = 1.0
        elif expected_action in actual_action:
            metrics.action_accuracy = 0.5
    
    return metrics


def compare_metrics(baseline: EvalMetrics, current: EvalMetrics) -> dict:
    """
    Compare current metrics against a baseline.
    
    Returns:
        Dict with comparison results (deltas, improvement flags)
    """
    return {
        "time_to_root_cause_delta": (
            (current.time_to_root_cause or 0) - (baseline.time_to_root_cause or 0)
        ),
        "accuracy_delta": current.overall_accuracy - baseline.overall_accuracy,
        "f1_delta": current.f1_score - baseline.f1_score,
        "improved": current.overall_accuracy > baseline.overall_accuracy,
        "faster": (
            (current.time_to_root_cause or float("inf")) <
            (baseline.time_to_root_cause or float("inf"))
        ),
    }
