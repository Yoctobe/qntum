"""
QNTUM Simulator API
═══════════════════════════════════════════════════════════════════════════════

Thin FastAPI wrapper around the ScenarioEngine.

    GET  /api/state      — channels, observed history, fitted relationships
    POST /api/simulate   — evaluate a scenario (pins + events + anticipation)
    GET  /api/library    — event templates
    POST /api/library    — add a template (new-event wizard, latent kind)
    POST /api/channels   — add an observable channel from uploaded history
    POST /api/matrix     — pin a coupling manually (editable matrix)
    DELETE /api/matrix   — drop a manual coupling (discovery takes over)
    GET  /api/scenarios  — saved scenarios
    POST /api/scenarios  — save a scenario
    DELETE /api/scenarios/{name}

Persistence (survives restarts): event templates (event_library.yaml),
manual couplings (coupling_overrides.yaml), uploaded channels
(user_channels/*.csv), saved scenarios (scenarios.json).

Four datasets, selectable per request via `dataset` — the model is
domain-agnostic; only the CSV and a couple of fit knobs change:
    "monthly"          — the live panel (us_macro_monthly_full.csv, 2006→
                          present). Fits couplings on the long panel (per-pair
                          overlaps back to 1971 where available), simulates
                          on the common panel. coupling_priors.yaml fills
                          pairs where discovery is silent. α is deliberately
                          low (0.30) so persistence isn't double-counted
                          against the fitted self-relationships — see
                          ScenarioEngine's docstring. Well-conditioned: the
                          v2 spectral cap never needs to shrink β here.
    "quarterly_stress"  — an exact reproduction of QUNTUM_draft.md §4.2's
                          honest-failure case (16 quarterly US macro
                          observations, α=0.85, β=0.50, min_corr=0.50 — the
                          paper's own published parameters, not tuned for
                          this comparison). The fitted structure genuinely
                          exceeds the spectral cap here (ρ≈1.3-1.4 pre-cap),
                          so v1 (per-step clamp) and v2 (one-time β shrink)
                          diverge for a real reason, not a cosmetic one.
    "medical"           — synthetic glucose/insulin panel (daily-timescale
                          analogue of the Bergman minimal model: glucose G,
                          plasma insulin I, insulin action X). Auto-discovery
                          alone recovers the textbook physiology: insulin
                          lowers glucose, glucose drives secretion, insulin
                          drives its own delayed action.
    "ecosystem"         — synthetic predator/prey panel (Lotka–Volterra,
                          monthly, RK4-integrated). Recovers the classic
                          asymmetric coupling: predators suppress prey growth
                          more visibly than prey population feeds predator
                          growth, at the model's fitted lag.

Run: uvicorn app:app --reload --port 8000
"""

import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Model"))

from quantum_model.simulator import ScenarioEngine, Pin  # noqa: E402
from quantum_model.event_library import EventLibrary, EventTemplate  # noqa: E402

DATA_DIR = Path(__file__).parent / "data"
MACRO_CSV = DATA_DIR / "us_macro_monthly.csv"
MACRO_FULL_CSV = DATA_DIR / "us_macro_monthly_full.csv"
STRESS_CSV = DATA_DIR / "us_macro_quarterly_stress.csv"
MEDICAL_CSV = DATA_DIR / "medical_glucose_insulin.csv"
ECOSYSTEM_CSV = DATA_DIR / "ecosystem_predator_prey.csv"
LIBRARY_YAML = DATA_DIR / "event_library.yaml"
PRIORS_YAML = DATA_DIR / "coupling_priors.yaml"
OVERRIDES_YAML = DATA_DIR / "coupling_overrides.yaml"
SCENARIOS_JSON = DATA_DIR / "scenarios.json"
USER_CHANNELS_DIR = DATA_DIR / "user_channels"

TRANSFORM_OVERRIDES = {
    "Industrial_Production": "log_diff",
    "Housing": "log_diff",
    "Oil_WTI": "log_diff",
    "Gold": "log_diff",
    "Dollar_Index": "log_diff",
    "Nasdaq": "log_diff",
}


# ──────────────────────────────────────────────────────────────────────────────
# PERSISTENCE HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def load_relationship_yaml(path: Path) -> list[tuple]:
    if not path.exists():
        return []
    entries = yaml.safe_load(path.read_text()) or []
    return [
        (e["target"], e["source"], float(e["weight"]), float(e.get("lag_days", 0.0)))
        for e in entries
    ]


def save_overrides(relationships: list[tuple]):
    entries = [
        {"target": t, "source": s, "weight": w, "lag_days": lag}
        for t, s, w, lag in relationships
    ]
    OVERRIDES_YAML.write_text(yaml.safe_dump(entries, sort_keys=False))


def load_scenarios() -> list[dict]:
    if not SCENARIOS_JSON.exists():
        return []
    return json.loads(SCENARIOS_JSON.read_text())


def save_scenarios(scenarios: list[dict]):
    SCENARIOS_JSON.write_text(json.dumps(scenarios, indent=2))


def build_monthly_engine() -> ScenarioEngine:
    df = pd.read_csv(MACRO_CSV, parse_dates=["Date"]).set_index("Date")
    fit_levels = None
    if MACRO_FULL_CSV.exists():
        fit_levels = pd.read_csv(MACRO_FULL_CSV, parse_dates=["Date"]).set_index("Date")

    engine = ScenarioEngine(
        df,
        transform_overrides=dict(TRANSFORM_OVERRIDES),
        dt=30.0,
        fit_levels=fit_levels,
        manual_relationships=load_relationship_yaml(OVERRIDES_YAML),
        prior_relationships=load_relationship_yaml(PRIORS_YAML),
    )

    # Re-attach channels the user uploaded in earlier sessions
    if USER_CHANNELS_DIR.exists():
        for csv in sorted(USER_CHANNELS_DIR.glob("*.csv")):
            try:
                s = pd.read_csv(csv, parse_dates=["date"]).set_index("date")["value"]
                transform = csv.with_suffix(".transform").read_text().strip() \
                    if csv.with_suffix(".transform").exists() else "diff"
                engine.add_channel(csv.stem, s, transform=transform)
            except (ValueError, KeyError) as exc:
                print(f"  ⚠ could not restore channel {csv.stem}: {exc}")
    return engine


def build_stress_engine() -> Optional[ScenarioEngine]:
    """
    Reproduces QUNTUM_draft.md §4.2 exactly: 16 quarterly US macro
    observations, α=0.85, β=0.50, min_corr=0.50 — the paper's own published
    parameters. The fitted structure genuinely exceeds the spectral cap
    (ρ≈1.3-1.4 before shrinkage), so v1 and v2 diverge here for a real
    reason rather than a cosmetic parameter tweak.
    """
    if not STRESS_CSV.exists():
        return None
    df = pd.read_csv(STRESS_CSV, parse_dates=["Date"]).set_index("Date")
    df = df.drop(columns=[c for c in ("Source",) if c in df.columns])
    train = df.iloc[:16]
    return ScenarioEngine(
        train,
        transform_overrides={"SP500": "log_diff", "DXY": "log_diff"},
        dt=90.0,
        alpha=0.85,
        beta=0.50,
        min_corr=0.50,
        max_spectral_radius=0.98,
    )


def build_medical_engine() -> Optional[ScenarioEngine]:
    """Synthetic glucose/insulin panel — see generate_example_domains.py."""
    if not MEDICAL_CSV.exists():
        return None
    df = pd.read_csv(MEDICAL_CSV, parse_dates=["Date"]).set_index("Date")
    return ScenarioEngine(df, dt=1.0)


def build_ecosystem_engine() -> Optional[ScenarioEngine]:
    """Synthetic predator/prey panel — see generate_example_domains.py."""
    if not ECOSYSTEM_CSV.exists():
        return None
    df = pd.read_csv(ECOSYSTEM_CSV, parse_dates=["Date"]).set_index("Date")
    return ScenarioEngine(df, dt=30.0)


ENGINES: dict[str, ScenarioEngine] = {"monthly": build_monthly_engine()}
for _key, _builder in (
    ("quarterly_stress", build_stress_engine),
    ("medical", build_medical_engine),
    ("ecosystem", build_ecosystem_engine),
):
    _eng = _builder()
    if _eng is not None:
        ENGINES[_key] = _eng
DATASET_CHOICES = tuple(ENGINES.keys())
engine = ENGINES["monthly"]  # default, used by legacy call sites below
library = EventLibrary(LIBRARY_YAML)


def get_engine(dataset: str) -> ScenarioEngine:
    if dataset not in ENGINES:
        raise HTTPException(400, f"Unknown dataset {dataset!r}, choices: {DATASET_CHOICES}")
    return ENGINES[dataset]

app = FastAPI(title="QNTUM Simulator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class PinModel(BaseModel):
    channel: str
    date: str  # ISO, must match a timeline date
    value: float


class EventModel(BaseModel):
    template: str
    date: str
    name: Optional[str] = None
    intensity: float = 1.0
    formation: Optional[int] = None
    tau: Optional[int] = None
    first_hop: Optional[dict[str, float]] = None


class SimRequest(BaseModel):
    pins: list[PinModel] = Field(default_factory=list)
    events: list[EventModel] = Field(default_factory=list)
    horizon: int = 24
    n_bootstrap: int = 80
    anticipation: int = 0
    replay_from: Optional[str] = None  # date; re-simulate from here to check vs actual
    dynamics: str = "v2"  # "v1" (documentation/QNTUM-model.md) or "v2" (spectral cap)
    dataset: str = "monthly"  # "monthly" | "quarterly_stress" | "medical" | "ecosystem"


class TemplateModel(BaseModel):
    name: str
    description: str = ""
    formation: int = 1
    tau: int = 4
    first_hop: dict[str, float]
    ranges: dict[str, list[float]] = Field(default_factory=dict)
    analogues: list[str] = Field(default_factory=list)


class ChannelUpload(BaseModel):
    name: str
    transform: str = "diff"
    data: list[dict]  # [{date, value}]


class CouplingModel(BaseModel):
    target: str
    source: str
    weight: float
    lag_days: float = 0.0


class ScenarioModel(BaseModel):
    name: str
    pins: list[PinModel] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    horizon: int = 24
    anticipation: int = 0


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def timeline_dates(eng: ScenarioEngine, horizon: int) -> pd.DatetimeIndex:
    return eng.dates.append(eng.future_dates(horizon))


def date_to_idx(eng: ScenarioEngine, date: str, horizon: int) -> int:
    ts = pd.Timestamp(date)
    dates = timeline_dates(eng, horizon)
    idx = int(dates.get_indexer([ts], method="nearest")[0])
    if idx < 0:
        raise HTTPException(400, f"Date {date} outside timeline")
    return idx


def library_json() -> list[dict]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "formation": t.formation,
            "tau": t.tau,
            "first_hop": t.first_hop,
            "ranges": t.ranges,
            "analogues": t.analogues,
        }
        for t in library.templates.values()
    ]


def state_json(eng: ScenarioEngine) -> dict:
    desc = eng.describe()
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in eng.dates],
        "observed": {
            name: eng.levels_df[name].round(4).tolist()
            for name in eng.channel_names
        },
        **desc,
    }


def run_simulation(req: SimRequest) -> dict:
    eng = get_engine(req.dataset)
    pins = [
        Pin(p.channel, date_to_idx(eng, p.date, req.horizon), p.value)
        for p in req.pins
    ]
    events = [
        library.get(e.template).instantiate(
            t0_idx=date_to_idx(eng, e.date, req.horizon),
            intensity=e.intensity,
            name=e.name,
            formation=e.formation,
            tau=e.tau,
            first_hop_overrides=e.first_hop,
        )
        for e in req.events
    ]
    replay_idx = date_to_idx(eng, req.replay_from, req.horizon) if req.replay_from else None
    result = eng.simulate(
        pins=pins,
        events=events,
        horizon=req.horizon,
        n_bootstrap=min(req.n_bootstrap, 200),
        anticipation=max(0, min(req.anticipation, 12)),
        replay_from_idx=replay_idx,
        dynamics=req.dynamics,
    )

    channels = []
    for i, name in enumerate(eng.channel_names):
        entry = {
            "name": name,
            "levels": [round(v, 6) for v in result["levels"][:, i]],
            "status": result["status"][:, i].tolist(),
        }
        if result["lower"] is not None:
            entry["lower"] = [round(v, 6) for v in result["lower"][:, i]]
            entry["upper"] = [round(v, 6) for v in result["upper"][:, i]]
        channels.append(entry)

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in result["dates"]],
        "sim_start": result["sim_start"],
        "channels": channels,
        "events": result["events"],
    }


# ──────────────────────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/datasets")
def get_datasets():
    return {
        "choices": list(DATASET_CHOICES),
        "descriptions": {
            "monthly": "Live US macro panel (monthly, 2006-present) — well-conditioned; v2's spectral cap stays idle.",
            "quarterly_stress": "QUNTUM_draft.md §4.2 reproduction (16 quarters, α=0.85, β=0.50) — genuinely unstable fit; v1 and v2 diverge for real.",
            "medical": "Synthetic glucose/insulin regulation (daily, Bergman-style constants) — the model recovers real physiology from data alone.",
            "ecosystem": "Synthetic predator/prey population (monthly, Lotka–Volterra) — same engine, an entirely different domain.",
        },
    }


@app.get("/api/state")
def get_state(dataset: str = "monthly"):
    return state_json(get_engine(dataset))


@app.get("/api/library")
def get_library():
    return library_json()


@app.post("/api/library")
def add_template(t: TemplateModel):
    unknown = [c for c in t.first_hop if c not in engine.channel_names]
    if unknown:
        raise HTTPException(400, f"Unknown channels in first_hop: {unknown}")
    library.add(EventTemplate(**t.model_dump()))
    return library_json()


@app.post("/api/simulate")
def simulate(req: SimRequest):
    try:
        return run_simulation(req)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/channels")
def add_channel(upload: ChannelUpload):
    try:
        df = pd.DataFrame(upload.data)
        series = pd.Series(
            df["value"].astype(float).values,
            index=pd.to_datetime(df["date"]),
        ).sort_index()
        # Align to month starts to match the master timeline
        series.index = series.index.to_period("M").to_timestamp()
        series = series[~series.index.duplicated(keep="last")]
        result = engine.add_channel(upload.name, series, transform=upload.transform)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc))

    USER_CHANNELS_DIR.mkdir(exist_ok=True)
    series.rename("value").rename_axis("date").to_csv(USER_CHANNELS_DIR / f"{upload.name}.csv")
    (USER_CHANNELS_DIR / f"{upload.name}.transform").write_text(upload.transform)
    return {"fit": result, "state": state_json(engine)}


@app.post("/api/matrix")
def set_coupling(c: CouplingModel):
    try:
        engine.set_coupling(c.target, c.source, c.weight, c.lag_days)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    save_overrides(engine.manual_relationships)
    return state_json(engine)


@app.delete("/api/matrix")
def remove_coupling(target: str, source: str):
    engine.remove_coupling(target, source)
    save_overrides(engine.manual_relationships)
    return state_json(engine)


@app.get("/api/scenarios")
def get_scenarios():
    return load_scenarios()


@app.post("/api/scenarios")
def save_scenario(s: ScenarioModel):
    scenarios = [x for x in load_scenarios() if x["name"] != s.name]
    scenarios.append(s.model_dump())
    save_scenarios(scenarios)
    return scenarios


@app.delete("/api/scenarios/{name}")
def delete_scenario(name: str):
    scenarios = [x for x in load_scenarios() if x["name"] != name]
    save_scenarios(scenarios)
    return scenarios
