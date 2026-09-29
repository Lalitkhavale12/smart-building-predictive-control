# Phase 03: Baselines + Comparison Harness — Research

**Researched:** 2026-09-29
**Domain:** Rule-based HVAC baselines + experiment harness (pure Python/numpy/pandas/matplotlib, no ML, no broker in eval path)
**Confidence:** HIGH (all interfaces read from source this session; semantics anchored in locked CONTEXT decisions + project pitfalls literature)

## User Constraints (from 03-CONTEXT.md — locked, planner MUST honor)

- **C1** = time-of-day schedule per room type (classrooms ON 08:00–18:00 weekdays, office 09:00–18:00, lab blocks), OFF otherwise; weekends mostly OFF. Schedule lives in `ctrl/schedules.py`, never hardcoded in the policy.
- **C2** = OFF if room continuously empty for 15 min (15 steps at 1-min timestep), else ON at last occupied setpoint; per-room empty-timer inside the policy, reset on occupancy > 0; constructor param `vacancy_min=15`.
- **C3** = C2 rule + setback: empty → HVAC REDUCED for first 60 min, then OFF; occupied → ON.
- **Harness:** `ctrl/harness.py` `run_controller(policy, scenario, seeds) -> DataFrame`, drives `BuildingSim` **directly** (not over MQTT). Full matrix = 4 scenarios × 5 seeds × 3 controllers = 60 runs; must finish **< 5 min** or harness gets a `--quick` subset flag.
- **Paired seeds:** identical `PAIRED_SEEDS` (0–4) for every controller; report **mean±std**.
- **Metrics:** energy kWh, ToU cost Rs, CO₂ kg (hourly EF), comfort % via `sim/metrics.py` + `sim/grid.py`. **Every table carries the comfort column.**
- **Output:** `ctrl/compare.py` CLI (`--controllers c1,c2,c3 --scenarios weekday,weekend,heatwave --seeds 5`) → `results/comparison/summary.csv` + `fig_24h_profile.png` (matplotlib, C1 vs C2 vs C3 only; Pareto/ablation stay in Phase 5).
- **Determinism:** same seed + same controller = byte-identical CSV; test asserts rerun equality.
- **Agent's discretion (planner decides):** exact schedule tables, setback durations, figure styling, summary.csv column order. **Lights follow occupancy (ON iff occupied) for all three baselines** — document once.
- **Out of scope:** forecaster, C4, carbon-shifting claims (report the Phase-1 series only), Pareto/ablation figures.

## Goal

Implement C1/C2/C3 as `BasePolicy` subclasses plus a comparison harness that produces the project's **first kWh number** — a fair, comfort-gated, paired-seed side-by-side of three non-ML controllers. This is the hard gate: no C4 work until C1–C3 are merged. The harness is the **Phase-5 embryo**: Phase 5 adds C4 + ablations + Pareto on the same `run_controller` interface, so the interface must be C4-compatible from day one (i.e., accept `forecast=None, signals=None` passthrough without change).

## Key Questions (answered below)

1. What C1/C2/C3 semantics are fair-not-strawman, so a later C4 win is credible?
2. What does the harness matrix look like, and does 60 runs fit the < 5 min budget?
3. How are paired-seed statistics, cost/CO₂ joins, and comfort aggregation computed without re-implementing Phase-1 code?
4. What does the 24h-profile figure show, and what do the determinism + bridge-wiring tests assert?

## Findings

### F1. Grounded interfaces (read from source this session — planner inherits these verbatim)

**`BasePolicy`** (`sim/policy.py:13-21`):
```python
class BasePolicy(ABC):
    @abstractmethod
    def step(self, obs, forecast=None, signals=None):
        # obs: {room_id: {"T_in", "T_out", "RH", "occupancy", "power_kW"}}
        # Returns: {room_id: {"hvac": "OFF"|"REDUCED"|"ON", "light": 0|1}}
```
C1–C3 subclass this with the **exact** signature; `forecast`/`signals` default `None` and are ignored (C4 will use them later — the harness passes them through untouched, which is what makes ablations flag-flips in Phase 5). Policies treat `obs` as read-only, never touch sim internals (`tests/test_boundaries.py` enforces the split).

**`BuildingSim`** (`sim/simulator.py:51-65`):
```python
def reset(self, seed=None, scenario=None): ...  # returns initial obs; reseeds RNG iff seed given
def step(self, action): ...                     # advances exactly 1 minute; returns obs dict
```
Copy the loop pattern from `sim/run.py:40-54`: `reset(seed)` → initial `policy.step(obs)` → per step, re-query policy every `CONTROL_HOOK_STEPS` (== 5, `sim/config.py:10`) steps, hold action between → `sim.step(action)` → `TelemetryLogger.record(step, room, obs[room], action[room])`. Harness reuses `TelemetryLogger` + `sim_timestamp` so per-run CSVs are schema-identical to Phase-1 output (`TELEMETRY_COLUMNS` order in `sim/logger.py:21-24`, `%.4f` floats, sim-time ISO stamps from `RUN_START` 2026-01-15).

**Constants to import, never re-hardcode:** `ROOMS` (4 rooms, `config.py:14`), `Q_HVAC = {"OFF": 0.0, "REDUCED": -1.2, "ON": -3.5}` kW (`config.py:43`), `PAIRED_SEEDS = [0,1,2,3,4]` (`config.py:77`), `SCENARIOS` (`config.py:74`), `TIMETABLES` weekday/weekend blocks (`config.py:85-122`), comfort band 22–26 °C / 30–60 %RH (`config.py:59-60`), `STEPS_PER_DAY = 1440` (`config.py:11`).

**Metrics reuse (do not reimplement):** `comfort_pct(frame)` / `energy_kwh(power_kw)` / `room_stats(frame)` from `sim/metrics.py:32-53`; `summarize()` pattern (mean±std with `ddof=1`, `nanmean`/`nanstd` for comfort) from `sim/summary.py:19-55`. **No scalar emission constant anywhere** — carbon/cost come only from `data/grid_hourly.csv` via `sim/grid.py::hourly_rows()` (24 rows: `hour, ef_kg_per_kwh, price_rs_per_kwh`; mean EF 0.710 anchored to CEA v21.0).

**Bridge interface for the wiring test only** (`iot/bridge.py:37-58`): `TelemetryBridge(sim, policy, client_factory=...)` + `tick()` = drain → `BasePolicy.step` → publish QoS-1 commands → `BuildingSim.step`. Reuse the `FakeBroker` test-double pattern from `tests/test_bridge.py` / `tests/test_faults.py` — no real broker in tests.

### F2. Baseline semantics that are fair-not-strawman (literature-anchored)

The pitfall being dodged is PITFALLS Pitfall 8: beating only a fixed schedule with 30–40% while a ₹200 timer switch captures most of it. The credibility rule (from project SUMMARY): **headline = savings-over-strongest-baseline (C3), never savings-over-fixed**. Each baseline below is the standard representative of its control family, not a weakened version:

**C1 fixed-schedule (the "traditional" family).** Wall-clock schedule per room type in `ctrl/schedules.py`, using the same day-type vocabulary as sim (`weekday/weekend/heatwave`; heatwave reuses weekday occupancy — `config.py:126-131`). Prescribed tables (agent's discretion, but start here): classrooms ON 08:00–18:00, office 09:00–18:00, lab ON during its four blocks (09:30–11:00, 12:30–14:00, 15:00–17:30, 18:00–20:00); OFF otherwise; weekend all OFF except classroom_A 10:00–14:00 (mirrors the weekend timetable, `config.py:116-121`). Deliberately **no gap-skipping** between class blocks — conditioning empty rooms 11:15–11:30 is exactly the waste C2/C3 must beat, and it is what real fixed schedules do. Anchor: ASHRAE Ch. 65 / ENERGY STAR SHEMS time-of-day scheduling as the industry default being displaced.

**C2 occupancy-rule with 15-min vacancy delay (the "reactive" family).** Per-room empty counter inside the policy; `occupancy > 0` → ON + reset counter; else increment and output OFF only once counter ≥ `vacancy_min` (default 15). **Critical hook subtlety:** the policy is called every 5 sim-minutes (`CONTROL_HOOK_STEPS`), so the counter must accumulate **sim-minutes (+= 5 per call)**, not policy calls — counting calls makes the real delay 75 min. Constructor takes `vacancy_min=15` (minutes, converted internally). The 15-min delay is the anti-short-cycling hysteresis real thermostats use (deadband equivalent); document it as such. Anchor: LBNL occupancy-control field evaluations; UCSD BuildSys savings figures — this is the strong baseline the headline is measured against.

**C3 setback (the "common practical strategy" family).** C2 logic + two-stage vacancy response: empty < 60 min → REDUCED (−1.2 kW vs ON −3.5 kW, i.e. ~1/3 capacity); empty ≥ 60 min → OFF; occupied → ON. Why 60 min is principled, not arbitrary: room τ ≈ 3.6 h (`config.py:38`); one hour of REDUCED holds the room within fast-recovery reach of the comfort band while OFF lets it drift — the recovery-vs-saving tradeoff the future Pareto curve will characterize. Anchor: Verdant/commercial setback references; Bursill sMPC finding (simplified predictive rules capture 94–95% of full MPC savings) — C3 is the "good engineer without ML" ceiling.

**Lights (all three):** ON iff currently occupied (`light = 1 if obs[room]["occupancy"] > 0 else 0`). No vacancy delay on lights — lighting has no thermal inertia, instant-off is free savings with zero comfort cost. Document once in `ctrl/` module docstring.

**What "fair" means for the planner:** C2/C3 read only current `occupancy` from obs (no future timetable peeking — that would be C4's job and would leak). C1 reads only wall-clock minute (derive from a step counter the harness passes, or `sim.minute`). None of the three uses `forecast`/`signals`.

### F3. Harness matrix design + measured runtime budget

**Function:** `run_controller(policy, scenario, seed, days=1) -> (telemetry_df, per_run_metrics)` in `ctrl/harness.py`; the CONTEXT `seeds` (plural) form loops `PAIRED_SEEDS` and returns one DataFrame with a row per (controller, scenario, seed). Drive `BuildingSim` directly — MQTT roundtrip already proven in Phase 2; the bridge path is asserted by exactly one wiring test, never used for eval.

**Matrix:** controllers {C1, C2, C3} × scenarios {weekday, weekend, heatwave, exam-day} × seeds {0–4} = **60 runs** (CONTEXT D-07). Note: `exam-day` currently returns weekday blocks (stub, `config.py:124-125`) — include it in the matrix for interface completeness but expect near-duplicate-of-weekday numbers; do NOT claim it as an independent scenario in any table label. The `compare.py` default CLI subset is `--scenarios weekday,weekend,heatwave` (45 runs); full 60 via explicit `--scenarios all`.

**Measured runtime (this session, machine Python 3.14, AlwaysOff 1-day run): 0.23 s/run → 60 runs ≈ 14 s** of pure sim. Add CSV write + metrics/grid joins + figure render: budget **< 2 min total**, comfortably inside the < 5 min gate (CONTEXT D-14). **No `--quick` flag needed at this scale** — but keep the per-(controller,scenario,seed) loop resumable by writing one CSV per run (`results/comparison/<controller>/<scenario>/seedNN/telemetry.csv` mirroring the Phase-1 `results/<scenario>/seedNN` layout), so a crash loses nothing (PITFALLS Performance-Traps: checkpoint per run, never one monolithic process).

**Per-run metric computation (all joins on sim-time hour):**
1. `energy_kwh` = `metrics.energy_kwh` summed over 4 rooms (power_kW → ×1/60 h).
2. `cost_rs` = Σ per-minute `power_kW/60 × price_rs_per_kwh[hour]`; `co2_kg` = Σ per-minute `power_kW/60 × ef_kg_per_kwh[hour]`; hour from timestamp, price/EF from `grid.hourly_rows()`. (Phase 1 built the series; Phase 3 only *reports* it — no shifting claims.)
3. `comfort_pct` per room via `metrics.comfort_pct` (NaN if room never occupied — weekend empty rooms); **building comfort = occupied-step-weighted mean across rooms, not naive mean of per-room %** (a room occupied 1 h must not count equally with one occupied 9 h; `summary.py`'s `nanmean` is per-room-display only).
4. `saved_pct_vs_c1` = 100 × (E_C1 − E_Cx)/E_C1 computed **within the same (scenario, seed) pair**, then aggregated.

**Aggregation:** group by (controller, scenario) over 5 paired seeds → mean±std (`ddof=1`, the `summary.py` convention) for energy, cost, CO₂, comfort, saved-%. Paired seeds are what make the comparison a paired design (PITFALLS Pitfall 3: ≥5 seeds, same seeds every controller, never a bare %).

**`summary.csv` columns** (prescriptive starting order; planner may adjust): `controller, scenario, n_seeds, energy_kwh_mean, energy_kwh_std, saved_pct_vs_c1_mean, saved_pct_vs_c1_std, cost_rs_mean, cost_rs_std, co2_kg_mean, co2_kg_std, comfort_pct_mean, comfort_pct_std`. Comfort column in **every** row — comfort-blind tables are a gate failure (PITFALLS Pitfall 5; CTL-06 groundwork).

### F4. 24h-profile figure design (the only figure this phase)

`results/comparison/fig_24h_profile.png`, matplotlib (already installed 3.10.8 — no new packages). Specification:
- **Panel:** weekday scenario, seed 0 (representative; label seed explicitly — never present one seed as the average).
- **X:** hour 0–24. **Left Y:** total building power kW (4 rooms summed, hourly-mean resampled from 1-min telemetry — 1440 points plotted raw is visual noise). **Three lines:** C1, C2, C3 (distinct colors + legend, line width ≥ 1.5 for report readability).
- **Right twin Y:** total building occupancy (shaded area or step line, light gray) — shows *why* curves differ (C1 flat-ON through gaps vs C2/C3 tracking occupancy).
- Title/labels/units mandatory; expected story the figure must show: C1 rectangular block 08–18, C2/C3 dipping in class gaps + lunch, C3 slightly above C2 during first vacancy hour (REDUCED vs OFF). If the figure does not show this, the controllers are miswired — treat as a smoke check, not styling.
- Pareto, savings-bars, cumulative-CO₂, ablation figures are **Phase 5** — do not build them here.

### F5. Determinism test design

`tests/test_harness.py::test_rerun_byte_identical`: `run_controller(C2, "weekday", seed=2)` twice → `DataFrame.equals` on both telemetry frames (mirrors `seeds_equal` in `simulator.py:33-37`) **and** byte-identical CSV bytes when written with `float_format="%.4f"` (the Phase-1 `fc /b` convention). Rationale: fixed RNG consumption order (`simulator.py:7-13`) + sim-time stamps make this structural, not aspirational. One controller/scenario/seed suffices per CONTEXT D-13; parametrize over all three controllers if free (cheap: 0.23 s each).

### F6. Bridge wiring test design

`tests/test_policy_bridge.py::test_c_policy_behind_bridge`: one C-policy (C2, the stateful one — exercises the most interface surface) driven through `TelemetryBridge.tick()` with the `FakeBroker` double from Phase-2 tests for 30 sim-minutes on weekday seed 0 → assert (a) no exception, (b) `sim.minute` advanced, (c) published commands contain only valid `hvac ∈ {OFF, REDUCED, ON}` / `light ∈ {0,1}`. This is a **compatibility assertion, not the eval path** — it proves C-policies also run behind `iot/bridge.py` (Phase-2 contract: QoS-1 absolute-setpoint commands, idempotent duplicates). Do not run the 60-run matrix through the bridge.

### F7. Don't hand-roll / reuse checklist

| Need | Don't build | Reuse |
|------|-------------|-------|
| Per-run energy/comfort | New math | `sim/metrics.py` (`energy_kwh`, `comfort_pct`, `room_stats`) |
| Mean±std over seeds | New stats helper | `sim/summary.py::summarize` convention (`ddof=1`, `nanmean`/`nanstd`) |
| EF/ToU series | Any constant factor | `sim/grid.py::hourly_rows()` + `data/grid_hourly.csv` (grep-test: no scalar `EMISSION_FACTOR` may appear in `ctrl/`) |
| Run loop + CSV schema | New loop/columns | `sim/run.py::run` structure + `TelemetryLogger` (`TELEMETRY_COLUMNS` order, `%.4f`, sim-time stamps) |
| Fake broker in tests | New MQTT double | Phase-2 `FakeBroker` + `MqttClientWrapper` factory injection |
| Plotting library | New dep (plotly etc.) | matplotlib (installed); plotly/Streamlit are Phase 6 |

No new pip packages this phase: stdlib + numpy/pandas/matplotlib only. (Env note: machine runs Python 3.14; sim emits a version warning but runs — the 3.12 pin is a team-venv concern from 01-03, unaffected by this phase since no TF/sklearn is imported.)

## Risks

| # | Risk | Likelihood / Impact | Mitigation (cheap, in-phase) |
|---|------|---------------------|------------------------------|
| R1 | **Vacancy timer counted in policy calls, not minutes** → C2/C3 delay becomes 75 min, baselines look strawman-weak and C4's later win is vacuous | High / High | Counter accumulates `CONTROL_HOOK_STEPS` (5) sim-minutes per call; unit test: room emptied at t → OFF/REDUCED exactly `vacancy_min` sim-minutes later |
| R2 | **C2/C3 peek at timetable or future occupancy** (e.g., importing `TIMETABLES` for control, not just C1's wall-clock) → reactive baselines inflated, forecast ablation in Phase 4 meaningless | Medium / High | Code-review rule: C2/C3 may read only current `obs["occupancy"]`; `TIMETABLES` import allowed only in `schedules.py` (C1) |
| R3 | **Comfort reported as naive mean of per-room %** → weekend single-room comfort misweighted; comfort-blind-equivalent claim | Medium / Medium | Building comfort = occupied-step-weighted mean; keep per-room columns alongside |
| R4 | **exam-day mistaken for independent scenario** (stub = weekday blocks) → duplicated numbers presented as generality | Medium / Medium | Label stub honestly; default CLI excludes it; real timetable is later-phase work |
| R5 | **summary.csv without comfort column or single-seed headline** → Pitfalls 3/5 trip at the gate | Low / High | Schema test asserts comfort columns present + `n_seeds == 5`; CLI prints mean±std, never bare % |
| R6 | **Harness interface not C4-compatible** → Phase 4 rewrites the harness instead of reusing it | Low / High | `run_controller` accepts and forwards `forecast`/`signals` kwargs today (ignored by C1–C3); Phase-5-embryo review checks C4 can plug in with zero harness edits |

## Open Questions

1. **C1 lab evening block (18:00–20:00)?** The lab timetable has an evening session; whether C1's fixed schedule covers it is agent's-discretion schedule detail. Recommendation: ON (a fixed schedule would cover the booked block) — planner decides, document the choice.
2. **Heatwave C1 behavior?** Schedule is wall-clock so C1 is identical in heatwave except physics response; comfort will likely crater. Recommendation: report as-is — it is the honest "traditional control under stress" data point Phase 5's Pareto needs.
3. **Cost/CO₂ joins when telemetry spans midnight?** 1-day runs stay within one date; multi-day (`--days N`) hour-mapping is modulo-24 on sim-time. Recommendation: implement hour join as `timestamp.hour`, which is day-agnostic by construction.

## Sources

- **Primary (HIGH — read this session):** `sim/policy.py:13-21` (BasePolicy contract), `sim/simulator.py:40-92` (reset/step, RNG order), `sim/config.py` (all constants: Q_HVAC:43, PAIRED_SEEDS:77, TIMETABLES:85-122, comfort band:59-60), `sim/metrics.py` + `sim/summary.py` (scoring/aggregation), `sim/grid.py` + `data/grid_hourly.csv` (hourly EF/ToU), `sim/run.py:40-58` (loop pattern), `sim/logger.py:21-33` (schema/stamps), `iot/bridge.py:37-58` (wiring-test interface), 03-CONTEXT.md (all locked decisions D-01–D-14).
- **Secondary (MEDIUM — project research):** PITFALLS.md Pitfalls 3/5/8 (paired seeds, comfort gating, strawman baselines), SUMMARY.md Phase-3 section (harness as highest-leverage artifact, build-order rationale), 01-03-SUMMARY.md (grid/logger/metrics interfaces + AlwaysOff sanity behavior), 02-02-SUMMARY.md (bridge tick semantics + FakeBroker test pattern).
- **Tertiary (LOW — anchors for report prose, not code):** ASHRAE Ch. 65 / LBNL occupancy-control field studies / Bursill sMPC 94–95% figure via SUMMARY.md citations; MSEDCL slab semantics via `grid.py` header comment (CEA v21.0 FY24-25 anchor 0.710).

## Metadata

- **Standard stack:** HIGH — zero new packages; every module reused is on disk and read this session.
- **Architecture:** HIGH — harness-as-Phase-5-embryo and direct-sim-eval vs bridge-compat-test split follow locked CONTEXT + established Phase 1/2 patterns.
- **Pitfalls:** HIGH — the three phase-killing pitfalls (strawman baselines, single-seed, comfort-blind) each have a named test/schema mitigation above.
- **Runtime budget:** VERIFIED by measurement — 0.23 s/1-day run on this machine → 60 runs ≈ 14 s sim + overhead, < 2 min total vs the 5-min gate.
- **Valid until:** 30 days (stable foundations; interfaces pinned by Phase 1/2 summaries).
