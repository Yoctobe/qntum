"""Objective checks that must pass before journal submission."""

from __future__ import annotations

import json

from experiments.common import RESULTS, write_result


def run() -> dict:
    required = [
        "table4_structure_recovery.json",
        "table5_observed_benchmarks.json",
        "table6_stability.json",
        "event_study.json",
        "manifest.json",
    ]
    artifacts_present = all((RESULTS / name).exists() for name in required)
    gates = {"artifacts_present": artifacts_present}

    observed_path = RESULTS / "table5_observed_benchmarks.json"
    if observed_path.exists():
        observed = json.loads(observed_path.read_text(encoding="utf-8"))
        real_panels = [panel for panel in observed["panels"] if not panel["panel"].endswith("negative_control")]
        gates["two_observed_panels"] = len(real_panels) >= 2
        gates["beats_persistence_majority"] = bool(real_panels) and sum(
            panel["qntum"]["horizons"]["1"]["mae"]
            < panel["baselines"]["persistence"]["1"]["mae"]
            for panel in real_panels
        ) > len(real_panels) / 2
        gates["interval_coverage"] = bool(real_panels) and all(
            0.85 <= panel["intervals"]["intervals"]["0.9"]["coverage"] <= 0.95
            for panel in real_panels
        )

    stability_path = RESULTS / "table6_stability.json"
    if stability_path.exists():
        stability = json.loads(stability_path.read_text(encoding="utf-8"))
        gates["no_capped_divergence"] = stability["summary"]["capped_divergence_rate"] == 0

    payload = {
        "gates": gates,
        "ready_for_forecasting_journal": bool(gates) and all(gates.values()),
        "fallback_positioning": "auditable scenario-engine software" if not all(gates.values()) else None,
    }
    write_result("publication_gates.json", payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
