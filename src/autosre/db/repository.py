"""Repository Pattern for Database Operations.

Provides CRUD operations for all models using async SQLAlchemy 2.0 patterns.
Each repository handles a specific model type with common operations.
"""

from datetime import datetime
from typing import Generic, TypeVar, Type, Optional, List, Any, Sequence

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from autosre.db.models import (
    Base,
    AlertModel,
    InvestigationModel,
    ObservationModel,
    ActionModel,
    RunbookModel,
    ChatMessageModel,
)


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Base repository with common CRUD operations.
    
    Provides async-friendly database operations using SQLAlchemy 2.0 patterns.
    """
    
    def __init__(self, session: AsyncSession, model: Type[ModelT]):
        self.session = session
        self.model = model
    
    async def get(self, id: str) -> Optional[ModelT]:
        """Get a single entity by ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_many(self, ids: List[str]) -> Sequence[ModelT]:
        """Get multiple entities by IDs."""
        result = await self.session.execute(
            select(self.model).where(self.model.id.in_(ids))
        )
        return result.scalars().all()
    
    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        desc: bool = True,
    ) -> Sequence[ModelT]:
        """List entities with pagination."""
        query = select(self.model)
        
        if order_by and hasattr(self.model, order_by):
            column = getattr(self.model, order_by)
            query = query.order_by(column.desc() if desc else column.asc())
        elif hasattr(self.model, "created_at"):
            query = query.order_by(
                self.model.created_at.desc() if desc else self.model.created_at.asc()
            )
        
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def create(self, entity: ModelT) -> ModelT:
        """Create a new entity."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity
    
    async def create_many(self, entities: List[ModelT]) -> List[ModelT]:
        """Create multiple entities."""
        self.session.add_all(entities)
        await self.session.flush()
        for entity in entities:
            await self.session.refresh(entity)
        return entities
    
    async def update(self, id: str, **kwargs) -> Optional[ModelT]:
        """Update an entity by ID."""
        # Filter out None values unless explicitly setting to None
        updates = {k: v for k, v in kwargs.items() if v is not None}
        
        if hasattr(self.model, "updated_at"):
            updates["updated_at"] = datetime.utcnow()
        
        await self.session.execute(
            update(self.model).where(self.model.id == id).values(**updates)
        )
        await self.session.flush()
        return await self.get(id)
    
    async def delete(self, id: str) -> bool:
        """Delete an entity by ID."""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.session.flush()
        return result.rowcount > 0
    
    async def count(self) -> int:
        """Count total entities."""
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()
    
    async def exists(self, id: str) -> bool:
        """Check if an entity exists."""
        result = await self.session.execute(
            select(func.count()).where(self.model.id == id)
        )
        return result.scalar_one() > 0


class AlertRepository(BaseRepository[AlertModel]):
    """Repository for Alert operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, AlertModel)
    
    async def get_with_investigations(self, id: str) -> Optional[AlertModel]:
        """Get alert with all related investigations loaded."""
        result = await self.session.execute(
            select(AlertModel)
            .options(selectinload(AlertModel.investigations))
            .where(AlertModel.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_external_id(self, external_id: str) -> Optional[AlertModel]:
        """Get alert by external system ID."""
        result = await self.session.execute(
            select(AlertModel).where(AlertModel.external_id == external_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_fingerprint(self, fingerprint: str) -> Optional[AlertModel]:
        """Get alert by fingerprint."""
        result = await self.session.execute(
            select(AlertModel).where(AlertModel.fingerprint == fingerprint)
        )
        return result.scalar_one_or_none()
    
    async def list_active(
        self,
        severity: Optional[str] = None,
        source: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[AlertModel]:
        """List active alerts with optional filters."""
        query = select(AlertModel).where(AlertModel.status == "active")
        
        if severity:
            query = query.where(AlertModel.severity == severity)
        if source:
            query = query.where(AlertModel.source == source)
        
        query = query.order_by(AlertModel.starts_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def list_by_status(
        self,
        status: str,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[AlertModel]:
        """List alerts by status."""
        result = await self.session.execute(
            select(AlertModel)
            .where(AlertModel.status == status)
            .order_by(AlertModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def count_by_severity(self) -> dict[str, int]:
        """Get count of active alerts grouped by severity."""
        result = await self.session.execute(
            select(AlertModel.severity, func.count())
            .where(AlertModel.status == "active")
            .group_by(AlertModel.severity)
        )
        return dict(result.all())


class InvestigationRepository(BaseRepository[InvestigationModel]):
    """Repository for Investigation operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, InvestigationModel)
    
    async def get_full(self, id: str) -> Optional[InvestigationModel]:
        """Get investigation with all related data loaded."""
        result = await self.session.execute(
            select(InvestigationModel)
            .options(
                selectinload(InvestigationModel.alert),
                selectinload(InvestigationModel.observations),
                selectinload(InvestigationModel.actions),
                selectinload(InvestigationModel.chat_messages),
                selectinload(InvestigationModel.runbook),
            )
            .where(InvestigationModel.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_alert(
        self,
        alert_id: str,
        status: Optional[str] = None,
    ) -> Sequence[InvestigationModel]:
        """Get all investigations for an alert."""
        query = select(InvestigationModel).where(
            InvestigationModel.alert_id == alert_id
        )
        if status:
            query = query.where(InvestigationModel.status == status)
        
        query = query.order_by(InvestigationModel.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def list_by_status(
        self,
        status: str,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[InvestigationModel]:
        """List investigations by status."""
        result = await self.session.execute(
            select(InvestigationModel)
            .where(InvestigationModel.status == status)
            .order_by(InvestigationModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def list_pending(self, limit: int = 10) -> Sequence[InvestigationModel]:
        """List pending investigations for processing."""
        return await self.list_by_status("pending", limit=limit)
    
    async def list_in_progress(self, limit: int = 50) -> Sequence[InvestigationModel]:
        """List in-progress investigations."""
        return await self.list_by_status("in_progress", limit=limit)
    
    async def start(self, id: str) -> Optional[InvestigationModel]:
        """Mark investigation as started."""
        return await self.update(
            id,
            status="in_progress",
            started_at=datetime.utcnow(),
        )
    
    async def complete(
        self,
        id: str,
        summary: str,
        root_cause: Optional[str] = None,
        resolution: Optional[str] = None,
        confidence_score: Optional[float] = None,
    ) -> Optional[InvestigationModel]:
        """Mark investigation as completed."""
        return await self.update(
            id,
            status="completed",
            summary=summary,
            root_cause=root_cause,
            resolution=resolution,
            confidence_score=confidence_score,
            completed_at=datetime.utcnow(),
        )
    
    async def fail(self, id: str, error_summary: str) -> Optional[InvestigationModel]:
        """Mark investigation as failed."""
        return await self.update(
            id,
            status="failed",
            summary=error_summary,
            completed_at=datetime.utcnow(),
        )
    
    async def escalate(self, id: str, reason: str) -> Optional[InvestigationModel]:
        """Mark investigation for escalation."""
        return await self.update(
            id,
            status="escalated",
            summary=reason,
            completed_at=datetime.utcnow(),
        )


class ObservationRepository(BaseRepository[ObservationModel]):
    """Repository for Observation operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ObservationModel)
    
    async def list_by_investigation(
        self,
        investigation_id: str,
        observation_type: Optional[str] = None,
    ) -> Sequence[ObservationModel]:
        """List observations for an investigation."""
        query = select(ObservationModel).where(
            ObservationModel.investigation_id == investigation_id
        )
        if observation_type:
            query = query.where(ObservationModel.observation_type == observation_type)
        
        query = query.order_by(ObservationModel.sequence_num.asc())
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_next_sequence_num(self, investigation_id: str) -> int:
        """Get the next sequence number for an investigation."""
        result = await self.session.execute(
            select(func.coalesce(func.max(ObservationModel.sequence_num), 0))
            .where(ObservationModel.investigation_id == investigation_id)
        )
        return result.scalar_one() + 1
    
    async def create_observation(
        self,
        investigation_id: str,
        observation_type: str,
        source: str,
        data: dict,
        query: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> ObservationModel:
        """Create a new observation with auto-incrementing sequence."""
        seq_num = await self.get_next_sequence_num(investigation_id)
        observation = ObservationModel(
            investigation_id=investigation_id,
            observation_type=observation_type,
            source=source,
            data=data,
            query=query,
            summary=summary,
            sequence_num=seq_num,
        )
        return await self.create(observation)


class ActionRepository(BaseRepository[ActionModel]):
    """Repository for Action operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ActionModel)
    
    async def list_by_investigation(
        self,
        investigation_id: str,
        status: Optional[str] = None,
    ) -> Sequence[ActionModel]:
        """List actions for an investigation."""
        query = select(ActionModel).where(
            ActionModel.investigation_id == investigation_id
        )
        if status:
            query = query.where(ActionModel.status == status)
        
        query = query.order_by(ActionModel.sequence_num.asc())
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def list_pending_approval(self, limit: int = 50) -> Sequence[ActionModel]:
        """List actions pending approval."""
        result = await self.session.execute(
            select(ActionModel)
            .where(
                and_(
                    ActionModel.requires_approval == True,
                    ActionModel.status == "pending",
                )
            )
            .order_by(ActionModel.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_next_sequence_num(self, investigation_id: str) -> int:
        """Get the next sequence number for an investigation."""
        result = await self.session.execute(
            select(func.coalesce(func.max(ActionModel.sequence_num), 0))
            .where(ActionModel.investigation_id == investigation_id)
        )
        return result.scalar_one() + 1
    
    async def approve(self, id: str, approved_by: str) -> Optional[ActionModel]:
        """Approve an action."""
        return await self.update(
            id,
            status="approved",
            approved_by=approved_by,
            approved_at=datetime.utcnow(),
        )
    
    async def reject(self, id: str, approved_by: str) -> Optional[ActionModel]:
        """Reject an action."""
        return await self.update(
            id,
            status="rejected",
            approved_by=approved_by,
            approved_at=datetime.utcnow(),
        )
    
    async def start_execution(self, id: str) -> Optional[ActionModel]:
        """Mark action as executing."""
        return await self.update(
            id,
            status="executing",
            started_at=datetime.utcnow(),
        )
    
    async def complete_execution(
        self,
        id: str,
        result: dict,
    ) -> Optional[ActionModel]:
        """Mark action as completed."""
        return await self.update(
            id,
            status="completed",
            result=result,
            completed_at=datetime.utcnow(),
        )
    
    async def fail_execution(
        self,
        id: str,
        error_message: str,
    ) -> Optional[ActionModel]:
        """Mark action as failed."""
        return await self.update(
            id,
            status="failed",
            error_message=error_message,
            completed_at=datetime.utcnow(),
        )


class RunbookRepository(BaseRepository[RunbookModel]):
    """Repository for Runbook operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, RunbookModel)
    
    async def find_matching(
        self,
        alert_name: str,
        labels: Optional[dict] = None,
    ) -> Optional[RunbookModel]:
        """Find a runbook matching the alert.
        
        Matches by alert name pattern first, then by labels.
        Returns the most specific match.
        """
        # Get all active runbooks
        result = await self.session.execute(
            select(RunbookModel)
            .where(RunbookModel.is_active == True)
            .order_by(RunbookModel.times_used.desc())
        )
        runbooks = result.scalars().all()
        
        # Find best match (simple pattern matching for now)
        for runbook in runbooks:
            if runbook.alert_name_pattern:
                import fnmatch
                if fnmatch.fnmatch(alert_name, runbook.alert_name_pattern):
                    return runbook
        
        return None
    
    async def list_active(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[RunbookModel]:
        """List active runbooks."""
        result = await self.session.execute(
            select(RunbookModel)
            .where(RunbookModel.is_active == True)
            .order_by(RunbookModel.name.asc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def increment_usage(self, id: str) -> None:
        """Increment the usage counter for a runbook."""
        await self.session.execute(
            update(RunbookModel)
            .where(RunbookModel.id == id)
            .values(times_used=RunbookModel.times_used + 1)
        )
        await self.session.flush()
    
    async def update_statistics(
        self,
        id: str,
        success: bool,
        resolution_time_seconds: int,
    ) -> None:
        """Update runbook statistics after an investigation."""
        runbook = await self.get(id)
        if not runbook:
            return
        
        # Calculate new success rate
        total = runbook.times_used or 1
        current_successes = (runbook.success_rate or 0) * (total - 1)
        new_successes = current_successes + (1 if success else 0)
        new_success_rate = new_successes / total
        
        # Calculate new average resolution time
        if runbook.avg_resolution_time_seconds:
            new_avg = (
                (runbook.avg_resolution_time_seconds * (total - 1) + resolution_time_seconds)
                / total
            )
        else:
            new_avg = resolution_time_seconds
        
        await self.update(
            id,
            success_rate=new_success_rate,
            avg_resolution_time_seconds=int(new_avg),
        )


class ChatMessageRepository(BaseRepository[ChatMessageModel]):
    """Repository for ChatMessage operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ChatMessageModel)
    
    async def list_by_investigation(
        self,
        investigation_id: str,
        role: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Sequence[ChatMessageModel]:
        """List chat messages for an investigation."""
        query = select(ChatMessageModel).where(
            ChatMessageModel.investigation_id == investigation_id
        )
        if role:
            query = query.where(ChatMessageModel.role == role)
        
        query = query.order_by(ChatMessageModel.sequence_num.asc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_next_sequence_num(self, investigation_id: str) -> int:
        """Get the next sequence number for an investigation."""
        result = await self.session.execute(
            select(func.coalesce(func.max(ChatMessageModel.sequence_num), 0))
            .where(ChatMessageModel.investigation_id == investigation_id)
        )
        return result.scalar_one() + 1
    
    async def add_message(
        self,
        investigation_id: str,
        role: str,
        content: Optional[str] = None,
        tool_calls: Optional[list] = None,
        tool_call_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
    ) -> ChatMessageModel:
        """Add a new message with auto-incrementing sequence."""
        seq_num = await self.get_next_sequence_num(investigation_id)
        message = ChatMessageModel(
            investigation_id=investigation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            model=model,
            tokens_used=tokens_used,
            sequence_num=seq_num,
        )
        return await self.create(message)
    
    async def get_conversation_history(
        self,
        investigation_id: str,
        max_messages: int = 50,
    ) -> List[dict]:
        """Get conversation history in OpenAI message format."""
        messages = await self.list_by_investigation(
            investigation_id,
            limit=max_messages,
        )
        
        history = []
        for msg in messages:
            entry = {"role": msg.role}
            if msg.content:
                entry["content"] = msg.content
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_name:
                entry["name"] = msg.tool_name
            history.append(entry)
        
        return history
    
    async def count_tokens_used(self, investigation_id: str) -> int:
        """Get total tokens used in an investigation."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(ChatMessageModel.tokens_used), 0))
            .where(ChatMessageModel.investigation_id == investigation_id)
        )
        return result.scalar_one()
