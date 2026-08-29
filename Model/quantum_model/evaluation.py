"""Leakage-free point and probabilistic forecast evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .data_preprocessor import DataPreprocessor, NormalizationParams

if TYPE_CHECKING:
    from .quantum_v2 import Event, QuantumV2


def regression_metrics(
    predictions: np.ndarray,
    actuals: np.ndarray,
    variable_names: list[str],
) -> dict:
    predictions = np.asarray(predictions, dtype=float)
    actuals = np.asarray(actuals, dtype=float)
    error = predictions - actuals
    valid = np.isfinite(error)
    mae = float(np.mean(np.abs(error[valid]))) if valid.any() else float("nan")
    rmse = float(np.sqrt(np.mean(np.square(error[valid])))) if valid.any() else float("nan")

    correlations: dict[str, float] = {}
    for index, name in enumerate(variable_names):
        mask = np.isfinite(predictions[:, index]) & np.isfinite(actuals[:, index])
        if mask.sum() < 3 or np.std(predictions[mask, index]) < 1e-12:
            correlations[name] = 0.0
            continue
        value = np.corrcoef(predictions[mask, index], actuals[mask, index])[0, 1]
        correlations[name] = 0.0 if np.isnan(value) else float(value)

    return {
        "mae": mae,
        "rmse": rmse,
        "correlations": correlations,
        "mean_correlation": float(np.mean(list(correlations.values()))),
        "n_predictions": int(len(predictions)),
    }


def always_on_events(variable_names: list[str], horizon: int) -> list["Event"]:
    from .quantum_v2 import Event

    return [
        Event(0.0, 0.0, float(horizon + 10), 0.0, name, 0.0)
        for name in variable_names
    ]


def predict_one_step(
    model: "QuantumV2",
    data: np.ndarray,
    start: int,
) -> np.ndarray:
    events = always_on_events([f"x{i}" for i in range(model.n)], len(data))
    predictions = np.zeros((len(data) - start - 1, model.n))
    for output_index, origin in enumerate(range(start, len(data) - 1)):
        history_start = max(0, origin - model.max_history_steps)
        model._history_buffer = data[history_start:origin].copy()
        predictions[output_index] = model.step(1.0, data[origin], events)
    model.reset_history()
    return predictions


def evaluate_one_step(
    model: "QuantumV2",
    data: np.ndarray,
    variable_names: list[str],
    split: int,
) -> dict:
    if split < 1 or split >= len(data) - 1:
        raise ValueError("split must leave conditioning and scoring observations")
    predictions = predict_one_step(model, data, split)
    actuals = data[split + 1 :]
    result = regression_metrics(predictions, actuals, variable_names)
    result.update(
        {
            "mode": "rolling_one_step",
            "n_train": int(split),
            "n_test": int(len(actuals)),
            "predictions": predictions,
            "actuals": actuals,
        }
    )
    return result


def _recursive_path(
    model: "QuantumV2",
    data: np.ndarray,
    origin: int,
    horizon: int,
    events: list["Event"],
) -> np.ndarray:
    history_start = max(0, origin - model.max_history_steps)
    model._history_buffer = data[history_start:origin].copy()
    state = data[origin].copy()
    path = np.zeros((horizon, model.n))
    for step in range(horizon):
        state = model.step(float(step + 1), state, events)
        path[step] = state
    model.reset_history()
    return path


def evaluate_recursive(
    model: "QuantumV2",
    data: np.ndarray,
    variable_names: list[str],
    split: int,
    horizons: tuple[int, ...] = (1, 3, 6, 12),
    levels: np.ndarray | None = None,
    params: NormalizationParams | None = None,
) -> dict:
    horizons = tuple(sorted(set(int(h) for h in horizons if h > 0)))
    if not horizons:
        raise ValueError("At least one positive horizon is required")

    events = always_on_events(variable_names, max(horizons))
    results: dict[int, dict] = {}
    preprocessor = DataPreprocessor()

    for horizon in horizons:
        predictions: list[np.ndarray] = []
        actuals: list[np.ndarray] = []
        level_predictions: list[np.ndarray] = []
        level_actuals: list[np.ndarray] = []

        for origin in range(split, len(data) - horizon):
            path = _recursive_path(model, data, origin, horizon, events)
            predictions.append(path[-1])
            actuals.append(data[origin + horizon])

            if levels is not None and params is not None:
                initial_level = levels[origin + 1]
                predicted_levels = preprocessor.inverse_transform(path, params, initial_level)
                level_predictions.append(predicted_levels[-1])
                level_actuals.append(levels[origin + horizon + 1])

        if not predictions:
            continue
        horizon_result = regression_metrics(
            np.asarray(predictions),
            np.asarray(actuals),
            variable_names,
        )
        if level_predictions:
            horizon_result["level_metrics"] = regression_metrics(
                np.asarray(level_predictions),
                np.asarray(level_actuals),
                variable_names,
            )
        results[horizon] = horizon_result

    return {
        "mode": "recursive_rolling_origin",
        "split": int(split),
        "horizons": results,
    }


def one_step_residuals(
    model: "QuantumV2",
    training_data: np.ndarray,
) -> np.ndarray:
    if len(training_data) < 3:
        raise ValueError("At least three training increments are required")
    predictions = predict_one_step(model, training_data, 0)
    return training_data[1:] - predictions


def evaluate_intervals(
    model: "QuantumV2",
    data: np.ndarray,
    variable_names: list[str],
    split: int,
    horizon: int = 6,
    n_paths: int = 300,
    levels: tuple[float, ...] = (0.5, 0.8, 0.9, 0.95),
    block_length: int = 3,
    seed: int = 42,
    calibration_start: int | None = None,
) -> dict:
    """Evaluate temporally split conformal intervals over rolling origins."""
    del n_paths, block_length, seed
    calibration_start = calibration_start or max(2, int(split * 0.8))
    if not 1 <= calibration_start < split - horizon:
        raise ValueError("Calibration window must precede the final test split")
    events = always_on_events(variable_names, horizon)
    calibration_errors = []
    for origin in range(calibration_start, split - horizon):
        prediction = _recursive_path(model, data, origin, horizon, events)[-1]
        calibration_errors.append(np.abs(data[origin + horizon] - prediction))
    calibration_errors = np.asarray(calibration_errors)
    if not len(calibration_errors):
        raise ValueError("Calibration window is too short")

    records = {}
    for level in levels:
        corrected_level = min(
            1.0,
            np.ceil((len(calibration_errors) + 1) * level) / len(calibration_errors),
        )
        radius = np.quantile(calibration_errors, corrected_level, axis=0)
        records[level] = {
            "inside": 0,
            "total": 0,
            "width": [],
            "winkler": [],
            "radius": radius,
        }

    for origin in range(split, len(data) - horizon):
        deterministic = _recursive_path(model, data, origin, horizon, events)[-1]
        actual = data[origin + horizon]
        for level in levels:
            lower = deterministic - records[level]["radius"]
            upper = deterministic + records[level]["radius"]
            valid = np.isfinite(actual) & np.isfinite(lower) & np.isfinite(upper)
            alpha = 1.0 - level
            width = upper[valid] - lower[valid]
            score = width.copy()
            score += np.where(actual[valid] < lower[valid], 2.0 / alpha * (lower[valid] - actual[valid]), 0.0)
            score += np.where(actual[valid] > upper[valid], 2.0 / alpha * (actual[valid] - upper[valid]), 0.0)
            records[level]["inside"] += int(np.sum((actual[valid] >= lower[valid]) & (actual[valid] <= upper[valid])))
            records[level]["total"] += int(valid.sum())
            records[level]["width"].extend(width.tolist())
            records[level]["winkler"].extend(score.tolist())

    summary = {}
    for level, record in records.items():
        total = record["total"]
        summary[str(level)] = {
            "coverage": record["inside"] / total if total else float("nan"),
            "mean_width": float(np.mean(record["width"])) if record["width"] else float("nan"),
            "winkler_score": float(np.mean(record["winkler"])) if record["winkler"] else float("nan"),
            "n": total,
        }
    return {
        "method": "temporally_split_conformal",
        "horizon": horizon,
        "calibration_start": calibration_start,
        "calibration_end": split,
        "intervals": summary,
    }


def evaluate_baselines(
    baselines: list,
    training_data: np.ndarray,
    full_data: np.ndarray,
    variable_names: list[str],
    split: int,
    horizons: tuple[int, ...] = (1, 3, 6, 12),
) -> dict:
    results = {}
    for baseline in baselines:
        baseline.fit(training_data)
        horizon_results = {}
        for horizon in horizons:
            predictions = []
            actuals = []
            for origin in range(split, len(full_data) - horizon):
                history = full_data[: origin + 1]
                predictions.append(baseline.forecast(history, horizon)[-1])
                actuals.append(full_data[origin + horizon])
            if predictions:
                horizon_results[horizon] = regression_metrics(
                    np.asarray(predictions),
                    np.asarray(actuals),
                    variable_names,
                )
        results[baseline.name] = horizon_results
    return results
