import pandas as pd
import pytest

pytest.importorskip('plotly')
from app import utils


def _write_csv(df, path):
    df.to_csv(path, index=False)
    return path


def test_missing_data_file_raises_actionable_error(tmp_path):
    with pytest.raises(utils.DataUnavailableError, match='not found'):
        utils.load_processed_data(str(tmp_path / 'missing.csv'))


def test_empty_data_file_raises(tmp_path):
    path = tmp_path / 'empty.csv'
    path.write_text('', encoding='utf-8')
    with pytest.raises(utils.DataUnavailableError, match='empty'):
        utils.load_processed_data(str(path))


def test_missing_required_column_raises(tmp_path, df):
    path = _write_csv(df.drop(columns=['CourseCategory']), tmp_path / 'bad.csv')
    with pytest.raises(utils.DataUnavailableError, match='CourseCategory'):
        utils.load_processed_data(str(path))


def test_non_numeric_amount_raises(tmp_path, df):
    bad = df.copy()
    bad['Amount'] = 'not-a-number'
    path = _write_csv(bad, tmp_path / 'bad.csv')
    with pytest.raises(utils.DataUnavailableError, match='Amount must be numeric'):
        utils.load_processed_data(str(path))


@pytest.mark.parametrize('column,value,match', [
    ('Amount', float('nan'), 'missing values'),
    ('CoursePrice', float('inf'), 'non-finite values'),
])
def test_non_finite_numeric_data_raises(tmp_path, df, column, value, match):
    bad = df.copy()
    bad.loc[0, column] = value
    path = _write_csv(bad, tmp_path / 'bad.csv')
    with pytest.raises(utils.DataUnavailableError, match=match):
        utils.load_processed_data(str(path))


@pytest.mark.parametrize('column,value,match', [
    ('CourseType', 'Trial', 'CourseType must be one of'),
    ('CourseLevel', 'Expert', 'CourseLevel must be one of'),
])
def test_invalid_categorical_domain_raises(tmp_path, df, column, value, match):
    bad = df.copy()
    bad.loc[0, column] = value
    path = _write_csv(bad, tmp_path / 'bad.csv')
    with pytest.raises(utils.DataUnavailableError, match=match):
        utils.load_processed_data(str(path))


def test_invalid_transaction_date_raises(tmp_path, df):
    bad = df.copy()
    bad['TransactionDate'] = 'not-a-date'
    path = _write_csv(bad, tmp_path / 'bad.csv')
    with pytest.raises(utils.DataUnavailableError):
        utils.load_processed_data(str(path))


def test_empty_dataframe_cannot_compute_kpis():
    with pytest.raises(ValueError, match='at least one transaction'):
        utils.compute_kpis(pd.DataFrame())


def test_kpis_match_verified_data(df):
    kpis = utils.compute_kpis(df)
    assert kpis['total_enrollments'] == 10000
    assert kpis['unique_courses'] == 60
    assert kpis['unique_teachers'] == 60
    assert kpis['top_category'] == 'Artificial Intelligence'
    assert kpis['paid_ratio'] == pytest.approx(35.97, abs=1e-9)


def test_missing_forecast_artifact_returns_no_error(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, 'MODELS_DIR', str(tmp_path))
    payload, error = utils.load_forecast_results()
    assert payload is None
    assert error is None


def test_corrupt_forecast_artifact_returns_error(tmp_path, monkeypatch):
    (tmp_path / 'forecast_results.pkl').write_bytes(b'not-a-pickle')
    monkeypatch.setattr(utils, 'MODELS_DIR', str(tmp_path))
    payload, error = utils.load_forecast_results()
    assert payload is None
    assert error and 'could not be loaded' in error


def _forecast_frame(**overrides):
    data = {
        'ds': pd.to_datetime(['2025-01-01', '2025-02-01']),
        'yhat': [100.0, 110.0],
        'yhat_lower': [90.0, 100.0],
        'yhat_upper': [110.0, 120.0],
    }
    data.update(overrides)
    return pd.DataFrame(data)


@pytest.mark.parametrize('payload,match', [
    (None, 'dictionary'),
    ({}, 'missing the revenue forecast'),
    ({'revenue': None}, 'missing the revenue forecast'),
    ({'revenue': pd.DataFrame()}, 'non-empty DataFrame'),
    ({'revenue': _forecast_frame().drop(columns=['yhat_lower'])}, 'missing columns'),
    ({'revenue': _forecast_frame(ds=['bad-date', '2025-02-01'])}, 'invalid dates'),
    ({'revenue': _forecast_frame(yhat=['a', 'b'])}, 'must be numeric'),
    ({'revenue': _forecast_frame(yhat=[float('nan'), 1.0])}, 'non-finite'),
])
def test_malformed_forecast_payload_is_rejected(payload, match):
    with pytest.raises(ValueError, match=match):
        utils.validate_forecast_payload(payload)


def test_valid_forecast_payload_is_accepted():
    payload = {'revenue': _forecast_frame(), 'enrollment': _forecast_frame()}
    assert utils.validate_forecast_payload(payload) is payload


def test_string_forecast_dates_are_normalized():
    payload = {'revenue': _forecast_frame(ds=['2025-01-01', '2025-02-01'])}
    cleaned = utils.validate_forecast_payload(payload)
    assert cleaned is payload
    assert pd.api.types.is_datetime64_any_dtype(cleaned['revenue']['ds'])


def test_checked_in_forecast_artifact_is_valid():
    payload, error = utils.load_forecast_results()
    assert error is None
    assert payload is not None
    assert len(payload['revenue']) > 0


def test_payment_chart_handles_no_paid_transactions(df):
    free_only = df.copy()
    free_only['Amount'] = 0
    fig = utils.chart_payment_methods(free_only)
    assert fig is not None
