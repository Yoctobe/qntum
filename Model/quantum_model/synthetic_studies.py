"""Repeated controlled studies for structure recovery and pin sensitivity."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .evaluation import evaluate_recursive
from .quantum_v2 import build_quantum_v2


@dataclass(frozen=True)
class SparseVARSystem:
    transition: np.ndarray
    data: np.ndarray
    variable_names: list[str]


def generate_sparse_var(
    n_variables: int = 5,
    n_steps: int = 300,
    density: float = 0.2,
    spectral_radius: float = 0.85,
    noise_scale: float = 0.15,
    seed: int = 0,
) -> SparseVARSystem:
    rng = np.random.default_rng(seed)
    transition = rng.normal(0.0, 0.35, size=(n_variables, n_variables))
    mask = rng.random((n_variables, n_variables)) < density
    np.fill_diagonal(mask, True)
    transition *= mask
    radius = np.max(np.abs(np.linalg.eigvals(transition)))
    if radius > 0:
        transition *= spectral_radius / radius

    data = np.zeros((n_steps, n_variables))
    data[0] = rng.normal(size=n_variables)
    for time in range(1, n_steps):
        data[time] = transition @ data[time - 1] + rng.normal(
            0.0,
            noise_scale,
            size=n_variables,
        )
    return SparseVARSystem(
        transition=transition,
        data=data,
        variable_names=[f"x{i}" for i in range(n_variables)],
    )


def support_metrics(
    truth: np.ndarray,
    estimate: np.ndarray,
    threshold: float = 1e-6,
) -> dict:
    true_support = np.abs(truth) > threshold
    estimated_support = np.abs(estimate) > threshold
    true_positive = int(np.sum(true_support & estimated_support))
    false_positive = int(np.sum(~true_support & estimated_support))
    false_negative = int(np.sum(true_support & ~estimated_support))
    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / max(precision + recall, 1e-12),
        "sign_accuracy": float(
            np.mean(np.sign(truth[true_support & estimated_support]) == np.sign(estimate[true_support & estimated_support]))
        ) if true_positive else 0.0,
        "coefficient_rmse": float(np.sqrt(np.mean(np.square(truth - estimate)))),
        "structural_hamming_distance": false_positive + false_negative,
    }


def _pins_from_truth(
    transition: np.ndarray,
    coverage: float,
    incorrect_fraction: float,
    rng: np.random.Generator,
) -> dict:
    edges = list(zip(*np.where(np.abs(transition) > 1e-12)))
    count = int(round(len(edges) * coverage))
    selected = rng.choice(len(edges), size=count, replace=False) if count else []
    pairs = []
    incorrect_count = int(round(count * incorrect_fraction))
    for position, edge_index in enumerate(selected):
        target, source = edges[int(edge_index)]
        weight = float(transition[target, source])
        if position < incorrect_count:
            weight *= -1.0
        pairs.append((int(target), int(source), weight, 0.0))
    return {"pairs": pairs}


def run_recovery_study(
    seeds: int = 20,
    sample_sizes: tuple[int, ...] = (80, 160, 320),
    pin_coverages: tuple[float, ...] = (0.0, 0.25, 0.5),
    incorrect_fractions: tuple[float, ...] = (0.0, 0.1),
) -> list[dict]:
    records = []
    for seed in range(seeds):
        for sample_size in sample_sizes:
            system = generate_sparse_var(n_steps=sample_size, seed=seed)
            split = int(sample_size * 0.7)
            for coverage in pin_coverages:
                for incorrect in incorrect_fractions:
                    rng = np.random.default_rng(seed * 10_000 + int(coverage * 1000) + int(incorrect * 100))
                    pins = _pins_from_truth(system.transition, coverage, incorrect, rng)
                    model = build_quantum_v2(
                        system.data[:split],
                        system.variable_names,
                        manual_relationships=pins,
                        min_corr=0.15,
                        alpha=0.0,
                        beta=1.0,
                        max_lag_steps=0,
                        search_lags=False,
                        l1_penalty=0.005,
                    )
                    structure = support_metrics(system.transition, model.I.to_matrix())
                    forecast = evaluate_recursive(
                        model,
                        system.data,
                        system.variable_names,
                        split,
                        horizons=(1, 3, 6, 12),
                    )
                    records.append(
                        {
                            "seed": seed,
                            "sample_size": sample_size,
                            "pin_coverage": coverage,
                            "incorrect_pin_fraction": incorrect,
                            **structure,
                            "forecast": {
                                str(h): {
                                    "mae": values["mae"],
                                    "rmse": values["rmse"],
                                }
                                for h, values in forecast["horizons"].items()
                            },
                        }
                    )
    return records
