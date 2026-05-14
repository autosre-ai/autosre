"""API Schemas Package.

Pydantic models for request validation and response serialization.
"""

from autosre.api.schemas.requests import (
    AlertCreate,
    AlertUpdate,
    ChatMessage,
    InvestigationTrigger,
    RunbookCreate,
    RunbookExecute,
    RunbookUpdate,
)
from autosre.api.schemas.responses import (
    AlertDetail,
    AlertList,
    ChatResponse,
    ChatSession,
    InvestigationDetail,
    InvestigationList,
    InvestigationStep,
    InvestigationSummary,
    PaginatedResponse,
    RunbookDetail,
    RunbookExecution,
    RunbookList,
)

__all__ = [
    # Requests
    "AlertCreate",
    "AlertUpdate",
    "ChatMessage",
    "InvestigationTrigger",
    "RunbookCreate",
    "RunbookExecute",
    "RunbookUpdate",
    # Responses
    "AlertDetail",
    "AlertList",
    "ChatResponse",
    "ChatSession",
    "InvestigationDetail",
    "InvestigationList",
    "InvestigationStep",
    "InvestigationSummary",
    "PaginatedResponse",
    "RunbookDetail",
    "RunbookExecution",
    "RunbookList",
]
