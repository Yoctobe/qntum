import numpy as np

from quantum_model.quantum_v2 import build_quantum_v2
from quantum_model.synthetic_studies import generate_sparse_var


def test_fixed_pin_is_invariant():
    system = generate_sparse_var(n_steps=120, seed=2)
    model = build_quantum_v2(
        system.data[:80],
        system.variable_names,
        manual_relationships={"pairs": [(0, 1, 0.42)]},
        alpha=0.0,
        beta=1.0,
        max_lag_steps=0,
        search_lags=False,
    )
    entry = model.I._relationships[(0, (1,))]
    assert entry.manually_set
    assert entry.constraint == "fixed"
    assert entry.weight == 0.42


def test_sign_bound_and_forbidden_constraints():
    system = generate_sparse_var(n_steps=140, seed=4)
    model = build_quantum_v2(
        system.data[:100],
        system.variable_names,
        relationship_constraints={
            "signs": [(0, (1,), 1)],
            "bounds": [(1, (2,), -0.3, -0.1)],
            "forbidden": [(2, (3,))],
        },
        alpha=0.0,
        beta=1.0,
        max_lag_steps=0,
        search_lags=False,
    )
    assert model.I._relationships[(0, (1,))].weight >= 0
    assert -0.3 <= model.I._relationships[(1, (2,))].weight <= -0.1
    assert (2, (3,)) not in model.I._relationships


def test_joint_estimator_recovers_sparse_transition():
    system = generate_sparse_var(n_steps=500, noise_scale=0.03, seed=9)
    model = build_quantum_v2(
        system.data[:400],
        system.variable_names,
        min_corr=0.08,
        alpha=0.0,
        beta=1.0,
        max_lag_steps=0,
        search_lags=False,
        l1_penalty=0.001,
    )
    error = np.sqrt(np.mean(np.square(model.I.to_matrix() - system.transition)))
    assert error < 0.2
