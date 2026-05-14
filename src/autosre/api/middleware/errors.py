"""Error handling middleware for AutoSRE API."""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING, Any, Callable

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger("autosre.api")


class APIError(Exception):
    """Base exception for API errors.

    Provides structured error responses with optional error codes
    and additional details.
    """

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize API error.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code.
            error_code: Machine-readable error code.
            details: Additional error details.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"ERR_{status_code}"
        self.details = details or {}

    def to_response(self) -> JSONResponse:
        """Convert error to JSON response.

        Returns:
            JSONResponse with error details.
        """
        return JSONResponse(
            status_code=self.status_code,
            content={
                "error": {
                    "message": self.message,
                    "code": self.error_code,
                    "details": self.details,
                }
            },
        )


class NotFoundError(APIError):
    """Resource not found error."""

    def __init__(
        self,
        resource: str,
        identifier: str | None = None,
    ) -> None:
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} '{identifier}' not found"
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
        )


class ConflictError(APIError):
    """Resource conflict error."""

    def __init__(
        self,
        message: str,
        resource: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT",
            details={"resource": resource} if resource else {},
        )


class BadRequestError(APIError):
    """Bad request error."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="BAD_REQUEST",
            details={"field": field} if field else {},
        )


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Convert exceptions to proper HTTP responses.

    Catches all exceptions and converts them to structured JSON
    error responses with appropriate status codes.
    """

    def __init__(
        self,
        app: ASGIApp,
        debug: bool = False,
        include_traceback: bool = False,
    ) -> None:
        """Initialize error handler middleware.

        Args:
            app: The ASGI application.
            debug: Whether to include debug information.
            include_traceback: Whether to include stack traces in errors.
        """
        super().__init__(app)
        self.debug = debug
        self.include_traceback = include_traceback

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> JSONResponse:
        """Handle request and catch any exceptions.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            Response from handler or error response.
        """
        try:
            return await call_next(request)
        except APIError as e:
            # Custom API errors
            self._log_error(request, e, level=logging.WARNING)
            return e.to_response()
        except HTTPException as e:
            # FastAPI HTTP exceptions
            self._log_error(request, e, level=logging.WARNING)
            return self._http_exception_response(e)
        except RequestValidationError as e:
            # Request validation errors
            self._log_error(request, e, level=logging.WARNING)
            return self._validation_error_response(e)
        except ValidationError as e:
            # Pydantic validation errors
            self._log_error(request, e, level=logging.WARNING)
            return self._pydantic_error_response(e)
        except Exception as e:
            # Generic errors - these are unexpected
            self._log_error(request, e, level=logging.ERROR)
            return self._generic_error_response(e, request)

    def _http_exception_response(self, exc: HTTPException) -> JSONResponse:
        """Convert HTTPException to JSON response.

        Args:
            exc: The HTTP exception.

        Returns:
            Structured JSON error response.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.detail,
                    "code": f"HTTP_{exc.status_code}",
                    "details": {},
                }
            },
            headers=getattr(exc, "headers", None),
        )

    def _validation_error_response(
        self,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Convert validation error to JSON response.

        Args:
            exc: The validation error.

        Returns:
            Structured JSON error response with field details.
        """
        errors = []
        for error in exc.errors():
            loc = " -> ".join(str(l) for l in error["loc"])
            errors.append({
                "field": loc,
                "message": error["msg"],
                "type": error["type"],
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "message": "Validation error",
                    "code": "VALIDATION_ERROR",
                    "details": {"errors": errors},
                }
            },
        )

    def _pydantic_error_response(self, exc: ValidationError) -> JSONResponse:
        """Convert Pydantic validation error to JSON response.

        Args:
            exc: The Pydantic validation error.

        Returns:
            Structured JSON error response.
        """
        errors = []
        for error in exc.errors():
            loc = " -> ".join(str(l) for l in error["loc"])
            errors.append({
                "field": loc,
                "message": error["msg"],
                "type": error["type"],
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "message": "Validation error",
                    "code": "VALIDATION_ERROR",
                    "details": {"errors": errors},
                }
            },
        )

    def _generic_error_response(
        self,
        exc: Exception,
        request: Request,
    ) -> JSONResponse:
        """Convert generic exception to JSON response.

        Args:
            exc: The exception.
            request: The incoming request.

        Returns:
            Structured JSON error response.
        """
        content: dict[str, Any] = {
            "error": {
                "message": "Internal server error",
                "code": "INTERNAL_ERROR",
                "details": {},
            }
        }

        # Add request ID if available
        if hasattr(request.state, "request_id"):
            content["error"]["details"]["request_id"] = request.state.request_id

        # Add debug info if enabled
        if self.debug:
            content["error"]["details"]["exception"] = str(exc)
            content["error"]["details"]["type"] = type(exc).__name__

        if self.include_traceback:
            content["error"]["details"]["traceback"] = traceback.format_exc()

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content,
        )

    def _log_error(
        self,
        request: Request,
        exc: Exception,
        level: int = logging.ERROR,
    ) -> None:
        """Log an error with request context.

        Args:
            request: The incoming request.
            exc: The exception that occurred.
            level: Logging level.
        """
        request_id = getattr(request.state, "request_id", None)

        extra = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        }

        logger.log(
            level,
            f"Error handling request: {exc}",
            extra=extra,
            exc_info=level >= logging.ERROR,
        )


def register_exception_handlers(app: Any) -> None:
    """Register exception handlers with FastAPI app.

    This is an alternative to using the middleware for more
    fine-grained control over exception handling.

    Args:
        app: FastAPI application instance.
    """
    from fastapi import FastAPI

    if not isinstance(app, FastAPI):
        raise TypeError("Expected FastAPI application")

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        return exc.to_response()

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.detail,
                    "code": f"HTTP_{exc.status_code}",
                    "details": {},
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = []
        for error in exc.errors():
            loc = " -> ".join(str(l) for l in error["loc"])
            errors.append({
                "field": loc,
                "message": error["msg"],
                "type": error["type"],
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "message": "Validation error",
                    "code": "VALIDATION_ERROR",
                    "details": {"errors": errors},
                }
            },
        )
