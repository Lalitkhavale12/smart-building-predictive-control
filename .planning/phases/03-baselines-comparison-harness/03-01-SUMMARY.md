# Phase 03 Plan 01: C1 + C2 Baselines Summary

**Status:** complete — C1 fixed-schedule (CTL-01) and C2 occupancy-rule
(CTL-02) implemented as `BasePolicy` subclasses, proven end-to-end against
`BuildingSim`. First kWh number: C1 weekday seed 0 = 48.583 kWh.

## What Was Built

- `ctrl/__init__.py` — package docstring documenting the lights rule once:
  lights follow occupancy (ON iff currently occupied) for all baselines.
- `ctrl/schedules.py` — room-type wall-clock tables (`weekday`/`weekend`/
  `heatwave` vocabulary); classrooms ON 08:00–18:00, office 09:00–18:00,
  lab four booked blocks incl. 18:00–20:00 evening, weekend all OFF except
  classroom_A 10:00–14:00; no gap-skipping; `is_on(room, minute, day_type)`
  helper; heatwave identical to weekday by design.
- `ctrl/baselines.py` — `FixedSchedulePolicy` (call-count ×
  CONTROL_HOOK_STEPS wall clock, hvac from schedule, lights from occupancy)
  and `OccupancyRulePolicy` (per-room empty timer in sim-minutes,
  `vacancy_min=15` default; current-obs occupancy only, no TIMETABLES).
- `tests/test_baselines.py` — 11 tests: C1 end-to-end kWh, C2 exact-timing
  (5/10 min ON, OFF on 3rd empty call), `vacancy_min=5`, reset, lights,
  no-timetable guard, schedule boundaries, heatwave parity, weekend < weekday.

## Test Results

- `tests/test_baselines.py`: 11 passed.
- Full suite `tests/`: 62 passed, 2 skipped (pre-existing skips).
- Measured (seed 0): C1 weekday 48.583 kWh > AlwaysOff 0.000 kWh;
  C1 weekend 5.450 kWh < C1 weekday 48.583 kWh.

## Deviations

None — plan executed exactly as written.

## Threat Flags

None — no new surface beyond the plan's threat model (T-03-01 mitigated by
sim-minute counter + exact-timing test; T-03-02 guarded by the
no-TIMETABLES-in-baselines test; T-03-03 accepted per plan).

## Commits

- f7c18e5 feat(03-01): C1 fixed-schedule baseline end-to-end with kWh tracer
- 8fa00e6 feat(03-01): C2 occupancy-rule with sim-minute vacancy counter
- c320a40 test(03-01): schedule boundary edges plus weekend below weekday energy

## Self-Check: PASSED

All files exist; all three commits verified via `git log`.
