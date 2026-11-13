"""
Tests for model metadata schema validation and artifact compatibility.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from edup.models.metadata import (
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
from edup.config import FEATURE_COLUMNS, NUMERIC_FEATURES, CATEGORICAL_FEATURES


class TestModelMetadata:
    """Tests for ModelMetadata dataclass."""

    def test_metadata_creation_minimal(self):
        """Test creating metadata with minimal required fields."""
        metadata = ModelMetadata(
            model_name="test_model",
            model_type="TestRegressor",
            artifact_filename="test.pkl",
            status="active",
        )
        assert metadata.model_name == "test_model"
        assert metadata.model_type == "TestRegressor"
        assert metadata.artifact_filename == "test.pkl"
        assert metadata.status == "active"
        assert metadata.feature_names == []
        assert metadata.metrics == {}

    def test_metadata_creation_full(self):
        """Test creating metadata with all fields."""
        metadata = ModelMetadata(
            model_name="full_model",
            model_type="XGBRegressor",
            artifact_filename="full.pkl",
            status="legacy",
            training_date_utc="2026-01-01T00:00:00+00:00",
            target_variable="EnrollmentCount",
            feature_names=["CoursePrice", "CourseDuration"],
            feature_order=["CoursePrice", "CourseDuration"],
            training_data_fingerprint="abc123",
            training_data_shape=(100, 10),
            training_data_date_range={"start": "2025-01-01", "end": "2025-12-31"},
            metrics={"RMSE": 10.5, "R2": 0.8},
            python_version="3.11.0",
            platform="Linux-test",
            library_versions={"scikit-learn": "1.9.1", "xgboost": "3.4.1"},
            artifact_sha256="deadbeef",
            artifact_size_bytes=1024,
            notes="Test model",
        )
        assert metadata.model_name == "full_model"
        assert metadata.training_data_shape == (100, 10)
        assert metadata.metrics["RMSE"] == 10.5

    def test_metadata_to_dict_and_back(self):
        """Test round-trip serialization."""
        metadata = ModelMetadata(
            model_name="roundtrip",
            model_type="TestModel",
            artifact_filename="rt.pkl",
            status="cached",
            training_data_shape=(50, 5),
        )
        data = metadata.to_dict()
        assert data["training_data_shape"] == [50, 5]

        restored = ModelMetadata.from_dict(data)
        assert restored.training_data_shape == (50, 5)
        assert restored.model_name == "roundtrip"

    def test_metadata_write_read(self, tmp_path):
        """Test writing and reading metadata to/from JSON."""
        metadata = ModelMetadata(
            model_name="write_test",
            model_type="TestModel",
            artifact_filename="write.pkl",
            status="active",
        )
        path = tmp_path / "test_metadata.json"
        metadata.write(path)

        assert path.exists()
        restored = ModelMetadata.read(path)
        assert restored.model_name == "write_test"
        assert restored.status == "active"


class TestMetadataValidation:
    """Tests for validate_model_metadata function."""

    def test_valid_metadata_passes(self):
        """Test that valid metadata produces no issues."""
        metadata = ModelMetadata(
            model_name="valid",
            model_type="TestModel",
            artifact_filename="valid.pkl",
            status="active",
            feature_names=["a", "b"],
            feature_order=["a", "b"],
            artifact_sha256="abc123",
        )
        issues = validate_model_metadata(metadata)
        assert issues == []

    def test_missing_model_name_fails(self):
        """Test that missing model_name is caught."""
        metadata = ModelMetadata(
            model_name="",
            model_type="TestModel",
            artifact_filename="valid.pkl",
            status="active",
        )
        issues = validate_model_metadata(metadata)
        assert any("model_name is required" in issue for issue in issues)

    def test_missing_model_type_fails(self):
        """Test that missing model_type is caught."""
        metadata = ModelMetadata(
            model_name="test",
            model_type="",
            artifact_filename="valid.pkl",
            status="active",
        )
        issues = validate_model_metadata(metadata)
        assert any("model_type is required" in issue for issue in issues)

    def test_missing_artifact_filename_fails(self):
        """Test that missing artifact_filename is caught."""
        metadata = ModelMetadata(
            model_name="test",
            model_type="TestModel",
            artifact_filename="",
            status="active",
        )
        issues = validate_model_metadata(metadata)
        assert any("artifact_filename is required" in issue for issue in issues)

    def test_invalid_status_fails(self):
        """Test that invalid status is caught."""
        metadata = ModelMetadata(
            model_name="test",
            model_type="TestModel",
            artifact_filename="valid.pkl",
            status="invalid_status",
        )
        issues = validate_model_metadata(metadata)
        assert any("invalid status" in issue for issue in issues)

    def test_feature_names_order_mismatch_fails(self):
        """Test that mismatched feature_names and feature_order is caught."""
        metadata = ModelMetadata(
            model_name="test",
            model_type="TestModel",
            artifact_filename="valid.pkl",
            status="active",
            feature_names=["a", "b"],
            feature_order=["a", "c"],
        )
        issues = validate_model_metadata(metadata)
        assert any("feature_names and feature_order must contain the same features" in issue for issue in issues)

    def test_missing_sha256_warned(self):
        """Test that missing artifact_sha256 is flagged."""
        metadata = ModelMetadata(
            model_name="test",
            model_type="TestModel",
            artifact_filename="valid.pkl",
            status="active",
        )
        issues = validate_model_metadata(metadata)
        assert any("artifact_sha256 is missing" in issue for issue in issues)


class TestMetadataUtilities:
    """Tests for metadata utility functions."""

    def test_compute_file_sha256(self, tmp_path):
        """Test SHA256 computation."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"hello world")
        sha = compute_file_sha256(test_file)
        assert len(sha) == 64
        assert sha == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_get_library_versions(self):
        """Test library version retrieval."""
        versions = get_library_versions()
        assert isinstance(versions, dict)
        assert "pandas" in versions
        assert "numpy" in versions
        assert "scikit-learn" in versions

    def test_compute_data_fingerprint(self):
        """Test DataFrame fingerprint computation."""
        import pandas as pd
        df = pd.DataFrame({
            "a": [1, 2, 3],
            "b": [4.0, 5.0, 6.0],
            "c": ["x", "y", "z"],
        })
        fp = compute_data_fingerprint(df)
        assert len(fp) == 16
        assert fp == compute_data_fingerprint(df)  # Deterministic

        # Different data -> different fingerprint
        df2 = df.copy()
        df2.loc[0, "a"] = 99
        fp2 = compute_data_fingerprint(df2)
        assert fp != fp2

    def test_compute_data_fingerprint_with_columns(self):
        """Test fingerprint with specific columns."""
        import pandas as pd
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
        fp1 = compute_data_fingerprint(df, columns=["a", "b"])
        fp2 = compute_data_fingerprint(df, columns=["a", "c"])
        assert fp1 != fp2


class TestExistingArtifactsMetadata:
    """Tests for generating metadata for existing artifacts."""

    def test_generate_metadata_for_existing_artifacts(self):
        """Test that metadata can be generated for all existing artifacts."""
        # Use the actual models directory
        models_dir = Path("models")
        artifacts = generate_metadata_for_existing_artifacts(models_dir)

        # Should have metadata for all 4 artifacts
        assert "enrollment_model" in artifacts
        assert "revenue_model" in artifacts
        assert "preprocessing_pipeline" in artifacts
        assert "forecast_results" in artifacts

        # Check enrollment model metadata
        enr_meta = artifacts["enrollment_model"]
        assert enr_meta.model_name == "enrollment_model"
        assert enr_meta.status == "legacy"
        assert enr_meta.artifact_sha256 is not None
        assert len(enr_meta.artifact_sha256) == 64

        # Check revenue model metadata
        rev_meta = artifacts["revenue_model"]
        assert rev_meta.model_name == "revenue_model"
        assert rev_meta.status == "retired"
        assert rev_meta.metrics.get("r2") == 1.0

        # Check preprocessing pipeline metadata
        prep_meta = artifacts["preprocessing_pipeline"]
        assert prep_meta.model_name == "preprocessing_pipeline"
        assert prep_meta.status == "legacy"

        # Check forecast results metadata
        fcst_meta = artifacts["forecast_results"]
        assert fcst_meta.model_name == "forecast_results"
        assert fcst_meta.status == "cached"
        assert fcst_meta.training_data_date_range is not None

    def test_write_all_metadata(self, tmp_path):
        """Test writing all metadata files."""
        # Create dummy artifact files
        (tmp_path / "enrollment_model.pkl").write_bytes(b"dummy")
        (tmp_path / "revenue_model.pkl").write_bytes(b"dummy")
        (tmp_path / "preprocessing_pipeline.pkl").write_bytes(b"dummy")
        (tmp_path / "forecast_results.pkl").write_bytes(b"dummy")

        write_all_metadata(tmp_path)

        # Check all metadata files created
        assert (tmp_path / "enrollment_model_metadata.json").exists()
        assert (tmp_path / "revenue_model_metadata.json").exists()
        assert (tmp_path / "preprocessing_pipeline_metadata.json").exists()
        assert (tmp_path / "forecast_results_metadata.json").exists()
        assert (tmp_path / "model_metadata_index.json").exists()

        # Verify index file
        with open(tmp_path / "model_metadata_index.json") as f:
            index = json.load(f)
        assert "artifacts" in index
        assert len(index["artifacts"]) == 4


class TestModelArtifactCompatibility:
    """Tests for model/artifact compatibility checks."""

    def test_load_model_with_metadata(self):
        """Test loading a model with its metadata."""
        models_dir = Path("models")
        model, metadata = load_model_with_metadata(
            models_dir / "enrollment_model.pkl",
            models_dir / "enrollment_model_metadata.json",
        )
        assert model is not None
        assert metadata is not None
        assert metadata.model_name == "enrollment_model"
        assert metadata.status == "legacy"

    def test_load_model_without_metadata(self):
        """Test loading a model when metadata file doesn't exist."""
        models_dir = Path("models")
        model, metadata = load_model_with_metadata(
            models_dir / "enrollment_model.pkl",
            models_dir / "nonexistent_metadata.json",
        )
        assert model is not None
        assert metadata is None

    def test_artifact_sha256_matches_metadata(self):
        """Test that artifact SHA256 matches metadata."""
        models_dir = Path("models")
        for artifact_name in ["enrollment_model", "revenue_model", "preprocessing_pipeline", "forecast_results"]:
            artifact_path = models_dir / f"{artifact_name}.pkl"
            metadata_path = models_dir / f"{artifact_name}_metadata.json"

            if artifact_path.exists() and metadata_path.exists():
                actual_sha = compute_file_sha256(artifact_path)
                with open(metadata_path) as f:
                    metadata = json.load(f)
                assert actual_sha == metadata["artifact_sha256"], (
                    f"SHA256 mismatch for {artifact_name}"
                )

    def test_legacy_enrollment_features_match_artifact(self):
        """Test that legacy enrollment model metadata features match the artifact."""
        models_dir = Path("models")
        model, metadata = load_model_with_metadata(
            models_dir / "enrollment_model.pkl",
            models_dir / "enrollment_model_metadata.json",
        )

        # Get feature names from the preprocessor in the pipeline
        preprocessor = model.named_steps["preprocessor"]
        num_features = list(preprocessor.transformers_[0][2])
        cat_features = list(preprocessor.transformers_[1][2])
        artifact_features = num_features + cat_features

        # Metadata should list the same features (order may differ)
        assert set(metadata.feature_names) == set(artifact_features)

    def test_legacy_revenue_features_match_artifact(self):
        """Test that legacy revenue model metadata features match the artifact."""
        models_dir = Path("models")
        model, metadata = load_model_with_metadata(
            models_dir / "revenue_model.pkl",
            models_dir / "revenue_model_metadata.json",
        )

        preprocessor = model.named_steps["preprocessor"]
        num_features = list(preprocessor.transformers_[0][2])
        cat_features = list(preprocessor.transformers_[1][2])
        artifact_features = num_features + cat_features

        assert set(metadata.feature_names) == set(artifact_features)

    def test_phase1_features_match_config(self):
        """Test that Phase 1 feature columns match config."""
        # FEATURE_COLUMNS should match NUMERIC_FEATURES + CATEGORICAL_FEATURES
        assert set(FEATURE_COLUMNS) == set(NUMERIC_FEATURES + CATEGORICAL_FEATURES)

    def test_preprocessing_pipeline_features_match_legacy_models(self):
        """Test that preprocessing pipeline has same features as legacy models."""
        models_dir = Path("models")
        pipe = __import__("joblib").load(models_dir / "preprocessing_pipeline.pkl")

        num_features = list(pipe.transformers_[0][2])
        cat_features = list(pipe.transformers_[1][2])
        prep_features = num_features + cat_features

        _, enr_meta = load_model_with_metadata(
            models_dir / "enrollment_model.pkl",
            models_dir / "enrollment_model_metadata.json",
        )
        assert set(prep_features) == set(enr_meta.feature_names)


class TestMetadataIndex:
    """Tests for the model metadata index."""

    def test_index_exists_and_valid(self):
        """Test that the index file exists and is valid JSON."""
        index_path = Path("models") / "model_metadata_index.json"
        assert index_path.exists()

        with open(index_path) as f:
            index = json.load(f)

        assert "generated_utc" in index
        assert "artifacts" in index
        assert len(index["artifacts"]) == 4

        # Each artifact should have required fields
        for name, artifact in index["artifacts"].items():
            assert artifact["model_name"] == name
            assert artifact["status"] in ("active", "legacy", "retired", "cached")
            assert "artifact_sha256" in artifact
            assert artifact["artifact_sha256"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])