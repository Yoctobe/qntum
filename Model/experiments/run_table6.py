"""Repeated stability and transient-growth stress study."""

from __future__ import annotations

import argparse

import numpy as np

from experiments.common import write_result
from quantum_model.evaluation import always_on_events
from quantum_model.quantum_v2 import build_quantum_v2
from quantum_model.stability import stability_report
from quantum_model.synthetic_studies import generate_sparse_var


def _path_growth(model, history: np.ndarray, horizon: int = 100) -> dict:
    events = always_on_events([f"x{i}" for i in range(model.n)], horizon)
    result = model.forecast(
        events,
        horizon,
        initial_state=history[-1],
        initial_history=history[:-1],
    )
    initial_norm = float(np.linalg.norm(history[-1], ord=np.inf))
    max_norm = float(np.max(np.linalg.norm(result["point"], ord=np.inf, axis=1)))
    return {
        "initial_norm": initial_norm,
        "max_100_step_norm": max_norm,
        "growth_factor": max_norm / max(initial_norm, 1e-12),
    }


def run(full: bool = False) -> dict:
    records = []
    for seed in range(100 if full else 10):
        system = generate_sparse_var(
            n_variables=8,
            n_steps=180,
            density=0.25,
            spectral_radius=1.02,
            noise_scale=0.05,
            seed=seed,
        )
        training = system.data[:120]
        common = dict(
            normalized_data=training,
            variable_names=system.variable_names,
            min_corr=0.1,
            alpha=0.0,
            beta=1.0,
            max_lag_steps=1,
            l1_penalty=0.002,
        )
        uncapped = build_quantum_v2(**common, max_spectral_radius=10.0)
        capped = build_quantum_v2(**common, max_spectral_radius=0.98)
        uncapped_report = stability_report(uncapped.I, uncapped.alpha, uncapped.beta)
        capped_report = stability_report(capped.I, capped.alpha, capped.beta)
        records.append(
            {
                "seed": seed,
                "uncapped": {
                    **uncapped_report.as_dict(),
                    **_path_growth(uncapped, training),
                },
                "companion_capped": {
                    **capped_report.as_dict(),
                    **_path_growth(capped, training),
                },
            }
        )

    payload = {
        "study": "companion_stability_stress",
        "records": records,
        "summary": {
            "replications": len(records),
            "uncapped_divergence_rate": float(np.mean([r["uncapped"]["growth_factor"] > 100 for r in records])),
            "capped_divergence_rate": float(np.mean([r["companion_capped"]["growth_factor"] > 100 for r in records])),
            "capped_mean_transient_gain": float(np.mean([r["companion_capped"]["max_transient_gain"] for r in records])),
        },
    }
    write_result("table6_stability.json", payload)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    run(args.full)
