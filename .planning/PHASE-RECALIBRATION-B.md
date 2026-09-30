# Phase Recalibration B — re-measured matrix + report on thermostat physics

**Date:** 2026-09-30 · **Wave:** B (post-calibration re-measurement) · **Base:** 8ae456b
**Python:** 3.14.6 · **No new packages** · **Suite:** 117 passed, 2 skipped

Wave A fixed the physics (thermostat 23.5/24.5 °C cutout, RH 52/0.3, distinct
exam-day) and wiped the pre-thermostat artifacts. This wave regenerates every
evaluation number on the new plant. Headline up front: **comfort is sane
(60–75%) and the old C4-saves-energy story is gone — the forecast overlay now
trades +energy for +comfort.** Reported honestly below.

## 1. Headline table (paired saved-% vs C3, mean±std ddof=1, n=5)

Regenerated via `python eval/matrix.py --controllers c1,c2,c3,c4-with,c4-as-c3
--scenarios weekday,weekend,heatwave,exam-day --seeds 5` (100 runs, 259.0 s)
+ `python ctrl/compare.py` (same args) for `results/comparison/`.

| Scenario | Controller | Energy kWh | Saved vs C3 % | Cost Rs (ToU) | CO₂ kg (hourly EF) | Comfort % |
|----------|-----------|------------|---------------|---------------|--------------------|-----------|
| weekday | c1 | 25.02±0.52 | +0.57±0.12 | 232.9 | 15.40 | 71.1±20.0 |
| weekday | c2 | 24.76±0.53 | +1.59±0.09 | 230.8 | 15.24 | 66.8±19.1 |
| weekday | c3 | 25.16±0.52 | 0.00±0.00 | 234.6 | 15.53 | 68.3±19.9 |
| weekday | c4-as-c3 | 25.16±0.52 | 0.00±0.00 | 234.6 | 15.53 | 68.3±19.9 |
| weekday | **c4-with** | 25.23±0.53 | **−0.28±0.17** | 235.2 | 15.58 | 71.3±20.1 |
| heatwave | c1 | 27.25±0.54 | +0.54±0.23 | 253.6 | 16.81 | 69.7±19.8 |
| heatwave | c2 | 26.84±0.51 | +2.02±0.16 | 250.4 | 16.56 | 60.3±17.4 |
| heatwave | c3 | 27.39±0.53 | 0.00±0.00 | 255.7 | 16.95 | 64.2±19.0 |
| heatwave | c4-as-c3 | 27.39±0.53 | 0.00±0.00 | 255.7 | 16.95 | 64.2±19.0 |
| heatwave | **c4-with** | 28.08±0.53 | **−2.49±0.14** | 260.8 | 17.46 | 70.3±20.3 |
| weekend | c1 | 1.97±0.03 | +5.60±1.29 | 18.6 | 1.15 | 75.6±38.6 |
| weekend | c2 | 2.01±0.04 | +3.57±0.78 | 19.0 | 1.16 | 72.7±37.7 |
| weekend | c3 | 2.09±0.05 | 0.00±0.00 | 19.6 | 1.21 | 72.7±37.7 |
| weekend | c4-as-c3 | 2.09±0.05 | 0.00±0.00 | 19.6 | 1.21 | 72.7±37.7 |
| weekend | **c4-with** | 2.10±0.06 | **−0.48±1.03** | 19.7 | 1.21 | 72.7±37.7 |
| exam-day (real) | c1 | 27.16±0.26 | −0.53±0.10 | 252.8 | 16.28 | 67.9±28.8 |
| exam-day (real) | c2 | 26.66±0.25 | +1.35±0.16 | 248.8 | 15.87 | 68.6±26.2 |
| exam-day (real) | c3 | 27.02±0.26 | 0.00±0.00 | 252.0 | 16.12 | 70.5±27.3 |
| exam-day (real) | c4-as-c3 | 27.02±0.26 | 0.00±0.00 | 252.0 | 16.12 | 70.5±27.3 |
| exam-day (real) | **c4-with** | 27.23±0.24 | **−0.77±0.11** | 253.7 | 16.28 | 75.2±29.3 |

Paired t-tests, c4-with vs c3 energy (ddof=1, n=5): weekday t=+3.83 p=0.0187
(significant — C4 uses MORE); weekend t=+1.04 p=0.3567 (ns); heatwave
t=+41.27 p=0.0000 (significant — C4 uses MORE); exam-day t=+16.53 p=0.0001
(significant — C4 uses MORE). c4-as-c3 is bit-identical to c3 on all 20
cells — the forecast-off fallback path still verifies.

Reading honestly vs the old plant: gaps compressed (thermostat makes
empty-room cooling cheap, so there is less waste to harvest), comfort is
60–75% everywhere (vs 1–5% pre-fix), and tuned C4 no longer beats C3 on
energy in ANY scenario — but it leads or ties on comfort in all four
(weekday 71.3 vs 68.3, heatwave 70.3 vs 64.2, exam-day 75.2 vs 70.5,
weekend tie). C2 remains the raw-kWh leader on occupied days. C4's value
prop on the new physics is comfort-per-kWh, not kWh saved.

## 2. Ablation gaps (results/ablation.csv, 180 rows, zero reruns)

Forecast arm — c4-with minus c4-as-c3, paired within (scenario, seed):

| Scenario | dEnergy kWh | dCost Rs | dCO₂ kg | dComfort pp |
|----------|-------------|----------|---------|-------------|
| weekday | +0.07±0.04 | +0.66±0.34 | +0.05±0.04 | +2.97±0.48 |
| heatwave | +0.68±0.04 | +5.09±0.31 | +0.51±0.04 | +6.09±1.83 |
| weekend | +0.01±0.02 | +0.09±0.20 | +0.01±0.01 | +0.00±0.00 |
| exam-day | +0.21±0.03 | +1.64±0.27 | +0.16±0.03 | +4.67±2.84 |

Old plant: forecasting bought energy at a comfort cost. New plant: the
overlay SPENDS energy (+0.7 kWh heatwave) to BUY comfort (+6.1 pp) —
pre-cool forces cooling ON ahead of arrivals that the thermostat would
otherwise serve late. Same mechanism, flipped sign: with cutout physics the
baseline no longer over-cools, so pre-cooling is pure extra.

Carbon arm — shifting-attributable dCO₂ (hourly-pair minus flat-pair):
weekday +0.002±0.011, weekend −0.001±0.003, heatwave +0.026±0.013,
exam-day +0.012±0.009 kg. Same verdict as 05-02: C4's CO₂ delta is
less/more-energy-overall, not shifting to cleaner hours. Flat-EF gate:
max |co2_delta| = 3.55e-15 < 1e-9 over 80 flat rows — PASS.

## 3. Sensitivity notes (results/sensitivity.csv, 144 rows, zero reruns)

- EF scale ×{0.8,1.0,1.2}, weekday CO₂ kg: c1 12.32/15.40/18.48,
  c2 12.19/15.24/18.29, c3 12.42/15.53/18.64, c4-with 12.47/15.58/18.70.
  Exact-linear in scale; ranking invariant at every scale.
- Tariff scale: same structure (exact post-multiply), ranking invariant.
- Band recompute, weekday comfort: c3 locked 68.3 / wide 69.5 / narrow 65.8;
  c4-with locked 71.3 / wide 71.5 / narrow 70.1. C4 leads C3 under every
  band; no reorder (H6 holds on the new plant).

## 4. Heatwave 10-seed verdict — SIGNIFICANT (both metrics)

`scripts/waveb_heatwave10.py` (ad-hoc, committed; global PAIRED_SEEDS
untouched): C3 vs tuned-C4, heatwave, seeds 0–9, frames under
`results/heatwave10/` (gitignored, like all results/).

- Energy: c3 27.51±0.37 vs c4-with 28.19±0.37 kWh → t=+56.29, p≈0.000000 —
  SIGNIFICANT (C4 spends +0.68 kWh).
- Comfort: c3 67.5±17.1 vs c4-with 73.7±18.5 % → t=+10.47, p=0.000002 —
  SIGNIFICANT (C4 gains +6.2 pp).

Old-plant heatwave was the one ns result (p=0.06, "ties C3"). On thermostat
physics with 10 seeds, heatwave is significant in BOTH directions at once:
costs energy, buys comfort. The 5-seed matrix t (+41.27, p=0.0000) already
agreed — the 10-seed run confirms it is not a small-n artifact.

## 5. Figure regen confirm

`python -m eval.report` (full): G1–G6 rewritten 19:32–19:33 IST, 11 tables
refreshed under `results/report_tables/` (g1..g6 + headline_savings_over_c3
+ shifting_peak_share + ablation + sensitivity copies). G7 recaptured live:
`scripts/capture_dashboard.py` against a local Streamlit server (detached
`python -m streamlit run`, killed after) → `results/figures/fig_g7_dashboard.png`
(89,156 B, 19:39 IST, 1600×900 real screenshot, force-added to git since
`results/` is gitignored — the committed G7 evidence exception from 06-02).
Sizes: G1 135 KB, G2 57 KB, G3 92 KB, G4 100 KB, G5 111 KB, G6 78 KB.
No capture tooling was missing — nothing faked, nothing stubbed.

## 6. Comment updates (stale-claim rule)

- `ctrl/predictive.py` docstring: −12.9%/−25.3% now scoped as "measured on
  the pre-thermostat plant" with a pointer to this file.
- `tests/test_c4_tuning.py::test_shipped_defaults_are_tuned` docstring: same
  scoping (assertions are constructor values, unchanged — no test weakened).
- Historical SUMMARYs (05-01/05-02), PROJECT.md, STATE.md left as-is: they
  record what was measured when, not live claims.

## 7. Verification

Full suite `python -m pytest tests/ -q` → **117 passed, 2 skipped** (73.4 s;
only warnings = Keras/numpy-2 `__array__` DeprecationWarning). No tolerance
touched, no test deleted, no comfort-band change, no retraining beyond the
frozen forecaster's normal in-pipeline training.

No BLOCKERs. Deferred: PROJECT.md/STATE.md headline refresh (a
planning-state edit, out of this wave's scope); MPC/RL still bonus.
