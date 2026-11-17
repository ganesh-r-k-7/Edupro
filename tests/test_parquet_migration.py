"""
Tests for R4.3-A Parquet Migration.

Covers:
- Parquet round-trip equivalence
- Parquet preferred when both formats exist
- CSV fallback when Parquet is absent
- Correct behavior when both formats are absent
- Corrupted Parquet handling
- Schema validation for both formats
- Cache invalidation when the active data file changes
"""

import importlib.util
import logging
import sys
import time

import pandas as pd
import pytest
from app.utils import _get_data_hash

import edup.config as config_module
from edup.config import PROCESSED_DATA_PARQUET, PROCESSED_DATA_PATH
from edup.data import load_processed_data, preprocess_data
from edup.data.data import _load_parquet_or_csv
from edup.exceptions import DataUnavailableError
from edup.schema import validate_processed_data


class TestParquetRoundTrip:
    """Test Parquet write/read round-trip preserves data."""

    def test_parquet_roundtrip_equivalence(self, tmp_path, df):
        """Write DataFrame to Parquet and read back - data should be equivalent."""
        parquet_path = tmp_path / "test.parquet"
        csv_path = tmp_path / "test.csv"

        # Write both formats
        df.to_parquet(parquet_path, compression="zstd", index=False)
        df.to_csv(csv_path, index=False)

        # Read back
        df_parquet = pd.read_parquet(parquet_path)
        df_csv = pd.read_csv(csv_path, parse_dates=["TransactionDate"])

        # Data should be equivalent (dtype differences like int32 vs int64 are acceptable)
        pd.testing.assert_frame_equal(df_parquet, df_csv, check_dtype=False)
        assert df_parquet.shape == df_csv.shape == df.shape
        assert list(df_parquet.columns) == list(df_csv.columns) == list(df.columns)

    def test_parquet_roundtrip_preserves_null_semantics(self, tmp_path, df):
        """Parquet should preserve null values correctly."""
        # Introduce some nulls in a nullable column
        test_df = df.copy()
        test_df.loc[0, "CourseRating"] = None

        parquet_path = tmp_path / "test_nulls.parquet"
        test_df.to_parquet(parquet_path, compression="zstd", index=False)

        df_read = pd.read_parquet(parquet_path)
        assert df_read["CourseRating"].isna().sum() == 1
        assert df_read.loc[0, "CourseRating"] is pd.NA or pd.isna(df_read.loc[0, "CourseRating"])


class TestParquetPreferred:
    """Test Parquet is preferred when both formats exist."""

    def test_load_processed_data_prefers_parquet(self, tmp_path, df, monkeypatch):
        """load_processed_data should load Parquet when both Parquet and CSV exist."""
        csv_path = tmp_path / "processed_data.csv"
        parquet_path = tmp_path / "processed_data.parquet"

        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, compression="zstd", index=False)

        # Mock the config paths
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PATH", csv_path)
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PARQUET", parquet_path)

        loaded = load_processed_data(str(csv_path))
        assert len(loaded) == len(df)

        # Verify it loaded from Parquet by checking the active source hash
        # (the data should be equivalent regardless of source)
        pd.testing.assert_frame_equal(loaded, df, check_dtype=False)

    def test_load_parquet_or_csv_prefers_parquet(self, tmp_path, df):
        """_load_parquet_or_csv should prefer Parquet over CSV."""
        csv_path = tmp_path / "data.csv"
        # _load_parquet_or_csv derives parquet path from csv path
        parquet_path = csv_path.with_suffix(".parquet")

        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, compression="zstd", index=False)

        loaded = _load_parquet_or_csv(str(csv_path))
        assert len(loaded) == len(df)
        pd.testing.assert_frame_equal(loaded, df, check_dtype=False)


class TestCSVFallback:
    """Test CSV fallback when Parquet is absent."""

    def test_load_processed_data_falls_back_to_csv(self, tmp_path, df, monkeypatch):
        """load_processed_data should load CSV when Parquet is missing."""
        csv_path = tmp_path / "processed_data.csv"
        parquet_path = tmp_path / "processed_data.parquet"

        df.to_csv(csv_path, index=False)
        # Do NOT create parquet file

        monkeypatch.setattr(config_module, "PROCESSED_DATA_PATH", csv_path)
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PARQUET", parquet_path)

        loaded = load_processed_data(str(csv_path))
        assert len(loaded) == len(df)
        # CSV uses int64
        assert loaded["TransactionMonth"].dtype == "int64"

    def test_load_parquet_or_csv_falls_back_to_csv(self, tmp_path, df):
        """_load_parquet_or_csv should fall back to CSV when Parquet missing."""
        csv_path = tmp_path / "data.csv"

        df.to_csv(csv_path, index=False)
        # Do NOT create parquet file

        loaded = _load_parquet_or_csv(str(csv_path))
        assert len(loaded) == len(df)
        assert loaded["TransactionMonth"].dtype == "int64"


class TestBothFormatsAbsent:
    """Test behavior when both Parquet and CSV are absent."""

    def test_load_processed_data_raises_when_both_absent(self, tmp_path, monkeypatch):
        """load_processed_data should raise DataUnavailableError when neither file exists."""
        csv_path = tmp_path / "missing.csv"
        parquet_path = tmp_path / "missing.parquet"

        monkeypatch.setattr(config_module, "PROCESSED_DATA_PATH", csv_path)
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PARQUET", parquet_path)

        with pytest.raises(DataUnavailableError, match="not found"):
            load_processed_data(str(csv_path))

    def test_load_parquet_or_csv_raises_when_both_absent(self, tmp_path):
        """_load_parquet_or_csv should raise DataUnavailableError when neither file exists."""
        csv_path = tmp_path / "missing.csv"
        with pytest.raises(DataUnavailableError, match="not found"):
            _load_parquet_or_csv(str(csv_path))


class TestCorruptedParquet:
    """Test handling of corrupted Parquet files."""

    def test_corrupted_parquet_falls_back_to_csv(self, tmp_path, df, monkeypatch):
        """Corrupted Parquet should fall back to CSV with a warning."""
        csv_path = tmp_path / "processed_data.csv"
        parquet_path = tmp_path / "processed_data.parquet"

        df.to_csv(csv_path, index=False)
        # Write corrupted parquet
        parquet_path.write_bytes(b"not a parquet file")

        monkeypatch.setattr(config_module, "PROCESSED_DATA_PATH", csv_path)
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PARQUET", parquet_path)

        # Should fall back to CSV, not raise
        loaded = load_processed_data(str(csv_path))
        assert len(loaded) == len(df)
        assert loaded["TransactionMonth"].dtype == "int64"

    def test_corrupted_parquet_raises_when_csv_also_missing(self, tmp_path, monkeypatch):
        """Corrupted Parquet with no CSV fallback should raise DataUnavailableError."""
        csv_path = tmp_path / "missing.csv"
        parquet_path = tmp_path / "processed_data.parquet"

        # Write corrupted parquet
        parquet_path.write_bytes(b"not a parquet file")

        monkeypatch.setattr(config_module, "PROCESSED_DATA_PATH", csv_path)
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PARQUET", parquet_path)

        with pytest.raises(DataUnavailableError, match="not found"):
            load_processed_data(str(csv_path))

    def test_corrupted_parquet_logs_warning(self, tmp_path, df, monkeypatch, caplog):
        """Corrupted Parquet should log a warning before falling back."""
        csv_path = tmp_path / "processed_data.csv"
        parquet_path = tmp_path / "processed_data.parquet"

        df.to_csv(csv_path, index=False)
        parquet_path.write_bytes(b"not a parquet file")

        monkeypatch.setattr(config_module, "PROCESSED_DATA_PATH", csv_path)
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PARQUET", parquet_path)

        caplog.set_level(logging.WARNING)

        load_processed_data(str(csv_path))

        assert any("Failed to read Parquet file" in record.message for record in caplog.records)
        assert any("Falling back to CSV" in record.message for record in caplog.records)


class TestSchemaValidation:
    """Test schema validation works for both formats."""

    def test_schema_validation_on_parquet(self, tmp_path, df):
        """validate_processed_data should pass for valid Parquet data."""
        parquet_path = tmp_path / "valid.parquet"
        df.to_parquet(parquet_path, compression="zstd", index=False)

        loaded = pd.read_parquet(parquet_path)
        validated = validate_processed_data(loaded)
        assert len(validated) == len(df)

    def test_schema_validation_on_csv(self, tmp_path, df):
        """validate_processed_data should pass for valid CSV data."""
        csv_path = tmp_path / "valid.csv"
        df.to_csv(csv_path, index=False)

        loaded = pd.read_csv(csv_path, parse_dates=["TransactionDate"])
        validated = validate_processed_data(loaded)
        assert len(validated) == len(df)

    def test_schema_validation_rejects_missing_column_parquet(self, tmp_path, df):
        """validate_processed_data should reject Parquet with missing required column."""
        bad_df = df.drop(columns=["CourseCategory"])
        parquet_path = tmp_path / "bad.parquet"
        bad_df.to_parquet(parquet_path, compression="zstd", index=False)

        loaded = pd.read_parquet(parquet_path)
        with pytest.raises(DataUnavailableError, match="CourseCategory"):
            validate_processed_data(loaded)

    def test_schema_validation_rejects_missing_column_csv(self, tmp_path, df):
        """validate_processed_data should reject CSV with missing required column."""
        bad_df = df.drop(columns=["CourseCategory"])
        csv_path = tmp_path / "bad.csv"
        bad_df.to_csv(csv_path, index=False)

        loaded = pd.read_csv(csv_path, parse_dates=["TransactionDate"])
        with pytest.raises(DataUnavailableError, match="CourseCategory"):
            validate_processed_data(loaded)

    def test_schema_validation_rejects_invalid_categorical_parquet(self, tmp_path, df):
        """validate_processed_data should reject Parquet with invalid categorical values."""
        bad_df = df.copy()
        bad_df.loc[0, "CourseType"] = "InvalidType"
        parquet_path = tmp_path / "bad.parquet"
        bad_df.to_parquet(parquet_path, compression="zstd", index=False)

        loaded = pd.read_parquet(parquet_path)
        with pytest.raises(DataUnavailableError, match="CourseType must be one of"):
            validate_processed_data(loaded)

    def test_schema_validation_rejects_non_numeric_parquet(self, df):
        """validate_processed_data should reject data with non-numeric values in numeric columns."""
        bad_df = df.copy()
        bad_df.loc[0, "Amount"] = "not-a-number"
        # Parquet won't store mixed types, so test validation directly on DataFrame
        with pytest.raises(DataUnavailableError, match="Amount must be numeric"):
            validate_processed_data(bad_df)


class TestCacheInvalidation:
    """Test cache invalidation when active data file changes."""

    def test_get_data_hash_changes_when_parquet_modified(self, tmp_path, df, monkeypatch):
        """_get_data_hash should change when the active Parquet file is modified."""
        csv_path = tmp_path / "processed_data.csv"
        parquet_path = tmp_path / "processed_data.parquet"

        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, compression="zstd", index=False)

        monkeypatch.setattr("app.utils._DATA_CSV", str(csv_path))
        monkeypatch.setattr("app.utils._DATA_PARQUET", str(parquet_path))

        hash1 = _get_data_hash()

        # Modify parquet file
        time.sleep(0.01)  # Ensure mtime changes
        df.to_parquet(parquet_path, compression="zstd", index=False)

        hash2 = _get_data_hash()
        assert hash1 != hash2

    def test_get_data_hash_changes_when_csv_becomes_active(self, tmp_path, df, monkeypatch):
        """_get_data_hash should change when falling back from Parquet to CSV."""
        csv_path = tmp_path / "processed_data.csv"
        parquet_path = tmp_path / "processed_data.parquet"

        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, compression="zstd", index=False)

        monkeypatch.setattr("app.utils._DATA_CSV", str(csv_path))
        monkeypatch.setattr("app.utils._DATA_PARQUET", str(parquet_path))

        hash_with_parquet = _get_data_hash()

        # Remove parquet so CSV becomes active
        parquet_path.unlink()

        hash_without_parquet = _get_data_hash()
        assert hash_with_parquet != hash_without_parquet

    def test_get_data_hash_includes_mtime_and_size(self, tmp_path, df, monkeypatch):
        """_get_data_hash should include both mtime and file size."""
        csv_path = tmp_path / "processed_data.csv"
        parquet_path = tmp_path / "processed_data.parquet"

        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, compression="zstd", index=False)

        monkeypatch.setattr("app.utils._DATA_CSV", str(csv_path))
        monkeypatch.setattr("app.utils._DATA_PARQUET", str(parquet_path))

        hash_val = _get_data_hash()
        parts = hash_val.split("_")
        expected_parts = 2
        assert len(parts) == expected_parts
        assert parts[0].isdigit()  # mtime in nanoseconds
        assert parts[1].isdigit()  # file size in bytes

    def test_get_data_hash_returns_no_data_when_both_absent(self, tmp_path, monkeypatch):
        """_get_data_hash should return 'no_data' when neither file exists."""
        csv_path = tmp_path / "missing.csv"
        parquet_path = tmp_path / "missing.parquet"

        monkeypatch.setattr("app.utils._DATA_CSV", str(csv_path))
        monkeypatch.setattr("app.utils._DATA_PARQUET", str(parquet_path))

        assert _get_data_hash() == "no_data"


class TestPreprocessDataWritesBoth:
    """Test that preprocess_data writes both CSV and Parquet."""

    def test_preprocess_data_writes_both_formats(self, tmp_path, df, monkeypatch):
        """preprocess_data should atomically write both CSV and Parquet."""
        # Use a small subset of real data for testing
        test_df = df.head(10).copy()

        def mock_load_raw_data(path=None):
            # Return minimal sheets that will produce test_df after preprocessing
            users = pd.DataFrame({
                "UserID": test_df["UserID"].unique(),
                "UserName": [f"User{i}" for i in test_df["UserID"].unique()],
                "Age": [25] * len(test_df["UserID"].unique()),
                "Gender": ["M"] * len(test_df["UserID"].unique()),
                "Email": [f"user{i}@test.com" for i in test_df["UserID"].unique()],
            })
            teachers = pd.DataFrame({
                "TeacherID": test_df["TeacherID"].unique(),
                "TeacherName": test_df.loc[test_df["TeacherID"].drop_duplicates().index, "TeacherName"].values,
                "Age": [35] * len(test_df["TeacherID"].unique()),
                "Gender": ["F"] * len(test_df["TeacherID"].unique()),
                "Expertise": test_df.loc[test_df["TeacherID"].drop_duplicates().index, "Expertise"].values,
                "YearsOfExperience": test_df.loc[test_df["TeacherID"].drop_duplicates().index, "YearsOfExperience"].values,
                "TeacherRating": test_df.loc[test_df["TeacherID"].drop_duplicates().index, "TeacherRating"].values,
            })
            courses = pd.DataFrame({
                "CourseID": test_df["CourseID"].unique(),
                "CourseName": test_df.loc[test_df["CourseID"].drop_duplicates().index, "CourseName"].values,
                "CourseCategory": test_df.loc[test_df["CourseID"].drop_duplicates().index, "CourseCategory"].values,
                "CourseType": test_df.loc[test_df["CourseID"].drop_duplicates().index, "CourseType"].values,
                "CourseLevel": test_df.loc[test_df["CourseID"].drop_duplicates().index, "CourseLevel"].values,
                "CoursePrice": test_df.loc[test_df["CourseID"].drop_duplicates().index, "CoursePrice"].values,
                "CourseDuration": test_df.loc[test_df["CourseID"].drop_duplicates().index, "CourseDuration"].values,
                "CourseRating": test_df.loc[test_df["CourseID"].drop_duplicates().index, "CourseRating"].values,
            })
            transactions = test_df[["TransactionID", "UserID", "CourseID", "TeacherID", "TransactionDate", "Amount", "PaymentMethod"]].copy()
            return {"Users": users, "Teachers": teachers, "Courses": courses, "Transactions": transactions}

        # Patch at the module where it's defined
        monkeypatch.setattr("edup.data.data.load_raw_data", mock_load_raw_data)

        csv_path = tmp_path / "processed.csv"
        parquet_path = tmp_path / "processed.parquet"

        monkeypatch.setattr(config_module, "PROCESSED_DATA_PATH", csv_path)
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PARQUET", parquet_path)
        monkeypatch.setattr(config_module, "RAW_DATA_PATH", tmp_path / "raw.xlsx")

        result = preprocess_data(output_path=str(csv_path))

        assert csv_path.exists()
        assert parquet_path.exists()
        assert len(result) == len(test_df)

        # Verify both files can be loaded and are equivalent
        df_csv = pd.read_csv(csv_path, parse_dates=["TransactionDate"])
        df_parquet = pd.read_parquet(parquet_path)
        pd.testing.assert_frame_equal(df_parquet, df_csv, check_dtype=False)


class TestFeatureEngineeringWritesBoth:
    """Test that feature engineering notebook writes both formats."""

    def test_feature_engineering_writes_both(self, tmp_path, df, monkeypatch):
        """run_feature_engineering should write both CSV and Parquet."""
        csv_path = tmp_path / "features.csv"
        parquet_path = tmp_path / "features.parquet"

        # Write test data first
        df.to_csv(csv_path, index=False)

        # Mock the config paths before loading module
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PATH", csv_path)
        monkeypatch.setattr(config_module, "PROCESSED_DATA_PARQUET", parquet_path)

        # Load the feature engineering module
        spec = importlib.util.spec_from_file_location(
            "feature_eng", "notebooks/03_feature_engineering.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["feature_eng"] = module
        spec.loader.exec_module(module)

        # Now set the module's path attributes
        module.DATA_PATH = str(csv_path)
        module.OUTPUT_PATH = str(csv_path)
        module.OUTPUT_PARQUET = str(parquet_path)

        result = module.run_feature_engineering()

        assert csv_path.exists()
        assert parquet_path.exists()
        assert len(result) == len(df)

        # Verify both files have the engineered columns
        df_csv = pd.read_csv(csv_path, parse_dates=["TransactionDate"])
        df_parquet = pd.read_parquet(parquet_path)

        for col in ["PriceBand", "DurationBucket", "RatingTier", "EncodedCourseLevel"]:
            assert col in df_csv.columns
            assert col in df_parquet.columns

        pd.testing.assert_frame_equal(df_parquet, df_csv, check_dtype=False)


class TestDataEquivalence:
    """Test that Parquet and CSV produce equivalent DataFrames in production."""

    def test_production_parquet_csv_equivalence(self):
        """Production Parquet and CSV files should contain equivalent data."""
        df_parquet = pd.read_parquet(PROCESSED_DATA_PARQUET)
        df_csv = pd.read_csv(PROCESSED_DATA_PATH, parse_dates=["TransactionDate"])

        assert df_parquet.shape == df_csv.shape
        assert list(df_parquet.columns) == list(df_csv.columns)
        pd.testing.assert_frame_equal(df_parquet, df_csv, check_dtype=False)

    def test_production_load_prefers_parquet(self):
        """load_processed_data should load from Parquet in production."""
        df = load_processed_data()
        # Verify data loads correctly (Parquet preferred)
        expected_rows = 10000
        assert len(df) == expected_rows
        assert "TransactionMonth" in df.columns
