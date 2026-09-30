"""Sensitivity recomputes (Phase 5, plan 05-02, D-13).

Pure recomputes on saved frames from results/full_matrix/ — zero reruns:

- EF scale x{0.8, 1.0, 1.2} via hourly_rows(ef_base=0.710*s): CO2 recompute.
- Tariff scale x{0.8, 1.0, 1.2}: exact linear post-multiply of cost_rs.
- Comfort band +-1C via comfort_pct recompute with overridden
  COMFORT_T_MIN/MAX (eval.sweep.comfort_at_band): locked 22-26 (headlines
  stay on the locked band per D-03), wide 21-27, narrow 23-25.

Output results/sensitivity.csv: tables, not new claims. Exam-day stub
labeling preserved via the scenario column (matrix convention).

Writes constrained under results/ (.. rejected, compare.py pattern).
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ctrl.harness import compute_metrics  # noqa: E402
from eval.sweep import comfort_at_band  # noqa: E402
from sim import config as cfg  # noqa: E402
from sim import grid as grid_mod  # noqa: E402

RESULTS_ROOT = pathlib.Path("results")
MATRIX_ROOT = RESULTS_ROOT / "full_matrix"

EF_SCALES = (0.8, 1.0, 1.2)
TARIFF_SCALES = (0.8, 1.0, 1.2)
BANDS = {"locked22-26": (22.0, 26.0), "wide21-27": (21.0, 27.0),
         "narrow23-25": (23.0, 25.0)}

SENS_CONTROLLERS = ("c1", "c2", "c3", "c4-with")  # c4-as-c3 == c3 exactly


def _out_path(name):
    for part in pathlib.PurePath(name).parts:
        if part == "..":
            raise ValueError(f"path traversal rejected: {name!r}")
    root = (pathlib.Path.cwd() / RESULTS_ROOT).resolve()
    candidate = (pathlib.Path.cwd() / RESULTS_ROOT / name).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"output must stay under results/, got {candidate}")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def _load_frame(matrix_root, controller, scenario, seed):
    path = (pathlib.Path(matrix_root) / controller / scenario
            / f"seed{seed:02d}" / "telemetry.csv")
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path} — run eval/matrix.py for the full matrix first")
    return pd.read_csv(path)


def _co2_at_ef_scale(frame, scale):
    """CO2 recompute with the EF series scaled by `scale` (shape preserved)."""
    hours = pd.to_datetime(frame["timestamp"]).dt.hour
    ef_by_hour = {h: ef for h, ef, _ in
                  grid_mod.hourly_rows(
                      ef_base=grid_mod.GRID_EF_BASE_KG_PER_KWH * scale)}
    return float(((frame["power_kW"] / 60.0) * hours.map(ef_by_hour)).sum())


def run_sensitivity(matrix_root=MATRIX_ROOT, scenarios=None):
    """All three sensitivity tables from saved frames (no reruns)."""
    scenarios = list(cfg.SCENARIOS) if scenarios is None else list(scenarios)
    seeds = list(cfg.PAIRED_SEEDS)
    rows = []
    for scenario in scenarios:
        for controller in SENS_CONTROLLERS:
            frames = {s: _load_frame(matrix_root, controller, scenario, s)
                      for s in seeds}
            base = {s: compute_metrics(frames[s]) for s in seeds}
            energy = np.array([base[s]["energy_kwh"] for s in seeds])
            # EF scale -> CO2 recompute.
            for scale in EF_SCALES:
                co2 = np.array([_co2_at_ef_scale(frames[s], scale)
                                for s in seeds])
                rows.append({
                    "analysis": "ef_scale", "scenario": scenario,
                    "controller": controller, "param": str(scale),
                    "energy_kwh_mean": float(np.mean(energy)),
                    "energy_kwh_std": float(np.std(energy, ddof=1)),
                    "co2_kg_mean": float(np.mean(co2)),
                    "co2_kg_std": float(np.std(co2, ddof=1)),
                    "cost_rs_mean": float("nan"), "cost_rs_std": float("nan"),
                    "comfort_pct_mean": float("nan"),
                    "comfort_pct_std": float("nan"),
                })
            # Tariff scale -> exact linear post-multiply of cost.
            for scale in TARIFF_SCALES:
                cost = np.array([base[s]["cost_rs"] * scale for s in seeds])
                rows.append({
                    "analysis": "tariff_scale", "scenario": scenario,
                    "controller": controller, "param": str(scale),
                    "energy_kwh_mean": float(np.mean(energy)),
                    "energy_kwh_std": float(np.std(energy, ddof=1)),
                    "co2_kg_mean": float("nan"), "co2_kg_std": float("nan"),
                    "cost_rs_mean": float(np.mean(cost)),
                    "cost_rs_std": float(np.std(cost, ddof=1)),
                    "comfort_pct_mean": float("nan"),
                    "comfort_pct_std": float("nan"),
                })
            # Band +-1C -> comfort recompute (headlines stay locked, D-03).
            for name, (t_min, t_max) in BANDS.items():
                comfort = np.array([comfort_at_band(frames[s], t_min, t_max)
                                    for s in seeds])
                rows.append({
                    "analysis": "band", "scenario": scenario,
                    "controller": controller, "param": name,
                    "energy_kwh_mean": float(np.mean(energy)),
                    "energy_kwh_std": float(np.std(energy, ddof=1)),
                    "co2_kg_mean": float("nan"), "co2_kg_std": float("nan"),
                    "cost_rs_mean": float("nan"), "cost_rs_std": float("nan"),
                    "comfort_pct_mean": float(np.nanmean(comfort)),
                    "comfort_pct_std": (float(np.nanstd(comfort, ddof=1))
                                        if len(comfort) > 1 else 0.0),
                })
    return pd.DataFrame(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sensitivity recomputes")
    parser.add_argument("--matrix-root", default=str(MATRIX_ROOT))
    parser.add_argument("--scenarios", default=",".join(cfg.SCENARIOS))
    parser.add_argument("--out", default="sensitivity.csv")
    args = parser.parse_args(argv)
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    table = run_sensitivity(args.matrix_root, scenarios)
    for analysis in ("ef_scale", "tariff_scale", "band"):
        sub = table[table["analysis"] == analysis]
        print(f"{analysis}: {len(sub)} rows "
              f"({sub['scenario'].nunique()} scenarios x "
              f"{sub['controller'].nunique()} controllers x "
              f"{sub['param'].nunique()} params)")
    out = _out_path(args.out)
    table.to_csv(out, index=False, float_format="%.4f")
    print(f"wrote {out} ({len(table)} rows)")
    return out


if __name__ == "__main__":
    main()
