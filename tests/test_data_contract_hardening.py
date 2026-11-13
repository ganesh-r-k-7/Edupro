import pandas as pd
import pytest

pytest.importorskip('plotly')
from app import utils


TEXT_COLUMNS = [
    'TransactionID', 'UserID', 'CourseID', 'TeacherID', 'CourseName',
    'CourseCategory', 'PaymentMethod', 'TeacherName',
]


def _write(df, path):
    df.to_csv(path, index=False)
    return str(path)


@pytest.mark.parametrize('column', TEXT_COLUMNS)
def test_missing_required_text_value_is_rejected(tmp_path, df, column):
    bad = df.copy()
    bad.loc[0, column] = None
    path = _write(bad, tmp_path / 'bad.csv')
    with pytest.raises(utils.DataUnavailableError, match=column):
        utils.load_processed_data(path)


def test_duplicate_transaction_ids_are_rejected(tmp_path, df):
    bad = df.copy()
    bad.loc[1, 'TransactionID'] = bad.loc[0, 'TransactionID']
    path = _write(bad, tmp_path / 'bad.csv')
    with pytest.raises(utils.DataUnavailableError, match='TransactionID.*duplicate'):
        utils.load_processed_data(path)


@pytest.mark.parametrize('column,value,match', [
    ('CoursePrice', -0.01, 'CoursePrice must be between'),
    ('CoursePrice', 500.01, 'CoursePrice must be between'),
    ('CourseDuration', 0.0, 'CourseDuration must be between'),
    ('CourseDuration', 200.01, 'CourseDuration must be between'),
    ('CourseRating', 0.99, 'CourseRating must be between'),
    ('CourseRating', 5.01, 'CourseRating must be between'),
    ('TeacherRating', 0.99, 'TeacherRating must be between'),
    ('TeacherRating', 5.01, 'TeacherRating must be between'),
    ('YearsOfExperience', -1, 'YearsOfExperience must be between'),
    ('YearsOfExperience', 31, 'YearsOfExperience must be between'),
    ('Amount', -0.01, 'Amount cannot be negative'),
])
def test_out_of_range_numeric_data_is_rejected(tmp_path, df, column, value, match):
    bad = df.copy()
    bad.loc[0, column] = value
    path = _write(bad, tmp_path / 'bad.csv')
    with pytest.raises(utils.DataUnavailableError, match=match):
        utils.load_processed_data(path)


@pytest.mark.parametrize('column,value', [
    ('CoursePrice', 0.0), ('CoursePrice', 500.0),
    ('CourseDuration', 1.0), ('CourseDuration', 200.0),
    ('CourseRating', 1.0), ('CourseRating', 5.0),
    ('TeacherRating', 1.0), ('TeacherRating', 5.0),
    ('YearsOfExperience', 0), ('YearsOfExperience', 30),
    ('Amount', 0.0),
])
def test_numeric_boundaries_are_accepted(tmp_path, df, column, value):
    valid = df.copy()
    valid.loc[0, column] = value
    path = _write(valid, tmp_path / 'valid.csv')
    loaded = utils.load_processed_data(path)
    assert len(loaded) == len(valid)


def test_header_only_file_is_rejected_as_empty(tmp_path, df):
    path = tmp_path / 'header-only.csv'
    df.head(0).to_csv(path, index=False)
    with pytest.raises(utils.DataUnavailableError, match='empty'):
        utils.load_processed_data(str(path))


def test_forecast_loader_reports_missing_joblib(monkeypatch):
    monkeypatch.setattr(utils, 'joblib', None)
    payload, error = utils.load_forecast_results()
    assert payload is None
    assert 'joblib is not installed' in error


def test_timezone_aware_forecast_dates_are_normalized():
    revenue = pd.DataFrame({
        'ds': pd.date_range('2025-01-01', periods=3, freq='MS', tz='UTC'),
        'yhat': [1.0, 2.0, 3.0],
        'yhat_lower': [0.0, 1.0, 2.0],
        'yhat_upper': [2.0, 3.0, 4.0],
    })
    cleaned = utils.validate_forecast_payload({'revenue': revenue})
    assert getattr(cleaned['revenue']['ds'].dt, 'tz', None) is None
    assert pd.api.types.is_datetime64_any_dtype(cleaned['revenue']['ds'])


def test_forecast_with_no_future_rows_is_valid():
    revenue = pd.DataFrame({
        'ds': pd.date_range('2025-01-01', periods=12, freq='MS'),
        'yhat': range(100, 112),
        'yhat_lower': range(90, 102),
        'yhat_upper': range(110, 122),
    })
    payload = utils.validate_forecast_payload({'revenue': revenue})
    assert len(payload['revenue']) == 12
