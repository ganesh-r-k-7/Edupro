"""
Notebook 02: Exploratory Data Analysis
EduPro Predictive Modeling Project

Produces professional-grade visualizations covering:
revenue distributions, enrollment distributions, category analysis,
pricing, teacher performance, time trends, payment methods, demographics.
"""

import pandas as pd
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed_data.csv')
REPORTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')

sns.set_theme(style='whitegrid', palette='Blues_r')
plt.rcParams.update({'font.family': 'DejaVu Sans', 'axes.titlesize': 13,
                     'axes.labelsize': 11, 'figure.dpi': 120})


def load_data():
    return pd.read_csv(DATA_PATH, parse_dates=['TransactionDate'])


def plot_revenue_distribution(df):
    paid = df[df['Amount'] > 0]['Amount']
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].hist(paid, bins=40, color='steelblue', edgecolor='white', alpha=0.85)
    axes[0].set_title('Revenue Distribution (Paid Transactions)')
    axes[0].set_xlabel('Transaction Amount ($)')
    axes[0].set_ylabel('Frequency')

    axes[1].boxplot(paid, vert=False, patch_artist=True,
                    boxprops=dict(facecolor='steelblue', alpha=0.7))
    axes[1].set_title('Revenue Boxplot')
    axes[1].set_xlabel('Transaction Amount ($)')

    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_revenue_distribution.png'), bbox_inches='tight')
    plt.close()
    print(f"Revenue stats: mean=${paid.mean():.2f}, median=${paid.median():.2f}, max=${paid.max():.2f}")


def plot_category_revenue(df):
    cat_rev = df.groupby('CourseCategory')['Amount'].sum().sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(10, 7))
    cat_rev.plot(kind='barh', ax=ax, color='steelblue', edgecolor='white', alpha=0.85)
    ax.set_title('Total Revenue by Course Category')
    ax.set_xlabel('Total Revenue ($)')
    ax.set_ylabel('Course Category')
    for bar in ax.patches:
        ax.text(bar.get_width() + cat_rev.max() * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f'${bar.get_width():,.0f}', va='center', fontsize=9)
    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_category_revenue.png'), bbox_inches='tight')
    plt.close()


def plot_enrollment_by_category(df):
    enroll = df.groupby('CourseCategory')['TransactionID'].count().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(12, 5))
    enroll.plot(kind='bar', ax=ax, color='steelblue', edgecolor='white', alpha=0.85)
    ax.set_title('Enrollment Count by Course Category')
    ax.set_xlabel('Course Category')
    ax.set_ylabel('Number of Enrollments')
    ax.tick_params(axis='x', rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_enrollment_by_category.png'), bbox_inches='tight')
    plt.close()


def plot_monthly_revenue_trend(df):
    monthly = df.groupby(['Year', 'TransactionMonth'])['Amount'].sum().reset_index()
    monthly['Period'] = pd.to_datetime(monthly['Year'].astype(str) + '-' +
                                        monthly['TransactionMonth'].astype(str))
    monthly = monthly.sort_values('Period')

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(monthly['Period'], monthly['Amount'], color='steelblue', lw=2.5, marker='o', ms=5)
    ax.fill_between(monthly['Period'], monthly['Amount'], alpha=0.15, color='steelblue')
    ax.set_title('Monthly Revenue Trend')
    ax.set_xlabel('Month')
    ax.set_ylabel('Total Revenue ($)')
    ax.tick_params(axis='x', rotation=30)
    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_monthly_revenue.png'), bbox_inches='tight')
    plt.close()


def plot_pricing_analysis(df):
    courses = df.drop_duplicates('CourseID')[['CourseCategory', 'CoursePrice', 'CourseType', 'CourseLevel']]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    cat_price = courses.groupby('CourseCategory')['CoursePrice'].mean().sort_values(ascending=False)
    cat_price.plot(kind='bar', ax=axes[0], color='steelblue', edgecolor='white', alpha=0.85)
    axes[0].set_title('Average Course Price by Category')
    axes[0].set_xlabel('Category')
    axes[0].set_ylabel('Average Price ($)')
    axes[0].tick_params(axis='x', rotation=45)

    type_counts = courses['CourseType'].value_counts()
    axes[1].pie(type_counts, labels=type_counts.index, autopct='%1.1f%%',
                colors=['steelblue', 'lightblue'], startangle=90)
    axes[1].set_title('Free vs Paid Course Distribution')

    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_pricing_analysis.png'), bbox_inches='tight')
    plt.close()


def plot_teacher_performance(df):
    teachers = df.groupby('TeacherID').agg(
        Revenue=('Amount', 'sum'),
        Enrollments=('TransactionID', 'count'),
        AvgRating=('TeacherRating', 'first'),
        Name=('TeacherName', 'first')
    ).reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    top10 = teachers.nlargest(10, 'Revenue')
    axes[0].barh(top10['Name'], top10['Revenue'], color='steelblue', edgecolor='white', alpha=0.85)
    axes[0].set_title('Top 10 Teachers by Revenue Generated')
    axes[0].set_xlabel('Total Revenue ($)')

    axes[1].scatter(teachers['AvgRating'], teachers['Revenue'],
                    c='steelblue', alpha=0.7, s=60, edgecolors='none')
    axes[1].set_title('Teacher Rating vs Revenue Generated')
    axes[1].set_xlabel('Teacher Rating')
    axes[1].set_ylabel('Total Revenue ($)')

    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_teacher_performance.png'), bbox_inches='tight')
    plt.close()


def plot_payment_methods(df):
    paid = df[df['Amount'] > 0]
    pm = paid.groupby('PaymentMethod')['Amount'].agg(['sum', 'count']).reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(pm['PaymentMethod'], pm['sum'], color='steelblue', edgecolor='white', alpha=0.85)
    axes[0].set_title('Revenue by Payment Method')
    axes[0].set_ylabel('Total Revenue ($)')

    axes[1].bar(pm['PaymentMethod'], pm['count'], color='steelblue', edgecolor='white', alpha=0.85)
    axes[1].set_title('Transaction Count by Payment Method')
    axes[1].set_ylabel('Count')

    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_payment_methods.png'), bbox_inches='tight')
    plt.close()


def plot_course_level_comparison(df):
    level_rev = df.groupby('CourseLevel').agg(
        TotalRevenue=('Amount', 'sum'),
        AvgRating=('CourseRating', 'mean'),
        Enrollments=('TransactionID', 'count')
    ).reset_index()

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, col, label in zip(axes, ['TotalRevenue', 'AvgRating', 'Enrollments'],
                               ['Total Revenue ($)', 'Avg Course Rating', 'Enrollment Count']):
        axes[list(axes).index(ax)].bar(level_rev['CourseLevel'], level_rev[col],
                                        color='steelblue', edgecolor='white', alpha=0.85)
        ax.set_title(f'{label} by Course Level')
        ax.set_xlabel('Course Level')
        ax.set_ylabel(label)

    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_course_level_comparison.png'), bbox_inches='tight')
    plt.close()


def plot_gender_age_analysis(df):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    gender_rev = df.groupby('UserGender')['Amount'].sum()
    axes[0].pie(gender_rev, labels=gender_rev.index, autopct='%1.1f%%',
                colors=['steelblue', 'lightcoral', 'lightgreen'], startangle=90)
    axes[0].set_title('Revenue Share by User Gender')

    df['AgeGroup'] = pd.cut(df['UserAge'], bins=[0, 18, 25, 35, 50, 100],
                             labels=['<18', '18-25', '25-35', '35-50', '50+'])
    age_rev = df.groupby('AgeGroup')['Amount'].sum()
    axes[1].bar(age_rev.index.astype(str), age_rev.values,
                color='steelblue', edgecolor='white', alpha=0.85)
    axes[1].set_title('Revenue by User Age Group')
    axes[1].set_xlabel('Age Group')
    axes[1].set_ylabel('Total Revenue ($)')

    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'eda_demographics.png'), bbox_inches='tight')
    plt.close()


def run_eda():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    df = load_data()
    print(f"Running EDA on {df.shape[0]} records...")
    plot_revenue_distribution(df)
    plot_category_revenue(df)
    plot_enrollment_by_category(df)
    plot_monthly_revenue_trend(df)
    plot_pricing_analysis(df)
    plot_teacher_performance(df)
    plot_payment_methods(df)
    plot_course_level_comparison(df)
    plot_gender_age_analysis(df)
    print("EDA complete. All charts saved to reports/")


if __name__ == '__main__':
    run_eda()
