"""
GLOBAL MACRO CYCLE CLOCK
========================
Tracks where major economies are in the rate cycle
and predicts capital flows, FX direction, and bond attractiveness.

Usage:
    python macro_cycle.py

You can edit the COUNTRIES data at the bottom to update with latest figures.
"""

# ── dependencies ────────────────────────────────────────────────────────────
import math

# ── CYCLE DEFINITIONS ───────────────────────────────────────────────────────
# The 4 phases of the macro cycle:
#
#  PHASE 1 — EXPANSION (low rates, rising growth)
#  PHASE 2 — OVERHEATING (rates rising, inflation high)
#  PHASE 3 — TIGHTENING PEAK (rates peak, growth slowing)
#  PHASE 4 — CONTRACTION (rates falling, recession risk)
#
# The CLOCK: 1 → 2 → 3 → 4 → 1 → ...

PHASES = {
    1: {
        "name": "EXPANSION",
        "desc": "Low rates. Growth accelerating. Inflation building.",
        "rate_direction": "HOLD / SLIGHT RISE",
        "currency": "WEAKENING",
        "bonds": "UNATTRACTIVE (yields low)",
        "exports": "COMPETITIVE (weak FX)",
        "risk": "OVERHEATING ahead",
        "color": "GREEN",
    },
    2: {
        "name": "OVERHEATING",
        "desc": "Rates rising fast. Inflation high. Growth still OK.",
        "rate_direction": "HIKING",
        "currency": "STRENGTHENING",
        "bonds": "IMPROVING (yields rising)",
        "exports": "SLOWING (strong FX)",
        "risk": "SLOWDOWN ahead",
        "color": "AMBER",
    },
    3: {
        "name": "TIGHTENING PEAK",
        "desc": "Rates at peak. Inflation cooling. Growth slowing.",
        "rate_direction": "HOLD / ABOUT TO CUT",
        "currency": "STRONG BUT PEAKING",
        "bonds": "ATTRACTIVE (high yields, about to rally)",
        "exports": "WEAK",
        "risk": "RECESSION ahead",
        "color": "RED",
    },
    4: {
        "name": "CONTRACTION",
        "desc": "Rates falling. Recession or near-recession. Inflation low.",
        "rate_direction": "CUTTING",
        "currency": "WEAKENING",
        "bonds": "RALLYING (yields falling, bond prices rising)",
        "exports": "RECOVERING (weak FX)",
        "risk": "RECOVERY ahead → back to Phase 1",
        "color": "BLUE",
    },
}

# ── SCORING ENGINE ───────────────────────────────────────────────────────────
def score_phase(cpi, rate, unemployment, gdp, rate_trend, cpi_trend):
    """
    Given current macro data, return a phase score 1-4 and confidence.

    Parameters
    ----------
    cpi          : float  — current CPI %
    rate         : float  — current central bank rate %
    unemployment : float  — unemployment %
    gdp          : float  — GDP growth %
    rate_trend   : str    — 'rising', 'holding', 'falling'
    cpi_trend    : str    — 'rising', 'holding', 'falling'

    Returns phase (1-4), position (0.0-1.0 within phase), signals list
    """
    signals = []
    scores = {1: 0, 2: 0, 3: 0, 4: 0}

    # CPI signals
    if cpi > 5:
        scores[2] += 3; scores[3] += 2
        signals.append(f"  ⚠  CPI {cpi}% — above target → Phase 2/3 territory")
    elif cpi > 3:
        scores[2] += 2; scores[1] += 1
        signals.append(f"  ↑  CPI {cpi}% — elevated → Phase 1→2 transition")
    elif cpi < 1.5:
        scores[4] += 3; scores[1] += 1
        signals.append(f"  ↓  CPI {cpi}% — below target → Phase 4/1 territory")
    else:
        scores[1] += 2; scores[4] += 1
        signals.append(f"  ✓  CPI {cpi}% — near target → stable")

    # Rate level signals
    if rate > 5:
        scores[3] += 3; scores[2] += 1
        signals.append(f"  ⚠  Rate {rate}% — restrictive territory → Phase 3")
    elif rate > 3:
        scores[2] += 2; scores[3] += 1
        signals.append(f"  ↑  Rate {rate}% — tightening → Phase 2/3")
    elif rate < 1:
        scores[1] += 3; scores[4] += 2
        signals.append(f"  ↓  Rate {rate}% — stimulative → Phase 1/4")
    else:
        scores[1] += 2; scores[4] += 1
        signals.append(f"  ◆  Rate {rate}% — neutral range")

    # Rate trend signals
    if rate_trend == 'rising':
        scores[2] += 3
        signals.append(f"  ↑  Rate RISING → clearly Phase 2 (hiking cycle)")
    elif rate_trend == 'falling':
        scores[4] += 3
        signals.append(f"  ↓  Rate FALLING → clearly Phase 4 (cutting cycle)")
    elif rate_trend == 'holding':
        scores[3] += 2; scores[1] += 1
        signals.append(f"  ■  Rate HOLDING → Phase 1 (low hold) or Phase 3 (peak hold)")

    # CPI trend signals
    if cpi_trend == 'rising':
        scores[2] += 2; scores[1] += 1
        signals.append(f"  ↑  CPI RISING → inflationary pressure building")
    elif cpi_trend == 'falling':
        scores[3] += 2; scores[4] += 1
        signals.append(f"  ↓  CPI FALLING → disinflation in progress")

    # GDP signals
    if gdp < 0:
        scores[4] += 3
        signals.append(f"  ⚠  GDP {gdp}% — contraction → Phase 4 confirmed")
    elif gdp < 1:
        scores[3] += 2; scores[4] += 2
        signals.append(f"  ↓  GDP {gdp}% — stalling → Phase 3/4")
    elif gdp > 3:
        scores[1] += 2; scores[2] += 1
        signals.append(f"  ↑  GDP {gdp}% — strong growth → Phase 1/2")
    else:
        scores[1] += 1; scores[3] += 1
        signals.append(f"  ◆  GDP {gdp}% — moderate")

    # Unemployment signals
    if unemployment > 7:
        scores[4] += 2
        signals.append(f"  ↑  Unemployment {unemployment}% — high → Phase 4")
    elif unemployment < 4:
        scores[2] += 2; scores[1] += 1
        signals.append(f"  ↓  Unemployment {unemployment}% — tight labor → Phase 1/2")

    # Determine phase
    phase = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = round((scores[phase] / total) * 100) if total > 0 else 50

    # Position within phase (0.0 = just entered, 1.0 = about to leave)
    # Simple heuristic based on contradicting signals
    next_phase = (phase % 4) + 1
    position = min(0.95, scores[next_phase] / max(scores[phase], 1) * 1.2)

    return phase, round(position, 2), confidence, signals, scores


# ── PREDICTIONS ENGINE ───────────────────────────────────────────────────────
def predict_next_quarter(country_name, phase, position, data):
    """Generate actionable predictions for next quarter."""
    predictions = []
    next_phase = (phase % 4) + 1
    transitioning = position > 0.6

    if phase == 1:
        predictions.append("RATES: Expect first hike if CPI keeps rising")
        predictions.append("FX: Currency still weak — exporters benefiting")
        predictions.append("BONDS: Avoid locking in long duration (yields will rise)")
        predictions.append("EQUITIES: Still supportive but late-cycle caution")
        if transitioning:
            predictions.append("⚡ TRANSITION SIGNAL: Moving toward Phase 2 — watch CPI closely")

    elif phase == 2:
        predictions.append("RATES: More hikes coming — borrow now before it gets worse")
        predictions.append("FX: Currency strengthening — import costs falling")
        predictions.append("BONDS: Short-term bonds attractive, avoid long duration")
        predictions.append("EQUITIES: Pressure on valuations as rates rise")
        if transitioning:
            predictions.append("⚡ TRANSITION SIGNAL: Approaching Phase 3 — hike cycle nearing peak")

    elif phase == 3:
        predictions.append("RATES: Hiking done or nearly done — next move is a cut")
        predictions.append("FX: Currency at peak — start positioning for weakening")
        predictions.append("BONDS: ★ BUY LONG BONDS NOW — yields peak here, prices will rally when cuts come")
        predictions.append("EQUITIES: Risk of correction — defensive positioning")
        if transitioning:
            predictions.append("⚡ TRANSITION SIGNAL: Rate cut imminent — Phase 4 incoming")

    elif phase == 4:
        predictions.append("RATES: Cutting cycle underway — cheap money returning")
        predictions.append("FX: Currency weakening — domestic exporters benefit next quarter")
        predictions.append("BONDS: Still rallying — hold long bonds")
        predictions.append("EQUITIES: Recovery play — growth stocks begin to recover")
        if transitioning:
            predictions.append("⚡ TRANSITION SIGNAL: Recovery ahead — Phase 1 rotation beginning")

    return predictions


# ── CAPITAL FLOW ANALYSIS ────────────────────────────────────────────────────
def analyze_capital_flows(countries):
    """
    Compare all countries and identify where capital will flow.
    Capital moves toward: highest real yield + most stable currency outlook
    """
    flows = []

    for c in countries:
        phase = c['phase']
        rate = c['data']['rate']
        cpi = c['data']['cpi']
        real_yield = rate - cpi  # real interest rate

        attractiveness = 0

        # Phase 3 = most attractive for capital (high rates, about to stabilize)
        if phase == 3:
            attractiveness += 40
        elif phase == 2:
            attractiveness += 25
        elif phase == 1:
            attractiveness += 10
        elif phase == 4:
            attractiveness += 5

        # Real yield bonus
        if real_yield > 1:
            attractiveness += 20
        elif real_yield > 0:
            attractiveness += 10
        elif real_yield < -1:
            attractiveness -= 15

        # High nominal rate = bond buyers attracted
        if rate > 4:
            attractiveness += 15
        elif rate > 2:
            attractiveness += 8

        flows.append({
            "country": c['name'],
            "phase": phase,
            "rate": rate,
            "cpi": cpi,
            "real_yield": round(real_yield, 2),
            "attractiveness": attractiveness
        })

    flows.sort(key=lambda x: x['attractiveness'], reverse=True)
    return flows


# ── DISPLAY HELPERS ──────────────────────────────────────────────────────────
COLORS = {
    "GREEN": "\033[92m",
    "AMBER": "\033[93m",
    "RED":   "\033[91m",
    "BLUE":  "\033[94m",
    "RESET": "\033[0m",
    "BOLD":  "\033[1m",
    "DIM":   "\033[2m",
    "CYAN":  "\033[96m",
}

def c(text, color):
    return f"{COLORS.get(color,'')}{text}{COLORS['RESET']}"

def bar(value, max_val=100, width=20, color="GREEN"):
    filled = int((value / max_val) * width)
    bar_str = "█" * filled + "░" * (width - filled)
    return c(bar_str, color)

def phase_clock_ascii(countries):
    """Draw a simple ASCII cycle clock showing all countries."""
    print()
    print(c("  ┌─────────────────────────────────────────────────────┐", "DIM"))
    print(c("  │", "DIM") + c("              THE MACRO CYCLE CLOCK                 ", "BOLD") + c("│", "DIM"))
    print(c("  └─────────────────────────────────────────────────────┘", "DIM"))
    print()

    clock = """
                    PHASE 1
                  EXPANSION
                 [LOW RATES]
                      ▲
                      │
    {p4}          │          {p2}
    PHASE 4 ◄──────────────────► PHASE 2
    CONTRACTION      │          OVERHEATING
    [CUTTING]        │          [HIKING]
                      │
                      ▼
                  PHASE 3
               TIGHTENING PEAK
                [RATES PEAK]
    """

    # Place countries
    phase_groups = {1: [], 2: [], 3: [], 4: []}
    for country in countries:
        phase_groups[country['phase']].append(country['name'])

    p1 = " ".join(phase_groups[1]) if phase_groups[1] else "—"
    p2 = " ".join(phase_groups[2]) if phase_groups[2] else "—"
    p3 = " ".join(phase_groups[3]) if phase_groups[3] else "—"
    p4 = " ".join(phase_groups[4]) if phase_groups[4] else "—"

    phase_colors = {1: "GREEN", 2: "AMBER", 3: "RED", 4: "BLUE"}

    print(f"                    {c('PHASE 1 — EXPANSION', 'GREEN')}")
    print(f"                    {c(p1, 'GREEN')}")
    print()
    print(f"  {c('PHASE 4', 'BLUE')}                              {c('PHASE 2', 'AMBER')}")
    print(f"  {c('CONTRACTION', 'BLUE')}  ◄────────────────────► {c('OVERHEATING', 'AMBER')}")
    print(f"  {c(p4, 'BLUE')}                              {c(p2, 'AMBER')}")
    print()
    print(f"                    {c('PHASE 3 — TIGHTENING PEAK', 'RED')}")
    print(f"                    {c(p3, 'RED')}")
    print()


def print_country_report(country):
    name = country['name']
    phase = country['phase']
    position = country['position']
    confidence = country['confidence']
    signals = country['signals']
    scores = country['scores']
    data = country['data']
    predictions = country['predictions']
    phase_info = PHASES[phase]
    phase_color = phase_info['color']

    width = 60
    print()
    print(c("─" * width, "DIM"))
    phase_label = f"[ PHASE {phase} — {phase_info['name']} ]"
    print(c(f"  {name}", "BOLD") + f"  {c(phase_label, phase_color)}")
    print(c("─" * width, "DIM"))

    # Key data
    cpi_col  = 'RED' if data['cpi']>4 else ('AMBER' if data['cpi']>2.5 else 'GREEN')
    rate_col = 'RED' if data['rate']>5 else ('AMBER' if data['rate']>2 else 'GREEN')
    ue_col   = 'RED' if data['unemployment']>7 else ('AMBER' if data['unemployment']>5 else 'GREEN')
    gdp_col  = 'GREEN' if data['gdp']>2 else ('AMBER' if data['gdp']>0 else 'RED')
    tb_col   = 'GREEN' if data['trade_balance']>0 else 'RED'
    print(f"\n  {'CPI':15} {c(str(data['cpi'])+'%', cpi_col)}")
    print(f"  {'RATE':15} {c(str(data['rate'])+'%', rate_col)}")
    print(f"  {'UNEMPLOYMENT':15} {c(str(data['unemployment'])+'%', ue_col)}")
    print(f"  {'GDP GROWTH':15} {c(str(data['gdp'])+'%', gdp_col)}")
    print(f"  {'10Y YIELD':15} {c(str(data['yield_10y'])+'%', 'AMBER')}")
    print(f"  {'TRADE BAL':15} {c(str(data['trade_balance'])+'B USD', tb_col)}")

    # Cycle position
    print(f"\n  CYCLE POSITION:")
    pos_pct = int(position * 100)
    bar_color = "GREEN" if pos_pct < 40 else "AMBER" if pos_pct < 70 else "RED"
    print(f"  {bar(pos_pct, 100, 30, bar_color)} {pos_pct}% through Phase {phase}")
    print(f"  {c('Confidence:', 'DIM')} {confidence}%")

    next_phase = (phase % 4) + 1
    if pos_pct > 60:
        next_name = PHASES[next_phase]['name']
        print(f"  {c('⚡ Approaching Phase ' + str(next_phase) + ' — ' + next_name, 'AMBER')}")

    # Phase description
    print(f"\n  {c('CURRENT DYNAMICS:', 'BOLD')}")
    print(f"  {phase_info['desc']}")
    print(f"  Rate direction : {c(phase_info['rate_direction'], phase_color)}")
    print(f"  Currency       : {c(phase_info['currency'], phase_color)}")
    print(f"  Bonds          : {c(phase_info['bonds'], phase_color)}")
    print(f"  Exports        : {phase_info['exports']}")
    print(f"  Risk ahead     : {c(phase_info['risk'], 'RED')}")

    # Signals
    print(f"\n  {c('SIGNALS DETECTED:', 'BOLD')}")
    for s in signals:
        print(f"  {s}")

    # Predictions
    print(f"\n  {c('NEXT QUARTER OUTLOOK:', 'BOLD')}")
    for p in predictions:
        print(f"  → {p}")


def print_capital_flows(flows):
    print()
    print(c("═" * 60, "DIM"))
    print(c("  CAPITAL FLOW ANALYSIS — WHERE MONEY MOVES NEXT QUARTER", "BOLD"))
    print(c("═" * 60, "DIM"))
    print()
    print(f"  {'RANK':<6} {'COUNTRY':<12} {'PHASE':<10} {'RATE':<8} {'CPI':<8} {'REAL YIELD':<12} {'SCORE'}")
    print(c("  " + "─"*56, "DIM"))

    for i, f in enumerate(flows):
        rank = f"#{i+1}"
        phase_color = {1:"GREEN",2:"AMBER",3:"RED",4:"BLUE"}[f['phase']]
        ry_color = "GREEN" if f['real_yield'] > 0 else "RED"
        score_bar = "█" * min(int(f['attractiveness']/5), 12)
        phase_str = c("P" + str(f['phase']), phase_color)
        ry_str = c(str(f['real_yield']) + "%", ry_color)
        print(
            f"  {c(rank,'BOLD'):<6} "
            f"{f['country']:<12} "
            f"{phase_str:<10} "
            f"{f['rate']:<8} "
            f"{f['cpi']:<8} "
            f"{ry_str:<12} "
            f"{c(score_bar,'CYAN')}"
        )

    print()
    top = flows[0]
    bottom = flows[-1]
    print(f"  {c('▶ CAPITAL FLOWS INTO:', 'GREEN')}  {top['country']} "
          f"(Phase {top['phase']}, Real Yield {top['real_yield']}%)")
    print(f"  {c('▶ CAPITAL FLEES FROM:', 'RED')} {bottom['country']} "
          f"(Phase {bottom['phase']}, Real Yield {bottom['real_yield']}%)")
    print()

    # FX prediction
    print(c("  FX IMPLICATIONS:", "BOLD"))
    for f in flows[:2]:
        print(f"  → {f['country']} currency {c('STRENGTHENS', 'GREEN')} "
              f"(capital inflows, high yield)")
    for f in flows[-2:]:
        print(f"  → {f['country']} currency {c('WEAKENS', 'RED')} "
              f"(capital outflows, unattractive yield)")


def print_cross_country_opportunity(countries):
    """Identify the best cross-country macro trade."""
    print()
    print(c("═" * 60, "DIM"))
    print(c("  MACRO TRADE OPPORTUNITIES", "BOLD"))
    print(c("═" * 60, "DIM"))
    print()

    phase3 = [c for c in countries if c['phase'] == 3]
    phase4 = [c for c in countries if c['phase'] == 4]
    phase1 = [c for c in countries if c['phase'] == 1]

    if phase3:
        names = ", ".join(c['name'] for c in phase3)
        print(f"  {c('★ BUY BONDS:', 'GREEN')} {names}")
        print(f"    Phase 3 = rates at peak → bonds about to rally when cuts come")
        print()

    if phase4:
        names = ", ".join(c['name'] for c in phase4)
        print(f"  {c('★ BUY EQUITIES:', 'GREEN')} {names}")
        print(f"    Phase 4 = cutting cycle = cheap money = equity recovery")
        print()

    if phase1:
        names = ", ".join(c['name'] for c in phase1)
        print(f"  {c('★ EXPORT PLAY:', 'GREEN')} {names}")
        print(f"    Phase 1 = weak currency = competitive exports = trade surplus building")
        print()

    # Rate divergence trade
    rates_sorted = sorted(countries, key=lambda x: x['data']['rate'], reverse=True)
    if len(rates_sorted) >= 2:
        high = rates_sorted[0]
        low = rates_sorted[-1]
        spread = round(high['data']['rate'] - low['data']['rate'], 2)
        print(f"  {c('★ CARRY TRADE:', 'CYAN')} Borrow in {low['name']} ({low['data']['rate']}%), "
              f"invest in {high['name']} ({high['data']['rate']}%)")
        print(f"    Spread: {c(str(spread)+'%', 'GREEN')} — but watch FX risk")


# ── MAIN ─────────────────────────────────────────────────────────────────────
def run():
    print()
    print(c("╔══════════════════════════════════════════════════════════╗", "CYAN"))
    print(c("║         GLOBAL MACRO CYCLE CLOCK  v1.0                  ║", "CYAN"))
    print(c("║         Where is each economy in the cycle?             ║", "CYAN"))
    print(c("╚══════════════════════════════════════════════════════════╝", "CYAN"))
    print(c("  Data as of Q1 2026 — edit COUNTRIES dict to update", "DIM"))

    # ── COUNTRY DATA ─────────────────────────────────────────────────────────
    # Update these numbers each quarter with real data
    # Sources: Fed, ECB, BOE, BOJ, RBA official releases + Tradingeconomics
    COUNTRIES_DATA = [
        {
            "name": "USA",
            "data": {
                "cpi": 2.9,
                "rate": 4.25,
                "unemployment": 4.1,
                "gdp": 2.3,
                "yield_10y": 4.6,
                "trade_balance": -100,
            },
            "rate_trend": "falling",    # 'rising' | 'holding' | 'falling'
            "cpi_trend":  "holding",    # 'rising' | 'holding' | 'falling'
        },
        {
            "name": "EUROZONE",
            "data": {
                "cpi": 2.3,
                "rate": 2.65,
                "unemployment": 6.3,
                "gdp": 0.9,
                "yield_10y": 2.8,
                "trade_balance": 20,
            },
            "rate_trend": "falling",
            "cpi_trend":  "falling",
        },
        {
            "name": "UK",
            "data": {
                "cpi": 2.5,
                "rate": 4.5,
                "unemployment": 4.4,
                "gdp": 0.9,
                "yield_10y": 4.7,
                "trade_balance": -30,
            },
            "rate_trend": "falling",
            "cpi_trend":  "holding",
        },
        {
            "name": "JAPAN",
            "data": {
                "cpi": 3.6,
                "rate": 0.5,
                "unemployment": 2.4,
                "gdp": 1.2,
                "yield_10y": 1.5,
                "trade_balance": -10,
            },
            "rate_trend": "rising",
            "cpi_trend":  "rising",
        },
        {
            "name": "AUSTRALIA",
            "data": {
                "cpi": 2.4,
                "rate": 4.1,
                "unemployment": 4.0,
                "gdp": 1.5,
                "yield_10y": 4.5,
                "trade_balance": 5,
            },
            "rate_trend": "falling",
            "cpi_trend":  "falling",
        },
        {
            "name": "CANADA",
            "data": {
                "cpi": 1.9,
                "rate": 3.0,
                "unemployment": 6.7,
                "gdp": 1.3,
                "yield_10y": 3.3,
                "trade_balance": -5,
            },
            "rate_trend": "falling",
            "cpi_trend":  "falling",
        },
    ]

    # ── PROCESS EACH COUNTRY ─────────────────────────────────────────────────
    processed = []
    for cd in COUNTRIES_DATA:
        phase, position, confidence, signals, scores = score_phase(
            cpi          = cd['data']['cpi'],
            rate         = cd['data']['rate'],
            unemployment = cd['data']['unemployment'],
            gdp          = cd['data']['gdp'],
            rate_trend   = cd['rate_trend'],
            cpi_trend    = cd['cpi_trend'],
        )
        predictions = predict_next_quarter(cd['name'], phase, position, cd['data'])
        processed.append({
            **cd,
            "phase":       phase,
            "position":    position,
            "confidence":  confidence,
            "signals":     signals,
            "scores":      scores,
            "predictions": predictions,
        })

    # ── CYCLE CLOCK ──────────────────────────────────────────────────────────
    phase_clock_ascii(processed)

    # ── INDIVIDUAL REPORTS ───────────────────────────────────────────────────
    print(c("\n  INDIVIDUAL COUNTRY REPORTS", "BOLD"))
    for country in processed:
        print_country_report(country)

    # ── CAPITAL FLOWS ────────────────────────────────────────────────────────
    flows = analyze_capital_flows(processed)
    print_capital_flows(flows)

    # ── TRADE OPPORTUNITIES ──────────────────────────────────────────────────
    print_cross_country_opportunity(processed)

    print()
    print(c("═" * 60, "DIM"))
    print(c("  HOW TO USE THIS SCRIPT", "BOLD"))
    print(c("═" * 60, "DIM"))
    print("""
  1. Every quarter, update the COUNTRIES_DATA dict with
     the latest official figures from:
       - Fed / ECB / BOE / BOJ / RBA press releases
       - Tradingeconomics.com for quick lookup
       - Bloomberg / Reuters for yield data

  2. Update rate_trend and cpi_trend:
       'rising'  = central bank hiking or data trending up
       'holding' = on pause
       'falling' = cutting cycle or data trending down

  3. Read the CAPITAL FLOW ANALYSIS to see where money moves

  4. Read MACRO TRADE OPPORTUNITIES for positioning ideas

  5. The model is mechanical — always layer in:
       - Geopolitical risk
       - Central bank forward guidance (words matter)
       - Market positioning (crowded trades reverse fast)
  """)
    print(c("  ★ The gap between cycle phases is where the money is made", "CYAN"))
    print()


if __name__ == "__main__":
    run()