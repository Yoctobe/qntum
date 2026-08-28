"""
BACKTEST HARNESS for the ScenarioEngine
═══════════════════════════════════════════════════════════════════════════════

Two independent checks that turn "treat magnitudes as directional" into
measured numbers:

    WALK-FORWARD : refit the engine on data through each origin, forecast h
                   steps ahead, score MAE against a random-walk baseline
                   (last value carried forward) and measure 90% CI coverage.
                   ratio < 1 means the fitted dynamics beat the naive carry.

    ANALOGUE REPLAY : drop a library event at its historical date as a
                   counterfactual and check the simulated first-hop responses
                   against what actually happened (direction + peak ratio).

CLI (from simulator/backend):
    python3 -m quantum_model.backtest            # walk-forward + COVID replay
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Optional

from .simulator import ScenarioEngine, EventInstance


def walk_forward(
    levels: pd.DataFrame,
    transform_overrides: Optional[dict[str, str]] = None,
    dt: float = 30.0,
    fit_levels: Optional[pd.DataFrame] = None,
    horizons: tuple[int, ...] = (1, 3, 6, 12),
    n_origins: int = 30,
    min_train: int = 120,
    n_bootstrap: int = 40,
    **engine_kwargs,
) -> pd.DataFrame:
    """
    Expanding-window backtest.

    Returns a DataFrame indexed by (channel, horizon) with model MAE,
    random-walk MAE, their ratio, and 90% CI coverage.
    """
    T = len(levels)
    max_h = max(horizons)
    last_origin = T - max_h
    if last_origin <= min_train:
        raise ValueError(f"Need > {min_train + max_h} observations, have {T}")

    origins = np.unique(np.linspace(min_train, last_origin, n_origins, dtype=int))
    names = levels.columns.tolist()

    abs_err = {h: [] for h in horizons}      # lists of (n,) arrays
    abs_err_rw = {h: [] for h in horizons}
    covered = {h: [] for h in horizons}      # lists of (n,) bool arrays

    for origin in origins:
        train = levels.iloc[:origin]
        fit_panel = None
        if fit_levels is not None:
            fit_panel = fit_levels[fit_levels.index <= train.index[-1]]
        engine = ScenarioEngine(
            train,
            transform_overrides=transform_overrides,
            dt=dt,
            fit_levels=fit_panel,
            **engine_kwargs,
        )
        res = engine.simulate(horizon=max_h, n_bootstrap=n_bootstrap)
        last = train.values[-1]

        for h in horizons:
            actual = levels.values[origin + h - 1]
            pred = res["levels"][origin + h - 1]
            abs_err[h].append(np.abs(pred - actual))
            abs_err_rw[h].append(np.abs(last - actual))
            if res["lower"] is not None:
                lo = res["lower"][h - 1]
                hi = res["upper"][h - 1]
                covered[h].append((actual >= lo) & (actual <= hi))

    rows = []
    for h in horizons:
        mae = np.mean(abs_err[h], axis=0)
        mae_rw = np.mean(abs_err_rw[h], axis=0)
        cov = np.mean(covered[h], axis=0) if covered[h] else np.full(len(names), np.nan)
        for i, name in enumerate(names):
            rows.append({
                "channel": name,
                "horizon": h,
                "model_mae": mae[i],
                "rw_mae": mae_rw[i],
                "ratio": mae[i] / mae_rw[i] if mae_rw[i] > 0 else np.nan,
                "coverage_90": cov[i],
            })
    return pd.DataFrame(rows).set_index(["channel", "horizon"])


def analogue_replay(
    engine: ScenarioEngine,
    event_name: str,
    first_hop: dict[str, float],
    t0_date: str,
    intensity: float,
    formation: int,
    tau: int,
    months_after: int = 12,
) -> pd.DataFrame:
    """
    Place an event at a historical date (counterfactual) and compare the
    simulated first-hop responses against what actually happened.

    Returns per first-hop channel: actual vs simulated peak move from the
    event start, and whether the direction matches.
    """
    t0_idx = int(engine.dates.get_indexer([pd.Timestamp(t0_date)], method="nearest")[0])
    end = min(t0_idx + months_after, len(engine.dates) - 1)

    event = EventInstance(
        name=event_name, t0_idx=t0_idx, intensity=intensity,
        formation=formation, tau=tau, first_hop=first_hop,
    )
    res = engine.simulate(events=[event], horizon=1, n_bootstrap=0)

    rows = []
    for ch in first_hop:
        if ch not in engine.channel_names:
            continue
        i = engine.channel_names.index(ch)
        base = engine.levels_df[ch].values[t0_idx - 1]
        actual_move = _peak_move(engine.levels_df[ch].values[t0_idx:end + 1], base)
        sim_move = _peak_move(res["levels"][t0_idx:end + 1, i], base)
        rows.append({
            "channel": ch,
            "actual_peak_move": actual_move,
            "simulated_peak_move": sim_move,
            "direction_hit": bool(np.sign(actual_move) == np.sign(sim_move)),
            "magnitude_ratio": sim_move / actual_move if actual_move != 0 else np.nan,
        })
    return pd.DataFrame(rows).set_index("channel")


def _peak_move(path: np.ndarray, base: float) -> float:
    """Signed displacement from base with the largest magnitude along the path."""
    moves = path - base
    return float(moves[np.argmax(np.abs(moves))])


def main():
    from pathlib import Path

    backend_data = Path(__file__).resolve().parents[2] / "simulator" / "backend" / "data"
    overrides = {
        "Industrial_Production": "log_diff", "Housing": "log_diff",
        "Oil_WTI": "log_diff", "Gold": "log_diff",
        "Dollar_Index": "log_diff", "Nasdaq": "log_diff",
    }
    levels = pd.read_csv(backend_data / "us_macro_monthly.csv", parse_dates=["Date"]).set_index("Date")
    full_path = backend_data / "us_macro_monthly_full.csv"
    fit_levels = (
        pd.read_csv(full_path, parse_dates=["Date"]).set_index("Date")
        if full_path.exists() else None
    )

    print("Walk-forward backtest (expanding window, vs random walk)")
    print("=" * 72)
    report = walk_forward(levels, overrides, dt=30.0, fit_levels=fit_levels)
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(report.reset_index().pivot(index="channel", columns="horizon", values="ratio")
              .rename_axis(columns="MAE ratio @ horizon"))
        print()
        print(report.reset_index().pivot(index="channel", columns="horizon", values="coverage_90")
              .rename_axis(columns="90% CI coverage @ horizon"))

    print()
    print("Analogue replay: COVID-19 pandemic, March 2020, intensity 1.0")
    print("=" * 72)
    engine = ScenarioEngine(levels, transform_overrides=overrides, dt=30.0, fit_levels=fit_levels)
    pandemic_hops = {
        "Industrial_Production": -18.0, "Unemployment": 40.0,
        "Oil_WTI": -10.0, "VIX": 12.0, "Nasdaq": -7.0,
    }
    # 3-month window: measure the shock itself, not the recovery rally
    replay = analogue_replay(
        engine, "COVID-19", pandemic_hops,
        t0_date="2020-03-01", intensity=1.0, formation=2, tau=6,
        months_after=3,
    )
    with pd.option_context("display.float_format", "{:.2f}".format):
        print(replay)


if __name__ == "__main__":
    main()
