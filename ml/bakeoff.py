"""Fixed-budget bake-off: persistence + RF + HistGB + LSTM (Phase 4, FOR-03).

Search spaces (locked, D-03/F3 — auditable, equal budgets, at most 12 configs
each; never all-defaults vs tuned):

- RF: ``ml.forecast.RF_SEARCH`` (6 configs, scaler+RF Pipeline).
- HistGB: ``ml.forecast.HGB_SEARCH`` (6 configs, scaler+HistGB Pipeline).
- LSTM: ``ml.lstm.LSTM_CONFIG`` (ONE config per target: 1 layer, 32 units,
  <=50 epochs with early stopping, 60-min windows — no architecture search,
  D-04). The single config IS the declared budget.

Protocol (D-05/F3): identical 04-01 splits, separate MAE/RMSE/R2 tables per
30-min and 60-min horizon — never averaged across horizons. Persistence
(repeat-last) appears in every row set.

Tie rule (locked, D-03): LSTM wins by under 3% with overlapping std across
PAIRED_SEEDS [0..4] means ship HistGB and report LSTM as reference only.

TF is imported only inside ``ml.lstm`` (function-local); a broken TF env
reports the LSTM row as skipped and never blocks the RF/HistGB verdict
(threat T-04-SC).
"""

from __future__ import annotations

import csv
import logging
import os

import numpy as np

from ml import forecast as fc
from sim import config as cfg

logger = logging.getLogger(__name__)

HORIZONS = fc.HORIZONS
MODELS = ("persistence", "rf", "histgb", "lstm")
PAIRED_SEEDS = list(cfg.PAIRED_SEEDS)
TIE_PCT = 0.03  # LSTM must beat HistGB by >=3% with non-overlapping std
DEFAULT_CSV = os.path.join("results", "bakeoff.csv")


def tie_break(lstm_mean, lstm_std, hgb_mean, hgb_std, threshold=TIE_PCT):
    """Locked tie rule → (verdict, reason). Lower metric is better (MAE/RMSE).

    - LSTM clearly better (>=threshold gain AND non-overlapping std):
      ship lstm.
    - Otherwise (tie, overlap, or HistGB outright better): ship histgb,
      LSTM reported as reference only.
    """
    if not (np.isfinite(lstm_mean) and np.isfinite(hgb_mean)):
        return ("ship: histgb",
                "lstm unavailable (reference-skipped); histgb ships by default")
    gain = (hgb_mean - lstm_mean) / hgb_mean if hgb_mean else 0.0
    overlap = (lstm_mean + lstm_std) >= (hgb_mean - hgb_std)
    if gain >= threshold and not overlap:
        return ("ship: lstm",
                f"lstm beats histgb by {gain:.1%} with non-overlapping std")
    if gain < threshold and overlap:
        return ("ship: histgb",
                f"tie: lstm gain {gain:.1%} < {threshold:.0%} with overlapping "
                "std → prefer simpler (reference-only lstm)")
    if gain < 0:
        return ("ship: histgb", "histgb outright better; lstm reference only")
    return ("ship: histgb",
            f"marginal lstm gain {gain:.1%} with overlapping std → histgb")


def _lstm_row(df, room, horizon, target, lstm_kwargs):
    """One LSTM row on identical splits; skipped (never fatal) without TF."""
    try:
        from ml import lstm as lstm_mod  # noqa: PLC0415 — isolated import

        params = {**lstm_mod.LSTM_CONFIG, **(lstm_kwargs or {})}
        train_df, test_df = fc.chronological_split(df)
        if target == "occupancy":
            tr = fc.build_occupancy_windows(train_df, room, horizon)
            te = fc.build_occupancy_windows(test_df, room, horizon)
            features = fc.OCC_FEATURES
        else:
            tr = fc.build_demand_windows(train_df, horizon)
            te = fc.build_demand_windows(test_df, horizon)
            features = fc.DEM_FEATURES
        Xtr, ytr = lstm_mod.dataset_from_windows(tr, features, window=params["window"])
        Xte, yte = lstm_mod.dataset_from_windows(te, features, window=params["window"])
        art = lstm_mod.train_lstm(Xtr, ytr, units=params["units"],
                                  layers=params["layers"], epochs=params["epochs"],
                                  patience=params["patience"],
                                  batch_size=params["batch_size"],
                                  seed=lstm_mod.DEFAULT_SEED)
        preds = lstm_mod.predict_lstm(art, Xte)
        row = fc.score_metrics(yte, preds)
        row["status"] = "ok"
        return row
    except Exception as exc:  # TF churn must never block HistGB (T-04-SC)
        logger.warning("lstm skipped: %s", exc)
        return {"mae": float("nan"), "rmse": float("nan"), "r2": float("nan"),
                "status": f"skipped: {exc}"}


def evaluate_models(df, room, horizon, target="occupancy", search=None, lstm_kwargs=None):
    """Per-horizon table with all four model rows (never cross-horizon)."""
    table = fc.evaluate_horizon(df, room, horizon, target=target, search=search)
    table["lstm"] = _lstm_row(df, room, horizon, target, lstm_kwargs)
    return table


def run_bakeoff(frames, room, target="occupancy", search=None, lstm_kwargs=None):
    """Bake-off over PAIRED_SEEDS frames → per-horizon tables + tie verdicts.

    ``frames`` maps seed → telemetry frame (same scenario, C1 data for
    demand). Returns ``{horizon: {"rows": {model: {mean,std,n}}, "verdict",
    "reason"}}`` with mean±std over seeds (nan-aware: skipped LSTM rows are
    excluded from its mean).
    """
    out = {}
    for horizon in HORIZONS:
        per_model = {m: [] for m in MODELS}
        for seed in PAIRED_SEEDS:
            table = evaluate_models(frames[seed], room, horizon,
                                    target=target, search=search,
                                    lstm_kwargs=lstm_kwargs)
            for model in MODELS:
                per_model[model].append(table[model]["mae"])
        rows = {}
        for model in MODELS:
            vals = np.array(per_model[model], dtype=float)
            finite = vals[np.isfinite(vals)]
            rows[model] = {
                "mean": float(np.mean(finite)) if len(finite) else float("nan"),
                "std": float(np.std(finite)) if len(finite) else float("nan"),
                "n": int(len(finite)),
            }
        verdict, reason = tie_break(rows["lstm"]["mean"], rows["lstm"]["std"],
                                    rows["histgb"]["mean"], rows["histgb"]["std"])
        out[horizon] = {"rows": rows, "verdict": verdict, "reason": reason}
    return out


def format_bakeoff(tables):
    """Render per-horizon tables (with verdicts) as a stdout table."""
    lines = []
    for horizon in sorted(tables):
        lines.append(f"horizon={horizon}min")
        for model in MODELS:
            r = tables[horizon]["rows"][model]
            lines.append(f"  {model:12s} MAE={r['mean']:.4f} ±{r['std']:.4f} (n={r['n']})")
        lines.append(f"  verdict: {tables[horizon]['verdict']} — {tables[horizon]['reason']}")
    return "\n".join(lines)


def save_csv(tables, path=DEFAULT_CSV):
    """Emit results CSV (results/ is gitignored)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["horizon_min", "model", "mae_mean", "mae_std", "n",
                         "verdict", "reason"])
        for horizon in sorted(tables):
            for model in MODELS:
                r = tables[horizon]["rows"][model]
                writer.writerow([horizon, model, f"{r['mean']:.6f}",
                                 f"{r['std']:.6f}", r["n"],
                                 tables[horizon]["verdict"],
                                 tables[horizon]["reason"]])
    return path


def main(days=2, scenario="weekday", room="classroom_A", target="occupancy"):
    """Synthetic-data bake-off entry point (tiny demo budget)."""
    from ctrl.baselines import FixedSchedulePolicy
    from ctrl.harness import run_controller

    frames = {}
    for seed in PAIRED_SEEDS:
        frame, _ = run_controller(FixedSchedulePolicy(scenario=scenario),
                                  scenario, seed, days=days)
        frames[seed] = frame
    tiny_lstm = {"units": 8, "layers": 1, "epochs": 5, "patience": 2}
    tables = run_bakeoff(frames, room, target=target, lstm_kwargs=tiny_lstm)
    print(format_bakeoff(tables))
    path = save_csv(tables)
    print(f"wrote {path}")
    return tables


if __name__ == "__main__":
    main()
