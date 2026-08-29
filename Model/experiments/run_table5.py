"""Observed benchmark comparison with recursive forecasts and calibration."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.common import ROOT, write_result
from quantum_model.baselines import default_baselines
from quantum_model.evaluation import evaluate_baselines, evaluate_intervals, evaluate_recursive
from quantum_model.pipeline import PreprocessingPipeline
from quantum_model.public_datasets import DATASETS, load_public_dataset
from quantum_model.quantum_v2 import build_quantum_v2


def _daily_blocks(frame: pd.DataFrame, block_size: int) -> pd.DataFrame:
    groups = np.arange(len(frame)) // block_size
    return frame.groupby(groups).mean().dropna()


def _evaluate_panel(name: str, frame: pd.DataFrame, interval_paths: int) -> dict:
    prepared = PreprocessingPipeline().prepare_dataframe(
        frame,
        train_fraction=0.7,
        date_column=None,
    )
    fit_end = max(12, int(prepared.split_increment * 0.8))
    model = build_quantum_v2(
        prepared.normalized[:fit_end],
        prepared.variable_names,
        min_corr=0.15,
        alpha=0.0,
        beta=1.0,
        max_lag_steps=1,
        l1_penalty=0.005,
    )
    horizons = tuple(h for h in (1, 3, 6, 12) if h < len(prepared.test_normalized))
    qntum = evaluate_recursive(
        model,
        prepared.normalized,
        prepared.variable_names,
        prepared.split_increment,
        horizons,
        levels=prepared.levels,
        params=prepared.params,
    )
    baselines = evaluate_baselines(
        default_baselines(),
        prepared.normalized[:fit_end],
        prepared.normalized,
        prepared.variable_names,
        prepared.split_increment,
        horizons,
    )
    intervals = evaluate_intervals(
        model,
        prepared.normalized,
        prepared.variable_names,
        prepared.split_increment,
        horizon=min(3, max(horizons)),
        n_paths=interval_paths,
        calibration_start=fit_end,
    )
    return {
        "panel": name,
        "rows": len(frame),
        "variables": len(prepared.variable_names),
        "train_increments": len(prepared.train_normalized),
        "fit_increments": fit_end,
        "calibration_increments": prepared.split_increment - fit_end,
        "test_increments": len(prepared.test_normalized),
        "qntum": qntum,
        "baselines": baselines,
        "intervals": intervals,
        "stability": model.stability.as_dict(),
        "relationship_count": len(model.I._relationships),
    }


def run(full: bool = False, include_public: bool = True) -> dict:
    panels = []
    manifests = []
    interval_paths = 500 if full else 100
    if include_public:
        cache = ROOT / "data" / "public"
        for name in DATASETS:
            frame, manifest = load_public_dataset(name, cache)
            block = 24 if name == "uci_air_quality" else 144
            panels.append(_evaluate_panel(name, _daily_blocks(frame, block), interval_paths))
            manifests.append(manifest)

    macro_path = ROOT.parent / "simulator" / "backend" / "data" / "us_macro_monthly.csv"
    if macro_path.exists():
        macro = pd.read_csv(macro_path).drop(columns=["Date", "Source"], errors="ignore")
        panels.append(_evaluate_panel("us_macro_negative_control", macro, interval_paths))

    payload = {
        "study": "observed_recursive_benchmarks",
        "panels": panels,
        "dataset_manifests": manifests,
    }
    write_result("table5_observed_benchmarks.json", payload)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--skip-public", action="store_true")
    args = parser.parse_args()
    run(args.full, not args.skip_public)
