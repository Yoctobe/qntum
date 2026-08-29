import numpy as np

from quantum_model.data_preprocessor import DataPreprocessor
from quantum_model.pipeline import PreprocessingPipeline


def test_training_parameters_do_not_depend_on_test_values():
    levels = np.arange(60, dtype=float).reshape(30, 2) + 10.0
    changed = levels.copy()
    changed[21:] *= 1000.0

    first = PreprocessingPipeline().prepare(levels, ["a", "b"], 0.7)
    second = PreprocessingPipeline().prepare(changed, ["a", "b"], 0.7)

    np.testing.assert_allclose(first.params.centers, second.params.centers)
    np.testing.assert_allclose(first.params.scale_factors, second.params.scale_factors)
    np.testing.assert_allclose(first.train_normalized, second.train_normalized)


def test_transform_inverse_round_trip():
    levels = np.column_stack([np.linspace(1, 4, 20), np.exp(np.linspace(0, 1, 20))])
    prep = DataPreprocessor()
    normalized, params = prep.transform(
        levels,
        ["linear", "positive"],
        {"positive": "log_diff"},
    )
    reconstructed = prep.inverse_transform(normalized, params)
    np.testing.assert_allclose(reconstructed, levels)
