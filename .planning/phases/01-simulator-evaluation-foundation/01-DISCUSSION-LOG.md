# Phase 01 Discussion Log

**Date:** 2026-09-29
**Mode:** --auto (all gray areas auto-selected with recommended defaults, single pass)

## Areas Discussed

### Thermal model
- Options: 1R1C (recommended) / 2R2C
- Selected: 1R1C in NumPy
- Notes: spike 2R2C only if sanity numbers fail

### Rooms & timestep
- Options: 1-min sim + 5-min control hook (recommended) / 5-min only
- Selected: 1-min sim, 5-min control hook, 4 rooms

### Seeding & reproducibility
- Options: explicit seed arg + paired seeds (recommended)
- Selected: numpy Generator(PCG64), CLI seed, mean±std helper

### Carbon/ToU series
- Options: build hourly series now (recommended) / defer to Phase 5
- Selected: build now, consume in Phase 5; CEA annual + daily shape, transparent assumption

### Comfort metric
- Options: 22-26C + 30-60% RH (recommended)
- Selected: yes

### CSV schema & interface
- Options: per-step CSV + BasePolicy stub (recommended)
- Selected: timestamp/room/T_in/T_out/RH/occupancy/HVAC/power + sim.step/policy.step stub

## Deferred Ideas
- None

## the agent's Discretion
- R/C values, Q_hvac sizing, sim/ layout
