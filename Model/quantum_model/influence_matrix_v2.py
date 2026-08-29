"""
INFLUENCE MATRIX V2 — Comprehensive Relationship Store
═══════════════════════════════════════════════════════════════════════════════

A unified store for ALL relationships: pairs, triplets, quadruplets, and beyond.

KEY PRINCIPLES:
    1. Manual relationships are ALWAYS respected (never overwritten)
    2. Auto-correlations are calculated CAUTIOUSLY (significance threshold)
    3. Stores linear AND non-linear relationships
    4. Sparse storage: only significant relationships are kept
    5. Order-agnostic: treats pairs, triplets, quadruplets uniformly

Relationship Types:
    LINEAR      : w · x_j                    (scalar weight)
    NONLINEAR   : f(x_j)                     (user-provided formula)
    AUTO        : fitted from data if significant (|r| ≥ min_corr)

Relationship Orders:
    order-2 (pair)       : f_ij(x_j)
    order-3 (triplet)    : f_ijk(x_j, x_k)
    order-4 (quadruplet) : f_ijkl(x_j, x_k, x_l)
    order-n              : f_i,{j1...jn-1}(x_j1, ..., x_jn-1)

Storage Structure:
    Each relationship is keyed by (target_idx, source_indices_tuple)
    Example:
        (0, (1,))      → pair: variable 1 influences variable 0
        (0, (1, 2))    → triplet: variables 1 AND 2 jointly influence 0
        (0, (1, 2, 3)) → quadruplet: variables 1, 2, 3 jointly influence 0
"""

from __future__ import annotations
import numpy as np
from typing import Callable, Optional, Dict, Tuple, Set
from dataclasses import dataclass
import warnings


# ══════════════════════════════════════════════════════════════════════════════
# RELATIONSHIP ENTRY
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RelationshipEntry:
    """
    A single relationship: how source variable(s) influence a target.
    
    Attributes
    ----------
    target_idx    : index of target variable
    source_indices: tuple of source variable indices
    relationship_type: "linear", "nonlinear", "auto"
    weight        : float (for linear relationships)
    formula       : callable (for nonlinear relationships)
    significance  : correlation coefficient (for auto relationships)
    manually_set  : True if user-provided, False if auto-discovered
    time_lag      : float (time delay in days, constrained to one time step
                    of the data: [0, max_lag_days])
    """
    target_idx: int
    source_indices: tuple
    relationship_type: str  # "linear", "nonlinear", "auto"
    weight: float = 0.0
    formula: Optional[Callable] = None
    significance: float = 0.0
    manually_set: bool = False
    time_lag: float = 0.0  # in days, max 1.0
    lag_steps: int = 0
    constraint: str = "estimated"
    lower_bound: float = -np.inf
    upper_bound: float = np.inf
    feature_name: str = "product"
    feature_transform: Optional[Callable] = None
    
    @property
    def order(self) -> int:
        """Relationship order: 2 = pair, 3 = triplet, 4 = quadruplet, etc."""
        return len(self.source_indices) + 1
    
    def evaluate(self, *values: float) -> float:
        """
        Evaluate the relationship given source values.
        
        For linear: weight * product of all source values
        For nonlinear: formula(*values)
        """
        if self.relationship_type == "nonlinear" and self.formula is not None:
            return float(self.formula(*values))
        if self.feature_transform is not None:
            return self.weight * float(self.feature_transform(*values))
        else:
            # Linear/multilinear: weight * product
            product = 1.0
            for v in values:
                product *= v
            return self.weight * product


# ══════════════════════════════════════════════════════════════════════════════
# INFLUENCE MATRIX V2
# ══════════════════════════════════════════════════════════════════════════════

class InfluenceMatrixV2:
    """
    Comprehensive relationship store for QNTUM.
    
    Stores ALL relationships (pairs, triplets, quadruplets, etc.) in one
    unified sparse structure.
    
    Manual relationships are NEVER overwritten.
    Auto relationships are only added if statistically significant.
    
    Parameters
    ----------
    n_variables   : number of variables in the system
    min_corr      : minimum |correlation| for auto-discovered relationships
    max_order     : maximum relationship order to auto-discover (2, 3, 4, ...)
                    e.g., max_order=3 means auto-discover pairs and triplets only
    
    Usage
    -----
        # Create matrix
        I = InfluenceMatrixV2(n_variables=5, min_corr=0.15, max_order=3)
        
        # Define manual relationships
        I.set_relationship(target=0, sources=(1,), weight=-0.4)          # pair
        I.set_relationship(target=0, sources=(1, 2), weight=0.3)         # triplet
        I.set_relationship(target=0, sources=(1, 2, 3), formula=my_fn)   # nonlinear quadruplet
        
        # Auto-discover significant relationships from data
        I.fit(data, discover_pairs=True, discover_triplets=True)
        
        # Apply all relationships to current state
        influence = I.apply(current_magnitudes)
    """
    
    def __init__(
        self,
        n_variables: int,
        min_corr: float = 0.15,
        max_order: int = 3,
        max_lag_days: Optional[float] = 1.0,
        shrinkage: bool = False,
    ):
        self.n = n_variables
        self.min_corr = min_corr
        self.max_order = max_order
        # Upper bound for relationship lags, in days. Must match the data
        # frequency (one time step): 1.0 for daily data, 30.0 for monthly.
        # None = unbounded.
        self.max_lag_days = max_lag_days
        # Soft thresholding: pairs with |r| in [min_corr/2, min_corr) enter
        # with a linearly shrunk weight instead of being dropped entirely.
        self.shrinkage = shrinkage
        
        # Sparse storage: key = (target, source_tuple) → RelationshipEntry
        self._relationships: Dict[Tuple, RelationshipEntry] = {}
        
        # Track which relationships are manual (never overwrite)
        self._manual_keys: Set[Tuple] = set()
        self._forbidden_keys: Set[Tuple] = set()
        self.intercepts = np.zeros(n_variables)
    
    # ──────────────────────────────────────────────────────────────────────────
    # MANUAL RELATIONSHIP DEFINITION
    # ──────────────────────────────────────────────────────────────────────────
    
    def set_relationship(
        self,
        target: int,
        sources: tuple,
        weight: Optional[float] = None,
        formula: Optional[Callable] = None,
        time_lag: float = 0.0,
        constraint: str = "fixed",
        bounds: tuple[float, float] | None = None,
    ):
        """
        Manually define a relationship (will NEVER be overwritten by auto-fit).
        
        Parameters
        ----------
        target   : target variable index
        sources  : tuple of source variable indices, e.g., (1,) or (1, 2) or (1, 2, 3)
        weight   : scalar weight for linear/multilinear relationship
        formula  : callable for nonlinear relationship: f(x_j1, x_j2, ...)
        time_lag : time delay in days, constrained to [0, max_lag_days]
                   (one time step: 1.0 for daily data, 30.0 for monthly)
        
        Examples
        --------
            # Pair: variable 1 influences variable 0 with weight -0.4, instant
            I.set_relationship(0, (1,), weight=-0.4, time_lag=0.0)
            
            # Pair with 6-hour lag
            I.set_relationship(0, (1,), weight=-0.4, time_lag=0.25)
            
            # Triplet: variables 1 AND 2 jointly influence variable 0
            I.set_relationship(0, (1, 2), weight=0.3, time_lag=0.5)
            
            # Nonlinear quadruplet with 1-day lag
            I.set_relationship(0, (1, 2, 3), formula=lambda r, c, u: -0.1*r*c*u, time_lag=1.0)
        """
        if not isinstance(sources, tuple) or len(sources) < 1:
            raise ValueError("sources must be a non-empty tuple of indices")
        
        if target < 0 or target >= self.n:
            raise ValueError(f"target {target} out of range [0, {self.n})")
        
        for s in sources:
            if s < 0 or s >= self.n:
                raise ValueError(f"source {s} out of range [0, {self.n})")
        
        # Constrain time lag to [0, max_lag_days] (one time step of the data)
        if time_lag < 0.0:
            warnings.warn(f"time_lag {time_lag} < 0, clamping to 0.0")
            time_lag = 0.0
        elif self.max_lag_days is not None and time_lag > self.max_lag_days:
            warnings.warn(
                f"time_lag {time_lag} > max_lag_days {self.max_lag_days}, clamping"
            )
            time_lag = self.max_lag_days
        
        if constraint not in {"fixed", "sign", "bounded"}:
            raise ValueError("constraint must be fixed, sign, or bounded")
        lower, upper = bounds or (-np.inf, np.inf)
        if constraint == "sign" and weight is not None:
            lower, upper = (0.0, np.inf) if weight >= 0 else (-np.inf, 0.0)
        if lower > upper:
            raise ValueError("constraint lower bound cannot exceed upper bound")

        key = (target, sources)
        
        if formula is not None:
            # Nonlinear relationship
            entry = RelationshipEntry(
                target_idx=target,
                source_indices=sources,
                relationship_type="nonlinear",
                weight=0.0,
                formula=formula,
                significance=1.0,  # manually set = fully significant
                manually_set=True,
                time_lag=time_lag,
                constraint="fixed",
            )
        elif weight is not None:
            # Linear/multilinear relationship
            entry = RelationshipEntry(
                target_idx=target,
                source_indices=sources,
                relationship_type="linear",
                weight=float(weight),
                formula=None,
                significance=1.0,
                manually_set=True,
                time_lag=time_lag,
                constraint=constraint,
                lower_bound=float(lower),
                upper_bound=float(upper),
            )
        else:
            raise ValueError("Must provide either weight or formula")
        
        self._relationships[key] = entry
        self._manual_keys.add(key)

    def forbid_relationship(self, target: int, sources: tuple) -> None:
        """Prevent an edge from being discovered and remove any estimated copy."""
        key = (target, tuple(sources))
        self._relationships.pop(key, None)
        self._manual_keys.discard(key)
        self._forbidden_keys.add(key)
    
    def set_pair(self, target: int, source: int, weight: float, time_lag: float = 0.0):
        """Convenience: set a pairwise relationship."""
        self.set_relationship(target, (source,), weight=weight, time_lag=time_lag)
    
    def set_triplet(self, target: int, source1: int, source2: int, weight: float, time_lag: float = 0.0):
        """Convenience: set a triplet relationship."""
        self.set_relationship(target, (source1, source2), weight=weight, time_lag=time_lag)
    
    def set_quadruplet(self, target: int, source1: int, source2: int, source3: int, weight: float, time_lag: float = 0.0):
        """Convenience: set a quadruplet relationship."""
        self.set_relationship(target, (source1, source2, source3), weight=weight, time_lag=time_lag)
    
    # ──────────────────────────────────────────────────────────────────────────
    # AUTO-DISCOVERY FROM DATA (CAUTIOUS)
    # ──────────────────────────────────────────────────────────────────────────
    
    def fit(
        self,
        data: np.ndarray,
        discover_pairs: bool = True,
        discover_triplets: bool = False,
        discover_quadruplets: bool = False,
        dt: float = 1.0,
        search_lags: bool = True,
        lag_search_steps: int = 10,
        max_lag_steps: int = 1,
        alpha: float = 0.0,
        beta: float = 1.0,
        l1_penalty: float = 0.01,
        candidate_library: Optional[list[dict]] = None,
    ):
        """
        Cautiously discover relationships from data.
        
        Only adds relationships if:
            1. Not manually set already
            2. Statistical significance |r| ≥ min_corr
            3. Order ≤ max_order
        
        Parameters
        ----------
        data                  : (T, n) array — normalized % changes
        discover_pairs        : discover pairwise relationships
        discover_triplets     : discover 3-way relationships
        discover_quadruplets  : discover 4-way relationships
        dt                    : time step size in days (e.g., 1/24 for hourly, 1.0 for daily)
        search_lags           : if True, search for optimal time lag per relationship
        lag_search_steps      : number of lag steps to test (distributed over [0, dt] days = one time step)
        """
        data = np.asarray(data, dtype=float)
        if data.ndim != 2:
            raise ValueError("data must be 2D array (T, n)")
        
        T, n = data.shape
        if n != self.n:
            raise ValueError(f"data has {n} variables but matrix expects {self.n}")
        
        if T < 4:
            warnings.warn("Too few time steps for reliable fitting, skipping auto-discovery")
            return
        
        max_lag_steps = min(max(0, int(max_lag_steps)), T - 2)

        if search_lags:
            lag_candidates = np.arange(max_lag_steps + 1, dtype=float) * dt
        else:
            lag_candidates = np.array([0.0])
        
        # Discover pairs (order 2)
        if discover_pairs and 2 <= self.max_order:
            self._fit_pairs(data, dt, lag_candidates)
        
        # Discover triplets (order 3)
        if discover_triplets and 3 <= self.max_order:
            self._fit_triplets(data, dt, lag_candidates)
        
        # Discover quadruplets (order 4)
        if discover_quadruplets and 4 <= self.max_order:
            self._fit_quadruplets(data, dt, lag_candidates)
        if candidate_library:
            self._fit_candidate_library(data, dt, candidate_library)

        self._joint_refit(data, dt, alpha, beta, l1_penalty)

    def _fit_candidate_library(
        self,
        data: np.ndarray,
        dt: float,
        candidates: list[dict],
    ) -> None:
        for candidate in candidates:
            target = int(candidate["target"])
            sources = tuple(candidate["sources"])
            key = (target, sources)
            if key in self._relationships or key in self._forbidden_keys:
                continue
            transform = candidate["transform"]
            lag_steps = int(candidate.get("lag_steps", 0))
            rows = np.arange(lag_steps, len(data) - 1)
            values = data[rows - lag_steps][:, sources]
            feature = np.asarray([transform(*row) for row in values], dtype=float)
            target_values = data[rows + 1, target]
            feature, target_values = self._valid_overlap(feature, target_values)
            corr = self._safe_corr(feature, target_values)
            if corr is None or abs(corr) < self.min_corr:
                continue
            self._relationships[key] = RelationshipEntry(
                target_idx=target,
                source_indices=sources,
                relationship_type="auto",
                significance=abs(corr),
                time_lag=lag_steps * dt,
                lag_steps=lag_steps,
                feature_name=str(candidate.get("name", "custom")),
                feature_transform=transform,
            )
    
    def _fit_pairs(self, data: np.ndarray, dt: float, lag_candidates: np.ndarray):
        """
        Discover significant pairwise relationships with optimal time lags.

        NaN-aware: each pair is fitted on its own valid overlap, so channels
        with different historical coverage contribute their longest common
        window rather than the global inner join.

        With shrinkage enabled, pairs whose |r| lands in [min_corr/2, min_corr)
        enter with a linearly shrunk weight (soft threshold) instead of being
        dropped — borderline-but-real economics contributes a small coupling
        rather than exactly zero.
        """
        T, n = data.shape
        r_floor = 0.5 * self.min_corr if self.shrinkage else self.min_corr

        for target in range(n):
            for source in range(n):
                key = (target, (source,))
                
                # Skip if manually set
                if key in self._manual_keys or key in self._forbidden_keys:
                    continue
                
                # Search over lag candidates
                best_corr = 0.0
                best_lag = 0.0
                best_weight = 0.0
                
                for lag_days in lag_candidates:
                    lag_steps = int(round(lag_days / dt))
                    
                    # Need enough data after lag
                    if lag_steps >= T - 1:
                        continue
                    
                    # X[t - lag] predicts Y[t]
                    x_vals = data[:(T - 1 - lag_steps), source]
                    y_vals = data[(1 + lag_steps):, target]
                    x_vals, y_vals = self._valid_overlap(x_vals, y_vals)
                    if len(x_vals) < 12:
                        continue

                    corr = self._safe_corr(x_vals, y_vals)
                    if corr is None or abs(corr) < r_floor:
                        continue
                    
                    # Keep best lag
                    if abs(corr) > abs(best_corr):
                        best_corr = corr
                        best_lag = lag_days
                        best_weight = self._fit_linear_weight(x_vals, y_vals)
                
                # Add relationship if it clears the (soft) threshold
                if abs(best_corr) >= r_floor and best_weight != 0.0:
                    shrink = self._shrink_factor(abs(best_corr))
                    if shrink <= 0.0:
                        continue
                    entry = RelationshipEntry(
                        target_idx=target,
                        source_indices=(source,),
                        relationship_type="auto",
                        weight=best_weight * shrink,
                        formula=None,
                        significance=abs(best_corr),
                        manually_set=False,
                        time_lag=best_lag,
                        lag_steps=int(round(best_lag / dt)),
                    )
                    
                    self._relationships[key] = entry

    def _shrink_factor(self, abs_corr: float) -> float:
        """1.0 above min_corr; with shrinkage, linear ramp to 0 at min_corr/2."""
        if abs_corr >= self.min_corr:
            return 1.0
        if not self.shrinkage:
            return 0.0
        lo = 0.5 * self.min_corr
        return max(0.0, (abs_corr - lo) / (self.min_corr - lo))

    @staticmethod
    def _valid_overlap(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        mask = np.isfinite(x) & np.isfinite(y)
        return x[mask], y[mask]

    @staticmethod
    def _safe_corr(x: np.ndarray, y: np.ndarray) -> Optional[float]:
        if len(x) < 3 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
            return None
        corr = np.corrcoef(x, y)[0, 1]
        return None if np.isnan(corr) else float(corr)
    
    def _fit_triplets(self, data: np.ndarray, dt: float, lag_candidates: np.ndarray):
        """Discover significant triplet relationships with optimal time lags."""
        T, n = data.shape
        
        # For efficiency, only check selected triplets
        # Strategy: check high-correlation pairs first, then add third variable
        for target in range(n):
            # Get significant pairs for this target
            pair_sources = []
            for source in range(n):
                key = (target, (source,))
                if key in self._relationships:
                    if abs(self._relationships[key].significance) >= self.min_corr:
                        pair_sources.append(source)
            
            # Now check triplets involving these promising sources
            if len(pair_sources) < 2:
                continue
            
            # Limit combinations to avoid explosion
            max_triplets_per_target = 20
            count = 0
            
            for i, s1 in enumerate(pair_sources):
                for s2 in pair_sources[i+1:]:
                    key = (target, (s1, s2))
                    
                    if key in self._manual_keys or key in self._forbidden_keys:
                        continue
                    
                    if count >= max_triplets_per_target:
                        break
                    
                    # Search over lags
                    best_corr = 0.0
                    best_lag = 0.0
                    best_weight = 0.0
                    
                    for lag_days in lag_candidates:
                        lag_steps = int(round(lag_days / dt))
                        
                        if lag_steps >= T - 1:
                            continue
                        
                        # Compute product predictor with lag
                        x_product = data[:(T - 1 - lag_steps), s1] * data[:(T - 1 - lag_steps), s2]
                        y_vals = data[(1 + lag_steps):, target]
                        x_product, y_vals = self._valid_overlap(x_product, y_vals)

                        corr = self._safe_corr(x_product, y_vals)
                        if corr is None or abs(corr) < self.min_corr:
                            continue
                        
                        if abs(corr) > abs(best_corr):
                            best_corr = corr
                            best_lag = lag_days
                            best_weight = self._fit_linear_weight(x_product, y_vals)
                    
                    # Add if significant
                    if abs(best_corr) >= self.min_corr:
                        entry = RelationshipEntry(
                            target_idx=target,
                            source_indices=(s1, s2),
                            relationship_type="auto",
                            weight=best_weight,
                            formula=None,
                            significance=abs(best_corr),
                            manually_set=False,
                            time_lag=best_lag,
                            lag_steps=int(round(best_lag / dt)),
                        )
                        
                        self._relationships[key] = entry
                        count += 1
    
    def _fit_quadruplets(self, data: np.ndarray, dt: float, lag_candidates: np.ndarray):
        """Discover significant quadruplet relationships with optimal time lags (very selective)."""
        T, n = data.shape
        
        # Only discover quadruplets for high-significance triplets
        max_quadruplets_per_target = 10
        
        for target in range(n):
            # Get significant triplets for this target
            triplet_sources = []
            for key, entry in self._relationships.items():
                if key[0] == target and len(key[1]) == 2:
                    if abs(entry.significance) >= self.min_corr * 1.2:  # higher bar
                        triplet_sources.append(key[1])
            
            if not triplet_sources:
                continue
            
            count = 0
            for s1, s2 in triplet_sources:
                if count >= max_quadruplets_per_target:
                    break
                
                # Try adding a third source
                for s3 in range(n):
                    if s3 in (s1, s2):
                        continue
                    
                    key = (target, tuple(sorted([s1, s2, s3])))
                    
                    if key in self._manual_keys or key in self._forbidden_keys:
                        continue
                    
                    # Search over lags
                    best_corr = 0.0
                    best_lag = 0.0
                    best_weight = 0.0
                    
                    for lag_days in lag_candidates:
                        lag_steps = int(round(lag_days / dt))
                        
                        if lag_steps >= T - 1:
                            continue
                        
                        # Compute 3-way product predictor with lag
                        x_product = (data[:(T - 1 - lag_steps), s1] * 
                                     data[:(T - 1 - lag_steps), s2] * 
                                     data[:(T - 1 - lag_steps), s3])
                        y_vals = data[(1 + lag_steps):, target]
                        x_product, y_vals = self._valid_overlap(x_product, y_vals)

                        corr = self._safe_corr(x_product, y_vals)
                        if corr is None or abs(corr) < self.min_corr:
                            continue
                        
                        if abs(corr) > abs(best_corr):
                            best_corr = corr
                            best_lag = lag_days
                            best_weight = self._fit_linear_weight(x_product, y_vals)
                    
                    # Add if significant
                    if abs(best_corr) >= self.min_corr:
                        entry = RelationshipEntry(
                            target_idx=target,
                            source_indices=tuple(sorted([s1, s2, s3])),
                            relationship_type="auto",
                            weight=best_weight,
                            formula=None,
                            significance=abs(best_corr),
                            manually_set=False,
                            time_lag=best_lag,
                            lag_steps=int(round(best_lag / dt)),
                        )
                        
                        self._relationships[key] = entry
                        count += 1
    
    def _fit_linear_weight(self, x: np.ndarray, y: np.ndarray) -> float:
        """Fit linear weight via least squares."""
        denom = float(np.dot(x, x)) + 1e-8
        return float(np.dot(x, y) / denom)

    def _joint_refit(
        self,
        data: np.ndarray,
        dt: float,
        alpha: float,
        beta: float,
        l1_penalty: float,
    ) -> None:
        """Jointly estimate all non-fixed terms for each target."""
        if beta <= 0:
            raise ValueError("beta must be positive for joint estimation")

        for entry in self._relationships.values():
            entry.lag_steps = int(round(entry.time_lag / dt))

        for target in range(self.n):
            entries = self.get_relationships_for_target(target)
            estimated = [
                entry for entry in entries
                if not (entry.manually_set and entry.constraint == "fixed")
                and entry.relationship_type != "nonlinear"
            ]
            max_lag = max((entry.lag_steps for entry in entries), default=0)
            rows = np.arange(max_lag, len(data) - 1)
            if len(rows) < 3:
                continue

            y = data[rows + 1, target] - alpha * data[rows, target]
            fixed = np.zeros(len(rows))
            for entry in entries:
                if entry in estimated:
                    continue
                values = [
                    data[rows - entry.lag_steps, source]
                    for source in entry.source_indices
                ]
                fixed += beta * np.asarray(
                    [entry.evaluate(*items) for items in zip(*values)]
                )
            y = y - fixed

            if not estimated:
                finite = np.isfinite(y)
                self.intercepts[target] = float(np.mean(y[finite])) if finite.any() else 0.0
                continue

            columns = []
            for entry in estimated:
                values = data[rows - entry.lag_steps][:, entry.source_indices]
                if entry.feature_transform is None:
                    columns.append(np.prod(values, axis=1))
                else:
                    columns.append(
                        np.asarray([entry.feature_transform(*row) for row in values])
                    )
            X = np.column_stack(columns)
            valid = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
            X = X[valid]
            y_valid = y[valid]
            if len(y_valid) < max(3, len(estimated)):
                continue

            x_mean = X.mean(axis=0)
            y_mean = float(y_valid.mean())
            X_centered = X - x_mean
            y_centered = y_valid - y_mean
            coefficients = self._projected_lasso(
                X_centered,
                y_centered,
                np.asarray([entry.lower_bound * beta for entry in estimated]),
                np.asarray([entry.upper_bound * beta for entry in estimated]),
                l1_penalty,
            )
            self.intercepts[target] = y_mean - float(x_mean @ coefficients)
            for entry, coefficient in zip(estimated, coefficients):
                entry.weight = float(coefficient / beta)

        removable = [
            key for key, entry in self._relationships.items()
            if not entry.manually_set and abs(entry.weight) < 1e-8
        ]
        for key in removable:
            del self._relationships[key]

    @staticmethod
    def _projected_lasso(
        X: np.ndarray,
        y: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        penalty: float,
        iterations: int = 1000,
    ) -> np.ndarray:
        """Proximal-gradient lasso with box/sign projection."""
        spectral_norm = float(np.linalg.norm(X, ord=2))
        step = 1.0 / max(spectral_norm * spectral_norm / len(X), 1e-12)
        coefficients = np.zeros(X.shape[1])
        threshold = step * max(0.0, penalty)
        for _ in range(iterations):
            gradient = X.T @ (X @ coefficients - y) / len(X)
            candidate = coefficients - step * gradient
            candidate = np.sign(candidate) * np.maximum(np.abs(candidate) - threshold, 0.0)
            candidate = np.clip(candidate, lower, upper)
            if np.max(np.abs(candidate - coefficients)) < 1e-9:
                coefficients = candidate
                break
            coefficients = candidate
        return coefficients
    
    # ──────────────────────────────────────────────────────────────────────────
    # APPLY RELATIONSHIPS WITH TIME LAGS
    # ──────────────────────────────────────────────────────────────────────────
    
    def apply(self, M_history: np.ndarray, dt: float = 1.0) -> np.ndarray:
        """
        Compute total influence from all relationships with time lags.
        
        For each target variable i:
            influence[i] = Σ all relationships targeting i, evaluated at lagged times
        
        Parameters
        ----------
        M_history : (T, n) array — historical magnitudes (normalized)
                    M_history[-1] is current time t
                    M_history[-2] is t - dt
                    M_history[0] is t - (T-1)*dt
        dt        : time step size in days
        
        Returns
        -------
        influence : (n,) array — total influence on each variable at current time
        
        Notes
        -----
        If a relationship requires a lag longer than available history,
        it uses the oldest available state (graceful degradation).
        """
        if M_history.ndim == 1:
            # Single state provided, no history for lags
            M_history = M_history.reshape(1, -1)
        
        T_history, n = M_history.shape
        if n != self.n:
            raise ValueError(f"M_history has {n} variables but matrix expects {self.n}")
        
        influence = np.zeros(self.n)
        
        for key, entry in self._relationships.items():
            target = entry.target_idx
            sources = entry.source_indices
            lag_steps = entry.lag_steps or int(round(entry.time_lag / dt))
            
            # Determine which historical index to use
            # M_history[-1] is current (t), M_history[-1 - lag_steps] is (t - lag)
            history_idx = -1 - lag_steps
            
            # Clip to available history
            if abs(history_idx) > T_history:
                history_idx = -T_history  # use oldest available
            
            # Get source values at lagged time
            source_values = [M_history[history_idx, s] for s in sources]
            
            # Evaluate relationship
            contrib = entry.evaluate(*source_values)
            
            influence[target] += contrib
        
        return influence
    
    # ──────────────────────────────────────────────────────────────────────────
    # INSPECTION & SUMMARY
    # ──────────────────────────────────────────────────────────────────────────
    
    def get_relationships_by_order(self, order: int) -> list[RelationshipEntry]:
        """Get all relationships of a specific order (2=pair, 3=triplet, etc.)."""
        return [
            entry for entry in self._relationships.values()
            if entry.order == order
        ]
    
    def get_relationships_for_target(self, target: int) -> list[RelationshipEntry]:
        """Get all relationships targeting a specific variable."""
        return [
            entry for entry in self._relationships.values()
            if entry.target_idx == target
        ]
    
    def summary(self, variable_names: Optional[list[str]] = None) -> str:
        """Generate a human-readable summary of all relationships."""
        if variable_names is None:
            variable_names = [f"X{i}" for i in range(self.n)]
        
        lines = []
        lines.append("=" * 80)
        lines.append("INFLUENCE MATRIX V2 — Relationship Summary")
        lines.append("=" * 80)
        lines.append(f"Variables: {self.n}")
        lines.append(f"Min correlation threshold: {self.min_corr}")
        lines.append(f"Max relationship order: {self.max_order}")
        lines.append(f"Total relationships: {len(self._relationships)}")
        lines.append(f"  Manual: {len(self._manual_keys)}")
        lines.append(f"  Auto-discovered: {len(self._relationships) - len(self._manual_keys)}")
        lines.append("")
        
        # Group by order
        for order in range(2, self.max_order + 2):
            entries = self.get_relationships_by_order(order)
            if not entries:
                continue
            
            order_name = {2: "Pairs", 3: "Triplets", 4: "Quadruplets"}.get(order, f"Order-{order}")
            lines.append(f"{order_name} ({len(entries)}):")
            lines.append("-" * 80)
            
            # Sort by significance (manual first, then by strength)
            entries_sorted = sorted(
                entries,
                key=lambda e: (not e.manually_set, -abs(e.significance)),
            )
            
            for entry in entries_sorted[:20]:  # Limit display
                target_name = variable_names[entry.target_idx]
                source_names = [variable_names[s] for s in entry.source_indices]
                
                if entry.relationship_type == "nonlinear":
                    rel_str = f"formula({', '.join(source_names)})"
                else:
                    rel_str = f"{entry.weight:+.4f} × {' × '.join(source_names)}"
                
                manual_flag = "[MANUAL]" if entry.manually_set else ""
                sig_str = f"r={entry.significance:.3f}" if not entry.manually_set else ""
                
                # Format time lag
                if entry.time_lag == 0.0:
                    lag_str = "instant"
                elif entry.time_lag < 0.042:  # < 1 hour
                    lag_str = f"~{entry.time_lag * 24 * 60:.0f}min"
                elif entry.time_lag < 1.0:
                    lag_str = f"~{entry.time_lag * 24:.1f}h"
                else:
                    lag_str = "1day"
                
                lines.append(
                    f"  {target_name:<12} ← {rel_str:<40} lag={lag_str:<8} {sig_str:<12} {manual_flag}"
                )
            
            if len(entries) > 20:
                lines.append(f"  ... and {len(entries) - 20} more")
            lines.append("")
        
        lines.append("=" * 80)
        return "\n".join(lines)
    
    def to_matrix(self, order: int = 2) -> np.ndarray:
        """
        Export relationships of a specific order as a matrix (for visualization).
        
        Only works for pairs (order=2). Returns (n, n) array.
        For higher orders, returns empty array.
        """
        if order != 2:
            warnings.warn(f"Matrix export only supported for pairs (order=2), not order={order}")
            return np.zeros((self.n, self.n))
        
        matrix = np.zeros((self.n, self.n))
        
        for key, entry in self._relationships.items():
            if entry.order == 2:
                target = entry.target_idx
                source = entry.source_indices[0]
                matrix[target, source] = entry.weight
        
        return matrix
