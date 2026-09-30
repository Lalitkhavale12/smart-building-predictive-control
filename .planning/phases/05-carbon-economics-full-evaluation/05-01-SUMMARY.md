---
phase: 05-carbon-economics-full-evaluation
plan: 01
subsystem: control-tuning
tags: [c4, predictive-control, threshold-sweep, load-shifting, paired-seeds]
requires: [04-03-ablation]
provides: [tuned-c4-defaults, tuning-sweep-evidence]
affects: [05-02-matrix, pareto, report-graphs]
tech-stack:
  added: []
  patterns: [constructor-param-tuning, frozen-forecaster-reuse, paired-seed-deltas]
key-files:
  created: [tests/test_c4_tuning.py, eval/sweep.py, eval/__init__.py]
  modified: [ctrl/predictive.py, tests/test_predictive.py]
decisions:
  - "Ship new C4 defaults occ_threshold=8 + precool_level=REDUCED (measured -12.9%/-25.3% + comfort non-regression)"
  - "results/*.csv + TUNING.md left gitignored; verdict preserved here"
metrics:
  duration: "~40 min active + ~15 min background sweep"
  completed: "2026-09-30"
  tasks: 3
  tests: "106 passed, 2 skipped (pre-existing skips)"
status: complete
actuals:
  tokens: 45000
  tasks: 3
  commits: 3
  plan_head_before: e7ed221
commits:
  - dc67a40: wire dead C4 params + H1/H2/H4/blackout variants + 7 tests
  - cc126b5: sweep script (10 configs, shifting metric, plant/band probes)
  - daa5fb4: promote tuned defaults + pin legacy params in tests
---

# Phase 05 Plan 01: C4 Threshold Tuning Investigation Summary

**One-liner:** H1 pre-cool-to-REDUCED + H3 occ_threshold=8 is the measured winner (weekday -12.9%, heatwave -25.3% energy, comfort 0%→2-3%) — shipped as the new C4 defaults; the Phase-4 negative ablation is explained (full-ON pre-cool overshoot) and the gap is robust across plant sizes.

## Tuning Verdict: SHIP NEW DEFAULTS

Shipped `PredictivePolicy` defaults: **`occ_threshold=8`, `precool_level="REDUCED"`**
(sweep row `precool-reduced+thr8` vs `stock` = Phase-4 legacy). Changed ONLY
`__init__` default values — zero logic edits.

Paired deltas, shipped-vs-legacy (mean±std ddof=1, within scenario+seed):

| Scenario | dEnergy | dCost (Rs) | dCO2 (kg) | dComfort |
|----------|---------|------------|-----------|----------|
| weekday (n=5) | -6.64±0.35 kWh (-12.9%) | -60.8±3.2 | -4.20±0.21 | +2.24pp (0.00→2.24%) |
| heatwave (n=3) | -15.53±0.81 kWh (-25.3%) | -138.7±7.4 | -11.02±0.54 | +3.39pp (0.00→3.39%) |

Consistent sign on all 8 paired seeds, std << mean. 05-02 matrix uses these
defaults; `stock` rows remain the honest Phase-4 baseline reference.

## What Won, What Didn't (H1-H5 + D-08)

- **H1 pre-cool-to-REDUCED — CONFIRMED, largest mover.** Alone: -9.6%/-17.7%,
  comfort improves (0→1.2%/3.4%). Root cause of the Phase-4 gap: 30-min
  full-ON pre-cool injects 1.75 kWh into a 0.14 kWh/K room (~12 K plunge
  through the band); REDUCED spends 0.6 kWh and overshoots less.
- **H3 occ_threshold sweep — CONFIRMED, second mover.** thr8 alone:
  -5.9%/-18.2%; stacks with H1 into the shipped winner. Office poisson noise
  arrivals were never comfort-buying, only overshoot-buying.
- **H2 early-off-from-REDUCED — small positive** (-2.2%/-1.0%, comfort flat).
  Not shipped: untested in combination, keep shipped config exactly as tested.
- **H4 dual-horizon gate — weak** (-0.3% weekday, -4.1% heatwave); thr8
  already kills most false positives. Not shipped.
- **H5 plant oversize — CONFIRMED structural.** Negative ablation persists at
  Q_ON -2.5 (39.28 vs 35.33) and -1.75 (29.91 vs 27.32); tuned config beats
  legacy at every size. Probe was a runtime override inside sweep.py only —
  `sim/` diff is empty, physics restored and asserted.
- **H6 band interplay — CONFIRMED no-movement.** Legacy stays 0.0% on all
  three bands; gap invariant → structural.
- **D-08 blackout-18-22 — weak on energy** (-0.2%/-3.7%) but the ONLY config
  cutting heatwave peak-share (0.104→0.070). Kept as the carbon-variant arm
  for 05-02, not shipped as default.

## Shifting Honesty Note (CTL-05)

C4 has no price signal: the tuned config saves energy in ALL hours rather
than moving kWh off-peak (weekday peak-share 0.071→0.080). Cost/CO2 deltas
come from the hourly EF+ToU series via `compute_metrics`, never a scalar.
Claim "cost/CO₂ consequences under time-varying tariffs," not
"carbon-responsive control" (blackout arm excepted).

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 (tracer) | Wire dead params + H1/H2/H4/blackout flags | dc67a40 | ctrl/predictive.py, tests/test_c4_tuning.py |
| 2 | Sweep + shifting metric + plant/band probes | cc126b5 | eval/sweep.py, eval/__init__.py (+ gitignored results/tuning_sweep{,_plant,_band}.csv) |
| 3 | Promotion verdict + new defaults | daa5fb4 | ctrl/predictive.py, tests/test_predictive.py, tests/test_c4_tuning.py (+ gitignored results/TUNING.md) |

Sweep runtime: forecaster training 58 s once; single C4-with run 7.80 s >
~5 s gate → heatwave cut to 3 seeds per the plan's documented fallback
(80 rows: 10 configs × 5 weekday + 3 heatwave). Reproduce:
`python eval/sweep.py --scenarios weekday,heatwave --seeds 5` (~15 min).

## Deviations from Plan

### Process deviations (no code impact)

**1. results/ artifacts left gitignored, not committed.**
- **Found during:** Task 2/3 commit
- **Issue:** Plan `files_modified` + T-05-02 assume `results/tuning_sweep.csv`
  and `results/TUNING.md` are committable, but the repo `.gitignore` excludes
  `results/` (established Phase 1-4 convention: commit code, never CSVs).
- **Fix:** Left them gitignored per repo convention and user instruction;
  verdict + all paired numbers preserved in this committed SUMMARY.md (and
  results/TUNING.md on disk); CSVs regenerable from one command.
- **Commit:** n/a (no commit possible for ignored files)

**2. Heatwave 3 seeds instead of 5 (plan-sanctioned fallback, not a deviation
from intent).** Timing gate tripped deterministically (7.80 s > ~5 s);
paired statistics remain valid (n=3, ddof=1). Noted in TUNING.md.

### Auto-fixed Issues

None — plan executed as written. (One self-caught test bug during Task 1:
intermediate assert in `test_earlyoff_from_reduced` contradicted the flag's
own mid-loop firing; restructured with a hold forecast — fixed before commit.)

## Known Stubs

None. Scanned created/modified files for empty/placeholder/TODO patterns —
clean. `precool_blackout=None` default is a deliberate off-switch, not a stub.

## Threat Flags

None. Pre-commit scan: no new network endpoints, auth paths, or file-access
patterns. Sweep writes constrained under `results/` (`..` rejected,
compare.py pattern); plant probe override restored in `finally` + asserted
(`Q_HVAC["ON"] == -3.5`); `git status sim/` empty at plan end (T-05-01).
T-05-02 repudiation coverage moved to this SUMMARY (see deviation 1).

## Self-Check: PASSED

- `eval/sweep.py`, `eval/__init__.py`, `tests/test_c4_tuning.py` exist.
- Commits dc67a40, cc126b5, daa5fb4 exist (`git log` verified, 3/3).
- `git status sim/` empty; full suite 106 passed / 2 skipped.
- `results/tuning_sweep.csv` has all required columns
  (config, scenario, seed, energy_kwh, comfort_pct, peak_share_18_22,
  cost_rs, co2_kg + vs-stock deltas); every row carries comfort.
- `results/TUNING.md` exists with verdict line.
