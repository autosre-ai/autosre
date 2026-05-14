"""Unit tests for middleware components.

Tests authentication, error handling, logging, and rate limiting middleware.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse, Response

from autosre.api.middleware.auth import (
    JWTAuth,
    User,
    TokenPayload,
    bearer_scheme,
    configure_jwt_auth,
    get_current_user,
    get_jwt_auth,
    require_all_roles,
    require_role,
)
from autosre.api.middleware.errors import (
    APIError,
    BadRequestError,
    ConflictError,
    ErrorHandlerMiddleware,
    NotFoundError,
    register_exception_handlers,
)
from autosre.api.middleware.logging import (
    RequestLoggingMiddleware,
    StructuredLogFormatter,
    setup_logging,
)
from autosre.api.middleware.ratelimit import (
    InMemoryBackend,
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimitResult,
    rate_limit,
)


# ============================================================================
# JWT Authentication Middleware Tests
# ============================================================================


class TestJWTAuth:
    """Tests for JWT authentication."""

    @pytest.fixture
    def jwt_auth(self):
        """Create JWTAuth instance with test secret."""
        return JWTAuth(
            secret_key="test-secret-key-12345",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7,
        )

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID."""
        return "user-123"

    @pytest.fixture
    def sample_roles(self):
        """Sample user roles."""
        return ["admin", "operator"]

    @pytest.mark.asyncio
    async def test_create_access_token(self, jwt_auth, sample_user_id, sample_roles):
        """Test creating an access token."""
        token = await jwt_auth.create_token(
            user_id=sample_user_id,
            roles=sample_roles,
            token_type="access",
        )

        assert token is not None
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_create_refresh_token(self, jwt_auth, sample_user_id, sample_roles):
        """Test creating a refresh token."""
        token = await jwt_auth.create_token(
            user_id=sample_user_id,
            roles=sample_roles,
            token_type="refresh",
        )

        assert token is not None

    @pytest.mark.asyncio
    async def test_verify_valid_token(self, jwt_auth, sample_user_id, sample_roles):
        """Test verifying a valid token."""
        token = await jwt_auth.create_token(
            user_id=sample_user_id,
            roles=sample_roles,
        )

        payload = await jwt_auth.verify_token(token)

        assert payload["sub"] == sample_user_id
        assert payload["roles"] == sample_roles

    @pytest.mark.asyncio
    async def test_verify_expired_token(self, jwt_auth, sample_user_id, sample_roles):
        """Test verifying an expired token."""
        # Create auth with very short expiry
        short_auth = JWTAuth(
            secret_key="test-secret-key-12345",
            access_token_expire_minutes=0,  # Expires immediately
        )

        token = await short_auth.create_token(
            user_id=sample_user_id,
            roles=sample_roles,
        )

        # Wait a moment for expiry
        await asyncio.sleep(0.1)

        with pytest.raises(HTTPException) as exc_info:
            await short_auth.verify_token(token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, jwt_auth):
        """Test verifying an invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth.verify_token("invalid.token.here")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_wrong_signature(self, jwt_auth, sample_user_id, sample_roles):
        """Test verifying token with wrong signature."""
        # Create token with different secret
        other_auth = JWTAuth(secret_key="different-secret-key")
        token = await other_auth.create_token(
            user_id=sample_user_id,
            roles=sample_roles,
        )

        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth.verify_token(token)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_flow(self, jwt_auth, sample_user_id, sample_roles):
        """Test refreshing a token."""
        # Create refresh token
        refresh_token = await jwt_auth.create_token(
            user_id=sample_user_id,
            roles=sample_roles,
            token_type="refresh",
        )

        # Refresh to get new access token
        new_access_token = await jwt_auth.refresh_token(refresh_token)

        assert new_access_token is not None
        payload = await jwt_auth.verify_token(new_access_token)
        assert payload["sub"] == sample_user_id

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(
        self, jwt_auth, sample_user_id, sample_roles
    ):
        """Test refreshing with access token fails."""
        access_token = await jwt_auth.create_token(
            user_id=sample_user_id,
            roles=sample_roles,
            token_type="access",
        )

        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth.refresh_token(access_token)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_revoke_token(self, jwt_auth, sample_user_id, sample_roles):
        """Test revoking a token."""
        token = await jwt_auth.create_token(
            user_id=sample_user_id,
            roles=sample_roles,
        )

        await jwt_auth.revoke_token(token)

        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth.verify_token(token)

        assert "revoked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_token_with_additional_claims(
        self, jwt_auth, sample_user_id, sample_roles
    ):
        """Test token with additional claims."""
        token = await jwt_auth.create_token(
            user_id=sample_user_id,
            roles=sample_roles,
            additional_claims={"email": "user@example.com", "org_id": "org-123"},
        )

        payload = await jwt_auth.verify_token(token)

        assert payload["email"] == "user@example.com"
        assert payload["org_id"] == "org-123"

    def test_jwt_auth_requires_secret(self):
        """Test JWTAuth raises error without secret."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                JWTAuth(secret_key="")

            assert "JWT_SECRET_KEY" in str(exc_info.value)


class TestAuthDependencies:
    """Tests for authentication dependencies."""

    @pytest.fixture
    def configured_jwt_auth(self):
        """Configure and return JWT auth."""
        return configure_jwt_auth(secret_key="test-secret-12345")

    @pytest.mark.asyncio
    async def test_get_current_user(self, configured_jwt_auth):
        """Test get_current_user dependency."""
        token = await configured_jwt_auth.create_token(
            user_id="user-123",
            roles=["admin"],
        )

        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        mock_credentials = MagicMock()
        mock_credentials.credentials = token

        user = await get_current_user(mock_request, mock_credentials)

        assert isinstance(user, User)
        assert user.id == "user-123"
        assert "admin" in user.roles

    @pytest.mark.asyncio
    async def test_get_current_user_no_credentials(self, configured_jwt_auth):
        """Test get_current_user without credentials."""
        mock_request = MagicMock(spec=Request)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, None)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_role_success(self, configured_jwt_auth):
        """Test require_role dependency success."""
        token = await configured_jwt_auth.create_token(
            user_id="user-123",
            roles=["admin", "operator"],
        )

        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        mock_credentials = MagicMock()
        mock_credentials.credentials = token

        user = await get_current_user(mock_request, mock_credentials)

        # Create role checker
        role_checker = require_role("admin")

        # Should not raise
        result = await role_checker(user)
        assert result.id == "user-123"

    @pytest.mark.asyncio
    async def test_require_role_failure(self, configured_jwt_auth):
        """Test require_role dependency failure."""
        user = User(id="user-123", roles=["viewer"])

        role_checker = require_role("admin")

        with pytest.raises(HTTPException) as exc_info:
            await role_checker(user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_all_roles_success(self, configured_jwt_auth):
        """Test require_all_roles dependency success."""
        user = User(id="user-123", roles=["admin", "operator", "viewer"])

        role_checker = require_all_roles("admin", "operator")

        result = await role_checker(user)
        assert result.id == "user-123"

    @pytest.mark.asyncio
    async def test_require_all_roles_failure(self, configured_jwt_auth):
        """Test require_all_roles dependency failure."""
        user = User(id="user-123", roles=["admin"])

        role_checker = require_all_roles("admin", "operator")

        with pytest.raises(HTTPException) as exc_info:
            await role_checker(user)

        assert exc_info.value.status_code == 403
        assert "operator" in exc_info.value.detail


# ============================================================================
# Error Handling Middleware Tests
# ============================================================================


class TestAPIErrors:
    """Tests for custom API error classes."""

    def test_api_error_basic(self):
        """Test basic APIError."""
        error = APIError("Something went wrong", status_code=500)

        assert error.message == "Something went wrong"
        assert error.status_code == 500
        assert error.error_code == "ERR_500"

    def test_api_error_with_details(self):
        """Test APIError with details."""
        error = APIError(
            "Validation failed",
            status_code=400,
            error_code="VALIDATION_ERROR",
            details={"field": "name", "reason": "required"},
        )

        assert error.error_code == "VALIDATION_ERROR"
        assert error.details["field"] == "name"

    def test_api_error_to_response(self):
        """Test APIError conversion to response."""
        error = APIError("Test error", status_code=400)
        response = error.to_response()

        assert response.status_code == 400
        body = json.loads(response.body)
        assert body["error"]["message"] == "Test error"

    def test_not_found_error(self):
        """Test NotFoundError."""
        error = NotFoundError("Alert", "alert-123")

        assert error.status_code == 404
        assert "alert-123" in error.message
        assert error.error_code == "NOT_FOUND"

    def test_conflict_error(self):
        """Test ConflictError."""
        error = ConflictError("Resource already exists", "Alert")

        assert error.status_code == 409
        assert error.details["resource"] == "Alert"

    def test_bad_request_error(self):
        """Test BadRequestError."""
        error = BadRequestError("Invalid input", "email")

        assert error.status_code == 400
        assert error.details["field"] == "email"


class TestErrorHandlerMiddleware:
    """Tests for error handler middleware."""

    @pytest.fixture
    def app_with_error_middleware(self):
        """Create app with error handler middleware."""
        app = FastAPI()

        app.add_middleware(ErrorHandlerMiddleware, debug=True)

        @app.get("/api-error")
        async def raise_api_error():
            raise NotFoundError("Item", "123")

        @app.get("/http-error")
        async def raise_http_error():
            raise HTTPException(status_code=403, detail="Forbidden")

        @app.get("/generic-error")
        async def raise_generic_error():
            raise RuntimeError("Unexpected error")

        @app.get("/success")
        async def success():
            return {"status": "ok"}

        return app

    @pytest.mark.asyncio
    async def test_api_error_handled(self, app_with_error_middleware):
        """Test APIError is handled properly."""
        transport = ASGITransport(app=app_with_error_middleware)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api-error")

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_http_exception_handled(self, app_with_error_middleware):
        """Test HTTPException is handled properly."""
        transport = ASGITransport(app=app_with_error_middleware)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/http-error")

        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "HTTP_403"

    @pytest.mark.asyncio
    async def test_generic_error_handled(self, app_with_error_middleware):
        """Test generic exceptions are handled."""
        transport = ASGITransport(app=app_with_error_middleware)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/generic-error")

        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "INTERNAL_ERROR"

    @pytest.mark.asyncio
    async def test_success_passes_through(self, app_with_error_middleware):
        """Test successful requests pass through."""
        transport = ASGITransport(app=app_with_error_middleware)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/success")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ============================================================================
# Request Logging Middleware Tests
# ============================================================================


class TestRequestLoggingMiddleware:
    """Tests for request logging middleware."""

    @pytest.fixture
    def app_with_logging(self):
        """Create app with logging middleware."""
        app = FastAPI()

        app.add_middleware(
            RequestLoggingMiddleware,
            log_request_body=True,
            exclude_paths=["/health"],
        )

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "test"}

        @app.get("/api/slow")
        async def slow_endpoint():
            await asyncio.sleep(0.1)
            return {"message": "slow"}

        return app

    @pytest.mark.asyncio
    async def test_request_id_generated(self, app_with_logging):
        """Test request ID is generated and returned."""
        transport = ASGITransport(app=app_with_logging)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/test")

        assert "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_custom_request_id_honored(self, app_with_logging):
        """Test custom request ID is honored."""
        custom_id = "my-custom-request-id"
        transport = ASGITransport(app=app_with_logging)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/test",
                headers={"X-Request-ID": custom_id},
            )

        assert response.headers["X-Request-ID"] == custom_id

    @pytest.mark.asyncio
    async def test_excluded_paths_not_logged(self, app_with_logging, caplog):
        """Test excluded paths are not logged."""
        transport = ASGITransport(app=app_with_logging)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with caplog.at_level(logging.INFO, logger="autosre.api"):
                response = await client.get("/health")

        # Health check should not appear in logs (excluded)
        assert response.status_code == 200


class TestStructuredLogFormatter:
    """Tests for structured log formatter."""

    def test_format_basic_record(self):
        """Test formatting basic log record."""
        formatter = StructuredLogFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "test"

    def test_format_record_with_extras(self):
        """Test formatting record with extra fields."""
        formatter = StructuredLogFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Request completed",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-123"
        record.method = "GET"
        record.path = "/api/test"
        record.status_code = 200
        record.duration_ms = 45.5

        output = formatter.format(record)
        data = json.loads(output)

        assert data["request_id"] == "req-123"
        assert data["method"] == "GET"
        assert data["status_code"] == 200
        assert data["duration_ms"] == 45.5


# ============================================================================
# Rate Limiting Middleware Tests
# ============================================================================


class TestInMemoryBackend:
    """Tests for in-memory rate limit backend."""

    @pytest.fixture
    def backend(self):
        """Create in-memory backend."""
        return InMemoryBackend()

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, backend):
        """Test first request is always allowed."""
        result = await backend.check_and_increment("user:123", limit=10, window_seconds=60)

        assert result.allowed is True
        assert result.remaining == 9
        assert result.limit == 10

    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self, backend):
        """Test rate limit is enforced."""
        # Make 5 requests (limit is 5)
        for _ in range(5):
            await backend.check_and_increment("user:123", limit=5, window_seconds=60)

        # 6th request should be denied
        result = await backend.check_and_increment("user:123", limit=5, window_seconds=60)

        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, backend):
        """Test different keys have independent limits."""
        # Exhaust limit for user 1
        for _ in range(5):
            await backend.check_and_increment("user:1", limit=5, window_seconds=60)

        # User 2 should still be allowed
        result = await backend.check_and_increment("user:2", limit=5, window_seconds=60)

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_reset_clears_limit(self, backend):
        """Test reset clears rate limit."""
        # Exhaust limit
        for _ in range(5):
            await backend.check_and_increment("user:123", limit=5, window_seconds=60)

        # Reset
        await backend.reset("user:123")

        # Should be allowed again
        result = await backend.check_and_increment("user:123", limit=5, window_seconds=60)

        assert result.allowed is True
        assert result.remaining == 4


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""

    @pytest.fixture
    def app_with_ratelimit(self):
        """Create app with rate limiting."""
        app = FastAPI()

        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
        )

        app.add_middleware(
            RateLimitMiddleware,
            config=config,
            exclude_paths=["/health"],
        )

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "test"}

        return app

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self, app_with_ratelimit):
        """Test rate limit headers are present in response."""
        transport = ASGITransport(app=app_with_ratelimit)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/test")

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_excluded_paths_not_limited(self, app_with_ratelimit):
        """Test excluded paths are not rate limited."""
        transport = ASGITransport(app=app_with_ratelimit)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Make many requests to health endpoint
            for _ in range(20):
                response = await client.get("/health")
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_429(self, app_with_ratelimit):
        """Test exceeding rate limit returns 429."""
        # Create app with very low limit
        app = FastAPI()

        config = RateLimitConfig(requests_per_minute=2)
        app.add_middleware(RateLimitMiddleware, config=config)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "test"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Make requests until limited
            for _ in range(3):
                response = await client.get("/api/test")

            # Should be rate limited
            assert response.status_code == 429
            data = response.json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    @pytest.mark.asyncio
    async def test_rate_limit_retry_after_header(self, app_with_ratelimit):
        """Test Retry-After header is set when rate limited."""
        app = FastAPI()

        config = RateLimitConfig(requests_per_minute=1)
        app.add_middleware(RateLimitMiddleware, config=config)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "test"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/api/test")  # First request
            response = await client.get("/api/test")  # Should be limited

        assert "Retry-After" in response.headers


class TestRateLimitDecorator:
    """Tests for rate_limit decorator."""

    @pytest.mark.asyncio
    async def test_rate_limit_decorator(self):
        """Test rate_limit decorator on route."""
        app = FastAPI()

        @app.get("/expensive")
        async def expensive_operation(
            request: Request,
            _: None = rate_limit(requests=2, window_seconds=60),
        ):
            return {"result": "expensive"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First two requests succeed
            r1 = await client.get("/expensive")
            assert r1.status_code == 200

            r2 = await client.get("/expensive")
            assert r2.status_code == 200

            # Third request limited
            r3 = await client.get("/expensive")
            assert r3.status_code == 429


# ============================================================================
# Middleware Integration Tests
# ============================================================================


class TestMiddlewareIntegration:
    """Integration tests for middleware stack."""

    @pytest.fixture
    def full_app(self):
        """Create app with full middleware stack."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            config=RateLimitConfig(requests_per_minute=100),
            exclude_paths=["/health"],
        )
        app.add_middleware(RequestLoggingMiddleware)
        app.add_middleware(ErrorHandlerMiddleware)

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/api/test")
        async def test():
            return {"message": "test"}

        @app.get("/api/error")
        async def error():
            raise NotFoundError("Item", "123")

        return app

    @pytest.mark.asyncio
    async def test_middleware_order(self, full_app):
        """Test middleware executes in correct order."""
        transport = ASGITransport(app=full_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/test")

        # All middleware should have processed
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert "X-RateLimit-Limit" in response.headers

    @pytest.mark.asyncio
    async def test_error_through_middleware_stack(self, full_app):
        """Test errors propagate through middleware stack."""
        transport = ASGITransport(app=full_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/error")

        assert response.status_code == 404
        # Request ID should still be present
        assert "X-Request-ID" in response.headers


# ============================================================================
# Webhook Signature Verification Tests
# ============================================================================


class TestWebhookSignatureVerification:
    """Tests for webhook signature verification."""

    def test_alertmanager_signature_valid(self):
        """Test valid Alertmanager signature."""
        from autosre.api.routes.webhooks import verify_alertmanager_signature

        secret = "my-secret"
        payload = b'{"status": "firing", "alerts": []}'
        expected_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"sha256={expected_sig}"

        assert verify_alertmanager_signature(payload, signature, secret) is True

    def test_alertmanager_signature_invalid(self):
        """Test invalid Alertmanager signature."""
        from autosre.api.routes.webhooks import verify_alertmanager_signature

        secret = "my-secret"
        payload = b'{"status": "firing", "alerts": []}'
        signature = "sha256=invalid"

        assert verify_alertmanager_signature(payload, signature, secret) is False

    def test_alertmanager_signature_no_secret(self):
        """Test Alertmanager signature with no secret configured."""
        from autosre.api.routes.webhooks import verify_alertmanager_signature

        payload = b'{"status": "firing"}'

        # No secret means verification is skipped
        assert verify_alertmanager_signature(payload, None, "") is True

    def test_pagerduty_signature_valid(self):
        """Test valid PagerDuty signature."""
        from autosre.api.routes.webhooks import verify_pagerduty_signature

        secret = "my-secret"
        payload = b'{"event": {}}'
        expected_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signatures = f"v1={expected_sig}"

        assert verify_pagerduty_signature(payload, signatures, secret) is True

    def test_pagerduty_signature_multiple_versions(self):
        """Test PagerDuty signature with multiple versions."""
        from autosre.api.routes.webhooks import verify_pagerduty_signature

        secret = "my-secret"
        payload = b'{"event": {}}'
        expected_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        # Multiple signature versions
        signatures = f"v0=oldsig,v1={expected_sig}"

        assert verify_pagerduty_signature(payload, signatures, secret) is True


# ============================================================================
# User Model Tests
# ============================================================================


class TestUserModel:
    """Tests for User model."""

    def test_user_creation(self):
        """Test User model creation."""
        user = User(
            id="user-123",
            roles=["admin", "operator"],
            email="user@example.com",
            metadata={"org": "acme"},
        )

        assert user.id == "user-123"
        assert "admin" in user.roles
        assert user.email == "user@example.com"

    def test_user_defaults(self):
        """Test User model defaults."""
        user = User(id="user-123")

        assert user.roles == []
        assert user.email is None
        assert user.metadata == {}


class TestTokenPayload:
    """Tests for TokenPayload model."""

    def test_token_payload(self):
        """Test TokenPayload model."""
        now = datetime.now(timezone.utc)
        payload = TokenPayload(
            sub="user-123",
            roles=["admin"],
            exp=now + timedelta(hours=1),
            iat=now,
            jti="token-abc",
        )

        assert payload.sub == "user-123"
        assert payload.jti == "token-abc"
