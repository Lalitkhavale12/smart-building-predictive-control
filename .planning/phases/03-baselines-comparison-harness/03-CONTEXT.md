# Phase 3: Baselines + Comparison Harness - Context

**Gathered:** 2026-09-29
**Status:** Ready for planning

## Phase Boundary

Three non-ML baseline controllers (C1 fixed-schedule, C2 occupancy-rule, C3 setback) implemented as `BasePolicy` subclasses plus one comparison harness that runs any controller over scenarios × seeds and reports kWh, saved %, cost, CO₂ and comfort side-by-side with a 24h-profile comparison. First kWh number lands here. No forecaster, no C4, no carbon shifting claims — the harness only reports the series Phase 1 built. This is the hard gate: no C4 work until C1–C3 are merged.

## Implementation Decisions

[--auto] Selected all gray areas: Controller semantics, Harness shape, Metrics, Comparison output, Determinism.

### C1 fixed-schedule
- **D-01:** C1 = time-of-day schedule per room type (classrooms ON 08:00–18:00 weekdays, office 09:00–18:00, lab blocks), OFF otherwise; weekends mostly OFF. Schedule lives in `ctrl/schedules.py`, not hardcoded in policy
- **D-02:** [auto] Schedule source — Q: "Hardcoded or config?" → Selected: "Room-type tables in schedules.py, same day-type vocabulary as sim (weekday/weekend/heatwave)" (recommended default)

### C2 occupancy-rule
- **D-03:** C2 = OFF if room continuously empty for 15 min (15 steps at 1-min timestep), else hold last occupied setpoint (ON); per-room empty-timer state inside the policy, reset on occupancy > 0
- **D-04:** [auto] Vacancy threshold — Q: "15 min fixed or param?" → Selected: "15 min default, constructor param `vacancy_min=15`" (recommended default)

### C3 setback
- **D-05:** C3 = C2 rule + setback: when empty, HVAC to REDUCED instead of OFF for the first 60 min (fast recovery), OFF after; occupied → ON. Captures the "common practical strategy" without any prediction
- **D-06:** [auto] Setback depth — Q: "REDUCED then OFF?" → Selected: "Yes — REDUCED 60 min, then OFF; occupied always ON" (recommended default)

### Harness shape
- **D-07:** `ctrl/harness.py` `run_controller(policy, scenario, seeds) -> DataFrame`: drives `BuildingSim` directly (not over MQTT — MQTT roundtrip already proven in Phase 2; harness needs speed for 4 scenarios × 5 seeds × 3 controllers = 60 runs)
- **D-08:** [auto] Harness path — Q: "Through MQTT bridge or direct sim?" → Selected: "Direct sim.step for speed; bridge compatibility asserted by one wiring test (policy works behind bridge too)" (recommended default)
- **D-09:** Paired seeds: identical `PAIRED_SEEDS` (0–4) reused for every controller so comparisons are paired, reported as mean±std

### Metrics & output
- **D-10:** Per-run metrics via `sim/metrics.py` + `sim/grid.py`: energy kWh, ToU cost Rs, CO₂ kg (hourly EF), comfort % — every table carries the comfort column, no comfort-blind claims
- **D-11:** `ctrl/compare.py` CLI: `--controllers c1,c2,c3 --scenarios weekday,weekend,heatwave --seeds 5` → `results/comparison/summary.csv` + `fig_24h_profile.png` (matplotlib, baseline side-by-side)
- **D-12:** [auto] First figure — Q: "Which graph now?" → Selected: "24h-profile C1 vs C2 vs C3 only; Pareto/ablation stay in Phase 5" (recommended default)

### Determinism
- **D-13:** Same seed + same controller = byte-identical CSV; harness test asserts rerun equality for one controller/scenario/seed
- **D-14:** [auto] Runtime — Q: "60 runs too slow?" → Selected: "1-day runs are seconds each; 60-run full matrix must finish < 5 min or harness gets a --quick subset flag" (recommended default)

### the agent's Discretion
- Exact schedule tables per room, setback durations, figure styling, summary.csv column order
- Light control in baselines: lights follow occupancy (ON iff occupied) for all three — document once

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope
- `.planning/PROJECT.md` — core value, hard gate (no C4 until C1–C3 merged)
- `.planning/REQUIREMENTS.md` — CTL-01..03 definitions
- `.planning/ROADMAP.md` Phase 3 — goal + 3 success criteria
- `smart_building_project_idea.md` — controllers compared table
- `.planning/phases/01-simulator-evaluation-foundation/01-CONTEXT.md` — comfort + CSV + seed decisions this harness consumes
- `.planning/phases/02-mqtt-pipeline-iot-contract/02-CONTEXT.md` — bridge/policy interface

### Research
- `.planning/research/SUMMARY.md` — baselines-before-C4 gate, comparison harness as highest-leverage artifact
- `.planning/research/FEATURES.md` — C1–C3 as table stakes, strawman-baseline pitfall
- `.planning/research/PITFALLS.md` — single-seed claims, comfort-blind savings, seeded harness ≥5 seeds
- `.planning/research/ARCHITECTURE.md` — emulator-controller split, BasePolicy.step() interface

## Existing Code Insights

### Reusable Assets
- `sim/policy.py` BasePolicy ABC + AlwaysOffPolicy — C1–C3 subclass it with the same `step(obs, forecast=None, signals=None)` signature
- `sim/simulator.py` BuildingSim — harness drives reset(seed)/step(action) directly
- `sim/metrics.py` comfort/energy + `sim/summary.py` summarize() — per-run scoring and mean±std
- `sim/grid.py` + `data/grid_hourly.csv` — hourly EF + ToU pricing for cost/CO₂ columns
- `sim/config.py` PAIRED_SEEDS, room list, timetables — schedules align to the same vocabulary

### Established Patterns
- Seeded RNG threading; byte-for-byte determinism; tests green (51 passed)
- `ctrl/` is a new package; future C4 lives here too

### Integration Points
- `ctrl/harness.py` is the Phase-5 embryo: Phase 5 adds C4 + scenarios × seeds × ablations × Pareto on the same interface
- One wiring test proves C-policies also run behind `iot/bridge.py` (Phase 2 compat, not the eval path)

## Specific Ideas

No specific requirements — standard baselines from the idea doc. Keep them dumb; their job is to be fairly beaten later.

## Deferred Ideas

None — discussion stayed within phase scope. C4/forecaster (Phase 4), carbon shifting claims + Pareto (Phase 5) untouched.

---

*Phase: 3-Baselines + Comparison Harness*
*Context gathered: 2026-09-29*
