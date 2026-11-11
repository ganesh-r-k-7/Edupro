"""
Notebook 04: Model Training
EduPro Predictive Modeling Project

Phase 1 modeling:
- Enrollment Count: course-level baseline comparison with valid CV/test separation.
- Revenue: the transaction Amount target is retired as an accounting identity.
  No revenue regressor is trained or persisted.
"""

import os
import sys
from sklearn.model_selection import cross_val_score as _sklearn_cross_val_score

# Ensure shared package is importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from edup.models import (
    audit_revenue_target as _audit_revenue_target,
    train_enrollment_model as _train_enrollment_model,
    prepare_enrollment_target,
    get_all_models,
    evaluate_model,
)
from edup.data import load_processed_data
from edup.config import (
    MODELS_DIR as _MODELS_DIR,
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
)

# Module-level variables for backward compatibility with tests
# These can be monkeypatched in tests
MODELS_DIR = _MODELS_DIR
cross_val_score = _sklearn_cross_val_score
NUMERIC_FEATURES = NUMERIC_FEATURES
CATEGORICAL_FEATURES = CATEGORICAL_FEATURES


def train_enrollment_model(df):
    """Wrapper that passes the module's cross_val_score and MODELS_DIR for test patching."""
    return _train_enrollment_model(df, cross_val_score_func=cross_val_score, models_dir=MODELS_DIR)


def audit_revenue_target(df):
    """Wrapper that uses the module's MODELS_DIR for test patching."""
    return _audit_revenue_target(df, models_dir=MODELS_DIR)


# Backward compatibility exports for tests
__all__ = [
    "audit_revenue_target",
    "train_enrollment_model",
    "prepare_enrollment_target",
    "get_all_models",
    "evaluate_model",
    "cross_val_score",
    "MODELS_DIR",
]


def run_model_training():
    df = load_processed_data()
    revenue_audit = audit_revenue_target(df)
    enrollment_metrics = train_enrollment_model(df)
    print("\nModel training complete. Legacy models were not overwritten.")
    return enrollment_metrics, revenue_audit


if __name__ == '__main__':
    run_model_training()