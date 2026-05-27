"""
Canary Analysis for Safe Deployments

Provides intelligent canary analysis to compare new versions against
baselines using statistical methods and metric thresholds.
"""

import asyncio
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class CanaryVerdict(str, Enum):
    """Final verdict for canary analysis."""
    
    PASS = "pass"              # Canary is healthy, safe to promote
    FAIL = "fail"              # Canary shows degradation
    INCONCLUSIVE = "inconclusive"  # Not enough data
    PENDING = "pending"        # Analysis in progress


class CanaryPhase(str, Enum):
    """Phases of canary deployment."""
    
    INITIALIZING = "initializing"
    ANALYZING = "analyzing"
    PROMOTING = "promoting"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"


class TestType(str, Enum):
    """Statistical test types for metric comparison."""
    
    MANN_WHITNEY = "mann_whitney"
    T_TEST = "t_test"
    WELCH = "welch"
    KS_TEST = "ks_test"
    THRESHOLD = "threshold"


class CanaryConfig(BaseModel):
    """Configuration for canary analysis."""
    
    # Basic settings
    name: str = "canary-analysis"
    namespace: str = "default"
    
    # Canary settings
    canary_service: str = ""
    baseline_service: str = ""
    
    # Analysis duration
    warmup_duration_seconds: int = Field(default=60, ge=0)
    analysis_duration_seconds: int = Field(default=300, ge=60)
    
    # Traffic settings
    initial_weight: int = Field(default=10, ge=1, le=100)
    max_weight: int = Field(default=50, ge=1, le=100)
    weight_increment: int = Field(default=10, ge=1)
    
    # Thresholds
    success_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    marginal_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    
    # Statistical settings
    confidence_level: float = Field(default=0.95, ge=0.0, le=1.0)
    min_sample_size: int = Field(default=100, ge=10)
    
    # Metrics to analyze
    metrics: list[str] = Field(default_factory=lambda: [
        "request_success_rate",
        "request_latency_p99",
        "error_rate",
    ])
    
    # Promotion settings
    auto_promote: bool = True
    auto_rollback_on_failure: bool = True


@dataclass
class CanaryMetric:
    """A metric to be analyzed in canary comparison."""
    
    name: str
    query: str = ""
    description: str = ""
    
    # Comparison settings
    direction: str = "lower_is_better"  # lower_is_better, higher_is_better
    threshold_type: str = "relative"  # relative, absolute
    threshold_value: float = 0.1  # 10% regression allowed
    
    # Statistical test
    test_type: TestType = TestType.MANN_WHITNEY
    
    # Weights
    weight: float = 1.0
    is_critical: bool = False  # Fail immediately if critical metric fails


@dataclass
class ComparisonResult:
    """Result of comparing a single metric."""
    
    metric_name: str
    baseline_mean: float
    canary_mean: float
    baseline_stddev: float = 0.0
    canary_stddev: float = 0.0
    
    # Statistical results
    p_value: float = 0.0
    statistic: float = 0.0
    is_significant: bool = False
    
    # Verdict
    verdict: CanaryVerdict = CanaryVerdict.PENDING
    score: float = 0.0  # 0.0 to 1.0
    
    # Details
    sample_size_baseline: int = 0
    sample_size_canary: int = 0
    message: str = ""
    
    def calculate_change_percentage(self) -> float:
        """Calculate percentage change from baseline to canary."""
        if self.baseline_mean == 0:
            return 0.0
        return ((self.canary_mean - self.baseline_mean) / self.baseline_mean) * 100


class MetricComparison(BaseModel):
    """Configuration for metric comparison in canary analysis."""
    
    metric: str
    direction: str = "lower_is_better"
    threshold: float = 0.1
    test_type: TestType = TestType.MANN_WHITNEY
    weight: float = 1.0
    critical: bool = False


class StatisticalTest:
    """Statistical tests for canary comparison."""
    
    @staticmethod
    def mann_whitney(
        baseline: list[float],
        canary: list[float],
        alternative: str = "two-sided",
    ) -> tuple[float, float]:
        """Perform Mann-Whitney U test.
        
        Returns (statistic, p_value).
        """
        # Simplified implementation - in production use scipy.stats.mannwhitneyu
        if len(baseline) < 2 or len(canary) < 2:
            return 0.0, 1.0
        
        # Combine and rank
        combined = [(v, "baseline") for v in baseline] + [(v, "canary") for v in canary]
        combined.sort(key=lambda x: x[0])
        
        # Calculate rank sum for canary
        n1, n2 = len(baseline), len(canary)
        rank_sum_canary = sum(
            i + 1 for i, (_, group) in enumerate(combined) if group == "canary"
        )
        
        # Calculate U statistic
        u_canary = rank_sum_canary - n2 * (n2 + 1) / 2
        u_baseline = n1 * n2 - u_canary
        u = min(u_canary, u_baseline)
        
        # Approximate p-value using normal approximation
        mu = n1 * n2 / 2
        sigma = (n1 * n2 * (n1 + n2 + 1) / 12) ** 0.5
        
        if sigma == 0:
            return u, 1.0
        
        z = (u - mu) / sigma
        # Approximate two-tailed p-value
        p_value = min(1.0, 2 * (1 - 0.5 * (1 + _erf(abs(z) / 2 ** 0.5))))
        
        return u, p_value
    
    @staticmethod
    def t_test(
        baseline: list[float],
        canary: list[float],
    ) -> tuple[float, float]:
        """Perform Student's t-test.
        
        Returns (statistic, p_value).
        """
        if len(baseline) < 2 or len(canary) < 2:
            return 0.0, 1.0
        
        mean1 = statistics.mean(baseline)
        mean2 = statistics.mean(canary)
        var1 = statistics.variance(baseline)
        var2 = statistics.variance(canary)
        n1, n2 = len(baseline), len(canary)
        
        # Pooled standard error
        se = ((var1 / n1) + (var2 / n2)) ** 0.5
        
        if se == 0:
            return 0.0, 1.0
        
        t = (mean1 - mean2) / se
        
        # Degrees of freedom (Welch-Satterthwaite approximation)
        df = ((var1 / n1 + var2 / n2) ** 2) / (
            (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
        )
        
        # Approximate p-value
        p_value = min(1.0, 2 * (1 - _student_t_cdf(abs(t), df)))
        
        return t, p_value
    
    @staticmethod
    def threshold_test(
        baseline: list[float],
        canary: list[float],
        threshold: float,
        direction: str,
    ) -> tuple[float, bool]:
        """Simple threshold-based comparison.
        
        Returns (change_percentage, passed).
        """
        if not baseline or not canary:
            return 0.0, True
        
        mean_baseline = statistics.mean(baseline)
        mean_canary = statistics.mean(canary)
        
        if mean_baseline == 0:
            return 0.0, True
        
        change = (mean_canary - mean_baseline) / mean_baseline
        
        if direction == "lower_is_better":
            # Canary should be lower or not much higher
            passed = change <= threshold
        else:
            # Canary should be higher or not much lower
            passed = change >= -threshold
        
        return change * 100, passed


@dataclass
class CanaryWeight:
    """Traffic weight configuration for canary."""
    
    canary: int = 10
    baseline: int = 90
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TrafficSplit(BaseModel):
    """Traffic split configuration."""
    
    canary_weight: int = Field(default=10, ge=0, le=100)
    baseline_weight: int = Field(default=90, ge=0, le=100)
    
    # Gradual rollout
    increments: list[int] = Field(default_factory=lambda: [10, 25, 50, 75, 100])
    increment_interval_seconds: int = Field(default=300)
    
    def validate_weights(self) -> bool:
        """Validate that weights sum to 100."""
        return self.canary_weight + self.baseline_weight == 100


class PromotionCriteria(BaseModel):
    """Criteria for promoting canary to production."""
    
    # Metric thresholds
    min_success_rate: float = Field(default=0.95, ge=0.0, le=1.0)
    max_error_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    max_latency_p99_ms: float = Field(default=1000.0, ge=0.0)
    
    # Statistical requirements
    min_sample_size: int = Field(default=100, ge=10)
    confidence_level: float = Field(default=0.95, ge=0.0, le=1.0)
    
    # Analysis requirements
    min_analysis_duration_seconds: int = Field(default=300, ge=60)
    consecutive_passes: int = Field(default=3, ge=1)


@dataclass
class CanaryPromotion:
    """Promotion decision and details."""
    
    should_promote: bool = False
    reason: str = ""
    
    # Analysis summary
    overall_score: float = 0.0
    passed_metrics: int = 0
    failed_metrics: int = 0
    inconclusive_metrics: int = 0
    
    # Timing
    analysis_duration_seconds: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Detailed results
    metric_results: list[ComparisonResult] = field(default_factory=list)


@dataclass
class CanaryEvent:
    """Event during canary analysis."""
    
    event_type: str  # weight_change, analysis_complete, promotion, rollback
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CanaryTimeline:
    """Timeline of canary deployment."""
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    events: list[CanaryEvent] = field(default_factory=list)
    
    def add_event(
        self,
        event_type: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add an event to the timeline."""
        self.events.append(CanaryEvent(
            event_type=event_type,
            message=message,
            details=details or {},
        ))


class CanaryReport(BaseModel):
    """Complete canary analysis report."""
    
    name: str
    verdict: CanaryVerdict = CanaryVerdict.PENDING
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: int = 0
    
    # Results
    overall_score: float = 0.0
    metric_scores: dict[str, float] = Field(default_factory=dict)
    
    # Traffic
    final_canary_weight: int = 0
    
    # Summary
    passed_metrics: int = 0
    failed_metrics: int = 0
    critical_failures: list[str] = Field(default_factory=list)
    
    # Recommendation
    recommendation: str = ""
    
    def generate_summary(self) -> str:
        """Generate human-readable summary."""
        verdict_emoji = {
            CanaryVerdict.PASS: "✅",
            CanaryVerdict.FAIL: "❌",
            CanaryVerdict.INCONCLUSIVE: "⚠️",
            CanaryVerdict.PENDING: "⏳",
        }
        
        return (
            f"{verdict_emoji.get(self.verdict, '❓')} Canary Analysis: {self.verdict.value}\n"
            f"  Score: {self.overall_score:.2%}\n"
            f"  Passed: {self.passed_metrics}, Failed: {self.failed_metrics}\n"
            f"  Duration: {self.duration_seconds}s\n"
            f"  Recommendation: {self.recommendation}"
        )


@dataclass
class CanaryResult:
    """Result of canary analysis."""
    
    verdict: CanaryVerdict = CanaryVerdict.PENDING
    phase: CanaryPhase = CanaryPhase.INITIALIZING
    
    # Scores
    overall_score: float = 0.0
    metric_results: dict[str, ComparisonResult] = field(default_factory=dict)
    
    # Details
    message: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Traffic state
    current_weight: CanaryWeight = field(default_factory=CanaryWeight)
    
    # Timeline
    timeline: CanaryTimeline = field(default_factory=CanaryTimeline)
    
    def calculate_overall_score(self) -> float:
        """Calculate weighted overall score from metric results."""
        if not self.metric_results:
            return 0.0
        
        total_weight = sum(1.0 for _ in self.metric_results.values())
        weighted_sum = sum(r.score for r in self.metric_results.values())
        
        self.overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        return self.overall_score
    
    def to_report(self) -> CanaryReport:
        """Convert to a report format."""
        return CanaryReport(
            name="canary-analysis",
            verdict=self.verdict,
            started_at=self.started_at,
            completed_at=self.completed_at,
            duration_seconds=int(
                (self.completed_at - self.started_at).total_seconds()
            ) if self.completed_at and self.started_at else 0,
            overall_score=self.overall_score,
            metric_scores={
                name: result.score
                for name, result in self.metric_results.items()
            },
            final_canary_weight=self.current_weight.canary,
            passed_metrics=sum(
                1 for r in self.metric_results.values()
                if r.verdict == CanaryVerdict.PASS
            ),
            failed_metrics=sum(
                1 for r in self.metric_results.values()
                if r.verdict == CanaryVerdict.FAIL
            ),
            recommendation="Promote to production" if self.verdict == CanaryVerdict.PASS else "Rollback canary",
        )


class CanaryAnalyzer:
    """Performs canary analysis comparing new versions to baselines."""
    
    def __init__(
        self,
        config: Optional[CanaryConfig] = None,
        metrics_client: Optional[Any] = None,
        traffic_manager: Optional[Any] = None,
        notify_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.config = config or CanaryConfig()
        self.metrics_client = metrics_client
        self.traffic_manager = traffic_manager
        self.notify_callback = notify_callback
        
        # State
        self._result: Optional[CanaryResult] = None
        self._metrics: dict[str, CanaryMetric] = {}
        self._is_running: bool = False
        
        # Initialize default metrics
        self._setup_default_metrics()
    
    def _setup_default_metrics(self) -> None:
        """Set up default metrics for analysis."""
        defaults = [
            CanaryMetric(
                name="request_success_rate",
                query='sum(rate(http_requests_total{status=~"2.."}[5m])) / sum(rate(http_requests_total[5m]))',
                direction="higher_is_better",
                threshold_value=0.05,
                is_critical=True,
            ),
            CanaryMetric(
                name="request_latency_p99",
                query='histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))',
                direction="lower_is_better",
                threshold_value=0.2,
            ),
            CanaryMetric(
                name="error_rate",
                query='sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))',
                direction="lower_is_better",
                threshold_value=0.1,
                is_critical=True,
            ),
        ]
        for metric in defaults:
            self._metrics[metric.name] = metric
    
    def add_metric(self, metric: CanaryMetric) -> None:
        """Add a metric to analyze."""
        self._metrics[metric.name] = metric
    
    async def analyze(
        self,
        baseline_data: Optional[dict[str, list[float]]] = None,
        canary_data: Optional[dict[str, list[float]]] = None,
    ) -> CanaryResult:
        """Perform canary analysis.
        
        If data is provided, analyzes it directly.
        Otherwise, queries metrics from the metrics client.
        """
        self._result = CanaryResult(
            phase=CanaryPhase.INITIALIZING,
            started_at=datetime.now(timezone.utc),
        )
        self._result.timeline.started_at = self._result.started_at
        self._is_running = True
        
        try:
            # Warmup period
            if self.config.warmup_duration_seconds > 0:
                self._result.timeline.add_event(
                    "warmup_started",
                    f"Starting warmup for {self.config.warmup_duration_seconds}s",
                )
                await asyncio.sleep(self.config.warmup_duration_seconds)
            
            self._result.phase = CanaryPhase.ANALYZING
            self._result.timeline.add_event(
                "analysis_started",
                "Beginning canary analysis",
            )
            
            # Collect or use provided data
            if baseline_data is None or canary_data is None:
                baseline_data, canary_data = await self._collect_metrics()
            
            # Analyze each metric
            for metric_name, metric in self._metrics.items():
                baseline_samples = baseline_data.get(metric_name, [])
                canary_samples = canary_data.get(metric_name, [])
                
                comparison = self._compare_metric(
                    metric, baseline_samples, canary_samples
                )
                self._result.metric_results[metric_name] = comparison
                
                # Check for critical failures
                if metric.is_critical and comparison.verdict == CanaryVerdict.FAIL:
                    self._result.verdict = CanaryVerdict.FAIL
                    self._result.message = f"Critical metric {metric_name} failed"
                    self._result.phase = CanaryPhase.FAILED
                    self._result.timeline.add_event(
                        "critical_failure",
                        f"Critical metric {metric_name} failed analysis",
                        {"metric": metric_name, "score": comparison.score},
                    )
                    break
            
            # Calculate overall verdict if not already failed
            if self._result.verdict != CanaryVerdict.FAIL:
                self._calculate_verdict()
            
            # Handle promotion/rollback
            if self._result.verdict == CanaryVerdict.PASS and self.config.auto_promote:
                await self._promote()
            elif self._result.verdict == CanaryVerdict.FAIL and self.config.auto_rollback_on_failure:
                await self._rollback()
            
        except Exception as e:
            self._result.verdict = CanaryVerdict.FAIL
            self._result.message = f"Analysis error: {str(e)}"
            self._result.phase = CanaryPhase.FAILED
        finally:
            self._is_running = False
            self._result.completed_at = datetime.now(timezone.utc)
            self._result.timeline.completed_at = self._result.completed_at
        
        return self._result
    
    def _compare_metric(
        self,
        metric: CanaryMetric,
        baseline: list[float],
        canary: list[float],
    ) -> ComparisonResult:
        """Compare a single metric between baseline and canary."""
        result = ComparisonResult(
            metric_name=metric.name,
            baseline_mean=statistics.mean(baseline) if baseline else 0.0,
            canary_mean=statistics.mean(canary) if canary else 0.0,
            baseline_stddev=statistics.stdev(baseline) if len(baseline) > 1 else 0.0,
            canary_stddev=statistics.stdev(canary) if len(canary) > 1 else 0.0,
            sample_size_baseline=len(baseline),
            sample_size_canary=len(canary),
        )
        
        # Check minimum sample size
        if len(baseline) < self.config.min_sample_size or len(canary) < self.config.min_sample_size:
            result.verdict = CanaryVerdict.INCONCLUSIVE
            result.message = "Insufficient samples"
            result.score = 0.5
            return result
        
        # Perform statistical test
        if metric.test_type == TestType.THRESHOLD:
            change, passed = StatisticalTest.threshold_test(
                baseline, canary, metric.threshold_value, metric.direction
            )
            result.statistic = change
            result.is_significant = not passed
        elif metric.test_type == TestType.T_TEST:
            t_stat, p_value = StatisticalTest.t_test(baseline, canary)
            result.statistic = t_stat
            result.p_value = p_value
            result.is_significant = p_value < (1 - self.config.confidence_level)
        else:  # Mann-Whitney
            u_stat, p_value = StatisticalTest.mann_whitney(baseline, canary)
            result.statistic = u_stat
            result.p_value = p_value
            result.is_significant = p_value < (1 - self.config.confidence_level)
        
        # Determine verdict based on direction and threshold
        change_pct = result.calculate_change_percentage()
        
        if metric.direction == "lower_is_better":
            # Canary is better if lower
            if change_pct <= -metric.threshold_value * 100:
                result.verdict = CanaryVerdict.PASS
                result.score = min(1.0, 0.5 + abs(change_pct) / 100)
            elif change_pct > metric.threshold_value * 100:
                result.verdict = CanaryVerdict.FAIL
                result.score = max(0.0, 0.5 - change_pct / 100)
            else:
                result.verdict = CanaryVerdict.PASS
                result.score = 0.5 + (metric.threshold_value * 100 - change_pct) / (2 * metric.threshold_value * 100)
        else:  # higher_is_better
            if change_pct >= metric.threshold_value * 100:
                result.verdict = CanaryVerdict.PASS
                result.score = min(1.0, 0.5 + change_pct / 100)
            elif change_pct < -metric.threshold_value * 100:
                result.verdict = CanaryVerdict.FAIL
                result.score = max(0.0, 0.5 + change_pct / 100)
            else:
                result.verdict = CanaryVerdict.PASS
                result.score = 0.5 + (change_pct + metric.threshold_value * 100) / (2 * metric.threshold_value * 100)
        
        result.message = f"Change: {change_pct:.2f}%, p-value: {result.p_value:.4f}"
        return result
    
    def _calculate_verdict(self) -> None:
        """Calculate overall verdict from metric results."""
        if not self._result.metric_results:
            self._result.verdict = CanaryVerdict.INCONCLUSIVE
            return
        
        # Calculate overall score
        self._result.calculate_overall_score()
        
        # Count verdicts
        passed = sum(
            1 for r in self._result.metric_results.values()
            if r.verdict == CanaryVerdict.PASS
        )
        failed = sum(
            1 for r in self._result.metric_results.values()
            if r.verdict == CanaryVerdict.FAIL
        )
        inconclusive = sum(
            1 for r in self._result.metric_results.values()
            if r.verdict == CanaryVerdict.INCONCLUSIVE
        )
        
        total = len(self._result.metric_results)
        
        if failed > 0:
            self._result.verdict = CanaryVerdict.FAIL
            self._result.message = f"{failed}/{total} metrics failed"
        elif inconclusive == total:
            self._result.verdict = CanaryVerdict.INCONCLUSIVE
            self._result.message = "All metrics inconclusive"
        elif self._result.overall_score >= self.config.success_threshold:
            self._result.verdict = CanaryVerdict.PASS
            self._result.message = f"Analysis passed with score {self._result.overall_score:.2%}"
            self._result.phase = CanaryPhase.COMPLETED
        elif self._result.overall_score >= self.config.marginal_threshold:
            self._result.verdict = CanaryVerdict.INCONCLUSIVE
            self._result.message = f"Marginal score {self._result.overall_score:.2%}"
        else:
            self._result.verdict = CanaryVerdict.FAIL
            self._result.message = f"Score {self._result.overall_score:.2%} below threshold"
    
    async def _collect_metrics(self) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
        """Collect metrics from baseline and canary."""
        # In a real implementation, this would query Prometheus/metrics backend
        # For now, return empty data
        return {}, {}
    
    async def _promote(self) -> None:
        """Promote canary to full production."""
        self._result.phase = CanaryPhase.PROMOTING
        self._result.timeline.add_event(
            "promotion_started",
            "Promoting canary to production",
        )
        
        # Gradually shift traffic
        if self.traffic_manager:
            await self._shift_traffic(100)
        
        self._result.current_weight = CanaryWeight(canary=100, baseline=0)
        self._result.phase = CanaryPhase.COMPLETED
        self._result.timeline.add_event(
            "promotion_completed",
            "Canary promoted to production",
        )
        
        self._notify("promotion", "✅ Canary analysis passed, promoted to production")
    
    async def _rollback(self) -> None:
        """Roll back canary deployment."""
        self._result.phase = CanaryPhase.ROLLING_BACK
        self._result.timeline.add_event(
            "rollback_started",
            "Rolling back canary deployment",
        )
        
        if self.traffic_manager:
            await self._shift_traffic(0)
        
        self._result.current_weight = CanaryWeight(canary=0, baseline=100)
        self._result.phase = CanaryPhase.FAILED
        self._result.timeline.add_event(
            "rollback_completed",
            "Canary rolled back",
        )
        
        self._notify("rollback", "❌ Canary analysis failed, rolled back")
    
    async def _shift_traffic(self, canary_weight: int) -> None:
        """Shift traffic to canary."""
        if self.traffic_manager:
            await self.traffic_manager.set_weight(
                canary=canary_weight,
                baseline=100 - canary_weight,
            )
        self._result.current_weight = CanaryWeight(
            canary=canary_weight,
            baseline=100 - canary_weight,
        )
    
    def _notify(self, event_type: str, message: str) -> None:
        """Send notification."""
        if self.notify_callback:
            self.notify_callback(event_type, message)
    
    def get_result(self) -> Optional[CanaryResult]:
        """Get current analysis result."""
        return self._result
    
    def is_running(self) -> bool:
        """Check if analysis is running."""
        return self._is_running


# Helper functions for statistical calculations

def _erf(x: float) -> float:
    """Error function approximation."""
    # Horner's method coefficients
    a1, a2, a3, a4, a5 = (
        0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    )
    p = 0.3275911
    
    sign = 1 if x >= 0 else -1
    x = abs(x)
    
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * (2.71828 ** (-x * x))
    
    return sign * y


def _student_t_cdf(t: float, df: float) -> float:
    """Student's t CDF approximation."""
    if df <= 0:
        return 0.5
    
    x = df / (df + t * t)
    return 0.5 * (1 + _erf(t / (2 ** 0.5)) if df > 100 else 1 - 0.5 * x ** (df / 2))
