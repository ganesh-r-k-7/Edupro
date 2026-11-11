import os

import pytest

pytest.importorskip('streamlit')
pytest.importorskip('plotly')

from streamlit.testing.v1 import AppTest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_app_renders_without_exception():
    app = AppTest.from_file(os.path.join(ROOT, 'app', 'app.py'), default_timeout=60)
    app.run()
    assert not app.exception, app.exception


def test_prediction_page_renders_without_exception():
    app = AppTest.from_file(os.path.join(ROOT, 'app', 'app.py'), default_timeout=60)
    app.run()
    app.radio[0].set_value('Course Demand Prediction').run()
    assert not app.exception, app.exception
