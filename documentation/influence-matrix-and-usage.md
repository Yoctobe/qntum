# Influence Matrix, Math Alignment & Usage

## Influence matrix as a flexible deterministic tool

The influence matrix $I$ is the **central math tool** for:

- **Interactions** — how component A affects component B (and vice versa), whether they are macroeconomic parameters, physical properties (temperature, volume, density, pressure), or any other quantities.
- **Value updates** — the model uses $I$ in the recurrence to compute the next state from the current state; $I$ therefore encodes who influences whom and by how much.

In the real world, components influence each other via **linear or nonlinear** relationships. The framework treats these in a **deterministic** way:

- **Linear:** $I_{ij}$ is the constant coefficient of $j$ on $i$ in a linearized one-step update (e.g. $\Delta x_i \propto \sum_j I_{ij}\, x_j$). Suitable for small changes, linearized physics, or macro.
- **Nonlinear:** Nonlinear relationships can be handled by (1) **pre-transforming** variables so that linear $I$ in transformed space captures the nonlinearity (e.g. log prices, ratios), or (2) **theory-based** $I_{ij}$ that you set from known laws (e.g. ideal gas, Taylor rule) and optionally estimate the rest from data.

**Pinning known relationships and letting the model guess the rest:** You can **pin** both linear and nonlinear relationships in **$I_{\mathrm{known}}$** and let the package **estimate the rest** from data:

- **Pin linear:** set $I_{\mathrm{known}}[i,j]$ to a **finite scalar** (e.g. 0.9 for persistence, -0.4 for a known linear effect). That pair is fixed as a linear weight; no fitting.
- **Pin nonlinear:** set $I_{\mathrm{known}}[i,j]$ to a **callable** (e.g. `lambda x: -0.4*x - 0.1*x**2`). That pair uses your exact formula; no fitting.
- **Let the model guess:** set $I_{\mathrm{known}}[i,j]$ to **NaN** (or leave it unspecified). The package then **auto-detects** the best form per pair (linear, poly, or RBF) from data and fits only those entries.

So you fix what you know from theory or calibration (linear or nonlinear), and the model **fills in the rest** deterministically from data. $I$ becomes part from you, part from data — reliable and flexible.

---

## How the influence matrix is defined and obtained

**The QNTUM model does not compute the influence matrix.** It is an **input** to the model. You must provide a square matrix $I$ where:

- $I_{ij}$ = **constant** influence of component (event) $j$ on component $i$.
- Interpretation: “If component $j$ has magnitude 1 and all others are 0, how much does component $i$ move in one step?” (at fixed scale).
- **Determinism:** without noise, these amplitudes are invariant — same cause → same effect (e.g. “kick ball with energy E → distance D, always”).

### Ways to obtain $I$ (domain-dependent)

| Domain | Possible approach |
|--------|-------------------|
| **Physics** | From theory or experiments: coupling constants, transfer coefficients, Green’s functions, etc. |
| **Finance / macro** | Calibrated from historical relationships (e.g. regression, Granger, or use correlation/cross-impact as a **proxy** for $I$, then scale). |
| **Generic** | Expert judgment, cross-impact tables, or any method that yields a square matrix of interaction strengths. |

**Important:**  
- $I$ is defined **at a reference scale** (e.g. magnitude 1). The dynamics then scale it with $\beta$ and the current magnitudes $M_j(t)$.  
- The model assumes $I$ is **constant** over the simulation unless you explicitly expand it (e.g. when adding a future event).  
- Diagonal $I_{ii}$: self-influence (stabilisation or destabilisation). Off-diagonal $I_{ij}$: effect of $j$ on $i$.

### Input data requirement

**Data used to estimate $I$ (or to run backtests) must be in level values**, not normalized. Use raw levels (e.g. temperature in K, volume in L, GDP in level, prices in level). Do not feed z-scores, min-max scaled series, or change-only series as if they were levels — the model and influence estimation assume level inputs; internal z-scaling or differencing is applied where needed (e.g. in change-space backtests).

**Why level data can still predict poorly (e.g. mixed or negative correlations):**
- **Short series** — With few rows (e.g. &lt; 20), the train half is very small. The influence matrix and drift are estimated from few one-step pairs, so they are unstable and can overfit or default to “constant drift”.
- **Drift dominance** — In change-space, if the estimated drift weight is high (e.g. 1.0), predictions are close to “repeat mean historical change” every step. When the test period has different dynamics (e.g. mean reversion, sign flips), predicted and actual can be anti-aligned → negative correlations.
- **Scale and regime** — Levels with large range trigger change-space (universal) and z-scoring. If the second half of the sample has a different trend or volatility, the same $I$ and drift fit to the first half will not match, so some variables can show good correlation and others strong negative correlation.
- **Recommendation** — Use longer level series where possible; or try level-space (optimal) when the data are stationary enough (e.g. after detrending or on shorter, stable windows).

### Built-in computation in the package (`quantum_model.influence`)

The package provides a **mechanism to estimate $I$ from data** so you don’t have to hand-pick it:

1. **Regression (recommended)** — `compute_influence(data, method="regression", ...)`  
   - Fits one-step-ahead dynamics: $x_i(t+1) \approx \sum_j I_{ij}\, x_j(t)$ for each variable $i$.  
   - Row $i$ of $I$ is the regression coefficients of $x_i(t+1)$ on $x_1(t),\ldots,x_n(t)$.  
   - Uses **Ridge regression** when the number of time points is small to avoid overfitting.  
   - Parameters: `alpha` (Ridge strength), `clip` (bound entries to $[-1,1]$), `diagonal_scale`.

2. **Correlation (fallback)** — `compute_influence(data, method="correlation", ...)`  
   - $I$ is built from the correlation matrix of the time series (clipped and scaled).  
   - Use when you have very few rows; regression is more accurate when you have enough data.

**Optimal (default):** `compute_influence(train_data, method="optimal", clip=1.0)` — when T-1 ≥ 2n uses Ridge regression; when T-1 < 2n uses a 50/50 blend of Ridge and lead-lag. See `examples/benchmark_influence_formulas.py`.

**Universal (one formula for linear and nonlinear):** `compute_influence(train_data, method="universal", clip=1.0)` — estimates $I$ in **change space**: $\Delta(t+1) = I\,\Delta(t) + c$ with $\Delta(t) = x(t) - x(t-1)$. Level relationships (linear or nonlinear) linearize in changes, so one $I$ fits both. Use with **change-space simulation**: $x(t+1) = x(t) + I\,\Delta(t)$, $\Delta(t) = x(t) - x(t-1)$. Recommended for level/physics data (e.g. `data_physics_nitrogen.csv`).

**Supplementing known relationships (scalar $I$):**  
`compute_influence(data, method="...", I_known=I_known)`  
- Use **finite** values where $I_{ij}$ is known; **NaN** where it should be estimated. Only non-finite entries are fitted; known entries are kept.

**Nonlinear influence (per-pair $f_{ij}$) — pin linear and nonlinear, model guesses the rest:**  
When the scalar model is too restrictive, use the **nonlinear influence matrix**: $x_i(t+1) = \sum_j f_{ij}(x_j(t))$. Each pair $(i,j)$ can be **pinned** (linear or nonlinear) or **left to the model**:

| $I_{\mathrm{known}}[i,j]$ | Meaning | Fitting |
|---------------------------|--------|--------|
| **Finite scalar** (e.g. 0.9) | Pin **linear** relationship $f_{ij}(x) = a\,x$ with that weight | None — fixed |
| **Callable** (e.g. `lambda x: -0.4*x - 0.1*x**2`) | Pin **nonlinear** relationship — your exact formula | None — fixed |
| **NaN** | Let the model **guess** this pair | Auto-detect (linear / poly / RBF) and fit from data |

- Use `compute_nonlinear_influence(data, I_known=I_known)` from `quantum_model`. Build $I_{\mathrm{known}}$ as a list-of-lists or object array when mixing scalars and callables; load from JSON only supports scalars/NaN.
- **Backtest:** `python3 examples/backtest_general.py [path_to_csv]`. Uses this nonlinear matrix; in change-space with very short series it may fall back to scalar $I$ for stability.

---

## Math definitions: model alignment

The implementation follows the QNTUM maths exactly.

### 1. Phase function $\Phi(E_i, t)$

$$
\Phi(E_i, t) =
\begin{cases}
0 & t < t_0 \\
\dfrac{t - t_0}{t_f} & t_0 \le t < t_0 + t_f \\
1 & t_0 + t_f \le t < t_0 + t_f + \tau \\
e^{-(t - (t_0 + t_f + \tau))/\tau} & t \ge t_0 + t_f + \tau
\end{cases}
$$

- **Code:** `QuantumModel.phase(t, event)` implements this piecewise (Inactive → Formation → Stable → Decay).  
- Inactive events have magnitude 0; when $\Phi = 0$ the event does not contribute to the network term.

### 2. Magnitude update

**Default (bounded) mode:**  
Scale current magnitudes for the influence term: $\tilde{M}_j = M_j / \max_k |M_k|$ (so interactions use fixed scale). Then
$$
M_i(t+1) = B_i + \alpha\, M_i(t) + \beta\, \Phi(E_i,t)\, \sum_j I_{ij}\, \tilde{M}_j(t).
$$
After the update: if $\max_i |M_i(t+1)| > 1$, scale by that max; then clamp to $[-1, 1]$.

**Linear dynamics mode** (`linear_dynamics=True`):  
No scaling: use $M_j(t)$ directly in the sum; no post-step scale or clamp. So
$M(t+1) = B + \alpha M(t) + \beta\,\Phi\, (I\,M(t))$; with $\alpha=0$, $\beta=1$, $\Phi=1$: $M(t+1) = B + I\,M(t)$.

- **Code:** `_update_magnitudes`; `_normalize_for_influence` (default: $\tilde{M} = M/\max|M|$); `_normalize_step` (scale then clamp). With `linear_dynamics=True`, both normalisations are skipped.  
- $B_i$ = `event.base_level`, $\alpha$ = `alpha`, $\beta$ = `beta`, $I$ = `influence_matrix`.

### 3. Influence matrix $I$

- **Structure:** square; $I_{ij}$ = effect of $j$ on $i$.  
- **Provided by the user** — the library never estimates or modifies $I$ except when expanding for a future event (new row/column).  
- So: **how the influence matrix is calculated** is entirely up to your application (theory, calibration, correlation-based proxy, etc.); the model only **uses** it.

---

## Universality: physics and finance

The model is **domain-agnostic**:

- **Physics:** components = physical quantities (e.g. fields, concentrations); $I$ from coupling constants; magnitudes in $[-1,1]$ can represent normalised deviations or activations.  
- **Finance / macro:** components = economic variables (e.g. inflation, rates, GDP); $I$ from structural relationships or empirical proxies; magnitudes = normalised changes or scores.

Same equations, same code; only the meaning of “event” and the way $I$ is obtained change.

---

## State at any future time

Given:

- Initial magnitudes at $t_0$ (e.g. current state),  
- Events (with $t_0, t_f, \tau, B_i$, initial_magnitude),  
- Influence matrix $I$ and parameters $\alpha, \beta$,  

the model **produces the state (magnitudes) at every future time step** in $[t_0, t_{\mathrm{end}}]$ with step `dt`. So you can read off **any** future date that falls on the time grid (e.g. next quarter, next year).

---

## Example: forecasting inflation at future dates

Below: a minimal example that forecasts **Inflation_Change** (and other variables) at specific future dates using `data.csv`. The influence matrix here is built from **historical correlations** as a simple proxy for $I$; in production you would replace this with a proper calibration or structural model.

### Data and setup

- **Input:** `data.csv` with columns including `Inflation_Change`, `Interest_Rate_Change`, `GDP_Change`, etc., and a `Date` index (e.g. quarterly).  
- **Goal:** Forecast magnitudes (e.g. inflation change) at future dates: e.g. 2024 Q2, 2024 Q3, 2024 Q4, 2025 Q1.

### Steps (conceptually)

1. **Define components** — one “event” per variable (e.g. Inflation_Change, Interest_Rate_Change, …).  
2. **Obtain $I$** — e.g. correlation matrix of historical changes, clipped and scaled to $[-1,1]$, with diagonal set to a self-influence value (one possible proxy; not the only way).  
3. **Set initial state** — last row of the dataset as `initial_magnitude` for each event, base_level from the previous period if desired.  
4. **Run simulation** — `model.simulate(events, t_end=T, dt=1)` with time unit = 1 quarter.  
5. **Map time index to dates** — e.g. $t=0$ = 2024 Q1, $t=1$ = 2024 Q2, … and read magnitudes at those indices.  
6. **Inflation forecast** — the series `magnitudes[:, inflation_index]` gives the forecast path; sample at the desired future dates.

### Minimal code (runnable)

See the script **`examples/forecast_inflation.py`** in the Model folder. It:

- Loads `data.csv`,  
- Builds a 7×7 influence matrix from historical correlations (as a proxy),  
- Creates one event per column (with $t_0=0$, formation/decay chosen for quarterly horizon),  
- Sets initial magnitudes from the latest row,  
- Runs `simulate(events, t_end=4, dt=1)` (4 quarters ahead),  
- Prints and (optionally) plots **Inflation_Change** (and others) at future quarters with explicit dates.

So: **how the influence matrix is calculated** in that example is “correlation-based proxy”; the **model** only consumes $I$ and the rest of the inputs and returns the state at every future point, including inflation at the dates you choose.
