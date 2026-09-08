"""
Notebook 01: Data Preprocessing
EduPro Predictive Modeling Project

Covers: sheet merging, duplicate removal, datatype correction,
missing value handling, outlier analysis, feature normalization,
categorical encoding, and correlation analysis.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
import os

warnings.filterwarnings('ignore')

RANDOM_STATE = 42
DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'EduPro_Online_Platform.xlsx')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed_data.csv')


def load_sheets(path):
    """Load all sheets from the Excel workbook."""
    xl = pd.read_excel(path, sheet_name=None)
    users = xl['Users']
    teachers = xl['Teachers']
    courses = xl['Courses']
    transactions = xl['Transactions']
    print(f"Users: {users.shape}, Teachers: {teachers.shape}, Courses: {courses.shape}, Transactions: {transactions.shape}")
    return users, teachers, courses, transactions


def merge_datasets(users, teachers, courses, transactions):
    """Merge all sheets into a single analytical dataframe."""
    df = transactions.merge(courses, on='CourseID', how='left')
    df = df.merge(teachers, on='TeacherID', how='left')
    df = df.merge(users[['UserID', 'Age', 'Gender']], on='UserID', how='left')
    df.rename(columns={'Age_x': 'UserAge', 'Age_y': 'TeacherAge',
                       'Gender_x': 'UserGender', 'Gender_y': 'TeacherGender'}, inplace=True)
    print(f"Merged dataset shape: {df.shape}")
    return df


def check_duplicates(df):
    """Identify and remove duplicate rows."""
    n_dupes = df.duplicated().sum()
    print(f"Duplicate rows found: {n_dupes}")
    df = df.drop_duplicates().reset_index(drop=True)
    return df


def handle_missing_values(df):
    """Detect and handle missing values."""
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    print(f"Missing values:\n{missing}")

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if df[col].isnull().sum() > 0:
            df[col].fillna(df[col].median(), inplace=True)

    categorical_cols = df.select_dtypes(include=['object', 'string']).columns
    for col in categorical_cols:
        if df[col].isnull().sum() > 0:
            df[col].fillna(df[col].mode()[0], inplace=True)

    print(f"Missing values after imputation: {df.isnull().sum().sum()}")
    return df


def fix_datatypes(df):
    """Correct data types for each column."""
    df['TransactionDate'] = pd.to_datetime(df['TransactionDate'])
    df['CoursePrice'] = pd.to_numeric(df['CoursePrice'], errors='coerce').fillna(0)
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
    df['CourseDuration'] = pd.to_numeric(df['CourseDuration'], errors='coerce').fillna(0)
    df['CourseRating'] = pd.to_numeric(df['CourseRating'], errors='coerce').fillna(df['CourseRating'].mean() if 'CourseRating' in df else 0)
    df['TeacherRating'] = pd.to_numeric(df['TeacherRating'], errors='coerce').fillna(df['TeacherRating'].mean() if 'TeacherRating' in df else 0)
    df['YearsOfExperience'] = pd.to_numeric(df['YearsOfExperience'], errors='coerce').fillna(0).astype(int)
    return df


def detect_outliers_iqr(df, col):
    """Detect outliers using IQR method."""
    Q1 = df[col].quantile(0.25)
    Q3 = df[col].quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    outliers = df[(df[col] < lower) | (df[col] > upper)]
    print(f"  {col}: {len(outliers)} outliers ({len(outliers)/len(df)*100:.1f}%)")
    return lower, upper


def analyze_outliers(df):
    """Analyze outliers in key numerical columns."""
    numeric_targets = ['Amount', 'CoursePrice', 'CourseDuration', 'CourseRating', 'TeacherRating']
    print("Outlier analysis (IQR method):")
    for col in numeric_targets:
        if col in df.columns:
            detect_outliers_iqr(df, col)
    return df


def plot_correlation_heatmap(df):
    """Generate and save correlation heatmap."""
    numeric_df = df.select_dtypes(include=[np.number])
    corr = numeric_df.corr()

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0,
                square=True, ax=ax, cbar_kws={"shrink": 0.8})
    ax.set_title('Feature Correlation Heatmap', fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()
    out = os.path.join(os.path.dirname(__file__), '..', 'reports', 'correlation_heatmap.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Correlation heatmap saved.")
    return corr


def run_preprocessing():
    """Full preprocessing pipeline."""
    users, teachers, courses, transactions = load_sheets(DATA_PATH)
    df = merge_datasets(users, teachers, courses, transactions)
    df = check_duplicates(df)
    df = fix_datatypes(df)
    df = handle_missing_values(df)
    df = analyze_outliers(df)
    corr = plot_correlation_heatmap(df)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nProcessed dataset saved: {OUTPUT_PATH}")
    print(f"Final shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    return df


if __name__ == '__main__':
    df = run_preprocessing()
