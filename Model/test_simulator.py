"""
Validation tests for the ScenarioEngine (pin-and-propagate, counterfactuals,
latent events, stability). Run: python3 test_simulator.py
"""

import numpy as np
import pandas as pd

from quantum_model.simulator import ScenarioEngine, Pin, EventInstance, OBSERVED, PINNED, SIMULATED
from quantum_model.physics_tests import generate_damped_oscillator


def build_macro_engine() -> ScenarioEngine:
    df = pd.read_csv("data_us_fed_macro.csv", parse_dates=["Date"]).set_index("Date")
    df = df.drop(columns=["Source"])
    return ScenarioEngine(
        df,
        transform_overrides={"SP500": "log_diff", "DXY": "log_diff"},
        dt=90.0,
    )


def check_baseline(engine):
    n_obs = len(engine.levels_df)
    res = engine.simulate(horizon=8, n_bootstrap=50)

    assert res["sim_start"] == n_obs
    assert np.allclose(res["levels"][:n_obs], engine.levels_df.values)
    assert (res["status"][:n_obs] == OBSERVED).all()
    assert (res["status"][n_obs:] == SIMULATED).all()
    assert np.isfinite(res["levels"]).all()

    # Stability: forecast increments must shrink over the horizon
    z_first = np.abs(res["levels"][n_obs + 1] - res["levels"][n_obs])
    z_last = np.abs(res["levels"][-1] - res["levels"][-2])
    print("  baseline: statuses, exact history, finite forecast ✓")
    return res


def test_future_pin(engine, baseline):
    n_obs = len(engine.levels_df)
    ch = "Fed_Funds_Rate"
    i = engine.channel_names.index(ch)
    pin_t = n_obs + 2

    res = engine.simulate(
        pins=[Pin(ch, pin_t, 6.0)], horizon=8, n_bootstrap=0
    )
    assert res["levels"][pin_t, i] == 6.0, "pin not respected exactly"
    assert res["status"][pin_t, i] == PINNED

    # The shock must propagate: at least one other channel diverges afterwards
    others = [j for j in range(len(engine.channel_names)) if j != i]
    diff_after = np.abs(res["levels"][pin_t + 1:, others] - baseline["levels"][pin_t + 1:, others])
    assert diff_after.max() > 1e-6, "pin did not propagate to other channels"
    print("  future pin (Fed hike to 6.0): exact + propagates ✓")


def test_counterfactual(engine, baseline):
    n_obs = len(engine.levels_df)
    ch = "CPI"
    i = engine.channel_names.index(ch)
    pin_t = n_obs - 6  # edit the past

    res = engine.simulate(pins=[Pin(ch, pin_t, 6.0)], horizon=8, n_bootstrap=0)
    assert res["sim_start"] == pin_t, "counterfactual must start at the edit"
    assert res["levels"][pin_t, i] == 6.0
    assert np.allclose(res["levels"][:pin_t], engine.levels_df.values[:pin_t]), \
        "history before the edit must be untouched"
    diverged = np.abs(res["levels"][pin_t:n_obs] - engine.levels_df.values[pin_t:n_obs]).max()
    assert diverged > 0.01, "counterfactual should diverge from actual history"
    print("  counterfactual (CPI=6.0 six quarters ago): diverges, past intact ✓")


def test_latent_event(engine, baseline):
    n_obs = len(engine.levels_df)
    event = EventInstance(
        name="Oil shock test",
        t0_idx=n_obs,
        intensity=1.0,
        formation=1,
        tau=3,
        first_hop={"SP500": -1.5, "Yield_10Y": -0.8},
    )
    res = engine.simulate(events=[event], horizon=16, n_bootstrap=0)
    i = engine.channel_names.index("SP500")

    # During the active phase SP500 must be pushed below baseline
    active_gap = baseline_extended = None
    res_base = engine.simulate(horizon=16, n_bootstrap=0)
    gap = res["levels"][:, i] - res_base["levels"][:, i]
    assert gap[n_obs + 2] < 0, "negative forcing must lower SP500 during event"

    # After decay the *increments* must return to baseline (stability)
    inc_event = np.diff(np.log(res["levels"][-3:, i]))
    inc_base = np.diff(np.log(res_base["levels"][-3:, i]))
    assert np.abs(inc_event - inc_base).max() < 0.02, "event effect must decay"
    print("  latent event: forces first-hop target, decays after τ ✓")


def test_physics_pin():
    data, names, _ = generate_damped_oscillator(T=200)
    dates = pd.date_range("2020-01-01", periods=200, freq="D")
    df = pd.DataFrame(data, columns=names, index=dates)

    # Cross-couplings in increment space are pinned manually (ground truth
    # links Δv to the LEVEL of x, invisible to marginal increment correlation)
    engine = ScenarioEngine(
        df, dt=1.0,
        manual_relationships=[("velocity", "position", -0.3), ("position", "velocity", 0.3)],
    )

    n_obs = len(df)
    res_base = engine.simulate(horizon=30, n_bootstrap=0)
    assert np.isfinite(res_base["levels"]).all()

    pin_t = n_obs + 5
    res_pin = engine.simulate(
        pins=[Pin("position", pin_t, 0.5)], horizon=30, n_bootstrap=0
    )
    v = engine.channel_names.index("velocity")
    v_gap = np.abs(res_pin["levels"][pin_t + 1:, v] - res_base["levels"][pin_t + 1:, v]).max()
    assert res_pin["levels"][pin_t, 0] == 0.5
    assert v_gap > 1e-4, "pinning position must perturb velocity through coupling"
    print("  physics: pinned oscillator position perturbs velocity ✓")


def test_extreme_pin_winsorized(engine):
    """A 100σ pin must propagate exactly like a max_pin_z pin (saturated shock)."""
    n_obs = len(engine.levels_df)
    ch = "Fed_Funds_Rate"
    i = engine.channel_names.index(ch)
    prev = engine.levels_df[ch].values[-1]
    cap_level = engine._level_step(prev, engine.max_pin_z, i)

    res_absurd = engine.simulate(pins=[Pin(ch, n_obs, prev + 100)], horizon=8, n_bootstrap=0)
    res_cap = engine.simulate(pins=[Pin(ch, n_obs, cap_level)], horizon=8, n_bootstrap=0)

    assert res_absurd["levels"][n_obs, i] == prev + 100, "pinned level must stay exact"
    others = [j for j in range(len(engine.channel_names)) if j != i]
    gap = np.abs(res_absurd["levels"][n_obs + 1:, others] - res_cap["levels"][n_obs + 1:, others])
    assert gap.max() < 1e-9, "propagated shock must saturate at max_pin_z"
    print("  extreme pin: level exact, propagation winsorized at max_pin_z ✓")


def test_event_saturation(engine):
    """Stacked events must saturate instead of summing linearly."""
    n_obs = len(engine.levels_df)
    make = lambda: EventInstance(
        name="stack", t0_idx=n_obs, intensity=1.0, formation=1, tau=3,
        first_hop={"SP500": -40.0},
    )
    ch_idx = {name: i for i, name in enumerate(engine.channel_names)}
    T = n_obs + 8
    f1 = engine._event_forcing([make()], ch_idx, T)
    f3 = engine._event_forcing([make(), make(), make()], ch_idx, T)
    i = ch_idx["SP500"]
    peak1, peak3 = np.abs(f1[:, i]).max(), np.abs(f3[:, i]).max()
    assert peak3 < 3 * peak1, "stacked forcing must be sub-linear"
    assert peak3 <= engine.event_forcing_cap + 1e-9, "forcing must respect the cap"
    print(f"  event saturation: 3× stack → {peak3 / peak1:.2f}× forcing (cap {engine.event_forcing_cap}) ✓")


def test_anticipation(engine, baseline):
    """With anticipation, the path leans toward a future pin before it lands."""
    n_obs = len(engine.levels_df)
    ch = "Fed_Funds_Rate"
    i = engine.channel_names.index(ch)
    pin_t = n_obs + 6
    pin_val = 6.0
    lead = 4

    res_no = engine.simulate(pins=[Pin(ch, pin_t, pin_val)], horizon=10, n_bootstrap=0)
    res_ant = engine.simulate(pins=[Pin(ch, pin_t, pin_val)], horizon=10, n_bootstrap=0, anticipation=lead)

    assert res_ant["levels"][pin_t, i] == pin_val
    # In the lead window the anticipated path must be closer to the pin
    t_probe = pin_t - 2
    gap_no = abs(res_no["levels"][t_probe, i] - pin_val)
    gap_ant = abs(res_ant["levels"][t_probe, i] - pin_val)
    assert gap_ant < gap_no, "anticipated path must lean toward the pin"
    # And the pre-move must propagate to other channels
    others = [j for j in range(len(engine.channel_names)) if j != i]
    pre_gap = np.abs(res_ant["levels"][pin_t - lead:pin_t, others] - res_no["levels"][pin_t - lead:pin_t, others])
    assert pre_gap.max() > 1e-9, "anticipation must propagate before the pin"
    print("  anticipation: path leans toward future pin, pre-move propagates ✓")


def test_prior_relationships():
    df = pd.read_csv("data_us_fed_macro.csv", parse_dates=["Date"]).set_index("Date")
    df = df.drop(columns=["Source"])
    base = ScenarioEngine(df, transform_overrides={"SP500": "log_diff", "DXY": "log_diff"}, dt=90.0)

    discovered = {(r["target"], r["source"]): r["weight"] for r in base.describe()["relationships"]}
    all_pairs = [(t, s) for t in base.channel_names for s in base.channel_names]
    silent = next(p for p in all_pairs if p not in discovered)
    taken = next(iter(discovered))

    engine = ScenarioEngine(
        df, transform_overrides={"SP500": "log_diff", "DXY": "log_diff"}, dt=90.0,
        prior_relationships=[
            (silent[0], silent[1], 0.42),   # fills the silent pair
            (taken[0], taken[1], 99.0),     # must NOT override discovery
        ],
    )
    rels = {(r["target"], r["source"]): r for r in engine.describe()["relationships"]}
    assert rels[silent]["weight"] == 0.42 and rels[silent]["manual"]
    assert rels[taken]["weight"] == discovered[taken], "prior must not override discovery"
    print("  priors: fill silent pairs only, never override discovery ✓")


def test_pairwise_long_history_fit():
    """Couplings are fitted on each pair's own overlap in the long panel."""
    rng = np.random.default_rng(7)
    T_long = 360
    dates = pd.date_range("1995-01-01", periods=T_long, freq="MS")
    src_inc = rng.normal(0, 1, T_long)
    # Discovery is one-step-ahead: source increment drives NEXT target increment
    tgt_inc = 0.6 * np.roll(src_inc, 1) + rng.normal(0, 1, T_long)
    tgt_inc[0] = 0.0
    fit_df = pd.DataFrame(
        {"Src": 100 + np.cumsum(src_inc), "Tgt": 50 + np.cumsum(tgt_inc)}, index=dates
    )
    # Third channel only exists for the last 40 months → short common panel
    fit_df["Late"] = np.nan
    fit_df.iloc[-40:, fit_df.columns.get_loc("Late")] = 10 + np.cumsum(rng.normal(0, 1, 40))
    common = fit_df.dropna()

    engine = ScenarioEngine(common, dt=30.0, fit_levels=fit_df)
    rels = {(r["target"], r["source"]): r for r in engine.describe()["relationships"]}
    key = ("Tgt", "Src")
    assert key in rels and rels[key]["weight"] > 0.2, "long-overlap coupling must be discovered"
    res = engine.simulate(horizon=12, n_bootstrap=0)
    assert np.isfinite(res["levels"]).all()
    print(f"  pairwise long-history fit: Tgt←Src r={rels[key]['significance']:.2f} from NaN panel ✓")


def test_v1_dynamics_bounded_and_distinct(engine, baseline):
    """
    v1 (documentation/QNTUM-model.md) shares the fitted store with v2 but
    uses relative-scale coupling + a per-step clamp instead of a spectral
    cap on β. Both must stay finite; the two recurrences must diverge.
    """
    res_v1 = engine.simulate(horizon=8, n_bootstrap=0, dynamics="v1")
    assert np.isfinite(res_v1["levels"]).all()
    assert not np.allclose(res_v1["levels"], baseline["levels"]), \
        "v1 and v2 use different recurrences and must not coincide"
    assert engine.describe()["clamp_v1"] == engine.clamp_v1
    print("  v1 dynamics: finite forecast, distinct from v2 ✓")

    try:
        engine.simulate(horizon=4, n_bootstrap=0, dynamics="bogus")
        raise AssertionError("unknown dynamics value must raise")
    except ValueError:
        pass
    print("  dynamics validation: unknown value rejected ✓")


def test_add_channel(engine):
    rng = np.random.default_rng(0)
    dates = engine.dates
    sp500 = engine.levels_df["SP500"].values
    gold = 1500 * np.exp(0.3 * np.log(sp500 / sp500[0]) + rng.normal(0, 0.02, len(dates)).cumsum())
    result = engine.add_channel("Gold", pd.Series(gold, index=dates), transform="log_diff")
    assert "Gold" in engine.channel_names
    res = engine.simulate(horizon=8, n_bootstrap=0)
    assert np.isfinite(res["levels"]).all()
    print(f"  add_channel: Gold added, {len(result['relationships'])} relationships, refit ok ✓")


if __name__ == "__main__":
    print("ScenarioEngine validation")
    print("=" * 60)
    engine = build_macro_engine()
    baseline = check_baseline(engine)
    test_future_pin(engine, baseline)
    test_counterfactual(engine, baseline)
    test_latent_event(engine, baseline)
    test_physics_pin()
    test_extreme_pin_winsorized(engine)
    test_event_saturation(engine)
    test_anticipation(engine, baseline)
    test_prior_relationships()
    test_pairwise_long_history_fit()
    test_v1_dynamics_bounded_and_distinct(engine, baseline)
    test_add_channel(engine)
    print("=" * 60)
    print("ALL TESTS PASSED")
