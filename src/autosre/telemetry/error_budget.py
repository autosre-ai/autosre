"""
AI Error Budget Tracker

Track AI reliability targets like any other service.
Implements circuit breaker pattern to switch to conservative mode when budget exhausted.

Based on principle: "AI needs reliability targets like any service"

Error Budget Targets:
- high_severity_accuracy: 80% (AI must be right 80% on critical issues)
- safe_action_rate: 99% (99% of AI-suggested actions must be safe)
- human_override_threshold: 20% (if humans override >20%, something's wrong)
- bad_recommendation_rate: 5% (max 5% harmful recommendations)
"""

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from enum import Enum

from prometheus_client import Gauge, Counter


# =============================================================================
# Prometheus Metrics for Error Budget
# =============================================================================

ERROR_BUDGET_REMAINING = Gauge(
    'autosre_ai_error_budget_remaining',
    'Remaining error budget (0-1)',
    ['budget_type']
)

ERROR_BUDGET_EXHAUSTED = Gauge(
    'autosre_ai_error_budget_exhausted',
    'Whether error budget is exhausted (1=exhausted)',
    ['budget_type']
)

CONSERVATIVE_MODE_ACTIVE = Gauge(
    'autosre_ai_conservative_mode_active',
    'Whether conservative mode is active (1=active)'
)

CIRCUIT_BREAKER_TRIPS = Counter(
    'autosre_ai_circuit_breaker_trips_total',
    'Number of times circuit breaker has tripped',
    ['reason']
)


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class BudgetType(str, Enum):
    """Types of error budgets tracked."""
    HIGH_SEVERITY_ACCURACY = "high_severity_accuracy"
    SAFE_ACTION_RATE = "safe_action_rate"
    HUMAN_OVERRIDE = "human_override"
    BAD_RECOMMENDATION = "bad_recommendation"


@dataclass
class ErrorBudgetConfig:
    """Configuration for error budgets."""
    # Target accuracy for high-severity incidents
    high_severity_accuracy_target: float = 0.80
    
    # Target rate of safe (non-harmful) actions
    safe_action_rate_target: float = 0.99
    
    # Maximum acceptable human override rate
    human_override_threshold: float = 0.20
    
    # Maximum acceptable bad recommendation rate
    bad_recommendation_rate_target: float = 0.05
    
    # Window for calculating budgets (days)
    budget_window_days: int = 7
    
    # Minimum samples needed before budget kicks in
    min_samples: int = 10
    
    # Cool-down period after budget exhaustion (hours)
    cooldown_hours: int = 24


@dataclass
class BudgetStatus:
    """Status of a single error budget."""
    budget_type: BudgetType
    target: float
    current: float
    remaining: float  # How much budget left (0-1)
    exhausted: bool
    samples: int
    window_days: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "budget_type": self.budget_type.value,
            "target": self.target,
            "current": self.current,
            "remaining": self.remaining,
            "exhausted": self.exhausted,
            "samples": self.samples,
            "window_days": self.window_days,
        }


@dataclass
class ErrorBudgetStatus:
    """Overall error budget status."""
    conservative_mode: bool
    conservative_mode_reason: str
    budgets: dict[BudgetType, BudgetStatus] = field(default_factory=dict)
    last_checked: datetime = field(default_factory=utcnow)
    circuit_breaker_tripped_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "conservative_mode": self.conservative_mode,
            "conservative_mode_reason": self.conservative_mode_reason,
            "budgets": {k.value: v.to_dict() for k, v in self.budgets.items()},
            "last_checked": self.last_checked.isoformat(),
            "circuit_breaker_tripped_at": self.circuit_breaker_tripped_at.isoformat() if self.circuit_breaker_tripped_at else None,
        }
    
    @property
    def any_budget_exhausted(self) -> bool:
        """Check if any budget is exhausted."""
        return any(b.exhausted for b in self.budgets.values())
    
    def get_exhausted_budgets(self) -> list[BudgetType]:
        """Get list of exhausted budgets."""
        return [k for k, v in self.budgets.items() if v.exhausted]


class AIErrorBudget:
    """
    Track AI error budgets and implement circuit breaker.
    
    When error budget is exhausted:
    - Switch to conservative mode
    - Require human approval for ALL actions
    - Alert on-call engineers
    """
    
    def __init__(
        self,
        db_path: Optional[Path] = None,
        config: Optional[ErrorBudgetConfig] = None,
    ):
        """Initialize the error budget tracker."""
        self.db_path = db_path or Path.home() / ".autosre" / "error_budget.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = config or ErrorBudgetConfig()
        self._lock = threading.Lock()
        self._conservative_mode = False
        self._conservative_mode_reason = ""
        self._circuit_breaker_tripped_at: Optional[datetime] = None
        self._init_db()
        
        # Check status on init
        self._update_prometheus_metrics()
    
    def _init_db(self):
        """Initialize the SQLite database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            # Track individual events for budget calculation
            conn.execute("""
                CREATE TABLE IF NOT EXISTS budget_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    budget_type TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    investigation_id TEXT,
                    details TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_budget_events_timestamp 
                ON budget_events(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_budget_events_type 
                ON budget_events(budget_type, timestamp)
            """)
            
            # Track circuit breaker state
            conn.execute("""
                CREATE TABLE IF NOT EXISTS circuit_breaker_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    conservative_mode INTEGER NOT NULL DEFAULT 0,
                    reason TEXT DEFAULT '',
                    tripped_at TEXT,
                    last_checked TEXT
                )
            """)
            
            # Initialize state if not exists
            conn.execute("""
                INSERT OR IGNORE INTO circuit_breaker_state (id, conservative_mode)
                VALUES (1, 0)
            """)
            
            conn.commit()
            
            # Load state
            cursor = conn.execute(
                "SELECT conservative_mode, reason, tripped_at FROM circuit_breaker_state WHERE id = 1"
            )
            row = cursor.fetchone()
            if row:
                self._conservative_mode = bool(row[0])
                self._conservative_mode_reason = row[1] or ""
                self._circuit_breaker_tripped_at = datetime.fromisoformat(row[2]) if row[2] else None
    
    def record_event(
        self,
        budget_type: BudgetType,
        success: bool,
        investigation_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """
        Record an event that affects error budget.
        
        Args:
            budget_type: Which budget this affects
            success: Whether it was a success (True) or failure (False)
            investigation_id: Related investigation ID
            details: Additional details
        """
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    INSERT INTO budget_events 
                    (timestamp, budget_type, event_type, success, investigation_id, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    utcnow().isoformat(),
                    budget_type.value,
                    "success" if success else "failure",
                    1 if success else 0,
                    investigation_id,
                    json.dumps(details) if details else None,
                ))
                conn.commit()
        
        # Check if budget exhausted
        self._check_budgets_and_trip()
    
    def record_high_severity_outcome(
        self,
        correct: bool,
        investigation_id: Optional[str] = None,
    ) -> None:
        """Record outcome of a high-severity investigation."""
        self.record_event(
            BudgetType.HIGH_SEVERITY_ACCURACY,
            success=correct,
            investigation_id=investigation_id,
        )
    
    def record_action_safety(
        self,
        safe: bool,
        investigation_id: Optional[str] = None,
        action_details: Optional[dict] = None,
    ) -> None:
        """Record whether a suggested action was safe."""
        self.record_event(
            BudgetType.SAFE_ACTION_RATE,
            success=safe,
            investigation_id=investigation_id,
            details=action_details,
        )
    
    def record_human_decision(
        self,
        accepted: bool,
        investigation_id: Optional[str] = None,
    ) -> None:
        """Record human acceptance/rejection of AI recommendation."""
        # For human override, success = accepted (not overridden)
        self.record_event(
            BudgetType.HUMAN_OVERRIDE,
            success=accepted,
            investigation_id=investigation_id,
        )
    
    def record_recommendation_quality(
        self,
        good: bool,
        investigation_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Record whether a recommendation was good or bad."""
        self.record_event(
            BudgetType.BAD_RECOMMENDATION,
            success=good,  # success = good recommendation
            investigation_id=investigation_id,
            details=details,
        )
    
    def get_budget_status(self, budget_type: BudgetType) -> BudgetStatus:
        """Get the status of a specific error budget."""
        cutoff = (utcnow() - timedelta(days=self.config.budget_window_days)).isoformat()
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(success) as successes
                FROM budget_events
                WHERE budget_type = ? AND timestamp > ?
            """, (budget_type.value, cutoff))
            row = cursor.fetchone()
            
            total = row[0] or 0
            successes = row[1] or 0
        
        # Calculate based on budget type
        if budget_type == BudgetType.HIGH_SEVERITY_ACCURACY:
            target = self.config.high_severity_accuracy_target
            current = successes / total if total > 0 else 1.0
            # Budget remaining = how much above target we are
            remaining = max(0, (current - target) / (1 - target)) if target < 1 else 1.0
            exhausted = current < target and total >= self.config.min_samples
            
        elif budget_type == BudgetType.SAFE_ACTION_RATE:
            target = self.config.safe_action_rate_target
            current = successes / total if total > 0 else 1.0
            remaining = max(0, (current - target) / (1 - target)) if target < 1 else 1.0
            exhausted = current < target and total >= self.config.min_samples
            
        elif budget_type == BudgetType.HUMAN_OVERRIDE:
            target = 1 - self.config.human_override_threshold  # Target is to be accepted
            override_rate = 1 - (successes / total) if total > 0 else 0.0
            current = 1 - override_rate  # Acceptance rate
            remaining = max(0, (current - target) / (1 - target)) if target < 1 else 1.0
            exhausted = override_rate > self.config.human_override_threshold and total >= self.config.min_samples
            
        elif budget_type == BudgetType.BAD_RECOMMENDATION:
            target = 1 - self.config.bad_recommendation_rate_target
            current = successes / total if total > 0 else 1.0
            remaining = max(0, (current - target) / (1 - target)) if target < 1 else 1.0
            exhausted = current < target and total >= self.config.min_samples
            
        else:
            target = 0.0
            current = 0.0
            remaining = 1.0
            exhausted = False
        
        return BudgetStatus(
            budget_type=budget_type,
            target=target,
            current=current,
            remaining=remaining,
            exhausted=exhausted,
            samples=total,
            window_days=self.config.budget_window_days,
        )
    
    def get_status(self) -> ErrorBudgetStatus:
        """Get overall error budget status."""
        budgets = {
            bt: self.get_budget_status(bt)
            for bt in BudgetType
        }
        
        return ErrorBudgetStatus(
            conservative_mode=self._conservative_mode,
            conservative_mode_reason=self._conservative_mode_reason,
            budgets=budgets,
            last_checked=utcnow(),
            circuit_breaker_tripped_at=self._circuit_breaker_tripped_at,
        )
    
    def _check_budgets_and_trip(self) -> None:
        """Check all budgets and trip circuit breaker if needed."""
        status = self.get_status()
        
        if status.any_budget_exhausted:
            exhausted = status.get_exhausted_budgets()
            reason = f"Budget(s) exhausted: {', '.join(b.value for b in exhausted)}"
            self._trip_circuit_breaker(reason, exhausted)
        else:
            # Check if we can reset from cooldown
            self._maybe_reset_circuit_breaker()
        
        self._update_prometheus_metrics()
    
    def _trip_circuit_breaker(self, reason: str, exhausted_budgets: list[BudgetType]) -> None:
        """Trip the circuit breaker and enter conservative mode."""
        if not self._conservative_mode:
            self._conservative_mode = True
            self._conservative_mode_reason = reason
            self._circuit_breaker_tripped_at = utcnow()
            
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    UPDATE circuit_breaker_state 
                    SET conservative_mode = 1, reason = ?, tripped_at = ?, last_checked = ?
                    WHERE id = 1
                """, (reason, self._circuit_breaker_tripped_at.isoformat(), utcnow().isoformat()))
                conn.commit()
            
            # Record metric
            for budget in exhausted_budgets:
                CIRCUIT_BREAKER_TRIPS.labels(reason=budget.value).inc()
    
    def _maybe_reset_circuit_breaker(self) -> None:
        """Reset circuit breaker if cooldown passed and budgets recovered."""
        if not self._conservative_mode:
            return
        
        if not self._circuit_breaker_tripped_at:
            return
        
        cooldown_end = self._circuit_breaker_tripped_at + timedelta(hours=self.config.cooldown_hours)
        
        if utcnow() >= cooldown_end:
            # Cooldown passed, check if budgets recovered
            status = self.get_status()
            if not status.any_budget_exhausted:
                self.reset_conservative_mode()
    
    def reset_conservative_mode(self) -> None:
        """Manually reset conservative mode (use with caution)."""
        with self._lock:
            self._conservative_mode = False
            self._conservative_mode_reason = ""
            self._circuit_breaker_tripped_at = None
            
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    UPDATE circuit_breaker_state 
                    SET conservative_mode = 0, reason = '', tripped_at = NULL, last_checked = ?
                    WHERE id = 1
                """, (utcnow().isoformat(),))
                conn.commit()
        
        self._update_prometheus_metrics()
    
    def is_conservative_mode(self) -> bool:
        """Check if we're in conservative mode."""
        return self._conservative_mode
    
    def requires_human_approval(self) -> bool:
        """
        Check if human approval is required.
        
        In conservative mode, ALL actions require human approval.
        """
        return self._conservative_mode
    
    def _update_prometheus_metrics(self) -> None:
        """Update Prometheus gauges."""
        for budget_type in BudgetType:
            status = self.get_budget_status(budget_type)
            ERROR_BUDGET_REMAINING.labels(budget_type=budget_type.value).set(status.remaining)
            ERROR_BUDGET_EXHAUSTED.labels(budget_type=budget_type.value).set(1 if status.exhausted else 0)
        
        CONSERVATIVE_MODE_ACTIVE.set(1 if self._conservative_mode else 0)


# Singleton instance
_error_budget: Optional[AIErrorBudget] = None
_budget_lock = threading.Lock()


def get_error_budget(
    db_path: Optional[Path] = None,
    config: Optional[ErrorBudgetConfig] = None,
) -> AIErrorBudget:
    """Get the global error budget tracker instance."""
    global _error_budget
    
    with _budget_lock:
        if _error_budget is None:
            _error_budget = AIErrorBudget(db_path, config)
        return _error_budget
