# Phase 03: Baselines + Comparison Harness — Verification Report

**Phase goal:** Users can compare three non-ML baseline controllers on energy and comfort through one harness
**Verified:** 2026-09-29 (UTC)
**Status:** PASS — all 3 success criteria met
**Method:** Goal-backward verification against codebase + live reproduction (pytest + compare.py rerun). SUMMARY.md claims treated as leads, not evidence.

## Verdict per Criterion

| # | Criterion (REQ) | Verdict | Evidence |
|---|---|---|---|
| 1 | C1 fixed-schedule yields a kWh number per scenario (CTL-01) | **PASS** | `ctrl/schedules.py::is_on` + `ctrl/baselines.py::FixedSchedulePolicy` (BasePolicy subclass, schedule-driven HVAC, lights from occupancy). Live rerun: C1 weekday 48.542±0.059 kWh (2 seeds); SUMMARY's C1 seed-0 48.583 kWh and 5-seed 48.433±0.116 kWh are consistent with this. `tests/test_baselines.py` C1 end-to-end kWh test passes. |
| 2 | C2 occupancy-rule beats fixed-schedule by switching off empty rooms (CTL-02) | **PASS** | `OccupancyRulePolicy` (per-room sim-minute empty timer, `vacancy_min=15`, current-obs only — no-timetable guard test enforces it). Exact-timing tests (ON at 5/10 min, OFF on 3rd empty call) prove the switch-off mechanism at unit level. Live rerun weekday: C2 43.972 kWh, **saved 9.4±1.1%** vs C1 (SUMMARY 5-seed: 10.7±1.4%). Mechanism shows where it should — on weekdays. |
| 3 | C3 setback compared side-by-side with C1/C2 in one 24h profile (CTL-03) | **PASS** | `SetbackPolicy` (ON hold <15 min, REDUCED 15–60 min, OFF ≥60 min) + `ctrl/harness.py::run_controller` + `ctrl/compare.py` CLI (paired seeds, crash-resumable CSVs, 13-col summary.csv). Live rerun regenerated `summary.csv` (all 13 columns incl. energy/cost/CO₂/comfort mean±std) and `fig_24h_profile.png` (106 KB, 3 power lines + occupancy shade). REDUCED-vs-OFF (30 min) and OFF-at-60-min tests pass; determinism test (byte-identical ×3 controllers) passes. |

## Weekend Negative Savings — Judgment

Rerun confirms the honest negative: C2 −3.6%, C3 −9.0% vs C1 on weekend (2 seeds; SUMMARY 5-seed: −1.8%, −7.3%). **This does not fail the phase.** Reasoning: C1's weekend schedule is nearly all-OFF already (only classroom_A 10:00–14:00), i.e. near-optimal, so C2/C3's post-block hold penalty (REDUCED 60 min after last class vs C1's sharp OFF) legitimately costs energy on a near-empty building. The deviation log in 03-02-SUMMARY shows the team already caught and fixed the *spurious* version of this (midnight hold-ON transient, commit 693cd4b); the residual is genuine hold behavior, kept as-reported with a C4 motivation note. Criterion 2 is about the switch-off mechanism showing — it shows decisively on weekdays (10.7%) plus unit-level timing tests. No comfort-blind claims anywhere: every row carries comfort %.

## Full Evidence

- **Tests:** `python -m pytest tests/ -q` → **70 passed, 2 skipped** (matches SUMMARY claim; skips pre-existing).
- **Harness rerun:** `python ctrl/compare.py --controllers c1,c2,c3 --scenarios weekday,weekend --seeds 2` → 6 rows, weekday C1 48.542 / C2 43.972 (−9.4%) / C3 46.639 (−3.9%); weekend negatives reproduced. summary.csv columns verified: controller, scenario, n_seeds, energy_kwh_mean/std, saved_pct_vs_c1_mean/std, cost_rs_mean/std, co2_kg_mean/std, comfort_pct_mean/std. fig_24h_profile.png written.
- **Artifacts confirmed substantive (not stubs):** all three policies implement real step() logic over `obs`; harness drives `BuildingSim` directly with CONTROL_HOOK_STEPS hold + TelemetryLogger; cost/CO₂ join hourly grid series (no-scalar-carbon grep gate test guards this); comfort is occupied-step-weighted, not a naive mean.
- **Wiring:** harness → BuildingSim/metrics/grid verified by import + passing end-to-end tests; bridge-compat proven by `test_policy_bridge.py` (C2 through TelemetryBridge.tick, 30 sim-min, valid command enums). Direct-sim eval path per D-07/D-08 is as decided.
- **Anti-patterns:** grep for TODO/FIXME/XXX/placeholder/"Not implemented" in `ctrl/*.py` → zero hits.
- **Locked decisions honored:** D-01..D-14 spot-checked — schedules in `schedules.py` (D-01), `vacancy_min` param (D-04), REDUCED-60-then-OFF (D-05/D-06), direct-sim harness (D-07), PAIRED_SEEDS (D-09), comfort in every row (D-10), single 24h figure only (D-12), rerun-equality test (D-13). Lights-follow-occupancy documented once in `ctrl/__init__.py`.

## Issues (non-blocking)

1. **Minor — `--out` constrained to `results/comparison/`:** `resolve_run_dir` rejects any `--out` outside `results/comparison/` (e.g. `--out results/verify3` → ValueError), so the flag only supports subdirectories of the default root. Verification used `--out results/comparison/verify3` successfully. Not a phase failure (default path is the documented contract), but the CLI help implies a general output dir — suggest either documenting the constraint or fixing the guard. Cleanup done: `results/comparison/verify3/` removed after verification.

## Overall

**PASS 3/3.** First kWh number is real, reproducible, and honestly reported — including the weekend negative that a weaker phase would have hidden. Hard gate satisfied: C4 work may proceed.
