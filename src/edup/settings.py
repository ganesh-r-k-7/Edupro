"""
settings.py — Environment-aware configuration for EduPro.

Provides typed configuration via Pydantic Settings with support for
environment variables and .env files. Development defaults are convenient;
production requires explicit configuration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Environment ──────────────────────────────────────────────────────────────
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Runtime environment. Affects defaults and validation.",
    )

    # ─── API Server ──────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")
    api_workers: int = Field(default=1, description="Number of Uvicorn workers")

    # ─── Authentication ──────────────────────────────────────────────────────────
    auth_enabled: bool = Field(
        default=False,
        description="Enable API key authentication. Disable for local development.",
    )
    api_keys: str = Field(
        default="",
        description="Comma-separated list of valid API keys. Required if auth_enabled=True.",
    )
    api_key_header: str = Field(
        default="X-API-Key",
        description="Header name for API key authentication.",
    )

    @field_validator("api_keys")
    @classmethod
    def _validate_api_keys(cls, v: str) -> str:
        if v:
            keys = [k.strip() for k in v.split(",") if k.strip()]
            if len(keys) != len(set(keys)):
                raise ValueError("API keys must be unique")  # noqa: TRY003
        return v

    # ─── Rate Limiting ───────────────────────────────────────────────────────────
    rate_limit_enabled: bool = Field(
        default=False,
        description="Enable rate limiting. Disable for local development.",
    )
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description="Maximum requests per window.",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Rate limit window in seconds.",
    )

    # ─── CORS ────────────────────────────────────────────────────────────────────
    cors_enabled: bool = Field(
        default=True,
        description="Enable CORS middleware.",
    )
    cors_origins: str = Field(
        default="*",
        description="Comma-separated allowed origins. Use '*' for all (dev only).",
    )
    cors_allow_credentials: bool = Field(default=False)
    cors_allow_methods: str = Field(default="GET,POST,OPTIONS")
    cors_allow_headers: str = Field(default="*")

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors_origins(cls, v: str) -> str:
        if v != "*":
            origins = [o.strip() for o in v.split(",") if o.strip()]
            for origin in origins:
                if not (origin.startswith("http://") or origin.startswith("https://")):
                    raise ValueError(f"Invalid CORS origin: {origin}")  # noqa: TRY003
        return v

    # ─── Trusted Hosts ───────────────────────────────────────────────────────────
    trusted_hosts_enabled: bool = Field(
        default=False,
        description="Enable trusted host middleware. Disable for local development.",
    )
    trusted_hosts: str = Field(
        default="localhost,127.0.0.1",
        description="Comma-separated allowed hostnames.",
    )

    # ─── Request Limits ──────────────────────────────────────────────────────────
    max_request_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum request body size in MB.",
    )

    # ─── Paths ───────────────────────────────────────────────────────────────────
    data_dir: str = Field(default="data", description="Data directory path")
    models_dir: str = Field(default="models", description="Models directory path")
    registry_dir: str = Field(default="models/registry", description="Model registry directory path")

    # ─── Logging ─────────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level.",
    )
    log_format: Literal["json", "text"] = Field(
        default="text",
        description="Log output format. JSON for production, text for development.",
    )
    log_request_timing: bool = Field(
        default=True,
        description="Log request timing information.",
    )

    # ─── Health Checks ───────────────────────────────────────────────────────────
    health_check_detailed: bool = Field(
        default=True,
        description="Include detailed checks in readiness endpoint.",
    )

    # ─── Derived Properties ──────────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def parsed_api_keys(self) -> list[str]:
        """Get list of valid API keys."""
        if not self.api_keys:
            return []
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def parsed_cors_origins(self) -> list[str]:
        """Get list of allowed CORS origins."""
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def parsed_trusted_hosts(self) -> list[str]:
        """Get list of trusted hosts."""
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def parsed_cors_methods(self) -> list[str]:
        """Get list of allowed CORS methods."""
        return [m.strip() for m in self.cors_allow_methods.split(",") if m.strip()]

    @property
    def parsed_cors_headers(self) -> list[str]:
        """Get list of allowed CORS headers."""
        if self.cors_allow_headers == "*":
            return ["*"]
        return [h.strip() for h in self.cors_allow_headers.split(",") if h.strip()]

    @property
    def max_request_size_bytes(self) -> int:
        """Maximum request size in bytes."""
        return self.max_request_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear the settings cache. Useful for testing."""
    get_settings.cache_clear()


def validate_production_settings(settings: Settings) -> list[str]:
    """Validate settings for production deployment. Returns list of issues."""
    issues = []

    if settings.is_production:
        if not settings.auth_enabled:
            issues.append("Production requires auth_enabled=True")
        if not settings.parsed_api_keys:
            issues.append("Production requires at least one API key in api_keys")
        if not settings.rate_limit_enabled:
            issues.append("Production requires rate_limit_enabled=True")
        if not settings.trusted_hosts_enabled:
            issues.append("Production requires trusted_hosts_enabled=True")
        if settings.cors_origins == "*":
            issues.append("Production requires explicit cors_origins (not '*')")
        if settings.log_format != "json":
            issues.append("Production requires log_format='json'")
        if settings.log_level == "DEBUG":
            issues.append("Production should not use DEBUG log level")

    return issues
