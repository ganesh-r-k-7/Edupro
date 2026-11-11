import importlib.util
import os

import pytest

pytest.importorskip('sklearn')
pytest.importorskip('xgboost')

import feature_contract as fc


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_training_module():
    path = os.path.join(ROOT, 'notebooks', '04_model_training.py')
    spec = importlib.util.spec_from_file_location('edup_training', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_training_and_inference_share_the_feature_contract(df):
    module = _load_training_module()
    course_rows = module.prepare_enrollment_target(df)
    for column in fc.FEATURE_COLUMNS:
        assert column in course_rows.columns
    for excluded in fc.EXCLUDED_TRANSACTION_FEATURES:
        assert excluded not in course_rows.columns
    assert len(course_rows) == 60


def test_training_feature_order_matches_inference():
    module = _load_training_module()
    assert module.NUMERIC_FEATURES == fc.NUMERIC_FEATURES
    assert module.CATEGORICAL_FEATURES == fc.CATEGORICAL_FEATURES
