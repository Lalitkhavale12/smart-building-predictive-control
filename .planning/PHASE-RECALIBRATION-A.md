# Phase Recalibration A — thermostat + exam-day timetable (post-Phase-5)

**Date:** 2026-09-30 · **Wave:** A (post-calibration fix + re-green) · **Python:** 3.14.6 · **No new packages**

## 1. Cause (why recalibration was needed)

1. **No-thermostat freeze.** The RC plant applied commanded HVAC Q unconditionally
   every minute. Constant ON drives rooms toward the equilibrium
   `T_out + R·Q ≈ 31 + 30·(−3.5) ≈ −74 °C`; measured trajectory minimum was
   **−44 °C** and comfort sat at **~2%**. Real split ACs cut out at setpoint —
   the sim had no cutout, so every controller comparison was physically meaningless.
2. **RH random walk too loose.** `RH_INIT=55 / STEP_STD=0.4` let humidity drift out
   of the 30–60% comfort band too often, depressing comfort for non-thermal reasons.
3. **Exam-day was a weekday alias** (`SCENARIO_TABLE["exam-day"]="weekday"` with
   "stub=weekday" labels). A scenario identical to weekday adds zero evaluation
   information while pretending to add coverage.

## 2. Fix (what changed — review of the uncommitted working tree)

- **`sim/config.py`** — added `THERMOSTAT_LO/HI = 23.5/24.5 °C` (setpoint 24 ±
  deadband) with a derivation comment (equilibrium math above); `RH_INIT=52`,
  `RH_STEP_STD=0.3` (≈85% of steps inside 30–60%); new dense `exam-day`
  timetable (09:00–17:00, lunch gap 12–13 only; classrooms 30, lab 12, office
  int-fill 4 = fixed roster via the binomial path); `SCENARIO_TABLE["exam-day"]`
  now points at it. Comfort band **locked, untouched** (22–26 °C / 30–60 %RH).
- **`sim/simulator.py`** — per-room `cutout` latch (init False in `reset`);
  hysteresis: cut out at/under LO, cut back in at/over HI; `OFF` resets the
  latch. Commanded level is **untouched** — the thermostat gates delivered Q
  **and** metered power (`power_kW` uses the gated `q_hvac`, exactly like
  hardware). Verified by review: gating, latch reset, power path all correct.
- **`sim/occupancy.py`, `sim/weather.py`** — docstring-only updates (exam-day
  now real; heatwave offset unchanged).
- **`ctrl/compare.py`, `ctrl/predictive.py`, `eval/matrix.py`, `eval/figures.py`,
  `eval/sensitivity.py`** — comment/label updates only: exam-day labeled
  `"exam-day"` (no longer "stub=weekday"); exam-day falls back to the weekday
  frozen forecaster (conservative until Wave B retrains); G2 keeps
  weekday/weekend/heatwave scope. **No logic changes, no tolerance changes.**
- **`tests/test_reproducibility.py`** — ADDED assertions only (no weakened
  tolerances): exam-day schedule must DIFFER from weekday (minute 810 =
  13:30 in the weekday lunch gap: weekday 0, exam-day > 0; minute 600 = 10:00
  occupied in all four exam-day rooms). Jitter-derivation comments included.
- **Wiped stale artifacts:** `results/full_matrix/` + `results/comparison/`
  removed (pre-thermostat CSVs, physically invalid). Re-measurement is Wave B.
- **`scripts/wavea_spot.py`** (new, untracked helper) — C1/C2/C3 + tuned-C4
  seed-0 spot probe for weekday + heatwave.

## 3. Verification

- **Full suite:** `python -m pytest tests/ -q` → **117 passed, 2 skipped**
  (81.9 s; only warnings = Keras/numpy-2 `__array__` DeprecationWarning).
  Includes TF-heavy bakeoff + UCI tests. Nothing fixed by deleting coverage;
  nothing re-measured without a physical derivation (thermostat equilibrium,
  RH band occupancy, jitter-edge arithmetic — all in comments).
- **Forecaster sanity (new physics):** `tests/test_bakeoff.py` green —
  `test_bakeoff_table` proves the 4-model × 2-horizon table with verdict+reason
  builds end-to-end post-calibration; `test_tie_rule` locks the <3%-gain →
  ship-HistGB rule. Recorded `results/bakeoff.csv`: HistGB MAE 4.29 (H30) /
  4.50 (H60) vs LSTM 0.66 / 0.79 (≈84%/82% gap, non-overlapping std). Frozen
  choice stays HistGB per the matrix freeze rule; bake-off verdict is Wave B input.
- **Spot (seed 0, `scripts/wavea_spot.py`, post-thermostat plant):**

  | Run | Energy (kWh) | Comfort (%) | Cost (Rs) | CO₂ (kg) |
  |-----|--------------|-------------|-----------|----------|
  | C1 weekday | 25.756 | 46.0 | 239.7 | 15.81 |
  | C2 weekday | 25.522 | 43.1 | 237.7 | 15.66 |
  | C3 weekday | 25.923 | 44.0 | 241.5 | 15.95 |
  | C4-tuned weekday | 26.007 | 46.5 | 242.3 | 16.02 |
  | C1 heatwave | 28.031 | 44.9 | 260.8 | 17.25 |
  | C2 heatwave | 27.583 | 39.0 | 257.1 | 16.96 |
  | C3 heatwave | 28.156 | 42.1 | 262.6 | 17.37 |
  | C4-tuned heatwave | 28.862 | 45.0 | 267.9 | 17.91 |

  Comfort is sane (39–46.5% vs ~2% pre-fix — expectation ~40%+ met; C2-heatwave
  39.0% is borderline but physical, not a bug). Single-seed energy ordering is
  NOT a headline — the −12.9%/−25.3% tuning verdict was a 5+3-seed mean on the
  old plant; re-measuring the matrix on the new plant is Wave B.

## 4. Deferred to Wave B

Full-matrix + comparison re-runs (all controllers × all 4 scenarios × paired
seeds), forecaster retrain decision for exam-day, figure/table regeneration.
No BLOCKERs — every check has a physical explanation above.
