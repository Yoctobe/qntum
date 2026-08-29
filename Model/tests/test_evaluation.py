import numpy as np

from quantum_model.baselines import PersistenceBaseline, VARBaseline
from quantum_model.evaluation import (
    evaluate_baselines,
    evaluate_intervals,
    evaluate_recursive,
)
from quantum_model.quantum_v2 import build_quantum_v2
from quantum_model.synthetic_studies import generate_sparse_var


def test_recursive_horizons_and_baselines_are_scored():
    system = generate_sparse_var(n_steps=140, seed=3)
    split = 100
    model = build_quantum_v2(
        system.data[:split],
        system.variable_names,
        alpha=0.0,
        beta=1.0,
        max_lag_steps=0,
        search_lags=False,
    )
    qntum = evaluate_recursive(
        model,
        system.data,
        system.variable_names,
        split,
        (1, 3, 6),
    )
    baselines = evaluate_baselines(
        [PersistenceBaseline(), VARBaseline()],
        system.data[:split],
        system.data,
        system.variable_names,
        split,
        (1, 3),
    )
    assert set(qntum["horizons"]) == {1, 3, 6}
    assert set(baselines) == {"persistence", "var"}
    assert qntum["horizons"][1]["n_predictions"] == len(system.data) - split - 1


def test_interval_evaluation_returns_all_nominal_levels():
    system = generate_sparse_var(n_steps=90, seed=5)
    split = 65
    model = build_quantum_v2(
        system.data[:split],
        system.variable_names,
        alpha=0.0,
        beta=1.0,
        max_lag_steps=0,
        search_lags=False,
    )
    result = evaluate_intervals(
        model,
        system.data,
        system.variable_names,
        split,
        horizon=2,
        n_paths=30,
        seed=1,
    )
    assert set(result["intervals"]) == {"0.5", "0.8", "0.9", "0.95"}
    assert all(0 <= item["coverage"] <= 1 for item in result["intervals"].values())
