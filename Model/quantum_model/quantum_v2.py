"""
QUANTUM MODEL V2 — Simplified Magnitude Dynamics
═══════════════════════════════════════════════════════════════════════════════

Profound simplification based on normalized data:
    - All inputs are % change normalized to [-1, 1]
    - NO SCALING NEEDED in magnitude dynamics
    - Clean, direct update equation
    - Influence matrix captures ALL dynamics

CORE EQUATION (simplified):

    M_i(t+1) = α·M_i(t)  +  β·Φ_i(t)·Σ_relationships + B_i

Where:
    α·M_i(t)                    ← Memory term (persistence)
    β·Φ_i(t)·Σ_relationships    ← Influence from all relationships
    Σ_relationships             ← From InfluenceMatrixV2 (all orders)
    B_i                         ← Base drift (typically 0 for normalized data)
    Φ_i(t)                      ← Phase function (event activation)

NO SCALING, NO CLAMPING — data is already normalized!

This is the "true" quantum model: pure relationship dynamics on normalized space.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable
from .influence_matrix_v2 import InfluenceMatrixV2


# ══════════════════════════════════════════════════════════════════════════════
# EVENT (unchanged from v1)
# ══════════════════════════════════════════════════════════════════════════════

class EventState(Enum):
    INACTIVE = 0
    FORMATION = 1
    STABLE = 2
    DECAY = 3


@dataclass
class Event:
    """
    Event definition with phase function.
    
    Parameters
    ----------
    t0                : start time
    tf                : formation duration
    tau               : decay constant
    initial_magnitude : initial value (normalized)
    name              : variable name
    base_level        : drift offset (typically 0 for normalized data)
    """
    t0: float
    tf: float
    tau: float
    initial_magnitude: float
    name: str
    base_level: float = 0.0
    
    def phase(self, t: float) -> float:
        """
        Phase function Φ(t) ∈ [0, 1].
        
        Returns activation level at time t.
        """
        if t < self.t0:
            return 0.0
        if t < self.t0 + self.tf:
            return (t - self.t0) / self.tf
        if t < self.t0 + self.tf + self.tau:
            return 1.0
        return float(np.exp(-(t - (self.t0 + self.tf + self.tau)) / self.tau))
    
    def state(self, t: float) -> EventState:
        """Return the current phase state."""
        if t < self.t0:
            return EventState.INACTIVE
        if t < self.t0 + self.tf:
            return EventState.FORMATION
        if t < self.t0 + self.tf + self.tau:
            return EventState.STABLE
        return EventState.DECAY


# ══════════════════════════════════════════════════════════════════════════════
# QUANTUM MODEL V2
# ══════════════════════════════════════════════════════════════════════════════

class QuantumV2:
    """
    QUAntified Network of Temporal Unfolding Magnitudes — Version 2.
    
    Simplified dynamics for normalized data WITH TIME LAGS:
    
        M_i(t+1) = α·M_i(t) + β·Φ_i(t)·influence_i(t) + B_i
    
    Where influence_i(t) comes from InfluenceMatrixV2.apply(M_history, dt).
    
    IMPORTANT: Time lags are constrained to [0, dt] — at most one time step back.
    
    NO SCALING NEEDED — data already normalized to [-1, 1].
    
    Parameters
    ----------
    influence : InfluenceMatrixV2 — stores all relationships with time lags
    alpha     : memory persistence ∈ [0, 1)
    beta      : influence strength
    dt        : time step size in days (e.g., 1/24 for hourly, 1.0 for daily)
    max_history_steps : maximum history buffer size (for memory efficiency)
    
    Usage
    -----
        # Build influence matrix with manual relationships
        I = InfluenceMatrixV2(n_variables=5, min_corr=0.15)
        I.set_pair(0, 1, -0.4, time_lag=0.25)  # 6-hour lag
        I.fit(normalized_data, dt=1.0, discover_pairs=True, discover_triplets=True)
        
        # Create model
        model = QuantumV2(I, alpha=0.85, beta=0.5, dt=1.0)
        
        # Simulate
        results = model.simulate(events, t_end=100)
        
        # Forecast
        forecast = model.forecast(events, n_steps=8, initial_state=last_state)
    """
    
    def __init__(
        self,
        influence: InfluenceMatrixV2,
        alpha: float = 0.85,
        beta: float = 0.50,
        dt: float = 1.0,
        max_history_steps: int = 100,
    ):
        self.I = influence
        self.alpha = alpha
        self.beta = beta
        self.dt = dt
        self.max_history_steps = max_history_steps
        
        # History buffer for lag handling
        self._history_buffer = None
    
    @property
    def n(self) -> int:
        """Number of variables."""
        return self.I.n
    
    # ──────────────────────────────────────────────────────────────────────────
    # CORE UPDATE STEP WITH TIME LAG SUPPORT
    # ──────────────────────────────────────────────────────────────────────────
    
    def step(self, t: float, M: np.ndarray, events: list[Event]) -> np.ndarray:
        """
        Single time step: M(t) → M(t+1) with time lag support.
        
        Simplified equation (no scaling, no clamping):
            M_i(t+1) = α·M_i(t) + β·Φ_i(t)·influence_i(t) + B_i
        
        The influence term uses historical states based on relationship lags.
        
        Parameters
        ----------
        t      : current time
        M      : (n,) current magnitudes (normalized)
        events : list of Event objects (one per variable)
        
        Returns
        -------
        M_next : (n,) next magnitudes
        """
        # Initialize history buffer if needed
        if self._history_buffer is None:
            self._history_buffer = M.reshape(1, -1).copy()
        else:
            # Append current state to history
            self._history_buffer = np.vstack([self._history_buffer, M])
            
            # Trim history to max size
            if len(self._history_buffer) > self.max_history_steps:
                self._history_buffer = self._history_buffer[-self.max_history_steps:]
        
        # Compute influence from all relationships using history
        influence = self.I.apply(self._history_buffer, dt=self.dt)
        
        # Apply update equation
        M_next = np.zeros(self.n)
        for i, event in enumerate(events):
            phi = event.phase(t)
            M_next[i] = (
                self.alpha * M[i]
                + self.beta * phi * influence[i]
                + event.base_level
            )
        
        return M_next
    
    def reset_history(self):
        """Clear the history buffer (useful when starting new simulation)."""
        self._history_buffer = None
    
    # ──────────────────────────────────────────────────────────────────────────
    # SIMULATION
    # ──────────────────────────────────────────────────────────────────────────
    
    def simulate(
        self,
        events: list[Event],
        t_end: float,
        dt: Optional[float] = None,
    ) -> dict:
        """
        Forward simulation from t=0 to t_end.
        
        Parameters
        ----------
        events : list of Event objects (one per variable)
        t_end  : simulation end time
        dt     : time step (if None, uses self.dt)
        
        Returns
        -------
        dict with:
            'time'       : (T,) time array
            'magnitudes' : (T, n) magnitude trajectories
            'events'     : event list
        """
        if dt is None:
            dt = self.dt
        
        n = len(events)
        if n != self.n:
            raise ValueError(f"Event count ({n}) ≠ matrix size ({self.n})")
        
        # Reset history buffer for new simulation
        self.reset_history()
        
        ts = np.arange(0, t_end, dt)
        M_all = np.zeros((len(ts), n))
        
        # Initialize
        for i, event in enumerate(events):
            if event.t0 <= 0:
                M_all[0, i] = event.initial_magnitude
        
        # Time stepping
        for idx in range(1, len(ts)):
            t = ts[idx]
            t_prev = ts[idx - 1]
            M_all[idx] = self.step(t, M_all[idx - 1], events)
            
            # Inject initial magnitude when event starts
            for i, event in enumerate(events):
                if t_prev < event.t0 <= t:
                    M_all[idx, i] = event.initial_magnitude
        
        return {
            "time": ts,
            "magnitudes": M_all,
            "events": events,
        }
    
    # ──────────────────────────────────────────────────────────────────────────
    # FORECAST
    # ──────────────────────────────────────────────────────────────────────────
    
    def forecast(
        self,
        events: list[Event],
        n_steps: int,
        initial_state: Optional[np.ndarray] = None,
        initial_history: Optional[np.ndarray] = None,
        n_bootstrap: int = 0,
        noise_scale: float = 0.03,
        seed: int = 42,
    ) -> dict:
        """
        Multi-step ahead forecast.
        
        Parameters
        ----------
        events          : list of Event objects
        n_steps         : forecast horizon
        initial_state   : (n,) starting state (normalized values)
        initial_history : (T, n) historical states for lag handling
                          If None, uses only initial_state
        n_bootstrap     : number of bootstrap samples for confidence intervals
        noise_scale     : standard deviation for bootstrap noise
        seed            : random seed
        
        Returns
        -------
        dict with:
            'time'  : (n_steps,) time array
            'point' : (n_steps, n) point forecast
            'lower' : (n_steps, n) 5th percentile (if n_bootstrap > 0)
            'upper' : (n_steps, n) 95th percentile (if n_bootstrap > 0)
            'events': event list
        """
        n = len(events)
        if n != self.n:
            raise ValueError(f"Event count ({n}) ≠ matrix size ({self.n})")
        
        if initial_state is None:
            initial_state = np.array([e.initial_magnitude for e in events])
        
        M0 = np.asarray(initial_state, dtype=float).copy()
        
        # Set up history buffer
        if initial_history is not None:
            self._history_buffer = np.asarray(initial_history, dtype=float).copy()
        else:
            self.reset_history()
            self._history_buffer = M0.reshape(1, -1).copy()
        
        # Point forecast
        point = np.zeros((n_steps, n))
        M = M0.copy()
        for k in range(n_steps):
            M = self.step(float(k + 1), M, events)
            point[k] = M
        
        result = {
            "time": np.arange(1, n_steps + 1, dtype=float) * self.dt,
            "point": point,
            "events": events,
        }
        
        # Bootstrap confidence intervals
        if n_bootstrap > 0:
            rng = np.random.default_rng(seed)
            samples = np.zeros((n_bootstrap, n_steps, n))
            
            for b in range(n_bootstrap):
                # Reset history buffer for each bootstrap sample
                if initial_history is not None:
                    self._history_buffer = initial_history.copy()
                else:
                    self.reset_history()
                    self._history_buffer = M0.reshape(1, -1).copy()
                
                M = M0.copy()
                for k in range(n_steps):
                    M = self.step(float(k + 1), M, events)
                    # Add noise (grows slightly with horizon)
                    noise = rng.normal(0.0, noise_scale * (1.0 + 0.03 * k), size=n)
                    M = M + noise
                    samples[b, k] = M
            
            result["lower"] = np.percentile(samples, 5, axis=0)
            result["upper"] = np.percentile(samples, 95, axis=0)
            # Full sample paths, so callers can compute percentiles in level
            # space (percentile-of-paths, not path-of-percentiles)
            result["samples"] = samples
        
        return result
    
    # ──────────────────────────────────────────────────────────────────────────
    # VALIDATION
    # ──────────────────────────────────────────────────────────────────────────
    
    def validate(
        self,
        data: np.ndarray,
        variable_names: list[str],
        train_fraction: float = 0.5,
    ) -> dict:
        """
        Validate model on held-out data.
        
        Uses rolling one-step-ahead prediction on test set.
        
        Parameters
        ----------
        data            : (T, n) normalized data
        variable_names  : list of variable names
        train_fraction  : fraction of data used for training
        
        Returns
        -------
        dict with:
            'mae'  : mean absolute error
            'rmse' : root mean squared error
            'correlations' : dict of {variable: correlation}
            'n_train' : number of training steps
            'n_test'  : number of test steps
        """
        T, n = data.shape
        split = int(T * train_fraction)
        
        test_data = data[split:]
        n_test = len(test_data) - 1
        
        # Create events
        events = [
            Event(
                t0=0,
                tf=0.0,
                tau=float(n_test + 10),
                initial_magnitude=float(data[split - 1, i]),
                base_level=0.0,
                name=variable_names[i],
            )
            for i in range(n)
        ]
        
        # Reset history and use training data as initial history
        history_window = min(self.max_history_steps, split)
        initial_history = data[split - history_window:split]
        self._history_buffer = initial_history.copy()
        
        # Rolling one-step predictions
        predictions = np.zeros((n_test, n))
        for k in range(n_test):
            M_prev = test_data[k]
            predictions[k] = self.step(1.0, M_prev, events)
        
        actuals = test_data[1:]
        
        # Metrics
        mae = float(np.mean(np.abs(predictions - actuals)))
        rmse = float(np.sqrt(np.mean((predictions - actuals) ** 2)))
        
        correlations = {}
        for i in range(n):
            corr = np.corrcoef(predictions[:, i], actuals[:, i])[0, 1]
            correlations[variable_names[i]] = 0.0 if np.isnan(corr) else float(corr)
        
        return {
            "mae": mae,
            "rmse": rmse,
            "correlations": correlations,
            "n_train": split,
            "n_test": n_test,
        }


# ══════════════════════════════════════════════════════════════════════════════
# STABILITY
# ══════════════════════════════════════════════════════════════════════════════

def spectral_radius(influence: InfluenceMatrixV2, alpha: float, beta: float) -> float:
    """
    Spectral radius of the linearized transition matrix α·Id + β·W,
    where W is the pairwise influence matrix.

    ρ < 1 guarantees the noise-free forecast decays toward zero increments
    (levels flatten) instead of exploding. Higher-order relationships are
    not included in this linearization.
    """
    W = influence.to_matrix(order=2)
    A = alpha * np.eye(influence.n) + beta * W
    return float(np.max(np.abs(np.linalg.eigvals(A))))


def stabilize_beta(
    influence: InfluenceMatrixV2,
    alpha: float,
    beta: float,
    max_rho: float = 0.98,
) -> float:
    """
    Shrink β until the linearized dynamics are contractive (ρ ≤ max_rho).

    Requires α < max_rho so a solution always exists (β → 0 gives ρ = α).
    """
    if alpha >= max_rho:
        raise ValueError(f"alpha={alpha} must be < max_rho={max_rho} for stability")

    rho = spectral_radius(influence, alpha, beta)
    if rho <= max_rho:
        return beta

    original_beta = beta
    while rho > max_rho and beta > 1e-6:
        beta *= 0.9
        rho = spectral_radius(influence, alpha, beta)

    print(
        f"  ⚠ Stability cap: spectral radius was "
        f"{spectral_radius(influence, alpha, original_beta):.3f} > {max_rho}, "
        f"β reduced {original_beta:.3f} → {beta:.3f} (ρ = {rho:.3f})"
    )
    return beta


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_quantum_v2(
    normalized_data: np.ndarray,
    variable_names: list[str],
    manual_relationships: Optional[dict] = None,
    min_corr: float = 0.15,
    max_order: int = 3,
    discover_pairs: bool = True,
    discover_triplets: bool = False,
    discover_quadruplets: bool = False,
    alpha: float = 0.85,
    beta: float = 0.50,
    dt: float = 1.0,
    search_lags: bool = True,
    lag_search_steps: int = 10,
    max_history_steps: int = 100,
    max_spectral_radius: float = 0.98,
) -> QuantumV2:
    """
    One-call builder for QuantumV2 model with time lag support.
    
    Parameters
    ----------
    normalized_data       : (T, n) array of normalized % changes
    variable_names        : list of variable names
    manual_relationships  : dict defining manual relationships, e.g.:
                            {
                                'pairs': [(target, source, weight, time_lag), ...],
                                'triplets': [(target, s1, s2, weight, time_lag), ...],
                                'formulas': [(target, sources_tuple, callable, time_lag), ...]
                            }
                            time_lag is optional, defaults to 0.0
    min_corr              : minimum correlation for auto-discovery
    max_order             : maximum relationship order
    discover_pairs        : auto-discover pairwise relationships
    discover_triplets     : auto-discover triplet relationships
    discover_quadruplets  : auto-discover quadruplet relationships
    alpha                 : memory parameter
    beta                  : influence strength
    dt                    : time step size in days
    search_lags           : search for optimal time lags during auto-discovery
    lag_search_steps      : number of lag steps to test (in [0, dt] day range = one time step)
    max_history_steps     : maximum history buffer size
    max_spectral_radius   : cap on ρ(α·Id + β·W); β is shrunk if exceeded,
                            guaranteeing non-explosive forecasts
    
    Returns
    -------
    model : QuantumV2 instance
    
    Example
    -------
        manual_rels = {
            'pairs': [(0, 1, -0.4, 0.25), (0, 2, 0.3, 0.0)],  # 6h lag, instant
            'triplets': [(0, 1, 2, 0.15, 0.5)],  # 12h lag
        }
        
        model = build_quantum_v2(
            normalized_data,
            variable_names,
            manual_relationships=manual_rels,
            min_corr=0.15,
            discover_pairs=True,
            discover_triplets=True,
            dt=1.0,  # daily data
            search_lags=True,
        )
    """
    n = normalized_data.shape[1]
    
    # Create influence matrix
    I = InfluenceMatrixV2(n_variables=n, min_corr=min_corr, max_order=max_order)
    
    # Add manual relationships
    if manual_relationships:
        if 'pairs' in manual_relationships:
            for entry in manual_relationships['pairs']:
                if len(entry) == 3:
                    target, source, weight = entry
                    time_lag = 0.0
                elif len(entry) == 4:
                    target, source, weight, time_lag = entry
                else:
                    raise ValueError(f"Invalid pair entry: {entry}")
                I.set_pair(target, source, weight, time_lag)
        
        if 'triplets' in manual_relationships:
            for entry in manual_relationships['triplets']:
                if len(entry) == 4:
                    target, s1, s2, weight = entry
                    time_lag = 0.0
                elif len(entry) == 5:
                    target, s1, s2, weight, time_lag = entry
                else:
                    raise ValueError(f"Invalid triplet entry: {entry}")
                I.set_triplet(target, s1, s2, weight, time_lag)
        
        if 'quadruplets' in manual_relationships:
            for entry in manual_relationships['quadruplets']:
                if len(entry) == 5:
                    target, s1, s2, s3, weight = entry
                    time_lag = 0.0
                elif len(entry) == 6:
                    target, s1, s2, s3, weight, time_lag = entry
                else:
                    raise ValueError(f"Invalid quadruplet entry: {entry}")
                I.set_quadruplet(target, s1, s2, s3, weight, time_lag)
        
        if 'formulas' in manual_relationships:
            for entry in manual_relationships['formulas']:
                if len(entry) == 3:
                    target, sources, formula = entry
                    time_lag = 0.0
                elif len(entry) == 4:
                    target, sources, formula, time_lag = entry
                else:
                    raise ValueError(f"Invalid formula entry: {entry}")
                I.set_relationship(target, sources, formula=formula, time_lag=time_lag)
    
    # Auto-discover relationships
    I.fit(
        normalized_data,
        discover_pairs=discover_pairs,
        discover_triplets=discover_triplets,
        discover_quadruplets=discover_quadruplets,
        dt=dt,
        search_lags=search_lags,
        lag_search_steps=lag_search_steps,
    )
    
    # Enforce contractive dynamics so multi-step forecasts cannot explode
    beta = stabilize_beta(I, alpha, beta, max_rho=max_spectral_radius)
    
    # Build model
    model = QuantumV2(I, alpha=alpha, beta=beta, dt=dt, max_history_steps=max_history_steps)
    
    return model
