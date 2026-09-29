"""Paired-seed comparison CLI (Phase 3, D-09/D-10/D-11/D-12).

  python ctrl/compare.py --controllers c1,c2,c3 --scenarios weekday,weekend,heatwave --seeds 5

Loops run_controller over the controller x scenario x seed matrix reusing
PAIRED_SEEDS identically per controller (paired design), writes one CSV per
run under results/comparison/<controller>/<scenario>/seedNN/telemetry.csv
(crash-resumable: existing CSVs are re-read, not re-run), then aggregates by
(controller, scenario) to mean+/-std (ddof=1, the summary.py convention) and
writes results/comparison/summary.csv. saved_pct is computed within the same
(scenario, seed) pair, then aggregated. Default scenarios exclude exam-day
(stub duplicates weekday — honest labeling); full matrix via --scenarios all.
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
}

DEFAULT_SCENARIOS = ["weekday", "weekend", "heatwave"]


def resolve_run_dir(out_root, controller, scenario, seed):
    """Constrain per-run output under results/comparison/ (reject traversal)."""
    for part in (controller, scenario):
        if ".." in pathlib.PurePath(part).parts:
            raise ValueError(f"path traversal rejected: {part!r}")
    root = (pathlib.Path.cwd() / RESULTS_ROOT).resolve()
    candidate = (pathlib.Path(out_root) / controller / scenario / f"seed{seed:02d}").resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"output must stay under results/comparison/, got {candidate}")
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
                    frame, metrics = run_controller(
                        POLICY_FACTORIES[controller](scenario), scenario, seed
                    )
                    run_dir.mkdir(parents=True, exist_ok=True)
                    frame.to_csv(csv_path, index=False, float_format="%.4f")
                per_run.append({
                    "controller": controller, "scenario": scenario, "seed": seed,
                    **metrics,
                })
    return per_run


def aggregate(per_run, n_seeds):
    """Per-(controller, scenario) mean+/-std; saved_pct paired within (scenario, seed)."""
    df = pd.DataFrame(per_run)
    c1_energy = {
        (r["scenario"], r["seed"]): r["energy_kwh"]
        for r in per_run if r["controller"] == "c1"
    }
    df["saved_pct"] = df.apply(
        lambda r: (
            100.0 * (c1_energy[(r["scenario"], r["seed"])] - r["energy_kwh"])
            / c1_energy[(r["scenario"], r["seed"])]
            if (r["scenario"], r["seed"]) in c1_energy and c1_energy[(r["scenario"], r["seed"])] > 0
            else (0.0 if r["controller"] == "c1" else float("nan"))
        ),
        axis=1,
    )
    rows = []
    for (controller, scenario), group in df.groupby(["controller", "scenario"]):
        means, stds = {}, {}
        for col in ("energy_kwh", "saved_pct", "cost_rs", "co2_kg", "comfort_pct"):
            vals = group[col].to_numpy(dtype=float)
            means[col] = float(np.mean(vals))
            stds[col] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        rows.append({
            "controller": controller, "scenario": scenario, "n_seeds": n_seeds,
            "energy_kwh_mean": means["energy_kwh"], "energy_kwh_std": stds["energy_kwh"],
            "saved_pct_vs_c1_mean": means["saved_pct"], "saved_pct_vs_c1_std": stds["saved_pct"],
            "cost_rs_mean": means["cost_rs"], "cost_rs_std": stds["cost_rs"],
            "co2_kg_mean": means["co2_kg"], "co2_kg_std": stds["co2_kg"],
            "comfort_pct_mean": means["comfort_pct"], "comfort_pct_std": stds["comfort_pct"],
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS).sort_values(
        ["scenario", "controller"]).reset_index(drop=True)


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
