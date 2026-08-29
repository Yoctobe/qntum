"""Transparent forecasting baselines used by the experiment suite."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class ForecastBaseline:
    name = "baseline"

    def fit(self, data: np.ndarray) -> "ForecastBaseline":
        raise NotImplementedError

    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        raise NotImplementedError


class ZeroIncrementBaseline(ForecastBaseline):
    name = "zero_increment"

    def fit(self, data: np.ndarray) -> "ZeroIncrementBaseline":
        self.n = data.shape[1]
        return self

    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        return np.zeros((horizon, self.n))


class PersistenceBaseline(ForecastBaseline):
    name = "persistence"

    def fit(self, data: np.ndarray) -> "PersistenceBaseline":
        self.n = data.shape[1]
        return self

    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        return np.repeat(np.asarray(history)[-1][None, :], horizon, axis=0)


@dataclass
class VARBaseline(ForecastBaseline):
    lags: int = 1
    ridge: float = 0.0
    name: str = "var"
    fixed_coefficients: dict[tuple[int, int, int], float] | None = None

    def fit(self, data: np.ndarray) -> "VARBaseline":
        data = np.asarray(data, dtype=float)
        if len(data) <= self.lags:
            raise ValueError("Not enough observations for requested VAR lags")
        rows = []
        targets = []
        for time in range(self.lags, len(data)):
            rows.append(np.concatenate([data[time - lag] for lag in range(1, self.lags + 1)]))
            targets.append(data[time])
        X = np.asarray(rows)
        Y = np.asarray(targets)
        valid = np.all(np.isfinite(X), axis=1) & np.all(np.isfinite(Y), axis=1)
        X = X[valid]
        Y = Y[valid]
        design = np.column_stack([np.ones(len(X)), X])
        gram = design.T @ design
        penalty = self.ridge * np.eye(gram.shape[0])
        penalty[0, 0] = 0.0
        coefficients = np.linalg.pinv(gram + penalty) @ design.T @ Y
        self.intercept_ = coefficients[0]
        self.coefficients_ = coefficients[1:].T.reshape(Y.shape[1], self.lags, Y.shape[1])

        for (target, source, lag), value in (self.fixed_coefficients or {}).items():
            self.coefficients_[target, lag, source] = value
        return self

    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        states = [row.copy() for row in np.asarray(history, dtype=float)]
        output = np.zeros((horizon, self.coefficients_.shape[0]))
        for step in range(horizon):
            prediction = self.intercept_.copy()
            for lag in range(self.lags):
                prediction += self.coefficients_[:, lag, :] @ states[-lag - 1]
            output[step] = prediction
            states.append(prediction)
        return output


class IndependentARBaseline(VARBaseline):
    name = "independent_ar"

    def fit(self, data: np.ndarray) -> "IndependentARBaseline":
        super().fit(data)
        for target in range(self.coefficients_.shape[0]):
            for source in range(self.coefficients_.shape[2]):
                if source != target:
                    self.coefficients_[target, :, source] = 0.0
        return self


class RidgeVARBaseline(VARBaseline):
    name = "ridge_var"

    def __init__(self, lags: int = 1, ridge: float = 1.0):
        super().__init__(lags=lags, ridge=ridge, name=self.name)


class SparseVARBaseline(VARBaseline):
    name = "sparse_var"

    def __init__(self, lags: int = 1, ridge: float = 0.1, threshold: float = 0.05):
        super().__init__(lags=lags, ridge=ridge, name=self.name)
        self.threshold = threshold

    def fit(self, data: np.ndarray) -> "SparseVARBaseline":
        super().fit(data)
        self.coefficients_[np.abs(self.coefficients_) < self.threshold] = 0.0
        return self


class RestrictedVARBaseline(VARBaseline):
    name = "restricted_var"

    def __init__(
        self,
        fixed_coefficients: dict[tuple[int, int, int], float],
        lags: int = 1,
        ridge: float = 0.0,
    ):
        super().__init__(
            lags=lags,
            ridge=ridge,
            name=self.name,
            fixed_coefficients=fixed_coefficients,
        )


def default_baselines() -> list[ForecastBaseline]:
    return [
        ZeroIncrementBaseline(),
        PersistenceBaseline(),
        IndependentARBaseline(),
        VARBaseline(),
        RidgeVARBaseline(),
        SparseVARBaseline(),
    ]
