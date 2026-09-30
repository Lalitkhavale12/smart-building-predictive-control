"""C4 threshold sweep (Phase 5, plan 05-01, D-01/D-02/D-12).

Grid of occ_threshold x precool_level x earlyoff_from_reduced x
require_both_horizons (pruned to ~10 configs) on weekday + heatwave x
PAIRED_SEEDS, one frozen forecaster per timetable group (train once, never
in the loop). Every row carries energy + comfort (CTL-06) + peak-window kWh
share 18-22h (D-05) + cost/CO2 deltas vs stock C4 from compute_metrics
against the hourly series (D-04 accounting-level shifting proof).

Analysis-only probes (separate CSVs, never committed physics):
- plant-size sensitivity: Q_HVAC ON in {-2.5,-1.75} via scratch override
  inside this script only (D-02, T-05-01); sim/config.py untouched.
- comfort-band +-1C recompute on in-memory frames, no reruns (D-03/D-13).

Writes are constrained under results/ (.. rejected, compare.py pattern).
"""

import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from ctrl.harness import compute_metrics, run_controller
from ctrl.predictive import PredictivePolicy, build_frozen_forecaster
from sim import config as cfg
from sim import metrics as met

RESULTS_ROOT = pathlib.Path("results")

# H3 x H1 full (3x2), H2/H4 one arm each, D-08 blackout arm, one combo.
CONFIGS = [
    ("stock", {}),
    ("thr3", {"occ_threshold": 3}),
    ("thr8", {"occ_threshold": 8}),
    ("precool-reduced", {"precool_level": "REDUCED"}),                       # H1
    ("precool-reduced+thr3", {"precool_level": "REDUCED", "occ_threshold": 3}),
    ("precool-reduced+thr8", {"precool_level": "REDUCED", "occ_threshold": 8}),
    ("earlyoff-from-reduced", {"earlyoff_from_reduced": True}),               # H2
    ("require-both-horizons", {"require_both_horizons": True}),               # H4
    ("blackout-18-22", {"precool_blackout": (18, 22)}),                       # D-08
    ("combo", {"occ_threshold": 3, "precool_level": "REDUCED",
               "require_both_horizons": True}),
]

PEAK_HOURS = {18, 19, 20, 21}  # D-05 peak window 18:00-22:00
PLANT_Q_ON = (-2.5, -1.75)  # scratch probe; -3.5 baseline comes from main sweep
BANDS = {"locked22-26": (22.0, 26.0), "wide21-27": (21.0, 27.0),
         "narrow23-25": (23.0, 25.0)}


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


def peak_share_18_22(frame):
    """Peak-window kWh share = kWh in 18:00-22:00 / total kWh."""
    hours = pd.to_datetime(frame["timestamp"]).dt.hour
    total = float((frame["power_kW"] / 60.0).sum())
    peak = float((frame.loc[hours.isin(PEAK_HOURS), "power_kW"] / 60.0).sum())
    return peak / total if total > 0 else float("nan")


def comfort_at_band(frame, t_min, t_max):
    """Occupied-weighted comfort at an overridden band (recompute, no rerun)."""
    lo, hi = cfg.COMFORT_T_MIN, cfg.COMFORT_T_MAX
    cfg.COMFORT_T_MIN, cfg.COMFORT_T_MAX = t_min, t_max
    try:
        weighted, weight_total = 0.0, 0
        for _, group in frame.groupby("room"):
            weight = int((group["occupancy"] > 0).sum())
            room_comfort = met.comfort_pct(group)
            if weight > 0 and not pd.isna(room_comfort):
                weight_total += weight
                weighted += room_comfort * weight
        return weighted / weight_total if weight_total else float("nan")
    finally:
        cfg.COMFORT_T_MIN, cfg.COMFORT_T_MAX = lo, hi


def main(argv=None):
    parser = argparse.ArgumentParser(description="C4 threshold tuning sweep")
    parser.add_argument("--scenarios", default="weekday,heatwave")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--out", default="tuning_sweep.csv")
    args = parser.parse_args(argv)
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    seeds = list(cfg.PAIRED_SEEDS[:args.seeds])

    # One frozen forecaster per timetable group (train once, never in loop).
    t0 = time.perf_counter()
    forecasters = {}
    for scenario in scenarios:
        group = cfg.SCENARIO_TABLE.get(scenario, "weekday")
        if group not in forecasters:
            forecasters[group], _ = build_frozen_forecaster(group)
    print(f"forecaster training: {time.perf_counter() - t0:.1f}s")

    # Timing gate: one C4-with run; >~5s cuts heatwave to 3 seeds.
    t0 = time.perf_counter()
    run_controller(PredictivePolicy(), scenarios[0], seeds[0], days=1,
                   forecast=forecasters[cfg.SCENARIO_TABLE.get(scenarios[0],
                                                               "weekday")])
    single_s = time.perf_counter() - t0
    print(f"single C4-with run: {single_s:.2f}s")
    heatwave_seeds = seeds
    if single_s > 5.0 and "heatwave" in scenarios:
        heatwave_seeds = seeds[:3]
        print("NOTE: per-run >5s, heatwave cut to 3 seeds (documented fallback)")

    rows, frames = [], {}
    for name, kwargs in CONFIGS:
        for scenario in scenarios:
            fc = forecasters[cfg.SCENARIO_TABLE.get(scenario, "weekday")]
            for seed in (heatwave_seeds if scenario == "heatwave" else seeds):
                frame, metrics = run_controller(
                    PredictivePolicy(**kwargs), scenario, seed, days=1,
                    forecast=fc)
                rows.append({"config": name, "scenario": scenario, "seed": seed,
                             "peak_share_18_22": peak_share_18_22(frame),
                             **metrics})
                frames[(name, scenario, seed)] = frame
    table = pd.DataFrame(rows)
    # Paired deltas vs stock C4 within (scenario, seed).
    stock = table[table["config"] == "stock"].set_index(["scenario", "seed"])
    table["energy_dkwh_vs_stock"] = table.apply(
        lambda r: r["energy_kwh"] - stock.loc[(r["scenario"], r["seed"])][
            "energy_kwh"], axis=1)
    table["cost_drs_vs_stock"] = table.apply(
        lambda r: r["cost_rs"] - stock.loc[(r["scenario"], r["seed"])][
            "cost_rs"], axis=1)
    table["co2_dkg_vs_stock"] = table.apply(
        lambda r: r["co2_kg"] - stock.loc[(r["scenario"], r["seed"])][
            "co2_kg"], axis=1)
    main_path = _out_path(args.out)
    table.to_csv(main_path, index=False)
    print(f"wrote {main_path} ({len(table)} rows)")

    # Probe 1: plant-size sensitivity (scratch override, restored in finally).
    plant_rows = []
    probe_configs = [("stock", {}), ("precool-reduced", {"precool_level": "REDUCED"}),
                     ("stock-off", None)]  # None = forecast-off ablation arm
    q_orig = cfg.Q_HVAC["ON"]
    try:
        for q_on in PLANT_Q_ON:
            cfg.Q_HVAC["ON"] = q_on
            for name, kwargs in probe_configs:
                fc = forecasters["weekday"]
                for seed in seeds:
                    policy = PredictivePolicy(**(kwargs or {}))
                    fc_arg = None if kwargs is None else fc
                    frame, metrics = run_controller(
                        policy, "weekday", seed, days=1, forecast=fc_arg)
                    plant_rows.append({"config": name, "plant_q_on": q_on,
                                       "scenario": "weekday", "seed": seed,
                                       **metrics})
    finally:
        cfg.Q_HVAC["ON"] = q_orig
    assert cfg.Q_HVAC["ON"] == -3.5  # physics restored, never committed
    plant_path = _out_path("tuning_sweep_plant.csv")
    pd.DataFrame(plant_rows).to_csv(plant_path, index=False)
    print(f"wrote {plant_path} ({len(plant_rows)} rows, physics restored)")

    # Probe 2: comfort-band recompute on saved frames (no reruns).
    band_rows = []
    for (name, scenario, seed), frame in frames.items():
        if name not in ("stock", "precool-reduced", "combo"):
            continue
        for band, (lo, hi) in BANDS.items():
            band_rows.append({"config": name, "scenario": scenario, "seed": seed,
                              "band": band,
                              "comfort_pct": comfort_at_band(frame, lo, hi)})
    band_path = _out_path("tuning_sweep_band.csv")
    pd.DataFrame(band_rows).to_csv(band_path, index=False)
    print(f"wrote {band_path} ({len(band_rows)} rows)")

    for scenario in scenarios:
        sub = table[table["scenario"] == scenario]
        base = sub[sub["config"] == "stock"]["energy_kwh"].mean()
        print(f"== {scenario} (stock {base:.3f} kWh) ==")
        for name, _ in CONFIGS:
            s = sub[sub["config"] == name]
            d = s["energy_dkwh_vs_stock"].mean()
            print(f"  {name:24s} dE={d:+.3f} kWh "
                  f"comfort={s['comfort_pct'].mean():.1f}% "
                  f"peak={s['peak_share_18_22'].mean():.3f}")
    return main_path


if __name__ == "__main__":
    main()
