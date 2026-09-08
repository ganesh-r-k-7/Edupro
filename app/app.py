"""
app.py — EduPro Predictive Analytics Dashboard
Multi-page Streamlit application for course demand and revenue forecasting.
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import warnings
warnings.filterwarnings('ignore')

# Ensure utils module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import utils

# ─── Page Configuration ──────────────────────────────────────────────────────

st.set_page_config(
    page_title='EduPro Analytics',
    page_icon=None,
    layout='wide',
    initial_sidebar_state='expanded'
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a3a5c;
        letter-spacing: 0.5px;
        margin-bottom: 0.25rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #5a7a9a;
        margin-bottom: 1.5rem;
    }
    .kpi-card {
        background-color: #f0f6ff;
        border-left: 4px solid #1f77b4;
        border-radius: 6px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.5rem;
    }
    .kpi-label {
        font-size: 0.82rem;
        font-weight: 600;
        color: #5a7a9a;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #1a3a5c;
        margin-top: 0.15rem;
    }
    .section-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #1a3a5c;
        border-bottom: 2px solid #e0ecf8;
        padding-bottom: 0.4rem;
        margin-bottom: 1rem;
        margin-top: 1.5rem;
    }
    .insight-box {
        background-color: #eaf4ff;
        border: 1px solid #c0dcf5;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-size: 0.92rem;
        color: #1a3a5c;
        margin-bottom: 0.75rem;
    }
    .stAlert { margin-top: 0.5rem; }
    div[data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)


# ─── Data Loading ─────────────────────────────────────────────────────────────

@st.cache_data
def get_data():
    return utils.load_processed_data()


@st.cache_data
def get_kpis(df_hash):
    df = get_data()
    return utils.compute_kpis(df)


def kpi_card(label, value, col):
    with col:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """, unsafe_allow_html=True)


# ─── Sidebar Navigation ───────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### EduPro Analytics Platform")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        options=[
            "Executive Dashboard",
            "Course Demand Prediction",
            "Revenue Forecasting",
            "Feature Importance Explorer",
            "Category Analytics",
        ],
        index=0,
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#888'>EduPro Predictive Modeling v1.0<br>"
        "Built with Streamlit + XGBoost + Prophet</small>",
        unsafe_allow_html=True
    )


# ─── Page 1: Executive Dashboard ─────────────────────────────────────────────

if page == "Executive Dashboard":
    st.markdown('<div class="main-header">Executive Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Platform-wide performance overview and strategic KPIs</div>', unsafe_allow_html=True)

    df = get_data()
    kpis = utils.compute_kpis(df)

    c1, c2, c3, c4 = st.columns(4)
    kpi_card("Total Revenue", f"${kpis['total_revenue']:,.0f}", c1)
    kpi_card("Total Enrollments", f"{kpis['total_enrollments']:,}", c2)
    kpi_card("Avg Course Rating", f"{kpis['avg_course_rating']:.2f} / 5.0", c3)
    kpi_card("Paid Transaction Rate", f"{kpis['paid_ratio']:.1f}%", c4)

    c5, c6, c7, c8 = st.columns(4)
    kpi_card("Active Courses", f"{kpis['unique_courses']}", c5)
    kpi_card("Active Teachers", f"{kpis['unique_teachers']}", c6)
    kpi_card("Top Category", kpis['top_category'], c7)
    kpi_card("Avg Revenue / Course", f"${kpis['avg_revenue_per_course']:,.0f}", c8)

    st.markdown('<div class="section-title">Revenue and Enrollment Trends</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(utils.chart_monthly_revenue(df), use_container_width=True)
    with col_b:
        st.plotly_chart(utils.chart_category_revenue(df), use_container_width=True)

    st.markdown('<div class="section-title">Top Performing Courses</div>', unsafe_allow_html=True)
    st.plotly_chart(utils.chart_top_courses(df, n=10), use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.plotly_chart(utils.chart_enrollment_by_category(df), use_container_width=True)
    with col_d:
        st.plotly_chart(utils.chart_payment_methods(df), use_container_width=True)

    st.markdown('<div class="section-title">Strategic Insights</div>', unsafe_allow_html=True)
    top_cat_rev = df.groupby('CourseCategory')['Amount'].sum()
    top3 = top_cat_rev.nlargest(3).index.tolist()
    total = top_cat_rev.sum()
    top3_share = top_cat_rev.nlargest(3).sum() / total * 100 if total > 0 else 0

    st.markdown(f'<div class="insight-box">The top 3 revenue-generating categories are <strong>{", ".join(top3)}</strong>, collectively accounting for <strong>{top3_share:.1f}%</strong> of total platform revenue.</div>', unsafe_allow_html=True)

    paid_rev = df[df['Amount'] > 0]['Amount'].sum()
    free_enroll = (df['Amount'] == 0).sum()
    st.markdown(f'<div class="insight-box">Free course enrollments account for <strong>{free_enroll:,}</strong> transactions ({free_enroll/len(df)*100:.1f}% of total), representing a significant upsell and conversion opportunity.</div>', unsafe_allow_html=True)


# ─── Page 2: Course Demand Prediction ────────────────────────────────────────

elif page == "Course Demand Prediction":
    st.markdown('<div class="main-header">Course Demand Prediction</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Predict expected enrollments and revenue for a new or existing course</div>', unsafe_allow_html=True)

    with st.form("prediction_form"):
        st.markdown('<div class="section-title">Course Parameters</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            category = st.selectbox("Course Category", utils.COURSE_CATEGORIES)
            level = st.selectbox("Course Level", utils.COURSE_LEVELS)
            course_type = st.selectbox("Course Type", utils.COURSE_TYPES)
        with col2:
            price = st.number_input("Course Price ($)", min_value=0.0, max_value=500.0,
                                    value=99.0, step=5.0)
            duration = st.number_input("Course Duration (hours)", min_value=1.0, max_value=200.0,
                                       value=20.0, step=1.0)
            course_rating = st.slider("Expected Course Rating", 1.0, 5.0, 4.0, 0.1)
        with col3:
            teacher_exp = st.slider("Teacher Experience (years)", 0, 30, 5)
            teacher_rating = st.slider("Teacher Rating", 1.0, 5.0, 4.0, 0.1)
            payment_method = st.selectbox("Payment Method", utils.PAYMENT_METHODS)

        submitted = st.form_submit_button("Generate Predictions", type="primary")

    if submitted:
        with st.spinner("Running prediction models..."):
            pred_rev, rev_err = utils.predict_revenue(
                category, level, price, duration, teacher_exp, teacher_rating)
            pred_enroll, enroll_err = utils.predict_enrollment(
                category, level, price, duration, teacher_exp, teacher_rating)

        st.markdown('<div class="section-title">Prediction Results</div>', unsafe_allow_html=True)

        if rev_err or enroll_err:
            st.warning(rev_err or enroll_err)
            st.info("Tip: Run the pipeline script first to train and save models. See README.md for instructions.")
        else:
            c1, c2, c3 = st.columns(3)
            kpi_card("Predicted Revenue / Transaction", f"${pred_rev:,.2f}", c1)
            kpi_card("Predicted Enrollments", f"{int(pred_enroll):,}", c2)
            projected_total = pred_rev * pred_enroll
            kpi_card("Projected Total Revenue", f"${projected_total:,.0f}", c3)

            st.markdown('<div class="section-title">Pricing Sensitivity Analysis</div>', unsafe_allow_html=True)
            prices = np.linspace(max(0, price - 50), price + 100, 20)
            rev_curve = []
            for p in prices:
                r, e = utils.predict_revenue(category, level, p, duration, teacher_exp, teacher_rating)
                rev_curve.append({'Price': p, 'Predicted Revenue': r or 0})

            import plotly.express as px
            fig_curve = px.line(pd.DataFrame(rev_curve), x='Price', y='Predicted Revenue',
                                title='Revenue Sensitivity to Price Change',
                                labels={'Price': 'Course Price ($)', 'Predicted Revenue': 'Predicted Revenue ($)'},
                                markers=True)
            fig_curve.add_vline(x=price, line_dash='dash', line_color='red',
                                annotation_text='Current Price')
            st.plotly_chart(fig_curve, use_container_width=True)

            st.markdown('<div class="insight-box">Based on the model, the optimal price point for maximum revenue is approximately <strong>${:.0f}</strong>. Consider A/B testing pricing around this range.</div>'.format(
                pd.DataFrame(rev_curve).set_index('Price')['Predicted Revenue'].idxmax()
            ), unsafe_allow_html=True)


# ─── Page 3: Revenue Forecasting ─────────────────────────────────────────────

elif page == "Revenue Forecasting":
    st.markdown('<div class="main-header">Revenue Forecasting</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Time-series revenue and enrollment forecasts using Prophet</div>', unsafe_allow_html=True)

    df = get_data()

    st.markdown('<div class="section-title">Historical Monthly Revenue</div>', unsafe_allow_html=True)
    st.plotly_chart(utils.chart_monthly_revenue(df), use_container_width=True)

    forecast_data = utils.load_forecast_results()
    if forecast_data:
        st.markdown('<div class="section-title">Revenue Forecast (Next 6 Months)</div>', unsafe_allow_html=True)
        rev_fc = forecast_data.get('revenue')
        if rev_fc is not None:
            import plotly.graph_objects as go
            fig_fc = go.Figure()
            hist = rev_fc[rev_fc['ds'] <= df['TransactionDate'].max()]
            fut = rev_fc[rev_fc['ds'] > df['TransactionDate'].max()]
            fig_fc.add_trace(go.Scatter(x=hist['ds'], y=hist['yhat'], name='Historical Fit',
                                        line=dict(color='steelblue', width=2)))
            fig_fc.add_trace(go.Scatter(x=fut['ds'], y=fut['yhat'], name='Forecast',
                                        line=dict(color='darkorange', width=2, dash='dash')))
            fig_fc.add_trace(go.Scatter(
                x=pd.concat([fut['ds'], fut['ds'].iloc[::-1]]),
                y=pd.concat([fut['yhat_upper'], fut['yhat_lower'].iloc[::-1]]),
                fill='toself', fillcolor='rgba(255,165,0,0.15)',
                line=dict(color='rgba(255,255,255,0)'), name='Confidence Interval'))
            fig_fc.update_layout(title='Monthly Revenue Forecast',
                                  xaxis_title='Date', yaxis_title='Revenue ($)', height=400)
            st.plotly_chart(fig_fc, use_container_width=True)

            future_rows = rev_fc[rev_fc['ds'] > df['TransactionDate'].max()][['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
            future_rows.columns = ['Month', 'Forecast ($)', 'Lower Bound ($)', 'Upper Bound ($)']
            future_rows = future_rows.round(2)
            st.markdown('<div class="section-title">Forecast Table</div>', unsafe_allow_html=True)
            st.dataframe(future_rows.reset_index(drop=True), use_container_width=True)
    else:
        st.info("Forecast results not yet generated. Run the forecasting pipeline (notebooks/06_forecasting.py) to compute and cache forecast results.")

    st.markdown('<div class="section-title">Category Revenue Growth Trends</div>', unsafe_allow_html=True)
    monthly_cat = df.groupby(['CourseCategory', df['TransactionDate'].dt.to_period('M')])['Amount'].sum().reset_index()
    monthly_cat['Month'] = monthly_cat['TransactionDate'].astype(str)

    import plotly.express as px
    fig_cat = px.line(monthly_cat, x='Month', y='Amount', color='CourseCategory',
                      title='Monthly Revenue by Category',
                      labels={'Amount': 'Revenue ($)', 'Month': 'Month'})
    fig_cat.update_layout(height=450, xaxis_tickangle=-30)
    st.plotly_chart(fig_cat, use_container_width=True)

    st.markdown('<div class="section-title">Revenue Growth Rate by Category</div>', unsafe_allow_html=True)
    cat_rev = df.groupby('CourseCategory')['Amount'].sum().sort_values(ascending=False)
    cat_monthly = df.groupby(['CourseCategory', df['TransactionDate'].dt.to_period('M')])['Amount'].sum().unstack().fillna(0)

    growth_data = []
    for cat in cat_monthly.index:
        row = cat_monthly.loc[cat]
        if len(row) >= 2 and row.iloc[0] > 0:
            growth = (row.iloc[-1] - row.iloc[0]) / row.iloc[0] * 100
            growth_data.append({'Category': cat, 'Revenue Growth (%)': round(growth, 1)})

    if growth_data:
        growth_df = pd.DataFrame(growth_data).sort_values('Revenue Growth (%)', ascending=False)
        fig_growth = px.bar(growth_df, x='Category', y='Revenue Growth (%)',
                            color='Revenue Growth (%)', color_continuous_scale='Blues',
                            title='YTD Revenue Growth Rate by Category')
        fig_growth.update_layout(xaxis_tickangle=-45, height=380)
        st.plotly_chart(fig_growth, use_container_width=True)


# ─── Page 4: Feature Importance Explorer ─────────────────────────────────────

elif page == "Feature Importance Explorer":
    st.markdown('<div class="main-header">Feature Importance Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Understand the key drivers of course demand and revenue using SHAP and feature importance analysis</div>', unsafe_allow_html=True)

    import os
    import plotly.express as px
    import joblib

    MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models')
    revenue_model_path = os.path.join(MODELS_DIR, 'revenue_model.pkl')
    enrollment_model_path = os.path.join(MODELS_DIR, 'enrollment_model.pkl')

    NUMERIC_FEATURES = [
        'CoursePrice', 'CourseDuration', 'CourseRating',
        'TeacherRating', 'YearsOfExperience', 'EncodedCourseLevel',
        'TeacherRatingScore', 'ExpertiseCategoryMatch',
        'TransactionMonth', 'Quarter', 'IsWeekend'
    ]
    CATEGORICAL_FEATURES = [
        'CourseCategory', 'CourseType', 'PriceBand',
        'DurationBucket', 'RatingTier', 'ExperienceBucket',
        'SeasonalityLabel', 'PaymentMethod'
    ]

    if not os.path.exists(revenue_model_path):
        st.info("Models not yet trained. Run the pipeline (notebooks/04_model_training.py) to generate models.")
    else:
        model_select = st.radio("Select Model", ["Revenue Prediction", "Enrollment Prediction"], horizontal=True)
        model_path = revenue_model_path if model_select == "Revenue Prediction" else enrollment_model_path

        if os.path.exists(model_path):
            model = joblib.load(model_path)
            final_model = model.named_steps['model']

            if hasattr(final_model, 'feature_importances_'):
                preprocessor = model.named_steps['preprocessor']
                try:
                    ohe = preprocessor.named_transformers_['cat']
                    cat_names = list(ohe.get_feature_names_out(CATEGORICAL_FEATURES))
                except Exception:
                    cat_names = []

                all_names = NUMERIC_FEATURES + cat_names
                importances = final_model.feature_importances_
                n = min(len(importances), len(all_names))
                feat_imp = pd.DataFrame({
                    'Feature': all_names[:n],
                    'Importance': importances[:n]
                }).sort_values('Importance', ascending=False)

                st.markdown('<div class="section-title">Top 20 Feature Importances</div>', unsafe_allow_html=True)
                top20 = feat_imp.head(20)
                fig_imp = px.bar(top20, x='Importance', y='Feature', orientation='h',
                                 color='Importance', color_continuous_scale='Blues',
                                 title=f'{model_select}: Feature Importance Rankings')
                fig_imp.update_layout(height=550, coloraxis_showscale=False, yaxis={'autorange': 'reversed'})
                st.plotly_chart(fig_imp, use_container_width=True)

                st.markdown('<div class="section-title">Feature Importance Table</div>', unsafe_allow_html=True)
                st.dataframe(feat_imp.round(6).reset_index(drop=True), use_container_width=True)

                st.markdown('<div class="section-title">Demand Driver Analysis</div>', unsafe_allow_html=True)
                top3_features = feat_imp.head(3)['Feature'].tolist()

                st.markdown(f"""
                <div class="insight-box">
                    <strong>Primary Demand Drivers:</strong><br>
                    The top 3 features driving {model_select.lower()} are: <strong>{', '.join(top3_features)}</strong>.
                    These features have the highest predictive weight in the model and should be the
                    primary focus for business optimization strategies.
                </div>
                """, unsafe_allow_html=True)

                if 'CoursePrice' in top3_features or 'PriceBand' in top3_features:
                    st.markdown('<div class="insight-box"><strong>Pricing Sensitivity:</strong> Course price is among the top demand drivers. A tiered pricing strategy aligned with the course category and level is recommended.</div>', unsafe_allow_html=True)

                if any('Teacher' in f or 'Rating' in f for f in top3_features):
                    st.markdown('<div class="insight-box"><strong>Instructor Influence:</strong> Teacher quality metrics are significant revenue predictors. Prioritizing instructor ratings and experience in course assignments can increase revenue.</div>', unsafe_allow_html=True)

                # SHAP section
                st.markdown('<div class="section-title">SHAP Explainability</div>', unsafe_allow_html=True)
                if st.button("Compute SHAP Values (may take 30-60 seconds)"):
                    with st.spinner("Computing SHAP values..."):
                        try:
                            import shap
                            df = get_data()
                            num_available = [c for c in NUMERIC_FEATURES if c in df.columns]
                            cat_available = [c for c in CATEGORICAL_FEATURES if c in df.columns]
                            X_sample = df[num_available + cat_available].sample(
                                min(200, len(df)), random_state=42)
                            shap_vals, X_df, explainer = utils.compute_shap_values(
                                model, X_sample, num_available, cat_available)

                            shap_imp = pd.DataFrame({
                                'Feature': X_df.columns,
                                'SHAP Mean Abs': np.abs(shap_vals).mean(axis=0)
                            }).sort_values('SHAP Mean Abs', ascending=False).head(20)

                            fig_shap = px.bar(shap_imp, x='SHAP Mean Abs', y='Feature',
                                              orientation='h', color='SHAP Mean Abs',
                                              color_continuous_scale='RdBu',
                                              title='SHAP Feature Contributions (Mean |SHAP|)')
                            fig_shap.update_layout(height=550, coloraxis_showscale=False,
                                                    yaxis={'autorange': 'reversed'})
                            st.plotly_chart(fig_shap, use_container_width=True)
                            st.success("SHAP analysis complete.")
                        except Exception as e:
                            st.error(f"SHAP computation error: {e}")
            else:
                st.warning("Loaded model does not support feature importances. Ensure XGBoost or RandomForest is the final estimator.")
        else:
            st.info(f"Model file not found at: {model_path}")


# ─── Page 5: Category Analytics ──────────────────────────────────────────────

elif page == "Category Analytics":
    st.markdown('<div class="main-header">Category Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Deep-dive into course category performance, profitability, and growth</div>', unsafe_allow_html=True)

    df = get_data()
    import plotly.express as px

    st.markdown('<div class="section-title">Category Profitability Matrix</div>', unsafe_allow_html=True)
    st.plotly_chart(utils.chart_category_profitability(df), use_container_width=True)

    st.markdown('<div class="section-title">Teacher Performance Overview</div>', unsafe_allow_html=True)
    st.plotly_chart(utils.chart_teacher_performance(df), use_container_width=True)

    st.markdown('<div class="section-title">Category Deep Dive</div>', unsafe_allow_html=True)
    selected_cat = st.selectbox("Select Category", utils.COURSE_CATEGORIES)
    cat_df = df[df['CourseCategory'] == selected_cat]

    if len(cat_df) == 0:
        st.warning("No data available for this category.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        kpi_card("Category Revenue", f"${cat_df['Amount'].sum():,.0f}", c1)
        kpi_card("Enrollments", f"{len(cat_df):,}", c2)
        kpi_card("Avg Course Rating", f"{cat_df['CourseRating'].mean():.2f}", c3)
        kpi_card("Avg Price", f"${cat_df['CoursePrice'].mean():.2f}", c4)

        col_a, col_b = st.columns(2)
        with col_a:
            level_rev = cat_df.groupby('CourseLevel')['Amount'].sum().reset_index()
            fig_lv = px.pie(level_rev, names='CourseLevel', values='Amount',
                            title=f'{selected_cat}: Revenue by Course Level',
                            color_discrete_sequence=['#1f77b4', '#4c9be8', '#89c4f4'])
            st.plotly_chart(fig_lv, use_container_width=True)

        with col_b:
            cat_monthly = cat_df.groupby(cat_df['TransactionDate'].dt.to_period('M'))['Amount'].sum().reset_index()
            cat_monthly['TransactionDate'] = cat_monthly['TransactionDate'].astype(str)
            fig_cm = px.bar(cat_monthly, x='TransactionDate', y='Amount',
                            title=f'{selected_cat}: Monthly Revenue',
                            labels={'Amount': 'Revenue ($)', 'TransactionDate': 'Month'},
                            color='Amount', color_continuous_scale='Blues')
            fig_cm.update_layout(xaxis_tickangle=-30, coloraxis_showscale=False)
            st.plotly_chart(fig_cm, use_container_width=True)

        st.markdown('<div class="section-title">Course-Level Breakdown</div>', unsafe_allow_html=True)
        course_perf = cat_df.groupby(['CourseID', 'CourseName']).agg(
            Revenue=('Amount', 'sum'),
            Enrollments=('TransactionID', 'count'),
            AvgRating=('CourseRating', 'mean'),
            Price=('CoursePrice', 'first'),
            Level=('CourseLevel', 'first'),
        ).reset_index().sort_values('Revenue', ascending=False)
        st.dataframe(course_perf[['CourseName', 'Level', 'Price', 'Revenue', 'Enrollments', 'AvgRating']].round(2).reset_index(drop=True),
                     use_container_width=True)

        st.markdown('<div class="section-title">Strategic Insights</div>', unsafe_allow_html=True)
        avg_rev_enroll = cat_df['Amount'].sum() / len(cat_df) if len(cat_df) > 0 else 0
        top_course = course_perf.iloc[0]['CourseName'] if len(course_perf) > 0 else 'N/A'
        st.markdown(f'<div class="insight-box"><strong>Top Course:</strong> "{top_course}" leads {selected_cat} in revenue. This course should be prioritized for marketing campaigns and instructor development.</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="insight-box"><strong>Revenue Efficiency:</strong> Average revenue per enrollment in {selected_cat} is <strong>${avg_rev_enroll:.2f}</strong>. Focus on moving learners from free to paid tiers to improve this metric.</div>', unsafe_allow_html=True)
