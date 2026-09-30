# Phase 05 Gap Closure: CTL-05 Shifting Claim — SUMMARY

**Date:** 2026-09-30 · **Gap:** 05-VERIFICATION.md Truth 1 (FAILED) —
tuned C4 saves energy all-hours; shifting-attributable dCO₂ ≈ +0.05 kg;
peak-share tuned-vs-stock rose 0.071→0.080.
**Disposition: GAP CLOSED as honest negative result** (no override needed —
claim reworded to match evidence, mechanism probed, defaults unchanged).

## What was measured (Task 1)

`precool_blackout(18,22)` stacked on tuned C4 (thr8+REDUCED), weekday +
heatwave × seeds 0–4 paired vs saved C3/tuned frames (frozen forecaster):

- vs tuned: weekday d_peak_share +0.0000 (p≈0.0001 on zero-variance
  rounding), heatwave -0.0001 (p=0.37 ns); dE ≈ 0, comfort identical.
  **Promotion criterion (negative d_peak_share, p<0.05) FAILED — not shipped.**
- Mechanism check on STOCK overlay (thr1+ON): heatwave d_peak_share
  -0.0334±0.0022 (p<0.0001, seed0 0.101→0.069, replicates 05-01's
  0.104→0.070); weekday ns. The apparatus detects shifting when pre-cools
  exist — tuning removed them.
- Blackout-vs-C3 mirrors tuned-vs-C3 (weekday -0.0067, heatwave -0.0038,
  both p<0.0001): small peak dip riding on all-hours savings, not moved energy.

Full per-seed tables: `SHIFTING-FINDING.md` (committed); raw CSVs
`results/blackout_vs_c3_tuned.csv`, `results/blackout_runs.csv` +
`results/full_matrix/c4-blackout|stock-blackout/` telemetry (gitignored,
regenerable).

## What was reworded (Task 2)

- `eval/figures.py` G1 title: "(kWh moved out of peak visible)" →
  "(all-hours savings; no off-peak shifting claimed)". Peak/solar shading kept.
- `eval/report.py` shifting-table comment: honest-accounting note + the
  p<0.05 claim gate.
- `results/TUNING.md` (on disk, gitignored — could not commit): honesty note
  extended with blackout-on-tuned outcome, pointed at SHIFTING-FINDING.md.
- New committed `SHIFTING-FINDING.md`: numbers + binding CTL-05 wording.

## Final CTL-05 disposition

C4's value is the comfort-aware overlay (less-energy-everywhere with comfort
non-regression), with cost/CO₂ consequences honestly measured under
time-varying EF+ToU series. No headline claims shifting. The only config with
measured significant shifting (stock+blackout, heatwave) is a probe, not the
default — by design, since tuning eliminated the pre-cools it blocks.

## Verify

- `python -m eval.report --only g1` → rewrote fig_g1 PNG with honest caption.
- Fast slice: **96 passed, 2 skipped** (36.4 s).
- No headline claims shifting without measured negative d_peak_share, p<0.05.
