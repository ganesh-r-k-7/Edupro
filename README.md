# EduPro Predictive Analytics Platform

## Predictive Modeling for Course Demand and Revenue Forecasting

---

## Project Overview

This project is a research/demo analytics platform for EduPro, an online education marketplace. It ingests multi-sheet relational data and provides data-verified portfolio facts, a historical enrollment reference, and transparent price what-if scenarios, alongside cached Prophet output. **It is not production-ready**: revenue prediction is retired because the original target is an accounting identity, and the enrollment model does not beat a mean baseline. All outputs are surfaced through a multi-page Streamlit dashboard.

---

## Current Project Stage

**Completed: Phases 1–3 (Architecture & Correctness)**

| Phase | Status | Focus | Key Outcomes |
|-------|--------|-------|--------------|
| **Phase 1** | ✅ Complete | Critical bugs & correctness | Retired leakage revenue model; fixed price-500 crash; removed invalid "optimal price"; corrected form inputs; fixed reporting contradictions (free=64.03%, top categories AI/Business/PM, ML=$133.38, Marketing=$0) |
| **Phase 2** | ✅ Complete | Reliability & testing | 247 automated tests; strong data contracts; train/serve parity verified; dashboard handles missing/corrupt artifacts gracefully |
| **Phase 3** | ✅ Complete | Architecture & code quality | Shared `src/edup/` package (config, schema, features, analytics, data, models, forecasting, reporting); dead code removed; typed exceptions; all 247 tests pass |

**The platform is now a well-tested, architecturally sound research prototype.**  
It does **not** have a validated demand or revenue model—the data does not support one.

---

## Business Problem

EduPro operates 60 courses across 12 categories with 60 instructors and 3,000 registered users. This project explores whether the available data can support data-driven decisions about:

- Revenue and demand forecasting
- Instructor capacity planning
- Course pricing
- New course launch planning

---

## Dataset

The source file `data/EduPro_Online_Platform.xlsx` contains four sheets:

| Sheet | Records | Description |
|-------|---------|-------------|
| Users | 3,000 | User demographics |
| Teachers | 60 | Instructor profiles and ratings |
| Courses | 60 | Course metadata and pricing |
| Transactions | 10,000 | Enrollment and payment records |

---

## Project Architecture

```
EduPro-Predictive-Modeling/
├── data/
│   ├── EduPro_Online_Platform.xlsx   # Raw data
│   └── processed_data.csv            # Feature-engineered dataset
├── notebooks/
│   ├── 01_data_preprocessing.py      # Data merging, cleaning, encoding
│   ├── 02_eda.py                     # Exploratory visualizations
│   ├── 03_feature_engineering.py     # Engineered feature generation
│   ├── 04_model_training.py          # ML model training and tuning
│   ├── 05_model_evaluation.py        # Metrics, plots, comparison
│   └── 06_forecasting.py             # Prophet time-series forecasting
├── models/
│   ├── enrollment_model.pkl          # Legacy artifact (not used)
│   ├── revenue_model.pkl             # Legacy artifact (not used)
│   ├── preprocessing_pipeline.pkl    # Fitted ColumnTransformer
│   └── forecast_results.pkl          # Saved Prophet forecast outputs
├── src/edup/                         # Shared package (Phase 3)
│   ├── config.py                     # Paths, constants, feature lists, binning edges
│   ├── schema.py                     # Data contracts (sheets, processed, forecast)
│   ├── exceptions.py                 # Typed exception hierarchy
│   ├── features/                     # Shared feature engineering (train/serve parity)
│   ├── analytics/                    # Business facts, KPIs, pricing scenarios
│   ├── data/                         # Loading, preprocessing, validation
│   ├── models/                       # Training, evaluation, prediction
│   ├── forecasting/                  # Prophet/ARIMA, backtest, validation
│   ├── reporting/                    # Executive summary, research paper generation
│   └── app/                          # Thin dashboard utilities
├── app/
│   ├── app.py                        # Streamlit multi-page dashboard
│   └── utils.py                      # Backward-compatible facade to src/edup
├── reports/
│   ├── executive_summary.md          # Business stakeholder summary
│   ├── research_paper.md             # Academic-style technical report
│   └── *.png                         # EDA and evaluation charts
├── tests/                            # 247 automated tests
├── run_pipeline.py                   # One-command full pipeline runner
├── requirements.txt                  # Python dependencies
└── README.md                         # This file
```

---

## ML Workflow

```
Raw Excel Data
     |
     v
[01] Data Preprocessing
     Merge 4 sheets -> Fix dtypes -> Handle missing values -> Outlier analysis
     |
     v
[03] Feature Engineering
     PriceBand, DurationBucket, RatingTier, EncodedCourseLevel
     ExperienceBucket, TeacherRatingScore, ExpertiseCategoryMatch
     Month, Quarter, Year, IsWeekend, SeasonalityLabel
     EnrollmentCount, TotalRevenue, RollingRevenueAverage, RevenueGrowthRate
     |
     v
[04] Model Training
     Course-level feature contract
     Compare candidates with a mean baseline using training-only CV
     Single final test evaluation; no model persisted if worse
     |
     v
[05] Model Evaluation
     Metrics, validation status, and baseline comparison
     |
     v
[06] Forecasting
     Prophet (multiplicative seasonality)
     6-month revenue + enrollment projections
     Category-level revenue trends
```

---

## Streamlit Dashboard Pages

| Page | Content |
|------|---------|
| Executive Dashboard | KPI cards, revenue trends, enrollment by category, payment analysis |
| Course Demand Prediction | Historical enrollment reference with transparent price scenarios; not a personalized prediction |
| Revenue Forecasting | Historical monthly revenue, cached unbacktested Prophet output, and first-to-last category growth |
| Feature Importance Explorer | Model-validity status, data-verified facts, descriptive enrollment associations |
| Category Analytics | Revenue-efficiency matrix, teacher associations, and course-level breakdown; no cost or profit data |

---

## Installation

### Prerequisites
- Python 3.9 or higher
- pip

### Setup

```bash
# 1. Clone or download the project
cd EduPro-Predictive-Modeling

# 2. (Optional) Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Ensure the raw data file is in place
# data/EduPro_Online_Platform.xlsx should already be present
```

---

## Usage

### Step 1: Run the Full Pipeline

```bash
python run_pipeline.py
```

This executes all preprocessing, feature engineering, EDA, model training, evaluation, and forecasting steps in sequence. It can overwrite checked-in data, model, and report artifacts; back them up first. Charts are saved to `reports/`.

### Step 2: Launch the Dashboard

```bash
streamlit run app/app.py
```

Open your browser at `http://localhost:8501`.

---

## Running Individual Steps

```bash
# Preprocessing only
python notebooks/01_data_preprocessing.py

# EDA only
python notebooks/02_eda.py

# Feature engineering
python notebooks/03_feature_engineering.py

# Model training
python notebooks/04_model_training.py

# Evaluation
python notebooks/05_model_evaluation.py

# Forecasting
python notebooks/06_forecasting.py
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Data Processing | pandas, NumPy |
| Machine Learning | scikit-learn, XGBoost |
| Explainability | Model-aware SHAP helper (disabled until a model is validated) |
| Forecasting | Prophet |
| Visualization | Plotly, Matplotlib, Seaborn |
| Dashboard | Streamlit |
| Persistence | joblib |

---

## Model Performance Summary

### Revenue Target (Retired)
The original revenue model predicted transaction `Amount` using `CoursePrice` as a feature. In this dataset, `Amount == CoursePrice` for every paid transaction and `Amount == 0` for every free transaction. The reported R² = 1.0 is therefore an accounting identity / target-leakage result, not predictive skill. The legacy artifact is preserved for audit but is no longer used by the dashboard.

### Enrollment Prediction (Baseline Comparison)
The persisted legacy enrollment artifact is an `XGBRegressor` pipeline, not Random Forest. Phase 1 compares enrollment candidates with a mean baseline using training-only cross-validation and a single final test evaluation. Because course enrollment is near-uniform (140–196, CV 7.5%), the model does not beat the mean baseline. In the Phase 1 evaluation, the mean baseline achieved CV RMSE 12.27 and test RMSE 13.73; the selected Random Forest achieved CV RMSE 13.05 and test RMSE 14.07. The dashboard shows a historical reference rather than a personalized prediction. See `audit/PHASE1_IMPLEMENTATION_REPORT.md` for details.

### Revenue Forecast (Cached, Unbacktested)
The six-month Prophet output is cached model output. It has not been backtested in this project and should not be treated as a validated forecast. Specific peak-month and enrollment-range claims are not independently verified.

---

## Business Insights (Data-Verified)

1. **Top 3 revenue categories** are Artificial Intelligence ($202,750.67), Business ($181,527.58), and Project Management ($169,103.21), together 60.72% of total revenue.
2. **Free transactions are 64.03%** (6,403 of 10,000). Paid/free is determined at the course level in this dataset, so this is not a learner conversion rate.
3. **Machine Learning revenue is $133.38** (0.0146%) and **Marketing revenue is $0.00**. Do not recommend ML/Marketing as leading investment categories from this data.
4. **There is no clear Q1 peak.** Q1 had 2,456 enrollments and $231,643.16 revenue; Q2 had 2,555 and $231,406.06.
5. **Price response is not identifiable.** Each course has one observed price and there are no within-course price changes. The dashboard provides what-if scenarios, not an estimated elasticity or an optimal price.

---

## Future Phases (Roadmap)

The detailed roadmap with acceptance criteria and validation tests is in `audit/EDUPRO_IMPROVEMENT_ROADMAP.md`.

### Phase 4 — Performance and Scalability (Ready to Start)
Goal: improve responsiveness and prepare for larger data without premature complexity.

| Task | Description | Effort |
|------|-------------|--------|
| R4.1 | Cache models and batch predictions (`st.cache_resource`) | S |
| R4.2 | Cache expensive dashboard computations (KPIs, charts) | S |
| R4.3 | Move serving data to Parquet/DuckDB (when justified) | M |
| R4.4 | Add an optional prediction API (FastAPI) | M/L |
| R4.5 | Scheduled retraining and model registry | L |
| R4.6 | Add monitoring and observability | M |

### Phase 5 — Product and UX Improvements (After Phase 4)
Goal: turn the repaired analytics into a trustworthy decision-support product.

| Task | Description | Effort |
|------|-------------|--------|
| R5.1 | Show uncertainty everywhere a prediction is shown (prediction intervals) | M |
| R5.2 | Add scenario planning (base/optimistic/pessimistic) instead of single forecast | M |
| R5.3 | Generate reports from data (no hand-written numbers) | M |
| R5.4 | Add a data-quality and category health panel | M |
| R5.5 | Improve labeling, accessibility, and exports | S/M |
| R5.6 | Add onboarding and actionable error states | S |

### Phase 6 — Advanced Features (Only After Phases 1–5)
These are only justified after Phases 1–5. Do not build them on top of an invalid revenue model.

| Task | Description | Prerequisites |
|------|-------------|---------------|
| R6.1 | User-level churn/retention | Event/session/completion data; privacy review |
| R6.2 | NLP course-quality signals | Review/description corpus; labeling |
| R6.3 | Dynamic pricing / experimentation | Real demand model; A/B infrastructure |
| R6.4 | Real-time ingestion and inference | Event stream, API, auth, monitoring |
| R6.5 | MLOps maturity (registry, drift, rollback) | R3.5, R3.4, R4.5, R4.6 |

---

## What Not to Do Yet

- Do not add a database, API, or MLflow just because they are "production" keywords. The data and usage do not yet justify them.
- Do not add deep learning, NLP, or reinforcement learning on 10k synthetic transactions.
- Do not add more dashboard pages before the existing pages are correct.
- Do not tune hyperparameters further to chase R²; the target and evaluation are the problem, not the search grid.
- Do not claim an ROI percentage without a causal design and a documented baseline.

---

## Definition of Done for the Roadmap

The improvement program is successful when:

1. A user can explain what every number on every page means, in which unit, and over what horizon.
2. The revenue model is not a restatement of price, and the demand model beats a documented baseline (or the UI says it does not).
3. Training and inference use the same feature code and pass parity tests.
4. Reports are generated from the current data and cannot silently drift.
5. The pipeline is reproducible from a clean environment and covered by CI.
6. A missing artifact or failed forecast produces a clear, actionable message.
7. If deployed beyond localhost, access is authenticated and audited.

---

## Screenshots

*Dashboard screenshots to be added after local deployment.*

- Executive Dashboard: KPI cards and revenue trend charts
- Demand Prediction: Historical reference and transparent price-scenario table
- Revenue Forecasting: Cached Prophet output with confidence intervals and caveats
- Model Validity: model-status explanation and descriptive data facts
- Category Analytics: Revenue-efficiency matrix and course-level breakdown

---

## License

This project is developed for portfolio, academic, and professional showcase purposes. All data is synthetic and generated for demonstration.