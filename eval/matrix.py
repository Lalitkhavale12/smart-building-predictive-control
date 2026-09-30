"""Full evaluation matrix driver (Phase 5, plan 05-02, D-06/D-12).

Thin driver over ctrl.compare run_matrix/aggregate (extended, not forked):

  python eval/matrix.py --controllers c1,c2,c3,c4-with,c4-as-c3 \
      --scenarios weekday,weekend,heatwave,exam-day --seeds 5

Controllers {C1,C2,C3,C4-with,C4-as-C3} x scenarios {weekday, weekend,
heatwave, exam-day} x PAIRED_SEEDS 0-4 = 100 runs. Per-run telemetry CSVs
under results/full_matrix/<controller>/<scenario>/seedNN/telemetry.csv
(crash-resumable: existing CSVs re-read, not re-run). Headline = paired
saved-% over C3 (strongest baseline); vs-C1 kept as secondary column.
Every row carries energy_kwh, saved_pct_vs_c3, cost_rs (ToU), co2_kg
(hourly EF), comfort_pct (EVAL-02/CTL-06). exam-day resolves to the weekday
stub and is labeled "exam-day (stub=weekday)" in every table (T-05-06).

Forecaster choice is frozen regardless of any pending bake-off verdict:
one shared frozen forecaster per timetable group, fresh PredictivePolicy
per run (04-03 leakage fix). Writes constrained under results/full_matrix/.
"""

import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from ctrl.compare import aggregate, paired_ttest, run_matrix  # noqa: E402
from sim import config as cfg  # noqa: E402

RESULTS_ROOT = pathlib.Path("results/full_matrix")

DEFAULT_CONTROLLERS = ["c1", "c2", "c3", "c4-with", "c4-as-c3"]
DEFAULT_SCENARIOS = ["weekday", "weekend", "heatwave", "exam-day"]

# T-05-06: honest stub labeling in every table.
SCENARIO_LABELS = {
    "weekday": "weekday",
    "weekend": "weekend",
    "heatwave": "heatwave",
    "exam-day": "exam-day (stub=weekday)",
}


def parse_args(argv=None):
    from ctrl.compare import POLICY_FACTORIES

    parser = argparse.ArgumentParser(description="Full evaluation matrix")
    parser.add_argument("--controllers", default=",".join(DEFAULT_CONTROLLERS))
    parser.add_argument("--scenarios", default=",".join(DEFAULT_SCENARIOS))
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
    started = time.time()
    args, controllers, scenarios, seeds = parse_args(argv)
    out_root = pathlib.Path(args.out)
    per_run = run_matrix(controllers, scenarios, seeds, out_root)
    summary = aggregate(per_run, len(seeds), baselines=("c3", "c1"))
    summary["scenario_label"] = summary["scenario"].map(SCENARIO_LABELS)
    cols = (["controller", "scenario", "scenario_label", "n_seeds"]
            + [c for c in summary.columns if c not in
               ("controller", "scenario", "scenario_label", "n_seeds")])
    summary = summary[cols]
    summary_path = out_root / "summary.csv"
    summary.to_csv(summary_path, index=False, float_format="%.4f")
    for _, row in summary.iterrows():
        print(f"{row['controller']} {row['scenario_label']}: "
              f"{row['energy_kwh_mean']:.3f}+/-{row['energy_kwh_std']:.3f} kWh, "
              f"saved-vs-C3 {row['saved_pct_vs_c3_mean']:.1f}"
              f"+/-{row['saved_pct_vs_c3_std']:.1f}%, "
              f"cost Rs{row['cost_rs_mean']:.1f}, CO2 {row['co2_kg_mean']:.2f}kg, "
              f"comfort {row['comfort_pct_mean']:.1f}"
              f"+/-{row['comfort_pct_std']:.1f}% (n={int(row['n_seeds'])})")
    if "c3" in controllers and "c4-with" in controllers:
        for scenario in scenarios:
            try:
                import math as _math

                t, p = paired_ttest(per_run, scenario, "c4-with", "c3")
                if not _math.isfinite(t):
                    print(f"paired t-test c4-with vs c3 [{scenario}]: "
                          f"t non-finite (paired deltas constant across seeds) "
                          f"p={p:.4f} -> significant difference")
                else:
                    verdict = ("no significant difference" if p > 0.05
                               else "significant difference")
                    print(f"paired t-test c4-with vs c3 [{scenario}]: "
                          f"t={t:.3f} p={p:.4f} -> {verdict}")
            except Exception as exc:  # never fail the matrix on stats
                print(f"paired t-test c4-with vs c3 [{scenario}]: skipped ({exc})")
    elapsed = time.time() - started
    print(f"wrote {summary_path} ({len(per_run)} runs, {elapsed:.1f}s)")
    return summary_path


if __name__ == "__main__":
    main()
