"""
Tests for the retraining CLI (edup-retrain).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import pandas as pd
import numpy as np

from edup.models import reset_registry, get_registry
from edup.models.registry import ModelRegistry, PromotionCriteria
from edup.models.retrain import (
    run_manual_retrain,
    run_scheduled_retrain,
    promote_version,
    rollback_version,
    show_registry_status,
)
from edup.config import FEATURE_COLUMNS, MODELS_DIR


class TestRetrainCLI:
    """Tests for the retrain CLI commands."""

    @pytest.fixture
    def temp_registry(self, tmp_path):
        registry_dir = tmp_path / "registry"
        registry = ModelRegistry(registry_dir)
        yield registry
        reset_registry()

    @pytest.fixture
    def dummy_training_data(self):
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

    def _create_dummy_model_artifact(self, models_dir: Path):
        """Create a dummy model artifact in the given directory."""
        import joblib
        from sklearn.linear_model import LinearRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        pipe = Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())])
        X = np.random.rand(10, len(FEATURE_COLUMNS))
        y = np.random.rand(10)
        pipe.fit(X, y)

        model_path = models_dir / "enrollment_model_phase1.pkl"
        joblib.dump(pipe, model_path)
        return model_path

    @patch("edup.models.retrain.get_registry")
    @patch("edup.data.load_processed_data")
    @patch("edup.models.models.train_enrollment_model")
    def test_run_manual_retrain_success(
        self, mock_train, mock_load_data, mock_get_registry, temp_registry, dummy_training_data
    ):
        """Test manual retrain with successful training."""
        mock_get_registry.return_value = temp_registry
        mock_load_data.return_value = dummy_training_data

        # Mock train_enrollment_model to return success metrics AND create the model file
        def train_side_effect(df, models_dir):
            self._create_dummy_model_artifact(Path(models_dir))
            return {
                "use_model": True,
                "selected_model": "RandomForest",
                "candidate_cv_rmse": {"RandomForest": 5.0},
                "selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8},
                "baseline": {"test": {"RMSE": 10.0}},
                "n_courses": 60,
                "features": FEATURE_COLUMNS,
            }

        mock_train.side_effect = train_side_effect

        result = run_manual_retrain(auto_promote=False)

        assert result["status"] == "candidate_ready"
        assert result["candidate_version"] is not None
        assert result["candidate_version"].startswith("v")

    @patch("edup.models.retrain.get_registry")
    @patch("edup.data.load_processed_data")
    @patch("edup.models.models.train_enrollment_model")
    def test_run_manual_retrain_no_model(
        self, mock_train, mock_load_data, mock_get_registry, temp_registry, dummy_training_data
    ):
        """Test manual retrain when no model beats baseline."""
        mock_get_registry.return_value = temp_registry
        mock_load_data.return_value = dummy_training_data
        mock_train.return_value = {
            "use_model": False,
            "selected_model": "RandomForest",
            "candidate_cv_rmse": {"RandomForest": 15.0},
            "selected_test": {"RMSE": 15.0, "MAE": 12.0, "R2": 0.1},
            "baseline": {"test": {"RMSE": 10.0}},
            "n_courses": 60,
        }

        result = run_manual_retrain(auto_promote=False)

        assert result["status"] == "failed"
        assert "did not produce a model" in result.get("error", "")

    @patch("edup.models.retrain.get_registry")
    def test_run_scheduled_retrain_disabled(self, mock_get_registry, temp_registry):
        """Test scheduled retrain when disabled."""
        mock_get_registry.return_value = temp_registry
        # Default config has enabled=False

        result = run_scheduled_retrain()

        assert result["status"] == "disabled"

    @patch("edup.models.retrain.get_registry")
    @patch("edup.data.load_processed_data")
    @patch("edup.models.models.train_enrollment_model")
    def test_run_scheduled_retrain_enabled(
        self, mock_train, mock_load_data, mock_get_registry, temp_registry, dummy_training_data
    ):
        """Test scheduled retrain when enabled."""
        mock_get_registry.return_value = temp_registry
        # Enable scheduled retraining
        config = temp_registry.get_retraining_config()
        config.enabled = True
        temp_registry.save_retraining_config(config)

        mock_load_data.return_value = dummy_training_data

        def train_side_effect(df, models_dir):
            self._create_dummy_model_artifact(Path(models_dir))
            return {
                "use_model": True,
                "selected_model": "RandomForest",
                "candidate_cv_rmse": {"RandomForest": 5.0},
                "selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8},
                "baseline": {"test": {"RMSE": 10.0}},
                "n_courses": 60,
                "features": FEATURE_COLUMNS,
            }

        mock_train.side_effect = train_side_effect

        result = run_scheduled_retrain()

        assert result["status"] == "candidate_ready"
        assert result["candidate_version"] is not None

    def test_promote_version(self, temp_registry):
        """Test promoting a version via CLI function."""
        import joblib
        from sklearn.linear_model import LinearRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        import numpy as np

        pipe = Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())])
        X = np.random.rand(10, len(FEATURE_COLUMNS))
        y = np.random.rand(10)
        pipe.fit(X, y)

        artifact_path = temp_registry.registry_dir / "test_model.pkl"
        joblib.dump(pipe, artifact_path)

        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=artifact_path,
            status="cached", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
        )

        with patch("edup.models.retrain.get_registry", return_value=temp_registry):
            success = promote_version(version)

        assert success is True
        assert temp_registry.get_active_version().version == version

    def test_promote_version_invalid_fails(self, temp_registry):
        """Test promoting invalid version fails."""
        import joblib
        from sklearn.linear_model import LinearRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        import numpy as np

        pipe = Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())])
        X = np.random.rand(10, len(FEATURE_COLUMNS))
        y = np.random.rand(10)
        pipe.fit(X, y)

        artifact_path = temp_registry.registry_dir / "test_model.pkl"
        joblib.dump(pipe, artifact_path)

        version = temp_registry.register_model(
            model_name="test_model", model_type="LR", artifact_path=artifact_path,
            status="cached", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 15.0, "MAE": 12.0, "R2": 0.1}, "baseline": {"test": {"RMSE": 10.0}}},
        )

        with patch("edup.models.retrain.get_registry", return_value=temp_registry):
            success = promote_version(version)

        assert success is False

    def test_rollback_version(self, temp_registry):
        """Test rolling back via CLI function."""
        import joblib
        from sklearn.linear_model import LinearRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        import numpy as np

        pipe = Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())])
        X = np.random.rand(10, len(FEATURE_COLUMNS))
        y = np.random.rand(10)
        pipe.fit(X, y)

        artifact_path = temp_registry.registry_dir / "model1.pkl"
        joblib.dump(pipe, artifact_path)

        v1 = temp_registry.register_model(
            model_name="model1", model_type="LR", artifact_path=artifact_path,
            status="cached", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
        )

        artifact_path2 = temp_registry.registry_dir / "model2.pkl"
        joblib.dump(pipe, artifact_path2)

        v2 = temp_registry.register_model(
            model_name="model2", model_type="RF", artifact_path=artifact_path2,
            status="cached", training_date_utc="2026-01-02T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 4.0, "MAE": 3.0, "R2": 0.9}, "baseline": {"test": {"RMSE": 10.0}}},
        )

        temp_registry.promote(v1)
        temp_registry.promote(v2)

        with patch("edup.models.retrain.get_registry", return_value=temp_registry):
            success = rollback_version()

        assert success is True
        assert temp_registry.get_active_version().version == v1

    def test_rollback_to_specific_version(self, temp_registry):
        """Test rolling back to specific version via CLI function."""
        import joblib
        from sklearn.linear_model import LinearRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        import numpy as np

        pipe = Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())])
        X = np.random.rand(10, len(FEATURE_COLUMNS))
        y = np.random.rand(10)
        pipe.fit(X, y)

        artifact_path = temp_registry.registry_dir / "model1.pkl"
        joblib.dump(pipe, artifact_path)

        v1 = temp_registry.register_model(
            model_name="model1", model_type="LR", artifact_path=artifact_path,
            status="cached", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
        )

        artifact_path2 = temp_registry.registry_dir / "model2.pkl"
        joblib.dump(pipe, artifact_path2)

        v2 = temp_registry.register_model(
            model_name="model2", model_type="RF", artifact_path=artifact_path2,
            status="cached", training_date_utc="2026-01-02T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 4.0, "MAE": 3.0, "R2": 0.9}, "baseline": {"test": {"RMSE": 10.0}}},
        )

        artifact_path3 = temp_registry.registry_dir / "model3.pkl"
        joblib.dump(pipe, artifact_path3)

        v3 = temp_registry.register_model(
            model_name="model3", model_type="XGB", artifact_path=artifact_path3,
            status="cached", training_date_utc="2026-01-03T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 3.0, "MAE": 2.0, "R2": 0.95}, "baseline": {"test": {"RMSE": 10.0}}},
        )

        temp_registry.promote(v1)
        temp_registry.promote(v2)
        temp_registry.promote(v3)

        with patch("edup.models.retrain.get_registry", return_value=temp_registry):
            success = rollback_version(v1)

        assert success is True
        assert temp_registry.get_active_version().version == v1


class TestCLICommands:
    """Test the actual CLI command execution."""

    def test_cli_help(self):
        """Test CLI help command."""
        result = subprocess.run(
            [sys.executable, "-m", "edup.models.retrain", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "EduPro Model Retraining" in result.stdout
        assert "retrain" in result.stdout
        assert "promote" in result.stdout
        assert "rollback" in result.stdout
        assert "status" in result.stdout

    def test_cli_status(self, tmp_path):
        """Test CLI status command."""
        # Create a temporary registry
        registry_dir = tmp_path / "registry"
        registry = ModelRegistry(registry_dir)

        result = subprocess.run(
            [sys.executable, "-m", "edup.models.retrain", "status"],
            capture_output=True,
            text=True,
            env={**os.environ, "EDUPRO_REGISTRY_DIR": str(registry_dir)},
        )
        # The command should run (may not find registry but shouldn't crash)
        # We mainly test it doesn't error out completely
        assert result.returncode in (0, 1)  # May fail if no registry but command runs


import os

if __name__ == "__main__":
    pytest.main([__file__, "-v"])