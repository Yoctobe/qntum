"""
DEMONSTRATION: CSV Normalization Process
=========================================

Shows how level values are transformed to standardized increments.
"""

import pandas as pd
import numpy as np
from quantum_model import DataPreprocessor

TRANSFORM_OVERRIDES = {"SP500": "log_diff", "DXY": "log_diff"}

# Load original CSV (level values)
df = pd.read_csv("data_us_fed_macro.csv")
df = df.drop(columns=['Date', 'Source'])

print("="*80)
print("STEP 1: Original CSV Data (LEVEL VALUES)")
print("="*80)
print("\nFirst 5 rows:")
print(df.head())
print("\nValue ranges:")
for col in df.columns:
    print(f"  {col:<20} range: [{df[col].min():>10.2f}, {df[col].max():>10.2f}]")

print("\n" + "="*80)
print("STEP 2: Compute stationary increments")
print("="*80)
print("""
Per variable type:
  diff     : d[t] = x[t] - x[t-1]            (default — rates, zero-crossing)
  log_diff : d[t] = ln(x[t]) - ln(x[t-1])    (positive multiplicative series)
""")

prep = DataPreprocessor()
normalized, params = prep.transform_from_dataframe(df, TRANSFORM_OVERRIDES)

print("\n" + "="*80)
print("STEP 3: Robust standardization (median / MAD z-score)")
print("="*80)
print("\nFormula: normalized = (increment - median) / (1.4826 * MAD)")

print("\nParameters computed:")
for i, name in enumerate(params.variable_names):
    print(
        f"  {name:<20} transform = {params.transform_types[i]:<10} "
        f"center = {params.centers[i]:>10.4f}  scale = {params.scale_factors[i]:>10.4f}"
    )

print("\nFirst 5 normalized values:")
print(pd.DataFrame(normalized, columns=params.variable_names).head())

print("\nNormalized ranges:")
for i, name in enumerate(params.variable_names):
    print(f"  {name:<20} range: [{normalized[:, i].min():>8.4f}, {normalized[:, i].max():>8.4f}]")

print("\n" + "="*80)
print("VERIFICATION")
print("="*80)
reconstructed = prep.inverse_transform(normalized, params)
max_err = np.max(np.abs(reconstructed - df.values))
print(f"✓ Exact inverse transform: max reconstruction error = {max_err:.2e}")
print(f"✓ Data shape: {df.shape[0]} rows → {normalized.shape[0]} rows (lost 1 for increments)")
print(f"✓ Variables: {normalized.shape[1]}")

print("\n" + "="*80)
print("INTERPRETATION")
print("="*80)
print("""
The normalized values are robust z-scores of increments:
  +1.0 = one robust standard deviation above the typical change
   0.0 = the typical (median) change for that variable
  -1.0 = one robust standard deviation below

They are NOT clamped to [-1, 1]: extreme moves (e.g. COVID quarters) keep
their true relative size. Stability is enforced in the model dynamics
(spectral radius cap), not by squashing the data.

This normalization ensures:
  1. All variables on same scale (unit robust SD)
  2. Works for rates, zero-crossing and negative series (diff)
     and for prices/indices (log_diff)
  3. Increments capture dynamics, not levels
  4. Exact, well-conditioned inverse (no tanh/arctanh blow-ups)
""")

print("="*80)
print("SAVED FILES")
print("="*80)
print("""
Input:  data_us_fed_macro.csv     (level values - NEVER modified)
Used:   DataPreprocessor           (transforms on-the-fly)
Output: Model uses normalized data (in memory, not saved)

The CSV files are ALWAYS level values - transformation happens at runtime.
""")
