# Phase 04 Discussion Log

**Date:** 2026-09-29
**Mode:** --auto (all gray areas auto-selected with recommended defaults, single pass)

## Areas Discussed

### Forecast target & horizon
- Options: occupancy + demand at 30/60 min (recommended) / more horizons
- Selected: 30-min + 60-min only

### Models
- Options: RF + HistGB vs one small LSTM, tie prefers simpler + persistence baseline (recommended)
- Selected: yes; single 1-2 layer LSTM, no architecture search

### Leakage protocol
- Options: chronological + walk-forward, shuffle forbidden + grep-guarded (recommended)
- Selected: yes

### C4 mechanism
- Options: C3 + forecast overlay (pre-cool/early-off), degrades to C3 on None (recommended)
- Selected: yes; in-process forecast calls, never MQTT

### Ablation & public data
- Options: C4-with vs C4-as-C3 gap + UCI Appliances first (recommended)
- Selected: yes; time-boxed fetch, synthetic-only fallback documented

## Deferred Ideas
- None

## the agent's Discretion
- Lags, hyperparams, LSTM size, adapter mapping, C4 thresholds as params
