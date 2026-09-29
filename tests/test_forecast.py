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


TINY_SEARCH = {
    "rf": [{"reg__n_estimators": [10], "reg__max_depth": [4], "reg__min_samples_leaf": [2]}],
    "histgb": [{"reg__max_iter": [10], "reg__max_depth": [3], "reg__learning_rate": [0.1]}],
}


def test_persistence_baseline_present():
    """Every results table carries persistence MAE/RMSE/R2 next to RF/HistGB."""
    frame = _frame()
    for horizon in fc.HORIZONS:
        for target in ("occupancy", "demand"):
            table = fc.evaluate_horizon(
                frame, "classroom_A", horizon, target=target, search=TINY_SEARCH
            )
            assert set(table) == {"persistence", "rf", "histgb"}
            for row in table.values():
                assert set(row) == {"mae", "rmse", "r2"}


def test_search_budget_fixed():
    """Search spaces are committed literals (<=12 configs) on a scaler Pipeline."""
    import inspect

    for space in (fc.RF_SEARCH, fc.HGB_SEARCH):
        assert isinstance(space, list) and 1 <= len(space) <= 12
        assert all(isinstance(cfg, dict) for cfg in space)
    assert inspect.signature(fc.train_model).parameters["random_state"].default == 0
    assert "RandomizedSearchCV" in inspect.getsource(fc.train_model)
    frame = _frame()
    train_df, _ = fc.chronological_split(frame)
    windows = fc.build_occupancy_windows(train_df, "classroom_A", 30)
    fitted = fc.train_model(
        windows[fc.OCC_FEATURES].to_numpy()[:500],
        windows[fc.TARGET_COL].to_numpy()[:500],
        model="histgb",
        horizon=30,
        search=TINY_SEARCH["histgb"],
    )
    # Scaler is inside the Pipeline: fit touches train data only, refit per fold.
    assert "scaler" in fitted.best_estimator_.named_steps
