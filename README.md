# EduPro Predictive Analytics Platform

## Predictive Modeling for Course Demand and Revenue Forecasting

---

## Project Overview

This project delivers a production-grade, end-to-end data science platform for EduPro, an online education marketplace. The system ingests multi-sheet relational data and produces machine learning models that predict course enrollment demand and transaction-level revenue, alongside a Prophet-based six-month revenue forecast. All outputs are surfaced through a professional multi-page Streamlit dashboard.

---

## Business Problem

EduPro operates 60 courses across 12 categories with 60 instructors and 3,000 registered users. Without predictive analytics, business decisions around pricing, instructor allocation, and course launches are reactive and suboptimal. This platform solves:

- Uncertain revenue forecasting
- Instructor capacity mismatches
- Suboptimal course pricing
- New course launch risk

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
│   ├── enrollment_model.pkl          # Trained enrollment predictor
│   ├── revenue_model.pkl             # Trained revenue predictor
│   ├── preprocessing_pipeline.pkl    # Fitted ColumnTransformer
│   └── forecast_results.pkl          # Saved Prophet forecast outputs
├── app/
│   ├── app.py                        # Streamlit multi-page dashboard
│   └── utils.py                      # Shared utilities and chart helpers
├── reports/
│   ├── executive_summary.md          # Business stakeholder summary
│   ├── research_paper.md             # Academic-style technical report
│   └── *.png                         # EDA and evaluation charts
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
     ColumnTransformer (StandardScaler + OneHotEncoder)
     Baseline: LinearRegression, Ridge, Lasso
     Advanced: RandomForest, GradientBoosting, XGBoost
     Tuning: RandomizedSearchCV (n_iter=20, cv=3)
     |
     v
[05] Model Evaluation
     MAE, RMSE, R2 | Prediction vs Actual | Residuals | Feature Importance
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
| Course Demand Prediction | Interactive form to predict revenue and enrollments for any course config |
| Revenue Forecasting | Prophet forecast charts, forecast table, category growth trends |
| Feature Importance Explorer | Feature importance bar charts, SHAP analysis, demand driver insights |
| Category Analytics | Profitability matrix, teacher performance, category deep-dive |

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

This executes all preprocessing, feature engineering, EDA, model training, evaluation, and forecasting steps in sequence. Trained models are saved to `models/`. Charts are saved to `reports/`.

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
| Explainability | SHAP |
| Forecasting | Prophet |
| Visualization | Plotly, Matplotlib, Seaborn |
| Dashboard | Streamlit |
| Persistence | joblib |

---

## Model Performance Summary

### Revenue Prediction (Model 2)
All six models achieve R² = 1.0, reflecting the near-deterministic relationship between CoursePrice and transaction Amount in the EduPro dataset.

### Enrollment Prediction (Model 1)
Random Forest achieves the best performance among all evaluated models. Low R² values reflect genuine uncertainty in enrollment prediction from static course attributes alone, which is expected and communicated to stakeholders via confidence intervals.

### Revenue Forecast (Prophet)
Six-month forecast projects $45K–$59K monthly revenue, with March 2026 as the peak month. Monthly enrollments are projected at 1,200–1,750, with January 2026 as the highest-demand period.

---

## Business Insights

1. **Top 3 categories** (AI, ML, Data Science) drive the majority of platform revenue.
2. **50% free enrollment rate** represents a significant upsell opportunity.
3. **Q1 seasonal peak** should anchor marketing and launch calendar planning.
4. **TeacherRating** is among the top predictors of course revenue — invest in instructor quality.
5. **Pricing sensitivity** analysis in the dashboard enables optimal price point selection per category and level.

---

## Future Improvements

- Real-time API integration for live inference
- User-level churn prediction model
- NLP course quality scoring from review text
- Automated monthly model retraining pipeline (MLflow)
- Dynamic pricing engine (reinforcement learning)
- 12-month multi-scenario forecasting (optimistic/base/pessimistic)

---

## Screenshots

*Dashboard screenshots to be added after local deployment.*

- Executive Dashboard: KPI cards and revenue trend charts
- Demand Prediction: Interactive prediction form with sensitivity curve
- Revenue Forecasting: Prophet forecast with confidence intervals
- Feature Importance: SHAP bar chart and demand driver insights
- Category Analytics: Profitability matrix and course-level breakdown

---

## License

This project is developed for portfolio, academic, and professional showcase purposes. All data is synthetic and generated for demonstration.
