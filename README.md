# EduPro Predictive Analytics Platform

## Predictive Modeling for Course Demand and Revenue Forecasting

---

## Project Overview

This project is a research/demo analytics platform for EduPro, an online education marketplace. It ingests multi-sheet relational data and provides data-verified portfolio facts, a historical enrollment reference, and transparent price what-if scenarios, alongside cached Prophet output. **It is not production-ready**: revenue prediction is retired because the original target is an accounting identity, and the enrollment model does not beat a mean baseline. All outputs are surfaced through a multi-page Streamlit dashboard.

---

## Current Project Stage

**Completed: Phases 1–3 (Architecture & Correctness) + R3.3–R3.5, R3.4 CI, R4.1–R4.6**

| Phase | Status | Focus | Key Outcomes |
|-------|--------|-------|--------------|
| **Phase 1** | Complete | Critical bugs & correctness | Retired leakage revenue model; fixed price-500 crash; removed invalid "optimal price"; corrected form inputs; fixed reporting contradictions (free=64.03%, top categories AI/Business/PM, ML=$133.38, Marketing=$0) |
| **Phase 2** | Complete | Reliability & testing | 247 automated tests; strong data contracts; train/serve parity verified; dashboard handles missing/corrupt artifacts gracefully |
| **Phase 3** | Complete | Architecture & code quality | Shared `src/edup/` package (config, schema, features, analytics, data, models, forecasting, reporting); dead code removed; typed exceptions; all tests pass |
| **R3.3** | Complete | Code quality & observability | Type hints on public APIs; Ruff/Mypy clean; structured logging; exception taxonomy |
| **R3.4** | Complete | Continuous Integration | GitHub Actions CI on push/PR; Python 3.12; dependency caching; 296 tests pass |
| **R3.5** | Complete | Dependency reproducibility & model metadata | Pinned deps (`requirements.lock`); `pyproject.toml`; model metadata JSON for all artifacts |
| **R4.1–R4.2** | Complete | Performance | Model caching (`st.cache_resource`); dashboard computation caching |
| **R4.3** | Complete | Data loading | Parquet-first with CSV fallback |
| **R4.4** | Complete | Enrollment Prediction API | FastAPI REST API with health, model-info, and prediction endpoints; 60 API tests; Swagger at `/docs` |
| **R4.5** | Complete | Model Retraining & Registry | Automated retraining, registry lifecycle, promotion/rollback, scheduled workflows |
| **R4.6** | Complete | Production Readiness | Auth, rate limiting, CORS, structured logging, health checks, Docker, CI hardening |

**The platform is now a well-tested, architecturally sound research prototype with CI, reproducible dependencies, model metadata, a REST API, automated retraining, and production-grade security/observability.**  
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
│   ├── processed_data.csv            # Feature-engineered dataset (CSV fallback)
│   └── processed_data.parquet        # Feature-engineered dataset (Parquet preferred)
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
│   ├── app/                          # Thin dashboard utilities
│   └── api/                          # FastAPI REST API (R4.4)
├── app/
│   ├── app.py                        # Streamlit multi-page dashboard
│   └── utils.py                      # Backward-compatible facade to src/edup
├── reports/
│   ├── executive_summary.md          # Business stakeholder summary
│   ├── research_paper.md             # Academic-style technical report
│   └── *.png                         # EDA and evaluation charts
├── tests/                            # 381 automated tests (321 core + 60 API)
├── run_pipeline.py                   # One-command full pipeline runner
├── pyproject.toml                    # Project config, dependencies, tool settings
├── requirements.lock                 # Fully pinned dependencies (runtime + test)
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
- Python 3.12 or higher (project requires `>=3.12`)
- pip

### Setup

```bash
# 1. Clone or download the project
cd EduPro-Predictive-Modeling

# 2. (Optional) Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 3. Install dependencies — choose one approach:

# Option A: Reproducible environment (recommended for CI, deployment, exact reproducibility)
# Uses the fully pinned lock file containing all runtime + test dependencies.
pip install -r requirements.lock

# Option B: Editable development installation
# Installs the package in development mode from pyproject.toml.
# For running tests, also install the dev dependencies:
pip install -e .[dev]

# 4. Ensure the raw data file is in place
# data/EduPro_Online_Platform.xlsx should already be present
```

**When to use which:**
- **`pip install -r requirements.lock`** — CI pipelines, production deployments, exact environment reproduction, and when you want a single command that includes everything (runtime + pytest).
- **`pip install -e .[dev]`** — Local development when you want to edit `src/edup/` code and have changes immediately available, plus access to `pytest`, `ruff`, `mypy` via the dev extras.

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
| API Framework | FastAPI, Uvicorn |
| Persistence | joblib |
| CI / Lint / Type Check | GitHub Actions, Ruff, Mypy, pytest |
| Dependency Management | pip, `pyproject.toml`, `requirements.lock` |

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

## Enrollment Prediction API (R4.4)

The EduPro Enrollment Prediction API provides a REST interface for programmatic access to enrollment predictions, model health, and model metadata.

### Installation

The API dependencies are included in the main installation:

```bash
# Using lock file (recommended)
pip install -r requirements.lock

# Or using editable install with dev dependencies
pip install -e .[dev]
```

### Local Startup

```bash
# Start the API server with Uvicorn
uvicorn edup.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API Base**: `http://localhost:8000`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### Endpoints

#### GET /health

Returns API status, model availability, and model identity/version. Does not reload the model.

**Response:**
```json
{
  "status": "healthy",
  "model_available": true,
  "model_name": "enrollment_model_phase1",
  "model_version": "enrollment_model_phase1.pkl"
}
```

**Status values:** `healthy` (model loaded), `degraded` (model not available)

---

#### GET /model-info

Returns safe model information: name, type, version, features, training metadata, and status. Never exposes filesystem paths, secrets, or sensitive internal information.

**Response:**
```json
{
  "model_name": "enrollment_model_phase1",
  "model_type": "RandomForest (Pipeline with ColumnTransformer + OneHotEncoder + StandardScaler)",
  "model_version": "enrollment_model_phase1.pkl",
  "status": "active",
  "feature_names": [
    "CoursePrice",
    "CourseDuration",
    "CourseRating",
    "TeacherRating",
    "YearsOfExperience",
    "EncodedCourseLevel",
    "TeacherRatingScore",
    "CourseCategory",
    "CourseType",
    "PriceBand",
    "DurationBucket",
    "RatingTier",
    "ExperienceBucket"
  ],
  "target_variable": "EnrollmentCount (course-level)",
  "training_date_utc": "2026-11-20T08:00:47.503256+00:00",
  "metrics": {
    "baseline_cv_rmse": 12.27,
    "selected_cv_rmse": 13.05,
    "selected_test": {"MAE": 11.46, "RMSE": 14.07, "R2": -0.09}
  },
  "notes": "Phase 1 enrollment model trained with course-level features only..."
}
```

**Error (503):** Model not available.

---

#### POST /predict/enrollment

Predicts enrollment for a course configuration using the canonical feature engineering shared with the Streamlit dashboard.

**Request:**
```json
{
  "course_category": "Programming",
  "course_level": "Beginner",
  "course_price": 99.0,
  "course_duration": 20.0,
  "teacher_experience": 5.0,
  "teacher_rating": 4.0,
  "course_type": "Paid",
  "course_rating": 4.0,
  "payment_method": "Credit Card"
}
```

**Required fields:** `course_category`, `course_level`, `course_price`, `course_duration`, `teacher_experience`, `teacher_rating`

**Optional fields:** `course_type` (default: "Paid"), `course_rating` (default: 4.0), `payment_method` (default: "Credit Card")

**Validation:**
- `course_category`: Must be one of 12 valid categories
- `course_level`: Must be "Beginner", "Intermediate", or "Advanced"
- `course_type`: Must be "Paid" or "Free"
- `payment_method`: Must be "Credit Card", "PayPal", or "Bank Transfer"
- `course_price`: 0–500 (0 only allowed for Free courses)
- `course_duration`: 1–200 hours
- `course_rating` / `teacher_rating`: 1.0–5.0
- `teacher_experience`: 0–30 years
- Free courses automatically normalize price to 0; Paid courses require price > 0

**Response:**
```json
{
  "predicted_enrollment": 167.5,
  "model_name": "enrollment_model_phase1",
  "model_version": "enrollment_model_phase1.pkl",
  "features_used": [
    "CoursePrice",
    "CourseDuration",
    "CourseRating",
    "TeacherRating",
    "YearsOfExperience",
    "EncodedCourseLevel",
    "TeacherRatingScore",
    "CourseCategory",
    "CourseType",
    "PriceBand",
    "DurationBucket",
    "RatingTier",
    "ExperienceBucket"
  ]
}
```

**Errors:**
- **400**: Validation error (invalid input values, e.g., price out of bounds)
- **422**: Schema validation error (missing required fields, invalid enum values)
- **503**: Model not loaded
- **500**: Internal prediction failure

**Error response format:**
```json
{
  "error": "ValidationError",
  "message": "Course price must be between $0 and $500; got 600.00.",
  "details": {"field": "request_body"}
}
```

---

### Example Prediction Request (cURL)

```bash
curl -X POST "http://localhost:8000/predict/enrollment" \
  -H "Content-Type: application/json" \
  -d '{
    "course_category": "Programming",
    "course_level": "Beginner",
    "course_price": 99.0,
    "course_duration": 20.0,
    "teacher_experience": 5.0,
    "teacher_rating": 4.0,
    "course_type": "Paid",
    "course_rating": 4.0,
    "payment_method": "Credit Card"
  }'
```

### Example Response

```json
{
  "predicted_enrollment": 167.5,
  "model_name": "enrollment_model_phase1",
  "model_version": "enrollment_model_phase1.pkl",
  "features_used": [
    "CoursePrice",
    "CourseDuration",
    "CourseRating",
    "TeacherRating",
    "YearsOfExperience",
    "EncodedCourseLevel",
    "TeacherRatingScore",
    "CourseCategory",
    "CourseType",
    "PriceBand",
    "DurationBucket",
    "RatingTier",
    "ExperienceBucket"
  ]
}
```

### Error Response Examples

**Missing required field (422):**
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "course_price"],
      "msg": "Field required",
      "input": {"course_category": "Programming", "course_level": "Beginner"}
    }
  ]
}
```

**Invalid value (400):**
```json
{
  "error": "ValidationError",
  "message": "course_price must be between $0 and $500; got 600.00.",
  "details": {"field": "request_body"}
}
```

**Model unavailable (503):**
```json
{
  "error": "HTTPException",
  "message": "Enrollment model not loaded. Check model artifacts and server logs.",
  "details": {"status_code": 503}
}
```

**Internal error (500):**
```json
{
  "error": "InternalServerError",
  "message": "An unexpected error occurred",
  "details": null
}
```

---

### Model Lifecycle

- The model is loaded **once per API process** on startup (via FastAPI lifespan handler).
- Uses the existing model-loading and caching architecture (`load_model_with_metadata`).
- Prefers `enrollment_model_phase1.pkl` (Phase 1 model); falls back to `enrollment_model.pkl` (legacy).
- Handles missing or corrupted model artifacts gracefully (returns 503 on health/model-info, 503 on predict).
- Uses existing model metadata (`ModelMetadata` from `edup.models.metadata`).

---

### Testing

Run the API test suite:

```bash
pytest tests/test_api.py -v
```

Run all tests (381 total):

```bash
pytest tests/ -v
```

### Limitations

- The enrollment model does not beat a mean baseline on this dataset (see Model Performance Summary).
- Predictions are based on the legacy model artifact unless the Phase 1 model is trained and persisted.
- The API is for research/prototype use; production hardening (auth, rate limiting, HTTPS) is configured via environment variables.
- Feature parity with Streamlit predictions is maintained through shared `edup.features` module.

---

## Production Readiness (R4.6)

The EduPro platform includes production-grade security, observability, and deployment preparation features.

### Security Features

| Feature | Configuration | Default |
|---------|---------------|---------|
| API Key Authentication | `AUTH_ENABLED`, `API_KEYS`, `API_KEY_HEADER` | Disabled |
| Rate Limiting | `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS` | Disabled |
| CORS | `CORS_ENABLED`, `CORS_ORIGINS`, `CORS_ALLOW_CREDENTIALS` | Enabled (`*`) |
| Trusted Hosts | `TRUSTED_HOSTS_ENABLED`, `TRUSTED_HOSTS` | Disabled |
| Request Size Limit | `MAX_REQUEST_SIZE_MB` | 10 MB |

**Development:** All security features are disabled or permissive by default for local development.
**Production:** Set `ENVIRONMENT=production` — the application will fail to start if required security settings are missing.

### Observability

| Feature | Description |
|---------|-------------|
| Structured Logging | JSON format in production (`LOG_FORMAT=json`), text in development |
| Correlation IDs | `X-Correlation-ID` header propagated through request lifecycle |
| Request Timing | `X-Process-Time` header on all responses (seconds) |
| Exception Logging | Full stack traces in logs; sanitized responses to clients |

### Health Endpoints

| Endpoint | Purpose | Auth/Rate Limit |
|----------|---------|-----------------|
| `GET /health/live` | Liveness probe (process alive) | Exempt |
| `GET /health/ready` | Readiness probe (model + registry available) | Exempt |
| `GET /health` | General status + model info | Exempt |

### Configuration

All settings via environment variables or `.env` file. See `.env.example` for template.

**Key Settings:**
```bash
ENVIRONMENT=production          # development|staging|production
AUTH_ENABLED=true               # Required for production
API_KEYS=key1,key2,key3         # Required for production
RATE_LIMIT_ENABLED=true         # Required for production
TRUSTED_HOSTS_ENABLED=true      # Required for production
CORS_ORIGINS=https://app.example.com  # Required for production (not *)
LOG_FORMAT=json                 # Required for production
LOG_LEVEL=INFO                  # Not DEBUG in production
```

### Docker Deployment

```bash
# Build
docker build -t edupro-api .

# Run (production)
docker run -d -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e AUTH_ENABLED=true \
  -e API_KEYS="<secure-keys>" \
  -e RATE_LIMIT_ENABLED=true \
  -e CORS_ORIGINS="https://yourdomain.com" \
  -e TRUSTED_HOSTS_ENABLED=true \
  -e LOG_FORMAT=json \
  -v /persistent/models:/app/models \
  -v /persistent/data:/app/data:ro \
  edupro-api
```

### Docker Compose

```bash
# Development
docker-compose up

# Production (create docker-compose.prod.yml with production overrides)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
```

### Model Persistence

Mount `/app/models` and `/app/data` to persistent storage. The model registry at `/app/models/registry` must survive container restarts.

### CI/CD

GitHub Actions workflows:
- **CI** (`ci.yml`): Test, lint (Ruff), typecheck (Mypy), Docker build validation
- **Retraining** (`retrain.yml`): Weekly scheduled retraining, manual dispatch, candidate validation

### Testing

```bash
# All tests (454)
pytest tests/ -v

# Security tests
pytest tests/test_api_security.py -v

# Lint
ruff check src/

# Type check
mypy src/
```

### Production Deployment Checklist

- [ ] `ENVIRONMENT=production`
- [ ] `AUTH_ENABLED=true` with secure `API_KEYS`
- [ ] `RATE_LIMIT_ENABLED=true` with appropriate limits
- [ ] `TRUSTED_HOSTS_ENABLED=true` with API domain
- [ ] `CORS_ORIGINS` set to frontend domain(s)
- [ ] `LOG_FORMAT=json`, `LOG_LEVEL=INFO`
- [ ] TLS termination at load balancer
- [ ] Persistent volumes for models/registry
- [ ] Model trained, validated, promoted to active
- [ ] `/health/ready` returns 200 with all checks passing
- [ ] Monitoring/alerts on health endpoints
- [ ] Log aggregation configured
- [ ] Retraining workflow scheduled

### Known Limitations

- In-memory rate limiting (single replica); use Redis for clustered deployments
- No built-in API key rotation; implement external key management
- No audit logging; add middleware if required for compliance
- HTTPS termination required at infrastructure layer

---

## R4.6 Documentation

- `audit/R4.6_PRODUCTION_READINESS_ASSESSMENT.md` — Initial gap analysis
- `audit/R4.6_IMPLEMENTATION_REPORT.md` — Detailed implementation documentation
- `audit/R4.6_FINAL_ACCEPTANCE_REPORT.md` — Validation evidence and sign-off

