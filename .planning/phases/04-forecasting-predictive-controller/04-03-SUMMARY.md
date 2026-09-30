---
phase: 04-forecasting-predictive-controller
plan: 03
subsystem: predictive-control
tags: [c4, predictive-policy, forecast-overlay, ablation, ctl-04]
requires: [04-01]
provides: [c4-policy, ablation-c4, pred-vs-actual]
affects: [phase-05-eval]
tech_stack:
  added: []
  patterns: [frozen-forecaster-in-process, flag-flip-ablation, tick-grid-features]
key_files:
  created: [ctrl/predictive.py, tests/test_predictive.py]
  modified: []
decisions:
  - "Fresh policy instance per ablation run (same class+params); shared forecaster reused with minute-wrap buffer reset"
  - "Negative ML gap reported as-is: pre-cool overshoots on oversized plant, comfort band unreachable for all controllers"
metrics:
  duration: "~45 min"
  completed: "2026-09-30"
  tasks: 3
  commits: 3
status: complete
---

# Phase 04 Plan 03: Predictive Controller C4 + Forecast Ablation Summary

**Status:** complete — C4 pre-cools before arrivals and early-offs before departures through `BasePolicy.step()`, degrades to C3 byte-identically on `forecast=None`, and the on/off ablation quantifies the ML contribution (negative, honestly reported).

## What was built

- `ctrl/predictive.py`
  - `Forecast` container (D-01/D-10): per-room occupancy at +30/+60 via `predictions(room)`, building demand at +30/+60; in-process only, never MQTT. Garbage predictions (NaN/str/missing room) fall back to C3 per-room (T-04-04).
  - `PredictivePolicy(SetbackPolicy)` (D-08, research F6): `forecast=None` returns `super().step(obs)` verbatim (D-09). Overlay: empty + occ@30 ≥ 1 → ON (pre-cool); empty + occ@30/60 < 1 + C3-hold-ON → OFF (early-off); occupied rooms and all other cases inherit C3 exactly. Lights follow current occupancy. `obs` never mutated.
  - Frozen forecaster: HistGB occupancy+demand models at +30/+60 pre-fit ONCE on C1-schedule 5-min-tick telemetry via `ml/forecast.py` (`train_model`, `chronological_split` — read-only, no edits to 04-02's file). 13-tick rolling obs buffer matches the training grid (tick lags 1/3/6/12 = 5/15/30/60 min); persistence cold start; minute-wrap buffer reset keeps shared-object reruns deterministic. Zero harness edits (`run_controller` forwards `forecast` already).
  - `run_ablation()` + `python -m ctrl.predictive --ablate`: flag-flip matrix over weekday/weekend/heatwave × PAIRED_SEEDS, comfort on every row.
- `tests/test_predictive.py` — 12 tests: None-is-C3 (incl. custom thresholds + obs-immutability), container shape, pre-cool fires/overrides-REDUCED, early-off fires/blocked-by-arrival, occupied-untouched, garbage-fallback, tick-features-match-vectorized, tiny frozen end-to-end (+determinism), ablation gap (arms/seeds/columns).
- `results/ablation_c4.csv` (30 rows, gitignored scratch) + `results/pred_vs_actual_c4.csv` (5340 holdout rows, both horizons, both targets).

## Test results

- `pytest tests/test_predictive.py tests/test_baselines.py tests/test_harness.py -q` → **30 passed**
- Full-budget forecaster quality (weekday holdout, classroom_A, H=30): median pred | true==0 is **0.009**, occupied 24.6 vs 25.7 true — the model is good; the gap below is control physics, not forecast error.

## Measured ablation gap (1-day, 5 paired seeds; comfort on every row)

| scenario | C4 forecast_on kWh | C4-as-C3 kWh | gap (ML contribution) | comfort_on | comfort_off |
|----------|-------------------|--------------|----------------------|------------|-------------|
| weekday | 51.681 | 46.015 | **−5.666 (−12.3%)** | 0.0% | 3.8% |
| weekend | 6.294 | 5.847 | **−0.447 (−7.6%)** | 0.0% | 3.1% |
| heatwave | 61.233 | 46.015 | **−15.218 (−33.1%)** | 0.0% | 2.5% |

The gap is negative and kept as-reported. Root causes, both verified live, both pre-existing sim structure (not C4 bugs):
1. ON cooling (−3.5 kW) is so oversized for a 0.14 kWh/K room that 30-min pre-cool plunges rooms ~13 °C (26.5 → 13.4 °C traced) straight through the 22–26 °C band — pre-cool spends energy and buys no comfort. Comfort 0–5% holds for C1/C2/C3 identically (Phase-3 table: C3 weekday 3.8%).
2. Weather-shifted T_in lags shift heatwave predictions → more pre-cool firing (−33.1%). Fixing either is plant/band redesign — out of scope (locked band, Phase-1 physics).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Cross-run state leakage under "identical policy object"**
- **Found during:** Task 3 ablation design
- **Issue:** Reusing one policy instance across runs leaks C3 vacancy timers between arms/seeds.
- **Fix:** Fresh `PredictivePolicy()` per run (same class + params); the flag flip is `forecast=forecaster` vs `forecast=None`.
- **Files modified:** `ctrl/predictive.py` (`run_ablation`)

**2. [Rule 1 - Bug] Shared-forecaster determinism across runs**
- **Found during:** Task 2 (`test_frozen_forecaster_end_to_end_tiny` rerun equality)
- **Issue:** A run's final tick wraps minute to 0, so `minute < last` missed the run boundary and stale buffers poisoned the next run.
- **Fix:** Reset on `minute <= last_minute` (midnight wrap = documented empty-building persistence cold start).
- **Files modified:** `ctrl/predictive.py` (`FrozenForecaster.observe`)

**3. [Rule 3 - Blocking] REDUCED-state test setup**
- **Found during:** Task 2 (`test_precool_overrides_reduced_hold`)
- **Issue:** Unseen rooms default long-vacant → first empty obs is OFF, never REDUCED.
- **Fix:** Occupy once first to start the vacancy timer, then vacate (matches C3 semantics).

`results/ablation_c4.csv` + `results/pred_vs_actual_c4.csv` are **not committed** (`results/` is gitignored) — plan's "committed" done-state yields to the repo's gitignore; files verified on disk. `ml/forecast.py` untouched (04-02 owns it this wave).

## Threat Flags

None — no surface beyond the plan register (T-04-04 schema-assert + None-fallback implemented and tested; T-04-05 empty-only early-off implemented, heatwave run as adversarial check).

## Known Stubs

None.

## Commits

- `5feff0c` feat(04-03): PredictivePolicy skeleton with None-to-C3 identity
- `15eaa79` feat(04-03): pre-cool plus early-off overlay with frozen forecaster
- `19b0532` feat(04-03): C4-with vs C4-as-C3 ablation with predicted-vs-actual evidence

## Self-Check: PASSED

- `ctrl/predictive.py`, `tests/test_predictive.py` FOUND; commits `5feff0c`, `15eaa79`, `19b0532` FOUND in log.
- `results/ablation_c4.csv` (30 rows, both arms × paired seeds, comfort column) + `results/pred_vs_actual_c4.csv` (5340 rows) FOUND on disk.
- `ml/forecast.py` unmodified (owned by 04-02); zero harness edits (`git status` shows only the two tracked files + SUMMARY untracked).
