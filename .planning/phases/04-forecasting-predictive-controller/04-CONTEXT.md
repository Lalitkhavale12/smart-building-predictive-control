# Phase 4: Forecasting + Predictive Controller - Context

**Gathered:** 2026-09-29
**Status:** Ready for planning

## Phase Boundary

Occupancy + demand forecaster (30–60 min ahead, walk-forward, chronological splits) plus predictive controller C4 (pre-cool before arrivals, early-off before departures) as a `BasePolicy` subclass consuming forecasts via the `forecast` kwarg `run_controller` already forwards. Forecast ablation (C4 with vs without forecast) included. No carbon-shifting claims (Phase 5), no Pareto (Phase 5), no dashboard (Phase 6). Public-dataset validation is a P1 deliverable of this phase, not stretch.

## Implementation Decisions

[--auto] Selected all gray areas: Forecast target, Horizons, Models, Leakage protocol, C4 mechanism, Ablation, Public data.

### Forecast target & horizon
- **D-01:** Forecast per-room occupancy (counts) + building demand (kW) at 30-min and 60-min horizons; model input = lagged telemetry windows from sim CSVs
- **D-02:** [auto] Horizons — Q: "30/60 or more?" → Selected: "30-min and 60-min only; more horizons is Phase-5 sensitivity material" (recommended default)

### Models
- **D-03:** RF + HistGB baselines (sklearn, fixed tuning budget) vs one Keras LSTM; tie → prefer simpler (ship HistGB, report LSTM)
- **D-04:** [auto] LSTM scope — Q: "How big?" → Selected: "Single small LSTM (1–2 layers), tiny synthetic data, CPU minutes; no architecture search" (recommended default)
- **D-05:** Persistence baseline (repeat-last) must be beaten and reported alongside MAE/RMSE/R²

### Leakage protocol
- **D-06:** Chronological splits + walk-forward evaluation only; random splits forbidden and grep-guarded in tests
- **D-07:** [auto] Leakage guard — Q: "How enforced?" → Selected: "Test asserts no shuffling (train max-time < test min-time) plus code grep for shuffle=True/train_test_split without shuffle=False" (recommended default)

### C4 mechanism
- **D-08:** C4 = C3 setback logic + forecast overlay: pre-cool (ON) when arrival predicted within 30 min, early-off when departure predicted within 30 min and room empty; otherwise fall back to C3 behavior exactly
- **D-09:** [auto] C4 fallback — Q: "C4 without forecast?" → Selected: "C4 degrades to C3 exactly when forecast is None (ablation arm + robustness for free)" (recommended default)
- **D-10:** Forecasts consumed via `run_controller(..., forecast=forecaster)` in-process calls, never over MQTT

### Ablation & public data
- **D-11:** Forecast ablation: C4-with-forecast vs C4-as-C3 (forecast=None) on same seeds; the gap is the ML contribution claim
- **D-12:** Public validation: UCI Appliances Energy Prediction (small, easy fetch) as forecaster-only validation; ASHRAE only if UCI fetch fails
- **D-13:** [auto] Dataset adapter — Q: "Which dataset?" → Selected: "UCI Appliances first (time-boxed fetch spike, fall back to synthetic-only with documented reason if network blocked)" (recommended default)

### the agent's Discretion
- Lag window lengths, HistGB hyperparams, LSTM units/epochs, adapter column mapping
- C4 pre-cool/early-off thresholds (minutes) as constructor params with documented defaults

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope
- `.planning/PROJECT.md` — core value (forecast drives savings), hard gate cleared
- `.planning/REQUIREMENTS.md` — FOR-01..04, CTL-04 definitions
- `.planning/ROADMAP.md` Phase 4 — goal + 5 success criteria
- `smart_building_project_idea.md` — forecasting method, controller table
- `.planning/phases/03-baselines-comparison-harness/03-CONTEXT.md` — C1–C3 semantics C4 extends

### Research
- `.planning/research/SUMMARY.md` — forecaster + C4 as core ML claim
- `.planning/research/STACK.md` — sklearn HistGB/RF, TF/Keras LSTM, versions
- `.planning/research/PITFALLS.md` — temporal leakage (pitfall #1), synthetic-only validation, LSTM-vs-RF tie rule
- `.planning/research/ARCHITECTURE.md` — forecast-as-input pattern

### Existing code (read actual APIs)
- `ctrl/baselines.py` — C3 SetbackPolicy C4 subclasses; `ctrl/harness.py` run_controller forecast kwarg
- `sim/policy.py` — BasePolicy.step(obs, forecast, signals) signature
- `sim/metrics.py`, `sim/summary.py`, `sim/grid.py` — scoring/summary/pricing reuse

## Existing Code Insights

### Reusable Assets
- `run_controller(..., forecast=None, signals=None)` — C4-ready, zero harness edits needed
- `SetbackPolicy` — C4 subclasses it, adds forecast overlay only
- `summarize()` + `compare.py` — ablation reuses the same CSV + figure path

### Established Patterns
- Seeded determinism; occupied-weighted comfort; no-scalar-carbon; mean±std over PAIRED_SEEDS

### Integration Points
- `ml/forecast.py` (new package) exposes `fit(df) -> model` + `predict(history) -> occupancy/demand`; C4 calls it in-process
- Public-dataset adapter lives in `ml/` and touches nothing in `sim/` or `ctrl/`

## Specific Ideas

No specific requirements — standard walk-forward forecasting. Keep models small and the leakage guard loud.

## Deferred Ideas

None — discussion stayed within phase scope. Carbon shifting + Pareto + full eval (Phase 5), dashboard (Phase 6) untouched.

---

*Phase: 4-Forecasting + Predictive Controller*
*Context gathered: 2026-09-29*
