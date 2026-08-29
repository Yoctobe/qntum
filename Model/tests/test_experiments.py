from experiments.run_event_study import run as run_event_study
from quantum_model.synthetic_studies import generate_sparse_var


def test_synthetic_generator_is_deterministic():
    first = generate_sparse_var(n_steps=40, seed=11)
    second = generate_sparse_var(n_steps=40, seed=11)
    assert (first.transition == second.transition).all()
    assert (first.data == second.data).all()


def test_declared_event_beats_always_on():
    result = run_event_study()
    assert result["declared_phase_mae"] < result["always_on_mae"]
