"""Forecaster leakage-guard + baseline tests (Phase 4, FOR-01/FOR-02, D-07)."""

import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from ctrl.baselines import FixedSchedulePolicy
from ctrl.harness import run_controller
from ml import forecast as fc


def _frame(days=2, seed=0):
    frame, _ = run_controller(
        FixedSchedulePolicy(scenario="weekday"), "weekday", seed, days=days
    )
    return frame


def test_no_time_leakage():
    """Layer-1 guard: train max-time < test min-time; windows never straddle."""
    frame = _frame()
    train_df, test_df = fc.chronological_split(frame)
    assert train_df["timestamp"].max() < test_df["timestamp"].min()
    for horizon in fc.HORIZONS:
        train_w = fc.build_occupancy_windows(train_df, "classroom_A", horizon)
        test_w = fc.build_occupancy_windows(test_df, "classroom_A", horizon)
        # Every train window row (incl. its +H target time) precedes test data.
        assert train_w["timestamp"].max() < test_w["timestamp"].min()
        dem_train = fc.build_demand_windows(train_df, horizon)
        dem_test = fc.build_demand_windows(test_df, horizon)
        assert dem_train["timestamp"].max() < dem_test["timestamp"].min()


def test_walkforward_chronology():
    """Per-fold: all training timestamps precede all test timestamps."""
    frame = _frame()
    _, test_df = fc.chronological_split(frame)
    for horizon in fc.HORIZONS:
        windows = fc.build_occupancy_windows(test_df, "classroom_A", horizon)
        ts = pd.to_datetime(windows["timestamp"])
        tss = TimeSeriesSplit(n_splits=4, gap=horizon)
        folds = list(tss.split(windows))
        assert len(folds) == 4
        for train_idx, test_idx in folds:
            assert ts.iloc[train_idx].max() < ts.iloc[test_idx].min()
            # Gap separates train end from test start by >= horizon steps.
            assert test_idx.min() - train_idx.max() > horizon


def test_persistence_metrics_present():
    """Persistence baseline scores on the holdout for every horizon."""
    frame = _frame()
    _, test_df = fc.chronological_split(frame)
    for horizon in fc.HORIZONS:
        occ = fc.build_occupancy_windows(test_df, "classroom_A", horizon)
        metrics = fc.score_metrics(occ[fc.TARGET_COL], fc.persistence_predict(occ))
        assert set(metrics) == {"mae", "rmse", "r2"}
        assert metrics["mae"] >= 0 and metrics["rmse"] >= 0
