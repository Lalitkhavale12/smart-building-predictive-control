---
phase: 05-carbon-economics-full-evaluation
plan: 02
subsystem: evaluation-matrix
tags: [paired-seeds, ablation, carbon-accounting, sensitivity, eval-matrix]
requires: [05-01-tuned-c4-defaults]
provides: [full-matrix-numbers, forecast-ablation, carbon-ablation, sensitivity-tables]
affects: [05-03-pareto-graphs, report-claims]
tech-stack:
  added: []
  patterns: [thin-driver-over-compare, paired-saved-pct-vs-strongest-baseline, recompute-no-reruns]
key-files:
  created: [eval/matrix.py, eval/ablate.py, eval/sensitivity.py]
  modified: [ctrl/compare.py]
decisions:
  - "Headline = paired saved-% over C3 (strongest baseline); vs-C1 kept secondary (D-12)"
  - "Carbon ablation is accounting-only (D-08 minimum); blackout behavioral arm cited from 05-01, not re-run"
  - "results/*.csv stay gitignored per repo convention; every reportable number preserved here"
metrics:
  duration: "~35 min active (matrix 271.6s + training incl.)"
  completed: "2026-09-30"
  tasks: 3
  tests: "106 passed, 2 skipped (05-01 baseline intact)"
status: complete
actuals:
  tokens: 7959
  tasks: 3
  commits: 3
  plan_head_before: fcb6ed036074db1a3741ac0957fa3aacace44ccd
commits:
  - 5ba8ff3: c4-with/c4-as-c3 factories + eval/matrix.py thin driver
  - be53f88: full 100-run matrix, paired vs-C3 headlines
  - 2155181: forecast x carbon ablations + sensitivity recomputes
---

# Phase 05 Plan 02: Full Evaluation Matrix Summary

**One-liner:** 100-run matrix (5 controllers x 4 scenarios x seeds 0-4, 271.6 s) with paired vs-C3 headlines — tuned C4 saves 2.1% weekday (p=0.0018), 3.3% weekend, ties C3 on heatwave (+0.5%, p=0.06 ns); forecast ablation isolates the overlay gain, flat-EF gate passes at 7e-15, and all sensitivities are pure recomputes.

## Headline Results (paired saved-% vs C3, mean+-std ddof=1, n=5)

| Scenario | Controller | Energy kWh | Saved vs C3 % | Cost Rs (ToU) | CO2 kg (hourly EF) | Comfort % |
|----------|-----------|------------|---------------|---------------|--------------------|-----------|
| weekday | c1 | 48.43+-0.12 | -5.27+-1.21 | 450.1 | 30.05 | 1.25+-1.21 |
| weekday | c2 | 43.24+-0.77 | +6.03+-0.39 | 403.7 | 26.92 | 3.84+-1.29 |
| weekday | c3 | 46.02+-0.64 | 0.00+-0.00 | 429.8 | 28.77 | 3.84+-1.29 |
| weekday | c4-as-c3 | 46.02+-0.64 | 0.00+-0.00 | 429.8 | 28.77 | 3.84+-1.29 |
| weekday | **c4-with** | 45.04+-0.56 | **+2.12+-0.63** | 420.4 | 28.12 | 2.24+-0.84 |
| heatwave | c1 | 48.43+-0.12 | -5.27+-1.21 | 450.1 | 30.05 | 3.42+-1.49 |
| heatwave | c2 | 43.24+-0.77 | +6.03+-0.39 | 403.7 | 26.92 | 5.23+-2.08 |
| heatwave | c3 | 46.02+-0.64 | 0.00+-0.00 | 429.8 | 28.77 | 2.46+-1.12 |
| heatwave | c4-as-c3 | 46.02+-0.64 | 0.00+-0.00 | 429.8 | 28.77 | 2.46+-1.12 |
| heatwave | **c4-with** | 45.77+-0.56 | **+0.53+-0.46** | 427.3 | 28.65 | 3.95+-1.53 |
| weekend | c1 | 5.45+-0.03 | +6.73+-2.42 | 51.3 | 3.17 | 1.86+-2.05 |
| weekend | c2 | 5.55+-0.18 | +5.13+-0.16 | 52.0 | 3.21 | 3.07+-2.80 |
| weekend | c3 | 5.85+-0.18 | 0.00+-0.00 | 54.7 | 3.39 | 3.07+-2.80 |
| weekend | c4-as-c3 | 5.85+-0.18 | 0.00+-0.00 | 54.7 | 3.39 | 3.07+-2.80 |
| weekend | **c4-with** | 5.65+-0.18 | **+3.33+-0.10** | 52.9 | 3.27 | 3.07+-2.80 |
| exam-day (stub=weekday) | c1/c2/c3/c4-as-c3/c4-with | = weekday rows exactly | | | | |

exam-day duplicates weekday bit-for-bit (stub=weekday, T-05-06 labeled in
every table including the `scenario_label` CSV column).

Paired t-tests, c4-with vs c3 energy: weekday t=-7.34 p=0.0018
(significant); weekend t non-finite — paired deltas constant across seeds
(p=0.0000, significant); heatwave t=-2.59 p=0.0608 (**no significant
difference**, stated per D-12); exam-day = weekday.

Reading the headline honestly: the Phase-4 negative ablation (-12 to -33%
vs C3) is closed by the 05-01 tuning — tuned C4 now beats/ties C3 on energy
in all scenarios with no comfort collapse (weekday comfort 2.2% vs 3.8%,
heatwave 4.0% vs 2.5%). C2 remains the energy leader on occupied days
(+6.0% vs C3) — C4's value is the comfort-aware overlay, not raw kWh.
Structural note: C1-C3 energies are weather-invariant by construction
(discrete HVAC levels keyed on occupancy/time only); weather moves comfort,
not their kWh. c4-as-c3 is bit-identical to c3 on all 20 cells, verifying
the forecast-off fallback path.

## Ablation Gaps (results/ablation.csv, 180 rows, zero reruns)

Forecast arm — c4-with minus c4-as-c3, paired within (scenario, seed):

| Scenario | dEnergy kWh | dCost Rs | dCO2 kg | dComfort pp |
|----------|-------------|----------|---------|-------------|
| weekday | -0.98+-0.30 | -9.33+-2.74 | -0.65+-0.18 | -1.59+-0.57 |
| heatwave | -0.25+-0.21 | -2.49+-1.91 | -0.12+-0.13 | +1.49+-1.46 |
| weekend | -0.19+-0.00 | -1.75+-0.00 | -0.11+-0.00 | +0.00+-0.00 |
| exam-day (stub=weekday) | = weekday | | | |

Forecasting buys energy everywhere; comfort cost is -1.6pp on weekday,
+1.5pp (gain) on heatwave, flat on weekend.

Carbon arm — load-shape premium (hourly CO2 minus flat CO2, mean+-std):

| Scenario | c1 | c2 | c3 | c4-with |
|----------|----|----|----|---------|
| weekday | -4.34+-0.02 | -3.78+-0.10 | -3.90+-0.08 | -3.86+-0.08 |
| heatwave | -4.34+-0.02 | -3.78+-0.10 | -3.90+-0.08 | -3.85+-0.07 |
| weekend | -0.70+-0.00 | -0.73+-0.02 | -0.77+-0.02 | -0.74+-0.02 |

All premiums negative: occupied-hour load already skews into the daytime
solar dip, so every controller beats flat-EF accounting. Shifting-
attributable dCO2 (hourly C4-C3 pair minus flat pair): weekday
+0.05+-0.04 kg, heatwave +0.05+-0.03 kg, weekend +0.03+-0.00 kg —
C4's CO2 win is *less energy overall*, not energy moved to cleaner hours
(05-01 honesty note holds: peak-share rises slightly). Flat-EF gate: max
|co2_delta| = 7.11e-15 < 1e-9 over 80 flat rows — PASS.

D-08 carbon-blind behavioral arm: accounting-only shipped as the ablation;
the precool_blackout(18,22) counterpart was measured in 05-01 (-0.2%/-3.7%
energy, only config cutting heatwave peak-share 0.104->0.070) and is cited,
not re-run.

## Sensitivity Tables (results/sensitivity.csv, 144 rows, zero reruns)

EF scale x{0.8,1.0,1.2} — weekday CO2 kg (exact-linear in scale; all
scenarios identical structure, see CSV):

| Controller | x0.8 | x1.0 | x1.2 |
|------------|------|------|------|
| c1 | 24.04 | 30.05 | 36.06 |
| c2 | 21.53 | 26.92 | 32.30 |
| c3 | 23.01 | 28.77 | 34.52 |
| c4-with | 22.49 | 28.12 | 33.74 |

Controller ranking invariant at every EF scale (energy order preserved).

Tariff scale x{0.8,1.0,1.2} — weekday cost Rs (exact post-multiply):

| Controller | x0.8 | x1.0 | x1.2 |
|------------|------|------|------|
| c1 | 360.1 | 450.1 | 540.1 |
| c2 | 322.9 | 403.7 | 484.4 |
| c3 | 343.8 | 429.8 | 515.7 |
| c4-with | 336.4 | 420.4 | 504.5 |

Ranking invariant; C4-vs-C3 Rs gap scales linearly (Rs9.3 at x1.0).

Band +-1C — comfort % (locked 22-26 headlines; wide 21-27 / narrow 23-25):

| Scenario | Controller | locked | wide | narrow |
|----------|------------|--------|------|--------|
| weekday | c1 | 1.25 | 2.14 | 0.51 |
| weekday | c2/c3 | 3.84 | 5.39 | 1.98 |
| weekday | c4-with | 2.24 | 3.38 | 1.17 |
| heatwave | c3 | 2.46 | 4.83 | 1.07 |
| heatwave | c4-with | 3.95 | 5.49 | 1.97 |
| weekend | c3/c4-with | 3.07 | 4.60 | 1.53 |

Comfort ranking invariant across bands (H6: gap is structural, band
recompute adds spread, not reorder). Full 48-row band table in CSV.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 (tracer) | c4 factories + matrix driver + 1-run E2E | 5ba8ff3 | ctrl/compare.py, eval/matrix.py |
| 2 | 100-run matrix + paired vs-C3 headlines | be53f88 | eval/matrix.py, results/full_matrix/summary.csv (gitignored) |
| 3 | Ablations + sensitivities + full suite | 2155181 | eval/ablate.py, eval/sensitivity.py, results/ablation.csv, results/sensitivity.csv (gitignored) |

Matrix runtime 271.6 s (<5 min gate incl. one-time 2-group forecaster
training); crash-resume re-read verified at 3.8-4.8 s. Reproduce:
`python eval/matrix.py --controllers c1,c2,c3,c4-with,c4-as-c3 --scenarios
weekday,weekend,heatwave,exam-day --seeds 5`
(`results/` gitignored; 100 telemetry files + 3 CSVs regenerate).

## Deviations from Plan

### Process deviations (no code impact)

**1. results/ artifacts left gitignored, not committed (05-01 precedent).**
- Plan `files_modified` + T-register assume `results/full_matrix/`,
  `results/ablation.csv`, `results/sensitivity.csv` are committable, but
  repo `.gitignore` excludes `results/` (Phases 1-4 convention: commit
  code, never CSVs).
- Left gitignored per convention; all 20 headline rows + ablation gaps +
  sensitivity tables preserved in this committed SUMMARY.md; CSVs (100
  telemetry files) regenerate from one command (resume verified 3.8 s).

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Weekend t-statistic non-finite + NaN-mean warning.**
- **Found during:** Task 2 verify (scipy catastrophic-cancellation warning;
  single-controller tracer summary emitting nan means).
- **Issue:** Constant paired weekend deltas make t=inf; tracer matrix
  without a baseline controller nanmeans an empty slice (RuntimeWarning).
- **Fix:** matrix.py prints a "constant paired deltas" note for non-finite
  t; compare.aggregate NaN-guards all-NaN saved_pct slices.
- **Files modified:** eval/matrix.py, ctrl/compare.py
- **Commit:** be53f88 / 5ba8ff3 (same task scope, no behavior change to
  numbers — display/statistical-reporting only)

## Known Stubs

None. Scanned created/modified files for empty/placeholder/TODO patterns —
clean. `c4-as-c3 == c3` bit-identity is the designed forecast-off arm, not
a stub; `scenario_label` stub annotation is the T-05-06 requirement.

## Threat Flags

None. Pre-commit scan: no new network endpoints, auth paths, or file-access
patterns. eval/* writes constrained under `results/` (`..` rejected,
compare.py pattern); ablate/sensitivity are read-only over saved frames
(zero reruns, no forecaster retraining — T-05-04); summary.csv carries
paired stats only, no single-seed or difference-of-means claims (T-plan
register); exam-day stub labeled in CSV + every table (T-05-06).

## Self-Check: PASSED

- `eval/matrix.py`, `eval/ablate.py`, `eval/sensitivity.py` exist.
- Commits 5ba8ff3, be53f88, 2155181 exist (`git log` verified, 3/3).
- 100 telemetry files under `results/full_matrix/` (rglob count verified).
- `results/full_matrix/summary.csv` 20 rows with energy/saved-vs-C3/cost/
  CO2/comfort columns; `results/ablation.csv` 180 rows, flat-EF gate
  7.11e-15 < 1e-9; `results/sensitivity.csv` 144 rows (48 x 3 analyses).
- Full suite 106 passed / 2 skipped (05-01 baseline intact).
- `git status sim/ ml/` empty (frozen stack untouched).
