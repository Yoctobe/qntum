"""Leakage-safe preprocessing and chronological split utilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data_preprocessor import DataPreprocessor, NormalizationParams


@dataclass(frozen=True)
class PreparedSplit:
    levels: np.ndarray
    normalized: np.ndarray
    train_levels: np.ndarray
    train_normalized: np.ndarray
    test_normalized: np.ndarray
    params: NormalizationParams
    variable_names: list[str]
    split_increment: int


class PreprocessingPipeline:
    def __init__(self, preprocessor: DataPreprocessor | None = None):
        self.preprocessor = preprocessor or DataPreprocessor()

    def prepare(
        self,
        levels: np.ndarray,
        variable_names: list[str],
        train_fraction: float,
        transform_overrides: dict[str, str] | None = None,
    ) -> PreparedSplit:
        levels = np.asarray(levels, dtype=float)
        if not 0 < train_fraction < 1:
            raise ValueError("train_fraction must be between 0 and 1")
        if len(levels) < 4:
            raise ValueError("At least four level observations are required")

        split_level = max(2, min(len(levels) - 1, int(len(levels) * train_fraction)))
        train_levels = levels[:split_level]
        params = self.preprocessor.fit(
            train_levels,
            variable_names,
            transform_overrides,
        )
        normalized = self.preprocessor.apply_params(levels, params)
        split_increment = split_level - 1

        return PreparedSplit(
            levels=levels,
            normalized=normalized,
            train_levels=train_levels,
            train_normalized=normalized[:split_increment],
            test_normalized=normalized[split_increment:],
            params=params,
            variable_names=list(variable_names),
            split_increment=split_increment,
        )

    def prepare_dataframe(
        self,
        frame: pd.DataFrame,
        train_fraction: float,
        date_column: str | None = "Date",
        skip_columns: list[str] | None = None,
        transform_overrides: dict[str, str] | None = None,
    ) -> PreparedSplit:
        data = frame.copy()
        excluded = set(skip_columns or [])
        if date_column:
            excluded.add(date_column)
        data = data.drop(columns=[name for name in excluded if name in data.columns])
        data = data.select_dtypes(include=[np.number])
        return self.prepare(
            data.to_numpy(dtype=float),
            data.columns.tolist(),
            train_fraction,
            transform_overrides,
        )

    def prepare_csv(
        self,
        path: str,
        train_fraction: float,
        date_column: str | None = "Date",
        skip_columns: list[str] | None = None,
        transform_overrides: dict[str, str] | None = None,
    ) -> PreparedSplit:
        return self.prepare_dataframe(
            pd.read_csv(path),
            train_fraction,
            date_column,
            skip_columns,
            transform_overrides,
        )
