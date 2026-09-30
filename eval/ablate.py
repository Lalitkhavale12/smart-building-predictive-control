"""Forecast x carbon ablation arms (Phase 5, plan 05-02, D-07/D-08).

Zero reruns — all arms recompute on saved frames from results/full_matrix/:

- Forecast arm (panel='forecast'): c4-with vs c4-as-c3 per (scenario, seed),
  paired deltas + std. Free from the matrix (T-05-04: no in-loop training).
- Carbon arm (panel='carbon'): per (scenario, seed, controller) CO2 under the
  hourly EF series vs flat EF = series mean 0.710 every hour. On 'hourly'
  rows co2_delta = co2_hourly - co2_flat (the load-shape premium: positive
  means the controller's load skews toward dirty hours). On 'flat' rows
  co2_delta = co2_flat - 0.710*energy (self-consistency residual, ~1e-12):
  identical kWh profiles show zero shifting delta (PITFALLS Pitfall 6 gate).

D-08 carbon-blind variant: accounting-only is the shipped ablation; the
behavioral counterpart (precool_blackout 18-22) was measured in 05-01
(-0.2%/-3.7% energy, only config cutting heatwave peak-share 0.104->0.070)
and is cited, not re-run.

Writes constrained under results/ (.. rejected, compare.py pattern).
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ctrl.harness import compute_metrics  # noqa: E402
from sim import config as cfg  # noqa: E402
from sim import grid as grid_mod  # noqa: E402

RESULTS_ROOT = pathlib.Path("results")
MATRIX_ROOT = RESULTS_ROOT / "full_matrix"

FLAT_EF = grid_mod.GRID_EF_BASE_KG_PER_KWH  # 0.710 series mean

CARBON_CONTROLLERS = ("c1", "c2", "c3", "c4-with")  # c4-as-c3 == c3 exactly


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


def _co2_flat(frame):
    """CO2 under flat EF = series mean every hour (== 0.710 * energy)."""
    return float((frame["power_kW"] / 60.0).sum() * FLAT_EF)


def run_ablation(matrix_root=MATRIX_ROOT, scenarios=None):
    """Build the two-panel ablation table from saved frames (no reruns)."""
    scenarios = list(cfg.SCENARIOS) if scenarios is None else list(scenarios)
    seeds = list(cfg.PAIRED_SEEDS)
    rows = []

    # Forecast arm: c4-with vs c4-as-c3, paired within (scenario, seed).
    for scenario in scenarios:
        for seed in seeds:
            m_on = compute_metrics(_load_frame(matrix_root, "c4-with", scenario, seed))
            m_off = compute_metrics(_load_frame(matrix_root, "c4-as-c3", scenario, seed))
            rows.append({
                "panel": "forecast", "scenario": scenario, "seed": seed,
                "controller": "c4-with-vs-c4-as-c3", "ef_mode": "hourly",
                "energy_kwh": m_on["energy_kwh"], "cost_rs": m_on["cost_rs"],
                "co2_kg": m_on["co2_kg"], "comfort_pct": m_on["comfort_pct"],
                "co2_delta": float("nan"),
                "d_energy_kwh": m_on["energy_kwh"] - m_off["energy_kwh"],
                "d_cost_rs": m_on["cost_rs"] - m_off["cost_rs"],
                "d_co2_kg": m_on["co2_kg"] - m_off["co2_kg"],
                "d_comfort_pp": m_on["comfort_pct"] - m_off["comfort_pct"],
            })

    # Carbon arm: hourly vs flat accounting on the same saved frame.
    for controller in CARBON_CONTROLLERS:
        for scenario in scenarios:
            for seed in seeds:
                frame = _load_frame(matrix_root, controller, scenario, seed)
                m = compute_metrics(frame)
                co2_flat = _co2_flat(frame)
                rows.append({
                    "panel": "carbon", "scenario": scenario, "seed": seed,
                    "controller": controller, "ef_mode": "hourly",
                    "energy_kwh": m["energy_kwh"], "cost_rs": m["cost_rs"],
                    "co2_kg": m["co2_kg"], "comfort_pct": m["comfort_pct"],
                    "co2_delta": m["co2_kg"] - co2_flat,
                    "d_energy_kwh": float("nan"), "d_cost_rs": float("nan"),
                    "d_co2_kg": float("nan"), "d_comfort_pp": float("nan"),
                })
                rows.append({
                    "panel": "carbon", "scenario": scenario, "seed": seed,
                    "controller": controller, "ef_mode": "flat",
                    "energy_kwh": m["energy_kwh"],
                    "cost_rs": m["cost_rs"], "co2_kg": co2_flat,
                    "comfort_pct": m["comfort_pct"],
                    "co2_delta": co2_flat - FLAT_EF * m["energy_kwh"],
                    "d_energy_kwh": float("nan"), "d_cost_rs": float("nan"),
                    "d_co2_kg": float("nan"), "d_comfort_pp": float("nan"),
                })
    return pd.DataFrame(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Forecast x carbon ablations")
    parser.add_argument("--matrix-root", default=str(MATRIX_ROOT))
    parser.add_argument("--scenarios", default=",".join(cfg.SCENARIOS))
    parser.add_argument("--out", default="ablation.csv")
    args = parser.parse_args(argv)
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    table = run_ablation(args.matrix_root, scenarios)

    # Flat-EF gate: identical kWh profiles show zero shifting delta.
    flat = table[table["ef_mode"] == "flat"]
    worst = float(flat["co2_delta"].abs().max())
    assert (flat["co2_delta"].abs() < 1e-9).all(), "flat-EF gate violated"
    print(f"flat-EF gate: max |co2_delta| = {worst:.2e} (n={len(flat)}) — PASS")

    # Forecast-ablation panel: paired deltas + std per scenario.
    for scenario in scenarios:
        sub = table[(table["panel"] == "forecast")
                    & (table["scenario"] == scenario)]
        for col in ("d_energy_kwh", "d_cost_rs", "d_co2_kg", "d_comfort_pp"):
            vals = sub[col].to_numpy(dtype=float)
            print(f"forecast {scenario} {col}: {np.mean(vals):+.4f}"
                  f"+/-{np.std(vals, ddof=1):.4f} (n={len(vals)})")

    # Carbon-ablation panel: shifting-attributable CO2 = paired C4-C3 delta
    # under hourly EF minus under flat EF, per (scenario, seed).
    hourly = table[(table["panel"] == "carbon")
                   & (table["ef_mode"] == "hourly")]
    for scenario in scenarios:
        shifts = []
        for seed in cfg.PAIRED_SEEDS:
            c4 = hourly[(hourly["scenario"] == scenario)
                        & (hourly["seed"] == seed)
                        & (hourly["controller"] == "c4-with")].iloc[0]
            c3 = hourly[(hourly["scenario"] == scenario)
                        & (hourly["seed"] == seed)
                        & (hourly["controller"] == "c3")].iloc[0]
            d_hourly = c4["co2_kg"] - c3["co2_kg"]
            d_flat = FLAT_EF * (c4["energy_kwh"] - c3["energy_kwh"])
            shifts.append(d_hourly - d_flat)
        shifts = np.asarray(shifts)
        print(f"carbon {scenario} shifting-attributable dCO2 "
              f"(hourly-pair minus flat-pair): {np.mean(shifts):+.4f}"
              f"+/-{np.std(shifts, ddof=1):.4f} kg (n={len(shifts)})")

    out = _out_path(args.out)
    table.to_csv(out, index=False, float_format="%.4f")
    print(f"wrote {out} ({len(table)} rows)")
    return out


if __name__ == "__main__":
    main()
