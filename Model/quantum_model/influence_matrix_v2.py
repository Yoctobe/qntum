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
from typing import Callable, Optional, Union, Dict, Tuple, Set
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
            )
        else:
            raise ValueError("Must provide either weight or formula")
        
        self._relationships[key] = entry
        self._manual_keys.add(key)
    
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
        
        # Maximum lag = one time step (parameter-agnostic across dt)
        max_lag_days = float(dt)
        max_lag_steps = min(max(1, int(round(max_lag_days / dt))), T - 2)
        
        # Lag candidates to test (in days)
        if search_lags and lag_search_steps > 1:
            lag_candidates = np.linspace(0, max_lag_days, lag_search_steps)
        else:
            lag_candidates = np.array([0.0])  # no lag search, instant only
        
        # Discover pairs (order 2)
        if discover_pairs and 2 <= self.max_order:
            self._fit_pairs(data, dt, lag_candidates)
        
        # Discover triplets (order 3)
        if discover_triplets and 3 <= self.max_order:
            self._fit_triplets(data, dt, lag_candidates)
        
        # Discover quadruplets (order 4)
        if discover_quadruplets and 4 <= self.max_order:
            self._fit_quadruplets(data, dt, lag_candidates)
    
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
                if key in self._manual_keys:
                    continue
                
                # Search over lag candidates
                best_corr = 0.0
                best_lag = 0.0
                best_weight = 0.0
                
                for lag_days in lag_candidates:
                    lag_steps = int(lag_days / dt)
                    
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
                    
                    if key in self._manual_keys:
                        continue
                    
                    if count >= max_triplets_per_target:
                        break
                    
                    # Search over lags
                    best_corr = 0.0
                    best_lag = 0.0
                    best_weight = 0.0
                    
                    for lag_days in lag_candidates:
                        lag_steps = int(lag_days / dt)
                        
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
                    
                    if key in self._manual_keys:
                        continue
                    
                    # Search over lags
                    best_corr = 0.0
                    best_lag = 0.0
                    best_weight = 0.0
                    
                    for lag_days in lag_candidates:
                        lag_steps = int(lag_days / dt)
                        
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
                        )
                        
                        self._relationships[key] = entry
                        count += 1
    
    def _fit_linear_weight(self, x: np.ndarray, y: np.ndarray) -> float:
        """Fit linear weight via least squares."""
        denom = float(np.dot(x, x)) + 1e-8
        return float(np.dot(x, y) / denom)
    
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
            lag_days = entry.time_lag
            
            # Convert lag to time steps
            lag_steps = int(round(lag_days / dt))
            
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
