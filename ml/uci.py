"""UCI Appliances Energy Prediction adapter (Phase 4, FOR-04, D-12/D-13).

Demand-only validation: the UCI set has NO occupancy ground truth, so
occupancy validation stays synthetic — only the demand forecaster is
evaluated here. The emitted frame carries ``occupancy=0`` placeholders that
must never be scored as an occupancy target.

Horizon mapping: native UCI steps are 10-min, so H=3 steps = 30 min and
H=6 steps = 60 min (documented here, not in sim/ or ctrl/).

Fetch uses stdlib only (urllib + zipfile + pandas, D-12/D-13 — no new
dataset-loader deps). Time-boxed: any network failure skips gracefully with
a printed reason and exit 0 (synthetic-only fallback, locked D-13).

This module touches nothing in sim/ or ctrl/ (CONTEXT.md integration rule).
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile

import pandas as pd

UCI_URL = (
    "https://archive.ics.uci.edu/static/public/374/"
    "appliances%20energy%20prediction.zip"
)
EXPECTED_ROWS = 19735
FETCH_TIMEOUT_S = 30

# Required columns on load (superset check; header variants tolerated).
REQUIRED_COLS = {"date", "Appliances", "lights", "T1", "RH_1", "T_out",
                 "Press_mm_hg", "RH_out", "Windspeed", "Visibility",
                 "Tdewpoint", "rv1", "rv2"}
NOISE_PROBES = ("rv1", "rv2")  # documented random probes — always dropped

# 04-01 room-frame schema this adapter aligns to (demand path only).
FRAME_COLS = ("timestamp", "room", "T_in_C", "T_out_C", "RH_pct",
              "occupancy", "power_kW")


def fetch_zip(url=UCI_URL, timeout=FETCH_TIMEOUT_S):
    """Download the UCI zip with a hard timeout; raises on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "ias-course-project"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def load_appliances(zip_bytes):
    """Parse + verify the UCI frame: 19,735 rows, column set, no silent NaNs."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError("uci: no CSV inside zip")
        with zf.open(names[0]) as fh:
            df = pd.read_csv(fh)
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"uci: missing columns {sorted(missing)}")
    if len(df) != EXPECTED_ROWS:
        raise ValueError(f"uci: row count {len(df)} != {EXPECTED_ROWS}")
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["date"])
    if df["timestamp"].isna().any():
        raise ValueError("uci: unparseable dates fail loudly, never imputed")
    return df.drop(columns=list(NOISE_PROBES))


def to_demand_frame(df):
    """Map UCI → 04-01 room-frame schema for demand-only validation.

    Mapping: T1→T_in_C, T_out→T_out_C, RH_1→RH_pct, Appliances (Wh per
    10-min interval) → power_kW (= Wh*0.006, i.e. Wh/1000 per 1/6 h).
    ``occupancy`` is a 0 placeholder — UCI has no occupancy ground truth.
    """
    out = pd.DataFrame({
        "timestamp": pd.to_datetime(df["timestamp"]),
        "room": "uci_appliances",
        "T_in_C": pd.to_numeric(df["T1"], errors="raise").astype(float),
        "T_out_C": pd.to_numeric(df["T_out"], errors="raise").astype(float),
        "RH_pct": pd.to_numeric(df["RH_1"], errors="raise").astype(float),
        "occupancy": 0.0,
        "power_kW": pd.to_numeric(df["Appliances"], errors="raise").astype(float) * 0.006,
    }).sort_values("timestamp").reset_index(drop=True)
    if out[["T_in_C", "T_out_C", "RH_pct", "power_kW"]].isna().any().any():
        raise ValueError("uci: NaN telemetry fails loudly, never imputed")
    return out[list(FRAME_COLS)]


def load_or_skip(url=UCI_URL, timeout=FETCH_TIMEOUT_S, fetcher=None):
    """Fetch+adapt, or return (None, reason) on any failure — never raises."""
    try:
        blob = (fetcher or fetch_zip)(url, timeout=timeout)
        frame = to_demand_frame(load_appliances(blob))
        return frame, ""
    except Exception as exc:
        return None, f"uci skipped (synthetic-only fallback): {exc}"


def main(url=UCI_URL, timeout=FETCH_TIMEOUT_S):
    """CLI: adapt UCI or print the documented skip reason; always exit 0."""
    frame, reason = load_or_skip(url=url, timeout=timeout)
    if frame is None:
        print(reason)
        return 0
    print(f"uci aligned frame: {len(frame)} rows, "
          f"{frame['timestamp'].min()} → {frame['timestamp'].max()}")
    print("demand-only: occupancy column is a 0 placeholder (no UCI ground truth); "
          "horizons H=3/H=6 native 10-min steps = 30/60 min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
