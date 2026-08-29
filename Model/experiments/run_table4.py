"""Repeated synthetic graph-recovery and pin-sensitivity study."""

from __future__ import annotations

import argparse
from collections import defaultdict

import numpy as np

from experiments.common import write_result
from quantum_model.synthetic_studies import run_recovery_study


def run(full: bool = False) -> dict:
    records = run_recovery_study(seeds=100 if full else 5)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for record in records:
        groups[(record["sample_size"], record["pin_coverage"], record["incorrect_pin_fraction"])].append(record)

    summary = []
    for (sample_size, coverage, incorrect), values in sorted(groups.items()):
        summary.append(
            {
                "sample_size": sample_size,
                "pin_coverage": coverage,
                "incorrect_pin_fraction": incorrect,
                "replications": len(values),
                "f1_mean": float(np.mean([item["f1"] for item in values])),
                "f1_std": float(np.std([item["f1"] for item in values])),
                "coefficient_rmse_mean": float(np.mean([item["coefficient_rmse"] for item in values])),
                "h6_mae_mean": float(np.mean([item["forecast"]["6"]["mae"] for item in values])),
            }
        )
    payload = {"study": "synthetic_structure_recovery", "records": records, "summary": summary}
    write_result("table4_structure_recovery.json", payload)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    run(args.full)
