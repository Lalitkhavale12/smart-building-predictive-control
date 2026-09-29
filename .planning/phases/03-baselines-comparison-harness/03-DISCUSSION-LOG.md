# Phase 03 Discussion Log

**Date:** 2026-09-29
**Mode:** --auto (all gray areas auto-selected with recommended defaults, single pass)

## Areas Discussed

### C1 fixed-schedule
- Options: room-type tables in schedules.py (recommended) / hardcoded
- Selected: schedules.py, weekday/weekend/heatwave vocabulary

### C2 occupancy-rule
- Options: 15-min vacancy param (recommended)
- Selected: vacancy_min=15, per-room timer, ON when occupied

### C3 setback
- Options: REDUCED 60 min then OFF (recommended)
- Selected: yes; occupied always ON

### Harness shape
- Options: direct sim.step for speed + one bridge wiring test (recommended) / through MQTT
- Selected: direct sim, paired PAIRED_SEEDS 0-4, mean±std

### Metrics & output
- Options: energy/cost/CO2/comfort columns + 24h-profile figure now, Pareto later (recommended)
- Selected: compare.py CLI → summary.csv + fig_24h_profile.png

### Determinism
- Options: rerun-equality test + <5 min full matrix (recommended)
- Selected: yes

## Deferred Ideas
- None

## the agent's Discretion
- Schedule tables, setback durations, figure style, summary.csv columns; lights follow occupancy
