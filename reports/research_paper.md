# Predictive Modeling for Course Demand and Revenue Forecasting on EduPro

## Research Paper

---

## Abstract

This paper presents a Phase 1 audit and remediation of a predictive analytics project for EduPro, an online education platform. The checked-in data contain 10,000 transactions across 60 courses and 60 instructors. The original project trained a transaction-level revenue model and a course-level enrollment model. The revenue target is an accounting identity: `Amount == CoursePrice` for every paid transaction and `Amount == 0` for every free transaction, so the reported R² = 1.0 reflects target leakage rather than predictive skill. Enrollment is near-uniform and the model does not beat a mean baseline. This paper therefore reports data-verified business facts, documents the invalidity of the legacy models, and replaces the pricing optimum with a transparent arithmetic scenario analysis. The Streamlit dashboard is a research/demo prototype, not a production forecasting system.

**Keywords:** Online education, target leakage, baseline comparison, pricing scenarios, forecast validation, Streamlit

---

## 1. Introduction

The global online education market has experienced sustained growth, driven by increased internet penetration, corporate upskilling mandates, and the democratization of specialized knowledge. Platform operators face two persistent challenges: accurately projecting enrollment demand before course launch, and optimizing revenue through dynamic pricing and instructor allocation decisions.

EduPro operates a multi-category course marketplace offering both free and paid content across twelve subject areas. With over 10,000 recorded transactions, 60 active courses, and 60 instructors, the platform generates sufficient longitudinal data to support data-driven decision-making. This project applies machine learning and time-series forecasting to transform raw transactional data into actionable business intelligence.

The primary contributions of this work are:

1. A reproducible research pipeline from raw Excel data to auditable diagnostics and baseline comparisons.
2. A feature engineering framework generating 20+ business-relevant predictive signals.
3. A comparative evaluation of six regression algorithms across two prediction tasks.
4. A six-month Prophet-based revenue and enrollment forecast with category-level granularity.
5. A Streamlit dashboard that exposes data facts and model limitations to non-technical stakeholders.

---

## 2. Problem Statement

EduPro's business decisions—including course scheduling, instructor assignment, pricing strategy, and marketing budget allocation—are currently made without systematic demand or revenue forecasting. This creates several operational risks:

- **Revenue uncertainty:** Without forward projections, budget planning relies on historical averages that fail to capture seasonal demand variation or growth trends.
- **Instructor misallocation:** Popular course categories may lack sufficient instructor capacity while low-demand areas are over-staffed.
- **Suboptimal pricing:** Uniform or ad hoc pricing fails to maximize revenue from high-demand segments.
- **Course launch risk:** New courses are launched without data-driven demand estimates, increasing the risk of underperformance.

This project addresses these gaps by developing predictive models for enrollment count, transaction revenue, and category-level revenue trends, supported by an interactive decision-support dashboard.

---

## 3. Dataset Description

The EduPro dataset is structured as a relational Excel workbook containing four sheets:

### 3.1 Users
- **Records:** 3,000 unique users
- **Features:** UserID, UserName, Age, Gender, Email
- **Notes:** User age ranges from 15 to 65 years. Gender is binary-coded (Male/Female). No missing values were identified.

### 3.2 Teachers
- **Records:** 60 instructors
- **Features:** TeacherID, TeacherName, Age, Gender, Expertise, YearsOfExperience, TeacherRating
- **Notes:** Expertise aligns with the 12 course categories. TeacherRating ranges from 1.0 to 5.0. Experience ranges from 1 to 20 years.

### 3.3 Courses
- **Records:** 60 unique courses
- **Features:** CourseID, CourseName, CourseCategory, CourseType, CourseLevel, CoursePrice, CourseDuration, CourseRating
- **Notes:** 12 categories, 3 levels (Beginner/Intermediate/Advanced), 2 types (Free/Paid). Prices range from $0 to $490.90. Duration ranges from approximately 2 to 180 hours.

### 3.4 Transactions
- **Records:** 10,000 transactions
- **Features:** TransactionID, UserID, CourseID, TransactionDate, Amount, PaymentMethod, TeacherID
- **Notes:** Date range spans January 1 to December 30, 2025. Free transactions are 64.03% (6,403 of 10,000); paid are 35.97% (3,597). Three payment methods are represented: Credit Card, PayPal, and Bank Transfer.

---

## 4. Methodology

The project follows a structured CRISP-DM workflow:

1. **Business Understanding:** Identify forecasting objectives and stakeholder requirements.
2. **Data Understanding:** Exploratory analysis of distributions, correlations, and temporal patterns.
3. **Data Preparation:** Sheet merging, type correction, missing value handling, outlier analysis.
4. **Feature Engineering:** Derivation of 20+ engineered signals from raw fields.
5. **Modeling:** Training and hyperparameter tuning of six regression algorithms.
6. **Evaluation:** MAE, RMSE, and R² with training-only cross-validation, a single final test evaluation, and an explicit mean baseline.
7. **Deployment:** Streamlit multi-page dashboard for interactive inference and visualization.

---

## 5. Data Preprocessing

### 5.1 Schema Merging
The four sheets are merged into a single analytical dataframe using the following join strategy:
- **Transactions** serves as the fact table (10,000 rows).
- **Courses** is joined on CourseID (left join, 100% match rate).
- **Teachers** is joined on TeacherID (left join, 100% match rate).
- **Users** is joined on UserID, retaining Age and Gender columns only.

The merged dataset contains 22 columns and 10,000 rows before feature engineering; the checked-in `processed_data.csv` contains 44 columns after feature engineering.

### 5.2 Data Quality Assessment
- **Duplicate rows:** Zero duplicates detected.
- **Missing values:** Zero missing values in the merged dataset.
- **Data type corrections:** TransactionDate is parsed as datetime64; CoursePrice, Amount, CourseDuration, CourseRating, and TeacherRating are cast to float64; YearsOfExperience is cast to int64.

### 5.3 Outlier Analysis
IQR-based outlier detection identifies 1,666 outliers (16.7%) in the Amount column, attributable to the bimodal distribution created by free (Amount=0) and paid transactions. This is a structural characteristic of the business model, not a data quality issue. TeacherRating contains 285 outliers (2.9%) on the lower tail. No values are clipped or removed, as outliers represent genuine business observations.

### 5.4 Correlation Analysis
Pearson correlation between CoursePrice and Amount is approximately 1.0, but this is an accounting identity: Amount equals CoursePrice for paid transactions and is zero for free transactions. It is not evidence of an independent predictive relationship. CourseRating and TeacherRating show moderate positive correlation (r=0.31), but this does not establish a causal effect on enrollment or revenue.

---

## 6. Feature Engineering

### 6.1 Course Features
- **PriceBand:** Ordinal categorical segmentation of CoursePrice into five bins: Free ($0), Budget ($0–50], Standard ($50–100], Premium ($100–200], and Elite ($200–500]. The same boundaries are used at training and inference.
- **DurationBucket:** Segmentation of CourseDuration into Short (<10h), Medium (10–25h), Long (25–50h), and Extended (50h+).
- **RatingTier:** Ordinal classification of CourseRating into Low (<3.0), Medium (3.0–4.0), High (4.0–4.5), and Elite (4.5+).
- **EncodedCourseLevel:** Ordinal integer encoding of Beginner=1, Intermediate=2, Advanced=3.

### 6.2 Instructor Features
- **ExperienceBucket:** Segmentation of YearsOfExperience into Junior (0–2), Mid (2–5), Senior (5–10), and Expert (10+).
- **TeacherRatingScore:** Fixed normalization of TeacherRating from the 1–5 scale to [0,1], shared by training and inference.
- **ExpertiseCategoryMatch:** Binary flag indicating whether the teacher's expertise domain matches the course category (1=match, 0=mismatch).

### 6.3 Time-Based Features
- **TransactionMonth:** Integer month extracted from TransactionDate (1–12).
- **Quarter:** Calendar quarter (1–4).
- **Year:** Transaction year.
- **DayOfWeek:** Integer day of week (0=Monday, 6=Sunday).
- **WeekOfYear:** ISO week number.
- **IsWeekend:** Binary flag for Saturday/Sunday transactions.
- **SeasonalityLabel:** Categorical seasonality label derived from Quarter: NewYearRush (Q1), Spring (Q2), Summer (Q3), YearEnd (Q4).

### 6.4 Historical Performance Features
Per-course aggregations computed across all transactions:
- **EnrollmentCount:** Total transaction count per CourseID.
- **TotalRevenue:** Sum of Amount per CourseID.
- **AverageRevenue:** Mean Amount per CourseID.
- **RevenuePerEnrollment:** TotalRevenue divided by EnrollmentCount.
- **MonthlyRevenue:** Revenue per (CourseID, Year, Month) grouping.
- **RollingRevenueAverage:** 3-month rolling mean of MonthlyRevenue per course.
- **RevenueGrowthRate:** Month-over-month percentage change in MonthlyRevenue per course.

---

## 7. Model Development

### 7.1 Target Variables

**Model 1 — Enrollment Count Prediction:** The target is the number of transactions (enrollments) per CourseID, derived by aggregating the transaction table at course level. This is a cross-sectional regression problem with 60 course-level observations.

**Model 2 — Transaction Revenue Prediction (retired):** The original target was the Amount field at the individual transaction level. Because `Amount == CoursePrice` for all paid rows and `Amount == 0` for all free rows, and because CoursePrice was also a feature, the model reconstructed an accounting identity. No revenue regressor is trained or used in Phase 1. The legacy `models/revenue_model.pkl` is preserved for audit only.

### 7.2 Feature Preparation
The Phase 1 enrollment model uses 7 course-configuration numeric features and 6 categorical features through a scikit-learn ColumnTransformer with StandardScaler and OneHotEncoder (dense output). Transaction-only fields (PaymentMethod, month, quarter, weekend) and ExpertiseCategoryMatch are excluded because they are not stable course-level inputs.

### 7.3 Algorithms

**Baseline Models:**
- **Linear Regression:** Ordinary least-squares baseline with no regularization.
- **Ridge Regression (alpha=1.0):** L2 regularization to manage multicollinearity.
- **Lasso Regression (alpha=0.1):** L1 regularization with implicit feature selection.

**Advanced Ensemble Models:**
- **Random Forest Regressor (n_estimators=200):** Bagging ensemble of decision trees with bootstrap sampling.
- **Gradient Boosting Regressor (n_estimators=200):** Sequential boosting with additive residual correction.
- **XGBoost Regressor (n_estimators=200):** Regularized gradient boosting with histogram-based tree construction.

### 7.4 Phase 1 Evaluation Protocol

A single train/test split is used. Candidate enrollment models are compared using 5-fold cross-validation on the training split only. The selected candidate is evaluated once on the test split and compared with a `DummyRegressor` mean baseline. If it does not beat the baseline on both cross-validation and the final test, no Phase 1 model artifact is saved. Hyperparameter tuning is not used to select a model on the test set.

---

## 8. Evaluation Metrics

Model performance is measured using three standard regression metrics:

- **Mean Absolute Error (MAE):** Average absolute deviation between predicted and actual values. Interpretable in the original unit scale (dollars or enrollments).
- **Root Mean Squared Error (RMSE):** Square root of mean squared error. Penalizes large prediction errors more heavily than MAE.
- **R² Score:** Coefficient of determination. Indicates the proportion of target variance explained by the model. A score of 1.0 indicates perfect prediction; 0.0 indicates the model performs no better than predicting the mean.

Cross-validation (5 folds) is used on the training split for model selection. The test split is touched once. The legacy revenue plots are not regenerated because the revenue target is invalid.

---

## 9. Results

### 9.1 Revenue Prediction (Retired)

The original revenue model achieved R² = 1.0 because the target is an accounting identity: `Amount == CoursePrice` for all 3,597 paid rows and `Amount == 0` for all 6,403 free rows. CoursePrice was also a feature. This is target leakage, not predictive skill.

**Practical Implication:** The legacy revenue model and its feature-importance/SHAP claims are not valid for pricing, revenue forecasting, or ROI analysis. Expected revenue in the dashboard is now calculated arithmetically as price × reference enrollments for paid courses, with explicit assumptions.

### 9.2 Enrollment Prediction (Baseline Comparison)

There are only 60 course-level observations. Enrollment ranges from 140 to 196 (mean 166.7, standard deviation 12.4; CV 7.5%). A global-mean baseline has MAE 10.02 and RMSE 12.42. A category-mean baseline is worse (MAE 11.13, R² -0.21).

Phase 1 compares candidate models (LinearRegression, Ridge, Lasso, RandomForest, GradientBoosting, XGBoost) with a mean baseline using 5-fold cross-validation on the training split and one final test evaluation. The baseline achieved CV RMSE 12.27 and test RMSE 13.73. No candidate beat the baseline on both criteria; therefore no Phase 1 enrollment model artifact was persisted. The dashboard shows the historical reference mean and 10th–90th percentile range instead.

**Practical Implication:** The available static course features do not support useful course-level enrollment prediction. Marketing, timing, and learner-level factors are not captured in the dataset.

### 9.3 Revenue Forecasting (Cached, Unbacktested)

The following values are cached Prophet output, not validated forecasts. No rolling-origin backtest has been performed:

| Month | Projected Revenue ($) |
|-------|----------------------|
| Jan 2026 | 45,288 |
| Feb 2026 | 50,353 |
| Mar 2026 | 59,400 |
| Apr 2026 | 46,779 |
| May 2026 | 30,418 |
| Jun 2026 | 51,761 |

The cached output shows March 2026 as the highest month, but this is not independently validated. The historical data do not show a clear Q1 peak. Monthly enrollment forecast values are likewise cached and unbacktested.

---

## 10. Business Insights

### 10.1 Pricing

The dataset has 22 paid prices, one per paid course, and no within-course price changes. Paid price/enrollment correlation is -0.022. Price elasticity is not identifiable. The dashboard therefore provides arithmetic what-if scenarios with an explicit assumed enrollment change, not an optimal price or an estimated demand curve. A controlled pricing experiment is required before causal pricing decisions.

### 10.2 Instructor Allocation

The legacy SHAP/feature-importance results are invalid because the revenue target is an accounting identity and the legacy enrollment model does not beat a mean baseline. No instructor-effect recommendation is supported by Phase 1 evidence.

### 10.3 Category Strategy

Artificial Intelligence ($202,750.67), Business ($181,527.58), and Project Management ($169,103.21) are the top three revenue categories, together 60.72% of total revenue. Machine Learning revenue is $133.38 (0.0146%) and Marketing revenue is $0.00. Category investment should follow these verified totals, not the original AI/ML/Data Science claim.

### 10.4 Free-to-Paid Conversion

Free transactions are 64.03% (6,403 of 10,000). However, paid/free is a course-level attribute: 22 courses are paid and 38 are free, with no mixed courses. There is no observed learner-level free-to-paid conversion in this dataset, so a conversion uplift cannot be estimated.

### 10.5 Seasonal Planning

Q1 and Q2 revenue are effectively equal: $231,643.16 versus $231,406.06. Q2 has slightly more enrollments (2,555 versus 2,456). A Q1 surge is not supported by the checked-in data.

---

## 11. Conclusion

This Phase 1 audit demonstrates why model validation and target definition matter more than a high R². The project provides EduPro with:

1. A documented revenue target-leakage finding and retirement of the invalid revenue model.
2. A baseline comparison showing that static course features do not support useful enrollment prediction.
3. Data-verified portfolio facts and transparent arithmetic price scenarios.
4. A dashboard that exposes model limitations instead of presenting false precision.

The pipeline is a research/demo prototype, not a production forecasting system.

---
 
## 12. Future Work
 
1. **Controlled pricing experiment:** Randomize prices within courses over time before attempting any elasticity or revenue-optimization model.
2. **Real-time inference:** Integrate a validated model pipeline with EduPro's transaction API for live prediction updates.
3. **User-level personalization:** Incorporate user engagement history (repeat purchases, session duration, completion rates) to build individual demand propensity models.
4. **NLP course analysis:** Apply text embeddings to course descriptions and reviews to generate semantic features that supplement tabular predictors.
5. **Dynamic pricing engine:** Implement a reinforcement learning or bandit-based pricing system only after a controlled experiment establishes measurable demand response.
6. **Churn prediction:** Develop a user churn propensity model to identify at-risk learners and trigger retention campaigns.
7. **Multi-horizon forecasting:** Backtest Prophet and extend validated forecasts to 12-month horizons with scenario simulation (optimistic/base/pessimistic).
8. **Automated retraining:** Implement MLflow or Weights & Biases pipelines for automatic model retraining on monthly data refreshes.
 
---
 
## 13. Engineering Improvements (Phases 3–4)
 
The following engineering improvements were implemented after the initial audit to harden the codebase:
 
- **R3.1 (Shared Package):** Created `src/edup/` as a single source of truth for configuration, feature engineering, data contracts, model operations, and analytics—eliminating train/serve skew.
- **R3.2 (Dead Code Removal):** Removed unused functions (`get_enrollment_model`, `_cached_compute`, `get_business_facts`, `get_price_demand_diagnostics`, `compute_shap_values`), unused constants in `config.py`, and obsolete compatibility wrappers.
- **R3.3 (Code Quality & Observability):** Added type hints to all public interfaces; configured Ruff and Mypy with zero errors; introduced structured logging via `edup.logging`; formalized exception taxonomy (`DataContractError`, `DataUnavailableError`, `ModelLoadError`, `ForecastError`, `DashboardError`).
- **R3.4 (Continuous Integration):** Added GitHub Actions workflow (`.github/workflows/ci.yml`) running on push/PR to `main` with Python 3.11, dependency caching, and full test suite (296 tests).
- **R3.5 (Dependency Reproducibility & Model Metadata):** Pinned all dependencies in `pyproject.toml` and `requirements.lock`; generated `model_metadata.json` for all artifacts with SHA256 hashes, training metadata, library versions, and explicit status flags (`legacy`, `retired`, `cached`).
- **R4.1–R4.2 (Performance):** Added `st.cache_resource` for model loading and `st.cache_data` for dashboard computations (KPIs, charts, forecasts) keyed by data hash for automatic invalidation.
 
---
 
## References

1. Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. *Proceedings of KDD 2016*.
2. Taylor, S. J., & Letham, B. (2018). Forecasting at Scale. *The American Statistician, 72*(1), 37–45.
3. Lundberg, S. M., & Lee, S.-I. (2017). A Unified Approach to Interpreting Model Predictions. *Advances in Neural Information Processing Systems, 30*.
4. Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research, 12*, 2825–2830.
5. Breiman, L. (2001). Random Forests. *Machine Learning, 45*(1), 5–32.
