import numpy as np

from quantum_model.influence_matrix_v2 import InfluenceMatrixV2
from quantum_model.stability import companion_matrix, stability_report, stabilize_beta


def test_companion_matrix_represents_lagged_recurrence():
    influence = InfluenceMatrixV2(1)
    influence.set_pair(0, 0, 0.4, time_lag=1.0)
    influence._relationships[(0, (0,))].lag_steps = 1
    matrix = companion_matrix(influence, alpha=0.3, beta=1.0)
    np.testing.assert_allclose(matrix, [[0.3, 0.4], [1.0, 0.0]])


def test_stabilizer_caps_executed_linear_recurrence():
    influence = InfluenceMatrixV2(2)
    influence.set_pair(0, 1, 2.0)
    influence.set_pair(1, 0, 2.0)
    beta, report = stabilize_beta(influence, alpha=0.2, beta=1.0, max_rho=0.98)
    assert beta < 1.0
    assert report.spectral_radius <= 0.98
    assert report.certified_linear


def test_nonlinear_store_is_not_certified():
    influence = InfluenceMatrixV2(2)
    influence.set_triplet(0, 0, 1, 0.2)
    report = stability_report(influence, alpha=0.2, beta=1.0)
    assert not report.certified_linear
    assert report.nonlinear_terms == 1
