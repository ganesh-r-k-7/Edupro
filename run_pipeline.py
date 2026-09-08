"""
run_pipeline.py — End-to-end EduPro pipeline runner.

Executes all steps in sequence:
  1. Data Preprocessing
  2. Feature Engineering
  3. EDA (generates charts)
  4. Model Training
  5. Model Evaluation
  6. Forecasting

Run this once before launching the Streamlit dashboard.
"""

import sys
import os

BASE = os.path.dirname(os.path.abspath(__file__))
NOTEBOOKS = os.path.join(BASE, 'notebooks')
sys.path.insert(0, NOTEBOOKS)


def step(name, fn):
    print(f"\n{'='*60}")
    print(f"  STEP: {name}")
    print(f"{'='*60}")
    fn()
    print(f"  DONE: {name}")


if __name__ == '__main__':
    import importlib.util

    def load_and_run(script, fn_name):
        spec = importlib.util.spec_from_file_location("mod", os.path.join(NOTEBOOKS, script))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        getattr(mod, fn_name)()

    step("Data Preprocessing", lambda: load_and_run('01_data_preprocessing.py', 'run_preprocessing'))
    step("Feature Engineering", lambda: load_and_run('03_feature_engineering.py', 'run_feature_engineering'))
    step("Exploratory Data Analysis", lambda: load_and_run('02_eda.py', 'run_eda'))
    step("Model Training", lambda: load_and_run('04_model_training.py', 'run_model_training'))
    step("Model Evaluation", lambda: load_and_run('05_model_evaluation.py', 'run_evaluation'))
    step("Forecasting", lambda: load_and_run('06_forecasting.py', 'run_forecasting'))

    print(f"\n{'='*60}")
    print("  PIPELINE COMPLETE")
    print("  Launch dashboard: streamlit run app/app.py")
    print(f"{'='*60}")
