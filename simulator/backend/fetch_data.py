"""
Fetch monthly US macro + market history for the QNTUM simulator.

Sources (all free, no API key):
    - FRED fredgraph CSV endpoints
    - datahub.io gold prices (LBMA monthly, maintained mirror)

Output:
    data/us_macro_monthly.csv      — inner join (simulation panel; binding
                                     constraint: broad dollar index, 2006→)
    data/us_macro_monthly_full.csv — outer join with NaNs (fitting panel;
                                     each coupling is fitted on its own pair
                                     overlap, e.g. CPI←oil back to 1986)

Run: python3 fetch_data.py
"""

import io
import subprocess
from pathlib import Path

import pandas as pd

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
GOLD_CSV = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"

# series_id → (channel_name, resample: None for already-monthly, "mean" for daily)
FRED_SERIES = {
    "CPIAUCSL": ("CPI_Index", None),
    "FEDFUNDS": ("Fed_Funds", None),
    "UNRATE": ("Unemployment", None),
    "INDPRO": ("Industrial_Production", None),
    "GS10": ("Yield_10Y", None),
    "CSUSHPISA": ("Housing", None),
    "MCOILWTICO": ("Oil_WTI", None),
    "VIXCLS": ("VIX", "mean"),
    "DTWEXBGS": ("Dollar_Index", "mean"),
    "NASDAQCOM": ("Nasdaq", "mean"),
}


def fetch_csv(url: str) -> pd.DataFrame:
    # curl uses the system trust store; python.org installs often lack CA certs
    result = subprocess.run(
        ["curl", "-sL", "--http1.1", "--max-time", "30", url],
        capture_output=True, text=True, check=True,
    )
    return pd.read_csv(io.StringIO(result.stdout))


def fetch_fred(series: str, name: str, resample: str | None) -> pd.Series:
    df = fetch_csv(FRED_CSV.format(series=series))
    df.columns = ["date", name]
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date")[name]
    s = pd.to_numeric(s, errors="coerce").dropna()
    if resample:
        s = s.resample("MS").mean().dropna()
    else:
        s.index = s.index.to_period("M").to_timestamp()  # normalize to month start
    print(f"  {name:<24} {series:<12} {s.index[0].date()} → {s.index[-1].date()}  ({len(s)} obs)")
    return s


def fetch_gold() -> pd.Series:
    df = fetch_csv(GOLD_CSV)
    df.columns = ["date", "Gold"]
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m")
    s = df.set_index("date")["Gold"].dropna()
    print(f"  {'Gold':<24} {'datahub':<12} {s.index[0].date()} → {s.index[-1].date()}  ({len(s)} obs)")
    return s


def main():
    print("Fetching series...")
    columns = {}
    for series, (name, resample) in FRED_SERIES.items():
        try:
            columns[name] = fetch_fred(series, name, resample)
        except Exception as exc:
            print(f"  ✗ {name} ({series}) failed: {exc} — skipping channel")

    try:
        columns["Gold"] = fetch_gold()
    except Exception as exc:
        print(f"  ✗ Gold failed: {exc} — skipping channel")

    df = pd.DataFrame(columns)

    # CPI index → YoY inflation rate (the channel users actually think in)
    if "CPI_Index" in df.columns:
        df["CPI_Inflation"] = 100.0 * (df["CPI_Index"] / df["CPI_Index"].shift(12) - 1.0)
        df = df.drop(columns=["CPI_Index"])

    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)

    # Fitting panel starts at the floating-rate era: earlier data (gold fixed
    # by law, pre-war output swings) belongs to a different regime and would
    # distort the robust scale estimates.
    full = df[df.index >= "1971-01-01"].dropna(how="all")
    print(f"\nFull panel (outer join): {full.index[0].date()} → {full.index[-1].date()}  ({len(full)} monthly rows)")
    full_out = data_dir / "us_macro_monthly_full.csv"
    full.round(4).rename_axis("Date").to_csv(full_out)
    print(f"Saved → {full_out}")

    df = df.dropna()
    print(f"Aligned (inner join): {df.index[0].date()} → {df.index[-1].date()}  ({len(df)} monthly obs)")
    out = data_dir / "us_macro_monthly.csv"
    df.round(4).rename_axis("Date").to_csv(out)
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
