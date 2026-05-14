"""Common schemas shared across API endpoints.

Provides base classes, mixins, and utility schemas for consistent API responses.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


# Type variable for generic responses
T = TypeVar("T")


class TimestampMixin(BaseModel):
    """Mixin providing created_at and updated_at timestamps."""

    created_at: datetime = Field(
        ...,
        description="Timestamp when the resource was created",
        json_schema_extra={"example": "2024-01-15T10:30:00Z"},
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the resource was last updated",
        json_schema_extra={"example": "2024-01-15T14:45:30Z"},
    )


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "page": 1,
                "per_page": 20,
            }
        },
    )

    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)",
        json_schema_extra={"example": 1},
    )
    per_page: int = Field(
        default=20,
        ge=1,
        le=100,
        alias="perPage",
        description="Number of items per page",
        json_schema_extra={"example": 20},
    )

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "per_page": 20,
                "pages": 5,
                "has_next": True,
                "has_prev": False,
            }
        },
    )

    items: list[T] = Field(..., description="List of items for the current page")
    total: int = Field(..., ge=0, description="Total number of items across all pages")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(
        ...,
        ge=1,
        alias="perPage",
        description="Number of items per page",
    )
    pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(
        ...,
        alias="hasNext",
        description="Whether there is a next page",
    )
    has_prev: bool = Field(
        ...,
        alias="hasPrev",
        description="Whether there is a previous page",
    )

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        per_page: int,
    ) -> PaginatedResponse[T]:
        """Create a paginated response with computed fields."""
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


class ErrorDetail(BaseModel):
    """Detailed error information."""

    model_config = ConfigDict(populate_by_name=True)

    field: str | None = Field(
        default=None,
        description="Field that caused the error (for validation errors)",
    )
    message: str = Field(..., description="Error message")
    code: str | None = Field(
        default=None,
        description="Error code for programmatic handling",
    )


class ErrorResponse(BaseModel):
    """Standard error response format."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "error": "not_found",
                "message": "Resource not found",
                "details": [],
                "request_id": "req_abc123",
            }
        },
    )

    error: str = Field(
        ...,
        description="Error code/type",
        json_schema_extra={"example": "validation_error"},
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        json_schema_extra={"example": "Invalid request parameters"},
    )
    details: list[ErrorDetail] = Field(
        default_factory=list,
        description="Additional error details",
    )
    request_id: str | None = Field(
        default=None,
        alias="requestId",
        description="Request ID for debugging",
    )


class SuccessResponse(BaseModel):
    """Generic success response for operations without return data."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation completed successfully",
            }
        },
    )

    success: bool = Field(default=True, description="Whether the operation succeeded")
    message: str = Field(
        default="Operation completed successfully",
        description="Success message",
    )
    data: dict[str, Any] | None = Field(
        default=None,
        description="Additional data if any",
    )


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Component name")
    status: HealthStatus = Field(..., description="Component health status")
    message: str | None = Field(default=None, description="Additional details")
    latency_ms: float | None = Field(
        default=None,
        alias="latencyMs",
        description="Response latency in milliseconds",
    )


class HealthResponse(BaseModel):
    """Health check response."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "2.0.0",
                "uptime_seconds": 3600.5,
                "components": [
                    {
                        "name": "database",
                        "status": "healthy",
                        "latency_ms": 2.5,
                    },
                    {
                        "name": "redis",
                        "status": "healthy",
                        "latency_ms": 0.8,
                    },
                ],
            }
        },
    )

    status: HealthStatus = Field(..., description="Overall health status")
    version: str = Field(..., description="Application version")
    uptime_seconds: float = Field(
        ...,
        alias="uptimeSeconds",
        description="Application uptime in seconds",
    )
    components: list[ComponentHealth] = Field(
        default_factory=list,
        description="Individual component health status",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp",
    )


class SortOrder(str, Enum):
    """Sort order direction."""

    ASC = "asc"
    DESC = "desc"


class SortParams(BaseModel):
    """Sorting parameters."""

    model_config = ConfigDict(populate_by_name=True)

    sort_by: str | None = Field(
        default=None,
        alias="sortBy",
        description="Field to sort by",
    )
    sort_order: SortOrder = Field(
        default=SortOrder.DESC,
        alias="sortOrder",
        description="Sort order direction",
    )
