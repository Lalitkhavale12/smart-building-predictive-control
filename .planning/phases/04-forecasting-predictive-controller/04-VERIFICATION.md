# Phase 04: Forecasting + Predictive Controller — Verification Report

**Phase goal (ROADMAP):** Users can predict occupancy and demand ahead and watch the predictive controller act on those forecasts.
**Mode:** mvp — the outcome clause ("watch C4 act on forecasts") is the success condition.
**Verified:** 2026-09-30
**Status:** passed
**Score:** 5/5 success criteria verified
**Test run:** `python -m pytest tests/test_forecast.py tests/test_bakeoff.py tests/test_uci_adapter.py tests/test_predictive.py -q` → **28 passed** (69s; only numpy/keras deprecation warnings)

## Verdict per criterion

| # | Criterion (Req) | Verdict | Evidence |
|---|-----------------|---------|----------|
| 1 | 30–60 min occupancy forecasts, walk-forward, no leakage (FOR-01) | ✅ PASS | `ml/forecast.py::chronological_split` (sort-by-ts, whole-day cut, split BEFORE windowing), `TimeSeriesSplit(n_splits=4, gap=horizon)`, lag features `{5,15,30,60}` + calendar, `power_kW` excluded from occupancy features. Tests `test_no_time_leakage`, `test_walkforward_chronology`, `test_no_shuffle_regression` green; no `shuffle` in `ml/*.py`. |
| 2 | Demand forecasts with MAE/RMSE/R² vs persistence (FOR-02) | ✅ PASS | `evaluate_horizon` scores persistence + rf + histgb per horizon (never averaged); `score_metrics` returns MAE/RMSE/R²; `test_persistence_baseline_present` green. Measured H=30 classroom_A: persistence R² 0.34 → rf 0.82 / histgb 0.86 (both beat persistence). |
| 3 | RF/HistGB vs LSTM with tie-to-simpler (FOR-03) | ✅ PASS | `ml/lstm.py` (1 layer × 32 units, caps 64/50/2 enforced by `check_caps`, TF function-local, artifact round-trip); `ml/bakeoff.py::tie_break` (<3% LSTM gain with overlapping std, HistGB win, or missing LSTM → `ship: histgb`); `evaluate_models`/`run_bakeoff` per-horizon 4-model tables + verdict + `results/bakeoff.csv`. 5 bake-off tests green. Note: the 04-02 demo's `ship: lstm` is a documented toy-budget artifact (1-day frames, 1-config searches), not a model claim. |
| 4 | Public-dataset validation (FOR-04) | ✅ PASS | `ml/uci.py` (stdlib-only fetch, 19,735-row + column-set verification, rv1/rv2 dropped, H=3/H=6 10-min-step mapping, demand-only frame, graceful `load_or_skip` fallback per D-13); 5 adapter tests green (mocked, <1s). Touches nothing in `sim/`/`ctrl/`. |
| 5 | C4 pre-cool / early-off via `BasePolicy.step()` (CTL-04) | ✅ PASS | `ctrl/predictive.py::PredictivePolicy(SetbackPolicy)`: `forecast=None` → `super().step(obs)` verbatim; empty + occ@30 ≥ 1 → ON (pre-cool); empty + occ@30/60 < 1 + C3-hold-ON → OFF (early-off); occupied rooms inherit C3; garbage → C3 fallback; `obs` never mutated. 12 tests green. Live spot-check this run: `None`-is-C3 `True`, pre-cool fires `OFF/REDUCED → ON`. Zero harness edits (`run_controller` already forwards `forecast`); in-process only, never MQTT. |

## Central judgment: the negative C4 ablation

**Finding (not a gap):** C4-with-forecast uses **12–33% MORE energy** than C4-as-C3 (weekday −12.3%, weekend −7.6%, heatwave −33.1%; comfort 0% vs ~3%).

**Why this PASSES the phase:** Phase 4's goal is the **mechanism** — "predict ahead and watch C4 act on forecasts" — and SC5 asks only that C4 pre-cools/early-offs through `BasePolicy.step()`. That mechanism is proven: forecast→action trace exists in `_apply_overlay`, 12 tests pin both triggers plus the None→C3 identity, and the forecaster itself is good (holdout: median pred 0.009 when true==0; 24.6 vs 25.7 occupied). The `run_ablation` harness measures the gap honestly on paired seeds with a comfort column on every row. Nothing in Phase 4's 5 success criteria requires C4 to **beat** C3 on energy — "beat baselines on the energy/comfort tradeoff" is Phase 5's goal (EVAL-03/04, Pareto). The negative gap is therefore **evaluation data for Phase 5, plus a tuning question** (oversized −3.5 kW plant plunges ~13 °C through the locked 22–26 °C band on 30-min pre-cool; comfort 0–5% holds for C1/C2/C3 identically — pre-existing sim structure, traced live, not a C4 bug). Failing the phase would conflate "capability missing" with "result unfavorable"; the capability is present and the unfavorable result was reported as-is instead of tuned away.

## Issues and follow-ups for Phase 5

1. **C4 tuning question (Phase 5):** pre-cool duration vs plant size vs comfort band — shorter pre-cool window, capacity-scaled pre-cool, or band-aware trigger. Plant/band redesign is out of Phase 4 scope (locked band, Phase-1 physics).
2. **Heatwave robustness:** weather-shifted T_in lags increase pre-cool firing (−33.1%). Phase 5 scenario×seed rigor should confirm whether retraining per regime or confidence-gated pre-cool closes it.
3. **Full-budget bake-off verdict:** the committed 6-config × 5-seed × multi-day verdict runs at the phase gate / Phase 5 context; the checked-in demo verdict is a toy-budget artifact (documented in 04-02-SUMMARY).
4. **`results/` artifacts uncommitted by design:** `ablation_c4.csv` (30 rows), `pred_vs_actual_c4.csv` (5340 rows), `bakeoff.csv` are gitignored scratch, verified on disk per summaries. Phase 5/6 should decide what gets committed or regenerated by one command.

## Anti-patterns

Clean: no TODO/FIXME/XXX/TBD, no `NotImplemented`, no empty returns. The only "placeholder" hits are the documented UCI `occupancy=0` demand-only column (by design — UCI has no occupancy ground truth, never scored).

## Requirements coverage

FOR-01, FOR-02 (04-01) · FOR-03, FOR-04 (04-02) · CTL-04 (04-03) — all satisfied with implementation + test evidence above.

---
_Verifier: gsd-verifier · 2026-09-30 · **PASS — mechanism proven, negative ablation recorded as Phase 5 input, not a phase failure.**_
