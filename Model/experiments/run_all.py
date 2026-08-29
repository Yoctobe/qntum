"""Run every paper experiment and write a reproducibility manifest."""

from __future__ import annotations

import argparse
import importlib.metadata
import platform
import subprocess

from experiments.common import ROOT, write_result
from experiments.run_table4 import run as run_table4
from experiments.run_table5 import run as run_table5
from experiments.run_table6 import run as run_table6
from experiments.run_event_study import run as run_event_study


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def run(full: bool = False, include_public: bool = True) -> dict:
    table4 = run_table4(full)
    table5 = run_table5(full, include_public)
    table6 = run_table6(full)
    event_study = run_event_study()
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = {
        "git_revision": revision,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            name: _version(name)
            for name in ("numpy", "pandas", "scipy", "matplotlib")
        },
        "mode": "full" if full else "fast",
        "public_datasets_included": include_public,
        "artifacts": {
            "table4_records": len(table4["records"]),
            "table5_panels": len(table5["panels"]),
            "table6_records": len(table6["records"]),
            "event_study": event_study,
        },
    }
    write_result("manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--skip-public", action="store_true")
    args = parser.parse_args()
    run(args.full, not args.skip_public)
