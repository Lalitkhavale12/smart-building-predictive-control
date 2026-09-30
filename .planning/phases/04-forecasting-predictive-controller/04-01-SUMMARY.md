# Phase 04 Plan 01: Walk-Forward Forecasting Framework Summary

**Status:** complete — leakage-proof split + windowing + persistence + RF/HistGB with fixed budgets, all tests green.

## What was built

- `ml/__init__.py` — forecasting package marker.
- `ml/forecast.py` — chronological_split (sort-by-timestamp, whole-day cut, split BEFORE windowing), build_occupancy_windows / build_demand_windows (lags {5,15,30,60}, sin/cos calendar, power_kW never a feature for occupancy), persistence_predict (repeat-last), score_metrics (MAE/RMSE/R²), RF_SEARCH/HGB_SEARCH (6-config committed literals), train_model (StandardScaler-in-Pipeline + RandomizedSearchCV over TimeSeriesSplit(n_splits=4, gap=horizon), random_state=PAIRED_SEEDS[0]), evaluate_horizon (per-horizon table with persistence + rf + histgb), demand-coupling doc (train demand on C1-schedule data only; occupancy unaffected).
- `tests/test_forecast.py` — test_no_time_leakage, test_walkforward_chronology, test_persistence_metrics_present, test_persistence_baseline_present, test_no_shuffle_regression (fragment-built patterns, self-trip-free), test_search_budget_fixed.
- `requirements.txt` — scikit-learn==1.8.0 pin + stale-Python-3.12 note (full TF pin in 04-02).

## Test results

- `pytest tests/test_forecast.py -x -q` → 6 passed
- `pytest tests/test_forecast.py tests/test_harness.py -q` → 13 passed
- Full `pytest tests/ -q` → 76 passed, 2 skipped (no regressions)

## Measured metrics (2-day C1 weekday, seed 0, classroom_A occupancy H=30)

| model | MAE | RMSE | R² |
|-------|-----|------|-----|
| persistence | 4.3215 | 10.0182 | 0.3409 |
| rf | 2.5406 | 5.2811 | 0.8168 |
| histgb | 2.6277 | 4.5410 | 0.8646 |

Both learned models beat persistence at H=30; full 30/60 × occupancy/demand bake-off tables are exercised in tests via TINY_SEARCH and run at full budget in 04-02.

## Deviations

None — plan executed as written (work already committed as eac2ee6 / 41a81ee / 566fb0b; this run verified + summarized).

## Self-Check: PASSED

- ml/forecast.py, ml/__init__.py, tests/test_forecast.py, requirements.txt pin all FOUND on disk.
- Commits eac2ee6, 41a81ee, 566fb0b FOUND in log.
