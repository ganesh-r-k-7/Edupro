"""
Notebook 05: Model Evaluation (Phase 1)

This step no longer evaluates the retired transaction-Amount regressor.
It reports the target-leakage audit and the persisted enrollment baseline
comparison produced by notebook 04. No misleading R²=1.0 plots are generated.
"""

import json
import os
import sys

import pandas as pd

# Ensure shared package is importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from edup.config import MODELS_DIR, REPORTS_DIR
from edup.analytics import amount_price_identity_summary
from edup.data import load_processed_data


def evaluate_revenue_target():
    """Report the accounting identity that invalidates the revenue model."""
    print("\n=== Revenue Target Validity ===")
    df = load_processed_data()
    summary = amount_price_identity_summary(df)
    print(f"  Amount == CoursePrice for paid rows: {summary['identity_holds']}")
    print(f"  Paid/free is course-level: {summary['paid_free_is_course_level']}")
    print(f"  Paid mismatches: {summary['paid_mismatches']}")
    print(f"  Free mismatches: {summary['free_mismatches']}")
    print("  The legacy revenue model is retired and is not evaluated as a predictor.")
    return summary


def evaluate_enrollment_baseline():
    """Read the CV/test comparison written by notebook 04."""
    print("\n=== Enrollment Baseline Comparison ===")
    path = os.path.join(MODELS_DIR, 'enrollment_metrics.json')
    if not os.path.exists(path):
        print("  enrollment_metrics.json not found. Run notebooks/04_model_training.py first.")
        return None
    with open(path, 'r', encoding='utf-8') as handle:
        metrics = json.load(handle)

    baseline = metrics.get('baseline', {})
    selected = metrics.get('selected_test', {})
    print(f"  Courses: {metrics.get('n_courses')}")
    print(f"  Baseline CV RMSE: {baseline.get('cv_rmse')}")
    print(f"  Baseline test RMSE: {baseline.get('test', {}).get('RMSE')}")
    print(f"  Selected model: {metrics.get('selected_model')}")
    print(f"  Selected CV RMSE: {metrics.get('candidate_cv_rmse', {}).get(metrics.get('selected_model'))}")
    print(f"  Selected test RMSE: {selected.get('RMSE')}")
    print(f"  Use model: {metrics.get('use_model')} — {metrics.get('decision')}")
    return metrics


def run_evaluation():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    revenue = evaluate_revenue_target()
    enrollment = evaluate_enrollment_baseline()
    print("\nEvaluation complete. No revenue prediction plots were generated.")
    return {'revenue_target': revenue, 'enrollment': enrollment}


if __name__ == '__main__':
    run_evaluation()