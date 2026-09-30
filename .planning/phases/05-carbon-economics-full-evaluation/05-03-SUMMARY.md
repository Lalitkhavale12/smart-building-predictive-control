---
phase: 05-carbon-economics-full-evaluation
plan: 03
subsystem: report-graphs
tags: [pareto, matplotlib, one-command-report, eval-rigor, report-tables]
requires: [05-02-matrix, 05-01-sweep]
provides: [seven-graph-report, pareto-evidence, report-tables]
affects: [report-claims, phase-6-dashboard]
tech-stack:
  added: []
  patterns: [saved-frames-only-figures, frozen-forecaster-regen, txt-stub-for-deferred-screenshot]
key-files:
  created: [eval/report.py, eval/figures.py]
  modified: []
decisions:
  - "G7 is a .txt stub labeled Phase-6 pending; no image file in this plan is a dashboard screenshot (T-05-09)"
  - "results/*.png/*.csv stay gitignored per repo convention; every figure backed by a committed-code-regenerable table"
  - "Pareto keeps all 10 sweep + 6 band points even where dominated; dominated cluster annotated as the honest finding"
metrics:
  duration: "~25 min active (pred regen ~1 min frozen training; full report <1 min thereafter)"
  completed: "2026-09-30"
  tasks: 3
  tests: "106 passed, 2 skipped (05-01 baseline intact)"
status: complete
actuals:
  tokens: 6400
  tasks: 3
  commits: 2
  plan_head_before: a9ea9ee
commits:
  - e38d129: one-command report entry + G1 24h load-shape with peak/solar shade
  - bead9a7: Pareto + savings + CO2 + pred-vs-actual + ablation figures
---

# Phase 05 Plan 03: One-Command Report + All 7 Graphs Summary

**One-liner:** `python -m eval.report` regenerates G1-G6 matplotlib PNGs + G7 `.txt` stub and 11 backing tables from saved frames/CSVs only — Pareto carries all 21 points (5 matrix + 10 sweep + 6 band) with honest dominated-cluster framing.

## What Was Built

`eval/report.py` (CLI, `--only g1|g2,...` subset) + `eval/figures.py` (Agg backend, no plotly).
Default run: regenerates `results/report_pred_holdout.csv` (5340 rows) from the
**frozen** forecaster (`build_frozen_forecaster` + `holdout_pred_rows`, C1-trained
HistGB, never retrained), reuses matrix/sweep/ablation CSVs if present (re-runs
only missing inputs with 05-01/05-02 defaults — never subset seeds), emits G1-G6
+ G7 stub, writes `results/report_tables/`.

## Figure List (results/figures/, gitignored, reproduced from committed code)

| # | File (size) | Content |
|---|-------------|---------|
| G1 | fig_g1_24h_profile.png (136KB) | Hourly-mean kW C3 vs C4-with ±std (n=5, weekday) + occupancy shade + 18-22 peak + 10-16 solar-dip spans |
| G2 | fig_g2_savings.png (59KB) | Saved-% vs C3 by scenario/controller with std error bars; comfort footnote; exam-day excluded (stub=weekday) |
| G3 | fig_g3_pareto.png (100KB) | Energy-vs-comfort, 21 pts: 5 matrix (C1/C2/C3/stock-C4/tuned-C4) + 10 sweep (H1-H4 incl.) + 6 ±1C band; zoomed axes + dominated-cluster annotation |
| G4 | fig_g4_co2.png (99KB) | Cumulative CO2 C3 vs C4 ±std + avoided fill + flat-EF counterfactual line |
| G5 | fig_g5_pred_actual.png (111KB) | Frozen-forecaster pred-vs-actual, occupancy + demand panels with RMSE, y=x |
| G6 | fig_g6_ablation.png (74KB) | Two-panel: forecast paired deltas (dE/dCO2 ±std + dComfort labels) + carbon load-shape premiums |
| G7 | fig_g7_dashboard_placeholder.txt (341B) | Stub note: screenshot is Phase 6; build never breaks on the 7th slot |

Backing tables (`results/report_tables/`, 11 CSVs): per-figure `g1..g6_*` (7) +
`headline_savings_over_c3.csv` + `shifting_peak_share.csv` (peak-share + Rs/CO2
deltas C4−C3 per seed) + `ablation.csv` + `sensitivity.csv` copies.

## Verification Results

- Tracer: `python -m eval.report --only g1` → G1 136332 B (>5KB gate) PASS
- Task 2: `--only g2,g3,g4,g5,g6` → all present PASS; Pareto 21 pts (≥9 sweep, ≥1 band) PASS; pred CSV from frozen forecaster PASS
- Task 3: full `python -m eval.report` → 7 figures / 11 tables PASS
- Full suite: 106 passed, 2 skipped (pre-existing skips) PASS

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 (tracer) | Report entry + G1 with price/carbon shade | e38d129 | eval/report.py, eval/figures.py |
| 2 | G2-G6 + backing tables | bead9a7 | eval/figures.py (+ report_tables/) |
| 3 | G7 stub + full one-command wiring | (code in e38d129/bead9a7; tree clean, no further diff) | eval/report.py, fig_g7 stub, summary tables |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] G1 controller key `c4` → `c4-with`.**
- **Found during:** Task 1 verify (FileNotFoundError on `results/full_matrix/c4/...`)
- **Fix:** one-line key correction; matrix dirs are `c4-with`/`c4-as-c3`.
- **Commit:** e38d129 (same task scope)

**2. [Rule 1 - Bug] G4 per-minute/per-row shape mismatch (1440 vs 5760).**
- **Found during:** Task 2 verify (broadcast ValueError in `_cumulative_co2`)
- **Fix:** aggregate power + hours over deduplicated timestamps before cumsum.
- **Commit:** bead9a7 (same task scope)

**3. [Rule 1 - Bug] Pareto band points duplicated per-seed (45 rows).**
- **Found during:** Task 2 self-check (band CSV is per-seed; loop added one point per row)
- **Fix:** groupby (config, band) → mean±std comfort; 21 pts (5+10+6).
- **Commit:** bead9a7 (same task scope)

### Process deviations (no code impact)

**4. results/ artifacts left gitignored, not committed (05-01/05-02 precedent).**
Plan `files_modified` assumes figures/tables committable, but repo `.gitignore`
excludes `results/` (Phases 1-4 convention: commit code, never CSVs/PNGs). All
artifacts regenerate from one command on committed code; figure sizes + table
row counts preserved above.

**5. Task 3 needed no separate commit.** G7 stub + summary-table wiring shipped
inside e38d129/bead9a7; `git status` clean at plan end, so a third empty commit
was not manufactured. Measured commits = 2 (not 3).

## Known Stubs

None in committed code. Scanned `eval/report.py`, `eval/figures.py` for
empty/placeholder/TODO patterns — clean. The G7 `.txt` is the plan-mandated
Phase-6 placeholder (T-05-09 mitigation), not a code stub; no image file in
this plan claims to be a dashboard screenshot.

## Threat Flags

None. Pre-commit scan: no new network endpoints, auth paths, or file-access
patterns. Report reads committed-code outputs only (T-05-07: pred CSV
regenerated from frozen forecaster, matrix reuse is re-read-or-rerun); every
figure carries error bars + scenario labels + comfort context (T-05-08); G7 is
an explicit `.txt` stub (T-05-09).

## Self-Check: PASSED

- `eval/report.py`, `eval/figures.py` exist; commits e38d129, bead9a7 exist (2/2 measured).
- Full `python -m eval.report` reproduces 7 figures + 11 tables from committed code.
- `git status sim/ ml/ ctrl/` empty (frozen stack untouched); suite 106/2.
