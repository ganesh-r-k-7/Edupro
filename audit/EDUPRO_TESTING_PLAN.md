# EDUPRO — Testing Plan

**Companion to:** `audit/EDUPRO_AUDIT_REPORT.md` and `audit/EDUPRO_IMPROVEMENT_ROADMAP.md`  
**Audit date:** 2026-10-28  
**Current status:** no automated tests exist. This plan defines the minimum credible suite and the regression tests for confirmed findings.

---

## 1. Existing Tests and Testing Gaps

### 1.1 What exists

**No test suite exists.** The repository contains:

- no `tests/` directory,
- no `test_*.py` or `*_test.py`,
- no `conftest.py`, `pytest.ini`, `tox.ini`, or `pyproject.toml` test configuration,
- no `.github/workflows` or other CI configuration,
- no fixtures or golden files,
- no coverage configuration,
- no `pytest`/`hypothesis`/`streamlit.testing` dependencies.

### 1.2 What was run during the audit

A safe syntax check was performed by parsing all nine Python files with Python's `ast` module. All parsed successfully. This is not a functional test and does not exercise imports, data, models, or the dashboard.

No pipeline, app, model training, Prophet fit, SHAP computation, or pickle load was executed because:

- the project dependencies are not installed in the audit environment,
- running the pipeline would overwrite checked-in data/models/reports,
- loading untrusted pickles is not safe in an audit.

### 1.3 Critical testing gaps

| Gap | Consequence | Findings |
|---|---|---|
| No feature parity tests | Training and inference can diverge silently (already do) | F-03, F-04, F-21 |
| No target/leakage tests | A tautological model can be reported as excellent | F-01, F-10 |
| No model evaluation tests | Test-set selection goes unnoticed | F-07 |
| No report fact tests | Docs can contradict data | F-06, F-20 |
| No dashboard tests | Crashes/ignored inputs ship | F-02, F-03, F-04, F-09, F-11 |
| No pipeline idempotency tests | Repeated runs change schema | F-12 |
| No schema tests | Excel edits break the pipeline | F-13 |
| No forecast tests | Fallback/metrics/claims are unverified | F-14, F-16 |
| No reproducibility tests | A clean environment may not load the models | F-17 |
| No security/smoke tests | Missing auth/artifact integrity goes unnoticed | F-22, F-24 |

---

## 2. Test Strategy

Use a small, fast test pyramid with a thin end-to-end layer.

```text
                 ┌─────────────────────────┐
                 │ E2E / Streamlit AppTest │  few, slow
                 ├─────────────────────────┤
                 │ Integration             │
                 │ pipeline, artifacts,    │
                 │ schema, forecast        │
                 ├─────────────────────────┤
                 │ Unit                    │
                 │ transforms, metrics,    │
                 │ validation, helpers     │  many, fast
                 └─────────────────────────┘
```

### Principles

1. **Fast unit tests for pure logic** (binning, metrics, schema rules, report facts).
2. **Fixture-based integration tests** on a tiny synthetic dataset checked into `tests/fixtures/` (not the full 10k-row workbook).
3. **AppTest for UI contracts** (page renders, inputs passed, error states) rather than brittle DOM snapshots.
4. **No network, no external services, no destructive operations** in tests.
5. **Deterministic**: fixed seeds, frozen dates, temporary directories.
6. **CI-enforced**: lint, type check, unit, integration, AppTest, and a small pipeline smoke run.

### Proposed layout

```text
tests/
├── conftest.py
├── fixtures/
│   ├── edup_small.xlsx          # 4 sheets, ~20 transactions
│   ├── processed_small.csv
│   ├── model_linear.pkl         # generated in fixture, not committed
│   └── model_tree.pkl
├── unit/
│   ├── test_binning.py
│   ├── test_input_builder.py
│   ├── test_metrics.py
│   ├── test_schema.py
│   ├── test_quality_rules.py
│   ├── test_report_facts.py
│   └── test_teacher_aggregation.py
├── integration/
│   ├── test_pipeline_idempotency.py
│   ├── test_model_artifact_contract.py
│   ├── test_forecast_backtest.py
│   └── test_artifact_missing.py
├── e2e/
│   ├── test_dashboard_pages.py
│   └── test_prediction_flow.py
└── regression/
    ├── test_f01_revenue_identity.py
    ├── test_f02_price_optimum.py
    ├── test_f03_inputs_used.py
    ├── test_f04_price_bounds.py
    └── test_f06_report_facts.py
```

---

## 3. Unit Tests

### 3.1 Feature binning and input construction (highest priority)

| Test | Cases | Expected |
|---|---|---|
| `test_price_band_matches_training` | 0, 0.01, 49.99, 50, 50.01, 99.99, 100, 200, 490.9, 500, 501 | Same label as training for every in-range value; explicit error/clamp for out-of-range; no `IndexError` |
| `test_duration_bucket_matches_training` | 1, 10, 10.01, 25, 50, 200, 201 | Same label as training; no index error |
| `test_rating_tier` | 1.0, 2.99, 3.0, 3.99, 4.0, 4.49, 4.5, 5.0 | Elite/High/Medium/Low exactly as training |
| `test_experience_bucket` | 0, 2, 2.1, 5, 5.1, 10, 10.1, 30 | Junior/Mid/Senior/Expert exactly as training |
| `test_teacher_rating_score` | 1.05, 3.0, 4.0, 4.97, 1.0, 5.0 | Uses the training normalization (dataset min/max), not a hardcoded 1–5, or the training code is changed to the same fixed range |
| `test_expertise_match` | matching, non-matching, unknown | Correct 0/1 and no hardcoded 1 |
| `test_seasonality` | Q1–Q4 | NewYearRush/Spring/Summer/YearEnd |
| `test_input_row_schema` | a full valid input | Exact expected columns, order, dtypes |

### 3.2 Prediction wrappers

| Test | Cases | Expected |
|---|---|---|
| `test_predict_revenue_missing_model` | no artifact | `(None, message)`, no exception |
| `test_predict_enrollment_missing_model` | no artifact | `(None, message)` |
| `test_predict_clamps_negative_revenue` | model returns negative | prediction >= 0 |
| `test_predict_enrollment_minimum` | model returns 0.2 | prediction >= 1 |
| `test_predict_does_not_reload_model_per_call` | monkeypatch loader | loader called once per cached resource, or document per-call behavior |
| `test_predict_response_includes_feature_row` | valid input | feature row available for audit (new behavior) |

### 3.3 Metrics and evaluation

| Test | Cases | Expected |
|---|---|---|
| `test_mae_rmse_r2_known_values` | hand-computed fixture | Exact expected metrics |
| `test_selection_uses_validation_only` | fake results | Test set never passed to selector |
| `test_baseline_comparison` | constant predictor vs model | Baseline reported |
| `test_metadata_persisted` | train a tiny model | Metadata contains data hash, versions, metrics, target |
| `test_no_test_set_reuse` | instrument split | Final test evaluation occurs once |

### 3.4 Data quality and schema

| Test | Cases | Expected |
|---|---|---|
| `test_required_sheets` | missing sheet | clear validation error |
| `test_required_columns` | missing column | clear validation error |
| `test_paid_price_threshold` | paid price < $1 | flagged |
| `test_paid_amount_consistency` | paid with Amount 0 / free with Amount > 0 | flagged |
| `test_duplicate_course_names` | duplicate name | flagged |
| `test_zero_revenue_category` | all-free category | flagged as anomaly, not silently ranked |
| `test_invalid_date` | unparseable date | clear error |
| `test_negative_price` | negative | rejected |

### 3.5 Report facts

| Test | Expected |
|---|---|
| `test_free_paid_share` | recomputed share matches generated report (currently 64.03% / 35.97% for the checked-in data) |
| `test_top3_categories` | report lists AI, Business, Project Management for the current data |
| `test_ml_revenue` | report does not claim ML leadership; value $133.38 is reflected |
| `test_no_production_ready_claim` | README/report status text is present and accurate |

These tests should read generated facts (e.g., `reports/facts.json`) rather than hardcoding prose.

### 3.6 Teacher aggregation

| Test | Expected |
|---|---|
| `test_shuffle_invariance` | Shuffling transaction rows produces identical course-level teacher features |
| `test_teacher_weighting` | Weighted/primary-teacher definition is applied deterministically |
| `test_no_first_on_arbitrary_columns` | `first`/median on transaction fields is not used for course-level modeling (or is explicitly justified) |

---

## 4. Integration Tests

### 4.1 Pipeline smoke test

- Use a tiny 4-sheet workbook fixture (~20 transactions, 3 courses, 2 teachers, 3 users) and a temporary output directory.
- Run preprocessing → feature engineering → EDA (headless) → training → evaluation → forecasting (Prophet optional; use a stub or skip marker).
- Assert:
  - expected files exist,
  - schema matches the contract,
  - no exceptions,
  - reports are generated,
  - models load and predict.

This test should **not** use the checked-in `data/processed_data.csv` or overwrite `models/`.

### 4.2 Idempotency

- Copy `data/processed_data.csv` to a temp directory.
- Run feature engineering twice.
- Assert identical column set, row count, and values (hash).
- Assert no `_x`/`_y` suffixes.

### 4.3 Artifact contract

- Load each saved model in a temp environment.
- Assert:
  - expected pipeline steps,
  - expected input columns (from metadata or a schema),
  - prediction shape and type,
  - no version mismatch (or a clear warning).
- Add a fixture that simulates an incompatible model and assert a friendly error.

### 4.4 Missing artifacts

- Start the app with a temp directory missing:
  - `processed_data.csv`,
  - revenue model,
  - enrollment model,
  - forecast results.
- Assert a friendly message with the pipeline command and no unhandled exception.

### 4.5 Forecast

- On a fixture with a known seasonal pattern:
  - assert backtest metrics are computed,
  - assert seasonal-naive baseline is present,
  - assert `forecast_results.pkl` includes source (`prophet`/`arima`), training window, horizon, metrics, and timestamp,
  - assert <24 months disables/qualifies yearly seasonality.

### 4.6 Report generation

- Generate `reports/facts.json` and the executive summary from the fixture.
- Assert the text/tables match the fixture facts.
- Assert the generator fails if a required fact is missing.

---

## 5. End-to-End / Dashboard Tests

Use `streamlit.testing.v1.AppTest` (available in modern Streamlit) to run the app headlessly.

| Test | Steps | Expected |
|---|---|---|
| `test_all_pages_render` | select each sidebar option | no exception; expected headers present |
| `test_executive_kpis` | default page | KPI values match computed fixture facts |
| `test_prediction_default` | submit default form | revenue/enrollment cards appear |
| `test_prediction_price_500` | set price 500, submit | no exception; validation or valid prediction |
| `test_prediction_price_400_sensitivity` | set price 400, submit | no exception (currently crashes) |
| `test_prediction_inputs_matter` | change course type/rating/payment | prediction changes or documented "not used" message |
| `test_feature_importance_revenue` | select Revenue Prediction | no warning dead-end; importances or a clear fallback |
| `test_feature_importance_enrollment` | select Enrollment Prediction | importances render |
| `test_shap_disabled_for_linear` | revenue model | no `TreeExplainer` crash; fallback message |
| `test_forecast_missing` | no forecast artifact | info message, no crash |
| `test_forecast_present` | fixture forecast | chart and table render |
| `test_missing_csv` | no CSV | friendly error |
| `test_category_analytics` | select category with data and empty category | KPIs/table or empty state |

Avoid snapshot-testing Plotly internals; assert on presence of chart/table elements and key text.

---

## 6. Critical Edge Cases

### Data

- Empty dataset / zero rows.
- Single month of history.
- Category with no paid rows (Marketing).
- Paid course with price below $1 (CR00028 at $0.78).
- Duplicate course names.
- Missing/NaN numeric and categorical columns.
- Unknown category/level/payment value.
- Negative price, zero duration, price > 500.
- Duplicate transaction IDs (should be rejected).
- All-null column during imputation.
- Excel sheet missing or renamed.
- Excel date stored as serial vs string.

### Model

- Model artifact missing/corrupt/incompatible.
- Model returns negative revenue or zero enrollments.
- Linear model with no `feature_importances_`.
- Tree model with SHAP shape mismatch.
- Unknown category handled by `OneHotEncoder(handle_unknown='ignore')`.
- Feature list mismatch between artifact and app.

### Forecast

- Fewer than 2 annual cycles.
- Zero-revenue months.
- Category with sparse/zero months.
- Prophet unavailable (ImportError).
- ARIMA fallback failure.
- Forecast file present but stale relative to data.

### UI

- No artifacts (first run).
- Price 500 and sensitivity >=400.
- Free vs paid course.
- Empty category.
- Long course/category names.
- Narrow viewport / mobile (manual check).
- Keyboard navigation and screen-reader labels (manual/axe).

---

## 7. Regression Tests for Confirmed Findings

Each confirmed finding should have a test that fails before the fix and passes after.

| Finding | Regression test | Assertion |
|---|---|---|
| F-01 | `test_f01_revenue_identity.py` | The model does not use a target-deterministic feature; a free course does not get a positive amount; a held-out period metric is reported with a baseline. |
| F-02 | `test_f02_price_optimum.py` | The UI does not call a price "optimal" from a monotonic identity; if a demand model exists, expected revenue uses price × demand. |
| F-03 | `test_f03_inputs_used.py` | Changing course type/rating/payment changes the feature row/prediction as expected; no silent defaults. |
| F-04 | `test_f04_price_bounds.py` | Price 0/50/100/200/500/501 and sensitivity up to price+100 never raise; boundary labels match training. |
| F-05 | `test_f05_enrollment_signal.py` | The model is compared to a mean baseline; if it does not beat it, the UI shows "insufficient signal"; intervals are present. |
| F-06 | `test_f06_report_facts.py` | Generated facts match data; no claim contradicts free share/top categories/readiness. |
| F-07 | `test_f07_split_protocol.py` | Selection/tuning never sees the test set; final metrics are evaluated once. |
| F-08 | `test_f08_teacher_aggregation.py` | Shuffling rows does not change course-level teacher features; aggregation is documented. |
| F-09 | `test_f09_explainability.py` | Both model choices render; linear model uses a linear/permutation explainer; no `TreeExplainer` on linear. |
| F-10 | `test_f10_point_in_time.py` | No feature timestamp exceeds the prediction cutoff. |
| F-11 | `test_f11_missing_artifacts.py` | Friendly error, no stack trace. |
| F-12 | `test_f12_idempotency.py` | Two runs produce identical schema/values; no `_x/_y`. |
| F-13 | `test_f13_schema.py` | Missing sheet/column/dtype fails with a clear message. |
| F-14 | `test_f14_error_handling.py` | ImportError vs data error handled differently; forecast status persisted; no global warning filter. |
| F-15 | `test_f15_caching.py` | Model loader called once; sensitivity predictions batched. |
| F-16 | `test_f16_forecast_backtest.py` | Baseline/metrics/persistence/min-history behavior verified. |
| F-17 | `test_f17_reproducibility.py` | Lockfile install + model load + metadata schema. |
| F-18 | `test_f18_no_pii_in_artifacts.py` | Generated artifacts/reports contain no email/name columns. |
| F-19 | `test_f19_labels.py` | "Profitability" is not claimed without costs; growth period is explicit. |
| F-20 | `test_f20_anomalies.py` | $0.78 paid course, zero-revenue category, duplicate names are flagged. |
| F-21 | `test_f21_no_duplication.py` | Training/inference use the same feature builder; dead code check. |
| F-22 | `test_f22_auth.py` (conditional) | If deployed, unauthenticated access is denied. |
| F-23 | CI itself | Lint, type, test, smoke pipeline pass on clean checkout. |
| F-24 | `test_f24_artifact_integrity.py` | Tampered artifact is rejected. |
| F-25 | `test_f25_html_escaping.py` | Data-derived strings are escaped or rendered natively. |
| F-26 | repo check | No Zone.Identifier/bytecode; LICENSE/.gitignore present. |
| F-27 | `test_f27_deprecations.py` | Supported Streamlit/sklearn APIs; no deprecation warnings in CI. |

---

## 8. Safe Commands

### 8.1 Current state (no dependencies installed)

Read-only checks that are safe:

```bash
# Syntax check without writing bytecode or modifying files
python3 - <<'PY'
import ast, glob
for p in sorted(glob.glob('**/*.py', recursive=True)):
    ast.parse(open(p, encoding='utf-8').read(), filename=p)
    print('OK', p)
PY

# Read-only data facts
python3 - <<'PY'
import csv
rows = list(csv.DictReader(open('data/processed_data.csv', encoding='utf-8-sig')))
print('rows', len(rows))
print('free', sum(1 for r in rows if float(r['Amount']) == 0))
PY
```

### 8.2 After adding test dependencies (recommended)

Do this in a disposable virtual environment or container, not against production data:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov  # Streamlit AppTest ships with streamlit
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/e2e -q
python -m pytest --cov=edup --cov-report=term-missing
```

### 8.3 Running the pipeline safely

The pipeline rewrites `data/processed_data.csv`, `models/*.pkl`, and `reports/*.png`. To test it without touching the repository:

```bash
tmp=$(mktemp -d)
cp -r data notebooks app models reports run_pipeline.py requirements.txt "$tmp"/
# run inside the temp copy, with a fixture or the copied data
cd "$tmp" && python run_pipeline.py
```

Do **not** run `python run_pipeline.py` in the repository during a code review unless you intend to regenerate artifacts.

### 8.4 Running the dashboard safely

```bash
streamlit run app/app.py
```

For automated UI tests, use `streamlit.testing.v1.AppTest` rather than Selenium where possible. If a browser test is required, use a disposable container and a temporary data directory.

### 8.5 Do not run

- `pip install` into the system Python without a venv.
- Any command that deletes/overwrites `data/`, `models/`, or `reports/`.
- Unpickling model files from untrusted sources.
- Security scans against external systems.
- Load tests against a shared/production deployment.

---

## 9. CI/CD Recommendations

### 9.1 Minimal CI pipeline

```yaml
# .github/workflows/ci.yml (conceptual)
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.lock
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy edup
      - run: pytest tests/unit tests/integration -q
      - run: pytest tests/e2e -q
      - run: python -m edup.pipeline --fixture tests/fixtures/edup_small.xlsx --output /tmp/edup
```

### 9.2 Quality gates

- Unit + integration tests must pass.
- E2E/AppTest must pass.
- Lint/type check must pass.
- Pipeline smoke test must pass on the fixture.
- Report fact tests must pass.
- Dependency lockfile must be unchanged unless intentionally updated.
- Optional: coverage threshold on changed files (start at 60–70%, increase over time).

### 9.3 Nightly / scheduled

- Backtest the forecast on a rolling window.
- Check model artifact loadability against the locked environment.
- Run data-quality checks on any refreshed data.
- Compare generated report facts to the previous run and alert on unexpected changes.

---

## 10. Acceptance Criteria for Major Fixes

### F-01 revenue target

- A written target definition and horizon exist.
- No feature is a deterministic function of the target.
- Baseline metrics are reported.
- Final metrics come from a held-out period/course set.
- The dashboard labels the unit and horizon.

### F-02 pricing

- The UI does not claim an "optimal price" from the current identity model.
- If a demand model exists, expected revenue uses price × predicted demand and includes uncertainty.
- A controlled experiment plan exists before any pricing recommendation is operationalized.

### F-03/F-04 inference

- Every form input is either passed to the model or explicitly marked "not used".
- Price 0/50/100/200/500/501 and sensitivity ranges never crash.
- Training/inference parity tests pass for all boundary values.

### F-05 enrollment

- Target has documented variance and a horizon.
- The model is compared to a mean/seasonal baseline.
- Prediction intervals are shown.
- A low-signal state is visible in the UI.

### F-06 reports

- All numeric claims are generated from data or asserted.
- Free/paid share, top categories, and readiness statements are correct.
- Forecast claims are labeled as model output.

### F-07 evaluation

- Selection/tuning uses validation/CV only.
- The test set is evaluated once.
- Metrics are persisted with the model.

### F-08 teacher model

- The course–teacher relationship is documented.
- Aggregation is deterministic and shuffle-invariant.
- No arbitrary `first`/median transaction fields for course-level features.

### F-09 explainability

- Both model choices render.
- Linear models use a linear/permutation explainer.
- A missing-importance state is informative.

### F-11/F-12/F-13 reliability

- Missing artifacts produce a friendly message.
- Feature engineering is idempotent.
- Schema violations fail early with actionable errors.

### F-16 forecast

- Backtest metrics and a seasonal-naive baseline are reported.
- Results carry source/training window/horizon/metadata.
- Enrollment forecasts are displayed or the claim is removed.

### F-17/F-23 reproducibility and CI

- Clean-environment install reproduces the environment.
- Model metadata is present and verified.
- CI runs lint/type/tests/pipeline smoke.
- No unreviewed dependency drift.

---

## 11. Test Data and Fixtures

### 11.1 Small fixture workbook

Create `tests/fixtures/edup_small.xlsx` with the four sheets and a deliberately small but representative dataset:

- 3 users, 2 teachers, 3 courses (one free, one paid normal, one paid at $0.78 to exercise the anomaly rule).
- ~12 transactions across 3 months, including a zero-revenue category.
- One duplicate course name to exercise the quality rule.
- One transaction with a boundary price ($50) and one with $500 to exercise binning.

Do not include real names/emails in the fixture. Use synthetic identifiers.

### 11.2 Deterministic dates

Use fixed dates (e.g., 2025-01-15) and avoid `today()` in tests. For forecast tests, use a fixture with at least 24 monthly points when testing yearly seasonality, plus a shorter fixture for the minimum-history guard.

### 11.3 Model fixtures

Generate linear and tree pipelines inside a fixture with a tiny dataset rather than committing binary pickles. This keeps tests portable and avoids pickle trust issues. If committed artifacts are tested, verify checksums and mark them as integration-only.

### 11.4 Golden facts

Generate `reports/facts.json` from the small fixture and use it in report tests. For the full checked-in data, keep a separate `tests/fixtures/full_facts.json` only for the documented headline values, and update it intentionally when the data changes.

---

## 12. Manual QA Checklist

Automated tests cannot cover everything. Before a demo/release:

- [ ] Open every dashboard page on desktop and a narrow viewport.
- [ ] Submit the prediction form with free and paid courses, price 0/50/100/200/500.
- [ ] Change every form field and confirm the output or the "not used" note.
- [ ] Open Feature Importance for both model choices.
- [ ] Open Revenue Forecasting with and without `forecast_results.pkl`.
- [ ] Select a category with and without paid revenue.
- [ ] Verify the executive KPI values against a quick data query.
- [ ] Check that no report number contradicts the dashboard.
- [ ] Check keyboard navigation and screen-reader labels on the main controls.
- [ ] Confirm the app is not publicly reachable unless intended.

---

## 13. Summary

EDUPRO currently has **zero automated tests**. The most valuable additions, in order, are:

1. feature binning/input-builder parity tests (catches F-03/F-04),
2. report-fact tests (catches F-06/F-20),
3. AppTest smoke tests for every page and both model selections (catches F-09/F-11),
4. pipeline idempotency and schema tests (catches F-12/F-13),
5. leakage/evaluation tests (catches F-01/F-07/F-10),
6. forecast backtest tests (catches F-16),
7. reproducibility/artifact-integrity tests (catches F-17/F-24).

A small suite of these tests, run in CI, would have prevented every High/P1 defect found in this audit.
