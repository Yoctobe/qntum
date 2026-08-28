"""
DATA PREPROCESSOR for QNTUM
═══════════════════════════════════════════════════════════════════════════════

Transforms level values into stationary, robustly standardized increments.

KEY PRINCIPLE:
    All CSV values contain level data (prices, rates, volumes, etc.).
    Each variable is converted to a stationary increment, then standardized
    to roughly unit scale. The model operates on this increment space; the
    inverse transform reconstructs levels exactly.

Per-variable transform types:
    "diff"     : d[t] = x[t] − x[t−1]           (default — safe for any series:
                 rates already in %, zero-crossing series, negative levels)
    "log_diff" : d[t] = ln(x[t]) − ln(x[t−1])   (opt-in — strictly positive
                 multiplicative series such as prices and indices)

Standardization (robust z-score):
    normalized[t] = (d[t] − center) / scale
    center = median(d),  scale = 1.4826 · MAD(d)

Why not % change + tanh (the previous design):
    - % change is undefined/explosive for zero-crossing series (GDP growth)
      and sign-confused for negative levels (trade balance)
    - a persistent % change compounds levels exponentially on reconstruction
    - arctanh amplifies enormously near saturation (±1), blowing up forecasts
    Differencing + robust scaling has an exact, well-conditioned inverse:
    cumulative sum ("diff") or exp of cumulative sum ("log_diff").

Boundedness is NOT enforced here; stability is the dynamics' responsibility
(see the spectral-radius cap in quantum_v2.build_quantum_v2).
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import warnings
from typing import Optional, Tuple
from dataclasses import dataclass


TRANSFORM_DIFF = "diff"
TRANSFORM_LOG_DIFF = "log_diff"


@dataclass
class NormalizationParams:
    """
    Normalization parameters for exact inverse transformation.

    Attributes
    ----------
    variable_names  : list of column names
    transform_types : "diff" or "log_diff" per variable
    centers         : median increment per variable (drift baseline)
    scale_factors   : robust scale (1.4826 · MAD) per variable
    first_values    : first level value per variable (for reconstruction)
    """
    variable_names: list[str]
    transform_types: list[str]
    centers: np.ndarray
    scale_factors: np.ndarray
    first_values: np.ndarray


class DataPreprocessor:
    """
    Transforms level data to standardized stationary increments.

    Usage
    -----
        prep = DataPreprocessor()
        normalized, params = prep.transform_from_csv(
            "data.csv",
            transform_overrides={"SP500": "log_diff", "DXY": "log_diff"},
        )

        # Later: inverse transform (exact reconstruction)
        level_forecast = prep.inverse_transform(normalized_forecast, params)
    """

    def transform_from_csv(
        self,
        csv_path: str,
        date_column: Optional[str] = "Date",
        skip_columns: Optional[list[str]] = None,
        transform_overrides: Optional[dict[str, str]] = None,
    ) -> Tuple[np.ndarray, NormalizationParams]:
        """
        Load CSV with level values and transform to standardized increments.

        Parameters
        ----------
        csv_path            : path to CSV file
        date_column         : name of date column (will be dropped)
        skip_columns        : list of column names to skip (e.g., ["Source"])
        transform_overrides : {variable_name: "diff" | "log_diff"}

        Returns
        -------
        normalized : (T-1, n) array of standardized increments
        params     : NormalizationParams for inverse transformation
        """
        df = pd.read_csv(csv_path)

        if date_column and date_column in df.columns:
            df = df.drop(columns=[date_column])
        if skip_columns:
            df = df.drop(columns=[col for col in skip_columns if col in df.columns])

        df = df.select_dtypes(include=[np.number])

        return self.transform_from_dataframe(df, transform_overrides)

    def transform_from_dataframe(
        self,
        df: pd.DataFrame,
        transform_overrides: Optional[dict[str, str]] = None,
    ) -> Tuple[np.ndarray, NormalizationParams]:
        """Transform a DataFrame with level values to standardized increments."""
        return self.transform(
            df.values.astype(float),
            df.columns.tolist(),
            transform_overrides,
        )

    def transform(
        self,
        level_data: np.ndarray,
        variable_names: list[str],
        transform_overrides: Optional[dict[str, str]] = None,
    ) -> Tuple[np.ndarray, NormalizationParams]:
        """
        Core transformation: level values → standardized increments.

        Parameters
        ----------
        level_data          : (T, n) array of level values
        variable_names      : list of n variable names
        transform_overrides : {variable_name: "diff" | "log_diff"}

        Returns
        -------
        normalized : (T-1, n) array of standardized increments
        params     : NormalizationParams for inverse transformation
        """
        T, n = level_data.shape

        if T < 2:
            raise ValueError("Need at least 2 time steps to compute increments")

        overrides = transform_overrides or {}
        transform_types = []
        for i, name in enumerate(variable_names):
            ttype = overrides.get(name, TRANSFORM_DIFF)
            if ttype not in (TRANSFORM_DIFF, TRANSFORM_LOG_DIFF):
                raise ValueError(f"Unknown transform type '{ttype}' for {name}")
            finite = level_data[np.isfinite(level_data[:, i]), i]
            if ttype == TRANSFORM_LOG_DIFF and finite.size and finite.min() <= 0:
                warnings.warn(
                    f"{name}: log_diff requires strictly positive values, "
                    f"falling back to diff"
                )
                ttype = TRANSFORM_DIFF
            transform_types.append(ttype)

        first_values = level_data[0].copy()

        increments = self._increments(level_data, transform_types)

        # NaN-aware statistics: channels may have different historical coverage
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            centers = np.nanmedian(increments, axis=0)

            # Robust scale: 1.4826 · MAD ≈ std for Gaussian data, outlier-resistant
            mad = np.nanmedian(np.abs(increments - centers[None, :]), axis=0)
        scale_factors = 1.4826 * mad
        for i in range(n):
            if not np.isfinite(scale_factors[i]) or scale_factors[i] < 1e-12:
                fallback = float(np.nanstd(increments[:, i]))
                scale_factors[i] = fallback if np.isfinite(fallback) and fallback > 1e-12 else 1.0
            if not np.isfinite(centers[i]):
                centers[i] = 0.0

        normalized = (increments - centers[None, :]) / scale_factors[None, :]

        params = NormalizationParams(
            variable_names=variable_names,
            transform_types=transform_types,
            centers=centers,
            scale_factors=scale_factors,
            first_values=first_values,
        )

        return normalized, params

    @staticmethod
    def _increments(level_data: np.ndarray, transform_types: list[str]) -> np.ndarray:
        T, n = level_data.shape
        increments = np.full((T - 1, n), np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            for i in range(n):
                if transform_types[i] == TRANSFORM_LOG_DIFF:
                    increments[:, i] = np.diff(np.log(level_data[:, i]))
                else:
                    increments[:, i] = np.diff(level_data[:, i])
        return increments

    def apply_params(
        self,
        level_data: np.ndarray,
        params: NormalizationParams,
    ) -> np.ndarray:
        """
        Transform another levels panel using already-estimated params.

        Used to normalize the simulation panel with statistics estimated on a
        longer fitting panel, so both live in the same z-space.
        """
        increments = self._increments(level_data, params.transform_types)
        return (increments - params.centers[None, :]) / params.scale_factors[None, :]

    def inverse_transform(
        self,
        normalized: np.ndarray,
        params: NormalizationParams,
        initial_levels: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Convert standardized increments back to level values (exact inverse).

        Parameters
        ----------
        normalized     : (T, n) array of standardized increments
        params         : NormalizationParams from transform()
        initial_levels : (n,) starting levels; if None, use params.first_values

        Returns
        -------
        levels : (T+1, n) array — reconstructed level values
        """
        T, n = normalized.shape

        if initial_levels is None:
            initial_levels = params.first_values

        increments = normalized * params.scale_factors[None, :] + params.centers[None, :]

        levels = np.zeros((T + 1, n))
        levels[0] = initial_levels

        for i in range(n):
            if params.transform_types[i] == TRANSFORM_LOG_DIFF:
                levels[1:, i] = initial_levels[i] * np.exp(np.cumsum(increments[:, i]))
            else:
                levels[1:, i] = initial_levels[i] + np.cumsum(increments[:, i])

        return levels

    def summary(self, params: NormalizationParams) -> str:
        """Human-readable summary of the normalization parameters."""
        lines = ["=" * 72]
        lines.append("DATA PREPROCESSOR — Normalization Parameters")
        lines.append("=" * 72)
        lines.append(f"Variables: {len(params.variable_names)}")
        lines.append("")
        lines.append(f"{'Variable':<20} {'Transform':<10} {'Center':<12} {'Scale':<12} {'Initial'}")
        lines.append("-" * 72)
        for i, name in enumerate(params.variable_names):
            lines.append(
                f"{name:<20} {params.transform_types[i]:<10} "
                f"{params.centers[i]:<12.4f} {params.scale_factors[i]:<12.4f} "
                f"{params.first_values[i]:.2f}"
            )
        lines.append("=" * 72)
        lines.append("Data in standardized increment space (robust z-scores, ~unit scale)")
        lines.append("=" * 72)
        return "\n".join(lines)


def load_and_normalize(
    csv_path: str,
    date_column: Optional[str] = "Date",
    skip_columns: Optional[list[str]] = None,
    transform_overrides: Optional[dict[str, str]] = None,
) -> Tuple[np.ndarray, NormalizationParams, list[str]]:
    """
    Quick helper: load CSV and return normalized data ready for QNTUM.

    Returns
    -------
    normalized     : (T-1, n) array of standardized increments
    params         : NormalizationParams for inverse transform
    variable_names : list of variable names
    """
    prep = DataPreprocessor()
    normalized, params = prep.transform_from_csv(
        csv_path, date_column, skip_columns, transform_overrides
    )
    return normalized, params, params.variable_names
