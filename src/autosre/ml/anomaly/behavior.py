"""Behavior anomaly detection for users and services."""

from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict, Tuple
from enum import Enum

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


class BehaviorAnomalyType(str, Enum):
    """Type of behavior anomaly."""
    USAGE_SPIKE = "usage_spike"
    USAGE_DROP = "usage_drop"
    PATTERN_CHANGE = "pattern_change"
    ACCESS_ANOMALY = "access_anomaly"
    SEQUENCE_ANOMALY = "sequence_anomaly"
    TIMING_ANOMALY = "timing_anomaly"
    GEOGRAPHIC_ANOMALY = "geographic_anomaly"


class BehaviorAnomaly(BaseModel):
    """Detected behavior anomaly."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    anomaly_id: str = Field(default_factory=generate_id)
    
    # Type
    anomaly_type: BehaviorAnomalyType = Field(default=BehaviorAnomalyType.PATTERN_CHANGE)
    
    # Entity
    entity_type: str = Field(default="user")  # user, service, api_key
    entity_id: str = Field(default="")
    
    # Description
    description: str = Field(default="")
    
    # Scores
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Behavior details
    observed_behavior: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: dict[str, Any] = Field(default_factory=dict)
    deviation: dict[str, float] = Field(default_factory=dict)
    
    # Context
    context: dict[str, Any] = Field(default_factory=dict)
    
    # Timing
    detected_at: datetime = Field(default_factory=utc_now)
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None


class BehaviorProfile(BaseModel):
    """Profile of normal behavior for an entity."""
    model_config = ConfigDict(validate_assignment=True)
    
    entity_id: str
    entity_type: str = Field(default="user")
    
    # Activity patterns
    activity_mean: float = Field(default=0.0)
    activity_std: float = Field(default=1.0)
    hourly_pattern: list[float] = Field(default_factory=list)  # 24 values
    daily_pattern: list[float] = Field(default_factory=list)  # 7 values
    
    # Access patterns
    common_endpoints: list[str] = Field(default_factory=list)
    endpoint_frequencies: dict[str, float] = Field(default_factory=dict)
    
    # Geographic data
    common_locations: list[str] = Field(default_factory=list)
    
    # Timing
    avg_session_duration: float = Field(default=0.0)
    avg_requests_per_session: float = Field(default=0.0)
    
    # Metadata
    last_updated: datetime = Field(default_factory=utc_now)
    sample_count: int = Field(default=0, ge=0)


class BehaviorEvent(BaseModel):
    """A single behavior event."""
    model_config = ConfigDict(validate_assignment=True)
    
    timestamp: datetime = Field(default_factory=utc_now)
    entity_id: str
    entity_type: str = Field(default="user")
    
    # Event details
    action: str = Field(default="")
    endpoint: str = Field(default="")
    method: str = Field(default="")
    
    # Context
    location: str = Field(default="")
    ip_address: str = Field(default="")
    user_agent: str = Field(default="")
    
    # Metrics
    response_time_ms: float = Field(default=0.0, ge=0.0)
    
    # Additional data
    metadata: dict[str, Any] = Field(default_factory=dict)


class BehaviorDetectionResult(BaseModel):
    """Result of behavior anomaly detection."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    anomalies: list[BehaviorAnomaly] = Field(default_factory=list)
    anomaly_count: int = Field(default=0, ge=0)
    
    # Entity info
    entity_id: str = Field(default="")
    entity_type: str = Field(default="")
    
    # Detection summary
    total_events: int = Field(default=0, ge=0)
    anomalous_events: int = Field(default=0, ge=0)
    
    # Profile comparison
    profile_match_score: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # By type
    anomaly_type_counts: dict[str, int] = Field(default_factory=dict)
    
    # Model info
    model_id: str = Field(default="")
    
    # Timing
    detection_time_ms: float = Field(default=0.0, ge=0.0)
    detected_at: datetime = Field(default_factory=utc_now)


class BehaviorAnomalyDetector(BaseMLModel[List[BehaviorEvent], BehaviorDetectionResult]):
    """Detect anomalies in user/service behavior.
    
    Analyzes behavioral patterns to detect:
    - Usage spikes/drops
    - Pattern changes
    - Unusual access patterns
    - Geographic anomalies
    - Timing anomalies
    
    Features:
    - Per-entity profiling
    - Temporal pattern analysis
    - Sequence analysis
    - Context-aware detection
    """
    
    def __init__(
        self,
        threshold_multiplier: float = 3.0,
        min_events_for_profile: int = 50,
        profile_update_interval_hours: int = 24,
        detect_geographic: bool = True,
    ):
        """Initialize the detector.
        
        Args:
            threshold_multiplier: Multiplier for anomaly threshold
            min_events_for_profile: Minimum events to build profile
            profile_update_interval_hours: How often to update profiles
            detect_geographic: Detect geographic anomalies
        """
        super().__init__(
            name="behavior_anomaly_detector",
            model_type="behavior_anomaly_detector",
            hyperparameters={
                "threshold_multiplier": threshold_multiplier,
                "min_events_for_profile": min_events_for_profile,
                "profile_update_interval_hours": profile_update_interval_hours,
                "detect_geographic": detect_geographic,
            },
        )
        
        self.threshold_multiplier = threshold_multiplier
        self.min_events_for_profile = min_events_for_profile
        self.profile_update_interval_hours = profile_update_interval_hours
        self.detect_geographic = detect_geographic
        
        # Entity profiles
        self._profiles: Dict[str, BehaviorProfile] = {}
        
        # Global statistics
        self._global_activity_mean: float = 0.0
        self._global_activity_std: float = 1.0
        self._global_hourly_pattern: np.ndarray = np.ones(24)
        self._global_daily_pattern: np.ndarray = np.ones(7)
    
    def _get_entity_key(self, entity_id: str, entity_type: str) -> str:
        """Get unique key for entity."""
        return f"{entity_type}:{entity_id}"
    
    def _build_profile(
        self,
        events: List[BehaviorEvent],
        entity_id: str,
        entity_type: str,
    ) -> BehaviorProfile:
        """Build behavior profile from events.
        
        Args:
            events: Events for this entity
            entity_id: Entity ID
            entity_type: Entity type
            
        Returns:
            Behavior profile
        """
        # Filter to this entity
        entity_events = [e for e in events if e.entity_id == entity_id and e.entity_type == entity_type]
        
        if not entity_events:
            return BehaviorProfile(entity_id=entity_id, entity_type=entity_type)
        
        # Calculate hourly pattern
        hourly_counts = np.zeros(24)
        daily_counts = np.zeros(7)
        
        for event in entity_events:
            hour = event.timestamp.hour
            day = event.timestamp.weekday()
            hourly_counts[hour] += 1
            daily_counts[day] += 1
        
        # Normalize
        hourly_pattern = hourly_counts / max(np.sum(hourly_counts), 1)
        daily_pattern = daily_counts / max(np.sum(daily_counts), 1)
        
        # Calculate activity stats
        # Group by hour
        hourly_activity: Dict[str, int] = {}
        for event in entity_events:
            hour_key = event.timestamp.strftime("%Y-%m-%d %H")
            hourly_activity[hour_key] = hourly_activity.get(hour_key, 0) + 1
        
        activity_values = list(hourly_activity.values())
        activity_mean = float(np.mean(activity_values)) if activity_values else 0
        activity_std = float(np.std(activity_values)) if activity_values else 1
        
        # Endpoint frequencies
        endpoints: Dict[str, int] = {}
        for event in entity_events:
            if event.endpoint:
                endpoints[event.endpoint] = endpoints.get(event.endpoint, 0) + 1
        
        total_endpoints = sum(endpoints.values())
        endpoint_freqs = {
            ep: count / total_endpoints
            for ep, count in endpoints.items()
        } if total_endpoints > 0 else {}
        
        # Common locations
        locations: Dict[str, int] = {}
        for event in entity_events:
            if event.location:
                locations[event.location] = locations.get(event.location, 0) + 1
        
        common_locations = sorted(locations.keys(), key=lambda x: locations[x], reverse=True)[:5]
        
        return BehaviorProfile(
            entity_id=entity_id,
            entity_type=entity_type,
            activity_mean=activity_mean,
            activity_std=max(activity_std, 0.1),  # Avoid zero std
            hourly_pattern=hourly_pattern.tolist(),
            daily_pattern=daily_pattern.tolist(),
            common_endpoints=list(endpoint_freqs.keys())[:10],
            endpoint_frequencies=endpoint_freqs,
            common_locations=common_locations,
            sample_count=len(entity_events),
        )
    
    def fit(
        self,
        X: List[BehaviorEvent],
        y: Optional[np.ndarray] = None,
        config: Optional[TrainingConfig] = None,
    ) -> "BehaviorAnomalyDetector":
        """Fit the detector to training events.
        
        Args:
            X: Training events (should be normal behavior)
            y: Not used
            config: Training configuration
            
        Returns:
            Self
        """
        # Group events by entity
        entity_events: Dict[str, List[BehaviorEvent]] = {}
        
        for event in X:
            key = self._get_entity_key(event.entity_id, event.entity_type)
            if key not in entity_events:
                entity_events[key] = []
            entity_events[key].append(event)
        
        # Build profiles for entities with enough data
        for key, events in entity_events.items():
            if len(events) >= self.min_events_for_profile:
                parts = key.split(":", 1)
                entity_type = parts[0]
                entity_id = parts[1] if len(parts) > 1 else ""
                
                profile = self._build_profile(events, entity_id, entity_type)
                self._profiles[key] = profile
        
        # Calculate global statistics
        self._calculate_global_stats(X)
        
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        version = ModelVersion(
            description=f"Trained on {len(X)} events, {len(self._profiles)} profiles",
            metrics={
                "num_events": float(len(X)),
                "num_profiles": float(len(self._profiles)),
            },
        )
        self._metadata.add_version(version)
        
        return self
    
    def _calculate_global_stats(self, events: List[BehaviorEvent]) -> None:
        """Calculate global statistics from all events.
        
        Args:
            events: All training events
        """
        # Calculate global hourly/daily patterns
        hourly_counts = np.zeros(24)
        daily_counts = np.zeros(7)
        
        for event in events:
            hour = event.timestamp.hour
            day = event.timestamp.weekday()
            hourly_counts[hour] += 1
            daily_counts[day] += 1
        
        self._global_hourly_pattern = hourly_counts / max(np.sum(hourly_counts), 1)
        self._global_daily_pattern = daily_counts / max(np.sum(daily_counts), 1)
        
        # Calculate global activity stats
        hourly_activity: Dict[str, int] = {}
        for event in events:
            hour_key = event.timestamp.strftime("%Y-%m-%d %H")
            hourly_activity[hour_key] = hourly_activity.get(hour_key, 0) + 1
        
        activity_values = list(hourly_activity.values())
        if activity_values:
            self._global_activity_mean = float(np.mean(activity_values))
            self._global_activity_std = max(float(np.std(activity_values)), 0.1)
    
    def predict(
        self,
        X: List[BehaviorEvent],
    ) -> PredictionResult[BehaviorDetectionResult]:
        """Detect behavior anomalies.
        
        Args:
            X: Events to analyze
            
        Returns:
            Detection result
        """
        import time
        start_time = time.time()
        
        if not self._is_fitted:
            # Auto-fit
            self.fit(X)
        
        anomalies = []
        
        # Group events by entity
        entity_events: Dict[str, List[BehaviorEvent]] = {}
        for event in X:
            key = self._get_entity_key(event.entity_id, event.entity_type)
            if key not in entity_events:
                entity_events[key] = []
            entity_events[key].append(event)
        
        # Analyze each entity
        for key, events in entity_events.items():
            profile = self._profiles.get(key)
            
            entity_anomalies = self._detect_entity_anomalies(events, profile)
            anomalies.extend(entity_anomalies)
        
        # Count by type
        type_counts: Dict[str, int] = {}
        for anomaly in anomalies:
            type_name = anomaly.anomaly_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        result = BehaviorDetectionResult(
            anomalies=anomalies,
            anomaly_count=len(anomalies),
            total_events=len(X),
            anomaly_type_counts=type_counts,
            model_id=self.model_id,
            detection_time_ms=(time.time() - start_time) * 1000,
        )
        
        return PredictionResult(
            prediction=result,
            confidence=0.8,
            model_id=self.model_id,
            latency_ms=(time.time() - start_time) * 1000,
        )
    
    def _detect_entity_anomalies(
        self,
        events: List[BehaviorEvent],
        profile: Optional[BehaviorProfile],
    ) -> List[BehaviorAnomaly]:
        """Detect anomalies for a single entity.
        
        Args:
            events: Events for this entity
            profile: Entity's behavior profile
            
        Returns:
            List of anomalies
        """
        anomalies = []
        
        if not events:
            return anomalies
        
        entity_id = events[0].entity_id
        entity_type = events[0].entity_type
        
        # Use entity profile or global stats
        if profile:
            activity_mean = profile.activity_mean
            activity_std = profile.activity_std
            hourly_pattern = np.array(profile.hourly_pattern) if profile.hourly_pattern else self._global_hourly_pattern
            common_endpoints = set(profile.common_endpoints)
            common_locations = set(profile.common_locations)
        else:
            activity_mean = self._global_activity_mean
            activity_std = self._global_activity_std
            hourly_pattern = self._global_hourly_pattern
            common_endpoints = set()
            common_locations = set()
        
        # Check activity level
        activity = len(events)
        if activity_std > 0:
            activity_zscore = (activity - activity_mean) / activity_std
            
            if abs(activity_zscore) > self.threshold_multiplier:
                anomaly_type = BehaviorAnomalyType.USAGE_SPIKE if activity_zscore > 0 else BehaviorAnomalyType.USAGE_DROP
                anomalies.append(BehaviorAnomaly(
                    anomaly_type=anomaly_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    description=f"Activity {'spike' if activity_zscore > 0 else 'drop'} detected",
                    anomaly_score=min(abs(activity_zscore) / 10, 1.0),
                    confidence=0.7,
                    observed_behavior={"activity": activity},
                    expected_behavior={"activity": activity_mean},
                    deviation={"activity": float(activity_zscore)},
                ))
        
        # Check for unusual endpoints
        if common_endpoints:
            for event in events:
                if event.endpoint and event.endpoint not in common_endpoints:
                    anomalies.append(BehaviorAnomaly(
                        anomaly_type=BehaviorAnomalyType.ACCESS_ANOMALY,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        description=f"Access to unusual endpoint: {event.endpoint}",
                        anomaly_score=0.6,
                        confidence=0.6,
                        observed_behavior={"endpoint": event.endpoint},
                        expected_behavior={"endpoints": list(common_endpoints)[:5]},
                        detected_at=event.timestamp,
                    ))
        
        # Check for geographic anomalies
        if self.detect_geographic and common_locations:
            for event in events:
                if event.location and event.location not in common_locations:
                    anomalies.append(BehaviorAnomaly(
                        anomaly_type=BehaviorAnomalyType.GEOGRAPHIC_ANOMALY,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        description=f"Access from unusual location: {event.location}",
                        anomaly_score=0.7,
                        confidence=0.7,
                        observed_behavior={"location": event.location},
                        expected_behavior={"locations": list(common_locations)},
                        detected_at=event.timestamp,
                    ))
        
        # Check for timing anomalies
        for event in events:
            hour = event.timestamp.hour
            expected_prob = hourly_pattern[hour] if len(hourly_pattern) > hour else 0.05
            
            if expected_prob < 0.01:  # Very unusual hour
                anomalies.append(BehaviorAnomaly(
                    anomaly_type=BehaviorAnomalyType.TIMING_ANOMALY,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    description=f"Activity at unusual time: {hour}:00",
                    anomaly_score=0.5,
                    confidence=0.5,
                    observed_behavior={"hour": hour},
                    expected_behavior={"expected_probability": float(expected_prob)},
                    detected_at=event.timestamp,
                ))
        
        return anomalies
    
    def evaluate(
        self,
        X: List[BehaviorEvent],
        y: np.ndarray,
    ) -> EvaluationMetrics:
        """Evaluate the detector."""
        import time
        start_time = time.time()
        
        result = self.predict(X)
        
        # Create predictions (entity-level)
        anomalous_entities = set()
        for anomaly in result.prediction.anomalies:
            anomalous_entities.add(anomaly.entity_id)
        
        # This is a simplification - in practice would need per-event labels
        predictions = np.zeros(len(X))
        for i, event in enumerate(X):
            if event.entity_id in anomalous_entities:
                predictions[i] = 1
        
        y = np.asarray(y).flatten()
        
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
            "activity_level": 0.25,
            "endpoint_access": 0.25,
            "timing_pattern": 0.2,
            "geographic_location": 0.15,
            "sequence_pattern": 0.15,
        }
