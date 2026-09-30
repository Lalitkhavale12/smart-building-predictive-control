# Phase 04: Forecasting + Predictive Controller — Research

**Researched:** 2026-09-29
**Domain:** Time-series forecasting (occupancy/demand, 30/60-min horizons) + rule-based predictive control
**Confidence:** HIGH on protocol/control-law; MEDIUM on UCI adapter; LOW on LSTM payoff

## Goal

Give the planner everything needed to plan FOR-01, FOR-02, FOR-03, FOR-04, CTL-04: a forecaster trained on sim telemetry CSVs with a leakage-proof evaluation protocol, a C4 `BasePolicy` subclass that consumes forecasts via the existing `forecast` kwarg, a forecast on/off ablation reusing the Phase-3 harness, and forecaster-only validation on UCI Appliances with a documented fallback. Locked decisions from 04-CONTEXT.md are honored throughout (30/60-min horizons only, RF+HistGB vs one small LSTM with tie→simpler, persistence baseline mandatory, chronological+walk-forward only, C4 = C3 + forecast overlay with None→C3 fallback, in-process forecasts never over MQTT, UCI-first with synthetic-only fallback).

## Key Questions

1. How exactly do chronological split + walk-forward work on 1-min sim CSVs, and how do tests enforce them? (credibility core)
2. What lag-feature design feeds occupancy + demand models at 30/60-min horizons?
3. How is the HistGB/RF vs LSTM bake-off made fair (fixed tuning budgets + tie rule + persistence baseline)?
4. What is C4's exact control law — which forecast values trigger pre-cool vs early-off, and what is the fallback?
5. How does the ablation isolate the ML contribution using existing harness interfaces?
6. How is UCI Appliances fetched/adapted, and what happens if the network is blocked?
7. What are the training-time budgets that keep LSTM from blocking the team?

## Findings

### F1. Walk-forward protocol on 1-min sim CSVs [VERIFIED: sim/logger.py:21-24, sim/config.py:8-11]

**Data shape.** Each `run_controller` run yields a telemetry frame with schema `timestamp,room,T_in_C,T_out_C,RH_pct,occupancy,HVAC_state,power_kW,light_on` [VERIFIED: sim/logger.py:21-24], 1440 rows/day × 4 rooms, 1-min steps (`DT_S = 60`, `STEPS_PER_DAY = 1440`) [VERIFIED: sim/config.py:8-11]. Forecaster training data = these CSVs (wide or per-room long format — planner's choice; per-room models are simpler and rooms have ±15% R/C variation so sharing one model across rooms is defensible but per-room avoids leakage-across-rooms questions).

**Chronological split mechanics (prescriptive).**
- Sort by `timestamp` ascending first (CSVs are already time-ordered, but sort defensively).
- Single holdout: train = first 70–80% of the timeline, test = final 20–30%, cut on timestamp, never shuffle. With multi-day runs, cut on whole-day boundaries (e.g., 5-day run → train days 1–3, validation day 4, test day 5) so no day is split mid-profile.
- **Split by time BEFORE windowing.** Build lag windows strictly inside each partition so no window straddles the train/test boundary [CITED: https://scikit-learn.org/stable/modules/cross_validation.html — TimeSeriesSplit docs warn KFold/ShuffleSplit leak via autocorrelation].
- Fit every preprocessing step (scalers, imputation) on the train partition only, then transform test [CITED: PITFALLS.md leakage checklist].
- Use `gap` ≥ horizon between train end and test start when windowing (sklearn `TimeSeriesSplit(..., gap=H)` excludes samples between train and test) [CITED: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html]. For direct 30/60-min-ahead targets, gap = 30 (resp. 60) rows on 1-min data.

**Walk-forward mechanics (prescriptive).**
- Use `sklearn.model_selection.TimeSeriesSplit(n_splits=4, test_size=<block>, gap=<horizon>)` — successive train sets are supersets of earlier ones, test block strictly after all its training data [CITED: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html]. 4 folds matches the PITFALLS.md worked example ("4 folds, each test block strictly after all its training data").
- Model selection (hyperparams) on walk-forward mean; final report on the single chronological holdout. Do NOT use the new `n_splits="walk_forward"` sentinel API [ASSUMED — it exists only in an unmerged sklearn PR (#33424), not in installed sklearn 1.8.0; integer `n_splits` + `test_size` + `gap` is the stable API].
- Multi-seed: forecaster metrics reported as mean±std over PAIRED_SEEDS [0,1,2,3,4] [VERIFIED: sim/config.py:77] — one CSV set per seed, same split fractions. (Forecaster seeds also cover sklearn `random_state` and TF seed; log all three.)

### F2. Lag-feature design [ASSUMED except schema]

- **Targets (direct forecasting, one model per horizon):** `occupancy(t+H)` per room and `power_kW(t+H)` summed over rooms (building demand), H ∈ {30, 60} rows. Direct (not recursive) multi-step avoids error accumulation; two horizons × two targets = 4 model instances per algorithm (cheap for HistGB/RF, fine for one small LSTM ×4 or one multi-output head — planner's discretion, CONTEXT.md D-agent's-discretion covers this).
- **Features (all knowable at prediction time — deployment-availability rule):** lagged `occupancy`, `T_in_C`, `T_out_C`, `RH_pct`, `power_kW` at lags {5, 15, 30, 60} min (multiples of the 5-min control hook, so features align with what C4 can actually observe live); calendar features `minute_of_day` (sin/cos), `is_weekend`. Never include same-timestep consequences of the target as features (e.g., don't use `power_kW(t)` to predict `occupancy(t)` — HVAC power is a *consequence* of occupancy+control, proxy-for-outcome leakage) [CITED: PITFALLS.md Pitfall 1 warning signs].
- **Window tensors for LSTM:** sliding windows of length 60 min (60 rows) → target at +30/+60; windows built post-split inside each partition (F1).
- **Lag lengths are the agent's discretion** (CONTEXT.md) — the sets above are starting defaults, not locked.

### F3. HistGB/RF vs LSTM comparison protocol with fixed tuning budgets + tie rule

- **Mandatory baseline set:** persistence (repeat-last: `ŷ(t+H) = y(t)`) + RF + HistGB + LSTM, same splits, same horizons, same metrics (MAE/RMSE/R²) [CITED: PITFALLS.md Pitfall 10]. Persistence is brutally strong for slow-changing occupancy at 30-min horizons — its absence is suspicious to evaluators.
- **Prefer `HistGradientBoostingRegressor` over legacy `GradientBoostingRegressor`** — orders of magnitude faster past ~10k samples [CITED: STACK.md, sklearn ensemble docs]. A 5-day run = 7200 rows/room; 4 rooms × 5 seeds is well past the threshold where legacy GB is painful.
- **Fixed tuning budgets (prescriptive, auditable):** each model gets an equal, small, pre-declared search (e.g., ≤12 configs via `RandomizedSearchCV` with `cv=TimeSeriesSplit`, or a hand-listed grid committed in the training script). Report the search space briefly so the comparison is auditable [CITED: PITFALLS.md Pitfall 10]. Never `RandomForestRegressor()` all-defaults vs a tuned LSTM — that rigs the bake-off.
- **Per-horizon reporting:** separate MAE/RMSE/R² tables for 30-min and 60-min; never average across horizons (hides degradation) [CITED: PITFALLS.md Pitfall 10].
- **Tie rule (locked, D-03):** if LSTM wins by <2–3% with overlapping std across seeds, ship HistGB and report LSTM as reference only. Rationale: deployment cost, inference latency, explainability all favor GB on ESP32-adjacent hardware [CITED: PITFALLS.md Pitfall 10].
- **sklearn 1.8.0 installed, verified this session** (env reports 1.8.0, not the 1.9.x STACK.md anticipated — `HistGradientBoostingRegressor`, `RandomForestRegressor`, `TimeSeriesSplit` APIs are stable across both; no action needed).

### F4. Persistence baseline (definition)

`ŷ(t+H) = y(t)` per target series — no training, computed on the same test blocks as the learned models. Report its MAE/RMSE/R² in every results table (locked, D-05). If no learned model beats persistence at 30 min, say so honestly — that is a finding about timetable regularity (sharp ±10-min-jittered blocks [VERIFIED: sim/config.py:134-135] are highly predictable), not a failure [ASSUMED — interpretive guidance].

### F5. Leakage-guard test design (credibility core, prescriptive)

Two layers, both required (locked, D-07):

**Layer 1 — behavioral assertion (timestamps):** after every split function returns `(train_df, test_df)`, assert `train_df["timestamp"].max() < test_df["timestamp"].min()`. For walk-forward folds, assert the same per fold. This is the test that actually catches leakage; name it `test_no_time_leakage` / `test_walkforward_chronology`.

**Layer 2 — static grep guard (code hygiene):** a test that greps `ml/` for `shuffle=True` and for `train_test_split` occurrences lacking `shuffle=False` on the same line, failing if found. This catches tutorial-copy-paste regressions. Precedent: the repo already uses grep-gate tests (`no-scalar-carbon grep gate on ctrl/` [VERIFIED: 03-02-SUMMARY.md:30-32, test_harness.py]), so the pattern is established — mirror it.

**Leakage checklist (run per model, from PITFALLS.md):** (a) any test timestamp earlier than a training timestamp? (b) any preprocessing statistic computed with test data? (c) every feature available at prediction time in deployment? Encode (a) as the Layer-1 test; (b)+(c) as code review items (scaler `fit` called only on train; feature list reviewed against F2 deployment-availability rule).

### F6. C4 pre-cool / early-off control law (prescriptive)

**Interfaces (quote verbatim, read this session):**
- `BasePolicy.step(self, obs, forecast=None, signals=None)` returns `{room_id: {"hvac": "OFF"|"REDUCED"|"ON", "light": 0|1}}` [VERIFIED: sim/policy.py:13-21].
- `run_controller(policy, scenario, seed, days=1, forecast=None, signals=None)` forwards `forecast`/`signals` into every `policy.step` call [VERIFIED: ctrl/harness.py:57-66] — **C4 plugs in with zero harness edits**.
- C3 reference: `SetbackPolicy(vacancy_min=15, setback_min=60)` — empty < 15 min → ON (hold); 15–60 → REDUCED; ≥ 60 → OFF; occupied → ON; unseen rooms default long-vacant [VERIFIED: ctrl/baselines.py:72-113]. C4 subclasses `SetbackPolicy` and adds the forecast overlay only.

**Control law (prescriptive, thresholds as constructor params per CONTEXT.md agent's discretion):**
```python
class PredictivePolicy(SetbackPolicy):
    def __init__(self, vacancy_min=15, setback_min=60,
                 precool_min=30, earlyoff_min=30, occ_threshold=1):
        ...
    def step(self, obs, forecast=None, signals=None):
        if forecast is None:
            return super().step(obs)          # ablation arm + robustness, D-09
        base = super().step(obs)              # C3 behavior = fallback default
        for room in obs:
            occ_now = obs[room]["occupancy"]
            pred = forecast.predictions(room) # e.g. occupancy at +30/+60
            if occ_now == 0 and max(pred.occ_next_30min) >= occ_threshold:
                base[room]["hvac"] = "ON"     # PRE-COOL before arrival
            elif occ_now == 0 and max(pred.occ_next_30min) < occ_threshold \
                    and base[room]["hvac"] == "ON":
                base[room]["hvac"] = "OFF"    # EARLY-OFF: C3 would hold ON
            # occupied rooms: C3 ON stands; REDUCED/OFF rooms with no arrival: C3 stands
        return base
```
- **Pre-cool trigger:** room currently empty AND forecast occupancy ≥ 1 person within the next 30 min → force ON (C3 would say REDUCED/OFF depending on vacancy timer). Default `precool_min=30` (== 30-min horizon — uses FOR-01's H=30 model directly).
- **Early-off trigger:** room currently empty AND forecast says it stays empty for the next 30 min AND C3's hold logic says ON (vacancy < 15 min) → force OFF (skip the hold). This is where C4 beats C3 on the weekend-deficit pattern (C3's post-block REDUCED hold [VERIFIED: 03-02-SUMMARY.md:49-55] is exactly what early-off shortens — but only when the forecast confirms no return).
- **Otherwise C3 exactly.** Occupied rooms, REDUCED rooms with no predicted arrival, OFF rooms staying empty — all inherit C3. Comfort safety follows: pre-cool only ever turns cooling ON (comfort-safe direction); early-off only fires when empty (no comfort exposure).
- **Forecast object shape** (`ml/forecast.py` exposes `fit(df)` + `predict(history)` per CONTEXT.md Integration Points): planner defines the container, but it must carry per-room occupancy predictions at +30/+60 and building demand at +30/+60 (D-01), built from lagged telemetry windows. Forecasts travel as **in-process calls, never MQTT** (locked, D-10). Lights follow current occupancy in all cases (all baselines do [VERIFIED: ctrl/baselines.py:110-113]).
- **Why tau-grounded:** room tau ≈ 3.6 h [VERIFIED: sim/config.py:35-38]; 30-min pre-cool ≈ 14% of tau — enough to pull a drifted room back toward band before arrival without all-day pre-cooling [ASSUMED — physical reasoning, validate via comfort column in ablation].

### F7. Ablation design: C4-with vs C4-as-C3

- **Arms:** `run_controller(PredictivePolicy(), scenario, seed, forecast=forecaster)` vs `run_controller(PredictivePolicy(), scenario, seed, forecast=None)` — identical policy object, flag flip only (possible because `forecast=None` degrades to C3 exactly, D-09, and `run_controller` forwards it [VERIFIED: ctrl/harness.py:57-66]).
- **Seeds/scenarios:** same PAIRED_SEEDS [0..4], same scenarios as Phase-3 matrix (weekday/weekend/heatwave; exam-day excluded by default per compare.py CLI [VERIFIED: 03-02-SUMMARY.md:23-24]). Reuse `compare.py` + `summarize()` + `compute_metrics` (energy/cost/CO₂/comfort) unchanged.
- **Claim:** the gap between arms = the ML contribution (forecast on/off ablation, mandatory per PITFALLS.md Pitfall 8). Headline framed as savings-over-strongest-baseline (C2/C3), not vs C1. Every table row carries the comfort column; comfort violations mark the run failed, not celebrated.
- **New figure:** predicted-vs-actual chart (FOR + CTL evidence in one plot) — forecast occupancy/demand vs telemetry on the holdout, per horizon.

### F8. UCI Appliances fetch + adapter design with fallback

- **Dataset facts:** 19,735 rows, 10-min intervals, ~4.5 months, 28 features, no missing values; target `Appliances` (Wh); features T1–T9/RH_1–RH_9 indoor, `To`/Pressure/`RH_out`/Windspeed/Visibility/Tdewpoint weather, `lights`, plus `rv1`/`rv2` random probes [CITED: https://archive.ics.uci.edu/dataset/374/appliances%2Benergy%2Bprediction]. Download ≈ 11.4 MB zip [CITED: https://archive-beta.ics.uci.edu/dataset/374/appliances+energy+prediction/files]. Paper + R scripts: `github.com/LuisM78/Appliances-energy-prediction-data` [CITED: UCI page].
- **Adapter (lives in `ml/`, touches nothing in `sim/`/`ctrl/` per CONTEXT.md):** parse `date` → timestamp index; resample 10-min → hourly or keep native and set horizons in steps (H=3/H=6 steps = 30/60 min — document the mapping); drop `rv1`/`rv2` (documented noise probes); target `Appliances` (+ optionally `lights`); features = indoor T/RH + weather. No occupancy ground truth exists in UCI — validate **demand forecasting only** there (occupancy validation stays synthetic); state this limitation explicitly in the report.
- **Scope:** forecaster-only validation (train/evaluate RF/GB+LSTM on UCI, report MAE/RMSE/R² side-by-side with synthetic). No controller runs on UCI.
- **Fallback (locked, D-13):** time-box the fetch spike; if network blocked, ship synthetic-only with a documented reason + the transfer-learning-optional note (synthetic-trained → real-trace zero-shot number is the strongest credibility signal per PITFALLS.md Pitfall 2, but optional under time pressure).
- **No new pip packages needed** for fetch (`urllib` + `pandas.read_csv` + zipfile stdlib); do NOT add dataset-loader dependencies.

### F9. Training-time budgets

- **Environment (verified this session):** Windows, Python 3.14.6, sklearn 1.8.0, numpy 2.4.3, pandas 3.0.1, **TensorFlow 2.22.0-rc0 imports OK on CPU** (oneDNN warnings only). LSTM is viable — no WSL/GPU needed.
- **Tension note [ASSUMED — needs planner awareness]:** STACK.md pins Python 3.12 (TF wheels stopped at 3.12), but this machine runs 3.14.6 with TF 2.22.0-rc0 working. Do NOT downgrade the env in this phase; do note in the report that the 3.12 pin is stale for TF ≥ 2.22. The `requirements.txt` currently lacks sklearn/TF entries (only numpy/pandas/matplotlib/pytest + paho-mqtt) — planner must add `scikit-learn` and `tensorflow` pins.
- **Budgets (prescriptive):** HistGB/RF full bake-off (4 targets × ≤12 configs × 4-fold walk-forward × 5 seeds) must run in minutes on CPU [ASSUMED — HistGB is fast by design]; LSTM capped at **1–2 layers, ≤64 units, ≤50 epochs with early stopping, one config per target** (no architecture search, locked D-04), CPU-minutes per fit; **train-once-per-config, version the artifact, reuse across controller experiments** (never retrain per scenario/seed — PITFALLS.md Performance Traps). If LSTM training blocks the team, RF/GB + C4 proceed while LSTM trains in the background (parallelizable per SUMMARY.md).

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Timetable regularity makes forecasting trivially easy (sharp blocks + ±10-min jitter) → tiny C4-vs-C3 gap | HIGH | MEDIUM | Honest reporting: persistence baseline exposes it; gap-over-strongest-baseline framing; office poisson noise + absence_p=0.05 [VERIFIED: sim/config.py:133-137] provide the irregularity |
| LSTM underperforms HistGB on tiny tabular data | MEDIUM | LOW | Expected per literature ("no champions", 3500+ nets); tie rule converts this into a shipped-HistGB decision, not a failure |
| `train_test_split(shuffle=True)` copy-paste from tutorials | MEDIUM | CRITICAL | Layer-2 grep guard + Layer-1 timestamp assertion; both block merge |
| Scaler fit on full data before split | MEDIUM | HIGH | Code-review checklist item; assert via refit-in-fold in walk-forward loop |
| Same-timestep consequence features (power→occupancy) | LOW | HIGH | F2 deployment-availability review; feature list in plan |
| UCI fetch blocked on lab network | MEDIUM | LOW | Time-boxed spike + documented synthetic-only fallback (locked) |
| TF version churn on 3.14 (rc build) | LOW | MEDIUM | Pin `tensorflow==2.22.0` post-rc in requirements; CPU-only; LSTM isolated so env issues never block C4 (HistGB path has no TF dep) |
| C4 early-off hurts comfort on jittered late arrivals | MEDIUM | MEDIUM | Early-off requires forecast-empty-30-min AND room-empty-now; comfort column gates every ablation table; heatwave scenario is the adversarial check |

## Open Questions

1. **Per-room vs single global forecaster?** Rooms differ ±15% in R/C and timetables differ sharply (classroom blocks vs office poisson). Per-room models are simpler to reason about and avoid cross-room leakage questions; a global model with room-ID features has 4× data. Recommendation: start per-room (agent's discretion; planner picks one, notes the other as follow-up).
2. **Online (rolling re-fit) vs frozen forecaster inside `run_controller`?** Frozen artifact is deterministic and reproducible (byte-identical reruns precedent [VERIFIED: 03-02-SUMMARY.md:30-32]); online re-fit per control tick is expensive and nondeterministic. Recommendation: frozen — C4 calls `predict` on a pre-fit model; no training inside the control loop.
3. **Demand target definition:** building-total `power_kW` suffers control-feedback coupling (power depends on which controller ran). Cleaner: forecast *uncontrolled* demand proxy (occupancy-driven load) or train demand models on C1-schedule data only and document the coupling. Planner must pick and document; occupancy forecasts (FOR-01) are unaffected and are C4's primary input.

## Validation Architecture

> nyquist_validation is enabled (`workflow.nyquist_validation: true` [VERIFIED: .planning/config.json:24]); security_enforcement enabled (level 1).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8 (installed per requirements.txt) |
| Config file | none at root — tests/ flat layout with conftest.py |
| Quick run command | `pytest tests/test_forecast.py tests/test_predictive.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOR-01 | occupancy +30/+60 forecast, chronological + walk-forward | unit + leakage-guard | `pytest tests/test_forecast.py::test_no_time_leakage -x` | ❌ Wave 0 |
| FOR-02 | demand +30/+60, MAE/RMSE/R² vs persistence | unit | `pytest tests/test_forecast.py::test_persistence_baseline_present -x` | ❌ Wave 0 |
| FOR-03 | RF/HistGB vs LSTM, fixed budgets, tie→simpler | unit (metrics table assertion) | `pytest tests/test_forecast.py::test_bakeoff_table -x` | ❌ Wave 0 |
| FOR-04 | UCI adapter produces aligned frame or documented skip | unit (adapter) | `pytest tests/test_uci_adapter.py -x` | ❌ Wave 0 |
| CTL-04 | C4 pre-cool on predicted arrival; early-off on predicted-empty; None→C3-identical | unit | `pytest tests/test_predictive.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** quick run command above
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** full suite green + leakage-guard tests green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_forecast.py` — split/windowing/leakage-guard + bake-off table tests (REQ FOR-01..03)
- [ ] `tests/test_predictive.py` — C4 overlay + None-fallback-identical-to-C3 tests (REQ CTL-04)
- [ ] `tests/test_uci_adapter.py` — adapter frame schema or graceful-skip test (REQ FOR-04)
- [ ] Framework install: `pip install scikit-learn tensorflow` pinned in requirements.txt — if none detected

## Security Domain

> security_enforcement: true, ASVS level 1. Phase surface: local data files + in-process calls; no auth/session/crypto; no network except UCI fetch.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no user accounts) |
| V3 Session Management | no | — |
| V4 Access Control | no | — (local files; results/ gitignored) |
| V5 Input Validation | yes | range-check UCI CSV columns on load (NaN/garbage → documented exclusion, never silent); assert feature schema at model load (precedent: PITFALLS.md integration gotchas) |
| V6 Cryptography | no | — (never hand-roll; nothing to encrypt) |

Known threat patterns: UCI zip from archive.ics.uci.edu — verify row count (19,735) + column set on load rather than trusting bytes [CITED: UCI dataset page]; never commit API keys (none needed).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `n_splits="walk_forward"` sentinel unavailable in sklearn 1.8.0 — use integer API | F1 | LOW — planner verifies with one import; fallback is the prescribed integer API either way |
| A2 | Lag sets {5,15,30,60} min + sin/cos calendar features suffice as starting defaults | F2 | LOW — agent's discretion; walk-forward scores will confirm or refute |
| A3 | HistGB bake-off runs in CPU-minutes at this data scale | F9 | LOW — matches sklearn design intent; time-box confirms |
| A4 | 30-min pre-cool ≈ 14% of 3.6 h tau is comfort-effective | F6 | MEDIUM — ablation comfort column is the empirical check |
| A5 | Python 3.14.6 + TF 2.22.0-rc0 stable enough to ship (3.12 pin stale) | F9 | MEDIUM — mitigated by isolating TF to LSTM-only path |

## Sources

### Primary (HIGH confidence)
- sim/policy.py:13-21, sim/config.py (timesteps, rooms, tau, timetables, seeds), sim/logger.py:21-24, sim/metrics.py, ctrl/baselines.py:72-113, ctrl/harness.py:57-66 — read this session
- 03-02-SUMMARY.md — harness/C3 interfaces, weekend-deficit motivation for C4
- 04-CONTEXT.md, REQUIREMENTS.md (FOR-01..04, CTL-04), PITFALLS.md (Pitfalls 1, 2, 8, 10 + checklists)
- https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html — TimeSeriesSplit semantics (expanding supersets, gap, test_size)
- https://scikit-learn.org/stable/modules/cross_validation.html — KFold/ShuffleSplit invalid on autocorrelated series
- https://archive.ics.uci.edu/dataset/374/appliances%2Benergy%2Bprediction — 19,735 rows, 10-min, 4.5 mo, 28 features, no missing, rv1/rv2 probes

### Secondary (MEDIUM confidence)
- TF 2.22.0-rc0 CPU import verified live this session (Windows, Py3.14.6); sklearn 1.8.0 verified
- Weng et al. (2026) random-split inflation 0.95+ → 0.61–0.88; Bergmeir (2023) naive-benchmark necessity (via PITFALLS.md)

### Tertiary (LOW confidence)
- LSTM-vs-HistGB payoff on this data (literature says expect tie-or-loss; tie rule handles it)
- UCI adapter horizon-step mapping details (planner discretion)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — sklearn HistGB/RF + TF CPU + stdlib fetch; all installed/importable this session
- Walk-forward/leakage protocol: HIGH — TimeSeriesSplit docs + repo grep-gate precedent
- C4 control law: HIGH — exact C3/harness signatures quoted; law is a thin overlay
- UCI adapter: MEDIUM — schema verified from UCI page; resampling choices are planner discretion
- LSTM payoff: LOW — honestly capped via tie rule + time box

**Research date:** 2026-09-29
**Valid until:** 30 days (stable APIs; re-verify TF 2.22 final on release)
