"""
utils.py — Shared utility functions for EduPro Streamlit dashboard.

Covers: data loading, model inference, KPI computation,
chart generation, and SHAP explanation helpers.
"""

import pandas as pd
import numpy as np
import os
import warnings
warnings.filterwarnings('ignore')

try:
    import joblib
except ImportError:
    joblib = None

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, '..', 'data', 'processed_data.csv')
MODELS_DIR = os.path.join(BASE_DIR, '..', 'models')

COURSE_CATEGORIES = [
    'Programming', 'Design', 'Business', 'Marketing', 'Data Science',
    'Machine Learning', 'Cybersecurity', 'Project Management', 'Finance',
    'Artificial Intelligence', 'Web Development', 'Digital Marketing'
]
COURSE_LEVELS = ['Beginner', 'Intermediate', 'Advanced']
COURSE_TYPES = ['Paid', 'Free']
PAYMENT_METHODS = ['Credit Card', 'PayPal', 'Bank Transfer']
PRICE_BANDS = ['Free', 'Budget', 'Standard', 'Premium', 'Elite']
DURATION_BUCKETS = ['Short', 'Medium', 'Long', 'Extended']
RATING_TIERS = ['Low', 'Medium', 'High', 'Elite']
EXPERIENCE_BUCKETS = ['Junior', 'Mid', 'Senior', 'Expert']
SEASONALITY_LABELS = ['NewYearRush', 'Spring', 'Summer', 'YearEnd']


# ─── Data Loading ────────────────────────────────────────────────────────────

def load_processed_data():
    """Load the feature-engineered dataset."""
    df = pd.read_csv(DATA_PATH, parse_dates=['TransactionDate'])
    return df


# ─── KPI Computation ─────────────────────────────────────────────────────────

def compute_kpis(df):
    """Compute key performance indicators for the executive dashboard."""
    total_revenue = df['Amount'].sum()
    total_enrollments = len(df)
    avg_course_rating = df['CourseRating'].mean()
    unique_courses = df['CourseID'].nunique()
    unique_teachers = df['TeacherID'].nunique()
    paid_ratio = (df['Amount'] > 0).mean() * 100
    top_category = df.groupby('CourseCategory')['Amount'].sum().idxmax()
    avg_revenue_per_course = total_revenue / unique_courses if unique_courses > 0 else 0

    return {
        'total_revenue': total_revenue,
        'total_enrollments': total_enrollments,
        'avg_course_rating': avg_course_rating,
        'unique_courses': unique_courses,
        'unique_teachers': unique_teachers,
        'paid_ratio': paid_ratio,
        'top_category': top_category,
        'avg_revenue_per_course': avg_revenue_per_course,
    }


# ─── Chart Generators ─────────────────────────────────────────────────────────

def chart_category_revenue(df):
    cat_rev = df.groupby('CourseCategory')['Amount'].sum().reset_index()
    cat_rev.columns = ['Category', 'Revenue']
    cat_rev = cat_rev.sort_values('Revenue', ascending=True)
    fig = px.bar(cat_rev, x='Revenue', y='Category', orientation='h',
                 title='Total Revenue by Course Category',
                 color='Revenue', color_continuous_scale='Blues',
                 labels={'Revenue': 'Total Revenue ($)', 'Category': 'Category'})
    fig.update_layout(coloraxis_showscale=False, height=420)
    return fig


def chart_monthly_revenue(df):
    monthly = df.groupby([df['TransactionDate'].dt.to_period('M')])['Amount'].sum().reset_index()
    monthly['TransactionDate'] = monthly['TransactionDate'].astype(str)
    fig = px.line(monthly, x='TransactionDate', y='Amount',
                  title='Monthly Revenue Trend',
                  labels={'Amount': 'Revenue ($)', 'TransactionDate': 'Month'},
                  markers=True)
    fig.update_traces(line_color='steelblue', line_width=2.5)
    fig.update_layout(height=360)
    return fig


def chart_top_courses(df, n=10):
    course_rev = df.groupby(['CourseID', 'CourseName'])['Amount'].sum().reset_index()
    course_rev.columns = ['CourseID', 'CourseName', 'Revenue']
    top = course_rev.nlargest(n, 'Revenue')
    fig = px.bar(top, x='Revenue', y='CourseName', orientation='h',
                 title=f'Top {n} Courses by Revenue',
                 color='Revenue', color_continuous_scale='Blues',
                 labels={'Revenue': 'Total Revenue ($)', 'CourseName': 'Course'})
    fig.update_layout(coloraxis_showscale=False, height=400)
    return fig


def chart_enrollment_by_category(df):
    enroll = df.groupby('CourseCategory')['TransactionID'].count().reset_index()
    enroll.columns = ['Category', 'Enrollments']
    enroll = enroll.sort_values('Enrollments', ascending=False)
    fig = px.bar(enroll, x='Category', y='Enrollments',
                 title='Enrollment Count by Category',
                 color='Enrollments', color_continuous_scale='Blues',
                 labels={'Enrollments': 'Enrollments', 'Category': 'Category'})
    fig.update_layout(xaxis_tickangle=-45, coloraxis_showscale=False, height=380)
    return fig


def chart_payment_methods(df):
    paid = df[df['Amount'] > 0]
    pm = paid.groupby('PaymentMethod')['Amount'].agg(['sum', 'count']).reset_index()
    pm.columns = ['Method', 'Revenue', 'Count']
    fig = make_subplots(rows=1, cols=2, subplot_titles=('Revenue Share', 'Transaction Count'),
                        specs=[[{"type": "domain"}, {"type": "domain"}]])

    fig.add_trace(go.Pie(labels=pm['Method'], values=pm['Revenue'],
                         name='Revenue', hole=0.4,
                         marker_colors=['#1f77b4', '#4c9be8', '#89c4f4']), row=1, col=1)
    fig.add_trace(go.Pie(labels=pm['Method'], values=pm['Count'],
                         name='Count', hole=0.4,
                         marker_colors=['#1f77b4', '#4c9be8', '#89c4f4']), row=1, col=2)
    fig.update_layout(title='Payment Method Analysis', height=380, showlegend=True)
    return fig


def chart_course_level_comparison(df):
    level_data = df.groupby('CourseLevel').agg(
        Revenue=('Amount', 'sum'),
        Enrollments=('TransactionID', 'count'),
        AvgRating=('CourseRating', 'mean')
    ).reset_index()

    fig = make_subplots(rows=1, cols=3,
                        subplot_titles=('Total Revenue', 'Enrollments', 'Avg Rating'))
    colors = ['#1f77b4', '#4c9be8', '#89c4f4']
    for i, (col, label) in enumerate(zip(['Revenue', 'Enrollments', 'AvgRating'],
                                          ['Revenue ($)', 'Count', 'Rating'])):
        fig.add_trace(go.Bar(x=level_data['CourseLevel'], y=level_data[col],
                             name=label, marker_color=colors[i]), row=1, col=i + 1)
    fig.update_layout(showlegend=False, title='Course Level Analysis', height=380)
    return fig


def chart_teacher_performance(df):
    teachers = df.groupby(['TeacherID', 'TeacherName']).agg(
        Revenue=('Amount', 'sum'),
        Enrollments=('TransactionID', 'count'),
        Rating=('TeacherRating', 'first')
    ).reset_index()
    top10 = teachers.nlargest(10, 'Revenue')

    fig = px.scatter(teachers, x='Rating', y='Revenue', size='Enrollments',
                     hover_name='TeacherName', color='Revenue',
                     color_continuous_scale='Blues',
                     title='Teacher Rating vs Revenue (bubble = enrollments)',
                     labels={'Rating': 'Teacher Rating', 'Revenue': 'Revenue ($)'})
    fig.update_layout(height=400)
    return fig


def chart_category_profitability(df):
    cat = df.groupby('CourseCategory').agg(
        Revenue=('Amount', 'sum'),
        Enrollments=('TransactionID', 'count'),
        AvgPrice=('CoursePrice', 'mean'),
        AvgRating=('CourseRating', 'mean')
    ).reset_index()
    cat['RevenuePerEnrollment'] = cat['Revenue'] / cat['Enrollments'].replace(0, 1)

    fig = px.scatter(cat, x='AvgPrice', y='RevenuePerEnrollment',
                     size='Enrollments', color='AvgRating',
                     hover_name='CourseCategory', text='CourseCategory',
                     color_continuous_scale='Blues',
                     title='Category Profitability Analysis',
                     labels={'AvgPrice': 'Avg Course Price ($)',
                             'RevenuePerEnrollment': 'Revenue per Enrollment ($)',
                             'AvgRating': 'Avg Rating'})
    fig.update_traces(textposition='top center', textfont_size=9)
    fig.update_layout(height=480)
    return fig


# ─── Model Inference ─────────────────────────────────────────────────────────

def _build_input_row(course_category, course_level, course_price, course_duration,
                     teacher_experience, teacher_rating, course_type='Paid',
                     course_rating=4.0, payment_method='Credit Card',
                     transaction_month=6, quarter=2, is_weekend=0):
    """Construct a single input row matching model feature schema."""
    level_map = {'Beginner': 1, 'Intermediate': 2, 'Advanced': 3}
    encoded_level = level_map.get(course_level, 1)

    min_r, max_r = 1.0, 5.0
    teacher_rating_score = (teacher_rating - min_r) / (max_r - min_r + 1e-9)

    price_bins = [-0.01, 0, 50, 100, 200, 500]
    price_labels = ['Free', 'Budget', 'Standard', 'Premium', 'Elite']
    price_band = price_labels[int(np.digitize(course_price, price_bins)) - 1] \
        if course_price >= 0 else 'Free'

    dur_bins = [0, 10, 25, 50, 200]
    dur_labels = ['Short', 'Medium', 'Long', 'Extended']
    dur_bucket = dur_labels[min(int(np.digitize(course_duration, dur_bins)) - 1, 3)]

    def rating_tier(r):
        if r >= 4.5: return 'Elite'
        elif r >= 4.0: return 'High'
        elif r >= 3.0: return 'Medium'
        else: return 'Low'

    def exp_bucket(e):
        if e <= 2: return 'Junior'
        elif e <= 5: return 'Mid'
        elif e <= 10: return 'Senior'
        else: return 'Expert'

    def seasonality(q):
        return {1: 'NewYearRush', 2: 'Spring', 3: 'Summer', 4: 'YearEnd'}.get(q, 'Spring')

    row = {
        'CoursePrice': course_price,
        'CourseDuration': course_duration,
        'CourseRating': course_rating,
        'TeacherRating': teacher_rating,
        'YearsOfExperience': teacher_experience,
        'EncodedCourseLevel': encoded_level,
        'TeacherRatingScore': teacher_rating_score,
        'ExpertiseCategoryMatch': 1,
        'TransactionMonth': transaction_month,
        'Quarter': quarter,
        'IsWeekend': is_weekend,
        'CourseCategory': course_category,
        'CourseType': course_type,
        'PriceBand': price_band,
        'DurationBucket': dur_bucket,
        'RatingTier': rating_tier(course_rating),
        'ExperienceBucket': exp_bucket(teacher_experience),
        'SeasonalityLabel': seasonality(quarter),
        'PaymentMethod': payment_method,
    }
    return pd.DataFrame([row])


def predict_revenue(course_category, course_level, course_price, course_duration,
                    teacher_experience, teacher_rating):
    """Load revenue model and return predicted revenue."""
    import joblib as _joblib
    model_path = os.path.join(MODELS_DIR, 'revenue_model.pkl')
    if not os.path.exists(model_path):
        return None, "Revenue model not found. Run model training first."
    model = _joblib.load(model_path)
    X = _build_input_row(course_category, course_level, course_price, course_duration,
                          teacher_experience, teacher_rating)
    pred = float(model.predict(X)[0])
    pred = max(0.0, pred)
    return pred, None


def predict_enrollment(course_category, course_level, course_price, course_duration,
                       teacher_experience, teacher_rating):
    """Load enrollment model and return predicted enrollments."""
    import joblib as _joblib
    model_path = os.path.join(MODELS_DIR, 'enrollment_model.pkl')
    if not os.path.exists(model_path):
        return None, "Enrollment model not found. Run model training first."
    model = _joblib.load(model_path)
    X = _build_input_row(course_category, course_level, course_price, course_duration,
                          teacher_experience, teacher_rating)
    pred = float(model.predict(X)[0])
    pred = max(1.0, round(pred))
    return pred, None


# ─── SHAP Explainability ─────────────────────────────────────────────────────

def compute_shap_values(model_pipe, X_sample, num_features, cat_features):
    """Compute SHAP values for the final estimator in the pipeline."""
    import shap

    preprocessor = model_pipe.named_steps['preprocessor']
    final_model = model_pipe.named_steps['model']

    X_transformed = preprocessor.transform(X_sample)
    try:
        ohe = preprocessor.named_transformers_['cat']
        cat_names = list(ohe.get_feature_names_out(cat_features))
    except Exception:
        cat_names = []

    all_names = list(num_features) + cat_names
    X_df = pd.DataFrame(X_transformed, columns=all_names[:X_transformed.shape[1]])

    explainer = shap.TreeExplainer(final_model)
    shap_values = explainer.shap_values(X_df)
    return shap_values, X_df, explainer


# ─── Forecast Data ────────────────────────────────────────────────────────────

def load_forecast_results():
    """Load saved Prophet forecast results if available."""
    import joblib as _joblib
    path = os.path.join(MODELS_DIR, 'forecast_results.pkl')
    if os.path.exists(path):
        return _joblib.load(path)
    return None
