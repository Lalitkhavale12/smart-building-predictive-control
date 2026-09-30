"""Paired-seed comparison CLI (Phase 3, D-09/D-10/D-11/D-12).

  python ctrl/compare.py --controllers c1,c2,c3 --scenarios weekday,weekend,heatwave --seeds 5

Loops run_controller over the controller x scenario x seed matrix reusing
PAIRED_SEEDS identically per controller (paired design), writes one CSV per
run under results/comparison/<controller>/<scenario>/seedNN/telemetry.csv
(crash-resumable: existing CSVs are re-read, not re-run), then aggregates by
(controller, scenario) to mean+/-std (ddof=1, the summary.py convention) and
writes results/comparison/summary.csv. saved_pct is computed within the same
(scenario, seed) pair, then aggregated. Default scenarios exclude exam-day
(dense exam timetable runs in the full matrix); full matrix via --scenarios all.
All tables carry the comfort column; the CLI prints mean+/-std only, never a
bare %. Writes are constrained under results/comparison/ (.. rejected).
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ctrl.baselines import (  # noqa: E402
    FixedSchedulePolicy,
    OccupancyRulePolicy,
    SetbackPolicy,
)
from ctrl.harness import compute_metrics, run_controller  # noqa: E402
from sim import config as cfg  # noqa: E402

RESULTS_ROOT = pathlib.Path("results/comparison")

SUMMARY_COLUMNS = [
    "controller", "scenario", "n_seeds",
    "energy_kwh_mean", "energy_kwh_std",
    "saved_pct_vs_c1_mean", "saved_pct_vs_c1_std",
    "cost_rs_mean", "cost_rs_std",
    "co2_kg_mean", "co2_kg_std",
    "comfort_pct_mean", "comfort_pct_std",
]

POLICY_FACTORIES = {
    "c1": lambda scenario: FixedSchedulePolicy(scenario=scenario),
    "c2": lambda scenario: OccupancyRulePolicy(),
    "c3": lambda scenario: SetbackPolicy(),
    "c4-with": lambda scenario: _predictive_policy(),
    "c4-as-c3": lambda scenario: _predictive_policy(),
}

# Controllers whose runs receive the shared frozen forecaster (forecast arm).
# c4-as-c3 deliberately gets forecast=None -> degrades to C3 exactly
# (predictive.py fallback) — the forecast-off ablation arm.
FORECAST_ARMS = {"c4-with"}

_FORECASTERS = {}


def _predictive_policy():
    """Fresh PredictivePolicy per run (04-03 leakage fix) with the shipped
    05-01 defaults (occ_threshold=8, precool_level=REDUCED)."""
    from ctrl.predictive import PredictivePolicy

    return PredictivePolicy()


def forecaster_for(scenario):
    """Shared frozen forecaster per timetable group (train once, never in the
    loop — T-05-04). Heatwave reuses the weekday forecaster; exam-day falls
    back to it (own timetable, pre-wave-B conservative choice)."""
    from ctrl.predictive import build_frozen_forecaster

    group = cfg.SCENARIO_TABLE.get(scenario, "weekday")
    key = group if group in ("weekday", "weekend") else "weekday"
    if key not in _FORECASTERS:
        forecaster, _ = build_frozen_forecaster(key)
        _FORECASTERS[key] = forecaster
    return _FORECASTERS[key]

DEFAULT_SCENARIOS = ["weekday", "weekend", "heatwave"]


def resolve_run_dir(out_root, controller, scenario, seed):
    """Constrain per-run output under out_root (reject traversal)."""
    for part in (controller, scenario):
        if ".." in pathlib.PurePath(part).parts:
            raise ValueError(f"path traversal rejected: {part!r}")
    root = (pathlib.Path.cwd() / out_root).resolve()
    candidate = (pathlib.Path(out_root) / controller / scenario / f"seed{seed:02d}").resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"output must stay under {out_root}/, got {candidate}")
    return candidate


def run_matrix(controllers, scenarios, seeds, out_root=RESULTS_ROOT):
    """Run the matrix → list of per-run dicts (controller, scenario, seed, metrics)."""
    per_run = []
    for controller in controllers:
        for scenario in scenarios:
            for seed in seeds:
                run_dir = resolve_run_dir(out_root, controller, scenario, seed)
                csv_path = run_dir / "telemetry.csv"
                if csv_path.exists():
                    frame = pd.read_csv(csv_path)
                    metrics = compute_metrics(frame)
                else:
                    policy = POLICY_FACTORIES[controller](scenario)
                    forecast = (
                        forecaster_for(scenario)
                        if controller in FORECAST_ARMS else None
                    )
                    frame, metrics = run_controller(
                        policy, scenario, seed, forecast=forecast
                    )
                    run_dir.mkdir(parents=True, exist_ok=True)
                    frame.to_csv(csv_path, index=False, float_format="%.4f")
                per_run.append({
                    "controller": controller, "scenario": scenario, "seed": seed,
                    **metrics,
                })
    return per_run


def summary_columns(baselines=("c1",)):
    """Summary column order for the given baseline controllers."""
    cols = ["controller", "scenario", "n_seeds",
            "energy_kwh_mean", "energy_kwh_std"]
    for b in baselines:
        cols += [f"saved_pct_vs_{b}_mean", f"saved_pct_vs_{b}_std"]
    cols += ["cost_rs_mean", "cost_rs_std",
             "co2_kg_mean", "co2_kg_std",
             "comfort_pct_mean", "comfort_pct_std"]
    return cols


def aggregate(per_run, n_seeds, baselines=("c1",)):
    """Per-(controller, scenario) mean+/-std; saved_pct paired within
    (scenario, seed) vs each baseline controller, then aggregated (D-12:
    never difference-of-means). Default baselines=("c1",) reproduces the
    Phase-3 summary exactly; Phase-5 passes ("c3", "c1")."""
    if isinstance(baselines, str):
        baselines = (baselines,)
    df = pd.DataFrame(per_run)
    base_energy = {
        b: {(r["scenario"], r["seed"]): r["energy_kwh"]
            for r in per_run if r["controller"] == b}
        for b in baselines
    }
    for b in baselines:
        be = base_energy[b]
        df[f"saved_pct_vs_{b}"] = df.apply(
            lambda r, be=be, b=b: (
                100.0 * (be[(r["scenario"], r["seed"])] - r["energy_kwh"])
                / be[(r["scenario"], r["seed"])]
                if (r["scenario"], r["seed"]) in be and be[(r["scenario"], r["seed"])] > 0
                else (0.0 if r["controller"] == b else float("nan"))
            ),
            axis=1,
        )
    rows = []
    for (controller, scenario), group in df.groupby(["controller", "scenario"]):
        row = {"controller": controller, "scenario": scenario, "n_seeds": n_seeds}
        for col in ("energy_kwh", "cost_rs", "co2_kg", "comfort_pct"):
            vals = group[col].to_numpy(dtype=float)
            row[f"{col}_mean"] = float(np.mean(vals))
            row[f"{col}_std"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        for b in baselines:
            vals = group[f"saved_pct_vs_{b}"].to_numpy(dtype=float)
            if np.isnan(vals).all():
                row[f"saved_pct_vs_{b}_mean"] = float("nan")
                row[f"saved_pct_vs_{b}_std"] = float("nan")
            else:
                row[f"saved_pct_vs_{b}_mean"] = float(np.nanmean(vals))
                row[f"saved_pct_vs_{b}_std"] = (
                    float(np.nanstd(vals, ddof=1)) if len(vals) > 1 else 0.0)
        rows.append(row)
    return pd.DataFrame(rows, columns=summary_columns(baselines)).sort_values(
        ["scenario", "controller"]).reset_index(drop=True)


def paired_ttest(per_run, scenario, a, b, metric="energy_kwh"):
    """Paired t-test of controller a vs b within one scenario (paired seeds).

    Returns (t, p); p > 0.05 is reported as no-significant-difference (D-12).
    """
    from scipy import stats as _stats

    df = pd.DataFrame(per_run)
    da = df[(df["scenario"] == scenario) & (df["controller"] == a)]
    db = df[(df["scenario"] == scenario) & (df["controller"] == b)]
    sa = da.set_index("seed")[metric]
    sb = db.set_index("seed")[metric]
    common = sa.index.intersection(sb.index)
    t, p = _stats.ttest_rel(sa.loc[common], sb.loc[common])
    return float(t), float(p)


def render_figure(controllers, out_root, path):
    """24h profile: weekday seed 0 hourly-mean total power (C1/C2/C3) + occupancy shade."""
    plt.figure(figsize=(10, 5))
    ax = plt.gca()
    occ_series = None
    for controller in controllers:
        csv_path = pathlib.Path(out_root) / controller / "weekday" / "seed00" / "telemetry.csv"
        frame = pd.read_csv(csv_path)
        frame["ts"] = pd.to_datetime(frame["timestamp"])
        per_min = frame.groupby("ts").agg({"power_kW": "sum", "occupancy": "sum"})
        per_min["hour"] = per_min.index.hour + per_min.index.minute / 60.0
        hourly = per_min.groupby(per_min.index.hour).agg({"power_kW": "mean", "occupancy": "mean"})
        ax.plot(hourly.index + 0.5, hourly["power_kW"], label=controller.upper(), linewidth=2.0)
        if occ_series is None:
            occ_series = hourly["occupancy"]
    ax2 = ax.twinx()
    ax2.fill_between(occ_series.index + 0.5, occ_series, color="lightgray", alpha=0.6,
                     step="mid", label="occupancy")
    ax.set_xlabel("hour of day")
    ax.set_ylabel("total building power [kW]")
    ax2.set_ylabel("total occupancy [persons]")
    ax.set_title("24h building power profile, weekday seed 0 (hourly mean)")
    ax.set_xlim(0, 24)
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="upper right")
    plt.tight_layout()
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Paired-seed baseline comparison")
    parser.add_argument("--controllers", default="c1,c2,c3")
    parser.add_argument("--scenarios", default="weekday,weekend,heatwave")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--out", default=str(RESULTS_ROOT))
    args = parser.parse_args(argv)
    controllers = [c.strip() for c in args.controllers.split(",") if c.strip()]
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    if scenarios == ["all"]:
        scenarios = list(cfg.SCENARIOS)
    unknown = set(controllers) - set(POLICY_FACTORIES)
    if unknown:
        parser.error(f"unknown controllers: {sorted(unknown)}")
    unknown = set(scenarios) - set(cfg.SCENARIOS)
    if unknown:
        parser.error(f"unknown scenarios: {sorted(unknown)}")
    if not 1 <= args.seeds <= len(cfg.PAIRED_SEEDS):
        parser.error(f"--seeds must be 1..{len(cfg.PAIRED_SEEDS)}")
    return args, controllers, scenarios, list(cfg.PAIRED_SEEDS[:args.seeds])


def main(argv=None):
    args, controllers, scenarios, seeds = parse_args(argv)
    out_root = pathlib.Path(args.out)
    per_run = run_matrix(controllers, scenarios, seeds, out_root)
    summary = aggregate(per_run, len(seeds))
    summary_path = out_root / "summary.csv"
    summary.to_csv(summary_path, index=False, float_format="%.4f")
    fig_path = None
    if "weekday" in scenarios and all(
            (out_root / c / "weekday" / "seed00" / "telemetry.csv").exists()
            for c in controllers):
        fig_path = render_figure(controllers, out_root, out_root / "fig_24h_profile.png")
    for _, row in summary.iterrows():
        print(f"{row['controller']} {row['scenario']}: "
              f"{row['energy_kwh_mean']:.3f}+/-{row['energy_kwh_std']:.3f} kWh, "
              f"saved {row['saved_pct_vs_c1_mean']:.1f}+/-{row['saved_pct_vs_c1_std']:.1f}%, "
              f"comfort {row['comfort_pct_mean']:.1f}+/-{row['comfort_pct_std']:.1f}%")
    print(f"wrote {summary_path}" + (f" + {fig_path}" if fig_path else ""))
    return summary_path


if __name__ == "__main__":
    main()
