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
PAGES = [
    'Executive Dashboard',
    'Course Demand Prediction',
    'Revenue Forecasting',
    'Feature Importance Explorer',
    'Category Analytics',
]


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


def test_all_pages_render_without_exception(monkeypatch):
    app = _make_app(monkeypatch)
    assert not app.exception, app.exception
    for page in PAGES[1:]:
        app.radio[0].set_value(page).run()
        assert not app.exception, (page, app.exception)


def test_prediction_paid_price_500_workflow(monkeypatch):
    app = _make_app(monkeypatch)
    app.radio[0].set_value('Course Demand Prediction').run()
    _widget(app.number_input, 'Course Price ($)').set_value(500.0)
    _widget(app.button, 'Generate Estimate').click().run()

    assert not app.exception, app.exception
    assert not app.error
    assert any('does not beat a mean baseline' in w.value for w in app.warning)
    assert any('No price is recommended' in w.value for w in app.warning)
    assert len(app.dataframe) >= 1


def test_prediction_free_course_normalizes_price(monkeypatch):
    app = _make_app(monkeypatch)
    app.radio[0].set_value('Course Demand Prediction').run()
    _widget(app.selectbox, 'Course Type').set_value('Free')
    _widget(app.number_input, 'Course Price ($)').set_value(99.0)
    _widget(app.button, 'Generate Estimate').click().run()

    assert not app.exception, app.exception
    assert not app.error
    messages = [item.value for item in app.info]
    assert any('normalized to a $0 course price' in msg for msg in messages)
    assert any('generate $0 in transaction revenue' in msg for msg in messages)
    assert not any('Price Scenario Analysis' in m.value for m in app.markdown)


def test_forecast_page_handles_missing_artifact(monkeypatch, tmp_path):
    app = _make_app(monkeypatch, models_dir=tmp_path)
    app.radio[0].set_value('Revenue Forecasting').run()
    assert not app.exception, app.exception
    assert not app.error
    assert any('not yet generated' in item.value for item in app.info)


def test_forecast_page_reports_corrupt_artifact(monkeypatch, tmp_path):
    (tmp_path / 'forecast_results.pkl').write_bytes(b'corrupt')
    app = _make_app(monkeypatch, models_dir=tmp_path)
    app.radio[0].set_value('Revenue Forecasting').run()
    assert not app.exception, app.exception
    assert any('could not be loaded' in item.value for item in app.error)


def test_forecast_page_accepts_string_dates(monkeypatch, tmp_path):
    dates = pd.date_range('2025-01-01', periods=18, freq='MS').strftime('%Y-%m-%d')
    revenue = pd.DataFrame({
        'ds': dates,
        'yhat': range(100, 118),
        'yhat_lower': range(90, 108),
        'yhat_upper': range(110, 128),
    })
    joblib.dump({'revenue': revenue}, tmp_path / 'forecast_results.pkl')
    app = _make_app(monkeypatch, models_dir=tmp_path)
    app.radio[0].set_value('Revenue Forecasting').run()
    assert not app.exception, app.exception
    assert not app.error
    assert len(app.dataframe) >= 1


def test_forecast_page_reports_malformed_artifact(monkeypatch, tmp_path):
    bad = pd.DataFrame({'ds': ['2025-01-01'], 'yhat': [1.0]})
    joblib.dump({'revenue': bad}, tmp_path / 'forecast_results.pkl')
    app = _make_app(monkeypatch, models_dir=tmp_path)
    app.radio[0].set_value('Revenue Forecasting').run()
    assert not app.exception, app.exception
    assert any('invalid' in item.value for item in app.error)


def test_missing_data_shows_actionable_error(monkeypatch, tmp_path):
    app = _make_app(monkeypatch, data_path=tmp_path / 'missing.csv')
    assert not app.exception, app.exception
    assert any('unavailable' in item.value for item in app.error)
    assert any('notebooks/01_data_preprocessing.py' in item.value for item in app.code)


def test_malformed_data_shows_actionable_error(monkeypatch, tmp_path, df):
    path = tmp_path / 'bad.csv'
    df.drop(columns=['CourseCategory']).to_csv(path, index=False)
    app = _make_app(monkeypatch, data_path=path)
    assert not app.exception, app.exception
    assert any('unavailable' in item.value for item in app.error)
    assert any('CourseCategory' in item.value for item in app.caption)


def test_category_page_handles_zero_revenue_category(monkeypatch):
    app = _make_app(monkeypatch)
    app.radio[0].set_value('Category Analytics').run()
    _widget(app.selectbox, 'Select Category').set_value('Marketing').run()
    assert not app.exception, app.exception
    assert not app.error
    assert any('Marketing' in item.value for item in app.markdown)
