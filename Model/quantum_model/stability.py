"""Stability diagnostics for the executed lagged linear recurrence."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .influence_matrix_v2 import InfluenceMatrixV2


@dataclass(frozen=True)
class StabilityReport:
    spectral_radius: float
    max_transient_gain: float
    max_lag_steps: int
    certified_linear: bool
    nonlinear_terms: int

    def as_dict(self) -> dict:
        return asdict(self)


def companion_matrix(
    influence: InfluenceMatrixV2,
    alpha: float,
    beta: float,
) -> np.ndarray:
    pairs = influence.get_relationships_by_order(2)
    max_lag = max((entry.lag_steps for entry in pairs), default=0)
    blocks = [np.zeros((influence.n, influence.n)) for _ in range(max_lag + 1)]
    blocks[0] += alpha * np.eye(influence.n)
    for entry in pairs:
        blocks[entry.lag_steps][entry.target_idx, entry.source_indices[0]] += beta * entry.weight

    if max_lag == 0:
        return blocks[0]

    companion = np.zeros((influence.n * (max_lag + 1), influence.n * (max_lag + 1)))
    companion[: influence.n, :] = np.hstack(blocks)
    companion[influence.n :, : -influence.n] = np.eye(influence.n * max_lag)
    return companion


def stability_report(
    influence: InfluenceMatrixV2,
    alpha: float,
    beta: float,
    transient_horizon: int = 100,
) -> StabilityReport:
    matrix = companion_matrix(influence, alpha, beta)
    radius = float(np.max(np.abs(np.linalg.eigvals(matrix))))
    power = np.eye(len(matrix))
    max_gain = 1.0
    for _ in range(transient_horizon):
        power = power @ matrix
        max_gain = max(max_gain, float(np.linalg.norm(power, ord=2)))
    nonlinear_count = sum(
        entry.order > 2
        or entry.relationship_type == "nonlinear"
        or entry.feature_transform is not None
        for entry in influence._relationships.values()
    )
    return StabilityReport(
        spectral_radius=radius,
        max_transient_gain=max_gain,
        max_lag_steps=max((entry.lag_steps for entry in influence._relationships.values()), default=0),
        certified_linear=nonlinear_count == 0 and radius < 1.0,
        nonlinear_terms=nonlinear_count,
    )


def stabilize_beta(
    influence: InfluenceMatrixV2,
    alpha: float,
    beta: float,
    max_rho: float = 0.98,
) -> tuple[float, StabilityReport]:
    if not 0 <= alpha < max_rho:
        raise ValueError("alpha must be non-negative and below max_rho")
    candidate = float(beta)
    report = stability_report(influence, alpha, candidate)
    while report.spectral_radius > max_rho and candidate > 1e-8:
        candidate *= 0.9
        report = stability_report(influence, alpha, candidate)
    return candidate, report
