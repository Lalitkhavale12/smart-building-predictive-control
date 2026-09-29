---
phase: 01-simulator-evaluation-foundation
plan: 03
subsystem: simulation
tags: [csv-logging, cli-runner, comfort-metric, carbon-series, tou-tariff, eval-harness, pytest]

# Dependency graph
requires:
  - 01-01 (BuildingSim reset/step, config pins, boundary guard)
  - 01-02 (scenario timetables, seeded weather, PAIRED_SEEDS)
provides:
  - sim/grid.py builder + data/grid_hourly.csv (24-row hourly EF/ToU, mean 0.710)
  - sim/logger.py schema-exact telemetry writer + run_meta.json
  - sim/run.py CLI (--scenario/--days/--seed/--out, 5-min control hold)
  - sim/metrics.py comfort + energy scoring, sim/summary.py multi-seed helper
  - tests/test_grid.py + tests/test_logging.py + tests/test_metrics.py
affects: [phase-03-baselines, phase-04-forecasting, phase-05-evaluation]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 5600
  tasks: 3
  commits: 0

# Tech tracking
tech-stack:
  added: []
  patterns: [mean-normalized hourly EF shape, sim-time ISO-8601 timestamps, results/<scenario>/seed<NN> layout, per-run/summary shared scoring path]

key-files:
  created: [sim/grid.py, data/grid_hourly.csv, sim/logger.py, sim/run.py, sim/metrics.py, sim/summary.py, tests/test_grid.py, tests/test_logging.py, tests/test_metrics.py]
  modified: []

key-decisions:
  - "EF hour-class leftovers (06-09 + 17) share the morning x0.95 multiplier so all 24 hours are covered with no overlap"
  - "run() uses the public reset() return as initial obs; no private-method calls from the CLI layer"
  - "AlwaysOff 5-seed means (~33-54 C) accepted as model-correct, not tuned — sealed hot rooms overheat without cooling, which is why control matters"
  - "Did not touch the working Python 3.14 env; zero installs (pytest/numpy/pandas reused as-is)"

patterns-established:
  - "No scalar emission constant anywhere in sim/ (grep-test enforced); grid series is the only carbon source"
  - "--out constrained under results/ with traversal rejection (threat T-03-01, test-enforced)"
  - "summary.py scores via metrics.py on the same CSVs, so per-run and multi-seed numbers share one code path"

requirements-completed: [SIM-03, SIM-04]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "grid_hourly.csv 24 rows, mean EF 0.710 +- 0.001, evening peak above solar dip, no scalar EF, builder reproduces CSV"
    requirement: "SIM-03"
    verification:
      - kind: unit
        ref: "tests/test_grid.py (5 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "One CLI command writes schema-exact telemetry.csv (5760 rows/day) + run_meta.json; same-seed rerun byte-identical"
    requirement: "SIM-03"
    verification:
      - kind: integration
        ref: "tests/test_logging.py (4 tests) + python -m sim.run --scenario weekday --days 1 --seed 0"
        status: pass
    human_judgment: false
  - id: D3
    description: "Comfort pct correct on 6 synthetic cases incl. empty-room NaN; summarize() prints mean+-std over 5 seeds"
    requirement: "SIM-04"
    verification:
      - kind: unit
        ref: "tests/test_metrics.py (7 tests) + summarize('results/weekday') table"
        status: pass
    human_judgment: false
  - id: D4
    description: "No Plan 01/02 regressions; full suite green in under 60 s"
    requirement: "SIM-03"
    verification:
      - kind: unit
        ref: "pytest tests/ -q (27 passed in 7.96 s)"
        status: pass
    human_judgment: false

# Metrics
duration: 40min
completed: 2026-09-29
status: complete
---

# Phase 01 Plan 03: Evaluation Record Summary

**CLI-to-CSV tracer slice live (5760 rows/day, byte-identical reruns), comfort scored from day one with empty-room NaN, hourly carbon/ToU series at CEA-anchored mean 0.710 — 27/27 tests green in 8 s**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-09-29 (session)
- **Completed:** 2026-09-29
- **Tasks:** 3/3
- **Files modified:** 9 created, 0 modified

## Accomplishments

- Carbon/ToU series: `sim/grid.py::hourly_rows/write_csv` + CLI (`--ef-base/--shape/--out`) writes `data/grid_hourly.csv` — 24 rows, EF mean 0.7100 (CEA v21.0 FY24-25 anchor), solar-dip 0.5789 vs evening-peak 0.8538 after mean-normalization, MSEDCL classic slabs (7.50/9.00/9.80/10.10 Rs/kWh). The module header carries the 4-point documented-assumptions comment (CEA source+year, modelled shape, average-not-marginal, MYT Phase-5 option). No `EMISSION_FACTOR = <number>` anywhere.
- Logger + CLI: `sim/logger.py` (`TELEMETRY_COLUMNS` in exact D-13 order, `RUN_START` 2026-01-15 sim epoch, `TelemetryLogger` with `%.4f` floats, `write_run_meta` with seed/git/config/versions) and `sim/run.py` (`--scenario/--days/--seed/--out`, `resolve_out` traversal guard, AlwaysOffPolicy with 5-step control hold). `python -m sim.run --scenario weekday --days 1 --seed 0` → 5760-row CSV + meta; `fc /b` rerun → no differences.
- Metrics + summary: `sim/metrics.py` (`comfort_flag/comfort_pct` on the locked 22–26 C / 30–60 % band with NaN-on-empty, `energy_kwh` at 1/60 h, `room_stats` triple) with the RH-noise + never-retune comment; `sim/summary.py::summarize` loads `seed*/telemetry.csv`, returns per-room mean±std (mean T_in, energy, comfort) and writes `summary.csv`. 5-seed weekday table prints with comfort column.
- Gates: `test_grid` 5/5, `test_logging` 4/4, `test_metrics` 7/7, full suite **27 passed in 7.96 s** (< 60 s budget), Plan 02 determinism still green.

## Task Commits

Per the execution request (implement, verify, write summary — no commit step), work is on disk uncommitted for review, matching the 01-01/01-02 convention:

1. **Task 1: Hourly carbon plus ToU series builder** — uncommitted (`sim/grid.py`, `data/grid_hourly.csv`, `tests/test_grid.py`)
2. **Task 2: CSV logger plus CLI runner end to end** — uncommitted (`sim/logger.py`, `sim/run.py`, `tests/test_logging.py`)
3. **Task 3: Comfort metric plus multi-seed summary helper** — uncommitted (`sim/metrics.py`, `sim/summary.py`, `tests/test_metrics.py`)

**Verification:** grid mean 0.7100042; CLI 5760 rows schema-exact; 5-seed `summarize()` table printed; `fc /b` byte-identical; `pytest tests/ -q` → 27 passed.

## Files Created/Modified

- `sim/grid.py` - Hourly EF/ToU builder (mean-normalized shape, MSEDCL slabs, assumptions header, CLI)
- `data/grid_hourly.csv` - 24 rows: hour, ef_kg_per_kwh, price_rs_per_kwh (mean EF 0.710)
- `sim/logger.py` - `TELEMETRY_COLUMNS`, sim-time stamps, `TelemetryLogger`, `write_run_meta`
- `sim/run.py` - CLI runner with `resolve_out` traversal guard + `run()` tracer loop
- `sim/metrics.py` - `comfort_flag/comfort_pct/energy_kwh/room_stats` on the locked band
- `sim/summary.py` - `summarize(scenario_dir)` mean±std DataFrame + summary.csv
- `tests/test_grid.py` - 24-row / mean / peak>dip / no-scalar / builder-reproduces tests
- `tests/test_logging.py` - schema order / 5760-row / 5-seed summary / traversal-reject tests
- `tests/test_metrics.py` - 6 comfort cases + energy-sum test
- `results/weekday/seed00-04/telemetry.csv + run_meta.json, results/weekday/summary.csv` - generated sample runs (on disk, untracked — see note below)

## Decisions Made

- EF hour-class leftovers (hours 06–09 + 17) share the morning x0.95 multiplier: the plan names 4 classes but not every hour, so night = 00–05, morning = 06–09 + 17, solar = 10–16, evening = 18–23 covers 24 with no overlaps; mean-normalization makes the exact partition mean-safe.
- `run()` takes its initial obs from the public `reset()` return (first draft called the private `_obs`; cleaned before verify — CLI must not reach into sim internals, same spirit as the D-14 boundary).
- AlwaysOff 5-seed means (classroom_A ~53.6 C, office ~33.5 C, comfort 0 %) accepted as model-correct: R = 30 + 30 occupants × 0.10 kW + Pune heat with zero cooling genuinely overheats sealed rooms (Plan 01 deviation-1 physics). No constant was touched to make tables prettier; Phase 3 controllers are exactly what brings these down.
- Reused the machine Python 3.14 env with zero installs; 3.12 pins remain a team-venv concern per 01-01.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two test-side assertion bugs (no source changes needed)**
- **Found during:** Task verify (`test_grid` + `test_metrics` first run: 10 passed, 2 failed)
- **Issue:** (a) `comfort_flag` on scalar inputs returns a 0-d numpy bool, so `.tolist() == [False]` failed — test bug, not source bug. (b) `energy_kwh` float sum `1.2000000000000002 != 1.2` — exact-equality on floats, test bug.
- **Fix:** (a) assert `not comfort_flag(...)`; (b) `pytest.approx`. Source modules untouched.
- **Files modified:** tests/test_metrics.py
- **Verification:** `pytest tests/test_grid.py tests/test_metrics.py -q` → 12 passed

**2. [Rule 1 - Bug] Timestamp assertion ignored 4-room row interleaving**
- **Found during:** `test_logging` first run (3 passed, 1 failed)
- **Issue:** each step writes 4 room-rows sharing one stamp, so `iloc[1]` is still step 0 — the test wrongly expected step 1.
- **Fix:** assert `iloc[4] == 2026-01-15T00:01:00` plus `nunique() == 1440` (stronger: pins one-stamp-per-step for the whole day).
- **Files modified:** tests/test_logging.py
- **Verification:** `pytest tests/test_logging.py -q` → 4 passed

---

**Total deviations:** 2 auto-fixed (both test-side; all plan constants byte-faithful)
**Impact on plan:** All must-have truths hold; verify gates pass as written.

## Issues Encountered

- PowerShell 5.1 rejects `&&` chaining — used `;` sequencing (same as Plan 02 note).
- A stray `Diff-Item() { }` fragment broke one Bash call (parser error, no side effects); reran without it.

## Known Stubs

None — every file created is wired and exercised. `results/` sample runs are generated output, not stubs.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary changes. `run_meta.json` holds git hash + package versions only (never keys). No new packages (threat T-01-SC unchanged from Plan 01 audit); T-03-01 (`--out` traversal) mitigated in `resolve_out` and test-pinned (`test_out_traversal_rejected`).

## User Setup Required

None. Note: `results/` (sample telemetry + meta + summary.csv) is on disk untracked — generated experiment output, deliberately left for the phase gate ("sample CSV present"). If the team wants it out of `git status`, add `results/` to `.gitignore` in a later phase (out of this plan's scope).

## Next Phase Readiness

- Phase 1 exit gate is GREEN: physics (01-01) + stochastic world (01-02) + evaluation record (this plan) = reproducible CSVs, comfort from day one, carbon series ready.
- Phase 3 baselines plug into `BuildingSim.step` + `BasePolicy` unchanged; `PAIRED_SEEDS` + `summarize()` are the paired-comparison harness embryo; Phase 5 consumes `data/grid_hourly.csv` (flat-vs-varying hook) and the ±1 C comfort sensitivity.
- Carry-forward: 01-01 pull-down band sign-off (13 vs 20–35 min) still needs human/verifier decision; `results/` gitignore decision pending (above).

## Self-Check: PASSED

- sim/grid.py, sim/logger.py, sim/run.py, sim/metrics.py, sim/summary.py, data/grid_hourly.csv, tests/test_grid.py, tests/test_logging.py, tests/test_metrics.py — all FOUND on disk
- `pytest tests/ -q` → 27 passed (re-run after SUMMARY authored: green — see below)

---
*Phase: 01-simulator-evaluation-foundation*
*Completed: 2026-09-29*
