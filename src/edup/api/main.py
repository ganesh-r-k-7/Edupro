"""
main.py — FastAPI application for EduPro Enrollment Prediction API.

Endpoints:
- GET /health: API status, model availability, model identity/version
- GET /health/live: Liveness probe (process alive)
- GET /health/ready: Readiness probe (can serve predictions)
- GET /model-info: Safe model information (name, type, version, features, metadata)
- POST /predict/enrollment: Enrollment prediction using canonical feature contract
- GET /model-registry: List all registry versions
- GET /model-registry/{version}: Get specific version details
- GET /: Root info
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import joblib
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from pydantic.functional_validators import BeforeValidator

from edup.config import (
    COURSE_CATEGORIES,
    COURSE_LEVELS,
    COURSE_TYPES,
    FEATURE_COLUMNS,
    MAX_DURATION,
    MAX_EXPERIENCE,
    MAX_PRICE,
    MAX_RATING,
    MIN_DURATION,
    MIN_EXPERIENCE,
    MIN_PRICE,
    MIN_RATING,
    MODELS_DIR,
    PAYMENT_METHODS,
)
from edup.exceptions import ModelLoadError
from edup.features import (
    assert_feature_frame_contract,
    build_feature_frame,
    validate_course_inputs,
)
from edup.logging import configure_logging, get_logger
from edup.models import get_registry
from edup.models.metadata import ModelMetadata, load_model_with_metadata
from edup.api.middleware import setup_middleware
from edup.settings import get_settings

# Configure logging
settings = get_settings()
configure_logging(
    level=getattr(logging, settings.log_level),
    json_format=settings.log_format == "json",
    include_correlation_id=True,
)
logger = get_logger("edup.api")

# Global model state (loaded once per process)
_model: Any = None
_model_metadata: ModelMetadata | None = None
_model_load_error: str | None = None


def _load_model_and_metadata() -> tuple[Any | None, ModelMetadata | None, str | None]:
    """Load the active enrollment model from the registry once per process."""
    global _model, _model_metadata, _model_load_error  # noqa: PLW0603

    if _model is not None or _model_load_error is not None:
        return _model, _model_metadata, _model_load_error

    try:
        registry = get_registry()
        active_path = registry.get_active_model_path()
        active_entry = registry.get_active_version()

        if active_path is not None and active_path.exists() and active_entry is not None:
            model_path = active_path
            logger.info("Loading active model from registry: %s", model_path.name)
            # Load model artifact
            _model = joblib.load(model_path)
            # Build metadata from registry entry (avoids file naming mismatch)
            _model_metadata = ModelMetadata(
                model_name=active_entry.model_name,
                model_type=active_entry.model_type,
                artifact_filename=active_entry.artifact_filename,
                status=active_entry.status,
                training_date_utc=active_entry.training_date_utc,
                target_variable=active_entry.target_variable,
                feature_names=active_entry.feature_names,
                feature_order=active_entry.feature_order,
                training_data_fingerprint=active_entry.training_data_fingerprint,
                training_data_shape=active_entry.training_data_shape,
                training_data_date_range=active_entry.training_data_date_range,
                metrics=active_entry.metrics,
                artifact_sha256=active_entry.artifact_sha256,
                artifact_size_bytes=active_entry.artifact_size_bytes,
                notes=active_entry.notes,
            )
            logger.info("Model: %s (status: %s)", _model_metadata.model_name, _model_metadata.status)
        else:
            # Fallback to Phase 1 model only (legacy model is incompatible with current feature engineering)
            phase1_path = Path(MODELS_DIR) / "enrollment_model_phase1.pkl"
            if phase1_path.exists():
                logger.warning("No active model in registry; falling back to %s", phase1_path.name)
                _model, _model_metadata = load_model_with_metadata(phase1_path)
            else:
                _model_load_error = "No compatible enrollment model found. Train a Phase 1 model or register a model in the registry."
                logger.error(_model_load_error)

    except ModelLoadError as exc:
        _model_load_error = str(exc)
        logger.exception("Failed to load enrollment model")
    except Exception as exc:
        _model_load_error = f"Unexpected error loading model: {exc}"
        logger.exception("Unexpected error loading enrollment model")

    return _model, _model_metadata, _model_load_error


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler - load model on startup."""
    _load_model_and_metadata()
    yield


app = FastAPI(
    title="EduPro Enrollment Prediction API",
    description="REST API for course enrollment predictions using the EduPro predictive model.",
    version="1.3.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)

# Setup middleware (auth, rate limiting, CORS, etc.)
setup_middleware(app)


# ─── Request/Response Models ───────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="API status")
    model_available: bool = Field(..., description="Whether the enrollment model is loaded and available")
    model_name: str | None = Field(None, description="Name of the loaded model")
    model_version: str | None = Field(None, description="Model version/artifact identity")


class ModelInfoResponse(BaseModel):
    """Model information response."""

    model_name: str = Field(..., description="Model name")
    model_type: str = Field(..., description="Model type/algorithm")
    model_version: str | None = Field(None, description="Model artifact filename")
    status: str = Field(..., description="Model status (active, legacy, retired, cached)")
    feature_names: list[str] = Field(..., description="Feature names in canonical order")
    target_variable: str | None = Field(None, description="Target variable name")
    training_date_utc: str | None = Field(None, description="Training date in UTC")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Model evaluation metrics")
    notes: str | None = Field(None, description="Additional notes")
    registry_version: str | None = Field(None, description="Registry version identifier")
    active_since_utc: str | None = Field(None, description="When this version became active")


def _reject_bool(v: Any) -> Any:
    """Reject boolean values before type coercion."""
    if isinstance(v, bool):
        raise ValueError("must be a number, not boolean")  # noqa: TRY004, TRY003
    return v


NonBoolFloat = Annotated[float, BeforeValidator(_reject_bool)]
NonBoolInt = Annotated[int, BeforeValidator(_reject_bool)]


class EnrollmentPredictionRequest(BaseModel):
    """Enrollment prediction request based on Streamlit form contract."""

    course_category: str = Field(..., description="Course category")
    course_level: str = Field(..., description="Course level")
    course_price: NonBoolFloat = Field(..., description="Course price in USD")
    course_duration: NonBoolFloat = Field(..., description="Course duration in hours")
    teacher_experience: NonBoolFloat = Field(..., description="Teacher years of experience")
    teacher_rating: NonBoolFloat = Field(..., description="Teacher rating (1-5)")
    course_type: str = Field(default="Paid", description="Course type (Paid or Free)")
    course_rating: NonBoolFloat = Field(default=4.0, description="Expected course rating (1-5)")
    payment_method: str = Field(default="Credit Card", description="Payment method (informational only)")

    @field_validator("course_category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in COURSE_CATEGORIES:
            raise ValueError(f"course_category must be one of {COURSE_CATEGORIES}")  # noqa: TRY003
        return v

    @field_validator("course_level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v not in COURSE_LEVELS:
            raise ValueError(f"course_level must be one of {COURSE_LEVELS}")  # noqa: TRY003
        return v

    @field_validator("course_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in COURSE_TYPES:
            raise ValueError(f"course_type must be one of {COURSE_TYPES}")  # noqa: TRY003
        return v

    @field_validator("payment_method")
    @classmethod
    def validate_payment(cls, v: str) -> str:
        if v not in PAYMENT_METHODS:
            raise ValueError(f"payment_method must be one of {PAYMENT_METHODS}")  # noqa: TRY003
        return v

    @field_validator("course_price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v < MIN_PRICE or v > MAX_PRICE:
            raise ValueError(f"course_price must be between ${MIN_PRICE:.0f} and ${MAX_PRICE:.0f}")  # noqa: TRY003
        return float(v)

    @field_validator("course_duration")
    @classmethod
    def validate_duration(cls, v: float) -> float:
        if v < MIN_DURATION or v > MAX_DURATION:
            raise ValueError(f"course_duration must be between {MIN_DURATION:.0f} and {MAX_DURATION:.0f} hours")  # noqa: TRY003
        return float(v)

    @field_validator("course_rating", "teacher_rating")
    @classmethod
    def validate_rating(cls, v: float) -> float:
        if v < MIN_RATING or v > MAX_RATING:
            raise ValueError(f"rating must be between {MIN_RATING:.1f} and {MAX_RATING:.1f}")  # noqa: TRY003
        return float(v)

    @field_validator("teacher_experience")
    @classmethod
    def validate_experience(cls, v: float) -> float:
        if v < MIN_EXPERIENCE or v > MAX_EXPERIENCE:
            raise ValueError(f"teacher_experience must be between {MIN_EXPERIENCE} and {MAX_EXPERIENCE} years")  # noqa: TRY003
        return float(v)


class EnrollmentPredictionResponse(BaseModel):
    """Enrollment prediction response."""

    predicted_enrollment: float = Field(..., description="Predicted enrollment count (non-negative)")
    model_name: str | None = Field(None, description="Name of the model used for prediction")
    model_version: str | None = Field(None, description="Model artifact filename")
    features_used: list[str] = Field(default_factory=list, description="Feature names in canonical order")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


# ─── Exception Handlers ────────────────────────────────────────────────────────


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent JSON format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="HTTPException",
            message=exc.detail,
            details={"status_code": exc.status_code} if exc.status_code else None,
        ).model_dump(),
    )


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError):
    """Handle validation errors with consistent JSON format."""
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="ValidationError",
            message=str(exc),
            details={"field": "request_body"},
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request: Request, _exc: Exception):
    """Handle unexpected errors without exposing stack traces."""
    logger.exception("Unhandled exception in API request")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred",
            details=None,
        ).model_dump(),
    )


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns API status, model availability, and model identity/version.
    Does not reload the model unnecessarily.
    """
    model, metadata, load_error = _load_model_and_metadata()

    return HealthResponse(
        status="healthy" if model is not None else "degraded",
        model_available=model is not None,
        model_name=metadata.model_name if metadata else None,
        model_version=metadata.artifact_filename if metadata else None,
    )


@app.get("/health/live", response_model=HealthResponse, tags=["Health"])
async def liveness_check() -> HealthResponse:
    """
    Liveness probe endpoint.

    Returns whether the application process is running.
    Does not check model or data availability.
    """
    return HealthResponse(
        status="alive",
        model_available=False,
        model_name=None,
        model_version=None,
    )


@app.get("/health/ready", tags=["Health"])
async def readiness_check(request: Request) -> JSONResponse:
    """
    Readiness probe endpoint.

    Returns whether the service can serve predictions.
    Checks model availability and optionally registry/data availability.
    """
    settings = get_settings()
    model, metadata, load_error = _load_model_and_metadata()

    checks = {
        "model_loaded": model is not None,
        "model_load_error": load_error is None,
    }

    # Optional detailed checks
    if settings.health_check_detailed:
        try:
            registry = get_registry()
            active_entry = registry.get_active_version()
            checks["registry_accessible"] = True
            checks["active_model_registered"] = active_entry is not None
        except Exception as exc:
            logger.warning("readiness_registry_check_failed: %s", exc)
            checks["registry_accessible"] = False
            checks["active_model_registered"] = False

    all_healthy = all(v for v in checks.values() if isinstance(v, bool))

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "model_name": metadata.model_name if metadata else None,
            "model_version": metadata.artifact_filename if metadata else None,
        },
    )


@app.get("/model-info", response_model=ModelInfoResponse, tags=["Model"])
async def model_info() -> ModelInfoResponse:
    """
    Get safe model information.

    Returns model name, type, version, features, training metadata, and status.
    Never exposes filesystem paths, secrets, or sensitive internal information.
    """
    model, metadata, load_error = _load_model_and_metadata()

    if model is None or metadata is None:
        raise HTTPException(
            status_code=503,
            detail="Model not available. Check model artifacts and logs.",
        )

    # Get registry info for active model
    registry = get_registry()
    active_entry = registry.get_active_version()
    registry_version = active_entry.version if active_entry else None
    active_since = active_entry.promoted_at_utc if active_entry else None

    return ModelInfoResponse(
        model_name=metadata.model_name,
        model_type=metadata.model_type,
        model_version=metadata.artifact_filename,
        status=metadata.status,
        feature_names=metadata.feature_names,
        target_variable=metadata.target_variable,
        training_date_utc=metadata.training_date_utc,
        metrics=metadata.metrics,
        notes=metadata.notes,
        registry_version=registry_version,
        active_since_utc=active_since,
    )


@app.post("/predict/enrollment", response_model=EnrollmentPredictionResponse, tags=["Prediction"])
async def predict_enrollment_endpoint(request: EnrollmentPredictionRequest) -> EnrollmentPredictionResponse:
    """
    Predict enrollment for a course configuration.

    Uses the canonical feature engineering and validation shared with the Streamlit dashboard.
    Returns a numeric enrollment prediction with model identity/version.
    """
    model, metadata, load_error = _load_model_and_metadata()

    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Enrollment model not loaded. Check model artifacts and server logs.",
        )

    try:
        # Validate and normalize inputs through shared contract
        values = validate_course_inputs(
            course_category=request.course_category,
            course_level=request.course_level,
            course_price=request.course_price,
            course_duration=request.course_duration,
            teacher_experience=request.teacher_experience,
            teacher_rating=request.teacher_rating,
            course_type=request.course_type,
            course_rating=request.course_rating,
            payment_method=request.payment_method,
        )

        # Build feature frame using shared feature engineering
        feature_frame = build_feature_frame(**values)
        assert_feature_frame_contract(feature_frame)

        # Predict using shared prediction function
        prediction = model.predict(feature_frame)[0]
        prediction = float(max(0, prediction))

        logger.info(
            "Prediction: %.2f for category=%s level=%s price=%.2f type=%s",
            prediction,
            request.course_category,
            request.course_level,
            request.course_price,
            request.course_type,
        )

        return EnrollmentPredictionResponse(
            predicted_enrollment=prediction,
            model_name=metadata.model_name if metadata else None,
            model_version=metadata.artifact_filename if metadata else None,
            features_used=FEATURE_COLUMNS,
        )

    except ValueError as exc:
        # Validation errors from shared feature engineering
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Let unexpected exceptions propagate to the general exception handler


# ─── Registry Endpoints ────────────────────────────────────────────────────────


class RegistryListResponse(BaseModel):
    """Response for listing registry versions."""

    versions: list[dict[str, Any]]


class RegistryVersionResponse(BaseModel):
    """Response for a single registry version."""

    version: str
    model_name: str
    model_type: str
    artifact_filename: str
    status: str
    training_date_utc: str
    target_variable: str
    feature_names: list[str]
    metrics: dict[str, Any]
    artifact_sha256: str
    promoted_at_utc: str | None
    promoted_by: str | None


@app.get("/model-registry", response_model=RegistryListResponse, tags=["Model Registry"])
async def list_registry_versions() -> RegistryListResponse:
    """
    List all registered model versions.

    Returns version metadata for all registered models, newest first.
    Does not expose filesystem paths.
    """
    registry = get_registry()
    versions = registry.list_versions()

    return RegistryListResponse(
        versions=[
            {
                "version": v.version,
                "model_name": v.model_name,
                "model_type": v.model_type,
                "artifact_filename": v.artifact_filename,
                "status": v.status,
                "training_date_utc": v.training_date_utc,
                "target_variable": v.target_variable,
                "feature_names": v.feature_names,
                "metrics": v.metrics,
                "artifact_sha256": v.artifact_sha256,
                "promoted_at_utc": v.promoted_at_utc,
                "promoted_by": v.promoted_by,
            }
            for v in versions
        ]
    )


@app.get("/model-registry/{version}", response_model=RegistryVersionResponse, tags=["Model Registry"])
async def get_registry_version(version: str) -> RegistryVersionResponse:
    """
    Get details for a specific registered model version.

    Does not expose filesystem paths.
    """
    registry = get_registry()
    entry = registry.get_version(version)

    if entry is None:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    return RegistryVersionResponse(
        version=entry.version,
        model_name=entry.model_name,
        model_type=entry.model_type,
        artifact_filename=entry.artifact_filename,
        status=entry.status,
        training_date_utc=entry.training_date_utc,
        target_variable=entry.target_variable,
        feature_names=entry.feature_names,
        metrics=entry.metrics,
        artifact_sha256=entry.artifact_sha256,
        promoted_at_utc=entry.promoted_at_utc,
        promoted_by=entry.promoted_by,
    )


# ─── Root Endpoint ─────────────────────────────────────────────────────────────


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "name": "EduPro Enrollment Prediction API",
        "version": "1.3.0",
        "docs": "/docs",
        "health": "/health",
        "model_info": "/model-info",
        "predict": "/predict/enrollment",
        "model_registry": "/model-registry",
    }
