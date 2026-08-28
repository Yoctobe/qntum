"""
Visual comparison: Level values vs standardized increments
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from quantum_model import DataPreprocessor

TRANSFORM_OVERRIDES = {"SP500": "log_diff", "DXY": "log_diff"}

# Load data
df = pd.read_csv("data_us_fed_macro.csv")
df = df.drop(columns=['Date', 'Source'])

# Normalize
prep = DataPreprocessor()
normalized, params = prep.transform_from_dataframe(df, TRANSFORM_OVERRIDES)

# Create visualization
fig, axes = plt.subplots(4, 2, figsize=(16, 12))
axes = axes.flatten()

variables = params.variable_names

for i, (var, ax) in enumerate(zip(variables, axes)):
    ax2 = ax.twinx()
    
    # Level values (blue, left axis)
    x_level = np.arange(len(df))
    ax.plot(x_level, df[var].values, 'o-', color='C0', linewidth=2, markersize=4, label='Level values')
    ax.set_ylabel('Level values', color='C0', fontsize=10)
    ax.tick_params(axis='y', labelcolor='C0')
    ax.grid(True, alpha=0.3)
    
    # Normalized values (orange, right axis)
    x_norm = np.arange(1, len(df))  # Start at 1 because we lose first value for increments
    ax2.plot(x_norm, normalized[:, i], 's--', color='C1', linewidth=2, markersize=4, label='Standardized increment')
    ax2.set_ylabel('Robust z-score', color='C1', fontsize=10)
    ax2.tick_params(axis='y', labelcolor='C1')
    ax2.axhline(0, color='gray', linestyle=':', alpha=0.5)
    
    ax.set_title(f'{var} ({params.transform_types[i]})', fontsize=12, fontweight='bold')
    ax.set_xlabel('Time step', fontsize=10)
    
    # Combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=8)

plt.suptitle(
    'Level Values (blue, left axis) vs Standardized Increments (orange, right axis)',
    fontsize=14,
    fontweight='bold',
    y=0.995
)
plt.tight_layout()
plt.savefig('normalization_comparison.png', dpi=150, bbox_inches='tight')
print("✓ Saved: normalization_comparison.png")
plt.close()

# Also create a simpler single-variable demo
fig, axes = plt.subplots(3, 1, figsize=(14, 10))

# Use CPI as example
var_idx = 0
var_name = "CPI"

# 1. Level values
axes[0].plot(df[var_name].values, 'o-', color='C0', linewidth=2, markersize=6)
axes[0].set_title('STEP 1: Original Level Values (from CSV)', fontsize=12, fontweight='bold')
axes[0].set_ylabel('CPI (%)', fontsize=11)
axes[0].grid(True, alpha=0.3)
axes[0].set_xlim(-1, len(df))

# 2. Increment (first difference — CPI is already a rate)
increments = df[var_name].diff().iloc[1:].values
axes[1].plot(increments, 's-', color='C2', linewidth=2, markersize=6)
axes[1].axhline(0, color='gray', linestyle='--', alpha=0.5)
axes[1].set_title('STEP 2: Increment = value[t] - value[t-1]  (transform: diff)', fontsize=12, fontweight='bold')
axes[1].set_ylabel('Change (pp)', fontsize=11)
axes[1].grid(True, alpha=0.3)
axes[1].set_xlim(-1, len(df))

# 3. Standardized
axes[2].plot(normalized[:, var_idx], 's-', color='C1', linewidth=2, markersize=6)
axes[2].axhline(0, color='gray', linestyle='--', alpha=0.5)
axes[2].set_title('STEP 3: Standardized = (increment - median) / (1.4826 · MAD)', fontsize=12, fontweight='bold')
axes[2].set_ylabel('Robust z-score', fontsize=11)
axes[2].grid(True, alpha=0.3)
axes[2].set_xlabel('Time step', fontsize=11)
axes[2].set_xlim(-1, len(df))

plt.suptitle(
    f'Normalization Process: {var_name}',
    fontsize=14,
    fontweight='bold',
    y=0.995
)
plt.tight_layout()
plt.savefig('normalization_process_cpi.png', dpi=150, bbox_inches='tight')
print("✓ Saved: normalization_process_cpi.png")
plt.close()

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("""
Two visualizations created:

1. normalization_comparison.png
   → All 8 variables side-by-side (level vs normalized)
   
2. normalization_process_cpi.png
   → Step-by-step transformation for CPI

Key points:
  - CSV files contain LEVEL values (never modified)
  - Transformation happens at runtime via DataPreprocessor
  - Model operates on STANDARDIZED INCREMENTS (diff / log_diff + robust z-score)
  - Forecasts are inverse-transformed back to level values for interpretation
""")
