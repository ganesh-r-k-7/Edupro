"""
main.py — FastAPI application for EduPro Enrollment Prediction API.

Endpoints:
- GET /health: API status, model availability, model identity/version
- GET /model-info: Safe model information (name, type, version, features, metadata)
- POST /predict/enrollment: Enrollment prediction using canonical feature contract
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

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
from edup.models.metadata import ModelMetadata, load_model_with_metadata

# Configure logging
configure_logging()
logger = get_logger("edup.api")

# Global model state (loaded once per process)
_model: Any = None
_model_metadata: ModelMetadata | None = None
_model_load_error: str | None = None


def _load_model_and_metadata() -> tuple[Any | None, ModelMetadata | None, str | None]:
    """Load the enrollment model and its metadata once per process."""
    global _model, _model_metadata, _model_load_error  # noqa: PLW0603

    if _model is not None or _model_load_error is not None:
        return _model, _model_metadata, _model_load_error

    try:
        # Try to load the Phase 1 model first (preferred), fallback to legacy
        phase1_path = Path(MODELS_DIR) / "enrollment_model_phase1.pkl"
        legacy_path = Path(MODELS_DIR) / "enrollment_model.pkl"

        model_path = phase1_path if phase1_path.exists() else legacy_path

        _model, _model_metadata = load_model_with_metadata(model_path)
        logger.info("Loaded enrollment model from %s", model_path.name)

        if _model_metadata:
            logger.info("Model: %s (status: %s)", _model_metadata.model_name, _model_metadata.status)

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
)


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


class EnrollmentPredictionRequest(BaseModel):
    """Enrollment prediction request based on Streamlit form contract."""

    course_category: str = Field(..., description="Course category")
    course_level: str = Field(..., description="Course level")
    course_price: float = Field(..., description="Course price in USD")
    course_duration: float = Field(..., description="Course duration in hours")
    teacher_experience: float = Field(..., description="Teacher years of experience")
    teacher_rating: float = Field(..., description="Teacher rating (1-5)")
    course_type: str = Field(default="Paid", description="Course type (Paid or Free)")
    course_rating: float = Field(default=4.0, description="Expected course rating (1-5)")
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
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("course_price must be a number")  # noqa: TRY003
        if v < MIN_PRICE or v > MAX_PRICE:
            raise ValueError(f"course_price must be between ${MIN_PRICE:.0f} and ${MAX_PRICE:.0f}")  # noqa: TRY003
        return float(v)

    @field_validator("course_duration")
    @classmethod
    def validate_duration(cls, v: float) -> float:
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("course_duration must be a number")  # noqa: TRY003
        if v < MIN_DURATION or v > MAX_DURATION:
            raise ValueError(f"course_duration must be between {MIN_DURATION:.0f} and {MAX_DURATION:.0f} hours")  # noqa: TRY003
        return float(v)

    @field_validator("course_rating", "teacher_rating")
    @classmethod
    def validate_rating(cls, v: float) -> float:
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("rating must be a number")  # noqa: TRY003
        if v < MIN_RATING or v > MAX_RATING:
            raise ValueError(f"rating must be between {MIN_RATING:.1f} and {MAX_RATING:.1f}")  # noqa: TRY003
        return float(v)

    @field_validator("teacher_experience")
    @classmethod
    def validate_experience(cls, v: float) -> float:
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("teacher_experience must be a number")  # noqa: TRY003
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
    }

