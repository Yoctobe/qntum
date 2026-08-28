"""
SCENARIO ENGINE for QNTUM
═══════════════════════════════════════════════════════════════════════════════

Interactive timeline simulation on top of the QNTUM dynamics:

    - PIN-AND-PROPAGATE : any cell (channel, time) can be pinned to a value.
      At each step the model update is computed, then pinned channels are
      overwritten with their pinned values, so the constraint propagates to
      all other channels through the influence matrix.

    - COUNTERFACTUALS   : pins or events placed before the end of observed
      history move the simulation start back; from that point the model takes
      over and history diverges ("what if CPI had been X in 2023").

    - LATENT EVENTS     : narrative shocks (war, embargo, pandemic) are
      exogenous forcing terms, NOT system channels. Each event has a phase
      envelope Φ (formation → stable → decay), an intensity, and first-hop
      couplings expressed in z-units per step. Because events never receive
      feedback, adding them cannot destabilize the fitted dynamics.

Cell status semantics:
    OBSERVED (1) : historical data, untouched
    PINNED   (2) : user constraint (edit or intervention)
    SIMULATED(3) : model output

All simulation state lives in the standardized increment space produced by
DataPreprocessor; levels are reconstructed exactly via its inverse transform.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

from .data_preprocessor import DataPreprocessor, NormalizationParams, TRANSFORM_LOG_DIFF
from .influence_matrix_v2 import InfluenceMatrixV2
from .quantum_v2 import stabilize_beta
from .quantum_v1 import normalize_rows, clamp_to_bound, DEFAULT_CLAMP

OBSERVED, PINNED, SIMULATED = 1, 2, 3
DYNAMICS_CHOICES = ("v1", "v2")


@dataclass
class Pin:
    """A user-imposed level value at (channel, time index)."""
    channel: str
    t_idx: int
    value: float


@dataclass
class EventInstance:
    """
    A latent shock placed on the timeline.

    first_hop : {channel_name: weight} — the peak LEVEL DISPLACEMENT of the
                target in z-units (robust SDs of its per-step change) at full
                intensity. The engine forces the DERIVATIVE of the phase
                envelope, so the displacement builds during formation, holds
                during the stable phase, and unwinds during decay — e.g. an
                oil weight of 8 with scale 7.5%/month means oil rises ≈ +60%
                (log) while the event is active and reverts as it fades.
                Memory echoes amplify the peak by roughly 1/(1−α).
    formation / tau are in time steps.
    """
    name: str
    t0_idx: int
    intensity: float
    formation: int
    tau: int
    first_hop: dict[str, float] = field(default_factory=dict)

    def phase(self, t_idx: int) -> float:
        if t_idx < self.t0_idx:
            return 0.0
        if self.formation > 0 and t_idx < self.t0_idx + self.formation:
            return (t_idx - self.t0_idx) / self.formation
        end_stable = self.t0_idx + self.formation + max(self.tau, 1)
        if t_idx < end_stable:
            return 1.0
        return float(np.exp(-(t_idx - end_stable) / max(self.tau, 1)))

    def trajectory(self, T: int) -> list[float]:
        return [self.intensity * self.phase(t) for t in range(T)]


class ScenarioEngine:
    """
    Fitted QNTUM system + scenario evaluation.

    The engine is fitted once from a levels DataFrame (DatetimeIndex, one
    column per channel); `simulate()` is then a pure function of the scenario
    (pins, events, horizon) and can be called on every UI interaction.
    """

    def __init__(
        self,
        levels: pd.DataFrame,
        transform_overrides: Optional[dict[str, str]] = None,
        alpha: float = 0.30,
        beta: float = 0.50,
        dt: float = 30.0,
        min_corr: Optional[float] = None,
        max_history_steps: int = 60,
        max_spectral_radius: float = 0.90,
        manual_relationships: Optional[list[tuple]] = None,
        prior_relationships: Optional[list[tuple]] = None,
        fit_levels: Optional[pd.DataFrame] = None,
        max_pin_z: float = 4.0,
        event_forcing_cap: float = 60.0,
        clamp_v1: float = DEFAULT_CLAMP,
    ):
        if not isinstance(levels.index, pd.DatetimeIndex):
            raise ValueError("levels must have a DatetimeIndex")

        self.levels_df = levels.astype(float)
        self.dates = levels.index
        self.channel_names: list[str] = levels.columns.tolist()
        self.transform_overrides = transform_overrides or {}
        # α is deliberately low: per-channel persistence is carried by the
        # FITTED self-relationships; a high global α double-counts momentum
        # and makes every shock persist for years.
        self.alpha = alpha
        self.beta0 = beta
        self.max_spectral_radius = max_spectral_radius
        self.dt = dt
        self.min_corr = min_corr
        self.max_history_steps = max_history_steps
        # Pinned couplings: (target_name, source_name, weight[, lag_days]).
        # Set BEFORE discovery and never overwritten by it.
        self.manual_relationships = list(manual_relationships or [])
        # Prior couplings: same shape, but applied AFTER discovery and only
        # where discovery found nothing — textbook economics as a fallback,
        # never overriding what the data says.
        self.prior_relationships = list(prior_relationships or [])
        # Optional longer panel (outer join, NaNs allowed) used only for
        # coupling discovery: each pair is fitted on its own valid overlap,
        # so e.g. CPI←oil can learn from pre-2006 history even though the
        # simulation panel starts later.
        self.fit_levels_df = fit_levels.astype(float) if fit_levels is not None else None
        # Pinned LEVELS are honored exactly, but the increment fed into
        # propagation is winsorized at ±max_pin_z so a 16σ pin doesn't get
        # extrapolated linearly by the momentum couplings.
        self.max_pin_z = max_pin_z
        # Total exogenous event displacement per channel passes through a
        # tanh soft cap: single events are essentially unchanged, stacked
        # events saturate instead of compounding to absurdity.
        self.event_forcing_cap = event_forcing_cap
        # v1 (documentation/QNTUM-model.md) bounds each step directly instead
        # of shrinking β to satisfy a spectral-radius cap; see quantum_v1.py.
        self.clamp_v1 = clamp_v1

        self._step_offset = self._infer_step_offset()
        self._fit()

    # ──────────────────────────────────────────────────────────────────────
    # FITTING
    # ──────────────────────────────────────────────────────────────────────

    def _infer_step_offset(self) -> pd.DateOffset:
        delta_days = int(np.median(np.diff(self.dates.values).astype("timedelta64[D]").astype(int)))
        if delta_days > 60:
            return pd.DateOffset(months=3)
        if delta_days > 20:
            return pd.DateOffset(months=1)
        if delta_days > 5:
            return pd.DateOffset(weeks=1)
        return pd.DateOffset(days=1)

    def _fit(self):
        prep = DataPreprocessor()

        if self.fit_levels_df is not None:
            # Estimate normalization + couplings on the long panel (NaN-aware,
            # per-pair overlap), then express the simulation panel in that
            # same z-space.
            fit_panel = self.fit_levels_df.reindex(columns=self.channel_names)
            fit_normalized, self.params = prep.transform(
                fit_panel.values, self.channel_names, self.transform_overrides
            )
            self.normalized = prep.apply_params(self.levels_df.values, self.params)
        else:
            self.normalized, self.params = prep.transform(
                self.levels_df.values, self.channel_names, self.transform_overrides
            )
            fit_normalized = self.normalized
        self._prep = prep

        T = len(self.normalized)
        n = len(self.channel_names)

        # Significance-based threshold: |r| must exceed ~2/√T to be signal
        min_corr = self.min_corr if self.min_corr is not None else max(0.15, 2.0 / np.sqrt(T))

        self.I = InfluenceMatrixV2(
            n_variables=n,
            min_corr=min_corr,
            max_order=2,
            max_lag_days=self.dt,
            shrinkage=True,
        )
        idx = {name: i for i, name in enumerate(self.channel_names)}
        for rel in self.manual_relationships:
            target, source, weight = rel[0], rel[1], rel[2]
            lag = rel[3] if len(rel) > 3 else 0.0
            self.I.set_pair(idx[target], idx[source], weight, time_lag=lag)
        self.I.fit(
            fit_normalized,
            discover_pairs=True,
            dt=self.dt,
            search_lags=True,
            lag_search_steps=4,
        )
        # Priors fill in only where discovery stayed silent
        for rel in self.prior_relationships:
            target, source, weight = rel[0], rel[1], rel[2]
            lag = rel[3] if len(rel) > 3 else 0.0
            if target not in idx or source not in idx:
                continue
            key = (idx[target], (idx[source],))
            if key not in self.I._relationships:
                self.I.set_pair(idx[target], idx[source], weight, time_lag=lag)

        # v2: boundedness enforced globally by shrinking β until the
        # linearized system's spectral radius clears a cap (checked once).
        self.beta_v2 = stabilize_beta(self.I, self.alpha, self.beta0, max_rho=self.max_spectral_radius)
        # v1: no shrinkage needed — boundedness is enforced per step by
        # clamp_to_bound instead (see quantum_v1.py), so β keeps its declared
        # value.
        self.beta_v1 = self.beta0

        self.residual_std_v2 = self._one_step_residual_std("v2")
        self.residual_std_v1 = self._one_step_residual_std("v1")

    def _step_core(self, M_prev: np.ndarray, hist: np.ndarray, dynamics: str) -> np.ndarray:
        """
        The bare recurrence (memory + influence), before forcing/pins/noise.

        v2 : M = α·M_prev + β·I(hist)                    [spectral cap on β]
        v1 : M = clamp(α·M_prev + β·I(hist/‖hist‖_∞))     [per-step clamp]
        """
        if dynamics == "v1":
            influence = self.I.apply(normalize_rows(hist), dt=self.dt)
            M = self.alpha * M_prev + self.beta_v1 * influence
            return clamp_to_bound(M, self.clamp_v1)
        influence = self.I.apply(hist, dt=self.dt)
        return self.alpha * M_prev + self.beta_v2 * influence

    def _one_step_residual_std(self, dynamics: str) -> np.ndarray:
        """Per-channel std of one-step-ahead residuals over history."""
        Tn = len(self.normalized)
        residuals = []
        for t in range(1, Tn):
            hist = self.normalized[max(0, t - self.max_history_steps):t]
            pred = self._step_core(self.normalized[t - 1], hist, dynamics)
            residuals.append(self.normalized[t] - pred)
        std = np.std(np.array(residuals), axis=0)
        return np.maximum(std, 0.05)

    # ──────────────────────────────────────────────────────────────────────
    # INCREMENT ↔ LEVEL HELPERS
    # ──────────────────────────────────────────────────────────────────────

    def _z_from_levels(self, prev_level: float, level: float, i: int) -> float:
        if self.params.transform_types[i] == TRANSFORM_LOG_DIFF:
            d = np.log(level) - np.log(prev_level)
        else:
            d = level - prev_level
        return float((d - self.params.centers[i]) / self.params.scale_factors[i])

    def _level_step(self, prev_level: float, z: float, i: int) -> float:
        d = z * self.params.scale_factors[i] + self.params.centers[i]
        if self.params.transform_types[i] == TRANSFORM_LOG_DIFF:
            return float(prev_level * np.exp(d))
        return float(prev_level + d)

    # ──────────────────────────────────────────────────────────────────────
    # SIMULATION
    # ──────────────────────────────────────────────────────────────────────

    def future_dates(self, horizon: int) -> pd.DatetimeIndex:
        start = self.dates[-1]
        return pd.DatetimeIndex([start + self._step_offset * (k + 1) for k in range(horizon)])

    def simulate(
        self,
        pins: Optional[list[Pin]] = None,
        events: Optional[list[EventInstance]] = None,
        horizon: int = 24,
        n_bootstrap: int = 100,
        seed: int = 42,
        anticipation: int = 0,
        replay_from_idx: Optional[int] = None,
        dynamics: str = "v2",
    ) -> dict:
        """
        Evaluate a scenario. Returns levels, cell statuses and CI per channel
        over the full timeline (observed history + horizon).

        anticipation : months of lead with which the path starts leaning
        toward upcoming pins (markets front-running announced policy). The
        pre-move enters the increment buffer, so other channels react to the
        expectation, not just the realization. 0 = off.

        replay_from_idx : if set, forces the simulation to start replaying
        (with the already-fitted dynamics, no pins needed) from this index —
        "what would the model have said from here forward", so the result
        can be plotted against what actually happened.

        dynamics : "v2" (default — spectral-radius-capped linear dynamics)
        or "v1" (documentation/QNTUM-model.md's relative-scale coupling with
        a per-step clamp). Same fitted influence store either way; only the
        recurrence differs.
        """
        if dynamics not in DYNAMICS_CHOICES:
            raise ValueError(f"dynamics must be one of {DYNAMICS_CHOICES}, got {dynamics!r}")
        pins = pins or []
        events = events or []
        n_obs = len(self.levels_df)
        T_total = n_obs + horizon
        n = len(self.channel_names)
        ch_idx = {name: i for i, name in enumerate(self.channel_names)}

        pin_map: dict[tuple[int, int], float] = {}
        for p in pins:
            if p.channel not in ch_idx:
                raise ValueError(f"Unknown channel: {p.channel}")
            t = max(1, min(p.t_idx, T_total - 1))  # t=0 is the anchor, not editable
            pin_map[(t, ch_idx[p.channel])] = float(p.value)

        # Anticipation targets: for each step in the lead window before a pin,
        # the nearest upcoming pin on that channel
        anticip_map: dict[tuple[int, int], tuple[int, float]] = {}
        if anticipation > 0:
            for (tp, i), v in pin_map.items():
                for t in range(max(1, tp - anticipation), tp):
                    if (t, i) in pin_map:
                        continue
                    prev = anticip_map.get((t, i))
                    if prev is None or tp < prev[0]:
                        anticip_map[(t, i)] = (tp, v)

        # Simulation start: end of history, or earliest edit (counterfactual)
        sim_start = n_obs
        if pin_map:
            sim_start = min(sim_start, min(t for t, _ in pin_map) - anticipation)
        for e in events:
            sim_start = min(sim_start, max(1, e.t0_idx))
        if replay_from_idx is not None:
            sim_start = min(sim_start, max(1, replay_from_idx))
        sim_start = max(1, sim_start)

        forcing = self._event_forcing(events, ch_idx, T_total)

        point = self._run_path(pin_map, anticip_map, anticipation, forcing, sim_start, T_total, rng=None, dynamics=dynamics)

        lower = upper = None
        if n_bootstrap > 0:
            rng = np.random.default_rng(seed)
            samples = np.zeros((n_bootstrap, T_total - sim_start, n))
            for b in range(n_bootstrap):
                path = self._run_path(pin_map, anticip_map, anticipation, forcing, sim_start, T_total, rng=rng, dynamics=dynamics)
                samples[b] = path[sim_start:]
            lower = np.percentile(samples, 5, axis=0)
            upper = np.percentile(samples, 95, axis=0)

        status = np.full((T_total, n), SIMULATED, dtype=np.int8)
        status[:sim_start] = OBSERVED
        for (t, i) in pin_map:
            status[t, i] = PINNED

        all_dates = self.dates.append(self.future_dates(horizon))

        return {
            "dates": all_dates,
            "sim_start": sim_start,
            "levels": point,
            "status": status,
            "lower": lower,   # (T_total - sim_start, n) or None
            "upper": upper,
            "events": [
                {"name": e.name, "trajectory": e.trajectory(T_total)} for e in events
            ],
            "dynamics": dynamics,
        }

    def _event_forcing(
        self,
        events: list[EventInstance],
        ch_idx: dict[str, int],
        T_total: int,
    ) -> Optional[np.ndarray]:
        """
        Total exogenous displacement per (step, channel), soft-capped.

        Displacement semantics: the forcing applied at step t is the
        DERIVATIVE F[t] − F[t−1], so the level tracks the (saturated)
        envelope — rises during formation, holds while stable, unwinds
        during decay. The tanh cap leaves single events essentially
        unchanged and saturates stacked events.
        """
        if not events:
            return None
        n = len(ch_idx)
        F = np.zeros((T_total, n))
        for e in events:
            hops = [(ch_idx[c], w) for c, w in e.first_hop.items() if c in ch_idx]
            phases = np.array([e.phase(t) for t in range(T_total)])
            for i, w in hops:
                F[:, i] += phases * e.intensity * w
        cap = self.event_forcing_cap
        return cap * np.tanh(F / cap)

    def _run_path(
        self,
        pin_map: dict[tuple[int, int], float],
        anticip_map: dict[tuple[int, int], tuple[int, float]],
        anticipation: int,
        forcing: Optional[np.ndarray],
        sim_start: int,
        T_total: int,
        rng: Optional[np.random.Generator],
        dynamics: str = "v2",
    ) -> np.ndarray:
        n = len(self.channel_names)
        levels = np.zeros((T_total, n))
        levels[: min(sim_start, len(self.levels_df))] = self.levels_df.values[:sim_start]
        residual_std = self.residual_std_v1 if dynamics == "v1" else self.residual_std_v2

        # History buffer of increments into levels 1..sim_start-1
        buffer = [row for row in self.normalized[: sim_start - 1]]
        buffer = buffer[-self.max_history_steps:]
        M_prev = buffer[-1] if buffer else np.zeros(n)

        for t in range(sim_start, T_total):
            hist = np.array(buffer) if buffer else M_prev.reshape(1, -1)
            M = self._step_core(M_prev, hist, dynamics)

            if forcing is not None:
                M = M + (forcing[t] - forcing[t - 1])

            if rng is not None:
                M = M + rng.normal(0.0, residual_std)

            for i in range(n):
                pinned = pin_map.get((t, i))
                if pinned is not None:
                    # Level honored exactly; the increment that propagates is
                    # winsorized so extreme pins act as saturated shocks
                    levels[t, i] = pinned
                    z = self._z_from_levels(levels[t - 1, i], pinned, i)
                    M[i] = float(np.clip(z, -self.max_pin_z, self.max_pin_z))
                    continue

                level = self._level_step(levels[t - 1, i], M[i], i)
                target = anticip_map.get((t, i))
                if target is not None:
                    # Lean toward the upcoming pin, harder as it approaches;
                    # the adjusted increment enters the buffer and propagates
                    tp, v = target
                    remaining = tp - t
                    desired = levels[t - 1, i] + (v - levels[t - 1, i]) / (remaining + 1)
                    w = (anticipation - remaining + 1) / (anticipation + 1)
                    level = level + (desired - level) * w
                    z = self._z_from_levels(levels[t - 1, i], level, i)
                    M[i] = float(np.clip(z, -self.max_pin_z, self.max_pin_z))
                levels[t, i] = level

            buffer.append(M)
            if len(buffer) > self.max_history_steps:
                buffer.pop(0)
            M_prev = M

        return levels

    # ──────────────────────────────────────────────────────────────────────
    # CHANNEL MANAGEMENT (new-event wizard, observable kind)
    # ──────────────────────────────────────────────────────────────────────

    def add_channel(
        self,
        name: str,
        series: pd.Series,
        transform: str = "diff",
    ) -> dict:
        """
        Add an observable channel and refit the whole system.

        The series is aligned on dates; the common (inner) date range across
        all channels becomes the new history. Returns the relationships
        discovered for the new channel.
        """
        if name in self.channel_names:
            raise ValueError(f"Channel {name} already exists")

        series = series.astype(float)
        series.name = name
        merged = self.levels_df.join(series, how="inner").dropna()
        if len(merged) < 12:
            raise ValueError(
                f"Only {len(merged)} overlapping observations after alignment — need ≥ 12"
            )

        self.levels_df = merged
        self.dates = merged.index
        self.channel_names = merged.columns.tolist()
        self.transform_overrides[name] = transform
        if self.fit_levels_df is not None:
            self.fit_levels_df = self.fit_levels_df.join(series, how="outer")
        self._fit()

        idx = self.channel_names.index(name)
        discovered = [
            {
                "target": self.channel_names[e.target_idx],
                "source": self.channel_names[e.source_indices[0]],
                "weight": e.weight,
                "significance": e.significance,
            }
            for e in self.I._relationships.values()
            if e.order == 2 and (e.target_idx == idx or e.source_indices[0] == idx)
        ]
        return {"n_observations": len(merged), "relationships": discovered}

    # ──────────────────────────────────────────────────────────────────────
    # COUPLING MANAGEMENT (editable matrix)
    # ──────────────────────────────────────────────────────────────────────

    def set_coupling(self, target: str, source: str, weight: float, lag_days: float = 0.0):
        """Pin a coupling manually and refit (discovery respects the pin)."""
        for name in (target, source):
            if name not in self.channel_names:
                raise ValueError(f"Unknown channel: {name}")
        self.manual_relationships = [
            r for r in self.manual_relationships if not (r[0] == target and r[1] == source)
        ]
        self.manual_relationships.append((target, source, weight, lag_days))
        self._fit()

    def remove_coupling(self, target: str, source: str):
        """Drop a manual coupling and refit (auto-discovery may take over)."""
        self.manual_relationships = [
            r for r in self.manual_relationships if not (r[0] == target and r[1] == source)
        ]
        self._fit()

    # ──────────────────────────────────────────────────────────────────────
    # INTROSPECTION
    # ──────────────────────────────────────────────────────────────────────

    def describe(self) -> dict:
        pairs = [
            {
                "target": self.channel_names[e.target_idx],
                "source": self.channel_names[e.source_indices[0]],
                "weight": round(e.weight, 4),
                "significance": round(e.significance, 3),
                "lag_days": e.time_lag,
                "manual": e.manually_set,
            }
            for e in self.I._relationships.values()
            if e.order == 2
        ]
        return {
            "channels": [
                {
                    "name": name,
                    "transform": self.params.transform_types[i],
                    "center": float(self.params.centers[i]),
                    "scale": float(self.params.scale_factors[i]),
                }
                for i, name in enumerate(self.channel_names)
            ],
            "alpha": self.alpha,
            "beta_v1": self.beta_v1,
            "beta_v2": self.beta_v2,
            "clamp_v1": self.clamp_v1,
            "max_spectral_radius": self.max_spectral_radius,
            "min_corr": self.I.min_corr,
            "relationships": sorted(pairs, key=lambda r: -abs(r["significance"])),
            "influence_matrix": self.I.to_matrix(order=2).tolist(),
        }
