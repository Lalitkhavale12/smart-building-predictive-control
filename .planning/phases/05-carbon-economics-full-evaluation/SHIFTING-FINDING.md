# SHIFTING FINDING — CTL-05 gap closure (2026-09-30)

**Question:** does the `precool_blackout(18,22)` arm give tuned C4 genuine
off-peak load shifting worth promoting as the documented carbon-aware variant?

**Method:** `PredictivePolicy(occ_threshold=8, precool_level="REDUCED",
precool_blackout=(18,22))` over weekday + heatwave × seeds 0–4, paired against
saved `results/full_matrix/` C3 and tuned-C4 frames (frozen weekday
forecaster, built once). Telemetry saved under
`results/full_matrix/c4-blackout/` (gitignored, regenerable); per-seed table
in `results/blackout_vs_c3_tuned.csv`.

## Result 1 — blackout on TUNED defaults: no effect, NOT promoted

| Scenario | d_peak_share vs tuned | p (paired t) | dE (kWh) | dRs | dCO2 (kg) | dComfort (pp) |
|----------|----------------------|--------------|----------|-----|-----------|---------------|
| weekday | +0.0000±0.0000 | 0.0001 (zero-variance rounding) | -0.001±0.000 | -0.01 | -0.001 | +0.00 |
| heatwave | -0.0001±0.0003 | 0.3745 ns | -0.008±0.015 | -0.08 | -0.006 | -0.01 |

Per-seed blackout peak-share (weekday): 0.0787 / 0.0801 / 0.0838 / 0.0773 /
0.0820 — identical to tuned C4 to 4 decimals. Heatwave: 0.0814 / 0.0832 /
0.0865 / 0.0805 / 0.0850 vs tuned 0.0821 / 0.0832 / 0.0865 / 0.0805 / 0.0850.

Comfort non-regression holds (identical) and energy cost is nil — but the
promotion criterion (measured negative d_peak_share, p<0.05) FAILS. The tuned
config (thr8+REDUCED) already eliminated the 18–22h pre-cool events the
blackout would block, so there is no load left to shift. **Tuned defaults
stay; blackout is not shipped.**

For reference, blackout-vs-C3 mirrors tuned-vs-C3 (weekday d_peak
-0.0067±0.0006, p=0.0000; heatwave -0.0038±0.0004, p=0.0000) — a small but
significant peak-share dip riding on all-hours savings, not moved energy.

## Result 2 — blackout on STOCK overlay: mechanism confirmed (probe only)

`PredictivePolicy(occ_threshold=1, precool_level="ON",
precool_blackout=(18,22))` vs stock, same seeds:

| Scenario | d_peak_share vs stock | p | dE (kWh) | note |
|----------|----------------------|---|----------|------|
| weekday | -0.0008±0.0015 | 0.27 ns | -0.10 | no evening pre-cools to block |
| heatwave | -0.0334±0.0022 | <0.0001 | -2.25 | seed0 0.101→0.069, replicates 05-01's 0.104→0.070 |

The apparatus DOES detect shifting when pre-cools exist (stock ON pre-cools
are frequent evening events). Tuning removed those events — efficiency and
shifting were traded, and efficiency won.

## Honest CTL-05 wording (binding)

- Savings are **less-energy-everywhere**, not load moved off-peak.
- Tariff/CO₂ numbers are **consequences measured under time-varying series**
  (hourly EF + ToU via `compute_metrics`), never a price response.
- Never claim load moved off-peak unless d_peak_share is negative with
  p<0.05. The only config meeting that bar is stock+blackout on heatwave —
  a probe, not the shipped default.
- Figure G1 keeps peak (18–22h) + solar (10–16h) shading with the honest
  caption; G6 title already states the win is less energy, not moved energy.
