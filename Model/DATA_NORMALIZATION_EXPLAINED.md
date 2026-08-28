# Data Normalization - Complete Explanation

## Question: Are the CSV values normalized?

**Short Answer**: No, and that's correct! CSV files contain **level values** (prices, rates, volumes, etc.). The normalization happens **at runtime** when the model loads the data.

## The Process

### Input: CSV Files (Level Values)
```csv
Date,CPI,Fed_Funds_Rate,Unemployment,GDP_Growth,...
2020-03-31,1.5,0.25,4.4,-4.8,...
2020-06-30,0.6,0.25,13.0,-31.2,...
2020-09-30,1.2,0.6,8.8,33.1,...
```

These are **raw level values** - never modified!

### Step 1: Compute a stationary increment (per variable type)

| Transform | Formula | Use for |
|-----------|---------|---------|
| `diff` (default) | `d[t] = x[t] − x[t−1]` | Rates already in % (CPI, Fed funds, unemployment, GDP growth, yields), zero-crossing or negative series (trade balance) |
| `log_diff` (opt-in) | `d[t] = ln(x[t]) − ln(x[t−1])` | Strictly positive multiplicative series (SP500, DXY) |

Example for CPI (`diff`): 1.5 → 0.6 gives d = −0.9 percentage points.
Example for SP500 (`log_diff`): 2584.59 → 3100.29 gives d = ln(3100.29/2584.59) ≈ +0.182.

**Why not % change?** % change is undefined or explosive for zero-crossing
series (GDP growth going −0.8 → 2.4 is a "−400% change"), sign-confused for
negative levels (trade balance), and a persistent % change compounds levels
exponentially on reconstruction. Differencing has none of these failure modes.

### Step 2: Robust standardization (no tanh)
```python
normalized = (d − center) / scale
# center = median(d)
# scale  = 1.4826 · MAD(d)   (≈ std for Gaussian data, outlier-resistant)
```

The result is a robust z-score of roughly unit scale. It is **not** clamped to
[−1, 1]: squashing with tanh made the inverse (arctanh) amplify enormously near
saturation, which blew up forecasts. Boundedness is instead guaranteed by the
**dynamics**: `build_quantum_v2` caps the spectral radius of the linearized
transition matrix `α·Id + β·W` at 0.98, so multi-step forecasts decay toward
"no further change" instead of exploding.

### Result: Standardized increments
- **+1.0** ≈ one robust standard deviation above the typical change
- **0.0** = the typical (median) change for that variable
- **−1.0** ≈ one robust standard deviation below

## Why This Matters

1. **All variables on same scale**: CPI, unemployment, GDP all comparable
2. **Stable dynamics**: stability enforced in the model (spectral radius cap), not by distorting the data
3. **Increments capture dynamics**: not the absolute level, but the change
4. **Exact inverse**: cumulative sum (`diff`) or exp of cumulative sum (`log_diff`) — no arctanh blow-ups
5. **No arbitrary thresholds**: center/scale computed from data, not hardcoded

## Code Flow

```python
# main_v2.py
normalized, params, var_names = load_and_normalize(
    csv_path,
    date_column="Date",
    skip_columns=["Source"],
    transform_overrides={"SP500": "log_diff", "DXY": "log_diff"},
)
# ↓ CSV loaded as level values
# ↓ Transformed to increments (diff / log_diff per variable)
# ↓ Standardized by robust z-score (median / MAD)
# ↓ Model operates on standardized increments

# Build model on normalized data (spectral radius capped for stability)
model = build_quantum_v2(normalized, ...)

# Forecast (in increment space)
forecast = model.forecast(...)

# Convert back to level values for interpretation
forecast_levels = prep.inverse_transform(forecast['point'], params)

# Confidence intervals: inverse-transform each bootstrap path, THEN take
# percentiles in level space (never inverse-transform the percentile paths)
```

## Files

**CSV files** (never change):
- `data_us_fed_macro.csv` - Level values

**Transformation** (runtime):
- `quantum_model/data_preprocessor.py` - Contains normalization logic
- Applied when loading data, not stored

**Model** (operates on):
- Standardized increments (robust z-scores)

**Output** (converted back):
- Forecasts in level values for interpretation

## Visualizations Generated

Run these to see the transformation:

```bash
# Demonstration script
python3 demo_normalization.py

# Visual comparison
python3 demo_visualization.py
```

**Generated plots:**
1. `normalization_comparison.png` - All variables: level vs normalized
2. `normalization_process_cpi.png` - Step-by-step for CPI
3. `financial_forecast.png` - 8-step forecast (level values)

## Key Insight

The CSV files are **intentionally kept as level values** because:
1. That's how data arrives (prices, rates, etc.)
2. Easier to update with new observations
3. Transformation is deterministic and reproducible
4. Can change normalization method without touching data

The model **always** transforms on load, ensuring consistency.

---

**Summary**: CSV = level values (correct) → Runtime transformation (typed differencing + robust z-score) → Model uses standardized increments → Forecasts converted back to levels for interpretation.
