# Phase 03 Plan 02: C3 Setback + Comparison Harness Summary

**Status:** complete — C3 setback (CTL-03) plus `run_controller` / `compare.py`
harness producing the project's first kWh comparison: C1 vs C2 vs C3 over
3 scenarios × 5 paired seeds, with comfort in every row.

## What Was Built

- `ctrl/baselines.py` — `SetbackPolicy` (C3, D-05/D-06): identical sim-minute
  vacancy counter to C2 (`vacancy_min=15`), two-stage response — empty <
  15 min ON (hold), 15–60 min REDUCED (−1.2 kW vs ON −3.5 kW), ≥ 60 min OFF,
  occupied ON. 60-min setback grounded in room tau 3.6 h (BASE_TAU_HOURS).
  Lights follow current occupancy (all baselines).
- `ctrl/harness.py` — `run_controller(policy, scenario, seed, days=1,
  forecast=None, signals=None) -> (telemetry_df, per_run_metrics)`: drives
  `BuildingSim` directly (run.py loop pattern, CONTROL_HOOK_STEPS hold,
  TelemetryLogger.record sorted ROOMS → schema-identical CSVs: 1440×4 rows,
  TELEMETRY_COLUMNS order, %.4f, sim-time stamps). Forwards forecast/signals
  into every policy.step call (C4 plugs in with zero edits). Metrics:
  energy via metrics.energy_kwh; cost/CO2 via per-minute power/60 joined to
  grid.hourly_rows() on timestamp.hour (day-agnostic); comfort as the
  occupied-step-weighted mean across rooms (NaN rooms zero weight).
- `ctrl/compare.py` — CLI (`--controllers/--scenarios/--seeds`, `--scenarios
  all` for the exam-day stub; default excludes it): paired-seed matrix reusing
  PAIRED_SEEDS identically per controller, crash-resumable per-run CSVs under
  `results/comparison/<controller>/<scenario>/seedNN/` (traversal-guarded),
  `summary.csv` with all 13 columns (mean±std ddof=1, saved_pct paired within
  (scenario,seed)), `fig_24h_profile.png` (matplotlib only: 3 power lines
  lw=2.0 + occupancy twin-axis shade, weekday seed 0). Prints mean±std only.
- `tests/test_harness.py` — C3 one-day schema/metrics, REDUCED-vs-OFF at
  30-min vacancy, OFF at 60 min, rerun byte-identical ×3 controllers
  (DataFrame.equals + CSV bytes), no-scalar-carbon grep gate on ctrl/.
- `tests/test_policy_bridge.py` — C2 driven 30 sim-min through
  TelemetryBridge.tick() with FakeBroker: no exception, sim.minute == 30,
  every published command hvac ∈ {OFF,REDUCED,ON} / light ∈ {0,1}.

## Measured kWh Table (default matrix, 5 paired seeds)

| controller | scenario | energy kWh | saved % vs C1 | cost Rs | CO2 kg | comfort % |
|------------|----------|------------|---------------|---------|--------|-----------|
| c1 | weekday | 48.433±0.116 | 0.0±0.0 | 450.10±1.06 | 30.05±0.07 | 1.3±1.2 |
| c2 | weekday | 43.242±0.774 | 10.7±1.4 | 403.66±7.12 | 26.92±0.46 | 3.8±1.3 |
| c3 | weekday | 46.015±0.640 | 5.0±1.1 | 429.76±5.87 | 28.77±0.38 | 3.8±1.3 |
| c1 | heatwave | 48.433±0.116 | 0.0±0.0 | 450.10±1.06 | 30.05±0.07 | 3.4±1.5 |
| c2 | heatwave | 43.242±0.774 | 10.7±1.4 | 403.66±7.12 | 26.92±0.46 | 5.2±2.1 |
| c3 | heatwave | 46.015±0.640 | 5.0±1.1 | 429.76±5.87 | 28.77±0.38 | 2.5±1.1 |
| c1 | weekend | 5.450±0.026 | 0.0±0.0 | 51.29±0.25 | 3.17±0.02 | 1.9±2.1 |
| c2 | weekend | 5.547±0.180 | −1.8±2.8 | 51.97±1.68 | 3.21±0.10 | 3.1±2.8 |
| c3 | weekend | 5.847±0.180 | −7.3±2.8 | 54.67±1.68 | 3.39±0.10 | 3.1±2.8 |

Figure story verified numerically (weekday seed 0): C1 rectangular block from
08:00, C2/C3 from 0.0 at 07:00 tracking occupancy, C3 ≥ C2 in gap hours
11–13 (REDUCED vs OFF), C2 below C1 at lunch. Weekend C2/C3 deficit is the
honest post-block hold penalty (C3 REDUCED 60 min after the last class vs
C1's sharp OFF) — paired-seed significant, kept as-reported; motivates C4.

## Test Results

- `tests/test_harness.py` + `test_policy_bridge.py` + `test_baselines.py`: 19 passed.
- Full suite `tests/`: 70 passed, 2 skipped (pre-existing skips).
- Default 45-run matrix: 16.8 s (gate < 5 min). Subset CLI + figure verified.
- `results/comparison/summary.csv` (13 cols, n_seeds == 5, comfort non-missing)
  + `fig_24h_profile.png` present on disk (`results/` gitignored, not committed).

## Deviations

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Long-vacant initial condition
for C2/C3 vacancy timers**
- **Found during:** full-matrix review (weekend C3 −36% vs C1)
- **Issue:** unseen-room timers defaulted to 0 ("just became empty"), so every
  run opened with all 4 rooms hold-ON 15 min (C2) / ON 15 min + REDUCED 45 min
  (C3) at midnight — physically wrong (rooms vacant for hours) and dominant in
  low-energy scenarios.
- **Fix:** unseen rooms default to `vacancy_min` (C2) / `setback_min` (C3):
  first empty observation yields OFF. Occupied observations still reset to 0;
  all 03-01 timing tests unaffected.
- **Files modified:** ctrl/baselines.py
- **Commit:** 693cd4b
- Residual weekend deficit (−1.8%/−7.3%) is genuine hold behavior, reported as-is.

**2. [Rule 3 - Blocking] `python ctrl/compare.py` import failure**
- **Issue:** script-dir (`ctrl/`) on sys.path, not repo root → `No module named 'ctrl'`.
- **Fix:** 3-line sys.path root bootstrap at top of compare.py (plan invokes it
  as `python ctrl/compare.py`, not `-m`).
- **Commit:** 2cdbf3f

## Threat Flags

None — no new surface beyond the plan's threat model (T-03-04 mitigated by
resolve_run_dir traversal guard; T-03-05 hour join day-agnostic, determinism
test byte-catches drift; T-03-06 CLI prints mean±std only, schema has
n_seeds == 5; T-03-07 exam-day excluded by default; T-03-SC zero new packages).

## Commits

- e500e6a feat(03-02): C3 setback policy plus run_controller harness
- 2cdbf3f feat(03-02): compare.py CLI with paired-seed matrix + 24h figure
- bd0d8eb test(03-02): determinism, bridge-wiring and no-scalar-carbon gates
- 693cd4b fix(03-02): long-vacant initial condition for C2/C3 timers

## Self-Check: PASSED

All files exist (ctrl/harness.py, ctrl/compare.py, tests/test_harness.py,
tests/test_policy_bridge.py, results/comparison/summary.csv +
fig_24h_profile.png); all four commits verified via `git log`.
