"""
app.py — EduPro Predictive Analytics Dashboard
Multi-page Streamlit application for course demand and revenue forecasting.
"""

import streamlit as st
import pandas as pd
import os
import sys

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
def get_data(data_path, modified_ns):
    return utils.load_processed_data(data_path)


def _get_data_hash() -> str:
    """Generate hash of processed data for cache invalidation."""
    try:
        stat = os.stat(utils.DATA_PATH)
        return f"{stat.st_mtime_ns}_{stat.st_size}"
    except OSError:
        return "no_data"


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
        "<small style='color:#888'>EduPro Analytics v1.2 — Phase 2<br>"
        "Baseline reference estimates + cached Prophet output</small>",
        unsafe_allow_html=True
    )


# ─── Data Availability ───────────────────────────────────────────────────────

try:
    try:
        data_mtime_ns = os.stat(utils.DATA_PATH).st_mtime_ns
    except OSError:
        data_mtime_ns = None
    df = get_data(utils.DATA_PATH, data_mtime_ns)
except utils.DataUnavailableError as exc:
    st.error("Processed data is unavailable, so the dashboard cannot load.")
    st.code(
        "python notebooks/01_data_preprocessing.py\n"
        "python notebooks/03_feature_engineering.py",
        language='bash'
    )
    st.caption(str(exc))
    st.stop()

# Data hash for cache invalidation
data_hash = _get_data_hash()
forecast_hash = utils._get_forecast_hash()


# ─── Page 1: Executive Dashboard ─────────────────────────────────────────────

if page == "Executive Dashboard":
    st.markdown('<div class="main-header">Executive Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Platform-wide performance overview and strategic KPIs</div>', unsafe_allow_html=True)

    kpis = utils.cached_compute_kpis(data_hash, df)

    c1, c2, c3, c4 = st.columns(4)
    kpi_card("Total Revenue", f"${kpis['total_revenue']:,.0f}", c1)
    kpi_card("Total Enrollments", f"{kpis['total_enrollments']:,}", c2)
    kpi_card("Avg Course Rating", f"{kpis['avg_course_rating']:.2f} / 5.0", c3)
    kpi_card("Paid Transaction Share", f"{kpis['paid_ratio']:.1f}%", c4)

    c5, c6, c7, c8 = st.columns(4)
    kpi_card("Active Courses", f"{kpis['unique_courses']}", c5)
    kpi_card("Active Teachers", f"{kpis['unique_teachers']}", c6)
    kpi_card("Top Category", kpis['top_category'], c7)
    kpi_card("Avg Revenue / Course", f"${kpis['avg_revenue_per_course']:,.0f}", c8)

    st.markdown('<div class="section-title">Revenue and Enrollment Trends</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(utils.cached_chart_monthly_revenue(data_hash, df), use_container_width=True)
    with col_b:
        st.plotly_chart(utils.cached_chart_category_revenue(data_hash, df), use_container_width=True)

    st.markdown('<div class="section-title">Top Performing Courses</div>', unsafe_allow_html=True)
    st.plotly_chart(utils.cached_chart_top_courses(data_hash, df, n=10), use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.plotly_chart(utils.cached_chart_enrollment_by_category(data_hash, df), use_container_width=True)
    with col_d:
        st.plotly_chart(utils.cached_chart_payment_methods(data_hash, df), use_container_width=True)

    st.markdown('<div class="section-title">Strategic Insights</div>', unsafe_allow_html=True)
    facts = utils.cached_business_facts(data_hash, df)
    top3 = facts['top3_categories']
    top3_share = facts['top3_share_pct']

    st.markdown(f'<div class="insight-box">The top 3 revenue-generating categories are <strong>{", ".join(top3)}</strong>, collectively accounting for <strong>{top3_share:.1f}%</strong> of total platform revenue.</div>', unsafe_allow_html=True)

    free_enroll = facts['free_transactions']
    free_share = facts['free_share_pct']
    st.markdown(f'<div class="insight-box">Free course transactions account for <strong>{free_enroll:,}</strong> enrollments ({free_share:.1f}% of total). In this dataset paid/free is determined at the course level, so this is a portfolio mix observation rather than a learner conversion rate.</div>', unsafe_allow_html=True)


# ─── Page 2: Course Demand Prediction ────────────────────────────────────────

elif page == "Course Demand Prediction":
    st.markdown('<div class="main-header">Course Demand Prediction</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Reference enrollment estimate and transparent revenue scenarios for a course configuration</div>', unsafe_allow_html=True)


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
            st.caption("Payment method is informational only; it is not used to estimate demand.")

        submitted = st.form_submit_button("Generate Estimate", type="primary")

    if submitted:
        try:
            values = utils.validate_course_inputs(
                category, level, price, duration, teacher_exp, teacher_rating,
                course_type, course_rating, payment_method)
        except ValueError as exc:
            st.error(str(exc))
        else:
            reference, ref_err = utils.cached_enrollment_reference(data_hash, df)
            if ref_err:
                st.error(ref_err)
            else:
                if values['course_type'] == 'Free' and price != 0:
                    st.info("Free courses are normalized to a $0 course price, matching the historical data.")
                expected_rev = utils.calculate_expected_revenue(
                    values['course_type'], values['course_price'], reference['mean'])
                low_rev = utils.calculate_expected_revenue(
                    values['course_type'], values['course_price'], reference['p10'])
                high_rev = utils.calculate_expected_revenue(
                    values['course_type'], values['course_price'], reference['p90'])

                st.markdown('<div class="section-title">Reference Estimate</div>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                kpi_card("Reference Enrollments", f"{reference['mean']:.0f}", c1)
                kpi_card("Historical Range", f"{reference['p10']:.0f}–{reference['p90']:.0f}", c2)
                kpi_card("Expected Revenue at Reference", f"${expected_rev:,.0f}", c3)
                st.caption(
                    "The reference value is the historical course-level average across "
                    f"{reference['n_courses']} courses. It is not a personalized demand forecast. "
                    f"Revenue range from the 10th–90th percentile enrollment range: "
                    f"${low_rev:,.0f}–${high_rev:,.0f}."
                )
                st.warning(
                    "The enrollment model does not beat a mean baseline on this dataset. "
                    "The dashboard therefore shows a historical reference, not a model prediction."
                )

                if values['course_type'] == 'Free':
                    st.info("Free courses generate $0 in transaction revenue in this dataset. Pricing scenarios are disabled for Free courses.")
                else:
                    st.markdown('<div class="section-title">Price Scenario Analysis</div>', unsafe_allow_html=True)
                    diag = utils.cached_price_diagnostics(data_hash, df)
                    corr = diag['paid_price_enrollment_corr']
                    corr_text = 'not defined' if corr is None else f'{corr:.3f}'
                    st.warning(
                        "Price response cannot be estimated from this dataset. "
                        f"There are {diag['unique_paid_prices']} paid prices across "
                        f"{diag['n_paid_courses']} paid courses, and "
                        f"{diag['courses_with_multiple_prices']} course(s) changed price. "
                        f"The paid price/enrollment correlation is {corr_text}. "
                        "The table below is an arithmetic what-if analysis, not a demand forecast. "
                        "No price is recommended."
                    )

                    assumed_change = st.slider(
                        "Assumed enrollment change versus reference (%)",
                        min_value=-50, max_value=50, value=0, step=5,
                        help="Applied equally at every tested price. This is an assumption, not an estimated elasticity."
                    )
                    scenario_prices = sorted(set(
                        [50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0,
                         round(values['course_price'], 2)]
                    ))
                    scenario = utils.get_pricing_scenarios(
                        values['course_price'], reference['mean'],
                        assumed_change_pct=assumed_change, prices=scenario_prices)

                    display = scenario.copy()
                    display['Price'] = display['Price'].map(lambda x: f"${x:,.2f}")
                    display['ProjectedEnrollments'] = display['ProjectedEnrollments'].round(1)
                    display['ProjectedRevenue'] = display['ProjectedRevenue'].map(lambda x: f"${x:,.0f}")
                    display['BreakEvenEnrollmentChangePct'] = display[
                        'BreakEvenEnrollmentChangePct'
                    ].map(lambda x: "n/a" if pd.isna(x) else f"{x:.1f}%")
                    display = display[[
                        'Price', 'ProjectedEnrollments', 'ProjectedRevenue',
                        'BreakEvenEnrollmentChangePct'
                    ]].rename(columns={
                        'Price': 'Price',
                        'ProjectedEnrollments': 'Enrollment Assumption',
                        'ProjectedRevenue': 'Scenario Revenue',
                        'BreakEvenEnrollmentChangePct': 'Break-even Enrollment Change',
                    })
                    st.dataframe(display.reset_index(drop=True), use_container_width=True)
                    st.caption(
                        "Break-even enrollment change is the demand change needed to keep revenue "
                        "unchanged relative to the current price. Positive values mean enrollment could "
                        "rise; negative values mean it would need to fall. It is arithmetic, not a forecast."
                    )

                    import plotly.express as px
                    fig_curve = px.line(
                        scenario, x='Price', y='ProjectedRevenue', markers=True,
                        title='Illustrative Revenue Scenario (Assumption: '
                              f'{assumed_change:+d}% enrollment change)',
                        labels={'Price': 'Course Price ($)',
                                'ProjectedRevenue': 'Scenario Revenue ($)'})
                    fig_curve.add_vline(x=values['course_price'], line_dash='dash',
                                        line_color='red', annotation_text='Current Price')
                    fig_curve.update_layout(height=380)
                    st.plotly_chart(fig_curve, use_container_width=True)
                    st.caption(
                        "This chart is not a demand curve. The dataset has one price per course "
                        "and no within-course price changes, so a price experiment is required "
                        "before making causal pricing decisions."
                    )


# ─── Page 3: Revenue Forecasting ─────────────────────────────────────────────

elif page == "Revenue Forecasting":
    st.markdown('<div class="main-header">Revenue Forecasting</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Historical monthly revenue and cached forecast output; not a validated forecast</div>', unsafe_allow_html=True)


    st.markdown('<div class="section-title">Historical Monthly Revenue</div>', unsafe_allow_html=True)
    st.plotly_chart(utils.cached_chart_monthly_revenue(data_hash, df), use_container_width=True)

    forecast_data, forecast_err = utils.cached_forecast_results(data_hash, forecast_hash)
    if forecast_err:
        st.error(forecast_err)
    elif forecast_data:
        st.warning(
            "This is cached Prophet model output. It has not been backtested in this project "
            "and should not be treated as a validated forecast."
        )
        st.markdown('<div class="section-title">Revenue Forecast (Next 6 Months)</div>', unsafe_allow_html=True)
        rev_fc = forecast_data['revenue']
        import plotly.graph_objects as go
        fig_fc = go.Figure()
        hist = rev_fc[rev_fc['ds'] <= df['TransactionDate'].max()]
        fut = rev_fc[rev_fc['ds'] > df['TransactionDate'].max()]
        fig_fc.add_trace(go.Scatter(x=hist['ds'], y=hist['yhat'], name='Historical Fit',
                                    line=dict(color='steelblue', width=2)))
        fig_fc.add_trace(go.Scatter(x=fut['ds'], y=fut['yhat'], name='Forecast',
                                    line=dict(color='darkorange', width=2, dash='dash')))
        if len(fut):
            fig_fc.add_trace(go.Scatter(
                x=pd.concat([fut['ds'], fut['ds'].iloc[::-1]]),
                y=pd.concat([fut['yhat_upper'], fut['yhat_lower'].iloc[::-1]]),
                fill='toself', fillcolor='rgba(255,165,0,0.15)',
                line=dict(color='rgba(255,255,255,0)'), name='Confidence Interval'))
        fig_fc.update_layout(title='Monthly Revenue Forecast',
                              xaxis_title='Date', yaxis_title='Revenue ($)', height=400)
        st.plotly_chart(fig_fc, use_container_width=True)

        future_rows = fut[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
        future_rows.columns = ['Month', 'Forecast ($)', 'Lower Bound ($)', 'Upper Bound ($)']
        value_columns = ['Forecast ($)', 'Lower Bound ($)', 'Upper Bound ($)']
        future_rows[value_columns] = future_rows[value_columns].round(2)
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

    st.markdown('<div class="section-title">First-to-Last Month Revenue Growth by Category</div>', unsafe_allow_html=True)
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
                            title='First-to-Last Month Revenue Growth by Category')
        fig_growth.update_layout(xaxis_tickangle=-45, height=380)
        st.plotly_chart(fig_growth, use_container_width=True)
        st.caption(
            "This compares the first and last observed months in the dataset. "
            "It is not a year-to-date measure and does not establish a trend."
        )


# ─── Page 4: Feature Importance Explorer ─────────────────────────────────────

elif page == "Feature Importance Explorer":
    st.markdown('<div class="main-header">Model Validity and Data Drivers</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Why the legacy models are not used for demand or pricing decisions</div>', unsafe_allow_html=True)

    facts = utils.cached_business_facts(data_hash, df)
    diagnostics = utils.cached_price_diagnostics(data_hash, df)
    reference, ref_err = utils.cached_enrollment_reference(data_hash, df)

    st.error(
        "Legacy revenue model retired: transaction Amount is an accounting identity with "
        "CoursePrice (Amount = CoursePrice for paid rows, $0 for free rows). Its R² = 1.0 "
        "reflects target leakage, not predictive skill."
    )
    st.warning(
        "The legacy enrollment model does not beat a mean baseline under a valid evaluation. "
        "Feature-importance and SHAP charts are therefore disabled until a model is validated "
        "against the baseline and persisted with its evaluation metadata."
    )

    st.markdown('<div class="section-title">Data-Verified Portfolio Facts</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    kpi_card("Free Transaction Share", f"{facts['free_share_pct']:.2f}%", c1)
    kpi_card("Paid Courses", f"{facts['paid_courses']}", c2)
    kpi_card("Free Courses", f"{facts['free_courses']}", c3)
    kpi_card("Top 3 Revenue Share", f"{facts['top3_share_pct']:.2f}%", c4)
    st.markdown(
        f'<div class="insight-box">Top revenue categories: <strong>{", ".join(facts["top3_categories"])}</strong>. '
        f'Machine Learning revenue is <strong>${facts["machine_learning_revenue"]:,.2f}</strong>; '
        f'Marketing revenue is <strong>${facts["marketing_revenue"]:,.2f}</strong>.</div>',
        unsafe_allow_html=True
    )

    st.markdown('<div class="section-title">Descriptive Enrollment Associations</div>', unsafe_allow_html=True)
    if ref_err:
        st.error(ref_err)
    else:
        st.caption(
            f"Historical reference enrollment: mean {reference['mean']:.1f}, "
            f"10th–90th percentile {reference['p10']:.0f}–{reference['p90']:.0f} "
            f"across {reference['n_courses']} courses. These are descriptive statistics, not a model."
        )
    st.plotly_chart(utils.cached_chart_enrollment_by_category(data_hash, df), use_container_width=True)

    st.markdown('<div class="section-title">Price-Response Evidence</div>', unsafe_allow_html=True)
    corr = diagnostics['paid_price_enrollment_corr']
    corr_text = "not defined" if corr is None else f"{corr:.3f}"
    st.markdown(
        f'<div class="insight-box">Paid courses: <strong>{diagnostics["n_paid_courses"]}</strong>; '
        f'unique paid prices: <strong>{diagnostics["unique_paid_prices"]}</strong>; '
        f'courses with more than one price: <strong>{diagnostics["courses_with_multiple_prices"]}</strong>; '
        f'paid price/enrollment correlation: <strong>{corr_text}</strong>.<br>'
        f'{diagnostics["reason"]}</div>',
        unsafe_allow_html=True
    )
    st.caption(
        "A valid feature-importance or SHAP result requires a model that beats a simple baseline "
        "on a held-out evaluation. No such model exists in this project."
    )


# ─── Page 5: Category Analytics ──────────────────────────────────────────────

elif page == "Category Analytics":
    st.markdown('<div class="main-header">Category Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Deep-dive into course category revenue, teacher associations, and growth</div>', unsafe_allow_html=True)

    import plotly.express as px

    st.markdown('<div class="section-title">Category Revenue Efficiency Matrix</div>', unsafe_allow_html=True)
    st.plotly_chart(utils.cached_chart_category_revenue_efficiency(data_hash, df), use_container_width=True)
    st.caption("Revenue per enrollment is descriptive. The dataset has no cost, margin, or profit data.")

    st.markdown('<div class="section-title">Teacher Performance Overview</div>', unsafe_allow_html=True)
    st.plotly_chart(utils.cached_chart_teacher_performance(data_hash, df), use_container_width=True)

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
        kpi_card("Avg Price (all courses)", f"${cat_df['CoursePrice'].mean():.2f}", c4)

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
        st.markdown(f'<div class="insight-box"><strong>Top Course:</strong> "{top_course}" has the highest historical revenue in {selected_cat}. This is a descriptive observation, not a causal recommendation.</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="insight-box"><strong>Revenue Efficiency:</strong> Average revenue per enrollment in {selected_cat} is <strong>${avg_rev_enroll:.2f}</strong>, including free enrollments. Paid/free is a course-level attribute here, so this is not a learner conversion rate.</div>', unsafe_allow_html=True)
