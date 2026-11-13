# edup.models — Model training, evaluation, and prediction
from .models import (
    train_enrollment_model,
    audit_revenue_target,
    prepare_enrollment_target,
    get_all_models,
    evaluate_model,
    load_enrollment_model,
    predict_enrollment,
    ModelLoadError,
)
from .metadata import (
    ModelMetadata,
    ModelStatus,
    compute_file_sha256,
    get_library_versions,
    compute_data_fingerprint,
    load_model_with_metadata,
    validate_model_metadata,
    generate_metadata_for_existing_artifacts,
    write_all_metadata,
)

__all__ = [
    "train_enrollment_model",
    "audit_revenue_target",
    "prepare_enrollment_target",
    "get_all_models",
    "evaluate_model",
    "load_enrollment_model",
    "predict_enrollment",
    "ModelLoadError",
    "ModelMetadata",
    "ModelStatus",
    "compute_file_sha256",
    "get_library_versions",
    "compute_data_fingerprint",
    "load_model_with_metadata",
    "validate_model_metadata",
    "generate_metadata_for_existing_artifacts",
    "write_all_metadata",
]