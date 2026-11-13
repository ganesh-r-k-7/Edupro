"""
Tests for logging configuration and error handling behavior.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest

from edup.logging import configure_logging, get_logger
from edup.exceptions import (
    DataContractError,
    DataUnavailableError,
    ModelLoadError,
    ForecastError,
    DashboardError,
)


class TestLoggingConfiguration:
    """Tests for logging configuration."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_configure_logging_returns_none(self):
        """Test that configure_logging returns None (no return value)."""
        stream = io.StringIO()
        result = configure_logging(level=logging.DEBUG, stream=stream)
        assert result is None

    def test_module_level_loggers_exist(self):
        """Test that module-level loggers are created."""
        from edup.logging import (
            logger_config,
            logger_data,
            logger_features,
            logger_analytics,
            logger_models,
            logger_forecasting,
            logger_reporting,
            logger_schema,
            logger_app,
        )

        for logger in [
            logger_config,
            logger_data,
            logger_features,
            logger_analytics,
            logger_models,
            logger_forecasting,
            logger_reporting,
            logger_schema,
            logger_app,
        ]:
            assert isinstance(logger, logging.Logger)
            assert logger.name.startswith("edup.")


class TestExceptionHierarchy:
    """Tests for exception hierarchy and behavior."""

    def test_data_contract_error_is_value_error(self):
        """Test that DataContractError inherits from ValueError."""
        exc = DataContractError("test")
        assert isinstance(exc, ValueError)

    def test_data_unavailable_error_is_data_contract_error(self):
        """Test that DataUnavailableError inherits from DataContractError."""
        exc = DataUnavailableError("test")
        assert isinstance(exc, DataContractError)
        assert isinstance(exc, ValueError)

    def test_model_load_error_is_exception(self):
        """Test that ModelLoadError inherits from Exception."""
        exc = ModelLoadError("test")
        assert isinstance(exc, Exception)
        assert not isinstance(exc, DataContractError)

    def test_forecast_error_is_data_contract_error(self):
        """Test that ForecastError inherits from DataContractError."""
        exc = ForecastError("test")
        assert isinstance(exc, DataContractError)
        assert isinstance(exc, ValueError)

    def test_dashboard_error_is_exception(self):
        """Test that DashboardError inherits from Exception."""
        exc = DashboardError("test")
        assert isinstance(exc, Exception)
        assert not isinstance(exc, DataContractError)

    def test_exception_chaining_preserved(self):
        """Test that exception chaining with 'from' is preserved."""
        try:
            try:
                raise ValueError("original")
            except ValueError as exc:
                raise DataUnavailableError("wrapped") from exc
        except DataUnavailableError as exc:
            assert exc.__cause__ is not None
            assert isinstance(exc.__cause__, ValueError)
            assert str(exc.__cause__) == "original"

    def test_model_load_error_chaining(self):
        """Test ModelLoadError preserves original exception."""
        try:
            try:
                raise FileNotFoundError("file not found")
            except FileNotFoundError as exc:
                raise ModelLoadError("Failed to load") from exc
        except ModelLoadError as exc:
            assert exc.__cause__ is not None
            assert isinstance(exc.__cause__, FileNotFoundError)


class TestErrorMessages:
    """Tests for error message quality."""

    def test_data_unavailable_error_message(self):
        """Test DataUnavailableError has descriptive message."""
        exc = DataUnavailableError("Processed data file not found: /path/to/data.csv")
        assert "not found" in str(exc)
        assert "/path/to/data.csv" in str(exc)

    def test_model_load_error_message(self):
        """Test ModelLoadError has descriptive message."""
        exc = ModelLoadError("Failed to load enrollment model: file not found")
        assert "Failed to load" in str(exc)
        assert "enrollment model" in str(exc)

    def test_forecast_error_message(self):
        """Test ForecastError has descriptive message."""
        exc = ForecastError("Forecast artifact could not be loaded")
        assert "Forecast artifact" in str(exc)


class TestLoggingInModules:
    """Tests that verify logging is used in key modules."""

    def test_models_module_uses_logger(self):
        """Test that models module uses logger_models."""
        import edup.models.models as models_module

        # Check that logger_models is imported
        assert hasattr(models_module, "logger_models")

    def test_data_module_uses_logger(self):
        """Test that data module uses logger_data."""
        import edup.data.data as data_module

        assert hasattr(data_module, "logger_data")

    def test_forecasting_module_uses_logger(self):
        """Test that forecasting module uses logger_forecasting."""
        import edup.forecasting.forecasting as forecasting_module

        assert hasattr(forecasting_module, "logger_forecasting")


class TestLoggingOutput:
    """Tests for actual logging output capture."""

    def test_logger_output_capture(self, caplog):
        """Test capturing log output with pytest's caplog."""
        logger = get_logger("test.capture")
        caplog.set_level(logging.INFO)

        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")

        assert "Test info message" in caplog.text
        assert "Test warning message" in caplog.text
        assert "Test error message" in caplog.text
        assert "INFO" in caplog.text
        assert "WARNING" in caplog.text
        assert "ERROR" in caplog.text

    def test_logger_debug_not_captured_by_default(self, caplog):
        """Test that DEBUG messages are not captured at INFO level."""
        logger = get_logger("test.debug")
        caplog.set_level(logging.INFO)

        logger.debug("Debug message")

        assert "Debug message" not in caplog.text


class TestErrorHandlingInDataLoading:
    """Tests for error handling in data loading functions."""

    def test_load_raw_data_missing_file_raises(self, tmp_path):
        """Test that load_raw_data raises DataUnavailableError for missing file."""
        from edup.data import load_raw_data

        missing_file = tmp_path / "missing.xlsx"
        with pytest.raises(DataUnavailableError) as exc_info:
            load_raw_data(missing_file)

        assert "not found" in str(exc_info.value)

    def test_load_processed_data_missing_file_raises(self, tmp_path):
        """Test that load_processed_data raises DataUnavailableError for missing file."""
        from edup.data import load_processed_data

        missing_file = tmp_path / "missing.csv"
        with pytest.raises(DataUnavailableError) as exc_info:
            load_processed_data(missing_file)

        assert "not found" in str(exc_info.value)

    def test_load_processed_data_empty_file_raises(self, tmp_path):
        """Test that load_processed_data raises for empty file."""
        from edup.data import load_processed_data

        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("")

        with pytest.raises(DataUnavailableError) as exc_info:
            load_processed_data(empty_file)

        assert "empty" in str(exc_info.value).lower()


class TestErrorHandlingInModelLoading:
    """Tests for error handling in model loading."""

    def test_load_enrollment_model_missing_raises(self):
        """Test that load_enrollment_model raises ModelLoadError for missing file."""
        from edup.models import load_enrollment_model

        with pytest.raises(ModelLoadError) as exc_info:
            load_enrollment_model("/nonexistent/path/model.pkl")

        assert "not found" in str(exc_info.value).lower()


class TestForecastErrorHandling:
    """Tests for forecast error handling."""

    def test_load_forecast_results_missing_returns_none(self):
        """Test that load_forecast_results returns (None, None) for missing artifact."""
        from edup.forecasting import load_forecast_results

        payload, error = load_forecast_results(models_dir="/nonexistent/path")
        assert payload is None
        assert error is None

    def test_load_forecast_results_no_joblib_returns_error(self, monkeypatch):
        """Test that load_forecast_results returns error when joblib not available."""
        import edup.forecasting.forecasting as forecasting_module
        from edup.forecasting import load_forecast_results

        # Patch joblib to None
        monkeypatch.setattr(forecasting_module, "_joblib", None)

        payload, error = load_forecast_results(models_dir="/some/path")
        assert payload is None
        assert error is not None
        assert "joblib" in error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])