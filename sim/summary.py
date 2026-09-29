"""Multi-seed summary helper (SIM-03/D-13/D-08, RESEARCH Findings section 6).

`summarize(scenario_dir)` loads every seed telemetry.csv under
results/<scenario>/seed*/ and returns a per-room DataFrame of mean+-std over
seeds (mean T_in, energy kWh, comfort pct) — the Phase-3-harness embryo, so
keep this signature stable. Per-run numbers come from sim/metrics.py on the
same CSVs, so per-run and multi-seed tables cannot disagree. Also writes
summary.csv next to the seed dirs.
"""

import pathlib

import numpy as np
import pandas as pd

from sim import metrics as met


def summarize(scenario_dir):
    """Load N seed CSVs -> per-room mean+-std DataFrame (+ summary.csv)."""
    scenario_dir = pathlib.Path(scenario_dir)
    csvs = sorted(scenario_dir.glob("seed*/telemetry.csv"))
    if not csvs:
        raise FileNotFoundError(f"no seed*/telemetry.csv under {scenario_dir}")
    per_seed = {}  # seed -> {room: stats}
    for csv_path in csvs:
        frame = pd.read_csv(csv_path)
        per_seed[csv_path.parent.name] = {
            room: met.room_stats(group)
            for room, group in frame.groupby("room")
        }
    rooms = sorted(next(iter(per_seed.values())))
    rows = []
    for room in rooms:
        means = np.array([per_seed[s][room]["mean_T_in"] for s in per_seed])
        energies = np.array([per_seed[s][room]["energy_kwh"] for s in per_seed])
        comforts = np.array([per_seed[s][room]["comfort_pct"] for s in per_seed])
        rows.append({
            "room": room,
            "n_seeds": len(csvs),
            "mean_T_in_mean": float(means.mean()),
            "mean_T_in_std": float(means.std(ddof=1)) if len(csvs) > 1 else 0.0,
            "energy_kwh_mean": float(energies.mean()),
            "energy_kwh_std": float(energies.std(ddof=1)) if len(csvs) > 1 else 0.0,
            "comfort_pct_mean": float(np.nanmean(comforts)),
            "comfort_pct_std": (
                float(np.nanstd(comforts, ddof=1)) if len(csvs) > 1 else 0.0
            ),
        })
    out = pd.DataFrame(rows, columns=[
        "room", "n_seeds", "mean_T_in_mean", "mean_T_in_std",
        "energy_kwh_mean", "energy_kwh_std", "comfort_pct_mean", "comfort_pct_std",
    ])
    out.to_csv(scenario_dir / "summary.csv", index=False, float_format="%.4f")
    return out
