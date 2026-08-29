"""Reproducible acquisition of observed multivariate benchmark datasets."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import numpy as np
import pandas as pd


DATASETS = {
    "uci_air_quality": {
        "url": "https://archive.ics.uci.edu/static/public/360/air+quality.zip",
        "member": "AirQualityUCI.csv",
        "citation": "De Vito et al., UCI Air Quality, 2008, DOI 10.24432/C59K5F",
        "frequency": "hourly",
        "columns": ["CO(GT)", "C6H6(GT)", "NOx(GT)", "NO2(GT)", "T", "RH", "AH"],
    },
    "uci_appliances_energy": {
        "url": "https://archive.ics.uci.edu/static/public/374/appliances+energy+prediction.zip",
        "member": "energydata_complete.csv",
        "citation": "Candanedo et al., UCI Appliances Energy Prediction, 2017, DOI 10.24432/C5VC8G",
        "frequency": "10 minutes",
        "columns": ["Appliances", "lights", "T1", "RH_1", "T2", "RH_2", "T_out", "RH_out"],
    },
}


def _download(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:
        return response.read()


def load_public_dataset(
    name: str,
    cache_dir: str | Path,
) -> tuple[pd.DataFrame, dict]:
    if name not in DATASETS:
        raise ValueError(f"Unknown dataset: {name}")
    spec = DATASETS[name]
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    archive_path = cache / f"{name}.zip"
    if not archive_path.exists():
        archive_path.write_bytes(_download(spec["url"]))
    payload = archive_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()

    with ZipFile(io.BytesIO(payload)) as archive:
        if name == "uci_air_quality":
            frame = pd.read_csv(
                archive.open(spec["member"]),
                sep=";",
                decimal=",",
                na_values=-200,
            )
        else:
            frame = pd.read_csv(archive.open(spec["member"]))

    frame = frame[spec["columns"]].apply(pd.to_numeric, errors="coerce")
    frame = frame.replace([np.inf, -np.inf], np.nan).interpolate(limit_direction="both")
    manifest = {
        **spec,
        "sha256": digest,
        "rows": len(frame),
        "columns_count": len(frame.columns),
    }
    (cache / f"{name}.manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return frame, manifest
