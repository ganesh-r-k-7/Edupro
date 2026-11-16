import importlib.util
import os

import pytest

pytest.importorskip('sklearn')
pytest.importorskip('xgboost')

from edup.config import (
    FEATURE_COLUMNS,
    EXCLUDED_TRANSACTION_FEATURES,
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
)


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
    for column in FEATURE_COLUMNS:
        assert column in course_rows.columns
    for excluded in EXCLUDED_TRANSACTION_FEATURES:
        assert excluded not in course_rows.columns
    assert len(course_rows) == 60


def test_training_feature_order_matches_inference():
    module = _load_training_module()
    assert module.NUMERIC_FEATURES == NUMERIC_FEATURES
    assert module.CATEGORICAL_FEATURES == CATEGORICAL_FEATURES