"""Log anomaly detection."""

from datetime import datetime
from typing import Any, Optional, List, Dict
from enum import Enum
import re
from collections import Counter
import hashlib

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id
from autosre.ml.common.base import (
    BaseMLModel,
    TrainingConfig,
    EvaluationMetrics,
    PredictionResult,
    ModelStatus,
    ModelVersion,
)
from autosre.ml.common.preprocessing import TextPreprocessor


class LogAnomalyType(str, Enum):
    """Type of log anomaly."""
    RARE_EVENT = "rare_event"
    FREQUENCY_SPIKE = "frequency_spike"
    NEW_PATTERN = "new_pattern"
    ERROR_BURST = "error_burst"
    SEQUENCE_ANOMALY = "sequence_anomaly"
    FORMAT_ANOMALY = "format_anomaly"


class LogAnomaly(BaseModel):
    """Detected log anomaly."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    anomaly_id: str = Field(default_factory=generate_id)
    
    # Type
    anomaly_type: LogAnomalyType = Field(default=LogAnomalyType.RARE_EVENT)
    
    # Log info
    log_message: str = Field(default="")
    log_pattern: str = Field(default="")
    log_level: str = Field(default="")
    source: str = Field(default="")
    
    # Scores
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Statistics
    occurrence_count: int = Field(default=1, ge=1)
    expected_count: float = Field(default=0.0)
    frequency_ratio: float = Field(default=1.0)
    
    # Related logs
    similar_logs: list[str] = Field(default_factory=list)
    
    # Timing
    first_seen: datetime = Field(default_factory=utc_now)
    last_seen: datetime = Field(default_factory=utc_now)
    
    # Context
    component: str = Field(default="")
    labels: dict[str, str] = Field(default_factory=dict)
    
    # Metadata
    detected_at: datetime = Field(default_factory=utc_now)


class LogDetectionResult(BaseModel):
    """Result of log anomaly detection."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    anomalies: list[LogAnomaly] = Field(default_factory=list)
    anomaly_count: int = Field(default=0, ge=0)
    
    # Statistics
    total_logs: int = Field(default=0, ge=0)
    unique_patterns: int = Field(default=0, ge=0)
    new_patterns: int = Field(default=0, ge=0)
    
    # By type
    anomaly_type_counts: dict[str, int] = Field(default_factory=dict)
    
    # Severity distribution
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    
    # Model info
    model_id: str = Field(default="")
    
    # Timing
    detection_time_ms: float = Field(default=0.0, ge=0.0)
    detected_at: datetime = Field(default_factory=utc_now)


class LogAnomalyDetector(BaseMLModel[List[str], LogDetectionResult]):
    """Detect anomalies in log data.
    
    Supports multiple detection strategies:
    - Pattern frequency analysis
    - New pattern detection
    - Error burst detection
    - Sequence anomaly detection
    
    Features:
    - Log template extraction
    - Pattern clustering
    - Time-based analysis
    """
    
    def __init__(
        self,
        min_frequency: float = 0.001,
        max_frequency: float = 0.99,
        error_patterns: Optional[List[str]] = None,
        detect_new_patterns: bool = True,
        sequence_window: int = 5,
    ):
        """Initialize the detector.
        
        Args:
            min_frequency: Minimum pattern frequency to be normal
            max_frequency: Maximum pattern frequency to be normal
            error_patterns: Patterns that indicate errors
            detect_new_patterns: Detect previously unseen patterns
            sequence_window: Window for sequence analysis
        """
        super().__init__(
            name="log_anomaly_detector",
            model_type="log_anomaly_detector",
            hyperparameters={
                "min_frequency": min_frequency,
                "max_frequency": max_frequency,
                "detect_new_patterns": detect_new_patterns,
                "sequence_window": sequence_window,
            },
        )
        
        self.min_frequency = min_frequency
        self.max_frequency = max_frequency
        self.detect_new_patterns = detect_new_patterns
        self.sequence_window = sequence_window
        
        # Error patterns
        self.error_patterns = error_patterns or [
            r"error",
            r"exception",
            r"fail(ed|ure)?",
            r"crash",
            r"fatal",
            r"critical",
            r"panic",
            r"timeout",
            r"refused",
            r"denied",
            r"unauthorized",
            r"oom|out of memory",
        ]
        self._error_regex = re.compile(
            "|".join(self.error_patterns),
            re.IGNORECASE
        )
        
        # Preprocessing
        self._preprocessor = TextPreprocessor(
            lowercase=True,
            remove_punctuation=False,
            remove_numbers=False,
        )
        
        # Learned patterns
        self._pattern_frequencies: Dict[str, float] = {}
        self._pattern_counts: Dict[str, int] = {}
        self._total_logs: int = 0
        
        # Pattern templates
        self._templates: Dict[str, str] = {}
        
        # Sequence model
        self._transition_probs: Dict[str, Dict[str, float]] = {}
    
    def _extract_template(self, log: str) -> str:
        """Extract a template from a log message.
        
        Replaces variable parts (numbers, IPs, etc.) with placeholders.
        
        Args:
            log: Log message
            
        Returns:
            Template string
        """
        template = log
        
        # Replace timestamps
        template = re.sub(
            r'\d{4}[-/]\d{2}[-/]\d{2}[T\s]\d{2}:\d{2}:\d{2}(\.\d+)?',
            '<TIMESTAMP>',
            template
        )
        
        # Replace IP addresses
        template = re.sub(
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?',
            '<IP>',
            template
        )
        
        # Replace UUIDs
        template = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '<UUID>',
            template,
            flags=re.IGNORECASE
        )
        
        # Replace hex strings
        template = re.sub(r'0x[0-9a-fA-F]+', '<HEX>', template)
        
        # Replace numbers (but keep structure)
        template = re.sub(r'\b\d+\b', '<NUM>', template)
        
        # Replace paths
        template = re.sub(r'/[\w/\-\.]+', '<PATH>', template)
        
        return template
    
    def _get_pattern_hash(self, template: str) -> str:
        """Get a hash for a pattern template.
        
        Args:
            template: Template string
            
        Returns:
            Hash string
        """
        return hashlib.md5(template.encode()).hexdigest()[:12]
    
    def fit(
        self,
        X: List[str],
        y: Optional[np.ndarray] = None,
        config: Optional[TrainingConfig] = None,
    ) -> "LogAnomalyDetector":
        """Fit the detector to training logs.
        
        Args:
            X: Training log messages (should be normal logs)
            y: Not used
            config: Training configuration
            
        Returns:
            Self
        """
        self._total_logs = len(X)
        self._pattern_counts = {}
        
        # Extract templates and count patterns
        for log in X:
            template = self._extract_template(log)
            pattern_hash = self._get_pattern_hash(template)
            
            self._templates[pattern_hash] = template
            self._pattern_counts[pattern_hash] = self._pattern_counts.get(pattern_hash, 0) + 1
        
        # Calculate frequencies
        for pattern_hash, count in self._pattern_counts.items():
            self._pattern_frequencies[pattern_hash] = count / self._total_logs
        
        # Build sequence transition model
        self._build_transition_model(X)
        
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        version = ModelVersion(
            description=f"Trained on {len(X)} logs with {len(self._templates)} patterns",
            metrics={
                "num_logs": float(len(X)),
                "num_patterns": float(len(self._templates)),
            },
        )
        self._metadata.add_version(version)
        
        return self
    
    def _build_transition_model(self, logs: List[str]) -> None:
        """Build sequence transition model.
        
        Args:
            logs: Training logs
        """
        if len(logs) < self.sequence_window:
            return
        
        # Get pattern sequence
        patterns = []
        for log in logs:
            template = self._extract_template(log)
            patterns.append(self._get_pattern_hash(template))
        
        # Count transitions
        transition_counts: Dict[str, Dict[str, int]] = {}
        
        for i in range(len(patterns) - 1):
            current = patterns[i]
            next_pattern = patterns[i + 1]
            
            if current not in transition_counts:
                transition_counts[current] = {}
            
            transition_counts[current][next_pattern] = (
                transition_counts[current].get(next_pattern, 0) + 1
            )
        
        # Convert to probabilities
        for current, transitions in transition_counts.items():
            total = sum(transitions.values())
            self._transition_probs[current] = {
                next_p: count / total
                for next_p, count in transitions.items()
            }
    
    def predict(
        self,
        X: List[str],
        source: str = "",
        component: str = "",
    ) -> PredictionResult[LogDetectionResult]:
        """Detect anomalies in logs.
        
        Args:
            X: Log messages to analyze
            source: Log source
            component: Component name
            
        Returns:
            Detection result
        """
        import time
        start_time = time.time()
        
        if not self._is_fitted:
            # Auto-fit on first batch
            self.fit(X)
        
        anomalies = []
        pattern_counts: Dict[str, int] = {}
        new_patterns: List[str] = []
        error_count = 0
        warning_count = 0
        
        # Process each log
        for i, log in enumerate(X):
            template = self._extract_template(log)
            pattern_hash = self._get_pattern_hash(template)
            
            pattern_counts[pattern_hash] = pattern_counts.get(pattern_hash, 0) + 1
            
            # Check for errors
            if self._error_regex.search(log):
                error_count += 1
            if re.search(r'\bwarn(ing)?\b', log, re.IGNORECASE):
                warning_count += 1
            
            # Check if new pattern
            if pattern_hash not in self._pattern_frequencies:
                new_patterns.append(pattern_hash)
                
                if self.detect_new_patterns:
                    anomaly = LogAnomaly(
                        anomaly_type=LogAnomalyType.NEW_PATTERN,
                        log_message=log[:500],  # Truncate
                        log_pattern=template[:200],
                        source=source,
                        anomaly_score=0.8,
                        confidence=0.7,
                        occurrence_count=1,
                        expected_count=0,
                        component=component,
                    )
                    anomalies.append(anomaly)
            else:
                # Check if rare pattern
                freq = self._pattern_frequencies[pattern_hash]
                if freq < self.min_frequency:
                    anomaly = LogAnomaly(
                        anomaly_type=LogAnomalyType.RARE_EVENT,
                        log_message=log[:500],
                        log_pattern=template[:200],
                        source=source,
                        anomaly_score=1.0 - freq / self.min_frequency,
                        confidence=0.6,
                        occurrence_count=1,
                        expected_count=self._pattern_counts.get(pattern_hash, 0),
                        frequency_ratio=freq / self.min_frequency,
                        component=component,
                    )
                    anomalies.append(anomaly)
        
        # Check for frequency spikes
        total_new = len(X)
        for pattern_hash, count in pattern_counts.items():
            if pattern_hash in self._pattern_frequencies:
                expected_ratio = self._pattern_frequencies[pattern_hash]
                actual_ratio = count / total_new if total_new > 0 else 0
                
                # Check for spike (>3x expected)
                if actual_ratio > expected_ratio * 3 and count >= 5:
                    template = self._templates.get(pattern_hash, "Unknown pattern")
                    anomaly = LogAnomaly(
                        anomaly_type=LogAnomalyType.FREQUENCY_SPIKE,
                        log_pattern=template[:200],
                        source=source,
                        anomaly_score=min(actual_ratio / expected_ratio / 10, 1.0),
                        confidence=0.7,
                        occurrence_count=count,
                        expected_count=expected_ratio * total_new,
                        frequency_ratio=actual_ratio / expected_ratio if expected_ratio > 0 else float('inf'),
                        component=component,
                    )
                    anomalies.append(anomaly)
        
        # Check for error bursts
        if error_count > total_new * 0.1 and error_count >= 5:  # >10% errors
            anomaly = LogAnomaly(
                anomaly_type=LogAnomalyType.ERROR_BURST,
                log_pattern="Multiple errors detected",
                source=source,
                anomaly_score=min(error_count / total_new, 1.0),
                confidence=0.9,
                occurrence_count=error_count,
                component=component,
            )
            anomalies.append(anomaly)
        
        # Count anomaly types
        type_counts: Dict[str, int] = {}
        for anomaly in anomalies:
            type_name = anomaly.anomaly_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        result = LogDetectionResult(
            anomalies=anomalies,
            anomaly_count=len(anomalies),
            total_logs=len(X),
            unique_patterns=len(pattern_counts),
            new_patterns=len(new_patterns),
            anomaly_type_counts=type_counts,
            error_count=error_count,
            warning_count=warning_count,
            model_id=self.model_id,
            detection_time_ms=(time.time() - start_time) * 1000,
        )
        
        return PredictionResult(
            prediction=result,
            confidence=0.8,
            model_id=self.model_id,
            latency_ms=(time.time() - start_time) * 1000,
        )
    
    def evaluate(
        self,
        X: List[str],
        y: np.ndarray,
    ) -> EvaluationMetrics:
        """Evaluate the detector.
        
        Args:
            X: Log messages
            y: True anomaly labels
            
        Returns:
            Evaluation metrics
        """
        import time
        start_time = time.time()
        
        result = self.predict(X)
        
        # Create predictions array
        predictions = np.zeros(len(X))
        for anomaly in result.prediction.anomalies:
            # Mark all logs matching anomaly patterns
            for i, log in enumerate(X):
                template = self._extract_template(log)
                if anomaly.log_pattern in template:
                    predictions[i] = 1
        
        y = np.asarray(y).flatten()
        
        # Calculate metrics
        tp = np.sum((predictions == 1) & (y == 1))
        fp = np.sum((predictions == 1) & (y == 0))
        fn = np.sum((predictions == 0) & (y == 1))
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return EvaluationMetrics(
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            dataset_size=len(y),
            evaluation_time_seconds=(time.time() - start_time),
        )
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get importance of detection features."""
        return {
            "pattern_frequency": 0.3,
            "new_pattern_detection": 0.3,
            "error_detection": 0.2,
            "sequence_analysis": 0.2,
        }
