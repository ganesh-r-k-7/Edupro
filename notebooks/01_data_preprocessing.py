"""
Notebook 01: Data Preprocessing
EduPro Predictive Modeling Project

Covers: sheet merging, duplicate removal, datatype correction,
missing value handling, outlier analysis, feature normalization,
categorical encoding, and correlation analysis.
"""

import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

# Ensure shared package is importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from edup.data import load_raw_data, preprocess_data
from edup.config import PROCESSED_DATA_PATH


RANDOM_STATE = 42


def plot_correlation_heatmap(df: pd.DataFrame):
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
    print("Correlation heatmap saved.")
    return corr


def run_preprocessing():
    """Full preprocessing pipeline."""
    xl = load_raw_data()
    df = preprocess_data(xl, output_path=PROCESSED_DATA_PATH)
    plot_correlation_heatmap(df)
    print(f"\nProcessed dataset saved: {PROCESSED_DATA_PATH}")
    print(f"Final shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    return df


if __name__ == '__main__':
    df = run_preprocessing()