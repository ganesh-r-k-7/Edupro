import os
import sys

import pandas as pd
import pytest

pytest.importorskip('joblib')
pytest.importorskip('streamlit')
pytest.importorskip('plotly')

import joblib

from streamlit.testing.v1 import AppTest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(ROOT, 'app', 'app.py')


def _make_app(monkeypatch, data_path=None, models_dir=None):
    import app.utils as app_utils

    monkeypatch.setitem(sys.modules, 'utils', app_utils)
    if data_path is not None:
        monkeypatch.setattr(app_utils, 'DATA_PATH', str(data_path))
    if models_dir is not None:
        monkeypatch.setattr(app_utils, 'MODELS_DIR', str(models_dir))
    app = AppTest.from_file(APP_PATH, default_timeout=90)
    app.run()
    return app


def _widget(widgets, label):
    for widget in widgets:
        if widget.label == label:
            return widget
    raise AssertionError(f'Widget not found: {label}')


def _forecast_frame(dates):
    return pd.DataFrame({
        'ds': dates,
        'yhat': range(100, 100 + len(dates)),
        'yhat_lower': range(90, 90 + len(dates)),
        'yhat_upper': range(110, 110 + len(dates)),
    })


def test_forecast_page_handles_no_future_rows(monkeypatch, tmp_path):
    joblib.dump(
        {'revenue': _forecast_frame(pd.date_range('2025-01-01', periods=12, freq='MS'))},
        tmp_path / 'forecast_results.pkl',
    )
    app = _make_app(monkeypatch, models_dir=tmp_path)
    app.radio[0].set_value('Revenue Forecasting').run()
    assert not app.exception, app.exception
    assert not app.error


def test_forecast_page_handles_all_future_rows(monkeypatch, tmp_path):
    joblib.dump(
        {'revenue': _forecast_frame(pd.date_range('2026-01-01', periods=6, freq='MS'))},
        tmp_path / 'forecast_results.pkl',
    )
    app = _make_app(monkeypatch, models_dir=tmp_path)
    app.radio[0].set_value('Revenue Forecasting').run()
    assert not app.exception, app.exception
    assert not app.error
    assert len(app.dataframe) >= 1


def test_forecast_page_rejects_non_finite_values(monkeypatch, tmp_path):
    frame = _forecast_frame(pd.date_range('2025-01-01', periods=6, freq='MS'))
    frame.loc[0, 'yhat'] = float('nan')
    joblib.dump({'revenue': frame}, tmp_path / 'forecast_results.pkl')
    app = _make_app(monkeypatch, models_dir=tmp_path)
    app.radio[0].set_value('Revenue Forecasting').run()
    assert not app.exception, app.exception
    assert any('non-finite' in item.value for item in app.error)


def test_duplicate_transaction_ids_show_actionable_error(monkeypatch, tmp_path, df):
    bad = df.copy()
    bad.loc[1, 'TransactionID'] = bad.loc[0, 'TransactionID']
    path = tmp_path / 'bad.csv'
    bad.to_csv(path, index=False)
    app = _make_app(monkeypatch, data_path=path)
    assert not app.exception, app.exception
    assert any('unavailable' in item.value for item in app.error)
    assert any('duplicate' in item.value for item in app.caption)
    assert any('TransactionID' in item.value for item in app.caption)


def test_null_category_shows_actionable_error(monkeypatch, tmp_path, df):
    bad = df.copy()
    bad.loc[0, 'CourseCategory'] = None
    path = tmp_path / 'bad.csv'
    bad.to_csv(path, index=False)
    app = _make_app(monkeypatch, data_path=path)
    assert not app.exception, app.exception
    assert any('CourseCategory' in item.value for item in app.caption)


def test_prediction_price_400_workflow(monkeypatch):
    app = _make_app(monkeypatch)
    app.radio[0].set_value('Course Demand Prediction').run()
    _widget(app.number_input, 'Course Price ($)').set_value(400.0)
    _widget(app.button, 'Generate Estimate').click().run()
    assert not app.exception, app.exception
    assert not app.error
    assert len(app.dataframe) >= 1


def test_prediction_paid_zero_price_is_rejected(monkeypatch):
    app = _make_app(monkeypatch)
    app.radio[0].set_value('Course Demand Prediction').run()
    _widget(app.number_input, 'Course Price ($)').set_value(0.0)
    _widget(app.button, 'Generate Estimate').click().run()
    assert not app.exception, app.exception
    assert any('Paid courses require' in item.value for item in app.error)


def test_category_page_handles_category_absent_from_data(monkeypatch, tmp_path, df):
    subset = df[df['CourseCategory'] == 'Artificial Intelligence']
    path = tmp_path / 'subset.csv'
    subset.to_csv(path, index=False)
    app = _make_app(monkeypatch, data_path=path)
    app.radio[0].set_value('Category Analytics').run()
    _widget(app.selectbox, 'Select Category').set_value('Marketing').run()
    assert not app.exception, app.exception
    assert not app.error
    assert any('No data available' in item.value for item in app.warning)
