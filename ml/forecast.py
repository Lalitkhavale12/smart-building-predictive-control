"""Walk-forward occupancy + demand forecaster (Phase 4, FOR-01/FOR-02).

Leakage protocol (D-06): chronological split by timestamp BEFORE windowing,
windows built strictly inside each partition, scalers fit on train only,
walk-forward evaluation via ``TimeSeriesSplit(n_splits=4, gap=horizon)``.

Demand-target coupling note (research Q3): building-total ``power_kW``
depends on which controller produced the telemetry (control-feedback
coupling). Demand models are therefore trained on C1-schedule
(``FixedSchedulePolicy``) data only, and the coupling is documented rather
than hidden. Occupancy forecasts — C4's primary input — are unaffected by
this choice because occupancy is controller-independent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

try:  # sklearn >= 1.4 preferred spelling; MSE-sqrt fallback otherwise
    from sklearn.metrics import root_mean_squared_error as _rmse_fn
except ImportError:  # pragma: no cover

    def _rmse_fn(y_true, y_pred):
        return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


HORIZONS = (30, 60)
FEATURE_LAGS = (5, 15, 30, 60)
TRAIN_FRAC = 0.7

TARGET_COL = "y_target"
NOW_COL = "y_now"

# Lagged telemetry columns. power_kW lags are NEVER features for occupancy
# targets (proxy-for-outcome leakage: HVAC power is a consequence of
# occupancy+control, not a predictor of it).
OCC_LAG_COLS = ("occupancy", "T_in_C", "T_out_C", "RH_pct")
DEM_LAG_COLS = ("power_total_kW", "T_in_mean_C", "T_out_C", "RH_mean_pct", "occ_total")
CALENDAR_COLS = ("tod_sin", "tod_cos", "is_weekend")

OCC_FEATURES = (
    [f"{c}_lag{lag}" for lag in FEATURE_LAGS for c in OCC_LAG_COLS] + list(CALENDAR_COLS)
)
DEM_FEATURES = (
    [f"{c}_lag{lag}" for lag in FEATURE_LAGS for c in DEM_LAG_COLS] + list(CALENDAR_COLS)
)


def chronological_split(df, train_frac=TRAIN_FRAC):
    """Split on timestamp BEFORE windowing; train max < test min guaranteed."""
    if df.empty:
        raise ValueError("chronological_split: empty frame")
    if df["timestamp"].isna().any():
        raise ValueError("chronological_split: NaN timestamps fail loudly, never imputed")
    work = df.assign(_ts=pd.to_datetime(df["timestamp"])).sort_values("_ts").reset_index(drop=True)
    ts = work["_ts"]
    days = ts.dt.normalize().drop_duplicates().sort_values().to_numpy()
    if len(days) > 1:  # multi-day: cut on whole-day boundaries
        n_train_days = max(1, min(len(days) - 1, round(len(days) * train_frac)))
        cut = ts[ts.dt.normalize() <= days[n_train_days - 1]].max()
    else:  # single-day: quantile cut on the sorted timeline
        cut = ts.quantile(train_frac)
    train = work[ts <= cut].drop(columns="_ts").reset_index(drop=True)
    test = work[ts > cut].drop(columns="_ts").reset_index(drop=True)
    if train.empty or test.empty:
        raise ValueError("chronological_split: split left a partition empty")
    return train, test


def _add_calendar(frame, ts):
    minute_of_day = ts.dt.hour * 60 + ts.dt.minute
    frame["tod_sin"] = np.sin(2 * np.pi * minute_of_day / 1440.0)
    frame["tod_cos"] = np.cos(2 * np.pi * minute_of_day / 1440.0)
    frame["is_weekend"] = (ts.dt.dayofweek >= 5).astype(int)
    return frame


def build_occupancy_windows(df, room, horizon):
    """Lag features + occupancy(t+H) target for one room, built inside one partition."""
    sub = df[df["room"] == room].copy()
    if sub.empty:
        raise ValueError(f"build_occupancy_windows: no rows for room {room!r}")
    sub["_ts"] = pd.to_datetime(sub["timestamp"])
    sub = sub.sort_values("_ts").reset_index(drop=True)
    feats = _add_calendar(pd.DataFrame(index=sub.index), sub["_ts"])
    for lag in FEATURE_LAGS:
        for col in OCC_LAG_COLS:
            feats[f"{col}_lag{lag}"] = sub[col].shift(lag)
    feats["timestamp"] = sub["_ts"]
    feats[TARGET_COL] = sub["occupancy"].shift(-horizon).astype(float)
    feats[NOW_COL] = sub["occupancy"].astype(float)
    return feats.dropna().reset_index(drop=True)


def build_demand_windows(df, horizon):
    """Lag features + building-total power_kW(t+H) target, inside one partition."""
    agg = (
        df.assign(_ts=pd.to_datetime(df["timestamp"]))
        .groupby("_ts", as_index=False)
        .agg(
            power_total_kW=("power_kW", "sum"),
            T_in_mean_C=("T_in_C", "mean"),
            T_out_C=("T_out_C", "first"),
            RH_mean_pct=("RH_pct", "mean"),
            occ_total=("occupancy", "sum"),
        )
        .sort_values("_ts")
        .reset_index(drop=True)
    )
    feats = _add_calendar(pd.DataFrame(index=agg.index), agg["_ts"])
    for lag in FEATURE_LAGS:
        for col in DEM_LAG_COLS:
            feats[f"{col}_lag{lag}"] = agg[col].shift(lag)
    feats["timestamp"] = agg["_ts"]
    feats[TARGET_COL] = agg["power_total_kW"].shift(-horizon).astype(float)
    feats[NOW_COL] = agg["power_total_kW"].astype(float)
    return feats.dropna().reset_index(drop=True)


def persistence_predict(frame):
    """Repeat-last baseline: yhat(t+H) = y(t). No training."""
    return frame[NOW_COL].to_numpy(dtype=float)


def score_metrics(y_true, y_pred):
    """MAE/RMSE/R2 for one prediction vector."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(_rmse_fn(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def format_table(tables):
    """Render {horizon: {model: metrics}} as a text metrics table."""
    lines = []
    for horizon in sorted(tables):
        lines.append(f"horizon={horizon}min")
        for model in ("persistence", "rf", "histgb"):
            if model not in tables[horizon]:
                continue
            m = tables[horizon][model]
            lines.append(
                f"  {model:12s} MAE={m['mae']:.4f} RMSE={m['rmse']:.4f} R2={m['r2']:.4f}"
            )
    return "\n".join(lines)


def demo(days=2, seed=0):
    """Tracer demo: persistence metrics on C1-schedule synthetic telemetry."""
    from ctrl.baselines import FixedSchedulePolicy
    from ctrl.harness import run_controller

    frame, _ = run_controller(FixedSchedulePolicy(scenario="weekday"), "weekday", seed, days=days)
    tables = {}
    for horizon in HORIZONS:
        train_df, test_df = chronological_split(frame)
        occ_test = build_occupancy_windows(test_df, "classroom_A", horizon)
        dem_test = build_demand_windows(test_df, horizon)
        tables[horizon] = {
            "persistence": score_metrics(
                occ_test[TARGET_COL], persistence_predict(occ_test)
            ),
            "persistence_demand": score_metrics(
                dem_test[TARGET_COL], persistence_predict(dem_test)
            ),
        }
    # Collapse to one persistence row per horizon for the tracer table.
    tracer = {
        h: {"persistence": tables[h]["persistence"]} for h in tables
    }
    print(format_table(tracer))
    return tables


if __name__ == "__main__":
    demo()
