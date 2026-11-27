"""
middleware.py — Security and observability middleware for EduPro API.

Provides:
- API key authentication (optional)
- Rate limiting (optional)
- Request timing and correlation IDs
- Request size limiting
- Structured logging
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from collections.abc import Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import edup.settings
from edup.logging import get_logger, set_correlation_id

logger = get_logger("edup.api.middleware")

PRODUCTION_CONFIG_INVALID_MSG = "Production configuration invalid"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for global rate limiting using in-memory token bucket."""

    def __init__(
        self,
        app: FastAPI,
        exempt_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.exempt_paths = exempt_paths or ["/health", "/health/live", "/health/ready", "/docs", "/openapi.json", "/redoc", "/"]
        # In-memory store: {client_ip: [(timestamp, ...)]}
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _is_exempt(self, path: str) -> bool:
        for exempt in self.exempt_paths:
            if path == exempt:
                return True
            if exempt.endswith("*") and path.startswith(exempt[:-1]):
                return True
        return False

    def _get_client_ip(self, request: Request) -> str:
        # Check for forwarded headers first (for proxy setups)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _check_rate_limit(self, client_ip: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """Check if client has exceeded rate limit. Returns (allowed, retry_after)."""
        now = time.time()
        window_start = now - window_seconds

        # Clean old requests
        self._requests[client_ip] = [ts for ts in self._requests[client_ip] if ts > window_start]

        if len(self._requests[client_ip]) >= max_requests:
            # Rate limited - calculate retry after
            oldest = min(self._requests[client_ip]) if self._requests[client_ip] else now
            retry_after = int(oldest + window_seconds - now) + 1
            return False, max(retry_after, 1)

        # Allow request
        self._requests[client_ip].append(now)
        return True, 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = edup.settings.get_settings()

        if not settings.rate_limit_enabled:
            return await call_next(request)  # type: ignore[no-any-return]

        if self._is_exempt(request.url.path):
            return await call_next(request)  # type: ignore[no-any-return]

        client_ip = self._get_client_ip(request)
        allowed, retry_after = self._check_rate_limit(
            client_ip,
            settings.rate_limit_requests,
            settings.rate_limit_window_seconds,
        )

        if not allowed:
            logger.warning(
                "rate_limit_exceeded path=%s client_ip=%s correlation_id=%s",
                request.url.path,
                client_ip,
                getattr(request.state, "correlation_id", "unknown"),
            )
            return JSONResponse(  # type: ignore[return-value]
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "RateLimitExceeded",
                    "message": "Too many requests. Please try again later.",
                    "details": {"retry_after_seconds": retry_after},
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)  # type: ignore[no-any-return]


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to measure and log request processing time."""

    def __init__(self, app: FastAPI, log_timing: bool = True):
        super().__init__(app)
        self.log_timing = log_timing

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4())[:8])
        request.state.correlation_id = correlation_id
        set_correlation_id(correlation_id)

        start_time = time.perf_counter()

        # Add correlation ID to response headers
        response = await call_next(request)

        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        response.headers["X-Correlation-ID"] = correlation_id

        if self.log_timing:
            logger.info(
                "request_complete method=%s path=%s status=%d duration_ms=%.2f correlation_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                process_time * 1000,
                correlation_id,
            )

        # Clear correlation ID after request
        set_correlation_id(None)

        return response  # type: ignore[no-any-return]


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""

    def __init__(self, app: FastAPI, max_size_bytes: int):
        super().__init__(app)
        self.max_size_bytes = max_size_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size_bytes:
                    logger.warning(
                        "request_too_large path=%s size=%d max=%d",
                        request.url.path,
                        size,
                        self.max_size_bytes,
                    )
                    return JSONResponse(  # type: ignore[return-value]
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": "RequestEntityTooLarge",
                            "message": f"Request body too large. Maximum size: {self.max_size_bytes} bytes",
                            "details": {"max_size_bytes": self.max_size_bytes},
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)  # type: ignore[no-any-return]


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication."""

    def __init__(
        self,
        app: FastAPI,
        exempt_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.exempt_paths = exempt_paths or ["/health", "/health/live", "/health/ready", "/docs", "/openapi.json", "/redoc", "/"]

    def _is_exempt(self, path: str) -> bool:
        for exempt in self.exempt_paths:
            if path == exempt:
                return True
            # Support wildcard prefixes like "/docs*"
            if exempt.endswith("*") and path.startswith(exempt[:-1]):
                return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = edup.settings.get_settings()

        if not settings.auth_enabled:
            return await call_next(request)  # type: ignore[no-any-return]

        if self._is_exempt(request.url.path):
            return await call_next(request)  # type: ignore[no-any-return]

        header_name = settings.api_key_header
        valid_keys = set(settings.parsed_api_keys)

        api_key = request.headers.get(header_name)
        if not api_key:
            logger.warning(
                "auth_missing path=%s correlation_id=%s",
                request.url.path,
                getattr(request.state, "correlation_id", "unknown"),
            )
            return JSONResponse(  # type: ignore[return-value]
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": f"Missing API key. Provide via '{header_name}' header.",
                    "details": None,
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if api_key not in valid_keys:
            logger.warning(
                "auth_invalid path=%s correlation_id=%s",
                request.url.path,
                getattr(request.state, "correlation_id", "unknown"),
            )
            return JSONResponse(  # type: ignore[return-value]
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid API key.",
                    "details": None,
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )

        return await call_next(request)  # type: ignore[no-any-return]


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the FastAPI application."""
    settings = edup.settings.get_settings()

    # Validate production settings
    if settings.is_production:
        issues = edup.settings.validate_production_settings(settings)
        if issues:
            for issue in issues:
                logger.error("production_config_issue: %s", issue)
            raise RuntimeError(f"{PRODUCTION_CONFIG_INVALID_MSG}: {'; '.join(issues)}")  # noqa: TRY003

    # 1. Request timing and correlation ID (outermost for full request timing)
    app.add_middleware(RequestTimingMiddleware, log_timing=settings.log_request_timing)  # type: ignore[arg-type]

    # 2. Request size limit
    app.add_middleware(RequestSizeLimitMiddleware, max_size_bytes=settings.max_request_size_bytes)  # type: ignore[arg-type]

    # 3. Trusted host middleware (if enabled)
    if settings.trusted_hosts_enabled:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.parsed_trusted_hosts,
        )
        logger.info("trusted_hosts_enabled allowed_hosts=%s", settings.parsed_trusted_hosts)

    # 4. CORS middleware
    if settings.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.parsed_cors_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.parsed_cors_methods,
            allow_headers=settings.parsed_cors_headers,
        )
        logger.info("cors_enabled origins=%s", settings.parsed_cors_origins)

    # 5. API Key authentication (always added, checks settings at request time)
    app.add_middleware(APIKeyAuthMiddleware)  # type: ignore[arg-type]
    if settings.auth_enabled:
        logger.info("auth_enabled header=%s keys_count=%d", settings.api_key_header, len(settings.parsed_api_keys))

    # 6. Rate limiting (always added, checks settings at request time)
    app.add_middleware(RateLimitMiddleware)  # type: ignore[arg-type]
    if settings.rate_limit_enabled:
        logger.info(
            "rate_limit_enabled requests=%d window=%ds",
            settings.rate_limit_requests,
            settings.rate_limit_window_seconds,
        )

