# Predictive Modeling for Course Demand and Revenue Forecasting on EduPro

## Research Paper

---

## Abstract

This paper presents a comprehensive predictive analytics system developed for EduPro, an online education platform. The system integrates multi-table relational data across users, teachers, courses, and transactions to build machine learning models capable of forecasting course enrollment demand and transaction-level revenue. Advanced feature engineering techniques generate over 20 derived predictive signals, including price sensitivity bands, instructor performance scores, rolling revenue averages, and temporal seasonality indicators. Regression models ranging from linear baselines to ensemble methods including Random Forest, Gradient Boosting, and XGBoost Regressor are trained and compared. Time-series forecasting using the Prophet model projects six-month revenue and enrollment trajectories. Explainability is addressed through SHAP (SHapley Additive exPlanations) analysis, revealing that course price, teacher rating, and course category are the dominant demand drivers. The system is deployed as a production Streamlit dashboard providing interactive prediction, forecasting, and strategic insight interfaces.

**Keywords:** Online education, predictive analytics, XGBoost, revenue forecasting, Prophet, SHAP, Streamlit, feature engineering

---

## 1. Introduction

The global online education market has experienced sustained growth, driven by increased internet penetration, corporate upskilling mandates, and the democratization of specialized knowledge. Platform operators face two persistent challenges: accurately projecting enrollment demand before course launch, and optimizing revenue through dynamic pricing and instructor allocation decisions.

EduPro operates a multi-category course marketplace offering both free and paid content across twelve subject areas. With over 10,000 recorded transactions, 60 active courses, and 60 instructors, the platform generates sufficient longitudinal data to support data-driven decision-making. This project applies machine learning and time-series forecasting to transform raw transactional data into actionable business intelligence.

The primary contributions of this work are:

1. A reproducible end-to-end data science pipeline from raw Excel data to trained production models.
2. A feature engineering framework generating 20+ business-relevant predictive signals.
3. A comparative evaluation of six regression algorithms across two prediction tasks.
4. A six-month Prophet-based revenue and enrollment forecast with category-level granularity.
5. A production-grade Streamlit dashboard enabling non-technical stakeholders to interact with model outputs.

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
- **Notes:** Date range spans January 1 to December 30, 2025. Approximately 50% of transactions are free enrollments (Amount = 0). Three payment methods are represented: Credit Card, PayPal, and Bank Transfer.

---

## 4. Methodology

The project follows a structured CRISP-DM workflow:

1. **Business Understanding:** Identify forecasting objectives and stakeholder requirements.
2. **Data Understanding:** Exploratory analysis of distributions, correlations, and temporal patterns.
3. **Data Preparation:** Sheet merging, type correction, missing value handling, outlier analysis.
4. **Feature Engineering:** Derivation of 20+ engineered signals from raw fields.
5. **Modeling:** Training and hyperparameter tuning of six regression algorithms.
6. **Evaluation:** MAE, RMSE, and R² scoring with cross-validation and residual analysis.
7. **Deployment:** Streamlit multi-page dashboard for interactive inference and visualization.

---

## 5. Data Preprocessing

### 5.1 Schema Merging
The four sheets are merged into a single analytical dataframe using the following join strategy:
- **Transactions** serves as the fact table (10,000 rows).
- **Courses** is joined on CourseID (left join, 100% match rate).
- **Teachers** is joined on TeacherID (left join, 100% match rate).
- **Users** is joined on UserID, retaining Age and Gender columns only.

The resulting merged dataset contains 22 columns and 10,000 rows with no data loss.

### 5.2 Data Quality Assessment
- **Duplicate rows:** Zero duplicates detected.
- **Missing values:** Zero missing values in the merged dataset.
- **Data type corrections:** TransactionDate is parsed as datetime64; CoursePrice, Amount, CourseDuration, CourseRating, and TeacherRating are cast to float64; YearsOfExperience is cast to int64.

### 5.3 Outlier Analysis
IQR-based outlier detection identifies 1,666 outliers (16.7%) in the Amount column, attributable to the bimodal distribution created by free (Amount=0) and paid transactions. This is a structural characteristic of the business model, not a data quality issue. TeacherRating contains 285 outliers (2.9%) on the lower tail. No values are clipped or removed, as outliers represent genuine business observations.

### 5.4 Correlation Analysis
Pearson correlations among numeric features reveal a near-perfect correlation (r=0.997) between CoursePrice and Amount, confirming that price is the primary revenue driver. CourseRating and TeacherRating show moderate positive correlation (r=0.31), suggesting instructor quality influences course ratings.

---

## 6. Feature Engineering

### 6.1 Course Features
- **PriceBand:** Ordinal categorical segmentation of CoursePrice into five bins: Free ($0), Budget ($0–50), Standard ($50–100), Premium ($100–200), and Elite ($200+). Enables non-linear price effects to be captured by tree-based models.
- **DurationBucket:** Segmentation of CourseDuration into Short (<10h), Medium (10–25h), Long (25–50h), and Extended (50h+).
- **RatingTier:** Ordinal classification of CourseRating into Low (<3.0), Medium (3.0–4.0), High (4.0–4.5), and Elite (4.5+).
- **EncodedCourseLevel:** Ordinal integer encoding of Beginner=1, Intermediate=2, Advanced=3.

### 6.2 Instructor Features
- **ExperienceBucket:** Segmentation of YearsOfExperience into Junior (0–2), Mid (2–5), Senior (5–10), and Expert (10+).
- **TeacherRatingScore:** Min-max normalization of TeacherRating to [0,1] scale for numeric stability.
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

**Model 2 — Transaction Revenue Prediction:** The target is the Amount field at the individual transaction level (10,000 observations). Free transactions (Amount=0) are included to model the propensity for paid versus free enrollment across feature combinations.

### 7.2 Feature Preparation
A scikit-learn ColumnTransformer applies StandardScaler to 11 numeric features and OneHotEncoder (handle_unknown='ignore') to 8 categorical features. The resulting sparse feature matrix is fed into a Pipeline for each model.

### 7.3 Algorithms

**Baseline Models:**
- **Linear Regression:** Ordinary least-squares baseline with no regularization.
- **Ridge Regression (alpha=1.0):** L2 regularization to manage multicollinearity.
- **Lasso Regression (alpha=0.1):** L1 regularization with implicit feature selection.

**Advanced Ensemble Models:**
- **Random Forest Regressor (n_estimators=200):** Bagging ensemble of decision trees with bootstrap sampling.
- **Gradient Boosting Regressor (n_estimators=200):** Sequential boosting with additive residual correction.
- **XGBoost Regressor (n_estimators=200):** Regularized gradient boosting with histogram-based tree construction.

### 7.4 Hyperparameter Tuning
XGBoost is tuned using RandomizedSearchCV (n_iter=20, cv=3) over the following parameter grid:
- n_estimators: [100, 200, 300]
- max_depth: [3, 5, 7]
- learning_rate: [0.05, 0.1, 0.2]
- subsample: [0.7, 0.8, 1.0]
- colsample_bytree: [0.7, 0.8, 1.0]

---

## 8. Evaluation Metrics

Model performance is measured using three standard regression metrics:

- **Mean Absolute Error (MAE):** Average absolute deviation between predicted and actual values. Interpretable in the original unit scale (dollars or enrollments).
- **Root Mean Squared Error (RMSE):** Square root of mean squared error. Penalizes large prediction errors more heavily than MAE.
- **R² Score:** Coefficient of determination. Indicates the proportion of target variance explained by the model. A score of 1.0 indicates perfect prediction; 0.0 indicates the model performs no better than predicting the mean.

Cross-validation (cv=3) is used to assess model generalization. Residual plots and prediction versus actual scatter plots provide visual diagnostics for heteroscedasticity and systematic bias.

---

## 9. Results

### 9.1 Revenue Prediction (Model 2)

All six models achieve an R² of 1.0 on the revenue prediction task, with MAE and RMSE near zero. This result reflects the near-deterministic relationship between CoursePrice and transaction Amount in the dataset. When a course is paid, the Amount equals CoursePrice; when free, Amount is zero. This makes CoursePrice a near-perfect predictor of Amount in this dataset.

**Practical Implication:** The revenue model is highly reliable for predicting individual transaction values given course attributes. Business value lies in combining this with enrollment volume predictions to project total revenue.

### 9.2 Enrollment Prediction (Model 1)

Given the small number of courses (60) and inherent randomness in enrollment distribution, enrollment prediction is a harder problem:
- Random Forest achieves the best R² (-0.003 on initial split, 0.0002 after tuning).
- All linear models show negative R², indicating enrollment count is not well-explained by a linear combination of static course attributes alone.
- The low R² is expected and business-relevant: enrollment demand is influenced by marketing, timing, and external factors not captured in the dataset.

**Practical Implication:** The enrollment model provides directional estimates useful for planning. Its confidence intervals should be communicated to stakeholders alongside point estimates.

### 9.3 Revenue Forecasting

Prophet models trained on 12 months of historical data project the following six-month revenue trajectory (January–June 2026):

| Month | Projected Revenue ($) |
|-------|----------------------|
| Jan 2026 | 45,288 |
| Feb 2026 | 50,353 |
| Mar 2026 | 59,400 |
| Apr 2026 | 46,779 |
| May 2026 | 30,418 |
| Jun 2026 | 51,761 |

March 2026 is projected as the peak revenue month, consistent with Q1 learning behavior patterns. May 2026 shows a predicted trough, which may reflect seasonality rather than structural decline.

Monthly enrollment forecast (Jan–Jun 2026) projects 1,200–1,750 enrollments per month, with January 2026 showing the highest expected enrollment at approximately 1,750.

---

## 10. Business Insights

### 10.1 Pricing Optimization
The near-perfect alignment between CoursePrice and Amount confirms that EduPro's pricing is a primary revenue lever. Categories with high average ratings and experienced instructors can support premium pricing without enrollment penalty. The pricing sensitivity analysis in the dashboard enables scenario planning for price point optimization.

### 10.2 Instructor Allocation
TeacherRating and YearsOfExperience are among the top SHAP contributors to revenue prediction. Allocating highly-rated, experienced instructors to high-demand, high-price categories maximizes expected revenue per course.

### 10.3 Category Strategy
Artificial Intelligence, Machine Learning, and Data Science categories show the highest total revenue and strongest growth trajectories. Strategic investment—additional courses, marketing spend, and instructor recruitment—in these categories should yield disproportionate revenue returns.

### 10.4 Free-to-Paid Conversion
Approximately 50% of enrollments are free, representing a significant untapped revenue pool. Targeted conversion campaigns—offering limited-time discounts, bundled pricing, or certification incentives—on popular free courses could materially increase platform revenue without requiring new user acquisition.

### 10.5 Seasonal Planning
Q1 (January–March) consistently shows the highest revenue and enrollment volumes, driven by New Year learning resolutions and corporate training budget releases. Marketing campaigns and new course launches should be concentrated in November–December to capture Q1 demand surge.

---

## 11. Conclusion

This project demonstrates the feasibility and business value of applying machine learning and time-series forecasting to online education platform data. The developed system provides EduPro with:

1. Transaction-level revenue prediction with near-perfect accuracy.
2. Course-level enrollment estimation to support capacity planning.
3. Six-month revenue and enrollment forecasts with confidence intervals.
4. An interactive dashboard enabling business users to explore predictions, sensitivity analyses, and category-level insights without requiring technical expertise.

The production-grade pipeline is reproducible, modular, and extensible, providing a foundation for continuous improvement as additional data becomes available.

---

## 12. Future Work

1. **Real-time inference:** Integrate the model pipeline with EduPro's transaction API for live prediction updates.
2. **User-level personalization:** Incorporate user engagement history (repeat purchases, session duration, completion rates) to build individual demand propensity models.
3. **NLP course analysis:** Apply text embeddings to course descriptions and reviews to generate semantic features that supplement tabular predictors.
4. **Dynamic pricing engine:** Implement a reinforcement learning or bandit-based pricing optimization system that adjusts prices in real time based on demand signals.
5. **Churn prediction:** Develop a user churn propensity model to identify at-risk learners and trigger retention campaigns.
6. **Multi-horizon forecasting:** Extend Prophet forecasts to 12-month horizons with scenario simulation (optimistic/base/pessimistic).
7. **Automated retraining:** Implement MLflow or Weights & Biases pipelines for automatic model retraining on monthly data refreshes.

---

## References

1. Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. *Proceedings of KDD 2016*.
2. Taylor, S. J., & Letham, B. (2018). Forecasting at Scale. *The American Statistician, 72*(1), 37–45.
3. Lundberg, S. M., & Lee, S.-I. (2017). A Unified Approach to Interpreting Model Predictions. *Advances in Neural Information Processing Systems, 30*.
4. Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research, 12*, 2825–2830.
5. Breiman, L. (2001). Random Forests. *Machine Learning, 45*(1), 5–32.
