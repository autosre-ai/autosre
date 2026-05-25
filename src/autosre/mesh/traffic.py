"""
Traffic Manager for Service Mesh

Provides high-level traffic management abstractions:
- Canary deployments with automatic rollback
- Blue-Green deployments
- A/B testing with metrics collection
- Traffic shifting and mirroring
- Rollback capabilities
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class TrafficShiftStrategy(str, Enum):
    """Strategy for shifting traffic."""
    
    LINEAR = "linear"           # Linear increase over time
    EXPONENTIAL = "exponential" # Exponential increase
    CANARY = "canary"           # Gradual canary rollout
    BLUE_GREEN = "blue_green"   # Instant switch
    CUSTOM = "custom"           # Custom weight schedule


class HeaderMatchType(str, Enum):
    """Type of header matching."""
    
    EXACT = "exact"
    PREFIX = "prefix"
    REGEX = "regex"
    PRESENT = "present"


class DeploymentPhase(str, Enum):
    """Phase of a deployment."""
    
    PENDING = "pending"
    PROGRESSING = "progressing"
    PAUSED = "paused"
    PROMOTING = "promoting"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Configuration Models
# =============================================================================


class TrafficManagerConfig(BaseModel):
    """Configuration for TrafficManager."""
    
    mesh_type: str = Field(default="istio", description="Mesh type: istio, linkerd")
    namespace: str = Field(default="default", description="Default namespace")
    
    # Metrics
    prometheus_url: Optional[str] = Field(default=None, description="Prometheus URL")
    metrics_interval_seconds: int = Field(default=30, description="Metrics check interval")
    
    # Safety
    auto_rollback: bool = Field(default=True, description="Enable automatic rollback")
    rollback_threshold_success_rate: float = Field(default=0.95, description="Success rate threshold")
    rollback_threshold_latency_p99_ms: float = Field(default=500.0, description="P99 latency threshold")


class WeightedRoute(BaseModel):
    """A weighted route to a service version."""
    
    host: str
    subset: Optional[str] = None
    weight: int = 100
    headers: dict[str, str] = Field(default_factory=dict)


class HeaderMatch(BaseModel):
    """Header match condition for routing."""
    
    name: str
    value: str
    match_type: HeaderMatchType = HeaderMatchType.EXACT


class MirrorConfig(BaseModel):
    """Configuration for traffic mirroring."""
    
    host: str
    subset: Optional[str] = None
    percentage: float = 100.0


class FaultConfig(BaseModel):
    """Configuration for fault injection."""
    
    delay_percentage: float = 0.0
    delay_duration_ms: int = 0
    abort_percentage: float = 0.0
    abort_code: int = 503


class RetryConfig(BaseModel):
    """Configuration for retries."""
    
    attempts: int = 3
    per_try_timeout_ms: int = 2000
    retry_on: list[str] = Field(default_factory=lambda: ["5xx", "reset", "connect-failure"])


class TimeoutConfig(BaseModel):
    """Configuration for timeouts."""
    
    request_timeout_ms: int = 15000
    idle_timeout_ms: int = 3600000


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker."""
    
    max_connections: int = 100
    max_pending_requests: int = 100
    max_requests: int = 100
    consecutive_errors: int = 5
    interval_seconds: int = 10
    base_ejection_time_seconds: int = 30
    max_ejection_percent: int = 100


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting."""
    
    requests_per_second: int = 100
    burst_size: int = 10


# =============================================================================
# Canary Deployment
# =============================================================================


class CanaryConfig(BaseModel):
    """Configuration for canary deployment."""
    
    service_name: str
    namespace: str
    
    # Versions
    stable_subset: str = "stable"
    canary_subset: str = "canary"
    
    # Rollout
    initial_weight: int = Field(default=5, ge=0, le=100)
    weight_increment: int = Field(default=10, ge=1, le=100)
    max_weight: int = Field(default=100, ge=1, le=100)
    interval_seconds: int = Field(default=60, ge=10)
    
    # Analysis
    success_rate_threshold: float = Field(default=0.99, ge=0.0, le=1.0)
    latency_p99_threshold_ms: float = Field(default=500.0, ge=0.0)
    error_rate_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    
    # Safety
    auto_rollback: bool = True
    min_request_count: int = Field(default=100, ge=1)


@dataclass
class CanaryMetrics:
    """Metrics for canary analysis."""
    
    success_rate: float
    error_rate: float
    latency_p50_ms: float
    latency_p99_ms: float
    request_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def is_healthy(self, config: CanaryConfig) -> bool:
        """Check if metrics indicate healthy canary."""
        return (
            self.success_rate >= config.success_rate_threshold
            and self.error_rate <= config.error_rate_threshold
            and self.latency_p99_ms <= config.latency_p99_threshold_ms
            and self.request_count >= config.min_request_count
        )


@dataclass
class CanaryStatus:
    """Status of a canary deployment."""
    
    phase: DeploymentPhase
    current_weight: int
    stable_weight: int
    started_at: datetime
    
    # Progress
    last_promotion: Optional[datetime] = None
    promotion_count: int = 0
    
    # Analysis
    metrics_history: list[CanaryMetrics] = field(default_factory=list)
    last_analysis: Optional[datetime] = None
    analysis_result: str = ""
    
    # Completion
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


@dataclass
class CanaryDeployment:
    """Canary deployment state and operations."""
    
    id: str
    config: CanaryConfig
    status: CanaryStatus
    
    # Metadata
    created_by: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    
    def can_promote(self) -> bool:
        """Check if canary can be promoted."""
        return (
            self.status.phase == DeploymentPhase.PROGRESSING
            and self.status.current_weight < self.config.max_weight
        )
    
    def can_rollback(self) -> bool:
        """Check if canary can be rolled back."""
        return self.status.phase in [
            DeploymentPhase.PROGRESSING,
            DeploymentPhase.PAUSED,
            DeploymentPhase.PROMOTING,
        ]


# =============================================================================
# Blue-Green Deployment
# =============================================================================


class BlueGreenConfig(BaseModel):
    """Configuration for blue-green deployment."""
    
    service_name: str
    namespace: str
    
    # Environments
    blue_subset: str = "blue"
    green_subset: str = "green"
    
    # Promotion
    promotion_strategy: str = "instant"  # instant, gradual
    gradual_steps: list[int] = Field(default_factory=lambda: [10, 50, 100])
    step_interval_seconds: int = 60
    
    # Validation
    smoke_test_enabled: bool = True
    smoke_test_timeout_seconds: int = 60
    health_check_enabled: bool = True
    health_check_path: str = "/health"
    
    # Rollback
    auto_rollback: bool = True
    rollback_on_smoke_test_failure: bool = True


@dataclass
class BlueGreenStatus:
    """Status of a blue-green deployment."""
    
    phase: DeploymentPhase
    active_environment: str  # "blue" or "green"
    inactive_environment: str
    
    # Progress
    started_at: datetime
    promotion_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Validation
    smoke_test_passed: Optional[bool] = None
    health_check_passed: Optional[bool] = None
    
    # Rollback
    rollback_reason: Optional[str] = None


@dataclass
class BlueGreenDeployment:
    """Blue-green deployment state and operations."""
    
    id: str
    config: BlueGreenConfig
    status: BlueGreenStatus
    
    # Metadata
    created_by: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    
    def can_promote(self) -> bool:
        """Check if ready to promote inactive environment."""
        return (
            self.status.phase == DeploymentPhase.PENDING
            or self.status.phase == DeploymentPhase.PROGRESSING
        )
    
    def can_rollback(self) -> bool:
        """Check if can rollback to previous environment."""
        return self.status.phase in [
            DeploymentPhase.PROMOTING,
            DeploymentPhase.COMPLETED,
        ]


# =============================================================================
# A/B Testing
# =============================================================================


class ABTestConfig(BaseModel):
    """Configuration for A/B test."""
    
    service_name: str
    namespace: str
    name: str
    
    # Variants
    control_subset: str = "control"
    treatment_subset: str = "treatment"
    traffic_split: dict[str, int] = Field(default_factory=lambda: {"control": 50, "treatment": 50})
    
    # Targeting
    header_matches: list[HeaderMatch] = Field(default_factory=list)
    user_percentage: float = 100.0  # Percentage of users to include
    
    # Duration
    duration_hours: int = 24
    min_sample_size: int = 1000
    
    # Metrics
    primary_metric: str = "conversion_rate"
    secondary_metrics: list[str] = Field(default_factory=list)
    confidence_level: float = 0.95


@dataclass
class ABTestResult:
    """Results of an A/B test."""
    
    test_name: str
    started_at: datetime
    ended_at: Optional[datetime]
    
    # Sample sizes
    control_samples: int
    treatment_samples: int
    
    # Primary metric
    control_metric: float
    treatment_metric: float
    relative_improvement: float
    p_value: float
    is_significant: bool
    
    # Confidence
    confidence_interval_lower: float
    confidence_interval_upper: float
    
    # Recommendation
    winner: Optional[str] = None
    recommendation: str = ""


@dataclass
class ABTest:
    """A/B test state and operations."""
    
    id: str
    config: ABTestConfig
    status: DeploymentPhase
    
    # Progress
    started_at: datetime
    expected_end_at: datetime
    
    # Results
    current_results: Optional[ABTestResult] = None
    
    # Metadata
    created_by: str = ""
    labels: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Traffic Shift
# =============================================================================


@dataclass
class TrafficShift:
    """Represents a traffic shift operation."""
    
    id: str
    service_name: str
    namespace: str
    
    # Weights
    source_weights: dict[str, int]
    target_weights: dict[str, int]
    current_weights: dict[str, int]
    
    # Strategy
    strategy: TrafficShiftStrategy
    
    # Timing
    started_at: datetime
    
    # Fields with defaults
    steps: list[dict[str, int]] = field(default_factory=list)
    current_step: int = 0
    step_interval_seconds: int = 60
    last_step_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Status
    phase: DeploymentPhase = DeploymentPhase.PENDING
    
    def is_complete(self) -> bool:
        """Check if shift is complete."""
        return self.current_weights == self.target_weights


# =============================================================================
# Traffic Snapshot (for rollback)
# =============================================================================


@dataclass
class TrafficSnapshot:
    """Snapshot of traffic configuration for rollback."""
    
    id: str
    service_name: str
    namespace: str
    
    # Configuration
    weights: dict[str, int]
    routes: list[dict[str, Any]]
    destination_rules: list[dict[str, Any]]
    
    # Metadata
    created_at: datetime
    created_by: str = ""
    description: str = ""
    labels: dict[str, str] = field(default_factory=dict)


class RollbackConfig(BaseModel):
    """Configuration for rollback operation."""
    
    service_name: str
    namespace: str
    
    # Target
    target_snapshot_id: Optional[str] = None
    target_weights: Optional[dict[str, int]] = None
    
    # Strategy
    instant: bool = False
    step_interval_seconds: int = 30
    
    # Reason
    reason: str = ""


# =============================================================================
# Traffic Manager
# =============================================================================


class TrafficManager:
    """
    High-level traffic management for service mesh.
    
    Provides unified interface for traffic operations regardless of
    underlying mesh (Istio, Linkerd, etc.). Supports:
    - Canary deployments with automatic analysis and rollback
    - Blue-green deployments with smoke testing
    - A/B testing with statistical analysis
    - Traffic shifting and mirroring
    - Rollback with snapshot support
    
    Usage:
        manager = TrafficManager(config=TrafficManagerConfig(mesh_type="istio"))
        await manager.connect()
        
        # Start a canary deployment
        canary = await manager.create_canary(
            config=CanaryConfig(
                service_name="my-service",
                namespace="production",
                initial_weight=5,
                weight_increment=10,
            )
        )
        
        # Monitor and auto-promote/rollback
        await manager.run_canary(canary.id)
    """
    
    def __init__(self, config: Optional[TrafficManagerConfig] = None):
        """Initialize TrafficManager."""
        self.config = config or TrafficManagerConfig()
        
        # Internal state
        self._canaries: dict[str, CanaryDeployment] = {}
        self._blue_greens: dict[str, BlueGreenDeployment] = {}
        self._ab_tests: dict[str, ABTest] = {}
        self._shifts: dict[str, TrafficShift] = {}
        self._snapshots: dict[str, TrafficSnapshot] = {}
        
        # Mesh clients (lazy initialized)
        self._istio_client: Any = None
        self._linkerd_client: Any = None
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to service mesh."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Disconnect from service mesh."""
        self._connected = False
    
    # -------------------------------------------------------------------------
    # Canary Deployments
    # -------------------------------------------------------------------------
    
    async def create_canary(
        self,
        config: CanaryConfig,
        created_by: str = "",
        labels: Optional[dict[str, str]] = None,
    ) -> CanaryDeployment:
        """
        Create a new canary deployment.
        
        Args:
            config: Canary configuration
            created_by: User/system creating the canary
            labels: Optional labels
        
        Returns:
            Created CanaryDeployment
        """
        import uuid
        
        canary_id = str(uuid.uuid4())[:8]
        
        status = CanaryStatus(
            phase=DeploymentPhase.PENDING,
            current_weight=config.initial_weight,
            stable_weight=100 - config.initial_weight,
            started_at=datetime.utcnow(),
        )
        
        canary = CanaryDeployment(
            id=canary_id,
            config=config,
            status=status,
            created_by=created_by,
            labels=labels or {},
        )
        
        self._canaries[canary_id] = canary
        return canary
    
    async def get_canary(self, canary_id: str) -> Optional[CanaryDeployment]:
        """Get a canary deployment by ID."""
        return self._canaries.get(canary_id)
    
    async def list_canaries(
        self,
        namespace: Optional[str] = None,
        phase: Optional[DeploymentPhase] = None,
    ) -> list[CanaryDeployment]:
        """List canary deployments with optional filters."""
        canaries = list(self._canaries.values())
        
        if namespace:
            canaries = [c for c in canaries if c.config.namespace == namespace]
        if phase:
            canaries = [c for c in canaries if c.status.phase == phase]
        
        return canaries
    
    async def start_canary(self, canary_id: str) -> CanaryDeployment:
        """Start a canary deployment."""
        canary = self._canaries.get(canary_id)
        if not canary:
            raise ValueError(f"Canary {canary_id} not found")
        
        canary.status.phase = DeploymentPhase.PROGRESSING
        
        # Apply initial traffic split
        await self._apply_traffic_weights(
            canary.config.service_name,
            canary.config.namespace,
            {
                canary.config.stable_subset: canary.status.stable_weight,
                canary.config.canary_subset: canary.status.current_weight,
            },
        )
        
        return canary
    
    async def promote_canary(self, canary_id: str) -> CanaryDeployment:
        """Promote canary to next weight level."""
        canary = self._canaries.get(canary_id)
        if not canary:
            raise ValueError(f"Canary {canary_id} not found")
        
        if not canary.can_promote():
            raise ValueError(f"Canary {canary_id} cannot be promoted")
        
        # Calculate new weights
        new_canary_weight = min(
            canary.status.current_weight + canary.config.weight_increment,
            canary.config.max_weight,
        )
        new_stable_weight = 100 - new_canary_weight
        
        canary.status.current_weight = new_canary_weight
        canary.status.stable_weight = new_stable_weight
        canary.status.promotion_count += 1
        canary.status.last_promotion = datetime.utcnow()
        
        # Check if complete
        if new_canary_weight >= canary.config.max_weight:
            canary.status.phase = DeploymentPhase.COMPLETED
            canary.status.completed_at = datetime.utcnow()
        
        # Apply new weights
        await self._apply_traffic_weights(
            canary.config.service_name,
            canary.config.namespace,
            {
                canary.config.stable_subset: new_stable_weight,
                canary.config.canary_subset: new_canary_weight,
            },
        )
        
        return canary
    
    async def rollback_canary(
        self, canary_id: str, reason: str = ""
    ) -> CanaryDeployment:
        """Rollback a canary deployment."""
        canary = self._canaries.get(canary_id)
        if not canary:
            raise ValueError(f"Canary {canary_id} not found")
        
        canary.status.phase = DeploymentPhase.ROLLING_BACK
        
        # Route all traffic to stable
        await self._apply_traffic_weights(
            canary.config.service_name,
            canary.config.namespace,
            {
                canary.config.stable_subset: 100,
                canary.config.canary_subset: 0,
            },
        )
        
        canary.status.phase = DeploymentPhase.FAILED
        canary.status.failure_reason = reason
        canary.status.completed_at = datetime.utcnow()
        canary.status.current_weight = 0
        canary.status.stable_weight = 100
        
        return canary
    
    async def analyze_canary(
        self, canary_id: str
    ) -> tuple[bool, CanaryMetrics]:
        """
        Analyze canary metrics and determine health.
        
        Returns:
            Tuple of (is_healthy, metrics)
        """
        canary = self._canaries.get(canary_id)
        if not canary:
            raise ValueError(f"Canary {canary_id} not found")
        
        # Fetch metrics (in production, from Prometheus/mesh)
        metrics = await self._fetch_canary_metrics(canary)
        
        canary.status.metrics_history.append(metrics)
        canary.status.last_analysis = datetime.utcnow()
        
        is_healthy = metrics.is_healthy(canary.config)
        canary.status.analysis_result = "healthy" if is_healthy else "unhealthy"
        
        return is_healthy, metrics
    
    async def run_canary(
        self,
        canary_id: str,
        on_promote: Optional[Callable[[CanaryDeployment], None]] = None,
        on_rollback: Optional[Callable[[CanaryDeployment, str], None]] = None,
    ) -> CanaryDeployment:
        """
        Run canary deployment to completion.
        
        Automatically promotes or rolls back based on metrics.
        
        Args:
            canary_id: Canary ID
            on_promote: Callback when canary is promoted
            on_rollback: Callback when canary is rolled back
        
        Returns:
            Completed CanaryDeployment
        """
        canary = await self.start_canary(canary_id)
        
        while canary.status.phase == DeploymentPhase.PROGRESSING:
            # Wait for interval
            await asyncio.sleep(canary.config.interval_seconds)
            
            # Analyze metrics
            is_healthy, metrics = await self.analyze_canary(canary_id)
            
            if is_healthy:
                if canary.can_promote():
                    canary = await self.promote_canary(canary_id)
                    if on_promote:
                        on_promote(canary)
            else:
                if canary.config.auto_rollback:
                    reason = f"Metrics unhealthy: success_rate={metrics.success_rate:.2%}"
                    canary = await self.rollback_canary(canary_id, reason)
                    if on_rollback:
                        on_rollback(canary, reason)
                    break
        
        return canary
    
    # -------------------------------------------------------------------------
    # Blue-Green Deployments
    # -------------------------------------------------------------------------
    
    async def create_blue_green(
        self,
        config: BlueGreenConfig,
        created_by: str = "",
    ) -> BlueGreenDeployment:
        """Create a new blue-green deployment."""
        import uuid
        
        bg_id = str(uuid.uuid4())[:8]
        
        status = BlueGreenStatus(
            phase=DeploymentPhase.PENDING,
            active_environment=config.blue_subset,
            inactive_environment=config.green_subset,
            started_at=datetime.utcnow(),
        )
        
        deployment = BlueGreenDeployment(
            id=bg_id,
            config=config,
            status=status,
            created_by=created_by,
        )
        
        self._blue_greens[bg_id] = deployment
        return deployment
    
    async def promote_blue_green(
        self, deployment_id: str
    ) -> BlueGreenDeployment:
        """Promote inactive environment to active."""
        deployment = self._blue_greens.get(deployment_id)
        if not deployment:
            raise ValueError(f"Blue-green {deployment_id} not found")
        
        # Swap environments
        deployment.status.phase = DeploymentPhase.PROMOTING
        deployment.status.promotion_started_at = datetime.utcnow()
        
        old_active = deployment.status.active_environment
        deployment.status.active_environment = deployment.status.inactive_environment
        deployment.status.inactive_environment = old_active
        
        # Apply traffic switch
        await self._apply_traffic_weights(
            deployment.config.service_name,
            deployment.config.namespace,
            {deployment.status.active_environment: 100},
        )
        
        deployment.status.phase = DeploymentPhase.COMPLETED
        deployment.status.completed_at = datetime.utcnow()
        
        return deployment
    
    async def rollback_blue_green(
        self, deployment_id: str, reason: str = ""
    ) -> BlueGreenDeployment:
        """Rollback to previous environment."""
        deployment = self._blue_greens.get(deployment_id)
        if not deployment:
            raise ValueError(f"Blue-green {deployment_id} not found")
        
        # Swap back
        old_active = deployment.status.active_environment
        deployment.status.active_environment = deployment.status.inactive_environment
        deployment.status.inactive_environment = old_active
        
        # Apply traffic switch
        await self._apply_traffic_weights(
            deployment.config.service_name,
            deployment.config.namespace,
            {deployment.status.active_environment: 100},
        )
        
        deployment.status.phase = DeploymentPhase.FAILED
        deployment.status.rollback_reason = reason
        
        return deployment
    
    # -------------------------------------------------------------------------
    # A/B Testing
    # -------------------------------------------------------------------------
    
    async def create_ab_test(
        self,
        config: ABTestConfig,
        created_by: str = "",
    ) -> ABTest:
        """Create a new A/B test."""
        import uuid
        
        test_id = str(uuid.uuid4())[:8]
        now = datetime.utcnow()
        
        test = ABTest(
            id=test_id,
            config=config,
            status=DeploymentPhase.PENDING,
            started_at=now,
            expected_end_at=now + timedelta(hours=config.duration_hours),
            created_by=created_by,
        )
        
        self._ab_tests[test_id] = test
        return test
    
    async def start_ab_test(self, test_id: str) -> ABTest:
        """Start an A/B test."""
        test = self._ab_tests.get(test_id)
        if not test:
            raise ValueError(f"A/B test {test_id} not found")
        
        test.status = DeploymentPhase.PROGRESSING
        
        # Apply traffic split
        await self._apply_traffic_weights(
            test.config.service_name,
            test.config.namespace,
            test.config.traffic_split,
        )
        
        return test
    
    async def get_ab_test_results(self, test_id: str) -> ABTestResult:
        """Get current results of an A/B test."""
        test = self._ab_tests.get(test_id)
        if not test:
            raise ValueError(f"A/B test {test_id} not found")
        
        # In production: fetch metrics and compute statistics
        result = ABTestResult(
            test_name=test.config.name,
            started_at=test.started_at,
            ended_at=None,
            control_samples=0,
            treatment_samples=0,
            control_metric=0.0,
            treatment_metric=0.0,
            relative_improvement=0.0,
            p_value=1.0,
            is_significant=False,
            confidence_interval_lower=0.0,
            confidence_interval_upper=0.0,
        )
        
        test.current_results = result
        return result
    
    async def end_ab_test(
        self, test_id: str, winner: Optional[str] = None
    ) -> ABTest:
        """End an A/B test and optionally route to winner."""
        test = self._ab_tests.get(test_id)
        if not test:
            raise ValueError(f"A/B test {test_id} not found")
        
        test.status = DeploymentPhase.COMPLETED
        
        if test.current_results:
            test.current_results.ended_at = datetime.utcnow()
        
        if winner:
            # Route all traffic to winner
            await self._apply_traffic_weights(
                test.config.service_name,
                test.config.namespace,
                {winner: 100},
            )
        
        return test
    
    # -------------------------------------------------------------------------
    # Traffic Shifting
    # -------------------------------------------------------------------------
    
    async def shift_traffic(
        self,
        service_name: str,
        namespace: str,
        target_weights: dict[str, int],
        strategy: TrafficShiftStrategy = TrafficShiftStrategy.LINEAR,
        steps: int = 5,
        interval_seconds: int = 60,
    ) -> TrafficShift:
        """
        Gradually shift traffic to target weights.
        
        Args:
            service_name: Service name
            namespace: Namespace
            target_weights: Target weights for each subset
            strategy: Shift strategy
            steps: Number of steps for gradual shift
            interval_seconds: Seconds between steps
        
        Returns:
            TrafficShift tracking object
        """
        import uuid
        
        shift_id = str(uuid.uuid4())[:8]
        
        # Get current weights (placeholder)
        current_weights = {k: 0 for k in target_weights}
        
        # Calculate steps
        weight_steps = self._calculate_shift_steps(
            current_weights, target_weights, strategy, steps
        )
        
        shift = TrafficShift(
            id=shift_id,
            service_name=service_name,
            namespace=namespace,
            source_weights=current_weights.copy(),
            target_weights=target_weights,
            current_weights=current_weights,
            strategy=strategy,
            steps=weight_steps,
            started_at=datetime.utcnow(),
            step_interval_seconds=interval_seconds,
        )
        
        self._shifts[shift_id] = shift
        return shift
    
    async def run_traffic_shift(self, shift_id: str) -> TrafficShift:
        """Run traffic shift to completion."""
        shift = self._shifts.get(shift_id)
        if not shift:
            raise ValueError(f"Traffic shift {shift_id} not found")
        
        shift.phase = DeploymentPhase.PROGRESSING
        
        for i, step_weights in enumerate(shift.steps):
            shift.current_step = i
            shift.current_weights = step_weights
            shift.last_step_at = datetime.utcnow()
            
            await self._apply_traffic_weights(
                shift.service_name,
                shift.namespace,
                step_weights,
            )
            
            if i < len(shift.steps) - 1:
                await asyncio.sleep(shift.step_interval_seconds)
        
        shift.phase = DeploymentPhase.COMPLETED
        shift.completed_at = datetime.utcnow()
        
        return shift
    
    # -------------------------------------------------------------------------
    # Traffic Mirroring
    # -------------------------------------------------------------------------
    
    async def start_mirroring(
        self,
        service_name: str,
        namespace: str,
        mirror_host: str,
        percentage: float = 100.0,
    ) -> dict[str, Any]:
        """
        Start mirroring traffic to another service.
        
        Args:
            service_name: Source service
            namespace: Namespace
            mirror_host: Destination for mirrored traffic
            percentage: Percentage of traffic to mirror
        
        Returns:
            Mirror configuration
        """
        mirror_config = MirrorConfig(
            host=mirror_host,
            percentage=percentage,
        )
        
        # In production: apply to mesh
        return {
            "service": service_name,
            "namespace": namespace,
            "mirror": mirror_config.model_dump(),
            "status": "active",
        }
    
    async def stop_mirroring(
        self, service_name: str, namespace: str
    ) -> bool:
        """Stop traffic mirroring."""
        # In production: remove mirror config from mesh
        return True
    
    # -------------------------------------------------------------------------
    # Snapshots and Rollback
    # -------------------------------------------------------------------------
    
    async def create_snapshot(
        self,
        service_name: str,
        namespace: str,
        description: str = "",
        created_by: str = "",
    ) -> TrafficSnapshot:
        """
        Create a snapshot of current traffic configuration.
        
        Args:
            service_name: Service name
            namespace: Namespace
            description: Snapshot description
            created_by: Creator
        
        Returns:
            TrafficSnapshot for rollback
        """
        import uuid
        
        snapshot_id = str(uuid.uuid4())[:8]
        
        # In production: fetch current config from mesh
        snapshot = TrafficSnapshot(
            id=snapshot_id,
            service_name=service_name,
            namespace=namespace,
            weights={},
            routes=[],
            destination_rules=[],
            created_at=datetime.utcnow(),
            created_by=created_by,
            description=description,
        )
        
        self._snapshots[snapshot_id] = snapshot
        return snapshot
    
    async def list_snapshots(
        self,
        service_name: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> list[TrafficSnapshot]:
        """List available snapshots."""
        snapshots = list(self._snapshots.values())
        
        if service_name:
            snapshots = [s for s in snapshots if s.service_name == service_name]
        if namespace:
            snapshots = [s for s in snapshots if s.namespace == namespace]
        
        return sorted(snapshots, key=lambda s: s.created_at, reverse=True)
    
    async def rollback_to_snapshot(
        self, snapshot_id: str
    ) -> TrafficSnapshot:
        """Rollback traffic configuration to a snapshot."""
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")
        
        # Apply snapshot configuration
        if snapshot.weights:
            await self._apply_traffic_weights(
                snapshot.service_name,
                snapshot.namespace,
                snapshot.weights,
            )
        
        return snapshot
    
    async def rollback(self, config: RollbackConfig) -> dict[str, Any]:
        """
        Perform a rollback operation.
        
        Args:
            config: Rollback configuration
        
        Returns:
            Rollback result
        """
        if config.target_snapshot_id:
            snapshot = await self.rollback_to_snapshot(config.target_snapshot_id)
            return {
                "type": "snapshot",
                "snapshot_id": snapshot.id,
                "status": "completed",
            }
        elif config.target_weights:
            shift = await self.shift_traffic(
                service_name=config.service_name,
                namespace=config.namespace,
                target_weights=config.target_weights,
                strategy=TrafficShiftStrategy.LINEAR if not config.instant else TrafficShiftStrategy.BLUE_GREEN,
            )
            await self.run_traffic_shift(shift.id)
            return {
                "type": "weight_shift",
                "shift_id": shift.id,
                "status": "completed",
            }
        else:
            raise ValueError("Either target_snapshot_id or target_weights required")
    
    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------
    
    async def _apply_traffic_weights(
        self,
        service_name: str,
        namespace: str,
        weights: dict[str, int],
    ) -> None:
        """Apply traffic weights to the mesh."""
        # In production: use Istio or Linkerd client based on config
        pass
    
    async def _fetch_canary_metrics(
        self, canary: CanaryDeployment
    ) -> CanaryMetrics:
        """Fetch metrics for canary analysis."""
        # In production: query Prometheus or mesh metrics
        return CanaryMetrics(
            success_rate=0.99,
            error_rate=0.01,
            latency_p50_ms=50.0,
            latency_p99_ms=200.0,
            request_count=1000,
        )
    
    def _calculate_shift_steps(
        self,
        source: dict[str, int],
        target: dict[str, int],
        strategy: TrafficShiftStrategy,
        num_steps: int,
    ) -> list[dict[str, int]]:
        """Calculate intermediate steps for traffic shift."""
        if strategy == TrafficShiftStrategy.BLUE_GREEN:
            return [target]
        
        steps = []
        for i in range(1, num_steps + 1):
            progress = i / num_steps
            step = {}
            for key in target:
                src_val = source.get(key, 0)
                tgt_val = target[key]
                step[key] = int(src_val + (tgt_val - src_val) * progress)
            steps.append(step)
        
        return steps
