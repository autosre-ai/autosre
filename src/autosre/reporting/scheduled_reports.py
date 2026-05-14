"""Scheduled Reports for AutoSRE V2.

Provides automated report scheduling and delivery:
- Cron-based scheduling
- Multiple delivery channels
- Report templates
- Delivery tracking
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class DeliveryChannel(str, Enum):
    """Report delivery channels."""
    
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    S3 = "s3"
    GCS = "gcs"
    WEBHOOK = "webhook"


class ScheduleFrequency(str, Enum):
    """Report schedule frequencies."""
    
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"  # Uses cron expression


class ReportStatus(str, Enum):
    """Report execution status."""
    
    PENDING = "pending"
    GENERATING = "generating"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ScheduleConfig:
    """Configuration for report scheduling."""
    
    # Schedule type
    frequency: ScheduleFrequency = ScheduleFrequency.DAILY
    
    # For custom frequency
    cron_expression: Optional[str] = None  # e.g., "0 9 * * MON"
    
    # Time settings
    hour: int = 9  # 24-hour format
    minute: int = 0
    day_of_week: Optional[int] = None  # 0=Monday for weekly
    day_of_month: Optional[int] = None  # 1-31 for monthly
    
    # Timezone
    timezone: str = "UTC"
    
    # Constraints
    skip_weekends: bool = False
    skip_holidays: bool = False
    
    def next_run(self, after: datetime = None) -> datetime:
        """Calculate next run time.
        
        Args:
            after: Calculate next run after this time
            
        Returns:
            Next run datetime
        """
        import zoneinfo
        
        tz = zoneinfo.ZoneInfo(self.timezone)
        now = after or datetime.now(tz)
        
        if self.frequency == ScheduleFrequency.HOURLY:
            next_time = now.replace(minute=self.minute, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(hours=1)
            return next_time
        
        elif self.frequency == ScheduleFrequency.DAILY:
            next_time = now.replace(
                hour=self.hour,
                minute=self.minute,
                second=0,
                microsecond=0,
            )
            if next_time <= now:
                next_time += timedelta(days=1)
            
            if self.skip_weekends:
                while next_time.weekday() >= 5:  # Saturday=5, Sunday=6
                    next_time += timedelta(days=1)
            
            return next_time
        
        elif self.frequency == ScheduleFrequency.WEEKLY:
            next_time = now.replace(
                hour=self.hour,
                minute=self.minute,
                second=0,
                microsecond=0,
            )
            
            target_day = self.day_of_week or 0  # Default to Monday
            days_ahead = target_day - now.weekday()
            if days_ahead <= 0 or (days_ahead == 0 and next_time <= now):
                days_ahead += 7
            
            next_time += timedelta(days=days_ahead)
            return next_time
        
        elif self.frequency == ScheduleFrequency.MONTHLY:
            target_day = self.day_of_month or 1
            
            # Try this month first
            try:
                next_time = now.replace(
                    day=target_day,
                    hour=self.hour,
                    minute=self.minute,
                    second=0,
                    microsecond=0,
                )
            except ValueError:
                # Day doesn't exist in this month, try next month
                if now.month == 12:
                    next_time = now.replace(
                        year=now.year + 1,
                        month=1,
                        day=target_day,
                        hour=self.hour,
                        minute=self.minute,
                        second=0,
                        microsecond=0,
                    )
                else:
                    next_time = now.replace(
                        month=now.month + 1,
                        day=target_day,
                        hour=self.hour,
                        minute=self.minute,
                        second=0,
                        microsecond=0,
                    )
            
            if next_time <= now:
                if now.month == 12:
                    next_time = now.replace(
                        year=now.year + 1,
                        month=1,
                        day=target_day,
                        hour=self.hour,
                        minute=self.minute,
                        second=0,
                        microsecond=0,
                    )
                else:
                    next_time = now.replace(
                        month=now.month + 1,
                        day=target_day,
                        hour=self.hour,
                        minute=self.minute,
                        second=0,
                        microsecond=0,
                    )
            
            return next_time
        
        elif self.frequency == ScheduleFrequency.CUSTOM and self.cron_expression:
            # Parse cron expression
            # For full cron support, would use croniter library
            # Simplified implementation for common cases
            return self._parse_cron_next(now)
        
        # Default: next day at configured time
        next_time = now.replace(
            hour=self.hour,
            minute=self.minute,
            second=0,
            microsecond=0,
        )
        if next_time <= now:
            next_time += timedelta(days=1)
        return next_time
    
    def _parse_cron_next(self, after: datetime) -> datetime:
        """Simple cron parser for common expressions."""
        # Would need croniter for full implementation
        # For now, fall back to daily
        next_time = after.replace(
            hour=self.hour,
            minute=self.minute,
            second=0,
            microsecond=0,
        )
        if next_time <= after:
            next_time += timedelta(days=1)
        return next_time


class DeliveryConfig(BaseModel):
    """Configuration for report delivery."""
    
    channel: DeliveryChannel
    
    # Email settings
    email_recipients: List[str] = Field(default_factory=list)
    email_cc: List[str] = Field(default_factory=list)
    email_subject: Optional[str] = None
    
    # Slack settings
    slack_channel: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    
    # Teams settings
    teams_webhook_url: Optional[str] = None
    
    # S3 settings
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = None
    s3_region: Optional[str] = None
    
    # GCS settings
    gcs_bucket: Optional[str] = None
    gcs_prefix: Optional[str] = None
    
    # Webhook settings
    webhook_url: Optional[str] = None
    webhook_headers: Dict[str, str] = Field(default_factory=dict)
    
    # Common options
    include_attachment: bool = True
    attachment_format: str = "pdf"  # pdf, html, csv


class ReportSchedule(BaseModel):
    """A scheduled report configuration."""
    
    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    
    # Report configuration
    report_type: str  # incident, slo, security, cost
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # Schedule
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    
    # Delivery
    deliveries: List[DeliveryConfig] = Field(default_factory=list)
    
    # Tenant
    tenant_id: Optional[str] = None
    
    # Status
    enabled: bool = True
    
    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    
    # Stats
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    
    # Created by
    created_by: Optional[str] = None
    
    def calculate_next_run(self) -> datetime:
        """Calculate and set next run time."""
        after = self.last_run_at or datetime.now(timezone.utc)
        self.next_run_at = self.schedule.next_run(after)
        return self.next_run_at


class ReportDelivery(BaseModel):
    """Record of a report delivery."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Schedule reference
    schedule_id: str
    schedule_name: str
    
    # Execution
    status: ReportStatus = ReportStatus.PENDING
    
    # Timing
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Report details
    report_type: str
    report_path: Optional[str] = None  # Path to generated report
    report_size_bytes: Optional[int] = None
    
    # Delivery results
    delivery_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    # channel_name -> {"status": "success/failed", "details": {...}}
    
    # Error tracking
    error: Optional[str] = None
    retry_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def mark_started(self) -> None:
        """Mark delivery as started."""
        self.status = ReportStatus.GENERATING
        self.started_at = datetime.now(timezone.utc)
    
    def mark_generating(self) -> None:
        """Mark as generating report."""
        self.status = ReportStatus.GENERATING
    
    def mark_delivering(self) -> None:
        """Mark as delivering report."""
        self.status = ReportStatus.DELIVERING
    
    def mark_completed(self) -> None:
        """Mark as completed."""
        self.status = ReportStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
    
    def mark_failed(self, error: str) -> None:
        """Mark as failed."""
        self.status = ReportStatus.FAILED
        self.error = error
        self.completed_at = datetime.now(timezone.utc)
    
    def add_delivery_result(
        self,
        channel: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add delivery result for a channel."""
        self.delivery_results[channel] = {
            "status": "success" if success else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(details or {}),
        }
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Get execution duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# Type for report generators
ReportGenerator = Callable[[str, Dict[str, Any]], Awaitable[bytes]]

# Type for delivery handlers
DeliveryHandler = Callable[[bytes, DeliveryConfig], Awaitable[Dict[str, Any]]]


class ScheduledReports:
    """
    Scheduled report management and execution.
    
    Provides:
    - Schedule CRUD operations
    - Report generation and delivery
    - Delivery channel management
    - Execution tracking
    
    Example:
        scheduler = ScheduledReports()
        
        # Register report generators
        scheduler.register_generator("incident", incident_report_generator)
        scheduler.register_generator("slo", slo_report_generator)
        
        # Register delivery handlers
        scheduler.register_delivery_handler(
            DeliveryChannel.EMAIL,
            email_delivery_handler,
        )
        
        # Create schedule
        schedule = ReportSchedule(
            name="Weekly Incident Report",
            report_type="incident",
            schedule=ScheduleConfig(
                frequency=ScheduleFrequency.WEEKLY,
                day_of_week=0,  # Monday
                hour=9,
            ),
            deliveries=[
                DeliveryConfig(
                    channel=DeliveryChannel.EMAIL,
                    email_recipients=["team@company.com"],
                ),
            ],
        )
        
        await scheduler.create_schedule(schedule)
        
        # Start scheduler
        await scheduler.start()
    """
    
    def __init__(
        self,
        check_interval_seconds: float = 60.0,
        max_concurrent_reports: int = 5,
        retry_failed: bool = True,
        max_retries: int = 3,
    ):
        """Initialize ScheduledReports.
        
        Args:
            check_interval_seconds: How often to check for due reports
            max_concurrent_reports: Maximum concurrent report generation
            retry_failed: Whether to retry failed deliveries
            max_retries: Maximum retry attempts
        """
        self.check_interval = check_interval_seconds
        self.max_concurrent = max_concurrent_reports
        self.retry_failed = retry_failed
        self.max_retries = max_retries
        
        self._schedules: Dict[str, ReportSchedule] = {}
        self._deliveries: List[ReportDelivery] = []
        
        self._generators: Dict[str, ReportGenerator] = {}
        self._delivery_handlers: Dict[DeliveryChannel, DeliveryHandler] = {}
        
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        self._lock = asyncio.Lock()
    
    # Generator Registration
    
    def register_generator(
        self,
        report_type: str,
        generator: ReportGenerator,
    ) -> None:
        """Register a report generator.
        
        Args:
            report_type: Report type identifier
            generator: Async function that generates report bytes
        """
        self._generators[report_type] = generator
        
        logger.info(
            "Registered report generator",
            report_type=report_type,
        )
    
    def unregister_generator(self, report_type: str) -> bool:
        """Unregister a report generator.
        
        Args:
            report_type: Report type identifier
            
        Returns:
            True if removed
        """
        if report_type in self._generators:
            del self._generators[report_type]
            return True
        return False
    
    # Delivery Handler Registration
    
    def register_delivery_handler(
        self,
        channel: DeliveryChannel,
        handler: DeliveryHandler,
    ) -> None:
        """Register a delivery handler.
        
        Args:
            channel: Delivery channel
            handler: Async function that delivers report
        """
        self._delivery_handlers[channel] = handler
        
        logger.info(
            "Registered delivery handler",
            channel=channel.value,
        )
    
    def unregister_delivery_handler(self, channel: DeliveryChannel) -> bool:
        """Unregister a delivery handler.
        
        Args:
            channel: Delivery channel
            
        Returns:
            True if removed
        """
        if channel in self._delivery_handlers:
            del self._delivery_handlers[channel]
            return True
        return False
    
    # Schedule Management
    
    async def create_schedule(
        self,
        schedule: ReportSchedule,
    ) -> ReportSchedule:
        """Create a report schedule.
        
        Args:
            schedule: Schedule to create
            
        Returns:
            Created schedule
        """
        async with self._lock:
            # Validate report type
            if schedule.report_type not in self._generators:
                logger.warning(
                    "Report type has no generator",
                    report_type=schedule.report_type,
                )
            
            # Calculate initial next run
            schedule.calculate_next_run()
            
            # Store
            self._schedules[schedule.id] = schedule
            
            logger.info(
                "Created report schedule",
                schedule_id=schedule.id,
                name=schedule.name,
                next_run=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
            )
            
            return schedule
    
    async def get_schedule(self, schedule_id: str) -> Optional[ReportSchedule]:
        """Get a schedule by ID.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            ReportSchedule or None
        """
        return self._schedules.get(schedule_id)
    
    async def list_schedules(
        self,
        tenant_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[ReportSchedule]:
        """List schedules.
        
        Args:
            tenant_id: Filter by tenant
            enabled_only: Only return enabled schedules
            
        Returns:
            List of schedules
        """
        schedules = list(self._schedules.values())
        
        if tenant_id:
            schedules = [s for s in schedules if s.tenant_id == tenant_id]
        
        if enabled_only:
            schedules = [s for s in schedules if s.enabled]
        
        return schedules
    
    async def update_schedule(
        self,
        schedule_id: str,
        updates: Dict[str, Any],
    ) -> Optional[ReportSchedule]:
        """Update a schedule.
        
        Args:
            schedule_id: Schedule ID
            updates: Fields to update
            
        Returns:
            Updated schedule or None
        """
        async with self._lock:
            schedule = self._schedules.get(schedule_id)
            if not schedule:
                return None
            
            for key, value in updates.items():
                if hasattr(schedule, key):
                    setattr(schedule, key, value)
            
            schedule.updated_at = datetime.now(timezone.utc)
            
            # Recalculate next run if schedule changed
            if "schedule" in updates:
                schedule.calculate_next_run()
            
            logger.info(
                "Updated report schedule",
                schedule_id=schedule_id,
            )
            
            return schedule
    
    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            True if deleted
        """
        async with self._lock:
            if schedule_id in self._schedules:
                del self._schedules[schedule_id]
                
                logger.info(
                    "Deleted report schedule",
                    schedule_id=schedule_id,
                )
                
                return True
            return False
    
    async def enable_schedule(self, schedule_id: str) -> bool:
        """Enable a schedule.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            True if enabled
        """
        schedule = self._schedules.get(schedule_id)
        if schedule:
            schedule.enabled = True
            schedule.calculate_next_run()
            return True
        return False
    
    async def disable_schedule(self, schedule_id: str) -> bool:
        """Disable a schedule.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            True if disabled
        """
        schedule = self._schedules.get(schedule_id)
        if schedule:
            schedule.enabled = False
            return True
        return False
    
    # Execution
    
    async def run_schedule_now(
        self,
        schedule_id: str,
    ) -> Optional[ReportDelivery]:
        """Run a schedule immediately.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            ReportDelivery or None
        """
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None
        
        return await self._execute_schedule(schedule)
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info(
            "Started report scheduler",
            check_interval=self.check_interval,
        )
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None
        
        logger.info("Stopped report scheduler")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_due_schedules()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "Scheduler loop error",
                    error=str(e),
                )
                await asyncio.sleep(self.check_interval)
    
    async def _check_due_schedules(self) -> None:
        """Check and execute due schedules."""
        now = datetime.now(timezone.utc)
        
        for schedule in list(self._schedules.values()):
            if not schedule.enabled:
                continue
            
            if not schedule.next_run_at:
                schedule.calculate_next_run()
                continue
            
            if schedule.next_run_at <= now:
                # Execute in background
                asyncio.create_task(
                    self._execute_schedule_with_semaphore(schedule)
                )
    
    async def _execute_schedule_with_semaphore(
        self,
        schedule: ReportSchedule,
    ) -> Optional[ReportDelivery]:
        """Execute schedule with concurrency control."""
        async with self._semaphore:
            return await self._execute_schedule(schedule)
    
    async def _execute_schedule(
        self,
        schedule: ReportSchedule,
    ) -> Optional[ReportDelivery]:
        """Execute a schedule.
        
        Args:
            schedule: Schedule to execute
            
        Returns:
            ReportDelivery
        """
        # Create delivery record
        delivery = ReportDelivery(
            schedule_id=schedule.id,
            schedule_name=schedule.name,
            scheduled_at=schedule.next_run_at or datetime.now(timezone.utc),
            report_type=schedule.report_type,
        )
        
        delivery.mark_started()
        
        try:
            # Get generator
            generator = self._generators.get(schedule.report_type)
            if not generator:
                raise ValueError(f"No generator for report type: {schedule.report_type}")
            
            # Generate report
            logger.info(
                "Generating report",
                schedule_id=schedule.id,
                report_type=schedule.report_type,
            )
            
            report_bytes = await generator(schedule.report_type, schedule.parameters)
            delivery.report_size_bytes = len(report_bytes)
            
            # Deliver to all channels
            delivery.mark_delivering()
            
            for config in schedule.deliveries:
                handler = self._delivery_handlers.get(config.channel)
                
                if not handler:
                    delivery.add_delivery_result(
                        config.channel.value,
                        False,
                        {"error": f"No handler for channel: {config.channel.value}"},
                    )
                    continue
                
                try:
                    result = await handler(report_bytes, config)
                    delivery.add_delivery_result(
                        config.channel.value,
                        True,
                        result,
                    )
                except Exception as e:
                    delivery.add_delivery_result(
                        config.channel.value,
                        False,
                        {"error": str(e)},
                    )
            
            # Check if all deliveries succeeded
            all_success = all(
                r.get("status") == "success"
                for r in delivery.delivery_results.values()
            )
            
            if all_success:
                delivery.mark_completed()
                schedule.successful_runs += 1
            else:
                delivery.mark_failed("Some deliveries failed")
                schedule.failed_runs += 1
            
        except Exception as e:
            logger.error(
                "Report execution failed",
                schedule_id=schedule.id,
                error=str(e),
            )
            delivery.mark_failed(str(e))
            schedule.failed_runs += 1
        
        # Update schedule
        schedule.last_run_at = datetime.now(timezone.utc)
        schedule.total_runs += 1
        schedule.calculate_next_run()
        
        # Store delivery
        self._deliveries.append(delivery)
        
        # Trim delivery history
        if len(self._deliveries) > 1000:
            self._deliveries = self._deliveries[-1000:]
        
        return delivery
    
    # Delivery History
    
    async def get_delivery(self, delivery_id: str) -> Optional[ReportDelivery]:
        """Get a delivery record.
        
        Args:
            delivery_id: Delivery ID
            
        Returns:
            ReportDelivery or None
        """
        for delivery in self._deliveries:
            if delivery.id == delivery_id:
                return delivery
        return None
    
    async def list_deliveries(
        self,
        schedule_id: Optional[str] = None,
        status: Optional[ReportStatus] = None,
        limit: int = 100,
    ) -> List[ReportDelivery]:
        """List delivery records.
        
        Args:
            schedule_id: Filter by schedule
            status: Filter by status
            limit: Maximum results
            
        Returns:
            List of deliveries
        """
        deliveries = list(reversed(self._deliveries))  # Most recent first
        
        if schedule_id:
            deliveries = [d for d in deliveries if d.schedule_id == schedule_id]
        
        if status:
            deliveries = [d for d in deliveries if d.status == status]
        
        return deliveries[:limit]
    
    async def get_schedule_stats(
        self,
        schedule_id: str,
    ) -> Dict[str, Any]:
        """Get statistics for a schedule.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            Statistics dict
        """
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return {}
        
        deliveries = [
            d for d in self._deliveries
            if d.schedule_id == schedule_id
        ]
        
        successful = [d for d in deliveries if d.status == ReportStatus.COMPLETED]
        failed = [d for d in deliveries if d.status == ReportStatus.FAILED]
        
        durations = [
            d.duration_seconds
            for d in successful
            if d.duration_seconds is not None
        ]
        
        return {
            "schedule_id": schedule_id,
            "schedule_name": schedule.name,
            "enabled": schedule.enabled,
            "total_runs": schedule.total_runs,
            "successful_runs": schedule.successful_runs,
            "failed_runs": schedule.failed_runs,
            "success_rate": (
                schedule.successful_runs / schedule.total_runs
                if schedule.total_runs > 0 else 0
            ),
            "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
            "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
            "avg_duration_seconds": (
                sum(durations) / len(durations) if durations else None
            ),
            "recent_deliveries": len(deliveries),
        }
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
