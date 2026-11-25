"""
Tests for model registry, retraining, promotion, and rollback.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from edup.config import FEATURE_COLUMNS, MODELS_DIR
from edup.models.metadata import compute_file_sha256
from edup.models.registry import (
    ModelRegistry,
    PromotionCriteria,
    RegistryEntry,
    RegistryIndex,
    RetrainingConfig,
    reset_registry,
)


class TestRegistryEntry:
    """Tests for RegistryEntry dataclass."""

    def test_entry_creation(self):
        """Test creating a registry entry."""
        entry = RegistryEntry(
            version="v20260101_120000",
            model_name="test_model",
            model_type="XGBRegressor",
            artifact_filename="model.pkl",
            status="active",
            training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="EnrollmentCount",
            feature_names=["a", "b"],
            feature_order=["a", "b"],
            training_data_fingerprint="abc123",
            training_data_shape=(100, 10),
            training_data_date_range={"start": "2025-01-01", "end": "2025-12-31"},
            metrics={"RMSE": 10.5},
            artifact_sha256="deadbeef",
            artifact_size_bytes=1024,
        )
        assert entry.version == "v20260101_120000"
        assert entry.model_name == "test_model"
        assert entry.status == "active"

    def test_entry_serialization(self):
        """Test entry to_dict and from_dict roundtrip."""
        entry = RegistryEntry(
            version="v1",
            model_name="test",
            model_type="Test",
            artifact_filename="test.pkl",
            status="cached",
            training_date_utc="2026-01-01T00:00:00+00:00",
            target_variable="target",
            feature_names=["a"],
            feature_order=["a"],
            training_data_fingerprint=None,
            training_data_shape=(100, 10),
            training_data_date_range=None,
            metrics={},
            artifact_sha256="abc",
            artifact_size_bytes=100,
        )
        data = entry.to_dict()
        assert data["training_data_shape"] == [100, 10]

        restored = RegistryEntry.from_dict(data)
        assert restored.version == entry.version
        assert restored.model_name == entry.model_name
        assert restored.training_data_shape == (100, 10)


class TestRegistryIndex:
    """Tests for RegistryIndex dataclass."""

    def test_index_creation(self):
        """Test creating an empty index."""
        index = RegistryIndex(
            created_utc="2026-01-01T00:00:00+00:00",
            updated_utc="2026-01-01T00:00:00+00:00",
        )
        assert index.active_version is None
        assert index.entries == {}

    def test_index_serialization(self):
        """Test index to_dict and from_dict roundtrip."""
        entry = RegistryEntry(
            version="v1",
            model_name="test",
            model_type="Test",
            artifact_filename="test.pkl",
            status="active",
            training_date_utc="2026-01-01T00:00:00+00:00",
            target_variable="target",
            feature_names=["a"],
            feature_order=["a"],
            training_data_fingerprint=None,
            training_data_shape=None,
            training_data_date_range=None,
            metrics={},
            artifact_sha256="abc",
            artifact_size_bytes=100,
        )
        index = RegistryIndex(
            created_utc="2026-01-01T00:00:00+00:00",
            updated_utc="2026-01-01T00:00:00+00:00",
            active_version="v1",
            entries={"v1": entry},
        )
        data = index.to_dict()
        assert data["active_version"] == "v1"
        assert "v1" in data["entries"]

        restored = RegistryIndex.from_dict(data)
        assert restored.active_version == "v1"
        assert restored.entries["v1"].model_name == "test"


class TestPromotionCriteria:
    """Tests for PromotionCriteria."""

    def test_default_criteria(self):
        """Test default promotion criteria."""
        criteria = PromotionCriteria()
        assert criteria.min_r2 == -1.0
        assert criteria.max_rmse == float("inf")
        assert criteria.max_mae == float("inf")
        assert criteria.must_beat_baseline is True

    def test_custom_criteria(self):
        """Test custom promotion criteria."""
        criteria = PromotionCriteria(min_r2=0.5, max_rmse=10.0, must_beat_baseline=False)
        assert criteria.min_r2 == 0.5
        assert criteria.max_rmse == 10.0
        assert criteria.must_beat_baseline is False

    def test_serialization(self):
        """Test criteria serialization."""
        criteria = PromotionCriteria(min_r2=0.5)
        data = criteria.to_dict()
        restored = PromotionCriteria.from_dict(data)
        assert restored.min_r2 == 0.5


class TestRetrainingConfig:
    """Tests for RetrainingConfig."""

    def test_default_config(self):
        """Test default retraining config."""
        config = RetrainingConfig()
        assert config.enabled is False
        assert config.schedule_cron == "0 2 * * 0"
        assert config.max_concurrent_jobs == 1

    def test_serialization(self):
        """Test config serialization."""
        config = RetrainingConfig(enabled=True, schedule_cron="0 3 * * *")
        data = config.to_dict()
        assert data["enabled"] is True
        assert data["schedule_cron"] == "0 3 * * *"

        restored = RetrainingConfig.from_dict(data)
        assert restored.enabled is True
        assert restored.schedule_cron == "0 3 * * *"


class TestModelRegistry:
    """Tests for ModelRegistry core functionality."""

    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary registry for testing."""
        registry_dir = tmp_path / "registry"
        registry = ModelRegistry(registry_dir)
        yield registry
        reset_registry()

    @pytest.fixture
    def dummy_model_artifact(self, tmp_path):
        """Create a dummy model artifact for testing."""
        import joblib
        from sklearn.linear_model import LinearRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        # Create a simple pipeline
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("model", LinearRegression()),
        ])

        # Fit on dummy data
        X = np.random.rand(10, 5)
        y = np.random.rand(10)
        pipe.fit(X, y)

        artifact_path = tmp_path / "test_model.pkl"
        joblib.dump(pipe, artifact_path)
        return artifact_path

    @pytest.fixture
    def dummy_training_data(self):
        """Create dummy training data."""
        return pd.DataFrame({
            "TransactionDate": pd.date_range("2025-01-01", periods=100),
            "CourseID": [f"C{i}" for i in range(100)],
            "CoursePrice": np.random.uniform(50, 200, 100),
            "CourseDuration": np.random.uniform(10, 50, 100),
            "CourseRating": np.random.uniform(3, 5, 100),
            "TeacherRating": np.random.uniform(3, 5, 100),
            "YearsOfExperience": np.random.randint(0, 20, 100),
            "EncodedCourseLevel": np.random.randint(1, 4, 100),
            "CourseCategory": np.random.choice(["Programming", "Design", "Business"], 100),
            "CourseType": np.random.choice(["Paid", "Free"], 100),
        })

    def test_register_model(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test registering a model version."""
        version = temp_registry.register_model(
            model_name="test_model",
            model_type="LinearRegression",
            artifact_path=dummy_model_artifact,
            status="cached",
            training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="EnrollmentCount",
            feature_names=FEATURE_COLUMNS,
            metrics={"RMSE": 10.5, "R2": 0.8},
            training_data=dummy_training_data,
            notes="Test model",
        )

        assert version is not None
        assert version.startswith("v")

        # Verify entry exists
        entry = temp_registry.get_version(version)
        assert entry is not None
        assert entry.model_name == "test_model"
        assert entry.status == "cached"
        assert entry.artifact_sha256 == compute_file_sha256(dummy_model_artifact)

        # Verify artifact was copied
        artifact_dest = temp_registry.registry_dir / "versions" / version / dummy_model_artifact.name
        assert artifact_dest.exists()

        # Verify metadata was written
        metadata_dest = temp_registry.registry_dir / "versions" / version / f"{dummy_model_artifact.stem}_metadata.json"
        assert metadata_dest.exists()

    def test_register_duplicate_version_fails(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test that registering duplicate version fails."""
        version = "v20260101_120000_000000"
        temp_registry.register_model(
            model_name="test_model",
            model_type="LinearRegression",
            artifact_path=dummy_model_artifact,
            status="cached",
            training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="EnrollmentCount",
            feature_names=FEATURE_COLUMNS,
            metrics={},
            training_data=dummy_training_data,
            version=version,
        )

        with pytest.raises(Exception, match="already exists"):
            temp_registry.register_model(
                model_name="test_model2",
                model_type="LinearRegression",
                artifact_path=dummy_model_artifact,
                status="cached",
                training_date_utc="2026-01-01T12:00:00+00:00",
                target_variable="EnrollmentCount",
                feature_names=FEATURE_COLUMNS,
                metrics={},
                training_data=dummy_training_data,
                version=version,
            )

    def test_register_missing_artifact_fails(self, temp_registry):
        """Test that registering with missing artifact fails."""
        with pytest.raises(Exception, match="Artifact not found"):
            temp_registry.register_model(
                model_name="test_model",
                model_type="LinearRegression",
                artifact_path=Path("/nonexistent/model.pkl"),
                status="cached",
                training_date_utc="2026-01-01T12:00:00+00:00",
                target_variable="EnrollmentCount",
                feature_names=FEATURE_COLUMNS,
                metrics={},
            )

    def test_list_versions(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test listing model versions."""
        v1 = temp_registry.register_model(
            model_name="model1", model_type="LR", artifact_path=dummy_model_artifact,
            status="cached", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS, metrics={},
            training_data=dummy_training_data, version="v20260101_120000_000000",
        )
        v2 = temp_registry.register_model(
            model_name="model2", model_type="RF", artifact_path=dummy_model_artifact,
            status="cached", training_date_utc="2026-01-02T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS, metrics={},
            training_data=dummy_training_data, version="v20260102_120000_000000",
        )

        versions = temp_registry.list_versions()
        assert len(versions) == 2
        # Newest first
        assert versions[0].version == v2
        assert versions[1].version == v1

    def test_get_version(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test retrieving a specific version."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="cached", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS, metrics={},
            training_data=dummy_training_data, version="v20260101_120000_000001",
        )

        entry = temp_registry.get_version(version)
        assert entry is not None
        assert entry.version == version

        # Non-existent version
        assert temp_registry.get_version("nonexistent") is None

    def test_get_active_version_none_initially(self, temp_registry):
        """Test that active version is None initially."""
        assert temp_registry.get_active_version() is None

    def test_promote_and_get_active(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test promoting a model and retrieving active."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260101_120000_000002",
        )

        # Approve then promote
        temp_registry.approve_candidate(version)
        temp_registry.promote(version)

        active = temp_registry.get_active_version()
        assert active is not None
        assert active.version == version
        assert active.status == "active"
        assert active.promoted_at_utc is not None
        assert active.promoted_by == "manual"

        # Check active model file
        active_path = temp_registry.get_active_model_path()
        assert active_path is not None
        assert active_path.exists()

    def test_promote_nonexistent_fails(self, temp_registry):
        """Test promoting non-existent version fails."""
        with pytest.raises(Exception, match="not found"):
            temp_registry.promote("nonexistent")

    def test_promote_invalid_candidate_fails(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test promoting invalid candidate fails validation."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 15.0, "MAE": 12.0, "R2": 0.1}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260101_120000_000003",
        )

        # Should fail because candidate RMSE > baseline RMSE (approval fails)
        with pytest.raises(Exception, match="does not beat baseline"):
            temp_registry.approve_candidate(version)

    def test_rollback_to_previous(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test rolling back to previous version."""
        v1 = temp_registry.register_model(
            model_name="model1", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260101_120000_000004",
        )
        v2 = temp_registry.register_model(
            model_name="model2", model_type="RF", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-02T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 4.0, "MAE": 3.0, "R2": 0.9}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260102_120000_000004",
        )

        # Approve and promote v1
        temp_registry.approve_candidate(v1)
        temp_registry.promote(v1)
        assert temp_registry.get_active_version().version == v1

        # Approve and promote v2
        temp_registry.approve_candidate(v2)
        temp_registry.promote(v2)
        assert temp_registry.get_active_version().version == v2
        assert temp_registry.get_version(v1).status == "legacy"

        # Rollback (should go to v1)
        temp_registry.rollback()
        assert temp_registry.get_active_version().version == v1
        assert temp_registry.get_version(v1).status == "active"
        assert temp_registry.get_version(v2).status == "legacy"

    def test_rollback_to_specific_version(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test rolling back to a specific version."""
        v1 = temp_registry.register_model(
            model_name="model1", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260101_120000_000005",
        )
        v2 = temp_registry.register_model(
            model_name="model2", model_type="RF", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-02T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 4.0, "MAE": 3.0, "R2": 0.9}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260102_120000_000005",
        )
        v3 = temp_registry.register_model(
            model_name="model3", model_type="XGB", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-03T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 3.0, "MAE": 2.0, "R2": 0.95}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260103_120000_000005",
        )

        temp_registry.approve_candidate(v1)
        temp_registry.promote(v1)
        temp_registry.approve_candidate(v2)
        temp_registry.promote(v2)
        temp_registry.approve_candidate(v3)
        temp_registry.promote(v3)

        # Rollback to v1 specifically
        temp_registry.rollback(v1)
        assert temp_registry.get_active_version().version == v1

    def test_rollback_nonexistent_fails(self, temp_registry):
        """Test rollback to non-existent version fails."""
        with pytest.raises(Exception, match="not found"):
            temp_registry.rollback("nonexistent")

    def test_rollback_no_previous_fails(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test rollback when no previous version exists."""
        version = temp_registry.register_model(
            model_name="model1", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260101_120000_000006",
        )
        temp_registry.approve_candidate(version)
        temp_registry.promote(version)

        # No previous version to rollback to
        with pytest.raises(Exception, match="No previous version"):
            temp_registry.rollback()

    def test_validate_candidate_success(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test validating a valid candidate."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260101_120000_000007",
        )

        valid, issues = temp_registry.validate_candidate(version)
        # Model output validation will produce a warning for dummy models, so check that
        # the core validation passes (metrics, artifact, checksum, features)
        assert any("Model output validation warning" in issue for issue in issues) or issues == []
        # The core validation should pass (no errors about metrics, artifact, checksum, features)
        core_issues = [i for i in issues if "Model output validation warning" not in i]
        assert core_issues == []

    def test_validate_candidate_missing_artifact(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test validation fails when artifact is missing."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}},
            training_data=dummy_training_data,
        )

        # Delete the artifact
        artifact_path = temp_registry.registry_dir / "versions" / version / dummy_model_artifact.name
        artifact_path.unlink()

        valid, issues = temp_registry.validate_candidate(version)
        assert valid is False
        assert any("Artifact not found" in issue for issue in issues)

    def test_validate_candidate_checksum_mismatch(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test validation fails on checksum mismatch."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}},
            training_data=dummy_training_data,
        )

        # Corrupt the artifact
        artifact_path = temp_registry.registry_dir / "versions" / version / dummy_model_artifact.name
        artifact_path.write_bytes(b"corrupted")

        valid, issues = temp_registry.validate_candidate(version)
        assert valid is False
        assert any("checksum mismatch" in issue for issue in issues)

    def test_validate_candidate_feature_mismatch(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test validation fails on feature contract mismatch."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=["wrong", "features"],
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}},
            training_data=dummy_training_data,
        )

        valid, issues = temp_registry.validate_candidate(version)
        assert valid is False
        assert any("Feature contract mismatch" in issue for issue in issues)

    def test_validate_candidate_missing_metrics(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test validation fails when metrics are missing."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={},  # Empty metrics
            training_data=dummy_training_data,
        )

        valid, issues = temp_registry.validate_candidate(version)
        assert valid is False
        assert any("No evaluation metrics" in issue for issue in issues)

    def test_validate_candidate_incomplete_metrics(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test validation fails when metrics are incomplete."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0}},  # Missing MAE, R2
            training_data=dummy_training_data,
        )

        valid, issues = temp_registry.validate_candidate(version)
        assert valid is False
        assert any("Missing MAE" in issue for issue in issues)
        assert any("Missing R2" in issue for issue in issues)

    def test_validate_candidate_below_min_r2(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test validation fails when R2 below minimum."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.3}},
            training_data=dummy_training_data, version="v20260101_120000_000008",
        )

        criteria = PromotionCriteria(min_r2=0.5)
        valid, issues = temp_registry.validate_candidate(version, criteria)
        assert valid is False
        # Filter out model output validation warnings
        core_issues = [i for i in issues if "Model output validation warning" not in i]
        assert any("below minimum" in issue for issue in core_issues)

    def test_validate_candidate_above_max_rmse(self, temp_registry, dummy_model_artifact, dummy_training_data):
        """Test validation fails when RMSE above maximum."""
        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 20.0, "MAE": 4.0, "R2": 0.8}},
            training_data=dummy_training_data, version="v20260101_120000_000009",
        )

        criteria = PromotionCriteria(max_rmse=10.0)
        valid, issues = temp_registry.validate_candidate(version, criteria)
        assert valid is False
        # Filter out model output validation warnings
        core_issues = [i for i in issues if "Model output validation warning" not in i]
        assert any("above maximum" in issue for issue in core_issues)

    def test_config_persistence(self, temp_registry):
        """Test retraining config persistence."""
        config = RetrainingConfig(enabled=True, schedule_cron="0 3 * * *")
        temp_registry.save_retraining_config(config)

        loaded = temp_registry.get_retraining_config()
        assert loaded.enabled is True
        assert loaded.schedule_cron == "0 3 * * *"

    def test_log_retraining_job(self, temp_registry):
        """Test logging retraining jobs."""
        temp_registry.log_retraining_job("job1", "success", {"version": "v1"})
        temp_registry.log_retraining_job("job2", "failed", {"error": "test"})

        logs = temp_registry.get_retraining_logs(limit=10)
        assert len(logs) == 2
        assert logs[0]["job_id"] == "job2"  # Newest first
        assert logs[1]["job_id"] == "job1"

    def test_persist_index_across_instances(self, tmp_path, dummy_model_artifact, dummy_training_data):
        """Test that index persists across registry instances."""
        registry_dir = tmp_path / "registry"
        registry1 = ModelRegistry(registry_dir)

        version = registry1.register_model(
            model_name="test_model", model_type="LR", artifact_path=dummy_model_artifact,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
            training_data=dummy_training_data, version="v20260101_120000_000010",
        )
        registry1.approve_candidate(version)
        registry1.promote(version)

        # Create new instance
        registry2 = ModelRegistry(registry_dir)
        active = registry2.get_active_version()
        assert active is not None
        assert active.version == version

        versions = registry2.list_versions()
        assert len(versions) == 1


class TestRetrainingPipeline:
    """Tests for the retraining pipeline."""

    @pytest.fixture
    def temp_registry(self, tmp_path):
        registry_dir = tmp_path / "registry"
        registry = ModelRegistry(registry_dir)
        yield registry
        reset_registry()

    @pytest.fixture
    def dummy_training_data(self):
        """Create dummy training data that matches the expected schema."""
        np.random.seed(42)
        n = 1000
        return pd.DataFrame({
            "TransactionID": [f"T{i}" for i in range(n)],
            "TransactionDate": pd.date_range("2025-01-01", periods=n),
            "CourseID": [f"C{i % 60}" for i in range(n)],
            "CoursePrice": np.random.uniform(50, 200, n),
            "CourseDuration": np.random.uniform(10, 50, n),
            "CourseRating": np.random.uniform(3, 5, n),
            "TeacherRating": np.random.uniform(3, 5, n),
            "YearsOfExperience": np.random.randint(0, 20, n),
            "EncodedCourseLevel": np.random.randint(1, 4, n),
            "CourseCategory": np.random.choice(["Programming", "Design", "Business"], n),
            "CourseType": np.random.choice(["Paid", "Free"], n),
            "Amount": np.random.uniform(0, 200, n),
            "PaymentMethod": np.random.choice(["Credit Card", "PayPal", "Bank Transfer"], n),
        })

    @patch("edup.models.models.train_enrollment_model")
    def test_run_retraining_success(self, mock_train, temp_registry, dummy_training_data):
        """Test successful retraining pipeline."""
        # Mock train_enrollment_model to return a model that beats baseline
        # and also create the model artifact file
        def mock_train_func(df, models_dir):
            import joblib
            import numpy as np
            from sklearn.linear_model import LinearRegression
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler

            pipe = Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())])
            X = np.random.rand(10, len(FEATURE_COLUMNS))
            y = np.random.rand(10)
            pipe.fit(X, y)

            model_path = Path(models_dir) / "enrollment_model_phase1.pkl"
            joblib.dump(pipe, model_path)

            return {
                "use_model": True,
                "selected_model": "RandomForest",
                "candidate_cv_rmse": {"RandomForest": 5.0},
                "selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8},
                "baseline": {"test": {"RMSE": 10.0}},
                "n_courses": 60,
                "features": FEATURE_COLUMNS,
            }

        mock_train.side_effect = mock_train_func

        with patch("edup.data.load_processed_data", return_value=dummy_training_data):
            result = temp_registry.run_retraining(auto_promote=False)

        assert result["status"] in ("candidate_ready", "promoted")
        assert result["candidate_version"] is not None
        assert result["candidate_version"].startswith("v")

    @patch("edup.models.models.train_enrollment_model")
    def test_run_retraining_no_model(self, mock_train, temp_registry, dummy_training_data):
        """Test retraining when no model beats baseline."""
        # Mock train_enrollment_model to return no model and not create artifact
        def mock_train_func(df, models_dir):
            return {
                "use_model": False,
                "selected_model": "RandomForest",
                "candidate_cv_rmse": {"RandomForest": 15.0},
                "selected_test": {"RMSE": 15.0, "MAE": 12.0, "R2": 0.1},
                "baseline": {"test": {"RMSE": 10.0}},
                "n_courses": 60,
            }

        mock_train.side_effect = mock_train_func

        with patch("edup.data.load_processed_data", return_value=dummy_training_data):
            result = temp_registry.run_retraining(auto_promote=False)

        assert result["status"] == "failed"
        assert "did not produce a model" in result.get("error", "")


class TestRegistryIntegration:
    """Integration tests for registry with actual model artifacts."""

    def test_registry_with_existing_artifacts(self):
        """Test registry operations with existing model artifacts."""
        # Use the actual models directory
        registry = ModelRegistry(MODELS_DIR / "registry")
        reset_registry()

        # Register the existing enrollment_model.pkl as a candidate
        enrollment_path = MODELS_DIR / "enrollment_model.pkl"
        if enrollment_path.exists():
            version = registry.register_model(
                model_name="enrollment_model_legacy",
                model_type="XGBRegressor (legacy)",
                artifact_path=enrollment_path,
                status="cached",
                training_date_utc="2025-09-01T00:00:00+00:00",
                target_variable="EnrollmentCount (course-level)",
                feature_names=[
                    "CoursePrice", "CourseDuration", "CourseRating", "TeacherRating",
                    "YearsOfExperience", "EncodedCourseLevel", "TeacherRatingScore",
                    "ExpertiseCategoryMatch", "TransactionMonth", "Quarter", "IsWeekend",
                    "CourseCategory", "CourseType", "PriceBand", "DurationBucket",
                    "RatingTier", "ExperienceBucket", "SeasonalityLabel", "PaymentMethod",
                ],
                metrics={
                    "selected_test": {"RMSE": 8.5, "MAE": 6.2, "R2": 0.45},
                    "baseline": {"test": {"RMSE": 10.0}},
                },
                notes="Legacy enrollment model from pre-Phase 1",
            )

            assert version is not None
            entry = registry.get_version(version)
            assert entry is not None
            assert entry.model_name == "enrollment_model_legacy"

        reset_registry()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
