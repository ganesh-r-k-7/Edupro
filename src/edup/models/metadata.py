"""
metadata.py — Model metadata schema and utilities for EduPro.

Provides a standardized metadata format for all model artifacts,
enabling reproducibility, auditability, and CI validation.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import joblib
import numpy as np
import pandas as pd

from edup.config import (
    FEATURE_COLUMNS,
    MODELS_DIR,
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
)


ModelStatus = Literal["active", "legacy", "retired", "cached"]


@dataclass
class ModelMetadata:
    """Standardized metadata for a model artifact."""

    # Identity
    model_name: str
    model_type: str
    artifact_filename: str
    status: ModelStatus

    # Training information
    training_date_utc: Optional[str] = None
    target_variable: Optional[str] = None
    feature_names: list[str] = field(default_factory=list)
    feature_order: list[str] = field(default_factory=list)

    # Data provenance
    training_data_fingerprint: Optional[str] = None
    training_data_shape: Optional[tuple[int, int]] = None
    training_data_date_range: Optional[dict[str, str]] = None

    # Evaluation metrics
    metrics: dict[str, Any] = field(default_factory=dict)

    # Environment
    python_version: str = field(default_factory=lambda: f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    platform: str = field(default_factory=lambda: platform.platform())
    library_versions: dict[str, str] = field(default_factory=dict)

    # Artifact integrity
    artifact_sha256: Optional[str] = None
    artifact_size_bytes: Optional[int] = None

    # Additional context
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, handling non-serializable fields."""
        data = asdict(self)
        # Convert tuples to lists for JSON
        if data.get("training_data_shape"):
            data["training_data_shape"] = list(data["training_data_shape"])
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelMetadata":
        """Create from dictionary."""
        if "training_data_shape" in data and data["training_data_shape"]:
            data["training_data_shape"] = tuple(data["training_data_shape"])
        return cls(**data)

    def write(self, path: Path | str) -> None:
        """Write metadata to JSON file."""
        path = Path(path)
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def read(cls, path: Path | str) -> "ModelMetadata":
        """Read metadata from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def compute_file_sha256(path: Path | str) -> str:
    """Compute SHA256 hash of a file."""
    path = Path(path)
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_library_versions() -> dict[str, str]:
    """Get versions of key libraries."""
    versions = {}
    for lib_name in [
        "pandas", "numpy", "scikit-learn", "xgboost", "shap",
        "prophet", "plotly", "streamlit", "joblib", "scipy",
    ]:
        try:
            mod = __import__(lib_name.replace("-", "_"))
            versions[lib_name] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[lib_name] = "not installed"
    return versions


def compute_data_fingerprint(df: pd.DataFrame, columns: Optional[list[str]] = None) -> str:
    """Compute a deterministic fingerprint of a DataFrame."""
    if columns:
        df = df[columns].copy()
    # Use hash of column names, dtypes, and a sample of values
    hasher = hashlib.sha256()
    hasher.update(str(sorted(df.columns.tolist())).encode())
    hasher.update(str([str(df[c].dtype) for c in df.columns]).encode())
    # Sample up to 1000 rows for value hash
    sample = df.head(1000)
    for col in sample.columns:
        hasher.update(sample[col].values.tobytes())
    return hasher.hexdigest()[:16]


def load_model_with_metadata(
    model_path: Path | str,
    metadata_path: Optional[Path | str] = None,
) -> tuple[Any, Optional[ModelMetadata]]:
    """Load a model artifact and its metadata if available."""
    model_path = Path(model_path)
    model = joblib.load(model_path)

    metadata = None
    if metadata_path is None:
        metadata_path = model_path.with_suffix(".json")
    metadata_path = Path(metadata_path)
    if metadata_path.exists():
        metadata = ModelMetadata.read(metadata_path)

    return model, metadata


def validate_model_metadata(metadata: ModelMetadata) -> list[str]:
    """Validate model metadata and return list of issues (empty if valid)."""
    issues = []

    if not metadata.model_name:
        issues.append("model_name is required")
    if not metadata.model_type:
        issues.append("model_type is required")
    if not metadata.artifact_filename:
        issues.append("artifact_filename is required")
    if metadata.status not in ("active", "legacy", "retired", "cached"):
        issues.append(f"invalid status: {metadata.status}")

    if metadata.feature_names and metadata.feature_order:
        if set(metadata.feature_names) != set(metadata.feature_order):
            issues.append("feature_names and feature_order must contain the same features")

    if metadata.artifact_sha256 is None:
        issues.append("artifact_sha256 is missing (recommended for integrity verification)")

    return issues


def generate_metadata_for_existing_artifacts(models_dir: Path | str = MODELS_DIR) -> dict[str, ModelMetadata]:
    """Generate metadata for all existing model artifacts in the models directory."""
    models_dir = Path(models_dir)
    artifacts = {}

    # enrollment_model.pkl (legacy XGBoost)
    enrollment_path = models_dir / "enrollment_model.pkl"
    if enrollment_path.exists():
        sha256 = compute_file_sha256(enrollment_path)
        size = enrollment_path.stat().st_size
        metadata = ModelMetadata(
            model_name="enrollment_model",
            model_type="XGBRegressor (Pipeline with ColumnTransformer + OneHotEncoder + StandardScaler)",
            artifact_filename="enrollment_model.pkl",
            status="legacy",
            training_date_utc=None,  # Unknown historical date
            target_variable="EnrollmentCount (course-level)",
            feature_names=[
                "CoursePrice", "CourseDuration", "CourseRating", "TeacherRating",
                "YearsOfExperience", "EncodedCourseLevel", "TeacherRatingScore",
                "ExpertiseCategoryMatch", "TransactionMonth", "Quarter", "IsWeekend",
                "CourseCategory", "CourseType", "PriceBand", "DurationBucket",
                "RatingTier", "ExperienceBucket", "SeasonalityLabel", "PaymentMethod",
            ],
            feature_order=[
                "CoursePrice", "CourseDuration", "CourseRating", "TeacherRating",
                "YearsOfExperience", "EncodedCourseLevel", "TeacherRatingScore",
                "ExpertiseCategoryMatch", "TransactionMonth", "Quarter", "IsWeekend",
                "CourseCategory", "CourseType", "PriceBand", "DurationBucket",
                "RatingTier", "ExperienceBucket", "SeasonalityLabel", "PaymentMethod",
            ],
            training_data_fingerprint=None,
            training_data_shape=None,
            training_data_date_range=None,
            metrics={
                "note": "Legacy model trained before Phase 1; no baseline comparison available. "
                        "Model uses transaction-level features including PaymentMethod and time features "
                        "that are not available at course-design time. Not recommended for inference.",
            },
            library_versions={
                "scikit-learn": "1.8.0",  # Version at time of artifact creation (inferred from warnings)
                "xgboost": "unknown",
                "pandas": "unknown",
                "numpy": "unknown",
            },
            artifact_sha256=sha256,
            artifact_size_bytes=size,
            notes=(
                "Legacy enrollment model artifact from pre-Phase 1. "
                "Contains transaction-level features (PaymentMethod, TransactionMonth, Quarter, IsWeekend) "
                "that leak information not available at course-design time. "
                "Phase 1+ training produces enrollment_model_phase1.pkl with course-level features only. "
                "This legacy artifact is preserved for audit but should not be used for new predictions."
            ),
        )
        artifacts["enrollment_model"] = metadata

    # revenue_model.pkl (retired LinearRegression)
    revenue_path = models_dir / "revenue_model.pkl"
    if revenue_path.exists():
        sha256 = compute_file_sha256(revenue_path)
        size = revenue_path.stat().st_size
        metadata = ModelMetadata(
            model_name="revenue_model",
            model_type="LinearRegression (Pipeline with ColumnTransformer + OneHotEncoder + StandardScaler)",
            artifact_filename="revenue_model.pkl",
            status="retired",
            training_date_utc=None,
            target_variable="Amount (transaction amount)",
            feature_names=[
                "CoursePrice", "CourseDuration", "CourseRating", "TeacherRating",
                "YearsOfExperience", "EncodedCourseLevel", "TeacherRatingScore",
                "ExpertiseCategoryMatch", "TransactionMonth", "Quarter", "IsWeekend",
                "CourseCategory", "CourseType", "PriceBand", "DurationBucket",
                "RatingTier", "ExperienceBucket", "SeasonalityLabel", "PaymentMethod",
            ],
            feature_order=[
                "CoursePrice", "CourseDuration", "CourseRating", "TeacherRating",
                "YearsOfExperience", "EncodedCourseLevel", "TeacherRatingScore",
                "ExpertiseCategoryMatch", "TransactionMonth", "Quarter", "IsWeekend",
                "CourseCategory", "CourseType", "PriceBand", "DurationBucket",
                "RatingTier", "ExperienceBucket", "SeasonalityLabel", "PaymentMethod",
            ],
            training_data_fingerprint=None,
            training_data_shape=None,
            training_data_date_range=None,
            metrics={
                "r2": 1.0,
                "note": "R² = 1.0 because Amount == CoursePrice for paid transactions and 0 for free. "
                        "This is an accounting identity / target leakage, not predictive skill. "
                        "See revenue_target_audit.json for details.",
            },
            library_versions={
                "scikit-learn": "1.8.0",
                "pandas": "unknown",
                "numpy": "unknown",
            },
            artifact_sha256=sha256,
            artifact_size_bytes=size,
            notes=(
                "RETIRED: Revenue model is an accounting identity (Amount == CoursePrice). "
                "This model does not forecast revenue; it reconstructs the target from a feature. "
                "Phase 1 retired this model. Artifact preserved for audit only. "
                "Dashboard uses transparent price x reference-enrollment scenarios instead."
            ),
        )
        artifacts["revenue_model"] = metadata

    # preprocessing_pipeline.pkl (legacy ColumnTransformer)
    preprocessing_path = models_dir / "preprocessing_pipeline.pkl"
    if preprocessing_path.exists():
        sha256 = compute_file_sha256(preprocessing_path)
        size = preprocessing_path.stat().st_size
        metadata = ModelMetadata(
            model_name="preprocessing_pipeline",
            model_type="ColumnTransformer (StandardScaler + OneHotEncoder)",
            artifact_filename="preprocessing_pipeline.pkl",
            status="legacy",
            training_date_utc=None,
            target_variable=None,
            feature_names=[
                "CoursePrice", "CourseDuration", "CourseRating", "TeacherRating",
                "YearsOfExperience", "EncodedCourseLevel", "TeacherRatingScore",
                "ExpertiseCategoryMatch", "TransactionMonth", "Quarter", "IsWeekend",
                "CourseCategory", "CourseType", "PriceBand", "DurationBucket",
                "RatingTier", "ExperienceBucket", "SeasonalityLabel", "PaymentMethod",
            ],
            feature_order=[
                "CoursePrice", "CourseDuration", "CourseRating", "TeacherRating",
                "YearsOfExperience", "EncodedCourseLevel", "TeacherRatingScore",
                "ExpertiseCategoryMatch", "TransactionMonth", "Quarter", "IsWeekend",
                "CourseCategory", "CourseType", "PriceBand", "DurationBucket",
                "RatingTier", "ExperienceBucket", "SeasonalityLabel", "PaymentMethod",
            ],
            training_data_fingerprint=None,
            training_data_shape=None,
            training_data_date_range=None,
            metrics={},
            library_versions={
                "scikit-learn": "1.8.0",
            },
            artifact_sha256=sha256,
            artifact_size_bytes=size,
            notes=(
                "Legacy preprocessing pipeline fitted on full transaction dataset. "
                "Uses same feature set as legacy enrollment/revenue models. "
                "Phase 1+ uses shared feature engineering from edup.features instead. "
                "Preserved for audit; not used by current inference pipeline."
            ),
        )
        artifacts["preprocessing_pipeline"] = metadata

    # forecast_results.pkl (cached Prophet output)
    forecast_path = models_dir / "forecast_results.pkl"
    if forecast_path.exists():
        sha256 = compute_file_sha256(forecast_path)
        size = forecast_path.stat().st_size
        metadata = ModelMetadata(
            model_name="forecast_results",
            model_type="Prophet (multiplicative seasonality) forecast output dict",
            artifact_filename="forecast_results.pkl",
            status="cached",
            training_date_utc=None,
            target_variable="Monthly revenue + enrollment",
            feature_names=[],
            feature_order=[],
            training_data_fingerprint=None,
            training_data_shape=None,
            training_data_date_range={"start": "2025-01-01", "end": "2025-12-30"},
            metrics={
                "note": "Cached Prophet output. Not backtested. No validation metrics available. "
                        "Dashboard displays with explicit 'unbacktested' warning.",
            },
            library_versions={
                "prophet": "1.1.4+",  # Minimum from requirements
                "pandas": "unknown",
            },
            artifact_sha256=sha256,
            artifact_size_bytes=size,
            notes=(
                "Cached Prophet forecast results for 6-month revenue and enrollment projections. "
                "Generated from monthly aggregated transaction data (2025-01 to 2025-12). "
                "NOT BACKTESTED: No holdout evaluation, no baseline comparison, no uncertainty calibration. "
                "Dashboard displays with explicit caveat. Do not treat as validated forecast."
            ),
        )
        artifacts["forecast_results"] = metadata

    return artifacts


def write_all_metadata(models_dir: Path | str = MODELS_DIR) -> None:
    """Generate and write metadata JSON files for all existing artifacts."""
    models_dir = Path(models_dir)
    artifacts = generate_metadata_for_existing_artifacts(models_dir)

    for name, metadata in artifacts.items():
        metadata_path = models_dir / f"{name}_metadata.json"
        metadata.write(metadata_path)
        print(f"  Wrote {metadata_path.name}")

    # Also write a combined index
    index = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "models_dir": str(models_dir),
        "artifacts": {name: meta.to_dict() for name, meta in artifacts.items()},
    }
    index_path = models_dir / "model_metadata_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, default=str)
    print(f"  Wrote {index_path.name}")


if __name__ == "__main__":
    write_all_metadata()