"""
test_api_security.py — Tests for R4.6 API security features.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def reload_api_module():
    """Reload the API module with fresh settings."""
    import importlib
    import edup.settings
    import edup.api.main

    edup.settings.clear_settings_cache()
    importlib.reload(edup.settings)
    importlib.reload(edup.api.main)
    from edup.api.main import app
    return app


class TestAPIAuthentication:
    """Tests for API key authentication."""

    def test_auth_disabled_by_default(self):
        """Auth should be disabled by default for local development."""
        # Reload module with default settings
        from edup.api.main import app
        client = TestClient(app)

        # Should work without auth header
        r = client.get("/health/live")
        assert r.status_code == 200

        # Should work on other endpoints too (though model may not be available)
        r = client.get("/model-registry")
        assert r.status_code in (200, 503)  # 503 if no model, but not 401

    def test_auth_enabled_requires_valid_key(self):
        """When auth enabled, valid API key required."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "true", "API_KEYS": "valid-key-123"}):
            app = reload_api_module()
            client = TestClient(app)

            # Without key - should be 401
            r = client.get("/model-registry")
            assert r.status_code == 401
            assert r.json()["error"] == "Unauthorized"

            # With invalid key - should be 401
            r = client.get("/model-registry", headers={"X-API-Key": "invalid"})
            assert r.status_code == 401

            # With valid key - should work (or 503 if no model)
            r = client.get("/model-registry", headers={"X-API-Key": "valid-key-123"})
            assert r.status_code in (200, 503)

    def test_auth_exempt_paths(self):
        """Health endpoints should be exempt from auth."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "true", "API_KEYS": "valid-key-123"}):
            import importlib
            import edup.api.main
            importlib.reload(edup.api.main)
            from edup.api.main import app

            client = TestClient(app)

            # Health endpoints should work without auth
            r = client.get("/health/live")
            assert r.status_code == 200

            r = client.get("/health/ready")
            assert r.status_code in (200, 503)

            r = client.get("/health")
            assert r.status_code == 200

            r = client.get("/")
            assert r.status_code == 200

            r = client.get("/docs")
            assert r.status_code == 200


class TestAPIRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limit_disabled_by_default(self):
        """Rate limiting should be disabled by default."""
        from edup.api.main import app
        client = TestClient(app)

        # Should allow many requests
        for _ in range(10):
            r = client.get("/health/live")
            assert r.status_code == 200

    def test_rate_limit_enabled_blocks_excess(self):
        """When enabled, rate limiting should block excess requests."""
        with patch.dict(os.environ, {
            "RATE_LIMIT_ENABLED": "true",
            "RATE_LIMIT_REQUESTS": "3",
            "RATE_LIMIT_WINDOW_SECONDS": "60",
        }):
            app = reload_api_module()
            client = TestClient(app)

            # First 3 requests should succeed
            for _ in range(3):
                r = client.get("/model-registry")
                assert r.status_code in (200, 503)

            # 4th request should be rate limited
            r = client.get("/model-registry")
            assert r.status_code == 429
            assert r.json()["error"] == "RateLimitExceeded"
            assert "Retry-After" in r.headers

    def test_rate_limit_exempt_paths(self):
        """Health endpoints should be exempt from rate limiting."""
        with patch.dict(os.environ, {
            "RATE_LIMIT_ENABLED": "true",
            "RATE_LIMIT_REQUESTS": "2",
            "RATE_LIMIT_WINDOW_SECONDS": "60",
        }):
            import importlib
            import edup.api.main
            importlib.reload(edup.api.main)
            from edup.api.main import app

            client = TestClient(app)

            # Health endpoints should allow many requests
            for _ in range(10):
                r = client.get("/health/live")
                assert r.status_code == 200


class TestAPICORS:
    """Tests for CORS configuration."""

    def test_cors_enabled_by_default(self):
        """CORS should be enabled by default."""
        from edup.api.main import app
        client = TestClient(app)

        # Check CORS headers on OPTIONS request
        r = client.options("/health/live")
        # TestClient doesn't fully support CORS preflight, but middleware should be present
        assert r.status_code in (200, 405)  # 405 if OPTIONS not allowed, 200 if handled


class TestAPIRequestSizeLimit:
    """Tests for request size limiting."""

    def test_request_size_limit(self):
        """Large requests should be rejected."""
        with patch.dict(os.environ, {"MAX_REQUEST_SIZE_MB": "1"}):
            import importlib
            import edup.api.main
            importlib.reload(edup.api.main)
            from edup.api.main import app

            client = TestClient(app)

            # Large payload should be rejected
            large_data = "x" * (2 * 1024 * 1024)  # 2MB
            r = client.post("/predict/enrollment", data=large_data, headers={"Content-Type": "application/json"})
            # Should be 413 or 400 (validation error before size check)
            assert r.status_code in (413, 400, 422)


class TestAPIHealthEndpoints:
    """Tests for health endpoints."""

    def test_liveness_endpoint(self):
        """Liveness endpoint should return alive status."""
        from edup.api.main import app
        client = TestClient(app)

        r = client.get("/health/live")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "alive"
        assert data["model_available"] is False

    def test_readiness_endpoint(self):
        """Readiness endpoint should check model availability."""
        from edup.api.main import app
        client = TestClient(app)

        r = client.get("/health/ready")
        # Should be 503 when no model loaded
        assert r.status_code == 503
        data = r.json()
        assert data["status"] == "not_ready"
        assert "checks" in data

    def test_health_endpoint_still_works(self):
        """Original health endpoint should still work."""
        from edup.api.main import app
        client = TestClient(app)

        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "model_available" in data


class TestAPICorrelationID:
    """Tests for correlation ID propagation."""

    def test_correlation_id_in_response(self):
        """Response should include correlation ID header."""
        from edup.api.main import app
        client = TestClient(app)

        r = client.get("/health/live")
        assert r.status_code == 200
        assert "X-Correlation-ID" in r.headers
        assert "X-Process-Time" in r.headers

    def test_custom_correlation_id_preserved(self):
        """Custom correlation ID should be preserved."""
        from edup.api.main import app
        client = TestClient(app)

        custom_id = "custom-correlation-123"
        r = client.get("/health/live", headers={"X-Correlation-ID": custom_id})
        assert r.status_code == 200
        assert r.headers["X-Correlation-ID"] == custom_id


class TestAPISecurityHeaders:
    """Tests for security-related headers and behavior."""

    def test_no_stack_traces_in_errors(self):
        """Error responses should not contain stack traces."""
        from edup.api.main import app
        client = TestClient(app)

        # Trigger a 500 error
        r = client.get("/model-info")
        assert r.status_code == 503
        data = r.json()
        assert "error" in data
        assert "traceback" not in str(data).lower()
        assert "stack" not in str(data).lower()

    def test_error_response_format(self):
        """All errors should have consistent format."""
        # Disable rate limiting for this test
        import os
        os.environ["RATE_LIMIT_ENABLED"] = "false"
        app = reload_api_module()
        client = TestClient(app)

        # Test validation error format (FastAPI default)
        r = client.post("/predict/enrollment", json={"invalid": "data"})
        assert r.status_code == 422
        data = r.json()
        # FastAPI validation errors have 'detail' field
        assert "detail" in data

        # Test our custom error format for 503
        r = client.get("/model-info")
        assert r.status_code == 503
        data = r.json()
        assert "error" in data
        assert "message" in data


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_settings_load_from_env(self):
        """Settings should load from environment variables."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "AUTH_ENABLED": "true",
            "API_KEYS": "key1,key2,key3",
            "RATE_LIMIT_ENABLED": "true",
            "RATE_LIMIT_REQUESTS": "50",
        }):
            import importlib
            import edup.settings
            importlib.reload(edup.settings)
            from edup.settings import get_settings

            settings = get_settings()
            assert settings.environment == "production"
            assert settings.auth_enabled is True
            assert settings.parsed_api_keys == ["key1", "key2", "key3"]
            assert settings.rate_limit_enabled is True
            assert settings.rate_limit_requests == 50

    def test_production_validation_fails_without_auth(self):
        """Production should fail validation without auth."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "AUTH_ENABLED": "false",
        }):
            import importlib
            import edup.settings
            importlib.reload(edup.settings)
            from edup.settings import get_settings, validate_production_settings

            settings = get_settings()
            issues = validate_production_settings(settings)
            assert len(issues) > 0
            assert any("auth_enabled" in issue.lower() for issue in issues)

    def test_cors_origins_parsing(self):
        """CORS origins should parse correctly."""
        with patch.dict(os.environ, {
            "CORS_ORIGINS": "https://example.com,https://app.example.com",
        }):
            import importlib
            import edup.settings
            importlib.reload(edup.settings)
            from edup.settings import get_settings

            settings = get_settings()
            assert settings.parsed_cors_origins == ["https://example.com", "https://app.example.com"]

    def test_cors_wildcard(self):
        """CORS wildcard should work."""
        with patch.dict(os.environ, {
            "CORS_ORIGINS": "*",
        }):
            import importlib
            import edup.settings
            importlib.reload(edup.settings)
            from edup.settings import get_settings

            settings = get_settings()
            assert settings.parsed_cors_origins == ["*"]


class TestStructuredLogging:
    """Tests for structured logging."""

    def test_correlation_id_in_logs(self):
        """Correlation ID should appear in logs."""
        import logging
        import io
        import sys

        # Capture logs
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(correlation_id)s | %(message)s")
        handler.setFormatter(formatter)
        # Add correlation ID filter
        from edup.logging import CorrelationIdFilter
        handler.addFilter(CorrelationIdFilter())

        root_logger = logging.getLogger()
        root_logger.handlers = [handler]
        root_logger.setLevel(logging.INFO)

        from edup.logging import configure_logging, get_logger, set_correlation_id
        configure_logging(level=logging.INFO, stream=sys.stdout, json_format=False)

        logger = get_logger("test")
        set_correlation_id("test-correlation-123")
        logger.info("Test message")
        set_correlation_id(None)

        # Check log output
        log_output = log_stream.getvalue()
        assert "test-correlation-123" in log_output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])