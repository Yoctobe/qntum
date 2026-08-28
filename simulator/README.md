# QNTUM Simulator

Interactive timeline simulator on top of the QNTUM model (`Model/quantum_model`).

- **Time cursor** over past → present → future (24-month horizon by default)
- **Pin any value** at any date: future pins are conditional forecasts (all other
  channels react through the fitted influence matrix); past pins are
  counterfactuals (the model re-simulates from the edit, actual history shown
  dotted for comparison)
- **Event library**: latent shocks (geopolitical conflict, oil supply shock,
  pandemic, financial crisis, fiscal stimulus) calibrated on historical
  analogues; drop one at the cursor, tune intensity / formation / decay
- **New event wizard**: define new latent events (first-hop couplings in
  z-units) or add observable channels from pasted history (couplings auto-fitted)
- **Influence matrix heatmap** of the fitted pairwise structure

## Data

11 monthly channels, 2006 → present, fetched from FRED (+ datahub gold):
CPI inflation (YoY), Fed funds, unemployment, industrial production,
10Y yield, Case-Shiller housing, WTI oil, VIX, broad dollar index, Nasdaq, gold.

Refresh: `python3 backend/fetch_data.py`

## Run

```bash
# Backend (from simulator/backend) — requires: pip install -r requirements.txt
uvicorn app:app --port 8000

# Frontend (from simulator/frontend) — requires: npm install
npm run dev        # → http://localhost:5173
```

## How events are modeled

Every event is (state channel, phase envelope Φ, couplings, history):

- **Observables** (CPI, oil, gold …) have real history; couplings are
  auto-discovered where |r| clears a significance threshold, and the linearized
  dynamics are stabilized by capping the spectral radius of α·Id + β·W.
- **Latent shocks** (war, pandemic …) are exogenous forcings: first-hop weights
  are peak level displacements in z-units, applied through the derivative of Φ
  so effects build, hold, and unwind. Second-hop effects (war → oil → inflation
  → Fed) propagate through the fitted matrix — never encode them in a template.
- **Interventions** (Fed decisions) are just pinned future values.

Engine semantics are validated in `Model/test_simulator.py`.
