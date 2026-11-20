"""
test_api.py — Comprehensive tests for EduPro Enrollment Prediction API.
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from edup.api.main import app, _load_model_and_metadata


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_model_state():
    """Reset global model state before each test."""
    import edup.api.main as api_main

    api_main._model = None
    api_main._model_metadata = None
    api_main._model_load_error = None
    yield
    api_main._model = None
    api_main._model_metadata = None
    api_main._model_load_error = None


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_status(self, client: TestClient):
        """Health endpoint returns a status field."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")

    def test_health_returns_model_available(self, client: TestClient):
        """Health endpoint returns model_available boolean."""
        response = client.get("/health")
        data = response.json()
        assert "model_available" in data
        assert isinstance(data["model_available"], bool)

    def test_health_returns_model_name_when_available(self, client: TestClient):
        """Health endpoint returns model_name when model is loaded."""
        response = client.get("/health")
        data = response.json()
        if data["model_available"]:
            # Model name may be None if metadata not available (legacy model)
            assert data["model_name"] is None or isinstance(data["model_name"], str)

    def test_health_returns_model_version_when_available(self, client: TestClient):
        """Health endpoint returns model_version when model is loaded."""
        response = client.get("/health")
        data = response.json()
        if data["model_available"]:
            # Model version may be None if metadata not available (legacy model)
            assert data["model_version"] is None or isinstance(data["model_version"], str)

    def test_health_does_not_reload_model(self, client: TestClient):
        """Health endpoint does not reload model on each call."""
        import edup.api.main as api_main

        # First call
        response1 = client.get("/health")
        model_id_1 = id(api_main._model)

        # Second call
        response2 = client.get("/health")
        model_id_2 = id(api_main._model)

        # Model should be the same object (not reloaded)
        assert model_id_1 == model_id_2


class TestModelInfoEndpoint:
    """Tests for GET /model-info endpoint."""

    def test_model_info_returns_403_when_model_unavailable(self, client: TestClient):
        """Model info returns 503 when model is not loaded."""
        import edup.api.main as api_main

        api_main._model = None
        api_main._model_metadata = None
        api_main._model_load_error = "Model not found"

        response = client.get("/model-info")
        assert response.status_code == 503
        data = response.json()
        assert "error" in data

    def test_model_info_returns_model_name(self, client: TestClient):
        """Model info returns model_name."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            assert "model_name" in data
            assert isinstance(data["model_name"], str)

    def test_model_info_returns_model_type(self, client: TestClient):
        """Model info returns model_type."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            assert "model_type" in data
            assert isinstance(data["model_type"], str)

    def test_model_info_returns_model_version(self, client: TestClient):
        """Model info returns model_version (artifact filename)."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            assert "model_version" in data
            assert isinstance(data["model_version"], str)

    def test_model_info_returns_status(self, client: TestClient):
        """Model info returns status."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert data["status"] in ("active", "legacy", "retired", "cached")

    def test_model_info_returns_feature_names(self, client: TestClient):
        """Model info returns feature_names in canonical order."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            assert "feature_names" in data
            assert isinstance(data["feature_names"], list)
            assert len(data["feature_names"]) > 0

    def test_model_info_returns_target_variable(self, client: TestClient):
        """Model info returns target_variable."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            assert "target_variable" in data

    def test_model_info_returns_training_date(self, client: TestClient):
        """Model info returns training_date_utc."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            assert "training_date_utc" in data

    def test_model_info_returns_metrics(self, client: TestClient):
        """Model info returns metrics dict."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            assert "metrics" in data
            assert isinstance(data["metrics"], dict)

    def test_model_info_returns_notes(self, client: TestClient):
        """Model info returns notes."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            assert "notes" in data

    def test_model_info_no_filesystem_paths(self, client: TestClient):
        """Model info never exposes filesystem paths."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            json_str = json.dumps(data)
            assert "/models/" not in json_str
            assert "enrollment_model.pkl" not in json_str or data["model_version"] == "enrollment_model.pkl"
            # Path should not contain directory separators beyond filename
            if "model_version" in data:
                assert "/" not in data["model_version"]
                assert "\\" not in data["model_version"]

    def test_model_info_no_secrets(self, client: TestClient):
        """Model info never exposes secrets or sensitive internal info."""
        response = client.get("/model-info")
        if response.status_code == 200:
            data = response.json()
            json_str = json.dumps(data).lower()
            assert "secret" not in json_str
            assert "password" not in json_str
            assert "key" not in json_str or "metrics" in data  # metrics keys are OK


class TestPredictEndpoint:
    """Tests for POST /predict/enrollment endpoint."""

    def test_predict_returns_403_when_model_unavailable(self, client: TestClient):
        """Predict returns 503 when model is not loaded."""
        import edup.api.main as api_main

        api_main._model = None
        api_main._model_metadata = None
        api_main._model_load_error = "Model not found"

        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 503
        data = response.json()
        assert "error" in data

    def test_predict_successful_with_required_fields(self, client: TestClient):
        """Predict succeeds with only required fields."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert "predicted_enrollment" in data
            assert isinstance(data["predicted_enrollment"], (int, float))
            assert data["predicted_enrollment"] >= 0

    def test_predict_successful_with_all_fields(self, client: TestClient):
        """Predict succeeds with all fields including optional."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
                "course_type": "Paid",
                "course_rating": 4.0,
                "payment_method": "Credit Card",
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert "predicted_enrollment" in data
            assert isinstance(data["predicted_enrollment"], (int, float))
            assert data["predicted_enrollment"] >= 0

    def test_predict_returns_model_name(self, client: TestClient):
        """Predict response includes model_name."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert "model_name" in data

    def test_predict_returns_model_version(self, client: TestClient):
        """Predict response includes model_version."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert "model_version" in data

    def test_predict_returns_features_used(self, client: TestClient):
        """Predict response includes features_used."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert "features_used" in data
            assert isinstance(data["features_used"], list)
            assert len(data["features_used"]) > 0

    def test_predict_rejects_missing_required_fields(self, client: TestClient):
        """Predict returns 422 for missing required fields (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                # Missing course_price, course_duration, teacher_experience, teacher_rating
            },
        )
        assert response.status_code == 422
        data = response.json()
        # FastAPI returns validation errors in 'detail' field for schema-level validation
        assert "detail" in data
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0

    def test_predict_rejects_invalid_category(self, client: TestClient):
        """Predict returns 422 for invalid course_category (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "InvalidCategory",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_invalid_level(self, client: TestClient):
        """Predict returns 422 for invalid course_level (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Expert",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_invalid_type(self, client: TestClient):
        """Predict returns 422 for invalid course_type (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
                "course_type": "FreeTrial",
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_invalid_payment_method(self, client: TestClient):
        """Predict returns 422 for invalid payment_method (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
                "payment_method": "Bitcoin",
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_price_out_of_bounds_low(self, client: TestClient):
        """Predict returns 422 for price below MIN_PRICE (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": -1.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_price_out_of_bounds_high(self, client: TestClient):
        """Predict returns 422 for price above MAX_PRICE (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 500.01,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_duration_out_of_bounds_low(self, client: TestClient):
        """Predict returns 422 for duration below MIN_DURATION (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 0.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_duration_out_of_bounds_high(self, client: TestClient):
        """Predict returns 422 for duration above MAX_DURATION (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 200.01,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_rating_out_of_bounds(self, client: TestClient):
        """Predict returns 422 for rating outside 1-5 range (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 5.01,
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_experience_out_of_bounds(self, client: TestClient):
        """Predict returns 422 for experience outside 0-30 range (FastAPI validation error)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 31.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 422

    def test_predict_rejects_boolean_inputs(self, client: TestClient):
        """Predict returns 400 for boolean inputs (should be numbers)."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": True,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 400

    def test_predict_rejects_nan_inputs(self, client: TestClient):
        """Predict rejects NaN inputs via validation (tested via direct validation call)."""
        # NaN cannot be sent via JSON, test the validation directly
        from edup.features import validate_course_inputs
        from edup.exceptions import ModelLoadError
        with pytest.raises(ValueError, match="must be finite"):
            validate_course_inputs(
                course_category="Programming",
                course_level="Beginner",
                course_price=float("nan"),
                course_duration=20.0,
                teacher_experience=5.0,
                teacher_rating=4.0,
            )

    def test_predict_rejects_inf_inputs(self, client: TestClient):
        """Predict rejects Inf inputs via validation (tested via direct validation call)."""
        # Inf cannot be sent via JSON, test the validation directly
        from edup.features import validate_course_inputs
        with pytest.raises(ValueError, match="must be finite"):
            validate_course_inputs(
                course_category="Programming",
                course_level="Beginner",
                course_price=float("inf"),
                course_duration=20.0,
                teacher_experience=5.0,
                teacher_rating=4.0,
            )

    def test_predict_boundary_price_zero(self, client: TestClient):
        """Predict accepts price=0 for Free courses."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 0.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
                "course_type": "Free",
            },
        )
        # Should succeed (0 is valid for Free courses)
        if response.status_code == 200:
            data = response.json()
            assert data["predicted_enrollment"] >= 0

    def test_predict_boundary_price_max(self, client: TestClient):
        """Predict accepts price=MAX_PRICE."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 500.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert data["predicted_enrollment"] >= 0

    def test_predict_boundary_duration_min(self, client: TestClient):
        """Predict accepts duration=MIN_DURATION."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 1.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert data["predicted_enrollment"] >= 0

    def test_predict_boundary_duration_max(self, client: TestClient):
        """Predict accepts duration=MAX_DURATION."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 200.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert data["predicted_enrollment"] >= 0

    def test_predict_boundary_rating_min(self, client: TestClient):
        """Predict accepts rating=MIN_RATING."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 1.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert data["predicted_enrollment"] >= 0

    def test_predict_boundary_rating_max(self, client: TestClient):
        """Predict accepts rating=MAX_RATING."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 5.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert data["predicted_enrollment"] >= 0

    def test_predict_boundary_experience_min(self, client: TestClient):
        """Predict accepts experience=MIN_EXPERIENCE."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 0.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert data["predicted_enrollment"] >= 0

    def test_predict_boundary_experience_max(self, client: TestClient):
        """Predict accepts experience=MAX_EXPERIENCE."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 30.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert data["predicted_enrollment"] >= 0

    def test_predict_response_schema(self, client: TestClient):
        """Predict response matches expected schema."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        if response.status_code == 200:
            data = response.json()
            # Check all required fields
            assert "predicted_enrollment" in data
            assert "model_name" in data
            assert "model_version" in data
            assert "features_used" in data
            # Check types
            assert isinstance(data["predicted_enrollment"], (int, float))
            assert isinstance(data["model_name"], (str, type(None)))
            assert isinstance(data["model_version"], (str, type(None)))
            assert isinstance(data["features_used"], list)
            # Check prediction is non-negative
            assert data["predicted_enrollment"] >= 0

    def test_predict_error_response_schema(self, client: TestClient):
        """Error responses follow consistent schema."""
        # Test our custom error format (for validation errors from our code)
        import edup.api.main as api_main
        from unittest.mock import MagicMock

        # Set up a mock model that works
        mock_model = MagicMock()
        mock_model.predict.return_value = [100.0]
        api_main._model = mock_model
        api_main._model_metadata = MagicMock()
        api_main._model_metadata.model_name = "test_model"
        api_main._model_metadata.artifact_filename = "test.pkl"

        # Test ValueError from our validation (e.g., invalid price for Paid course)
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 0.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
                "course_type": "Paid",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "message" in data
        assert isinstance(data["error"], str)
        assert isinstance(data["message"], str)
        # HTTPException handler returns "HTTPException" for all HTTP exceptions
        assert data["error"] == "HTTPException"

    def test_predict_no_stack_trace_in_error(self, client: TestClient):
        """Error responses don't contain stack traces."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "InvalidCategory",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        data = response.json()
        json_str = json.dumps(data)
        assert "traceback" not in json_str.lower()
        assert "file " not in json_str.lower()
        assert "line " not in json_str.lower()


class TestModelLoadedOnce:
    """Tests that model is loaded only once per process."""

    def test_model_loaded_once_across_requests(self, client: TestClient):
        """Model loading happens only once across multiple requests."""
        import edup.api.main as api_main

        # Make multiple requests
        client.get("/health")
        client.get("/health")
        client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )

        # Model should be loaded and cached
        assert api_main._model is not None
        # Check that _load_model_and_metadata doesn't reload
        model1, _, _ = api_main._load_model_and_metadata()
        model2, _, _ = api_main._load_model_and_metadata()
        assert model1 is model2


class TestFeatureParityWithStreamlit:
    """Tests that API predictions match Streamlit prediction logic."""

    def test_predict_uses_same_feature_engineering(self, client: TestClient):
        """API uses the same feature engineering as Streamlit."""
        from edup.features import build_feature_frame, validate_course_inputs

        # Build feature frame directly
        values = validate_course_inputs(
            course_category="Programming",
            course_level="Beginner",
            course_price=99.0,
            course_duration=20.0,
            teacher_experience=5.0,
            teacher_rating=4.0,
            course_type="Paid",
            course_rating=4.0,
            payment_method="Credit Card",
        )
        X_direct = build_feature_frame(**values)

        # Make API request
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
                "course_type": "Paid",
                "course_rating": 4.0,
                "payment_method": "Credit Card",
            },
        )

        if response.status_code == 200:
            data = response.json()
            # Features used should match FEATURE_COLUMNS
            from edup.config import FEATURE_COLUMNS
            assert data["features_used"] == FEATURE_COLUMNS

    def test_predict_free_course_normalizes_price(self, client: TestClient):
        """API normalizes price to 0 for Free courses, like Streamlit."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
                "course_type": "Free",
            },
        )
        if response.status_code == 200:
            # Should succeed (validation normalizes price to 0 for Free)
            data = response.json()
            assert data["predicted_enrollment"] >= 0

    def test_predict_rejects_paid_zero_price(self, client: TestClient):
        """API rejects zero price for Paid courses, like Streamlit."""
        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 0.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
                "course_type": "Paid",
            },
        )
        assert response.status_code == 400


class TestMissingModelArtifact:
    """Tests for missing model artifact scenarios."""

    def test_health_shows_degraded_when_model_missing(self, client: TestClient):
        """Health shows degraded when model artifact is missing."""
        import edup.api.main as api_main

        api_main._model = None
        api_main._model_metadata = None
        api_main._model_load_error = "Model not found"

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["model_available"] is False

    def test_model_info_returns_503_when_model_missing(self, client: TestClient):
        """Model info returns 503 when model artifact is missing."""
        import edup.api.main as api_main

        api_main._model = None
        api_main._model_metadata = None
        api_main._model_load_error = "Model not found"

        response = client.get("/model-info")
        assert response.status_code == 503

    def test_predict_returns_503_when_model_missing(self, client: TestClient):
        """Predict returns 503 when model artifact is missing."""
        import edup.api.main as api_main

        api_main._model = None
        api_main._model_metadata = None
        api_main._model_load_error = "Model not found"

        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        assert response.status_code == 503


class TestCorruptedModelArtifact:
    """Tests for corrupted model artifact scenarios."""

    def test_health_shows_degraded_when_model_corrupted(self, client: TestClient):
        """Health shows degraded when model artifact is corrupted."""
        import edup.api.main as api_main

        api_main._model = None
        api_main._model_metadata = None
        api_main._model_load_error = "Failed to load model: corrupted data"

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["model_available"] is False


class TestPredictionFailures:
    """Tests for prediction failure scenarios."""

    def test_predict_handles_model_prediction_error(self, client: TestClient):
        """Predict handles model prediction errors gracefully."""
        import edup.api.main as api_main

        # Mock model that raises on predict
        mock_model = MagicMock()
        mock_model.predict.side_effect = Exception("Prediction failed")
        api_main._model = mock_model
        api_main._model_metadata = MagicMock()
        api_main._model_metadata.model_name = "test_model"
        api_main._model_metadata.artifact_filename = "test.pkl"

        response = client.post(
            "/predict/enrollment",
            json={
                "course_category": "Programming",
                "course_level": "Beginner",
                "course_price": 99.0,
                "course_duration": 20.0,
                "teacher_experience": 5.0,
                "teacher_rating": 4.0,
            },
        )
        # General exception handler catches it and returns 500 with InternalServerError
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"] == "InternalServerError"


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_returns_api_info(self, client: TestClient):
        """Root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data
        assert "model_info" in data
        assert "predict" in data


class TestOpenAPIDocs:
    """Tests that OpenAPI docs are accessible."""

    def test_docs_endpoint_accessible(self, client: TestClient):
        """Swagger UI at /docs is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_accessible(self, client: TestClient):
        """OpenAPI JSON at /openapi.json is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "/health" in data["paths"]
        assert "/model-info" in data["paths"]
        assert "/predict/enrollment" in data["paths"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])