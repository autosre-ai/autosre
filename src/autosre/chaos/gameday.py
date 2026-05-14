"""
Game Day Planner for chaos engineering.

Plans and coordinates game day events with multiple experiments.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import (
    GameDay,
    GameDayStatus,
    Experiment,
    ExperimentStatus,
)
from .experiment import ExperimentRunner

logger = get_logger(__name__)


class GameDayPlanner:
    """
    Plans and runs game day events.
    
    Features:
    - Schedule game days
    - Coordinate multiple experiments
    - Track participants
    - Generate reports
    
    Example:
        planner = GameDayPlanner(experiment_runner)
        
        game_day = GameDay(
            name="Q4 Resilience Test",
            scheduled_date=datetime.now() + timedelta(days=7),
            facilitator="sre-team",
        )
        
        game_day.add_experiment(api_latency_experiment)
        game_day.add_experiment(pod_failure_experiment)
        
        await planner.run(game_day)
    """
    
    def __init__(
        self,
        experiment_runner: ExperimentRunner,
    ):
        self._runner = experiment_runner
        
        # Planned game days
        self._planned: dict[UUID, GameDay] = {}
        
        # History
        self._history: list[GameDay] = []
    
    async def plan(
        self,
        game_day: GameDay,
    ) -> GameDay:
        """
        Plan a game day.
        
        Args:
            game_day: Game day to plan
            
        Returns:
            Planned game day
        """
        game_day.status = GameDayStatus.PLANNED
        self._planned[game_day.id] = game_day
        
        logger.info(
            f"Planned game day: {game_day.name} "
            f"for {game_day.scheduled_date}"
        )
        
        return game_day
    
    async def schedule(
        self,
        game_day_id: UUID,
        scheduled_date: datetime | None = None,
    ) -> bool:
        """
        Schedule a planned game day.
        
        Args:
            game_day_id: Game day ID
            scheduled_date: Override scheduled date
            
        Returns:
            True if scheduled
        """
        game_day = self._planned.get(game_day_id)
        if not game_day:
            return False
        
        if scheduled_date:
            game_day.scheduled_date = scheduled_date
        
        game_day.status = GameDayStatus.SCHEDULED
        
        logger.info(f"Scheduled game day: {game_day.name} for {game_day.scheduled_date}")
        
        # Send notifications to participants
        await self._notify_participants(
            game_day,
            f"Game Day '{game_day.name}' scheduled for {game_day.scheduled_date}",
        )
        
        return True
    
    async def run(
        self,
        game_day: GameDay,
        dry_run: bool = False,
    ) -> GameDay:
        """
        Run a game day.
        
        Args:
            game_day: Game day to run
            dry_run: Dry run mode
            
        Returns:
            Completed game day
        """
        logger.info(f"Starting game day: {game_day.name}")
        
        game_day.status = GameDayStatus.IN_PROGRESS
        game_day.started_at = datetime.utcnow()
        
        await self._notify_participants(
            game_day,
            f"🚀 Game Day '{game_day.name}' is starting!",
        )
        
        # Run experiments in order
        for exp_id in game_day.experiment_order:
            experiment = next(
                (e for e in game_day.experiments if e.id == exp_id),
                None,
            )
            
            if not experiment:
                continue
            
            logger.info(
                f"Running experiment {game_day.experiments.index(experiment) + 1}/"
                f"{len(game_day.experiments)}: {experiment.name}"
            )
            
            await self._notify_participants(
                game_day,
                f"📊 Running experiment: {experiment.name}",
            )
            
            # Run experiment
            result = await self._runner.run(experiment, dry_run=dry_run)
            
            # Notify result
            status_emoji = "✅" if result.success else "❌"
            await self._notify_participants(
                game_day,
                f"{status_emoji} Experiment '{experiment.name}': "
                f"{'PASSED' if result.success else 'FAILED'}",
            )
            
            # Pause between experiments
            pause_seconds = 60  # Configurable
            await asyncio.sleep(pause_seconds)
        
        # Calculate overall success
        game_day.overall_success = (
            game_day.successful_experiments == len(game_day.experiments)
        )
        
        game_day.status = GameDayStatus.COMPLETED
        game_day.completed_at = datetime.utcnow()
        
        # Generate findings
        game_day.findings = self._generate_findings(game_day)
        
        # Move to history
        self._planned.pop(game_day.id, None)
        self._history.append(game_day)
        
        # Final notification
        success_rate = (
            game_day.successful_experiments / len(game_day.experiments) * 100
            if game_day.experiments else 0
        )
        
        await self._notify_participants(
            game_day,
            f"🏁 Game Day '{game_day.name}' completed!\n"
            f"Success Rate: {success_rate:.0f}%\n"
            f"Duration: {self._format_duration(game_day.started_at, game_day.completed_at)}",
        )
        
        logger.info(
            f"Game day completed: {game_day.name} "
            f"({game_day.successful_experiments}/{len(game_day.experiments)} passed)"
        )
        
        return game_day
    
    async def cancel(self, game_day_id: UUID) -> bool:
        """
        Cancel a game day.
        
        Args:
            game_day_id: Game day ID
            
        Returns:
            True if cancelled
        """
        game_day = self._planned.get(game_day_id)
        if not game_day:
            return False
        
        game_day.status = GameDayStatus.CANCELLED
        
        await self._notify_participants(
            game_day,
            f"⚠️ Game Day '{game_day.name}' has been cancelled",
        )
        
        self._planned.pop(game_day_id, None)
        self._history.append(game_day)
        
        logger.info(f"Cancelled game day: {game_day.name}")
        
        return True
    
    def add_experiment(
        self,
        game_day_id: UUID,
        experiment: Experiment,
        position: int | None = None,
    ) -> bool:
        """
        Add experiment to game day.
        
        Args:
            game_day_id: Game day ID
            experiment: Experiment to add
            position: Position in order (None = end)
            
        Returns:
            True if added
        """
        game_day = self._planned.get(game_day_id)
        if not game_day:
            return False
        
        game_day.experiments.append(experiment)
        
        if position is not None:
            game_day.experiment_order.insert(position, experiment.id)
        else:
            game_day.experiment_order.append(experiment.id)
        
        return True
    
    def remove_experiment(
        self,
        game_day_id: UUID,
        experiment_id: UUID,
    ) -> bool:
        """
        Remove experiment from game day.
        
        Args:
            game_day_id: Game day ID
            experiment_id: Experiment ID
            
        Returns:
            True if removed
        """
        game_day = self._planned.get(game_day_id)
        if not game_day:
            return False
        
        game_day.experiments = [
            e for e in game_day.experiments if e.id != experiment_id
        ]
        game_day.experiment_order = [
            eid for eid in game_day.experiment_order if eid != experiment_id
        ]
        
        return True
    
    def get_planned(self) -> list[GameDay]:
        """Get all planned game days."""
        return list(self._planned.values())
    
    def get_upcoming(self, days: int = 30) -> list[GameDay]:
        """Get upcoming game days within specified days."""
        cutoff = datetime.utcnow() + timedelta(days=days)
        return [
            gd for gd in self._planned.values()
            if gd.scheduled_date <= cutoff
        ]
    
    def get_history(self, limit: int = 50) -> list[GameDay]:
        """Get game day history."""
        return self._history[-limit:]
    
    async def _notify_participants(
        self,
        game_day: GameDay,
        message: str,
    ) -> None:
        """Send notification to participants."""
        # Integration with Slack, PagerDuty, etc.
        logger.info(f"[NOTIFY] {message}")
        
        if game_day.slack_channel:
            # Send to Slack
            pass
    
    def _generate_findings(self, game_day: GameDay) -> list[str]:
        """Generate findings from game day results."""
        findings = []
        
        for experiment in game_day.experiments:
            if not experiment.result:
                continue
            
            result = experiment.result
            
            if not result.success:
                findings.append(
                    f"❌ {experiment.name}: {result.message}"
                )
            
            if not result.steady_state_met_during:
                findings.append(
                    f"⚠️ {experiment.name}: Steady state violated during fault"
                )
            
            if result.was_rolled_back:
                findings.append(
                    f"🔄 {experiment.name}: Required rollback"
                )
        
        if not findings:
            findings.append("✅ All experiments passed without issues")
        
        return findings
    
    def _format_duration(
        self,
        start: datetime | None,
        end: datetime | None,
    ) -> str:
        """Format duration between two times."""
        if not start or not end:
            return "Unknown"
        
        duration = end - start
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    
    def generate_schedule(
        self,
        game_day: GameDay,
    ) -> str:
        """Generate schedule for game day."""
        lines = [
            f"# {game_day.name}",
            "",
            f"**Date:** {game_day.scheduled_date.strftime('%Y-%m-%d %H:%M')}",
            f"**Facilitator:** {game_day.facilitator or 'TBD'}",
            f"**Estimated Duration:** {game_day.estimated_duration_hours}h",
            "",
            "## Experiments",
            "",
        ]
        
        current_time = game_day.scheduled_date
        
        for i, exp_id in enumerate(game_day.experiment_order):
            experiment = next(
                (e for e in game_day.experiments if e.id == exp_id),
                None,
            )
            
            if not experiment:
                continue
            
            duration_min = experiment.total_duration_seconds / 60
            
            lines.append(
                f"{i+1}. **{experiment.name}** "
                f"({current_time.strftime('%H:%M')} - "
                f"{duration_min:.0f}min)"
            )
            lines.append(f"   - {experiment.description}")
            lines.append(f"   - Faults: {experiment.get_fault_summary()}")
            lines.append("")
            
            current_time += timedelta(seconds=experiment.total_duration_seconds)
            current_time += timedelta(minutes=5)  # Buffer
        
        lines.extend([
            "## Participants",
            "",
        ])
        
        for participant in game_day.participants:
            lines.append(f"- {participant}")
        
        return "\n".join(lines)
