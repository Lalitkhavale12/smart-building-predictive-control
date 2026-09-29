# Phase 1: Simulator + Evaluation Foundation - Context

**Gathered:** 2026-09-29
**Status:** Ready for planning

## Phase Boundary

Reproducible multi-room RC-thermal simulator with seeded CSV logging, comfort metric, and hourly carbon/ToU series. No MQTT, no ML, no controllers yet — this phase builds the physics + evaluation foundation every later phase consumes. First kWh number comes in Phase 3.

## Implementation Decisions

[--auto] Selected all gray areas: Thermal model, Rooms & timestep, Seeding & reproducibility, Carbon/ToU series, Comfort metric, CSV schema.

### Thermal model
- **D-01:** 1R1C per room in pure NumPy: `T_in += dt/C*((T_out-T_in)/R + Q_occ + Q_hvac)` — start simple, spike 2R2C only if pull-down looks wrong
- **D-02:** [auto] Thermal model — Q: "1R1C or 2R2C?" → Selected: "1R1C" (recommended default)
- **D-03:** HVAC as discrete levels (OFF/reduced/ON) with fixed Q_hvac per level, plus occupancy heat gain Q_occ per person

### Rooms & timestep
- **D-04:** 4 rooms (class/office pattern), 1-min sim timestep (1440 steps/day), control hook every 5 min for later phases
- **D-05:** [auto] Timestep — Q: "1-min or 5-min?" → Selected: "1-min sim, 5-min control hook" (recommended default)
- **D-06:** Outdoor temp = daily sinusoid + heatwave offset param + seeded noise; humidity random-walk bounded 30-70%

### Seeding & reproducibility
- **D-07:** `numpy.random.Generator(PCG64(seed))` everywhere, seed passed via CLI/config; same seed = identical CSV byte-for-byte
- **D-08:** [auto] Seeds — Q: "Seed plumbing?" → Selected: "Explicit seed arg + ≥5 paired seeds in eval helper" (recommended default)

### Carbon/ToU series
- **D-09:** Hourly emission factor + ToU tariff series built in Phase 1 as CSV (CEA India annual figure + transparent daily shape assumption, documented in code comment); carbon shifting itself claimed in Phase 5
- **D-10:** [auto] Carbon source — Q: "Hourly series now or later?" → Selected: "Build hourly series now, consume in Phase 5" (recommended default)

### Comfort metric
- **D-11:** Comfort = % occupied time with 22-26C AND 30-60% RH; computed per run, no comfort-blind tables allowed downstream
- **D-12:** [auto] Comfort band — Q: "22-26C / 30-60% RH?" → Selected: "Yes, guide default, confirm later" (recommended default)

### CSV schema & interface
- **D-13:** Per-step CSV: timestamp, room, T_in, T_out, RH, occupancy, HVAC_state, power_kW; summary helper gives mean±std over seeds
- **D-14:** Expose `sim.step(action)->obs` + `BasePolicy.step(obs)->action` stub interface now so Phase 3 baselines plug in without refactor

### the agent's Discretion
- Exact R/C values per room, Q_hvac sizing, file layout under `sim/` — pick boring standard values, document pull-down/decay sanity numbers
- Library versions pinned at setup (Python 3.12, numpy 2.x, pandas 2.x, matplotlib 3.x)

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope
- `.planning/PROJECT.md` — core value, constraints, work split
- `.planning/REQUIREMENTS.md` — SIM-01..04 definitions
- `.planning/ROADMAP.md` Phase 1 — goal + 4 success criteria
- `smart_building_project_idea.md` — thermal equation, scenarios, comfort band

### Research
- `.planning/research/SUMMARY.md` — boring-first stack, build order physics→contract→loop
- `.planning/research/STACK.md` — Python 3.12 pin, numpy/pandas versions, what NOT to use
- `.planning/research/ARCHITECTURE.md` — emulator-controller split, build order, BasePolicy interface
- `.planning/research/PITFALLS.md` — equifinality, seed variance, comfort gating, hourly carbon requirement
- `.planning/research/FEATURES.md` — comparison harness as highest-leverage artifact

## Existing Code Insights

### Reusable Assets
- None — greenfield, no existing code

### Established Patterns
- Single-Python monolith (sim + later forecast + control in one loop), no Docker/TSDB/GPU

### Integration Points
- `sim/` output CSVs feed Phase 3 harness and Phase 4 forecaster; `topics.py` contract comes in Phase 2; no MQTT in this phase

## Specific Ideas

No specific requirements — open to standard approaches. Keep it boring and deterministic.

## Deferred Ideas

None — discussion stayed within phase scope. MPC/RL, Wokwi firmware, dashboard all deferred to their phases.

---

*Phase: 1-Simulator + Evaluation Foundation*
*Context gathered: 2026-09-29*
