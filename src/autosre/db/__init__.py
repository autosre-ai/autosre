"""AutoSRE Database Layer.

SQLAlchemy 2.0 async database models, session management, and repositories.
"""

from autosre.db.models import (
    Base,
    AlertModel,
    InvestigationModel,
    ObservationModel,
    ActionModel,
    RunbookModel,
    ChatMessageModel,
)
from autosre.db.session import (
    get_engine,
    get_async_session,
    get_db,
    init_db,
)
from autosre.db.repository import (
    AlertRepository,
    InvestigationRepository,
    ObservationRepository,
    ActionRepository,
    RunbookRepository,
    ChatMessageRepository,
)

__all__ = [
    # Models
    "Base",
    "AlertModel",
    "InvestigationModel",
    "ObservationModel",
    "ActionModel",
    "RunbookModel",
    "ChatMessageModel",
    # Session
    "get_engine",
    "get_async_session",
    "get_db",
    "init_db",
    # Repositories
    "AlertRepository",
    "InvestigationRepository",
    "ObservationRepository",
    "ActionRepository",
    "RunbookRepository",
    "ChatMessageRepository",
]
