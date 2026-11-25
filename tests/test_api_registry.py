"""
Tests for API endpoints with model registry integration.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from edup.api.main import app
from edup.config import CATEGORICAL_FEATURES, FEATURE_COLUMNS, NUMERIC_FEATURES
from edup.models import reset_registry
from edup.models.registry import ModelRegistry


@pytest.fixture(autouse=True)
def reset_global_model_state():
    """Reset global model state before each test."""
    import edup.api.main as api_main
    api_main._model = None
    api_main._model_metadata = None
    api_main._model_load_error = None
    yield
    # Also reset after test
    api_main._model = None
    api_main._model_metadata = None
    api_main._model_load_error = None


@pytest.fixture
def client():
    """Create test client - will be created in each test after patches."""
    # This fixture is overridden in tests that need specific registry setup
    return TestClient(app)


@pytest.fixture
def temp_registry(tmp_path):
    """Create a temporary registry for testing."""
    registry_dir = tmp_path / "registry"
    registry = ModelRegistry(registry_dir)
    yield registry
    reset_registry()


@pytest.fixture
def patched_registry(temp_registry):
    """Patch get_registry to return the temp registry."""
    with patch("edup.api.main.get_registry", return_value=temp_registry):
        with patch("edup.models.retrain.get_registry", return_value=temp_registry):
            with patch("edup.models.get_registry", return_value=temp_registry):
                yield temp_registry


def _create_compatible_pipeline():
    """Create a pipeline compatible with the feature engineering output."""
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    # Use DummyRegressor with constant positive value to ensure non-negative predictions
    pipe = Pipeline([("preprocessor", preprocessor), ("model", DummyRegressor(strategy="constant", constant=10.0))])
    # Fit on dummy data with correct feature names
    X = np.random.rand(10, len(FEATURE_COLUMNS))
    X_df = pd.DataFrame(X, columns=FEATURE_COLUMNS)
    y = np.full(10, 10.0)  # Constant positive target
    pipe.fit(X_df, y)
    return pipe


class TestAPIWithRegistry:
    """Tests for API endpoints using the model registry."""

    def test_health_endpoint_with_registry(self, client, patched_registry):
        """Test health endpoint returns registry model info."""
        # The API should load from registry
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "model_available" in data

    def test_model_info_endpoint_with_registry(self, patched_registry):
        """Test model-info endpoint returns registry info."""
        import joblib

        pipe = _create_compatible_pipeline()

        artifact_path = patched_registry.registry_dir / "test_model.pkl"
        joblib.dump(pipe, artifact_path)

        version = patched_registry.register_model(
            model_name="test_model",
            model_type="LinearRegression",
            artifact_path=artifact_path,
            status="candidate",
            training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="EnrollmentCount",
            feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
        )
        patched_registry.approve_candidate(version)
        patched_registry.promote(version)

        # Create client after model is registered and promoted
        from fastapi.testclient import TestClient

        from edup.api.main import app
        client = TestClient(app)

        response = client.get("/model-info")
        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "test_model"
        assert data["status"] == "active"
        assert "registry_version" in data
        assert data["registry_version"] == version
        assert "active_since_utc" in data

    def test_predict_endpoint_with_registry(self, patched_registry):
        """Test predict endpoint works with registry model."""
        import joblib

        pipe = _create_compatible_pipeline()

        artifact_path = patched_registry.registry_dir / "test_model.pkl"
        joblib.dump(pipe, artifact_path)

        version = patched_registry.register_model(
            model_name="test_model",
            model_type="LinearRegression",
            artifact_path=artifact_path,
            status="candidate",
            training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="EnrollmentCount",
            feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
        )
        patched_registry.approve_candidate(version)
        patched_registry.promote(version)

        # Create client after model is registered and promoted
        from fastapi.testclient import TestClient

        from edup.api.main import app
        client = TestClient(app)

        response = client.post("/predict/enrollment", json={
            "course_category": "Programming",
            "course_level": "Beginner",
            "course_price": 100.0,
            "course_duration": 20.0,
            "teacher_experience": 5,
            "teacher_rating": 4.5,
            "course_type": "Paid",
            "course_rating": 4.0,
            "payment_method": "Credit Card",
        })
        assert response.status_code == 200
        data = response.json()
        assert "predicted_enrollment" in data
        assert data["predicted_enrollment"] >= 0
        assert data["model_name"] == "test_model"


class TestRegistryEndpoints:
    """Tests for the new model registry endpoints."""

    def test_list_registry_versions(self, patched_registry):
        """Test listing registry versions."""
        import joblib

        pipe = _create_compatible_pipeline()

        artifact_path = patched_registry.registry_dir / "model1.pkl"
        joblib.dump(pipe, artifact_path)

        patched_registry.register_model(
            model_name="model1", model_type="LR", artifact_path=artifact_path,
            status="cached", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={},
        )

        artifact_path2 = patched_registry.registry_dir / "model2.pkl"
        joblib.dump(pipe, artifact_path2)

        patched_registry.register_model(
            model_name="model2", model_type="RF", artifact_path=artifact_path2,
            status="active", training_date_utc="2026-01-02T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={},
        )

        # Create client after models are registered
        from fastapi.testclient import TestClient

        from edup.api.main import app
        client = TestClient(app)

        response = client.get("/model-registry")
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        assert len(data["versions"]) == 2
        # Newest first
        assert data["versions"][0]["model_name"] == "model2"
        assert data["versions"][1]["model_name"] == "model1"

    def test_get_registry_version(self, patched_registry):
        """Test getting a specific registry version."""
        import joblib

        pipe = _create_compatible_pipeline()

        artifact_path = patched_registry.registry_dir / "model1.pkl"
        joblib.dump(pipe, artifact_path)

        version = patched_registry.register_model(
            model_name="model1", model_type="LR", artifact_path=artifact_path,
            status="cached", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0}},
        )

        # Create client after model is registered
        from fastapi.testclient import TestClient

        from edup.api.main import app
        client = TestClient(app)

        import edup.api.main as api_main
        api_main._model = None
        api_main._model_metadata = None
        api_main._model_load_error = None

        response = client.get(f"/model-registry/{version}")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == version
        assert data["model_name"] == "model1"
        assert data["status"] == "cached"

    def test_get_registry_version_not_found(self, patched_registry):
        """Test getting non-existent registry version returns 404."""
        # Create client
        from fastapi.testclient import TestClient

        from edup.api.main import app
        client = TestClient(app)

        response = client.get("/model-registry/nonexistent")
        assert response.status_code == 404


class TestModelLoadingPriority:
    """Tests for model loading priority (registry active > phase1 > legacy)."""

    def test_registry_active_takes_priority(self, patched_registry, tmp_path):
        """Test that registry active model takes priority over phase1/legacy."""
        import joblib

        pipe_registry = _create_compatible_pipeline()

        artifact_path = patched_registry.registry_dir / "registry_model.pkl"
        joblib.dump(pipe_registry, artifact_path)

        version = patched_registry.register_model(
            model_name="registry_model", model_type="LR", artifact_path=artifact_path,
            status="candidate", training_date_utc="2026-01-01T12:00:00+00:00",
            target_variable="target", feature_names=FEATURE_COLUMNS,
            metrics={"selected_test": {"RMSE": 5.0, "MAE": 4.0, "R2": 0.8}, "baseline": {"test": {"RMSE": 10.0}}},
        )
        patched_registry.approve_candidate(version)
        patched_registry.promote(version)

        # Create client after model is registered and promoted
        from fastapi.testclient import TestClient

        from edup.api.main import app
        client = TestClient(app)

        response = client.get("/model-info")
        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "registry_model"
        assert data["registry_version"] == version


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
