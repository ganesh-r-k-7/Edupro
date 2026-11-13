# EduPro Predictive Analytics Platform
## Executive Summary

**Project:** Predictive Modeling for Course Demand and Revenue Forecasting
**Prepared For:** Senior Leadership, Strategic Planning, and Government Stakeholders
**Classification:** Business Intelligence — Internal Use

---

## Overview

EduPro operates a growing online education marketplace across twelve subject categories, serving thousands of learners through a portfolio of 60 courses delivered by 60 instructors. This Phase 1 review separates data-verified facts from model claims. The available dataset supports portfolio reporting, a historical enrollment reference, and transparent arithmetic price scenarios. It does not support a personalized demand forecast or an estimated price elasticity.

The dashboard currently addresses three questions with explicit limitations:

1. What is a typical course enrollment in the historical data?
2. What is expected revenue under a stated enrollment assumption?
3. What cached six-month forecast exists, and why is it not yet validated?

---

## Business Problem

Despite generating over 10,000 transactions in 2025, EduPro lacks systematic tools to forecast future demand or optimize revenue. Business decisions—including course scheduling, instructor assignments, pricing, and marketing budget allocation—are made reactively rather than proactively. This reactive posture creates exposure to:

- Revenue forecasting errors that complicate financial planning
- Instructor capacity mismatches in high-growth categories
- Pricing inefficiencies that leave revenue on the table
- Course launch failures due to insufficient demand validation

Phase 1 tests whether the available data can support these decisions. It finds that revenue prediction is invalid because the target is an accounting identity, and that enrollment is too uniform for the model to beat a mean baseline.

---

## Key Findings

### Revenue Performance (2025)

Free transactions are **64.03%** of the data (6,403 of 10,000) and paid transactions are **35.97%** (3,597). Paid/free is determined at the course level: 22 courses are paid and 38 are free, with no mixed courses. Total revenue is **$911,323.47**.

The top three revenue categories are **Artificial Intelligence ($202,750.67)**, **Business ($181,527.58)**, and **Project Management ($169,103.21)**, together **60.72%** of revenue. **Machine Learning revenue is $133.38 (0.0146%)** and **Marketing revenue is $0.00**. A 50% free share and AI/ML/Data Science leadership are not supported by the checked-in data.

### Revenue Forecast (January–June 2026) — Cached, Unbacktested

The following values are cached Prophet output. They have not been backtested and are not validated forecasts:

| Month | Projected Revenue |
|-------|------------------|
| January 2026 | $45,288 |
| February 2026 | $50,353 |
| March 2026 | $59,400 |
| April 2026 | $46,779 |
| May 2026 | $30,418 |
| June 2026 | $51,761 |

The cached output shows March 2026 as the highest month, but this claim is not independently validated. Do not use it for planning until a backtest is completed.

### Enrollment Forecast (January–June 2026)

The cached enrollment forecast projects 1,200–1,750 enrollments per month, but it is unbacktested. The historical data does **not** show a clear Q1 peak: Q1 had 2,456 enrollments and $231,643.16 revenue; Q2 had 2,555 and $231,406.06.

---

## Strategic Recommendations

### 1. Prioritize the Actual Top Categories

Artificial Intelligence, Business, and Project Management are the three largest revenue categories. Machine Learning ($133.38) and Marketing ($0.00) are not supported as leading investment areas by this dataset.

### 2. Do Not Optimize Price from This Dataset

The dataset has 22 paid prices, one per paid course, and no within-course price changes. Paid price/enrollment correlation is -0.022. Demand response is not identifiable, so the dashboard provides arithmetic what-if scenarios and does not recommend an optimal price. Use a controlled pricing experiment before changing prices.

### 3. Treat Free/Paid as a Portfolio Split, Not Conversion

Free transactions are 64.03%, but paid/free is a course-level attribute in this dataset. There is no observed free-to-paid learner conversion. Conversion campaigns require data that tracks individual learners across course types.

### 4. Do Not Infer Instructor Effects from the Legacy Model

The legacy revenue model is retired due to target leakage, and its SHAP/feature-importance output is not valid evidence. No instructor-quality recommendation is supported until a model beats a baseline on a valid holdout.

### 5. Do Not Plan Around a Q1 Surge

Q1 and Q2 revenue are effectively equal ($231,643 vs $231,406), and Q2 has slightly more enrollments. A Q1 seasonal surge is not supported by simple aggregates.

### 6. Use Reference Estimates, Not Thresholds, for Course Launch

The Demand Prediction module now shows a historical enrollment reference with a 10th–90th percentile range. It does not provide a personalized demand prediction. Course launches should be validated with a controlled pilot, not with model thresholds.

---

## Platform Capabilities

The EduPro Analytics Dashboard provides five interactive modules:

| Module | Function |
|--------|----------|
| Executive Dashboard | Real-time KPIs, revenue trends, and enrollment overview |
| Course Demand Prediction | Historical enrollment reference plus transparent price what-if scenarios |
| Revenue Forecasting | Cached six-month Prophet output, explicitly labelled unbacktested |
| Feature Importance Explorer | Model-validity status and descriptive enrollment associations |
| Category Analytics | Deep-dive revenue efficiency, teacher associations, growth, and course-level performance by category |

---

## Implementation Roadmap

**Phase 1 (Remediation complete):** Core pipeline plus correction of the revenue target, pricing claims, prediction inputs, and report facts.

**Phase 2 (Recommended, 60–90 days):** Integration of real-time transaction feeds for live dashboard updates; automated monthly model retraining.

**Phase 3 (Recommended, 90–180 days):** User-level churn prediction and personalized recommendation engine; dynamic pricing module with A/B testing infrastructure.

---

## Return on Investment

No ROI or uplift figures are estimated in Phase 1. The data does not identify price response, and there is no observed learner-level free-to-paid conversion. The earlier 8–15% pricing and 5–10% Q1 marketing figures were unsupported and have been removed.

---

## Conclusion

This Phase 1 platform is a research/demo decision-support prototype. It reliably reports checked-in portfolio facts and exposes the limits of the available data. It does not provide validated demand or revenue forecasts, and it is not production-ready.

Progress requires a controlled pricing experiment, learner-level conversion data, forecast backtesting, and a model that beats a simple baseline under a valid holdout.
