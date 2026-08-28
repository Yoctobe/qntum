"""
Generates two illustrative synthetic panels to demonstrate QNTUM outside
finance: a medical (physiological) system and an ecological system. Both
are coupled, nonlinear, multi-variable dynamics with literature-typical
constants — the same "known ground truth, then let the model discover it"
pattern used by Model/quantum_model/physics_tests.py.

Run once to (re)generate the CSVs consumed by simulator/backend/app.py:
    python3 generate_example_domains.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "simulator" / "backend" / "data"


# ══════════════════════════════════════════════════════════════════════════
# MEDICAL: glucose–insulin regulation
# ══════════════════════════════════════════════════════════════════════════
# A daily-timescale analogue of the Bergman minimal model (Bergman et al.
# 1979; Pacini & Bergman 1986): glucose G is cleared both on its own (p1)
# and via insulin-mediated uptake (X); insulin action X decays and is
# driven by circulating insulin I above baseline; I is secreted by the
# pancreas in response to hyperglycemia and cleared at a constant rate.
# Constants are illustrative (chosen for daily-aggregate stability), not
# a clinical calibration.

def generate_glucose_insulin(T: int = 180, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    Gb, Ib = 90.0, 10.0          # fasting baselines (mg/dL, uU/mL)
    p1, px = 0.20, 0.020          # glucose self-clearance, insulin-mediated uptake
    p2, p3 = 0.30, 0.050          # insulin-action decay, sensitivity to insulin
    p4, p5 = 0.25, 0.150          # insulin clearance, secretion response to glucose

    G = np.zeros(T)
    X = np.zeros(T)
    I = np.zeros(T)
    G[0], X[0], I[0] = Gb + 5.0, 0.0, Ib

    for t in range(T - 1):
        meal = 15.0 + 10.0 * np.sin(2 * np.pi * t / 7) + rng.normal(0, 3.0)
        dG = -p1 * (G[t] - Gb) - px * X[t] * (G[t] - Gb) + meal
        dX = -p2 * X[t] + p3 * (I[t] - Ib)
        dI = -p4 * (I[t] - Ib) + p5 * max(G[t] - Gb, 0.0)
        G[t + 1] = G[t] + dG
        X[t + 1] = X[t] + dX
        I[t + 1] = I[t] + dI

    dates = pd.date_range("2024-01-01", periods=T, freq="D")
    df = pd.DataFrame(
        {
            "Glucose_mgdl": G,
            "Plasma_Insulin_uUmL": I,
            "Insulin_Action": X,
        },
        index=dates,
    )
    df.index.name = "Date"
    return df


# ══════════════════════════════════════════════════════════════════════════
# ECOSYSTEM: predator–prey (Lotka–Volterra)
# ══════════════════════════════════════════════════════════════════════════
# Classic coupled nonlinear ODE pair with known "biological constants":
# prey growth rate a, predation rate b, predator death rate c, predator
# growth-from-predation rate d. Integrated with RK4 for numerical
# stability, monthly time steps, ~14 years to show several full cycles.

def _lv_deriv(state, a, b, c, d):
    prey, pred = state
    return np.array([a * prey - b * prey * pred, -c * pred + d * prey * pred])


def generate_predator_prey(T: int = 170, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    a, b, c, d = 1.0 / 12, 0.10 / 12, 1.5 / 12, 0.075 / 12  # per month
    state = np.array([40.0, 9.0])  # initial prey, predator populations

    prey = np.zeros(T)
    pred = np.zeros(T)
    prey[0], pred[0] = state

    dt = 1.0
    for t in range(T - 1):
        k1 = _lv_deriv(state, a, b, c, d)
        k2 = _lv_deriv(state + dt / 2 * k1, a, b, c, d)
        k3 = _lv_deriv(state + dt / 2 * k2, a, b, c, d)
        k4 = _lv_deriv(state + dt * k3, a, b, c, d)
        state = state + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        state = np.maximum(state, 0.1)  # keep populations positive
        # small demographic noise so the discovered structure isn't perfectly deterministic
        state = state * (1 + rng.normal(0, 0.01, size=2))
        prey[t + 1], pred[t + 1] = state

    dates = pd.date_range("2010-01-01", periods=T, freq="MS")
    df = pd.DataFrame({"Prey_Population": prey, "Predator_Population": pred}, index=dates)
    df.index.name = "Date"
    return df


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    medical = generate_glucose_insulin()
    medical.to_csv(OUT_DIR / "medical_glucose_insulin.csv")
    print(f"medical: {medical.shape}, ranges:\n{medical.describe().loc[['min', 'max']]}")

    ecosystem = generate_predator_prey()
    ecosystem.to_csv(OUT_DIR / "ecosystem_predator_prey.csv")
    print(f"ecosystem: {ecosystem.shape}, ranges:\n{ecosystem.describe().loc[['min', 'max']]}")
