"""
Evaluation Framework Core - Run scenarios and track results.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field
import yaml

from autosre.logging import get_logger

logger = get_logger(__name__)


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Scenario(BaseModel):
    """A synthetic incident scenario for evaluation."""
    id: str = Field(default="", description="Unique scenario ID")
    name: str = Field(..., description="Scenario identifier")
    description: str = Field(..., description="What this scenario tests")
    difficulty: str = Field(default="medium", description="easy/medium/hard")
    
    # Setup
    setup_steps: list[str] = Field(default_factory=list, description="Steps to set up the scenario")
    
    # Alert data
    alert: dict = Field(default_factory=dict, description="The alert that triggers investigation")
    
    # Context data (simulated)
    services: list[dict] = Field(default_factory=list, description="Services in the scenario")
    changes: list[dict] = Field(default_factory=list, description="Recent changes")
    metrics: dict = Field(default_factory=dict, description="Metric data")
    
    # Expected outcomes
    expected_root_cause: str = Field(..., description="The correct root cause")
    expected_service: Optional[str] = Field(None, description="Expected affected service")
    expected_runbook: Optional[str] = Field(None, description="Expected runbook to suggest")
    expected_action: Optional[str] = Field(None, description="Expected remediation action")
    
    # Time limits
    max_time_seconds: int = Field(default=300, description="Maximum time for analysis")


class ScenarioResult(BaseModel):
    """Result of running a scenario."""
    scenario: str
    success: bool
    run_at: datetime = Field(default_factory=utcnow)
    
    # Metrics
    time_to_root_cause: Optional[float] = Field(None, description="Seconds to identify root cause")
    root_cause_correct: bool = Field(default=False)
    service_correct: bool = Field(default=False)
    runbook_correct: bool = Field(default=False)
    action_correct: bool = Field(default=False)
    
    # Agent output
    agent_root_cause: Optional[str] = None
    agent_confidence: Optional[float] = None
    agent_reasoning: Optional[str] = None
    
    # Computed accuracy
    accuracy: float = Field(default=0.0)
    
    def compute_accuracy(self) -> float:
        """Compute overall accuracy score."""
        scores = [
            self.root_cause_correct,
            self.service_correct,
            self.runbook_correct,
            self.action_correct,
        ]
        valid_scores = [s for s in scores if s is not None]
        if not valid_scores:
            return 0.0
        return sum(valid_scores) / len(valid_scores)
    
    @property
    def score(self) -> float:
        """Alias for accuracy."""
        return self.accuracy
    
    @property
    def passed(self) -> bool:
        """Whether the scenario passed."""
        return self.success
    
    @property
    def errors(self) -> list[str]:
        """List of errors, if any."""
        return []  # Placeholder
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return self.model_dump()


class EvalStore:
    """SQLite storage for evaluation results."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / ".autosre" / "evals.db")
        
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS eval_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    run_at TEXT NOT NULL,
                    time_to_root_cause REAL,
                    root_cause_correct INTEGER,
                    service_correct INTEGER,
                    runbook_correct INTEGER,
                    action_correct INTEGER,
                    agent_root_cause TEXT,
                    agent_confidence REAL,
                    agent_reasoning TEXT,
                    accuracy REAL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_eval_scenario ON eval_results(scenario)
            """)
    
    def save_result(self, result: ScenarioResult) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO eval_results
                (scenario, success, run_at, time_to_root_cause, root_cause_correct,
                 service_correct, runbook_correct, action_correct, agent_root_cause,
                 agent_confidence, agent_reasoning, accuracy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.scenario,
                1 if result.success else 0,
                result.run_at.isoformat(),
                result.time_to_root_cause,
                1 if result.root_cause_correct else 0,
                1 if result.service_correct else 0,
                1 if result.runbook_correct else 0,
                1 if result.action_correct else 0,
                result.agent_root_cause,
                result.agent_confidence,
                result.agent_reasoning,
                result.accuracy,
            ))
    
    def get_results(self, scenario: Optional[str] = None, limit: int = 100) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if scenario:
                rows = conn.execute(
                    "SELECT * FROM eval_results WHERE scenario = ? ORDER BY run_at DESC LIMIT ?",
                    (scenario, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM eval_results ORDER BY run_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_scenario_stats(self, scenario: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total_runs,
                    SUM(success) as successful_runs,
                    AVG(accuracy) as avg_accuracy,
                    AVG(time_to_root_cause) as avg_time
                FROM eval_results WHERE scenario = ?
            """, (scenario,)).fetchone()
            
            return {
                "scenario": scenario,
                "total_runs": row[0],
                "successful_runs": row[1],
                "success_rate": row[1] / row[0] if row[0] > 0 else 0,
                "avg_accuracy": row[2],
                "avg_time_to_root_cause": row[3],
            }


# Global store
_eval_store: Optional[EvalStore] = None


def get_eval_store() -> EvalStore:
    global _eval_store
    if _eval_store is None:
        _eval_store = EvalStore()
    return _eval_store


def load_scenario(name: str) -> Optional[Scenario]:
    """Load a scenario by name."""
    logger.debug("Loading scenario", scenario=name)
    
    # Check built-in scenarios
    scenarios_dir = Path(__file__).parent / "scenarios"
    
    for path in scenarios_dir.glob("*.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
            if data.get("name") == name:
                logger.debug("Found scenario", path=str(path))
                return Scenario(**data)
    
    # Check custom scenarios directory
    custom_dir = Path.home() / ".autosre" / "scenarios"
    if custom_dir.exists():
        for path in custom_dir.glob("*.yaml"):
            with open(path) as f:
                data = yaml.safe_load(f)
                if data.get("name") == name:
                    return Scenario(**data)
    
    return None


def list_scenarios() -> list[dict]:
    """List all available scenarios."""
    scenarios = []
    
    # Built-in scenarios
    scenarios_dir = Path(__file__).parent / "scenarios"
    if scenarios_dir.exists():
        for path in scenarios_dir.glob("*.yaml"):
            with open(path) as f:
                data = yaml.safe_load(f)
                scenarios.append({
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "difficulty": data.get("difficulty", "medium"),
                })
    
    # Custom scenarios
    custom_dir = Path.home() / ".autosre" / "scenarios"
    if custom_dir.exists():
        for path in custom_dir.glob("*.yaml"):
            with open(path) as f:
                data = yaml.safe_load(f)
                scenarios.append({
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "difficulty": data.get("difficulty", "medium"),
                    "custom": True,
                })
    
    return scenarios


async def run_scenario(name: str, verbose: bool = False) -> dict:
    """
    Run a scenario and evaluate the agent's response.
    
    Args:
        name: Scenario name
        verbose: Print detailed output
        
    Returns:
        Dict with results and metrics
    """
    import time
    
    logger.info("Running scenario", scenario=name, verbose=verbose)
    
    scenario = load_scenario(name)
    if not scenario:
        logger.warning("Scenario not found", scenario=name)
        return {
            "success": False,
            "error": f"Scenario '{name}' not found",
            "metrics": {},
        }
    
    start_time = time.time()
    logger.debug("Scenario loaded", difficulty=scenario.difficulty)
    
    # TODO: Actually run the agent against the scenario
    # For now, return a stub result
    
    result = ScenarioResult(
        scenario=name,
        success=False,  # Will be True when agent is implemented
        time_to_root_cause=time.time() - start_time,
        root_cause_correct=False,
        service_correct=False,
        runbook_correct=False,
        action_correct=False,
        agent_root_cause="Agent not yet implemented",
        agent_confidence=0.0,
        agent_reasoning="This is a placeholder - agent implementation coming soon",
    )
    
    result.accuracy = result.compute_accuracy()
    
    # Save result
    get_eval_store().save_result(result)
    logger.info("Scenario completed", scenario=name, accuracy=result.accuracy)
    
    return {
        "success": result.success,
        "metrics": {
            "time_to_root_cause": result.time_to_root_cause,
            "accuracy": result.accuracy,
            "root_cause_correct": result.root_cause_correct,
            "service_correct": result.service_correct,
        },
        "agent_output": {
            "root_cause": result.agent_root_cause,
            "confidence": result.agent_confidence,
            "reasoning": result.agent_reasoning,
        },
    }

def get_results(scenario: Optional[str] = None, limit: int = 100) -> list[dict]:
    """Get evaluation results."""
    return get_eval_store().get_results(scenario=scenario, limit=limit)


def get_all_scenarios() -> list[Scenario]:
    """Get all available scenarios as Scenario objects."""
    scenarios = []
    
    # Built-in scenarios
    scenarios_dir = Path(__file__).parent / "scenarios"
    if scenarios_dir.exists():
        for path in scenarios_dir.glob("*.yaml"):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                    if data:
                        # Add id field from filename if not present
                        if "id" not in data:
                            data["id"] = path.stem
                        scenarios.append(Scenario(**data))
            except Exception:
                pass  # Skip invalid files
    
    # Custom scenarios
    custom_dir = Path.home() / ".autosre" / "scenarios"
    if custom_dir.exists():
        for path in custom_dir.glob("*.yaml"):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                    if data:
                        if "id" not in data:
                            data["id"] = path.stem
                        scenarios.append(Scenario(**data))
            except Exception:
                pass
    
    return scenarios


def get_scenario(scenario_id: str) -> Optional[Scenario]:
    """Get a specific scenario by ID."""
    for scenario in get_all_scenarios():
        if getattr(scenario, 'id', scenario.name) == scenario_id:
            return scenario
    return None


class EvalRunner:
    """Runner for evaluation scenarios."""
    
    def __init__(self):
        self.store = get_eval_store()
    
    def run_scenario(self, scenario: Scenario) -> ScenarioResult:
        """Run a single scenario and return results."""
        import time
        
        start_time = time.time()
        
        # TODO: Actually run the agent against the scenario
        # For now, return a stub result
        result = ScenarioResult(
            scenario=scenario.name,
            success=False,
            time_to_root_cause=time.time() - start_time,
            root_cause_correct=False,
            service_correct=False,
            runbook_correct=False,
            action_correct=False,
            agent_root_cause="Agent not yet implemented",
            agent_confidence=0.0,
            agent_reasoning="Placeholder - agent implementation coming soon",
        )
        
        result.accuracy = result.compute_accuracy()
        self.store.save_result(result)
        
        return result
    
    def run_all(self) -> list[ScenarioResult]:
        """Run all scenarios and return results."""
        results = []
        for scenario in get_all_scenarios():
            results.append(self.run_scenario(scenario))
        return results
