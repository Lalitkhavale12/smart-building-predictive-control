"""One-command report (Phase 5, plan 05-03, D-10).

  python -m eval.report [--only g1 | --only g2,g3,g4,g5,g6]

Default run regenerates the forecaster holdout pred CSV if absent (frozen
forecaster — build_frozen_forecaster + holdout_pred_rows, never a retrain),
reuses matrix/sweep/ablation CSVs if present (re-runs only missing inputs
via eval/matrix.py + eval/sweep.py with 05-01/05-02 defaults — never
silently subsetting seeds), emits G1-G6 plus the G7 dashboard-screenshot
placeholder note file (.txt stub; screenshot itself is Phase 6, T-05-09),
and writes results/report_tables/ summary tables backing every figure.

Commit code, never CSVs (results/ is gitignored): a clean run from
committed code reproduces all artifacts.
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

import eval.figures as figs  # noqa: E402

PRED_CSV = pathlib.Path("results/report_pred_holdout.csv")
G7_STUB = figs.FIG_DIR / "fig_g7_dashboard_placeholder.txt"

G7_TEXT = """G7 dashboard screenshot — PLACEHOLDER (Phase 6).

The live Streamlit dashboard screenshot is a Phase-6 deliverable and is
deliberately NOT included here. This stub exists so the one-command report
build (`python -m eval.report`) never breaks on the missing 7th artifact.
No image file in this plan is a dashboard screenshot (T-05-09).
"""

GRAPH_KEYS = ("g1", "g2", "g3", "g4", "g5", "g6", "g7")


def ensure_pred_csv():
    """Regenerate the holdout pred CSV from the frozen forecaster if absent."""
    if PRED_CSV.exists():
        return PRED_CSV
    from ctrl.predictive import build_frozen_forecaster, holdout_pred_rows

    rows = []
    for group in ("weekday", "weekend"):
        forecaster, test_ticks = build_frozen_forecaster(group)
        rows.extend(holdout_pred_rows(forecaster, test_ticks, group))
    PRED_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(PRED_CSV, index=False)
    print(f"regenerated {PRED_CSV} ({len(rows)} rows, frozen forecaster)")
    return PRED_CSV


def ensure_inputs():
    """Re-run only missing matrix/sweep/ablation inputs with plan defaults."""
    missing = [p for p in ("results/full_matrix/summary.csv",
                           "results/tuning_sweep.csv",
                           "results/tuning_sweep_band.csv",
                           "results/ablation.csv",
                           "results/sensitivity.csv")
               if not pathlib.Path(p).exists()]
    if not missing:
        return
    print(f"missing inputs: {missing} — regenerating with plan defaults")
    if "results/full_matrix/summary.csv" in missing:
        from eval.matrix import main as matrix_main
        matrix_main(["--controllers", "c1,c2,c3,c4-with,c4-as-c3",
                     "--scenarios", "weekday,weekend,heatwave,exam-day",
                     "--seeds", "5"])
    if ("results/tuning_sweep.csv" in missing
            or "results/tuning_sweep_band.csv" in missing):
        from eval.sweep import main as sweep_main
        sweep_main(["--scenarios", "weekday,heatwave", "--seeds", "5"])
    if "results/ablation.csv" in missing:
        from eval.ablate import main as ablate_main
        ablate_main([])
    if "results/sensitivity.csv" in missing:
        from eval.sensitivity import main as sensitivity_main
        sensitivity_main([])


def write_summary_tables():
    """Headline + shifting + ablation/sensitivity tables backing every figure."""
    figs.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    summary = pd.read_csv(figs.MATRIX_SUMMARY)
    # Headline savings-over-C3 with std + comfort.
    summary.to_csv(figs.TABLES_DIR / "headline_savings_over_c3.csv", index=False)
    # Shifting metric (CTL-05, honest accounting): peak-window kWh share +
    # Rs + CO2 deltas C4-C3 per seed. Measured outcome is less-energy-
    # everywhere, NOT load moved off-peak (see SHIFTING-FINDING.md): do not
    # claim shifting unless d_peak_share is negative with p<0.05.
    from eval.sweep import peak_share_18_22

    from ctrl.harness import compute_metrics

    rows = []
    for scenario in ("weekday", "weekend", "heatwave"):
        for seed in (0, 1, 2, 3, 4):
            frames, metrics = {}, {}
            for c in ("c3", "c4-with"):
                path = (figs.MATRIX_ROOT / c / scenario / f"seed{seed:02d}"
                        / "telemetry.csv")
                frame = pd.read_csv(path)
                frames[c] = frame
                metrics[c] = compute_metrics(frame)
            rows.append({
                "scenario": scenario, "seed": seed,
                "c3_peak_share_18_22": peak_share_18_22(frames["c3"]),
                "c4_peak_share_18_22": peak_share_18_22(frames["c4-with"]),
                "d_peak_share": (peak_share_18_22(frames["c4-with"])
                                 - peak_share_18_22(frames["c3"])),
                "d_cost_rs": metrics["c4-with"]["cost_rs"] - metrics["c3"]["cost_rs"],
                "d_co2_kg": metrics["c4-with"]["co2_kg"] - metrics["c3"]["co2_kg"],
                "d_energy_kwh": (metrics["c4-with"]["energy_kwh"]
                                 - metrics["c3"]["energy_kwh"]),
            })
    pd.DataFrame(rows).to_csv(figs.TABLES_DIR / "shifting_peak_share.csv", index=False)
    # Ablation + sensitivity tables (copies backing G6 + D-13).
    for name in ("ablation.csv", "sensitivity.csv"):
        src = pathlib.Path("results") / name
        if src.exists():
            pd.read_csv(src).to_csv(figs.TABLES_DIR / f"{src.stem}.csv", index=False)


def run_graph(key):
    if key == "g1":
        return figs.fig_g1()
    if key == "g2":
        return figs.fig_g2()
    if key == "g3":
        return figs.fig_g3()
    if key == "g4":
        return figs.fig_g4()
    if key == "g5":
        return figs.fig_g5(ensure_pred_csv())
    if key == "g6":
        return figs.fig_g6()
    if key == "g7":
        figs.FIG_DIR.mkdir(parents=True, exist_ok=True)
        G7_STUB.write_text(G7_TEXT)
        return G7_STUB
    raise ValueError(f"unknown graph key: {key!r}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="One-command report (G1-G7)")
    parser.add_argument("--only", default="",
                        help="comma-separated subset, e.g. 'g1' or 'g2,g3,g4,g5,g6'")
    args = parser.parse_args(argv)
    if not args.only:
        return list(GRAPH_KEYS)
    keys = [k.strip().lower() for k in args.only.split(",") if k.strip()]
    unknown = set(keys) - set(GRAPH_KEYS)
    if unknown:
        parser.error(f"unknown graphs: {sorted(unknown)} (choose from {list(GRAPH_KEYS)})")
    return keys


def main(argv=None):
    keys = parse_args(argv)
    ensure_inputs()
    if "g5" in keys or keys == list(GRAPH_KEYS):
        ensure_pred_csv()
    made = [run_graph(k) for k in keys]
    if keys == list(GRAPH_KEYS):
        write_summary_tables()
    for path in made:
        print(f"wrote {path}")
    return made


if __name__ == "__main__":
    main()
